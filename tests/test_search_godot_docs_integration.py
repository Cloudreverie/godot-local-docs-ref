from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY_ROOT / "scripts" / "search_godot_docs.py"
DOCS_ROOT = REPOSITORY_ROOT / "references" / "godot-docs" / "4.7"
SPEC = importlib.util.spec_from_file_location("search_godot_docs_integration", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
search_godot_docs = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = search_godot_docs
SPEC.loader.exec_module(search_godot_docs)


class Godot47CorpusRegressionTests(unittest.TestCase):
    """Exercise search behavior against the generated official Godot 4.7 corpus."""

    @classmethod
    def setUpClass(cls) -> None:
        if not DOCS_ROOT.is_dir():
            raise unittest.SkipTest(
                "Godot 4.7 docs are not built; run scripts/build_godot_docs.py first"
            )

        # A present but malformed or incomplete corpus is a regression, not a skip.
        cls.corpus = search_godot_docs.load_corpus(DOCS_ROOT)
        cls.documents_by_path = {
            document.relative_path: document for document in cls.corpus.documents
        }

    def search(self, query: str):
        parsed = search_godot_docs.parse_query(query, self.corpus)
        return search_godot_docs.search_corpus(
            self.corpus,
            parsed,
            mode="auto",
            limit=5,
            context=2,
            max_chars=2000,
        )

    def test_corpus_identity_and_required_pages(self) -> None:
        self.assertEqual(self.corpus.version, "4.7")
        self.assertRegex(self.corpus.commit, re.compile(r"^[0-9a-f]{40}$"))
        self.assertGreaterEqual(len(self.corpus.documents), 1500)

        required_paths = {
            "classes/class_@gdscript.md",
            "classes/class_@globalscope.md",
            "classes/class_basebutton.md",
            "classes/class_camera3d.md",
            "classes/class_hashingcontext.md",
            "classes/class_json.md",
            "classes/class_node.md",
            "classes/class_signal.md",
            "classes/class_vector2.md",
            "classes/class_viewport.md",
            "getting_started/first_3d_game/02.player_input.md",
        }
        self.assertTrue(required_paths.issubset(self.documents_by_path))

    def test_project_derived_inherited_members_resolve_to_defining_classes(self) -> None:
        # These cases were selected from real Godot 4.7 usage in 实际 Godot 游戏项目.
        cases = (
            ("Button.disabled", "BaseButton", "property", "disabled"),
            ("Button.visible", "CanvasItem", "property", "visible"),
            ("ColorRect.position", "Control", "property", "position"),
            ("Camera3D.global_basis", "Node3D", "property", "global_basis"),
            ("MeshInstance3D.global_position", "Node3D", "property", "global_position"),
            (
                "MeshInstance3D.material_override",
                "GeometryInstance3D",
                "property",
                "material_override",
            ),
            ("CanvasLayer.add_child", "Node", "method", "add_child"),
            ("SubViewport.push_input", "Viewport", "method", "push_input"),
            ("SubViewport.queue_free", "Node", "method", "queue_free"),
            ("Window.get_visible_rect", "Viewport", "method", "get_visible_rect"),
        )

        for query, defining_class, kind, member in cases:
            with self.subTest(query=query):
                results = self.search(query)
                self.assertEqual(len(results), 1)
                best = results[0]
                self.assertEqual(best.document.title, defining_class)
                self.assertEqual(best.kind, kind)
                self.assertIn(f"**{member}**", best.excerpt)

    def test_explicit_class_member_does_not_escape_the_inheritance_chain(self) -> None:
        for query in ("Button.global_basis", "Node3D.disabled", "Wrong.KEY_YEN"):
            with self.subTest(query=query):
                self.assertEqual(self.search(query), [])

    def test_operator_symbol_resolves_to_operator_declarations(self) -> None:
        results = self.search("Vector3.operator *")
        self.assertTrue(results)
        self.assertTrue(all(result.kind == "operator" for result in results))
        self.assertTrue(all(result.document.title == "Vector3" for result in results))
        self.assertTrue(all(r"**operator \***" in result.excerpt for result in results))

    def test_project_derived_enum_and_constant_queries_return_one_item(self) -> None:
        cases = (
            (
                "Camera3D.PROJECTION_ORTHOGONAL",
                "Camera3D",
                "enumeration",
                "PROJECTION_ORTHOGONAL",
                "PROJECTION_PERSPECTIVE",
            ),
            (
                "BaseMaterial3D.SHADING_MODE_UNSHADED",
                "BaseMaterial3D",
                "enumeration",
                "SHADING_MODE_UNSHADED",
                "SHADING_MODE_PER_PIXEL",
            ),
            ("FileAccess.READ", "FileAccess", "enumeration", "READ", "WRITE"),
            ("Key.KEY_SPACE", "@GlobalScope", "enumeration", "KEY_SPACE", "KEY_ESCAPE"),
            ("Vector3.ZERO", "Vector3", "constant", "ZERO", "ONE"),
        )

        for query, title, kind, member, neighbor in cases:
            with self.subTest(query=query):
                results = self.search(query)
                self.assertEqual(len(results), 1)
                result = results[0]
                self.assertEqual(result.document.title, title)
                self.assertEqual(result.kind, kind)
                self.assertIn(f"**{member}**", result.excerpt)
                self.assertNotIn(f"**{neighbor}**", result.excerpt)
                self.assertLess(len(result.excerpt), 1000)

    def test_input_actions_remains_a_concept_query(self) -> None:
        parsed = search_godot_docs.parse_query("input actions", self.corpus)
        self.assertIsNone(parsed.class_document)
        self.assertIsNone(parsed.member)

        results = self.search("input actions")
        self.assertTrue(results)
        self.assertEqual(
            results[0].document.relative_path,
            "getting_started/first_3d_game/02.player_input.md",
        )
        self.assertEqual(results[0].document.title, "Player scene and input actions")
        self.assertEqual(results[0].kind, "document")

    def test_signal_beats_same_named_theme_property(self) -> None:
        results = self.search("Button.pressed")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document.title, "BaseButton")
        self.assertEqual(results[0].kind, "signal")
        self.assertIn("**pressed**()", results[0].excerpt)

    def test_theme_property_resolves_when_no_script_api_conflicts(self) -> None:
        results = self.search("Button.font_color")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document.title, "Button")
        self.assertEqual(results[0].kind, "theme-property")
        self.assertIn("Color **font_color**", results[0].excerpt)
        self.assertEqual(self.search("Button.font_color()"), [])

    def test_annotation_resolves_as_a_structured_member(self) -> None:
        results = self.search("@GDScript.@export_range")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document.title, "@GDScript")
        self.assertEqual(results[0].kind, "annotation")
        self.assertIn("**@export_range**(", results[0].excerpt)

    def test_empty_value_call_returns_the_default_constructor(self) -> None:
        results = self.search("Vector2()")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document.title, "Vector2")
        self.assertEqual(results[0].kind, "constructor")
        self.assertIn("Vector2 **Vector2**()", results[0].excerpt)

        two_arguments = self.search("Vector2(1, 2)")
        self.assertEqual(len(two_arguments), 1)
        self.assertEqual(two_arguments[0].document.title, "Vector2")
        self.assertEqual(two_arguments[0].kind, "constructor")
        self.assertIn("x: float, y: float", two_arguments[0].excerpt)

        one_argument = self.search("Vector2(1)")
        self.assertEqual(len(one_argument), 2)
        self.assertTrue(all(result.kind == "constructor" for result in one_argument))
        self.assertTrue(all(result.document.title == "Vector2" for result in one_argument))

    def test_constructor_call_is_not_reinterpreted_as_a_section_alias(self) -> None:
        results = self.search("Signal()")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document.title, "Signal")
        self.assertEqual(results[0].kind, "constructor")
        self.assertIn("Signal **Signal**()", results[0].excerpt)

    def test_object_new_returns_the_exact_class_reference(self) -> None:
        results = self.search("JSON.new")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document.relative_path, "classes/class_json.md")
        self.assertEqual(results[0].kind, "document")
        self.assertNotIn("**new**", results[0].excerpt)

    def test_nested_enum_qualifier_is_validated(self) -> None:
        results = self.search("HashingContext.HashType.HASH_SHA256")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document.title, "HashingContext")
        self.assertEqual(results[0].kind, "enumeration")
        self.assertIn("HashType **HASH_SHA256**", results[0].excerpt)
        self.assertNotIn("**HASH_MD5**", results[0].excerpt)
        self.assertEqual(self.search("HashingContext.Wrong.HASH_SHA256"), [])

    def test_inherited_constant_resolves_to_its_defining_class(self) -> None:
        results = self.search("Control.NOTIFICATION_TRANSLATION_CHANGED")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document.title, "Node")
        self.assertEqual(results[0].kind, "constant")
        self.assertIn("**NOTIFICATION_TRANSLATION_CHANGED**", results[0].excerpt)


if __name__ == "__main__":
    unittest.main()
