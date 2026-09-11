"""用手写的 Sphinx HTML 结构样例验证实际转换器与检索器的衔接。

样例不作为引擎事实来源，也不覆盖完整 Sphinx 构建；全部生成物位于临时目录。
此组测试要求安装构建脚本中 CONVERTER_REQUIREMENTS 指定的依赖，不自动跳过。
"""

from __future__ import annotations

import contextlib
import importlib.metadata
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_build_godot_docs import build_godot_docs as build
from test_search_godot_docs import search_godot_docs as search


FIXTURES = Path(__file__).parent / "fixtures" / "conversion"


class ConversionPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for requirement in build.CONVERTER_REQUIREMENTS:
            name, expected = requirement.split("==")
            try:
                actual = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                actual = "未安装"
            if actual != expected:
                raise RuntimeError(
                    f"转换测试需要 {requirement}，当前为 {actual}；"
                    "请按 README 的转换回归说明在虚拟环境中安装依赖。"
                )
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.html = cls.root / "html"
        cls.source = cls.root / "source"
        cls.output = cls.root / "corpus"
        shutil.copytree(FIXTURES, cls.html)
        for page in cls.html.rglob("*.html"):
            source = cls.source / page.relative_to(cls.html).with_suffix(".rst")
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("转换样例占位源文件；不执行 Sphinx。\n", encoding="utf-8")
        cls.fragment = cls.root / "pages.json"
        with contextlib.redirect_stdout(io.StringIO()):
            build.invoke_converter(
                Path(sys.executable), cls.html, cls.source, cls.output,
                cls.fragment, "4.7", "fixture-ref", "fixture-commit", (), cls.root / "convert.log",
            )
        cls.entries = json.loads(cls.fragment.read_text())
        build.validate_corpus(cls.output, cls.entries)
        build.write_json(cls.output / "manifest.json", {
            "schema_version": build.MANIFEST_SCHEMA_VERSION,
            "godot_docs": {"version": "4.7", "source_commit": "fixture-commit"},
            "build": {"selected_sources": [entry["source_path"] for entry in cls.entries]},
            "files": cls.entries,
        })

    def invoke(self, query, *options):
        completed = subprocess.run([
            sys.executable, "-B", str(Path(search.__file__)), query,
            "--docs-root", str(self.output), "--version", "4.7", "--no-log", "--json", *options,
        ], capture_output=True, text=True, env=build.build_environment())
        self.assertEqual(completed.stderr, "")
        return completed.returncode, json.loads(completed.stdout)

    def test_converted_subclass_defaults_keep_parent_declaration_and_exact_source(self):
        for member, expected, parent in (("mouse_filter", "2", "0"), ("size_flags_vertical", "4", "1")):
            with self.subTest(member=member):
                code, payload = self.invoke(f"Label.{member}", "--show-best")
                self.assertEqual(code, 0)
                self.assertEqual(payload["corpus_coverage"], "partial")
                self.assertFalse(payload["missing_ancestors"])
                result = payload["results"][0]
                self.assertEqual((result["target_class"], result["declaring_class"]), ("Label", "Control"))
                self.assertIn(f"= `{parent}`", result["excerpt"])
                evidence = result["document_default"]
                self.assertEqual((evidence["value"], evidence["title"]), (expected, "Label"))
                lines = (self.output / evidence["path"]).read_text().splitlines()
                self.assertEqual(lines[evidence["line"] - 1], evidence["excerpt"])
                self.assertIn("overrides Control", evidence["excerpt"])

    def test_converted_accessors_and_admonitions_remain_in_member_evidence(self):
        code, payload = self.invoke("Label.get_mouse_filter()", "--show-best")
        self.assertEqual(code, 0)
        result = payload["results"][0]
        self.assertEqual(result["document_default"]["value"], "2")
        self.assertIn("get_mouse_filter", result["excerpt"])
        self.assertIn("Warning", result["excerpt"])
        self.assertIn("Check the target class default", result["excerpt"])
        self.assertNotIn("size_flags_vertical", result["excerpt"])

    def test_converted_overloads_remain_separate_and_ambiguity_is_reported(self):
        for query, kind in (("Vector2(Vector2i(1, 2))", "constructor"), ("Vector3.operator *", "operator")):
            with self.subTest(query=query):
                code, payload = self.invoke(query)
                self.assertEqual(code, 0)
                self.assertEqual(len(payload["results"]), 2)
                self.assertEqual({r["kind"] for r in payload["results"]}, {kind})
                self.assertTrue(payload["ambiguous"])
                self.assertNotEqual(payload["results"][0]["line"], payload["results"][1]["line"])
                _, best = self.invoke(query, "--show-best")
                self.assertEqual(len(best["results"]), 1)
                self.assertTrue(best["ambiguous"])
        _, payload = self.invoke("Vector2()", "--show-best")
        self.assertFalse(payload["ambiguous"])

    def test_code_examples_do_not_create_fake_sections_or_members(self):
        code, payload = self.invoke("Label.invented_property")
        self.assertEqual(code, 1)
        self.assertEqual(payload["results"], [])
        page = (self.output / "tutorials/example.md").read_text()
        sections = search.parse_sections(page.splitlines())
        self.assertEqual([s.title for s in sections], ["Example workflow", "Lifecycle example", "Follow-up example"])
        self.assertIn("```gdscript", page)
        self.assertIn("```csharp", page)
        self.assertIn("**GDScript**", page)
        self.assertIn("**C#**", page)
        self.assertIn('print("fixture")', page)
        self.assertNotIn("navigation-only", page)
        self.assertNotIn("script-only", page)

    def test_converted_manual_sections_are_searchable_with_warning_context(self):
        code, payload = self.invoke("Lifecycle example", "--mode", "section", "--show-best")
        self.assertEqual(code, 0)
        self.assertFalse(payload["ambiguous"])
        result = payload["results"][0]
        self.assertEqual(result["path"], "tutorials/example.md")
        self.assertIn("Fixture warning", result["excerpt"])
        self.assertIn("```gdscript", result["excerpt"])
        self.assertNotIn("Additional fixture context", result["excerpt"])

    def test_conversion_metadata_and_document_links_are_preserved(self):
        self.assertEqual(len(self.entries), 5)
        for entry in self.entries:
            with self.subTest(path=entry["path"]):
                page = self.output / entry["path"]
                self.assertEqual(build.sha256_file(page), entry["sha256"])
                self.assertEqual(page.stat().st_size, entry["bytes"])
                self.assertIn('source_commit: "fixture-commit"', page.read_text())
                expected = "MIT" if entry["path"].startswith("classes/") else "CC-BY-3.0"
                self.assertEqual(entry["license"], expected)
        manual = (self.output / "tutorials/example.md").read_text()
        self.assertIn("[Another page](other.md)", manual)


if __name__ == "__main__":
    unittest.main()
