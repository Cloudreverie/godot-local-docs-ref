from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_godot_docs.py"
SPEC = importlib.util.spec_from_file_location("build_godot_docs", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
build_godot_docs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_godot_docs)


class InputValidationTests(unittest.TestCase):
    def test_dot_version_is_a_safe_directory_component(self) -> None:
        self.assertEqual(build_godot_docs.validate_version("4.7"), "4.7")

    def test_version_rejects_path_traversal(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            build_godot_docs.validate_version("../4.7")

    def test_only_path_normalizes_html_and_rejects_parent_segments(self) -> None:
        self.assertEqual(
            build_godot_docs.normalize_source_path("classes/class_node.html"),
            "classes/class_node.rst",
        )
        with self.assertRaises(argparse.ArgumentTypeError):
            build_godot_docs.normalize_source_path("../class_node.rst")

    def test_old_python_is_rejected_before_build_work(self) -> None:
        executable = Path("/example/python")
        with mock.patch.object(build_godot_docs, "python_version", return_value=(3, 9, 9)):
            with self.assertRaisesRegex(build_godot_docs.BuildError, "Python 3.10"):
                build_godot_docs.require_build_python(executable)


class BuildEnvironmentTests(unittest.TestCase):
    def test_only_required_configuration_is_inherited(self) -> None:
        supplied = {
            "PATH": os.defpath, "https_proxy": "http://proxy.example:8080",
            "SSL_CERT_FILE": "/example/ca.pem", "SystemRoot": "C:/Windows",
            "GITHUB_TOKEN": "fake-github-secret", "OTHER_API_KEY": "fake-api-secret",
            "PYTHONPATH": "/example/injected", "PIP_INDEX_URL": "https://private.example",
            "PIP_CONFIG_FILE": "/example/pip.conf", "SPHINX_TAGS": "unexpected",
        }
        with mock.patch.dict(os.environ, supplied, clear=True):
            environment = build_godot_docs.build_environment()
            for key in ("PATH", "https_proxy", "SSL_CERT_FILE", "SystemRoot"):
                self.assertEqual(environment[key], supplied[key])
            for key in ("GITHUB_TOKEN", "OTHER_API_KEY", "PYTHONPATH", "PIP_INDEX_URL", "SPHINX_TAGS"):
                self.assertNotIn(key, environment)
            self.assertEqual(environment["PIP_CONFIG_FILE"], os.devnull)
            self.assertEqual(os.environ["GITHUB_TOKEN"], supplied["GITHUB_TOKEN"])

    def test_actual_child_cannot_read_parent_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "environment.json"
            code = "import os,json,sys; open(sys.argv[1], 'w').write(json.dumps(dict(os.environ)))"
            with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "fake-secret", "OTHER_API_KEY": "fake-secret"}):
                build_godot_docs.run_logged(
                    [sys.executable, "-c", code, str(output)],
                    Path(temporary) / "build.log",
                    env={"READTHEDOCS_VERSION": "4.7"},
                )
            environment = json.loads(output.read_text())
            self.assertNotIn("GITHUB_TOKEN", environment)
            self.assertNotIn("OTHER_API_KEY", environment)
            self.assertEqual(environment["READTHEDOCS_VERSION"], "4.7")

    def test_python_probes_also_use_clean_environment(self) -> None:
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "fake-secret"}):
            with mock.patch.object(build_godot_docs.subprocess, "run") as run:
                run.return_value.stdout = "[3, 12, 0]"
                build_godot_docs.python_version(Path(sys.executable))
                self.assertNotIn("GITHUB_TOKEN", run.call_args.kwargs["env"])
                run.return_value.stdout = "{}"
                build_godot_docs.installed_versions(Path(sys.executable))
                self.assertNotIn("GITHUB_TOKEN", run.call_args.kwargs["env"])


class ConversionHelpersTests(unittest.TestCase):
    def test_relative_html_links_become_markdown_links(self) -> None:
        self.assertEqual(
            build_godot_docs.rewrite_relative_html_link("../classes/class_node.html#method"),
            "../classes/class_node.md#method",
        )
        self.assertEqual(
            build_godot_docs.rewrite_relative_html_link("https://example.com/page.html"),
            "https://example.com/page.html",
        )

    def test_internal_document_links_are_version_scoped(self) -> None:
        self.assertTrue(build_godot_docs.is_internal_document_href("#method", "4.7"))
        self.assertTrue(
            build_godot_docs.is_internal_document_href("class_node.html#class-node", "4.7")
        )
        self.assertTrue(
            build_godot_docs.is_internal_document_href(
                "https://docs.godotengine.org/en/4.7/classes/class_node.html",
                "4.7",
            )
        )
        self.assertFalse(
            build_godot_docs.is_internal_document_href(
                "https://docs.godotengine.org/en/4.6/classes/class_node.html",
                "4.7",
            )
        )
        self.assertFalse(
            build_godot_docs.is_internal_document_href(
                "https://github.com/godotengine/godot-demo-projects/",
                "4.7",
            )
        )


