from __future__ import annotations

import argparse
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


if __name__ == "__main__":
    unittest.main()
