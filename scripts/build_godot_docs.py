#!/usr/bin/env python3
"""Build an Agent-oriented local Markdown copy of the Godot documentation.

This is a deployment tool. It downloads a pinned godot-docs source snapshot,
builds the official reStructuredText sources with Sphinx in an isolated virtual
environment, converts the resulting article HTML to Markdown, validates the
corpus, and publishes it atomically.

The script itself uses only the Python standard library. Build dependencies are
installed into a temporary virtual environment and never into the caller's
Python environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCRIPT_VERSION = "0.2.0"
MANIFEST_SCHEMA_VERSION = 2
REPOSITORY = "godotengine/godot-docs"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
GITHUB_API_ROOT = "https://api.github.com"
USER_AGENT = f"godot-local-docs-ref/{SCRIPT_VERSION}"
MIN_BUILD_PYTHON = (3, 10)
CONVERTER_REQUIREMENTS = (
    "beautifulsoup4==4.15.0",
    "markdownify==1.2.3",
)
EXCLUDED_SOURCE_PATHS = {
    "404.rst",
}
SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_REFERENCES_ROOT = SKILL_DIR / "references" / "godot-docs"


class BuildError(RuntimeError):
    """An expected, user-facing build failure."""


def log(message: str) -> None:
    print(message, flush=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_version(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", value):
        raise argparse.ArgumentTypeError(
            "version must start with a letter or digit and contain only letters, digits, '.', '_', '+', or '-'"
        )
    return value


def normalize_source_path(value: str) -> str:
    candidate = value.strip().replace("\\", "/")
    if candidate.endswith(".md") or candidate.endswith(".html"):
        candidate = str(Path(candidate).with_suffix(".rst")).replace("\\", "/")
    if not candidate.endswith(".rst"):
        candidate += ".rst"
    path = Path(candidate)
    if path.is_absolute() or ".." in path.parts:
        raise argparse.ArgumentTypeError("--only paths must be relative source .rst paths")
    return path.as_posix()


def default_output(version: str) -> Path:
    return DEFAULT_REFERENCES_ROOT / version


def request_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def read_url(url: str, timeout: int = 60, attempts: int = 3) -> bytes:
    last_error: Optional[BaseException] = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, headers=request_headers())
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt == attempts:
                break
            time.sleep(2 ** (attempt - 1))
    raise BuildError(f"failed to download {url}: {last_error}")


def download_file(url: str, destination: Path, timeout: int = 60, attempts: int = 3) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: Optional[BaseException] = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, headers=request_headers())
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                with destination.open("wb") as handle:
                    shutil.copyfileobj(response, handle)
            return
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
            destination.unlink(missing_ok=True)
            if attempt == attempts:
                break
            time.sleep(2 ** (attempt - 1))
    raise BuildError(f"failed to download {url}: {last_error}")


def resolve_github_commit(repository: str, ref: str) -> str:
    if re.fullmatch(r"[0-9a-fA-F]{40}", ref):
        return ref.lower()
    encoded_repository = urllib.parse.quote(repository, safe="/")
    encoded_ref = urllib.parse.quote(ref, safe="")
    url = f"{GITHUB_API_ROOT}/repos/{encoded_repository}/commits/{encoded_ref}"
    try:
        payload = json.loads(read_url(url).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BuildError(f"GitHub returned invalid commit metadata for {repository}@{ref}: {error}") from error
    commit = payload.get("sha")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise BuildError(f"GitHub did not return a valid commit for {repository}@{ref}")
    return commit.lower()


def is_within_directory(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def extract_zip_safely(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if not members:
            raise BuildError(f"source archive is empty: {archive}")
        for member in members:
            member_path = (destination / member.filename).resolve()
            if not is_within_directory(root, member_path):
                raise BuildError(f"unsafe path in source archive: {member.filename}")
        bundle.extractall(destination)

    top_levels = sorted(
        path for path in destination.iterdir() if path.is_dir() and not path.name.startswith("__MACOSX")
    )
    if len(top_levels) != 1:
        raise BuildError(f"expected one source directory in {archive}, found {len(top_levels)}")
    return top_levels[0]


def validate_source_archive_commit(archive: Path, commit: str) -> None:
    expected_root = f"godot-docs-{commit}"
    try:
        with zipfile.ZipFile(archive) as bundle:
            roots = {
                Path(member.filename).parts[0]
                for member in bundle.infolist()
                if member.filename and Path(member.filename).parts
            }
    except (OSError, zipfile.BadZipFile) as error:
        raise BuildError(f"cannot read cached source archive {archive}: {error}") from error
    if roots != {expected_root}:
        found = ", ".join(sorted(roots)) or "no top-level directory"
        raise BuildError(
            f"cached source archive does not match commit {commit}: expected {expected_root}, found {found}"
        )


def python_version(executable: Path) -> Tuple[int, int, int]:
    command = [
        str(executable),
        "-c",
        "import json, sys; print(json.dumps(list(sys.version_info[:3])))",
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        values = json.loads(result.stdout.strip())
        return int(values[0]), int(values[1]), int(values[2])
    except (OSError, subprocess.CalledProcessError, ValueError, json.JSONDecodeError, IndexError) as error:
        raise BuildError(f"cannot execute build Python {executable}: {error}") from error


def require_build_python(executable: Path) -> Tuple[int, int, int]:
    version = python_version(executable)
    if version[:2] < MIN_BUILD_PYTHON:
        required = ".".join(str(part) for part in MIN_BUILD_PYTHON)
        actual = ".".join(str(part) for part in version)
        raise BuildError(
            f"Godot's Sphinx build requires Python {required}+; {executable} is Python {actual}. "
            "Pass a newer interpreter with --python."
        )
    return version


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def run_logged(command: Sequence[str], log_path: Path, cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None) -> None:
    rendered = " ".join(command)
    log(f"$ {rendered}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as build_log:
        build_log.write(f"\n$ {rendered}\n")
        try:
            process = subprocess.Popen(
                list(command),
                cwd=str(cwd) if cwd else None,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as error:
            raise BuildError(f"failed to start command {command[0]}: {error}") from error

        assert process.stdout is not None
        tail: List[str] = []
        for line in process.stdout:
            build_log.write(line)
            tail.append(line.rstrip())
            tail = tail[-30:]
            if line.startswith(
                ("Running Sphinx", "building [", "writing output", "build succeeded", "Converted ")
            ):
                print(line, end="", flush=True)
        return_code = process.wait()
    if return_code != 0:
        excerpt = "\n".join(tail)
        raise BuildError(
            f"command failed with exit code {return_code}: {rendered}\n"
            f"Last output:\n{excerpt}\nFull log: {log_path}"
        )


def create_build_environment(build_python: Path, venv_dir: Path, source_dir: Path, log_path: Path) -> Path:
    require_build_python(build_python)

    run_logged([str(build_python), "-m", "venv", str(venv_dir)], log_path)
    python = venv_python(venv_dir)
    requirements = source_dir / "requirements.txt"
    if not requirements.is_file():
        raise BuildError(f"upstream requirements.txt not found in {source_dir}")
    run_logged(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            "-r",
            str(requirements),
            *CONVERTER_REQUIREMENTS,
        ],
        log_path,
    )
    return python


def installed_versions(python: Path) -> Dict[str, str]:
    names = [
        "Sphinx",
        "sphinx-rtd-theme",
        "sphinx-tabs",
        "beautifulsoup4",
        "markdownify",
    ]
    code = (
        "import importlib.metadata as m, json; "
        f"names={names!r}; "
        "print(json.dumps({name: m.version(name) for name in names}, sort_keys=True))"
    )
    try:
        result = subprocess.run([str(python), "-c", code], check=True, capture_output=True, text=True)
        payload = json.loads(result.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        raise BuildError(f"failed to inspect build dependency versions: {error}") from error
    return {str(key): str(value) for key, value in payload.items()}


def validate_source_tree(source_dir: Path) -> None:
    for required in ("conf.py", "requirements.txt", "LICENSE.txt", "index.rst"):
        if not (source_dir / required).is_file():
            raise BuildError(f"upstream source tree is missing {required}: {source_dir}")


def reuse_build_assets(reuse_root: Path, commit: str) -> Tuple[Path, Path, Path, str, Dict[str, str]]:
    archive = reuse_root / "godot-docs.zip"
    source_dir = reuse_root / "source" / f"godot-docs-{commit}"
    python = venv_python(reuse_root / "venv")
    if not archive.is_file():
        raise BuildError(f"cached source archive not found: {archive}")
    validate_source_archive_commit(archive, commit)
    validate_source_tree(source_dir)
    if not python.is_file():
        raise BuildError(f"cached build Python not found: {python}")
    packages = installed_versions(python)
    return archive, source_dir, python, sha256_file(archive), packages


def validate_only_paths(source_dir: Path, values: Sequence[str]) -> List[str]:
    normalized: List[str] = []
    for value in values:
        source_path = normalize_source_path(value)
        if source_path in EXCLUDED_SOURCE_PATHS:
            raise BuildError(f"excluded generated/UI page cannot be selected: {source_path}")
        if not (source_dir / source_path).is_file():
            raise BuildError(f"selected source page does not exist: {source_path}")
        if source_path not in normalized:
            normalized.append(source_path)
    return normalized


def build_html(
    python: Path,
    source_dir: Path,
    html_dir: Path,
    doctrees_dir: Path,
    version: str,
    jobs: str,
    only_paths: Sequence[str],
    log_path: Path,
) -> None:
    environment = os.environ.copy()
    environment.pop("SPHINX_TAGS", None)
    environment.update(
        {
            "READTHEDOCS_VERSION": version,
            "READTHEDOCS_LANGUAGE": "en",
            "PYTHONUTF8": "1",
        }
    )
    command = [
        str(python),
        "-m",
        "sphinx",
        "-b",
        "html",
        "-j",
        jobs,
        "-d",
        str(doctrees_dir),
        str(source_dir),
        str(html_dir),
    ]
    command.extend(str(source_dir / path) for path in only_paths)
    run_logged(command, log_path, cwd=source_dir, env=environment)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def invoke_converter(
    python: Path,
    html_dir: Path,
    source_dir: Path,
    output_dir: Path,
    fragment_path: Path,
    version: str,
    source_ref: str,
    source_commit: str,
    only_paths: Sequence[str],
    log_path: Path,
) -> None:
    command = [
        str(python),
        str(Path(__file__).resolve()),
        "__convert-html",
        "--html-dir",
        str(html_dir),
        "--source-dir",
        str(source_dir),
        "--output",
        str(output_dir),
        "--fragment",
        str(fragment_path),
        "--version",
        version,
        "--source-ref",
        source_ref,
        "--source-commit",
        source_commit,
    ]
    for path in only_paths:
        command.extend(["--only", path])
    run_logged(command, log_path)


def write_attribution(output_dir: Path, version: str, ref: str, commit: str) -> None:
    content = f"""# Source attribution