class FilesystemSafetyTests(unittest.TestCase):
    def test_cached_archive_must_match_resolved_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "source.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("godot-docs-abc/index.rst", "Godot")
            build_godot_docs.validate_source_archive_commit(archive, "abc")
            with self.assertRaisesRegex(build_godot_docs.BuildError, "与 commit .* 不匹配"):
                build_godot_docs.validate_source_archive_commit(archive, "def")

    def test_zip_extraction_requires_paths_inside_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "source.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("godot-docs/index.rst", "Godot")
            extracted = build_godot_docs.extract_zip_safely(archive, root / "safe")
            self.assertEqual(extracted.name, "godot-docs")

            unsafe_archive = root / "unsafe.zip"
            with zipfile.ZipFile(unsafe_archive, "w") as bundle:
                bundle.writestr("../outside.txt", "unsafe")
            with self.assertRaisesRegex(build_godot_docs.BuildError, "路径不安全"):
                build_godot_docs.extract_zip_safely(unsafe_archive, root / "unsafe")

    def test_force_publish_replaces_only_after_preparation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared = root / "prepared"
            output = root / "output"
            prepared.mkdir()
            output.mkdir()
            (prepared / "new.txt").write_text("new", encoding="utf-8")
            (output / "old.txt").write_text("old", encoding="utf-8")

            with self.assertRaisesRegex(build_godot_docs.BuildError, "使用 --force"):
                build_godot_docs.publish_atomically(prepared, output, force=False)
            self.assertTrue((output / "old.txt").is_file())

            build_godot_docs.publish_atomically(prepared, output, force=True)
            self.assertEqual((output / "new.txt").read_text(encoding="utf-8"), "new")
            self.assertFalse((output / "old.txt").exists())


class PartialBuildSafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.default = self.root / "deployed" / "4.7"
        self.default.mkdir(parents=True)
        self.write_manifest(self.default, {"build": {"selected_sources": None}})
        (self.default / "page.md").write_text("complete corpus")
        patcher = mock.patch.object(build_godot_docs, "default_output", return_value=self.default)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_manifest(self, destination, payload):
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "manifest.json").write_text(json.dumps(payload))

    def assert_rejected_before_build(self, options, reason):
        args = build_godot_docs.build_parser().parse_args([
            "--only", "classes/class_node.rst", "--force", *options,
        ])
        unexpected_work = AssertionError("输出检查前不应启动构建")
        with mock.patch.object(build_godot_docs, "require_build_python", side_effect=unexpected_work) as python:
            with mock.patch.object(build_godot_docs, "resolve_github_commit", side_effect=unexpected_work) as resolve:
                with mock.patch.object(build_godot_docs.tempfile, "mkdtemp", side_effect=unexpected_work) as create:
                    with self.assertRaisesRegex(build_godot_docs.BuildError, reason):
                        build_godot_docs.build(args)
        python.assert_not_called()
        resolve.assert_not_called()
        create.assert_not_called()
        self.assertEqual((self.default / "page.md").read_text(), "complete corpus")

    def test_partial_build_requires_explicit_separate_output(self):
        self.assert_rejected_before_build([], "--output")
        for destination in (self.default, self.default.parent, self.default / "smoke"):
            with self.subTest(destination=destination):
                self.assert_rejected_before_build(["--output", str(destination)], "独立")
        alias = self.root / "alias"
        alias.symlink_to(self.default, target_is_directory=True)
        self.assert_rejected_before_build(["--output", str(alias)], "独立")

    def test_partial_build_cannot_replace_custom_full_or_unknown_output(self):
        destination = self.root / "custom"
        for payload in (
            {"build": {"selected_sources": None}}, {}, [],
            {"build": {"selected_sources": []}},
            {"build": {"selected_sources": "partial"}},
            {"build": {"selected_sources": [None]}},
            {"build": {"selected_sources": [" "]}},
            {"build": []},
        ):
            with self.subTest(payload=payload):
                self.write_manifest(destination, payload)
                original = (destination / "manifest.json").read_bytes()
                self.assert_rejected_before_build(["--output", str(destination)], "部分语料")
                self.assertEqual((destination / "manifest.json").read_bytes(), original)
        (destination / "manifest.json").write_text("{")
        self.assert_rejected_before_build(["--output", str(destination)], "部分语料")
        (destination / "manifest.json").unlink()
        (destination / "other.txt").write_text("unrelated content")
        self.assert_rejected_before_build(["--output", str(destination)], "部分语料")
        self.assertEqual((destination / "other.txt").read_text(), "unrelated content")

    def test_partial_publish_rechecks_coverage_after_staging(self):
        output = self.root / "partial"
        self.write_manifest(output, {"build": {"selected_sources": ["index.rst"]}})
        prepared = self.root / "prepared"
        prepared.mkdir()
        (prepared / "partial.md").write_text("partial result")
        copytree = build_godot_docs.shutil.copytree

        def publish_full_while_staging(source, destination):
            result = copytree(source, destination)
            self.write_manifest(output, {"build": {"selected_sources": None}})
            (output / "full.md").write_text("new full corpus")
            return result

        with mock.patch.object(build_godot_docs.shutil, "copytree", side_effect=publish_full_while_staging):
            with self.assertRaisesRegex(build_godot_docs.BuildError, "部分语料"):
                build_godot_docs.publish_atomically(prepared, output, force=True, partial=True)
        self.assertEqual((output / "full.md").read_text(), "new full corpus")
        self.assertFalse((output / "partial.md").exists())
        self.assertFalse(list(self.root.glob(".partial.*")))

    def test_partial_publish_still_requires_force_for_existing_partial_output(self):
        output = self.root / "partial"
        self.write_manifest(output, {"build": {"selected_sources": ["index.rst"]}})
        prepared = self.root / "prepared"
        prepared.mkdir()
        (prepared / "new.md").write_text("new partial")
        with self.assertRaisesRegex(build_godot_docs.BuildError, "--force"):
            build_godot_docs.publish_atomically(prepared, output, force=False, partial=True)
        build_godot_docs.publish_atomically(prepared, output, force=True, partial=True)
        self.assertEqual((output / "new.md").read_text(), "new partial")


def write_source_archive(path, commit="abc"):
    with zipfile.ZipFile(path, "w") as bundle:
        for name in ("conf.py", "requirements.txt", "LICENSE.txt", "index.rst"):
            bundle.writestr(f"godot-docs-{commit}/{name}", f"original {name}")


class ReuseSourceTests(unittest.TestCase):
    def test_reuse_extracts_archive_without_using_or_changing_old_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "godot-docs.zip"
            write_source_archive(archive)
            old_source = build_godot_docs.extract_zip_safely(archive, root / "source")
            (old_source / "index.rst").write_text("local modification")
            (old_source / "extra.rst").write_text("local addition")
            python = build_godot_docs.venv_python(root / "venv")
            python.parent.mkdir(parents=True)
            python.touch()
            archive_hash = build_godot_docs.sha256_file(archive)
            for name in ("first-run", "second-run"):
                destination = root / name / "source"
                with mock.patch.object(build_godot_docs, "installed_versions", return_value={"Sphinx": "test"}):
                    result = build_godot_docs.reuse_build_assets(root, "abc", destination)
                reused_archive, new_source, reused_python, digest, packages = result
                self.assertEqual(new_source.parent, destination)
                self.assertEqual((new_source / "index.rst").read_text(), "original index.rst")
                self.assertFalse((new_source / "extra.rst").exists())
                self.assertEqual((reused_archive, reused_python, digest), (archive, python, archive_hash))
                self.assertEqual(packages, {"Sphinx": "test"})
                (new_source / "index.rst").write_text("changed in this run")
            self.assertEqual((old_source / "index.rst").read_text(), "local modification")
            self.assertEqual(build_godot_docs.sha256_file(archive), archive_hash)

    def test_reuse_does_not_require_previously_extracted_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_source_archive(root / "godot-docs.zip")
            python = build_godot_docs.venv_python(root / "venv")
            python.parent.mkdir(parents=True)
            python.touch()
            with mock.patch.object(build_godot_docs, "installed_versions", return_value={}):
                _, source, _, _, _ = build_godot_docs.reuse_build_assets(root, "abc", root / "run" / "source")
            self.assertTrue((source / "conf.py").is_file())

    def test_reuse_rejects_mismatched_archive_before_extracting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_source_archive(root / "godot-docs.zip", "different")
            destination = root / "run" / "source"
            with self.assertRaisesRegex(build_godot_docs.BuildError, "不匹配"):
                build_godot_docs.reuse_build_assets(root, "abc", destination)
            self.assertFalse(destination.exists())

    def test_reuse_rejects_existing_destination_instead_of_merging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_source_archive(root / "godot-docs.zip")
            python = build_godot_docs.venv_python(root / "venv")
            python.parent.mkdir(parents=True)
            python.touch()
            destination = root / "source"
            destination.mkdir()
            (destination / "local.rst").write_text("local")
            with mock.patch.object(build_godot_docs, "installed_versions", return_value={}):
                with self.assertRaisesRegex(build_godot_docs.BuildError, "全新"):
                    build_godot_docs.reuse_build_assets(root, "abc", destination)
            self.assertEqual([p.name for p in destination.iterdir()], ["local.rst"])


class BuildLifecycleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "output"
        self.output.mkdir()
        (self.output / "old.txt").write_text("old corpus")
        self.work_parent = self.root / "work"
        self.args = build_godot_docs.build_parser().parse_args([
            "--output", str(self.output), "--work-dir", str(self.work_parent), "--force",
        ])
        self.patch("require_build_python", return_value=(3, 10, 0))
        self.patch("python_version", return_value=(3, 10, 0))
        self.patch("installed_versions", return_value={})
        self.resolve = self.patch("resolve_github_commit", return_value="abc")
        self.patch("download_file", side_effect=self.download)
        self.environment = self.patch("create_build_environment", side_effect=self.create_environment)
        self.html = self.patch("build_html")
        self.patch("invoke_converter", side_effect=self.convert)

    def patch(self, name, **kwargs):
        patcher = mock.patch.object(build_godot_docs, name, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def download(self, url, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.suffix == ".zip":
            write_source_archive(destination)
        else:
            destination.write_text("license fixture")

    def create_environment(self, python, venv, source, log_path):
        venv.mkdir()
        (venv / "marker").touch()
        return Path(sys.executable)

    def convert(self, python, html, source, prepared, fragment, version, ref, commit, only, log_path):
        prepared.mkdir()
        page = prepared / "example.md"
        page.write_text("# Example\n")
        build_godot_docs.write_json(fragment, [{
            "path": page.name, "sha256": build_godot_docs.sha256_file(page),
        }])

    def fail_subprocess(self, python, source, html, doctrees, version, jobs, only, log_path):
        html.mkdir()
        (html / "partial.html").write_text("partial")
        build_godot_docs.run_logged(
            [sys.executable, "-c", "import sys; print('first diagnostic'); print('last diagnostic'); sys.exit(7)"],
            log_path,
        )

    def invoke_failure(self, exception=build_godot_docs.BuildError):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), self.assertRaises(exception) as raised:
            build_godot_docs.build(self.args)
        self.assertEqual((self.output / "old.txt").read_text(), "old corpus")
        return str(raised.exception), stdout.getvalue()

    def test_subprocess_failure_keeps_log_at_reported_path_and_cleans_artifacts(self):
        self.html.side_effect = self.fail_subprocess
        error, output = self.invoke_failure()
        workdirs = list(self.work_parent.iterdir())
        self.assertEqual(len(workdirs), 1)
        work = workdirs[0]
        self.assertEqual([p.name for p in work.iterdir()], ["build.log"])
        log_path = work / "build.log"
        self.assertIn(str(log_path), error)
        self.assertIn(str(log_path), output)
        content = log_path.read_text()
        self.assertIn("first diagnostic", content)
        self.assertIn("last diagnostic", content)
        self.assertIn("退出码为 7", content)

    def test_early_failure_creates_diagnostic_log(self):
        self.resolve.side_effect = build_godot_docs.BuildError("cannot resolve fixture ref")
        _, output = self.invoke_failure()
        logs = list(self.work_parent.glob("*/build.log"))
        self.assertEqual(len(logs), 1)
        self.assertIn("cannot resolve fixture ref", logs[0].read_text())
        self.assertIn(str(logs[0]), output)

    def test_keep_workdir_preserves_artifacts_and_error_log(self):
        self.args.keep_workdir = True
        self.html.side_effect = self.fail_subprocess
        self.invoke_failure()
        work = next(self.work_parent.iterdir())
        self.assertTrue((work / "html" / "partial.html").exists())
        self.assertTrue((work / "venv" / "marker").exists())
        self.assertIn("退出码为 7", (work / "build.log").read_text())

    def test_success_removes_temporary_work_and_publishes_output(self):
        with contextlib.redirect_stdout(io.StringIO()):
            result = build_godot_docs.build(self.args)
        self.assertEqual(result, self.output.resolve())
        self.assertEqual(list(self.work_parent.iterdir()), [])
        self.assertEqual((self.output / "example.md").read_text(), "# Example\n")
        self.assertTrue((self.output / "manifest.json").is_file())

    def test_interrupt_preserves_diagnostics_and_original_exception(self):
        self.html.side_effect = KeyboardInterrupt("fixture interruption")
        self.invoke_failure(KeyboardInterrupt)
        logs = list(self.work_parent.glob("*/build.log"))
        self.assertEqual(len(logs), 1)
        self.assertIn("fixture interruption", logs[0].read_text())

    def test_reused_build_consumes_fresh_source_and_preserves_original_cache(self):
        self.args.keep_workdir = True
        with contextlib.redirect_stdout(io.StringIO()):
            build_godot_docs.build(self.args)
        cache = next(self.work_parent.iterdir())
        old_source = cache / "source" / "godot-docs-abc"
        (old_source / "index.rst").write_text("local modification")
        python = build_godot_docs.venv_python(cache / "venv")
        python.parent.mkdir(parents=True, exist_ok=True)
        python.touch()
        self.args.keep_workdir = False
        self.args.reuse_workdir = cache
        self.args.work_dir = None
        used_source = []

        def check_source(python, source, *args):
            self.assertNotEqual(source, old_source)
            self.assertEqual((source / "index.rst").read_text(), "original index.rst")
            used_source.append(source)

        self.html.side_effect = check_source
        with contextlib.redirect_stdout(io.StringIO()):
            build_godot_docs.build(self.args)
        self.assertEqual(len(used_source), 1)
        self.assertFalse(used_source[0].exists())
        self.environment.assert_called_once()
        self.assertEqual((old_source / "index.rst").read_text(), "local modification")
        self.assertTrue((cache / "godot-docs.zip").is_file())
        self.assertTrue(python.is_file())
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertTrue(manifest["build"]["reused_build_assets"])
        self.assertEqual(manifest["godot_docs"]["source_archive_sha256"], build_godot_docs.sha256_file(cache / "godot-docs.zip"))

    def test_partial_build_can_create_and_replace_separate_partial_output(self):
        self.args.only = ["index.rst"]
        self.args.output = self.root / "smoke"
        for _ in range(2):
            with contextlib.redirect_stdout(io.StringIO()):
                build_godot_docs.build(self.args)
            manifest = json.loads((self.args.output / "manifest.json").read_text())
            self.assertEqual(manifest["build"]["selected_sources"], ["index.rst"])
            self.assertEqual((self.args.output / "example.md").read_text(), "# Example\n")
        self.assertEqual((self.output / "old.txt").read_text(), "old corpus")

    def test_partial_build_accepts_empty_separate_directory(self):
        self.args.only = ["index.rst"]
        self.args.output = self.root / "empty-smoke"
        self.args.output.mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
            build_godot_docs.build(self.args)
        self.assertTrue((self.args.output / "manifest.json").is_file())

    def test_partial_build_preserves_output_that_becomes_full_during_build(self):
        self.args.only = ["index.rst"]
        self.args.output = self.root / "smoke"
        self.args.output.mkdir()
        manifest_path = self.args.output / "manifest.json"
        build_godot_docs.write_json(manifest_path, {"build": {"selected_sources": ["index.rst"]}})

        def replace_with_full_corpus(*args):
            build_godot_docs.write_json(manifest_path, {"build": {"selected_sources": None}})
            (self.args.output / "full.md").write_text("new full corpus")

        self.html.side_effect = replace_with_full_corpus
        error, _ = self.invoke_failure()
        self.assertIn("部分语料", error)
        self.assertEqual((self.args.output / "full.md").read_text(), "new full corpus")
        self.assertFalse((self.args.output / "example.md").exists())
        self.assertIsNone(json.loads(manifest_path.read_text())["build"]["selected_sources"])
        self.assertFalse(list(self.root.glob(".smoke.*")))


if __name__ == "__main__":
    unittest.main()