This local corpus was generated from the official Godot Engine documentation.

- Repository: {REPOSITORY_URL}
- Requested ref: `{ref}`
- Resolved commit: `{commit}`
- Documentation version: `{version}`
- Generator: `build_godot_docs.py` {SCRIPT_VERSION}

Except for pages under `classes/`, the upstream documentation is licensed under
CC BY 3.0 and is attributed to Juan Linietsky, Ariel Manzur, and the Godot
community. Pages under `classes/` are derived from the Godot Engine source and
are licensed under the MIT License. See the accompanying license files and each
page's frontmatter.
"""
    (output_dir / "SOURCE-ATTRIBUTION.md").write_text(content, encoding="utf-8")


def validate_corpus(output_dir: Path, files: Sequence[Dict[str, Any]]) -> None:
    if not files:
        raise BuildError("conversion produced no Markdown pages")
    seen: set[str] = set()
    for entry in files:
        relative = entry.get("path")
        expected_hash = entry.get("sha256")
        if not isinstance(relative, str) or not relative.endswith(".md"):
            raise BuildError(f"invalid manifest page path: {relative!r}")
        if relative in seen:
            raise BuildError(f"duplicate output page in manifest: {relative}")
        seen.add(relative)
        path = output_dir / relative
        if not path.is_file():
            raise BuildError(f"manifest page is missing: {relative}")
        if sha256_file(path) != expected_hash:
            raise BuildError(f"manifest hash mismatch: {relative}")


def publish_atomically(prepared_dir: Path, output_dir: Path, force: bool) -> None:
    output_dir = output_dir.resolve()
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists() and not force:
        raise BuildError(f"output already exists: {output_dir}; use --force to replace it")

    staging = parent / f".{output_dir.name}.staging-{uuid.uuid4().hex}"
    backup = parent / f".{output_dir.name}.backup-{uuid.uuid4().hex}"
    try:
        shutil.copytree(prepared_dir, staging)
        if output_dir.exists():
            output_dir.rename(backup)
        staging.rename(output_dir)
    except BaseException:
        if not output_dir.exists() and backup.exists():
            backup.rename(output_dir)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    if backup.exists():
        shutil.rmtree(backup)


def build(args: argparse.Namespace) -> Path:
    version = args.version
    source_ref = args.ref or version
    output_dir = (args.output or default_output(version)).expanduser().resolve()
    build_python = Path(args.python).expanduser().resolve()
    reuse_root = Path(args.reuse_workdir).expanduser().resolve() if args.reuse_workdir else None
    if reuse_root:
        if not reuse_root.is_dir():
            raise BuildError(f"reusable work directory not found: {reuse_root}")
        work_parent = reuse_root
    else:
        require_build_python(build_python)
        work_parent = Path(args.work_dir).expanduser().resolve() if args.work_dir else None
    if work_parent and not reuse_root:
        work_parent.mkdir(parents=True, exist_ok=True)
    prefix = "godot-docs-reuse-run-" if reuse_root else "godot-docs-build-"
    work_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=str(work_parent) if work_parent else None))
    log_path = work_dir / "build.log"
    log(f"Work directory: {work_dir}")

    try:
        log(f"[1/7] Resolving {REPOSITORY}@{source_ref}")
        commit = resolve_github_commit(REPOSITORY, source_ref)
        log(f"Resolved commit: {commit}")

        archive_url = f"https://codeload.github.com/{REPOSITORY}/zip/{commit}"
        if reuse_root:
            log(f"[2/7] Reusing the pinned source archive and tree from {reuse_root}")
            archive, source_dir, python, archive_hash, packages = reuse_build_assets(reuse_root, commit)
            log("[3/7] Reusing the validated isolated Sphinx build environment")
        else:
            log("[2/7] Downloading the pinned source archive")
            archive = work_dir / "godot-docs.zip"
            download_file(archive_url, archive)
            archive_hash = sha256_file(archive)
            source_dir = extract_zip_safely(archive, work_dir / "source")
            validate_source_tree(source_dir)

            log("[3/7] Creating an isolated Sphinx build environment")
            python = create_build_environment(build_python, work_dir / "venv", source_dir, log_path)
            packages = installed_versions(python)
        only_paths = validate_only_paths(source_dir, args.only)

        log("[4/7] Building the official documentation HTML with Sphinx")
        html_dir = work_dir / "html"
        build_html(
            python,
            source_dir,
            html_dir,
            work_dir / "doctrees",
            version,
            args.jobs,
            only_paths,
            log_path,
        )

        log("[5/7] Converting article HTML to Agent-oriented Markdown")
        prepared_dir = work_dir / "prepared"
        fragment_path = work_dir / "pages.json"
        invoke_converter(
            python,
            html_dir,
            source_dir,
            prepared_dir,
            fragment_path,
            version,
            source_ref,
            commit,
            only_paths,
            log_path,
        )
        try:
            files = json.loads(fragment_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise BuildError(f"converter did not produce valid page metadata: {error}") from error
        if not isinstance(files, list):
            raise BuildError("converter page metadata must be a list")

        log("[6/7] Writing provenance, licenses, and manifest")
        shutil.copy2(source_dir / "LICENSE.txt", prepared_dir / "LICENSE-GODOT-DOCS.txt")
        engine_license_url = f"https://raw.githubusercontent.com/godotengine/godot/{urllib.parse.quote(version, safe='')}/LICENSE.txt"
        download_file(engine_license_url, prepared_dir / "LICENSE-GODOT-CLASSES.txt")
        write_attribution(prepared_dir, version, source_ref, commit)
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generator": {
                "name": "build_godot_docs.py",
                "version": SCRIPT_VERSION,
            },
            "godot_docs": {
                "version": version,
                "repository": REPOSITORY_URL,
                "source_ref": source_ref,
                "source_commit": commit,
                "source_archive_url": archive_url,
                "source_archive_sha256": archive_hash,
            },
            "build": {
                "generated_at": utc_now(),
                "page_count": len(files),
                "selected_sources": only_paths or None,
                "reused_build_assets": bool(reuse_root),
                "python": ".".join(str(part) for part in python_version(python)),
                "packages": packages,
            },
            "licenses": {
                "manual": {
                    "spdx": "CC-BY-3.0",
                    "file": "LICENSE-GODOT-DOCS.txt",
                    "attribution": "Juan Linietsky, Ariel Manzur, and the Godot community",
                },
                "classes": {
                    "spdx": "MIT",
                    "file": "LICENSE-GODOT-CLASSES.txt",
                    "source": engine_license_url,
                },
            },
            "output_contract": {
                "format": "markdown",
                "frontmatter": "per-page provenance preserved",
                "class_internal_links": "plain text",
                "manual_internal_links": "relative Markdown links",
                "external_links": "preserved",
                "images": "official absolute URLs",
            },
            "files": sorted(files, key=lambda entry: str(entry.get("path", ""))),
        }
        write_json(prepared_dir / "manifest.json", manifest)
        validate_corpus(prepared_dir, files)

        log("[7/7] Publishing the validated corpus atomically")
        publish_atomically(prepared_dir, output_dir, args.force)
        log(f"Built {len(files)} pages at {output_dir}")
        return output_dir
    finally:
        if args.keep_workdir:
            log(f"Kept work directory: {work_dir}")
        else:
            shutil.rmtree(work_dir, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local Agent-oriented Markdown from the official Godot documentation source.",
        epilog=(
            "The command downloads the complete pinned godot-docs source archive (currently about 200 MB), "
            "creates a temporary virtual environment, and needs additional temporary disk space. "
            "--only limits the pages built, not the source download."
        ),
    )
    parser.add_argument(
        "--version",
        type=validate_version,
        default="4.7",
        help="Godot documentation version and output directory name (default: 4.7)",
    )
    parser.add_argument(
        "--ref",
        help="godot-docs Git ref to resolve and pin (default: same as --version)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="output directory (default: <skill>/references/godot-docs/<version>)",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python 3.10+ executable used for the isolated Sphinx environment",
    )
    parser.add_argument(
        "--jobs",
        default="auto",
        help="parallel Sphinx jobs: 'auto' or a positive integer (default: auto)",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="SOURCE.rst",
        help="build only a selected source page; repeat for smoke tests",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace an existing generated corpus after the new one validates",
    )
    work_group = parser.add_mutually_exclusive_group()
    work_group.add_argument(
        "--work-dir",
        type=Path,
        help="parent directory for temporary build files",
    )
    work_group.add_argument(
        "--reuse-workdir",
        type=Path,
        help="reuse archive, source tree, and virtual environment from a previous --keep-workdir build",
    )
    parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="keep temporary source, HTML, virtual environment, and logs",
    )
    return parser


def validate_jobs(value: str) -> str:
    if value == "auto":
        return value
    try:
        number = int(value)
    except ValueError as error:
        raise BuildError("--jobs must be 'auto' or a positive integer") from error
    if number < 1:
        raise BuildError("--jobs must be 'auto' or a positive integer")
    return str(number)


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def infer_code_language(element: Any) -> Optional[str]:
    aliases = {
        "c#": "csharp",
        "cs": "csharp",
        "gdscript3": "gdscript",
        "javascript": "javascript",
        "js": "javascript",
        "shell": "bash",
        "console": "text",
        "default": "text",
    }
    current = element
    for _ in range(5):
        if current is None:
            break
        classes = current.get("class", []) if hasattr(current, "get") else []
        for class_name in classes:
            for prefix in ("highlight-", "language-"):
                if class_name.startswith(prefix):
                    language = class_name[len(prefix) :].casefold()
                    return aliases.get(language, language)
        current = getattr(current, "parent", None)
    return None


def rewrite_relative_html_link(href: str) -> str:
    parsed = urllib.parse.urlsplit(href)
    if parsed.scheme or parsed.netloc:
        return href
    if parsed.path.endswith(".html"):
        path = parsed.path[:-5] + ".md"
        return urllib.parse.urlunsplit(("", "", path, parsed.query, parsed.fragment))
    return href


def is_internal_document_href(href: str, version: str) -> bool:
    parsed = urllib.parse.urlsplit(href)
    if not parsed.scheme and not parsed.netloc:
        return True
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.casefold() != "docs.godotengine.org":
        return False
    return parsed.path.startswith(f"/en/{version}/")


def clean_markdown(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = re.sub(r"\[\s*\]\(\s*\)", "", value)
    return value.strip() + "\n"


def prepare_article(
    soup: Any,
    article: Any,
    source_url: str,
    version: str,
    compact_class_links: bool,
) -> None:
    for selector in (
        "script",
        "style",
        "noscript",
        "form",
        "a.headerlink",
        ".viewcode-link",
        ".rst-footer-buttons",
        ".article-status",
        ".user-content-notes",
    ):
        for node in article.select(selector):
            node.decompose()

    for tab_group in article.select(".sphinx-tabs-tabgroup, [role='tablist']"):
        container = tab_group.parent
        labels: Dict[str, str] = {}
        for button in tab_group.find_all(["button", "div"], recursive=True):
            target = button.get("aria-controls")
            label = button.get_text(" ", strip=True)
            if target and label:
                labels[target] = label
        if container is not None:
            for panel in container.select(".sphinx-tabs-panel"):
                label = labels.get(panel.get("id", ""))
                if not label:
                    labelled_by = panel.get("aria-labelledby")
                    if labelled_by:
                        label_node = soup.find(id=labelled_by)
                        if label_node:
                            label = label_node.get_text(" ", strip=True)
                if label:
                    paragraph = soup.new_tag("p")
                    strong = soup.new_tag("strong")
                    strong.string = label
                    paragraph.append(strong)
                    panel.insert(0, paragraph)
        tab_group.decompose()

    for admonition in article.select("div.admonition"):
        classes = [name for name in admonition.get("class", []) if name != "admonition"]
        kind = classes[0] if classes else "note"
        title_node = admonition.select_one(".admonition-title")
        title = title_node.get_text(" ", strip=True) if title_node else kind.replace("-", " ").title()
        if title_node:
            title_node.decompose()
        quote = soup.new_tag("blockquote")
        marker = soup.new_tag("p")
        strong = soup.new_tag("strong")
        strong.string = f"{title}:"
        marker.append(strong)
        quote.append(marker)
        for child in list(admonition.contents):
            quote.append(child.extract())
        admonition.replace_with(quote)

    for anchor in list(article.find_all("a", href=True)):
        href = anchor["href"]
        if compact_class_links and is_internal_document_href(href, version):
            if anchor.get_text(" ", strip=True) in {"🔗", ""}:
                anchor.decompose()
            else:
                anchor.unwrap()
            continue
        anchor["href"] = rewrite_relative_html_link(href)
    for image in article.find_all("img", src=True):
        image["src"] = urllib.parse.urljoin(source_url, image["src"])
        if not image.get("alt"):
            image["alt"] = "Godot documentation image"


def convert_page(
    html_path: Path,
    html_dir: Path,
    source_dir: Path,
    output_dir: Path,
    version: str,
    source_ref: str,
    source_commit: str,
) -> Dict[str, Any]:
    try:
        from bs4 import BeautifulSoup
        from markdownify import MarkdownConverter
    except ImportError as error:
        raise BuildError(f"converter dependency is missing in the isolated environment: {error}") from error

    relative_html = html_path.relative_to(html_dir)
    source_relative = relative_html.with_suffix(".rst")
    source_path = source_dir / source_relative
    source_url = f"https://docs.godotengine.org/en/{version}/{source_relative.with_suffix('.html').as_posix()}"
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    article = (
        soup.select_one('[itemprop="articleBody"]')
        or soup.select_one('div[role="main"]')
        or soup.select_one("div.document")
    )
    if article is None:
        raise BuildError(f"article body not found in {relative_html.as_posix()}")
    heading = article.find("h1")
    title = heading.get_text(" ", strip=True).removesuffix("").strip() if heading else source_relative.stem
    if not title:
        title = source_relative.stem

    is_class_reference = bool(source_relative.parts and source_relative.parts[0] == "classes")
    prepare_article(soup, article, source_url, version, is_class_reference)
    converter = MarkdownConverter(
        heading_style="ATX",
        bullets="-",
        code_language_callback=infer_code_language,
        table_infer_header=True,
        escape_underscores=False,
        wrap=False,
        keep_inline_images_in=["td", "th"],
    )
    markdown = clean_markdown(converter.convert_soup(article))
    license_id = "MIT" if is_class_reference else "CC-BY-3.0"
    frontmatter = "\n".join(
        (
            "---",
            f"title: {yaml_string(title)}",
            f"godot_version: {yaml_string(version)}",
            f"source_ref: {yaml_string(source_ref)}",
            f"source_commit: {yaml_string(source_commit)}",
            f"source_path: {yaml_string(source_relative.as_posix())}",
            f"source_url: {yaml_string(source_url)}",
            f"license: {yaml_string(license_id)}",
            f"generated_by: {yaml_string('build_godot_docs.py')}",
            "---",
            "",
        )
    )
    output_relative = source_relative.with_suffix(".md")
    output_path = output_dir / output_relative
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(frontmatter + markdown, encoding="utf-8", newline="\n")
    return {
        "path": output_relative.as_posix(),
        "source_path": source_relative.as_posix(),
        "title": title,
        "license": license_id,
        "bytes": output_path.stat().st_size,
        "sha256": sha256_file(output_path),
    }


def internal_convert(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--html-dir", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fragment", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--only", action="append", default=[])
    args = parser.parse_args(argv)

    html_dir = args.html_dir.resolve()
    source_dir = args.source_dir.resolve()
    output_dir = args.output.resolve()
    only = set(args.only)
    candidates: List[Path] = []
    for html_path in sorted(html_dir.rglob("*.html")):
        source_relative = html_path.relative_to(html_dir).with_suffix(".rst")
        source_name = source_relative.as_posix()
        if source_name in EXCLUDED_SOURCE_PATHS:
            continue
        if only and source_name not in only:
            continue
        if (source_dir / source_relative).is_file():
            candidates.append(html_path)

    if only:
        built_sources = {path.relative_to(html_dir).with_suffix(".rst").as_posix() for path in candidates}
        missing = sorted(only - built_sources)
        if missing:
            raise BuildError(f"Sphinx did not build selected pages: {', '.join(missing)}")

    files: List[Dict[str, Any]] = []
    for index, html_path in enumerate(candidates, 1):
        files.append(
            convert_page(
                html_path,
                html_dir,
                source_dir,
                output_dir,
                args.version,
                args.source_ref,
                args.source_commit,
            )
        )
        if index % 100 == 0:
            log(f"Converted {index}/{len(candidates)} pages")
    write_json(args.fragment, files)
    log(f"Converted {len(files)} pages")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if values and values[0] == "__convert-html":
        try:
            return internal_convert(values[1:])
        except BuildError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2

    parser = build_parser()
    args = parser.parse_args(values)
    try:
        args.jobs = validate_jobs(args.jobs)
        args.only = [normalize_source_path(value) for value in args.only]
        build(args)
        return 0
    except (BuildError, OSError, zipfile.BadZipFile) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
