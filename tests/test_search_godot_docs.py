from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "search_godot_docs.py"
SPEC = importlib.util.spec_from_file_location("search_godot_docs", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
search_godot_docs = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = search_godot_docs
SPEC.loader.exec_module(search_godot_docs)


NODE_PAGE = """---
title: "Node"
godot_version: "4.7"
source_path: "classes/class_node.rst"
license: "MIT"
---
# Node

**Inherits:** Object

Base class for scene objects.

## Signals

**ready**()

Emitted when the node is ready.

---

## Enumerations

enum **DuplicateFlags**:

DuplicateFlags **DUPLICATE_SIGNALS** = `1`

Duplicate the node's signal connections.

DuplicateFlags **DUPLICATE_GROUPS** = `2`

Duplicate the node's groups.

---

## Constants

**NOTIFICATION_READY** = `13`

Notification received when the node is ready.

**NOTIFICATION_PROCESS** = `17`

Notification received every rendered frame. See NOTIFICATION_READY for startup order.

---

## Method Descriptions

void **queue_free**()

Queues this node to be deleted at the end of the current frame.

---

void **remove_child**(node: Node)

Removes a child node.
"""


OBJECT_PAGE = """---
title: "Object"
godot_version: "4.7"
source_path: "classes/class_object.rst"
license: "MIT"
---
# Object

Base class for all Godot objects.

## Method Descriptions

void **free**()

Deletes the object immediately.
"""


CANVAS_ITEM_PAGE = """---
title: "CanvasItem"
godot_version: "4.7"
source_path: "classes/class_canvasitem.rst"
license: "MIT"
---
# CanvasItem

**Inherits:** Node **<** Object

## Property Descriptions

bool **visible** = `true`

- void **set_visible**(value: bool)
- bool **is_visible**()

Controls whether this CanvasItem is drawn.
"""


NODE_2D_PAGE = """---
title: "Node2D"
godot_version: "4.7"
source_path: "classes/class_node2d.rst"
license: "MIT"
---
# Node2D

**Inherits:** CanvasItem **<** Node **<** Object

## Property Descriptions

Vector2 **global_position**

- void **set_global_position**(value: Vector2)
- Vector2 **get_global_position**()

Global position.

---

Vector2 **position** = `Vector2(0, 0)`

- void **set_position**(value: Vector2)
- Vector2 **get_position**()

Position relative to the parent.
"""


TUTORIAL_PAGE = """---
title: "Creating your first script"
godot_version: "4.7"
source_path: "getting_started/step_by_step/scripting_first_script.rst"
license: "CC-BY-3.0"
---
# Creating your first script

## Hello, world!

Print a message to the Output
panel.

```gdscript
## This is code, not a document heading
print("Hello, world!")
```

The editor may report: "Indented block expected".

## Moving forward

Move the sprite each frame.
"""


INPUT_ACTIONS_PAGE = """---
title: "Player scene and input actions"
godot_version: "4.7"
source_path: "getting_started/first_3d_game/02.player_input.rst"
license: "CC-BY-3.0"
---
# Player scene and input actions

Register custom input actions and use them to move the player.
"""


CHARACTER_BODY_PAGE = """---
title: "CharacterBody2D"
godot_version: "4.7"
source_path: "classes/class_characterbody2d.rst"
license: "MIT"
---
# CharacterBody2D

**Inherits:** PhysicsBody2D **<** CollisionObject2D **<** Node2D **<** CanvasItem **<** Node **<** Object

A 2D physics body specialized for characters.

## Property Descriptions

float **safe_margin** = `0.08`

- void **set_safe_margin**(value: float)

The margin keeps collision recovery visible and stable.

---

Vector2 **velocity** = `Vector2(0, 0)`

- void **set_velocity**(value: Vector2)

Velocity used by movement methods.

---

## Method Descriptions

Vector2 **get_position_delta**() const

Returns the position delta from the last movement.
"""


BASE_BUTTON_PAGE = """---
title: "BaseButton"
godot_version: "4.7"
source_path: "classes/class_basebutton.rst"
license: "MIT"
---
# BaseButton

**Inherits:** Control **<** CanvasItem **<** Node **<** Object

## Signals

**pressed**()

Emitted when the button is pressed.

---

## Property Descriptions

bool **disabled** = `false`

- void **set_disabled**(value: bool)
- bool **is_disabled**()

If true, the button cannot be clicked.
"""


BUTTON_PAGE = """---
title: "Button"
godot_version: "4.7"
source_path: "classes/class_button.rst"
license: "MIT"
---
# Button

**Inherits:** BaseButton **<** Control **<** CanvasItem **<** Node **<** Object

## Theme Property Descriptions

StyleBox **disabled**

StyleBox used when the Button is disabled.

---

Color **font_color** = `Color(1, 1, 1, 1)`

Default text color.
"""


INPUT_PAGE = """---
title: "Input"
godot_version: "4.7"
source_path: "classes/class_input.rst"
license: "MIT"
---
# Input

Handles input actions.

## Method Descriptions

void **action_press**(action: StringName)

Simulates an input action press.
"""


GLOBAL_SCOPE_PAGE = """---
title: "@GlobalScope"
godot_version: "4.7"
source_path: "classes/class_@globalscope.rst"
license: "MIT"
---
# @GlobalScope

## Enumerations

enum **Key**:

Key **KEY_NONE** = `0`

No key.

Key **KEY_YEN** = `165`

Yen symbol key.
"""


CAMERA_3D_PAGE = """---
title: "Camera3D"
godot_version: "4.7"
source_path: "classes/class_camera3d.rst"
license: "MIT"
---
# Camera3D

**Inherits:** Node3D **<** Node **<** Object

## Enumerations

enum **ProjectionType**:

ProjectionType **PROJECTION_PERSPECTIVE** = `0`

Perspective projection.

ProjectionType **PROJECTION_ORTHOGONAL** = `1`

Orthogonal projection.

ProjectionType **PROJECTION_FRUSTUM** = `2`

Frustum projection.
"""


VECTOR_3_PAGE = r"""---
title: "Vector3"
godot_version: "4.7"
source_path: "classes/class_vector3.rst"
license: "MIT"
---
# Vector3

## Operator Descriptions

Vector3 **operator \***(right: float)

Multiplies every component by the scalar.
"""


VECTOR_2_PAGE = """---
title: "Vector2"
godot_version: "4.7"
source_path: "classes/class_vector2.rst"
license: "MIT"
---
# Vector2

## Constructor Descriptions

Vector2 **Vector2**()

Constructs a zero vector.

---

Vector2 **Vector2**(from: Vector2)

Constructs a copy of a Vector2.

---

Vector2 **Vector2**(from: Vector2i)

Constructs a Vector2 from a Vector2i.

---

Vector2 **Vector2**(x: float, y: float)

Constructs a vector from two components.
"""


PACKED_VECTOR_2_ARRAY_PAGE = """---
title: "PackedVector2Array"
godot_version: "4.7"
source_path: "classes/class_packedvector2array.rst"
license: "MIT"
---
# PackedVector2Array

An array of Vector2 values.
"""


JSON_PAGE = """---
title: "JSON"
godot_version: "4.7"
source_path: "classes/class_json.rst"
license: "MIT"
---
# JSON

**Inherits:** RefCounted **<** Object

A helper class for creating and parsing JSON data. Create an instance with `JSON.new()`.

## Method Descriptions

Error **parse**(json_text: String)

Parses JSON text.
"""


CRYPTO_PAGE = """---
title: "Crypto"
godot_version: "4.7"
source_path: "classes/class_crypto.rst"
license: "MIT"
---
# Crypto

**Inherits:** RefCounted **<** Object

Provides cryptographic operations.
"""


AUTOLOAD_PAGE = """---
title: "Singletons (Autoload)"
godot_version: "4.7"
source_path: "tutorials/scripting/singletons_autoload.rst"
license: "CC-BY-3.0"
---
# Singletons (Autoload)

Autoloading nodes and scripts makes shared state available between scenes.
"""


PLUGIN_PAGE = """---
title: "Making plugins"
godot_version: "4.7"
source_path: "tutorials/plugins/editor/making_plugins.rst"
license: "CC-BY-3.0"
---
# Making plugins

## Registering autoloads and singletons

An editor plugin can register an autoload singleton automatically.
"""


PAUSING_PAGE = """---
title: "Pausing games and process mode"
godot_version: "4.7"
source_path: "tutorials/scripting/pausing_games.rst"
license: "CC-BY-3.0"
---
# Pausing games and process mode

Pausing interrupts the game while selected nodes keep processing.

## How pausing works

Set SceneTree.paused to true to pause the game.
"""


CPU_PAGE = """---
title: "CPU optimization"
godot_version: "4.7"
source_path: "tutorials/performance/cpu_optimization.rst"
license: "CC-BY-3.0"
---
# CPU optimization

Removing nodes from the SceneTree can be faster than pausing them.
"""


class CorpusFixture:
    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        pages = {
            "classes/class_object.md": (
                "Object",
                "classes/class_object.rst",
                "MIT",
                OBJECT_PAGE,
            ),
            "classes/class_node.md": ("Node", "classes/class_node.rst", "MIT", NODE_PAGE),
            "classes/class_canvasitem.md": (
                "CanvasItem",
                "classes/class_canvasitem.rst",
                "MIT",
                CANVAS_ITEM_PAGE,
            ),
            "classes/class_node2d.md": (
                "Node2D",
                "classes/class_node2d.rst",
                "MIT",
                NODE_2D_PAGE,
            ),
            "classes/class_characterbody2d.md": (
                "CharacterBody2D",
                "classes/class_characterbody2d.rst",
                "MIT",
                CHARACTER_BODY_PAGE,
            ),
            "classes/class_basebutton.md": (
                "BaseButton",
                "classes/class_basebutton.rst",
                "MIT",
                BASE_BUTTON_PAGE,
            ),
            "classes/class_button.md": (
                "Button",
                "classes/class_button.rst",
                "MIT",
                BUTTON_PAGE,
            ),
            "classes/class_input.md": (
                "Input",
                "classes/class_input.rst",
                "MIT",
                INPUT_PAGE,
            ),
            "classes/class_@globalscope.md": (
                "@GlobalScope",
                "classes/class_@globalscope.rst",
                "MIT",
                GLOBAL_SCOPE_PAGE,
            ),
            "classes/class_camera3d.md": (
                "Camera3D",
                "classes/class_camera3d.rst",
                "MIT",
                CAMERA_3D_PAGE,
            ),
            "classes/class_vector3.md": (
                "Vector3",
                "classes/class_vector3.rst",
                "MIT",
                VECTOR_3_PAGE,
            ),
            "classes/class_vector2.md": (
                "Vector2",
                "classes/class_vector2.rst",
                "MIT",
                VECTOR_2_PAGE,
            ),
            "classes/class_packedvector2array.md": (
                "PackedVector2Array",
                "classes/class_packedvector2array.rst",
                "MIT",
                PACKED_VECTOR_2_ARRAY_PAGE,
            ),
            "classes/class_json.md": (
                "JSON",
                "classes/class_json.rst",
                "MIT",
                JSON_PAGE,
            ),
            "classes/class_crypto.md": (
                "Crypto",
                "classes/class_crypto.rst",
                "MIT",
                CRYPTO_PAGE,
            ),
            "getting_started/step_by_step/scripting_first_script.md": (
                "Creating your first script",
                "getting_started/step_by_step/scripting_first_script.rst",
                "CC-BY-3.0",
                TUTORIAL_PAGE,
            ),
            "getting_started/first_3d_game/02.player_input.md": (
                "Player scene and input actions",
                "getting_started/first_3d_game/02.player_input.rst",
                "CC-BY-3.0",
                INPUT_ACTIONS_PAGE,
            ),
            "tutorials/scripting/singletons_autoload.md": (
                "Singletons (Autoload)",
                "tutorials/scripting/singletons_autoload.rst",
                "CC-BY-3.0",
                AUTOLOAD_PAGE,
            ),
            "tutorials/plugins/editor/making_plugins.md": (
                "Making plugins",
                "tutorials/plugins/editor/making_plugins.rst",
                "CC-BY-3.0",
                PLUGIN_PAGE,
            ),
            "tutorials/scripting/pausing_games.md": (
                "Pausing games and process mode",
                "tutorials/scripting/pausing_games.rst",
                "CC-BY-3.0",
                PAUSING_PAGE,
            ),
            "tutorials/performance/cpu_optimization.md": (
                "CPU optimization",
                "tutorials/performance/cpu_optimization.rst",
                "CC-BY-3.0",
                CPU_PAGE,
            ),
        }
        entries = []
        for relative, (title, source_path, license_id, content) in pages.items():
            page = self.root / relative
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(content, encoding="utf-8")
            entries.append(
                {
                    "path": relative,
                    "title": title,
                    "source_path": source_path,
                    "license": license_id,
                }
            )
        manifest = {
            "schema_version": 2,
            "godot_docs": {"version": "4.7", "source_commit": "fixture-commit"},
            "files": entries,
        }
        (self.root / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    def close(self) -> None:
        self.temporary.cleanup()


class SearchTests(unittest.TestCase):
    def setUp(self) -> None:
        logging = mock.patch.object(search_godot_docs, "resolve_log_path", return_value=None)
        logging.start()
        self.addCleanup(logging.stop)
        self.fixture = CorpusFixture()
        self.corpus = search_godot_docs.load_corpus(self.fixture.root)

    def tearDown(self) -> None:
        self.fixture.close()

    def search(self, query: str, mode: str = "auto"):
        parsed = search_godot_docs.parse_query(query, self.corpus)
        return search_godot_docs.search_corpus(
            self.corpus,
            parsed,
            mode=mode,
            limit=5,
            context=2,
            max_chars=2000,
        )

    def test_exact_class_title_returns_document(self) -> None:
        results = self.search("Node")
        self.assertEqual(results[0].kind, "document")
        self.assertEqual(results[0].document.relative_path, "classes/class_node.md")

    def test_explicit_class_member_returns_only_member_description(self) -> None:
        results = self.search("Node.queue_free")
        self.assertEqual(results[0].kind, "method")
        self.assertIn("Queues this node", results[0].excerpt)
        self.assertNotIn("remove_child", results[0].excerpt)

    def test_unscoped_identifier_ranks_exact_member_first(self) -> None:
        results = self.search("queue_free")
        self.assertEqual(results[0].kind, "method")
        self.assertTrue(results[0].excerpt.startswith("void **queue_free**()"))

    def test_explicit_inherited_member_falls_back_to_defining_class(self) -> None:
        results = self.search("CharacterBody2D.queue_free")
        self.assertEqual(results[0].kind, "method")
        self.assertEqual(results[0].document.title, "Node")

    def test_inherited_property_uses_declaration_not_body_mention(self) -> None:
        results = self.search("CharacterBody2D.position")
        self.assertEqual(results[0].kind, "property")
        self.assertEqual(results[0].document.title, "Node2D")
        self.assertTrue(results[0].excerpt.startswith("Vector2 **position**"))
        self.assertNotIn("get_position_delta", results[0].excerpt)

        visible = self.search("CharacterBody2D.visible")
        self.assertEqual(visible[0].document.title, "CanvasItem")
        self.assertTrue(visible[0].excerpt.startswith("bool **visible**"))

    def test_explicit_member_does_not_search_descendants_or_unrelated_classes(self) -> None:
        self.assertEqual(self.search("Node.velocity"), [])
        self.assertEqual(self.search("CharacterBody2D.action_press"), [])

    def test_script_property_beats_same_named_theme_property(self) -> None:
        results = self.search("Button.disabled")
        self.assertEqual(results[0].kind, "property")
        self.assertEqual(results[0].document.title, "BaseButton")
        self.assertTrue(results[0].excerpt.startswith("bool **disabled**"))
        self.assertTrue(all(result.kind != "theme-property" for result in results))

    def test_property_accessor_alias_resolves_to_property_declaration(self) -> None:
        results = self.search("Button.is_disabled")
        self.assertEqual(results[0].kind, "property")
        self.assertEqual(results[0].document.title, "BaseButton")
        self.assertIn("bool **is_disabled**()", results[0].excerpt)

    def test_enumeration_value_returns_only_the_matching_item(self) -> None:
        results = self.search("Camera3D.PROJECTION_ORTHOGONAL")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].kind, "enumeration")
        self.assertIn("**PROJECTION_ORTHOGONAL**", results[0].excerpt)
        self.assertNotIn("PROJECTION_PERSPECTIVE", results[0].excerpt)
        self.assertNotIn("PROJECTION_FRUSTUM", results[0].excerpt)

        global_value = self.search("Key.KEY_YEN")
        self.assertEqual(global_value[0].document.title, "@GlobalScope")
        self.assertIn("**KEY_YEN**", global_value[0].excerpt)
        self.assertNotIn("KEY_NONE", global_value[0].excerpt)

    def test_constant_returns_only_the_matching_item(self) -> None:
        results = self.search("Node.NOTIFICATION_PROCESS")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].kind, "constant")
        self.assertTrue(results[0].excerpt.startswith("**NOTIFICATION_PROCESS**"))
        self.assertNotIn("**NOTIFICATION_READY**", results[0].excerpt)

    def test_unknown_qualified_identifier_does_not_fall_back_to_concept_search(self) -> None:
        self.assertEqual(self.search("Wrong.KEY_YEN"), [])

    def test_operator_symbol_is_a_member_not_a_section_alias(self) -> None:
        results = self.search("Vector3.operator *")
        self.assertEqual(results[0].kind, "operator")
        self.assertTrue(results[0].excerpt.startswith(r"Vector3 **operator \***"))

    def test_empty_class_call_returns_only_the_default_constructor(self) -> None:
        results = self.search("Vector2()")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document.title, "Vector2")
        self.assertEqual(results[0].kind, "constructor")
        self.assertTrue(results[0].excerpt.startswith("Vector2 **Vector2**()"))
        self.assertNotIn("x: float", results[0].excerpt)

        explicit = self.search("Vector2.Vector2()")
        self.assertEqual(len(explicit), 1)
        self.assertEqual(explicit[0].excerpt, results[0].excerpt)

        spaced = self.search("Vector2.Vector2( )")
        self.assertEqual(len(spaced), 1)
        self.assertEqual(spaced[0].excerpt, results[0].excerpt)

    def test_constructor_name_without_parentheses_returns_all_overloads(self) -> None:
        results = self.search("Vector2.Vector2")
        self.assertEqual(len(results), 4)
        self.assertTrue(all(result.kind == "constructor" for result in results))
        self.assertTrue(any("x: float" in result.excerpt for result in results))

    def test_constructor_arguments_select_matching_arity(self) -> None:
        two_arguments = self.search("Vector2(1, 2)")
        self.assertEqual(len(two_arguments), 1)
        self.assertEqual(two_arguments[0].kind, "constructor")
        self.assertIn("x: float, y: float", two_arguments[0].excerpt)

        explicit = self.search("Vector2.Vector2(1, 2)")
        self.assertEqual(explicit[0].excerpt, two_arguments[0].excerpt)

        nested = self.search('Vector2(foo(1, 2), "a,b")')
        self.assertEqual(nested[0].excerpt, two_arguments[0].excerpt)

        collections = self.search('Vector2([1, 2], {"x": 1, "y": 2})')
        self.assertEqual(collections[0].excerpt, two_arguments[0].excerpt)

        one_argument = self.search("Vector2(1)")
        self.assertEqual(len(one_argument), 2)
        self.assertTrue(all(result.kind == "constructor" for result in one_argument))
        self.assertTrue(all("from:" in result.excerpt for result in one_argument))

        self.assertEqual(self.search("Vector2(1, 2, 3)"), [])
        self.assertEqual(self.search("Vector2(1,"), [])

    def test_show_best_reports_constructor_ambiguity(self) -> None:
        for query, ambiguous in (
            ("Vector2(Vector2i(1, 2))", True),
            ("Vector2.Vector2", True),
            ("Vector2(1, 2)", False),
            ("Node.queue_free()", False),
        ):
            for json_output in (False, True):
                with self.subTest(query=query, json=json_output):
                    stdout = io.StringIO()
                    args = [query, "--docs-root", str(self.fixture.root), "--show-best"]
                    if json_output:
                        args.append("--json")
                    with contextlib.redirect_stdout(stdout):
                        exit_code = search_godot_docs.main(args)
                    self.assertEqual(exit_code, 0)
                    if json_output:
                        payload = json.loads(stdout.getvalue())
                        self.assertEqual(len(payload["results"]), 1)
                        self.assertEqual(bool(payload["warnings"]), ambiguous)
                    else:
                        self.assertEqual("构造重载" in stdout.getvalue(), ambiguous)

    def test_unscoped_calls_match_only_callable_members(self) -> None:
        for mode in ("auto", "member"):
            for query in ("queue_free()", "queue_free( )"):
                with self.subTest(mode=mode, query=query):
                    results = self.search(query, mode=mode)
                    self.assertEqual(len(results), 1)
                    self.assertIn("void **queue_free**()", results[0].excerpt)
            for query in ("disabled()", "Wrong.queue_free()", "nonexistent()"):
                with self.subTest(mode=mode, query=query):
                    self.assertEqual(self.search(query, mode=mode), [])

    def test_document_preview_marks_omitted_lines_as_truncated(self) -> None:
        document = self.corpus.documents[0]
        for line_count, expected in ((23, False), (24, False), (25, True), (42, True)):
            with self.subTest(line_count=line_count):
                document.path.write_text("\n".join(["# Preview"] + ["正文"] * (line_count - 1)))
                result = search_godot_docs.document_result(document, 1000, 6000, {})
                self.assertEqual(result.truncated, expected)
                self.assertEqual(len(result.excerpt.splitlines()), min(line_count, 24))
        document.path.write_text("# Preview\n" + "正文" * 200)
        result = search_godot_docs.document_result(document, 1000, 200, {})
        self.assertTrue(result.truncated)

    def test_object_new_falls_back_to_the_exact_class_document(self) -> None:
        for query, title in (("JSON.new", "JSON"), ("Crypto.new()", "Crypto")):
            with self.subTest(query=query):
                results = self.search(query)
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0].document.title, title)
                self.assertEqual(results[0].kind, "document")
                self.assertNotIn("**new**", results[0].excerpt)

        self.assertEqual(self.search("Crypto.new( )")[0].document.title, "Crypto")

    def test_constructor_routing_rejects_invalid_forms(self) -> None:
        self.assertEqual(self.search("Vector2.new()"), [])
        self.assertEqual(self.search("JSON()"), [])
        self.assertEqual(self.search("Wrong.new()"), [])
        self.assertEqual(self.search("JSON.new", mode="member"), [])

        method = self.search("JSON.parse")
        self.assertEqual(len(method), 1)
        self.assertEqual(method[0].kind, "method")

    def test_empty_call_suffix_requires_a_callable_declaration(self) -> None:
        self.assertEqual(self.search("Button.font_color()"), [])
        self.assertEqual(self.search("Button.disabled()"), [])
        self.assertEqual(self.search("Node.NOTIFICATION_PROCESS()"), [])
        self.assertEqual(self.search("Camera3D.PROJECTION_ORTHOGONAL()"), [])

        accessor = self.search("Button.is_disabled()")
        self.assertEqual(accessor[0].kind, "property")
        signal = self.search("Button.pressed()")
        self.assertEqual(signal[0].kind, "signal")

    def test_space_after_class_name_is_scoped_only_for_section_aliases(self) -> None:
        concept = search_godot_docs.parse_query("input actions", self.corpus)
        self.assertIsNone(concept.class_document)
        self.assertIsNone(concept.member)
        results = self.search("input actions")
        self.assertEqual(results[0].document.title, "Player scene and input actions")

        section = search_godot_docs.parse_query("Node signals", self.corpus)
        self.assertEqual(section.class_document.title, "Node")
        self.assertEqual(section.member, "signals")

    def test_class_section_alias_beats_member_mentions(self) -> None:
        results = self.search("Node signals")
        self.assertEqual(results[0].kind, "section")
        self.assertEqual(results[0].heading, "Signals")

    def test_exact_manual_heading_returns_bounded_section(self) -> None:
        results = self.search("Hello, world!", mode="section")
        self.assertEqual(results[0].heading, "Hello, world!")
        self.assertIn("Indented block expected", results[0].excerpt)
        self.assertNotIn("Move the sprite", results[0].excerpt)

    def test_content_mode_rejects_pages_with_only_one_query_term(self) -> None:
        results = self.search("Indented block expected", mode="content")
        self.assertEqual(len(results), 1)
        self.assertIn("Indented block expected", results[0].excerpt)

    def test_content_mode_matches_phrase_across_wrapped_lines(self) -> None:
        results = self.search("Print a message to the Output panel", mode="content")
        self.assertEqual(len(results), 1)
        self.assertIn("Print a message", results[0].excerpt)
        self.assertIn("panel.", results[0].excerpt)

    def test_small_title_inflection_difference_still_finds_document(self) -> None:
        results = self.search("Creating our first script", mode="title")
        self.assertEqual(results[0].kind, "document")
        self.assertEqual(results[0].document.title, "Creating your first script")

    def test_camel_case_terms_match_separate_query_words(self) -> None:
        self.assertEqual(
            search_godot_docs.query_terms("SceneTree.paused"),
            ("scene", "tree", "pause"),
        )

    def test_unordered_inflected_title_terms_beat_incidental_content(self) -> None:
        results = self.search("autoload singleton")
        self.assertEqual(
            results[0].document.relative_path,
            "tutorials/scripting/singletons_autoload.md",
        )
        paths = [result.document.relative_path for result in results]
        self.assertEqual(len(paths), len(set(paths)))

    def test_page_level_coverage_beats_incidental_single_paragraph(self) -> None:
        results = self.search("scene tree pausing")
        self.assertEqual(
            results[0].document.relative_path,
            "tutorials/scripting/pausing_games.md",
        )

    def test_markdown_headings_inside_fences_are_ignored(self) -> None:
        document = next(doc for doc in self.corpus.documents if not doc.is_class_reference)
        lines = document.path.read_text(encoding="utf-8").splitlines()
        headings = [section.title for section in search_godot_docs.parse_sections(lines)]
        self.assertNotIn("This is code, not a document heading", headings)
        self.assertIn("Moving forward", headings)

    def test_json_cli_output_is_machine_readable(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = search_godot_docs.main(
                ["Node.queue_free", "--docs-root", str(self.fixture.root), "--json"]
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["source_commit"], "fixture-commit")
        self.assertEqual(payload["results"][0]["kind"], "method")

    def test_text_output_uses_compact_provenance_header(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = search_godot_docs.main(
                ["Node.queue_free", "--docs-root", str(self.fixture.root)]
            )
        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Godot 4.7 @ fixture-comm | auto | Node.queue_free", output)
        self.assertNotIn("Root:", output)
        self.assertNotIn(str(self.fixture.root), output)

    def test_missing_explicit_member_does_not_recommend_content_fallback(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = search_godot_docs.main(
                ["Node.velocity", "--docs-root", str(self.fixture.root)]
            )
        output = stdout.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("未找到匹配的 API 声明", output)
        self.assertIn("文档中的继承链", output)
        self.assertNotIn("--mode content", output)

    def test_ranked_text_compacts_results_after_top_three(self) -> None:
        documents = list(self.corpus.documents[:5])
        results = [
            search_godot_docs.SearchResult(
                document=document,
                kind="content",
                score=500 - index,
                line=10 + index,
                heading=f"Heading {index}",
                excerpt=f"excerpt-{index}",
            )
            for index, document in enumerate(documents, 1)
        ]
        results[3] = search_godot_docs.SearchResult(
            document=documents[3],
            kind="method",
            score=496,
            line=14,
            heading="Method Descriptions",
            excerpt="void **fourth_method**()\n\nfourth method details",
        )

        stdout = io.StringIO()
        parsed = search_godot_docs.parse_query("concept query", self.corpus)
        with contextlib.redirect_stdout(stdout):
            search_godot_docs.render_text(
                self.corpus,
                parsed,
                "auto",
                results,
                show_best=False,
            )
        output = stdout.getvalue()

        self.assertIn("Results: 5 （前 3 项提供摘要，其余条目仅提供索引）", output)
        self.assertIn("excerpt-1", output)
        self.assertIn("excerpt-3", output)
        self.assertNotIn("fourth method details", output)
        self.assertIn("Declaration: void **fourth_method**()", output)
        self.assertNotIn("excerpt-5", output)
        self.assertIn(f"{documents[4].relative_path}:15", output)

    def test_json_keeps_excerpts_for_all_ranked_results(self) -> None:
        document = self.corpus.documents[0]
        results = [
            search_godot_docs.SearchResult(
                document=document,
                kind="content",
                score=500 - index,
                line=10 + index,
                heading=None,
                excerpt=f"json-excerpt-{index}",
            )
            for index in range(1, 6)
        ]
        stdout = io.StringIO()
        parsed = search_godot_docs.parse_query("concept query", self.corpus)
        with contextlib.redirect_stdout(stdout):
            search_godot_docs.render_json(self.corpus, parsed, "auto", results)
        payload = json.loads(stdout.getvalue())

        self.assertEqual(payload["results"][3]["excerpt"], "json-excerpt-4")
        self.assertEqual(payload["results"][4]["excerpt"], "json-excerpt-5")


class EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = CorpusFixture()
        self.addCleanup(self.fixture.close)
        self.manifest_path = self.fixture.root / "manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text())

    def save_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def add_class(self, title, body):
        relative = f"classes/class_{title.lower()}.md"
        (self.fixture.root / relative).write_text(f"# {title}\n\n{body}", encoding="utf-8")
        self.manifest["files"].append({
            "path": relative, "title": title,
            "source_path": relative[:-3] + ".rst", "license": "MIT",
        })
        self.save_manifest()

    def add_property_pages(self):
        self.add_class("Control", """**Inherits:** CanvasItem **<** Node **<** Object

## Property Descriptions

MouseFilter **mouse_filter** = `0`

- void **set_mouse_filter**(value: MouseFilter)
- MouseFilter **get_mouse_filter**()

Controls mouse input propagation.

---

SizeFlags **size_flags_vertical** = `1`
""")
        self.add_class("Label", """**Inherits:** Control **<** CanvasItem **<** Node **<** Object

## Properties

| Type | Name | Default |
| --- | --- | --- |
| MouseFilter | mouse_filter | `2` (overrides Control) |
| SizeFlags | size_flags_vertical | `4` (overrides Control) |
""")

    def invoke(self, query, *options, json_output=True, default_root=False):
        arguments = [query, "--no-log", *options]
        if not default_root:
            arguments.extend(["--docs-root", str(self.fixture.root)])
        if json_output:
            arguments.append("--json")
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = search_godot_docs.main(arguments)
        output = stdout.getvalue()
        return code, json.loads(output) if json_output and output else output, stderr.getvalue()

    def test_explicit_version_is_checked_before_search(self):
        for version in ("4.6", "4.7.2"):
            with self.subTest(version=version):
                with mock.patch.object(search_godot_docs, "search_corpus") as search:
                    code, output, error = self.invoke("Node.queue_free", "--version", version)
                self.assertEqual(code, 2)
                self.assertFalse(output)
                self.assertIn(version, error)
                self.assertIn("4.7", error)
                search.assert_not_called()

    def test_matching_and_unspecified_versions_are_reported(self):
        code, payload, error = self.invoke("Node.queue_free", "--version", "4.7")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(payload["requested_version"], "4.7")
        self.assertEqual(payload["godot_version"], "4.7")
        self.manifest["godot_docs"]["version"] = "4.6"
        self.save_manifest()
        code, payload, error = self.invoke("Node.queue_free")
        self.assertEqual((code, error), (0, ""))
        self.assertIsNone(payload["requested_version"])
        self.assertEqual(payload["godot_version"], "4.6")

    def test_default_directory_version_cannot_be_mislabeled(self):
        self.manifest["godot_docs"]["version"] = "4.6"
        self.save_manifest()
        with mock.patch.object(search_godot_docs, "default_docs_root", return_value=self.fixture.root):
            code, _, error = self.invoke("Node.queue_free", default_root=True)
        self.assertEqual(code, 2)
        self.assertIn(search_godot_docs.DEFAULT_VERSION, error)

    def test_subclass_defaults_keep_both_sources_and_parent_excerpt(self):
        self.add_property_pages()
        for member, expected, parent in (("mouse_filter", "2", "0"), ("size_flags_vertical", "4", "1")):
            with self.subTest(member=member):
                code, payload, _ = self.invoke(f"Label.{member}", "--show-best")
                self.assertEqual(code, 0)
                result = payload["results"][0]
                self.assertEqual(result["target_class"], "Label")
                self.assertEqual(result["declaring_class"], "Control")
                self.assertIn(f"= `{parent}`", result["excerpt"])
                evidence = result["document_default"]
                self.assertEqual(evidence["value"], expected)
                self.assertEqual(evidence["title"], "Label")
                lines = (self.fixture.root / evidence["path"]).read_text().splitlines()
                self.assertEqual(lines[evidence["line"] - 1], evidence["excerpt"])
                self.assertIn("overrides Control", evidence["excerpt"])
                _, text, _ = self.invoke(f"Label.{member}", "--show-best", json_output=False)
                self.assertIn("文档默认值", text)
                self.assertIn(f"{evidence['path']}:{evidence['line']}", text)

    def test_defaults_follow_nearest_override_and_property_accessor(self):
        self.add_property_pages()
        self.add_class("DerivedLabel", "**Inherits:** Label **<** Control **<** CanvasItem **<** Node **<** Object\n")
        for query, expected, source in (
            ("DerivedLabel.mouse_filter", "2", "Label"),
            ("Label.get_mouse_filter()", "2", "Label"),
            ("Label.visible", "true", "CanvasItem"),
            ("Control.mouse_filter", "0", "Control"),
        ):
            with self.subTest(query=query):
                _, payload, _ = self.invoke(query, "--show-best")
                evidence = payload["results"][0]["document_default"]
                self.assertEqual((evidence["value"], evidence["title"]), (expected, source))
        page = self.fixture.root / "classes/class_derivedlabel.md"
        page.write_text(page.read_text() + "\n## Properties\n\n| Type | Name | Default |\n| --- | --- | --- |\n| MouseFilter | mouse_filter | `1` (overrides Control) |\n")
        _, payload, _ = self.invoke("DerivedLabel.mouse_filter", "--show-best")
        self.assertEqual(payload["results"][0]["document_default"]["value"], "1")

    def test_override_parser_ignores_examples_and_other_sections(self):
        self.add_property_pages()
        page = self.fixture.root / "classes/class_label.md"
        page.write_text("""# Label

**Inherits:** Control **<** CanvasItem **<** Node **<** Object

## Properties

```text
| MouseFilter | mouse_filter | `99` (overrides Control) |
```

| Type | Name | Default |
| --- | --- | --- |
| MouseFilter | another_property | `98` (overrides Control) |

## Theme Properties

| MouseFilter | mouse_filter | `97` (overrides Control) |
""")
        _, payload, _ = self.invoke("Label.mouse_filter", "--show-best")
        self.assertEqual(payload["results"][0]["document_default"]["value"], "0")

    def test_string_defaults_keep_empty_strings_and_table_pipes(self):
        self.add_class("BaseText", '## Property Descriptions\n\nString **text** = `""`\n')
        self.add_class("DerivedText", '**Inherits:** BaseText\n\n## Properties\n\n| Type | Name | Default |\n| --- | --- | --- |\n| String | text | `"a\\|b"` (overrides BaseText) |\n')
        for title, expected in (("BaseText", '""'), ("DerivedText", '"a|b"')):
            _, payload, _ = self.invoke(f"{title}.text", "--show-best")
            self.assertEqual(payload["results"][0]["document_default"]["value"], expected)

    def test_partial_and_legacy_corpus_coverage(self):
        for metadata, expected in ((None, "unknown"), ({"selected_sources": None}, "full"), ({"selected_sources": ["classes/class_node.rst"]}, "partial")):
            with self.subTest(coverage=expected):
                if metadata is None:
                    self.manifest.pop("build", None)
                else:
                    self.manifest["build"] = metadata
                self.save_manifest()
                for query in ("Node.queue_free", "Node.nonexistent"):
                    _, payload, _ = self.invoke(query)
                    self.assertEqual(payload["corpus_coverage"], expected)
                    self.assertEqual(bool(payload["warnings"]), expected == "partial")

    def test_invalid_coverage_metadata_is_not_reported_as_full(self):
        for selected in ([], "all", False, [None]):
            with self.subTest(selected=selected):
                self.manifest["build"] = {"selected_sources": selected}
                self.save_manifest()
                code, _, error = self.invoke("Node.queue_free")
                self.assertEqual(code, 2)
                self.assertIn("selected_sources", error)

    def test_default_evidence_is_bounded_and_absence_is_not_a_value(self):
        self.add_class("LongText", '## Property Descriptions\n\nString **text** = `"' + 'x' * 1000 + '"`\n')
        _, payload, _ = self.invoke("LongText.text", "--show-best", "--max-chars", "200")
        evidence = payload["results"][0]["document_default"]
        self.assertTrue(evidence["truncated"])
        self.assertLessEqual(len(evidence["value"]), 202)
        self.assertLessEqual(len(evidence["excerpt"]), 202)
        (self.fixture.root / "classes/class_longtext.md").write_text('# LongText\n\n## Property Descriptions\n\nString **text**\n')
        _, payload, _ = self.invoke("LongText.text", "--show-best")
        self.assertIsNone(payload["results"][0]["document_default"])

    def test_missing_ancestor_is_distinct_from_no_match(self):
        self.manifest["files"] = [e for e in self.manifest["files"] if e["title"] != "BaseButton"]
        self.save_manifest()
        code, payload, _ = self.invoke("Button.pressed", "--show-best")
        self.assertEqual(code, 1)
        self.assertIn("BaseButton", payload["missing_ancestors"])
        self.assertTrue(payload["warnings"])
        _, text, _ = self.invoke("Button.pressed", json_output=False)
        self.assertIn("BaseButton", text)
        self.assertIn("不能据此", text)

    def test_gap_before_definition_prevents_claiming_target_default(self):
        self.add_property_pages()
        self.add_class("GapLabel", "**Inherits:** MissingControl **<** Control **<** CanvasItem **<** Node **<** Object\n")
        code, payload, _ = self.invoke("GapLabel.mouse_filter", "--show-best")
        self.assertEqual(code, 0)
        self.assertEqual(payload["missing_ancestors"], ["MissingControl"])
        self.assertIsNone(payload["results"][0]["document_default"])
        self.assertTrue(payload["warnings"])
        page = self.fixture.root / "classes/class_gaplabel.md"
        page.write_text(page.read_text() + "\n## Properties\n\n| Type | Name | Default |\n| --- | --- | --- |\n| MouseFilter | mouse_filter | `2` (overrides Control) |\n")
        _, payload, _ = self.invoke("GapLabel.mouse_filter", "--show-best")
        self.assertEqual(payload["results"][0]["document_default"]["value"], "2")
        self.assertEqual(payload["missing_ancestors"], ["MissingControl"])
        _, payload, _ = self.invoke("Control.mouse_filter", "--show-best")
        self.assertFalse(payload["missing_ancestors"])

    def test_missing_ancestors_after_definition_do_not_warn(self):
        self.add_property_pages()
        self.manifest["files"] = [e for e in self.manifest["files"] if e["title"] != "Object"]
        self.save_manifest()
        _, payload, _ = self.invoke("Label.mouse_filter", "--show-best")
        self.assertFalse(payload["missing_ancestors"])
        self.assertFalse(payload["warnings"])

    def test_operator_and_cross_class_ambiguity_survives_output_limit(self):
        page = self.fixture.root / "classes/class_vector3.md"
        page.write_text(page.read_text() + '\n---\n\n' + r'Vector3 **operator \***(right: Vector3)' + '\n')
        self.add_class("OtherObject", "## Method Descriptions\n\nvoid **free**()\n")
        for query in ("Vector3.operator *", "free()"):
            for options in (("--show-best",), ("--limit", "1"), ()):
                with self.subTest(query=query, options=options):
                    code, payload, _ = self.invoke(query, *options)
                    self.assertEqual(code, 0)
                    self.assertTrue(payload["ambiguous"])
                    self.assertTrue(payload["warnings"])
                    if options:
                        self.assertEqual(len(payload["results"]), 1)
            _, text, _ = self.invoke(query, "--show-best", json_output=False)
            self.assertIn("尚未消歧", text)

    def test_overridden_methods_and_concept_candidates_are_not_ambiguous(self):
        self.add_class("CustomObject", "**Inherits:** Object\n\n## Method Descriptions\n\nvoid **free**()\n")
        for query in ("CustomObject.free", "input actions"):
            _, payload, _ = self.invoke(query, "--show-best")
            self.assertFalse(payload["ambiguous"])
            self.assertFalse(payload["warnings"])


class UsageLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = CorpusFixture()
        self.addCleanup(self.fixture.close)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.log_path = Path(temporary.name) / "logs" / "usage.jsonl"
        location = mock.patch.object(search_godot_docs, "SKILL_DIR", Path(temporary.name))
        location.start()
        self.addCleanup(location.stop)
        environment = mock.patch.dict(os.environ, {"GODOT_DOCS_LOG_FILE": "", "GODOT_DOCS_TASK_ID": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def invoke(self, query="Node.queue_free", options=()):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = search_godot_docs.main([
                query, "--docs-root", str(self.fixture.root), "--json", *options,
            ])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_local_config_relative_path_and_disabled_override(self):
        config = search_godot_docs.SKILL_DIR / "config.local.json"
        config.write_text(json.dumps({"LOG_FILE": "logs/usage.jsonl"}))
        with mock.patch.dict(os.environ, {"GODOT_DOCS_LOG_FILE": str(self.log_path.parent / "old.jsonl")}):
            self.assertEqual(self.invoke()[0], 0)
            self.assertEqual(len(self.read_records()), 1)
            config.write_text('{"LOG_FILE": null}')
            self.assertEqual(self.invoke()[0], 0)
            self.assertFalse((self.log_path.parent / "old.jsonl").exists())
            self.assertEqual(len(self.read_records()), 1)
            self.assertEqual(self.invoke(options=["--log-file", str(self.log_path)])[0], 0)
            self.assertEqual(len(self.read_records()), 2)

    def test_invalid_local_config_is_nonblocking(self):
        config = search_godot_docs.SKILL_DIR / "config.local.json"
        for content in ('{', '[]', '{"LOG_FILE": true}'):
            config.write_text(content)
            code, output, error = self.invoke()
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(output))
            self.assertIn("本地配置读取失败", error)
            self.assertFalse(self.log_path.exists())

    def read_records(self):
        return [json.loads(line) for line in self.log_path.read_text().splitlines()]

    def test_missing_config_or_key_ignores_environment(self) -> None:
        with mock.patch.object(search_godot_docs, "append_usage_log") as append:
            self.assertEqual(self.invoke()[0], 0)
            with mock.patch.dict(os.environ, {"GODOT_DOCS_LOG_FILE": str(self.log_path)}):
                self.assertEqual(self.invoke()[0], 0)
                (search_godot_docs.SKILL_DIR / "config.local.json").write_text("{}")
                self.assertEqual(self.invoke()[0], 0)
            append.assert_not_called()
        self.assertFalse(self.log_path.parent.exists())

    def test_config_appends_metadata_without_changing_output(self) -> None:
        expected = self.invoke()
        (search_godot_docs.SKILL_DIR / "config.local.json").write_text(json.dumps({"LOG_FILE": str(self.log_path)}))
        with mock.patch.dict(os.environ, {
            "GODOT_DOCS_LOG_FILE": str(self.log_path), "GODOT_DOCS_TASK_ID": "task-1",
        }):
            self.assertEqual(self.invoke(), expected)
            self.assertEqual(self.invoke(), expected)
        records = self.read_records()
        self.assertEqual(len(records), 2)
        record = records[0]
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["task_id"], "task-1")
        self.assertEqual(record["godot_version"], "4.7")
        self.assertEqual(record["source_commit"], "fixture-commit")
        self.assertEqual(record["result_count"], 1)
        self.assertEqual(record["results"][0]["kind"], "method")
        self.assertNotIn("excerpt", record["results"][0])
        self.assertGreaterEqual(record["duration_ms"], 0)

    def test_cli_path_overrides_environment(self) -> None:
        other = self.log_path.parent / "other.jsonl"
        with mock.patch.dict(os.environ, {"GODOT_DOCS_LOG_FILE": str(other)}):
            self.assertEqual(self.invoke(options=["--log-file", str(self.log_path)])[0], 0)
        self.assertTrue(self.log_path.exists())
        self.assertFalse(other.exists())

    def test_no_matches_errors_and_ambiguity_are_recorded(self) -> None:
        (search_godot_docs.SKILL_DIR / "config.local.json").write_text(json.dumps({"LOG_FILE": str(self.log_path)}))
        with mock.patch.dict(os.environ, {"GODOT_DOCS_LOG_FILE": str(self.log_path)}):
            self.assertEqual(self.invoke("Wrong.member")[0], 1)
            self.assertEqual(self.invoke(options=["--limit", "0"])[0], 2)
            self.assertEqual(self.invoke(options=["--docs-root", str(self.log_path.parent / "missing")])[0], 2)
            self.assertEqual(self.invoke("Vector2(1)", ["--show-best"])[0], 0)
        records = self.read_records()
        self.assertEqual([r["status"] for r in records], ["no_matches", "error", "error", "ok"])
        self.assertEqual(records[0]["result_count"], 0)
        self.assertIn("--limit", records[1]["error"])
        self.assertIn("manifest.json", records[2]["error"])
        self.assertTrue(records[3]["warnings"])
        self.assertTrue(records[3]["ambiguous"])

    def test_version_conflict_and_incomplete_evidence_are_logged(self):
        options = ["--log-file", str(self.log_path)]
        self.assertEqual(self.invoke(options=[*options, "--version", "4.6"])[0], 2)
        manifest_path = self.fixture.root / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["build"] = {"selected_sources": ["classes/class_button.rst"]}
        manifest["files"] = [entry for entry in manifest["files"] if entry["title"] != "BaseButton"]
        manifest_path.write_text(json.dumps(manifest))
        self.assertEqual(self.invoke("Button.pressed", options)[0], 1)
        conflict, incomplete = self.read_records()
        self.assertEqual(conflict["requested_version"], "4.6")
        self.assertEqual(conflict["godot_version"], "4.7")
        self.assertEqual(conflict["status"], "error")
        self.assertEqual(incomplete["corpus_coverage"], "partial")
        self.assertIn("BaseButton", incomplete["missing_ancestors"])
        self.assertTrue(incomplete["warnings"])

    def test_unwritable_log_does_not_change_search_or_json(self) -> None:
        self.log_path.mkdir(parents=True)
        expected_code, expected_output, _ = self.invoke()
        code, output, error = self.invoke(options=["--log-file", str(self.log_path)])
        self.assertEqual((code, output), (expected_code, expected_output))
        self.assertIn("日志写入失败", error)

    def test_log_cannot_modify_corpus_or_references(self) -> None:
        targets = [self.fixture.root / "usage.jsonl", self.log_path.parent / "references" / "usage.jsonl"]
        for target in targets:
            with self.subTest(target=target):
                code, output, error = self.invoke(options=["--log-file", str(target)])
                self.assertEqual(code, 0)
                self.assertTrue(json.loads(output)["results"])
                self.assertIn("日志写入失败", error)
                self.assertFalse(target.exists())
        alias = self.log_path.parent.parent / "corpus-link"
        alias.symlink_to(self.fixture.root, target_is_directory=True)
        self.assertIn("日志写入失败", self.invoke(options=["--log-file", str(alias / "usage.jsonl")])[2])
        self.assertFalse((self.fixture.root / "usage.jsonl").exists())


class FailureTests(unittest.TestCase):
    def test_non_object_manifest_reports_corpus_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for value in ([], None, "manifest", 1, True):
                with self.subTest(value=value):
                    (root / "manifest.json").write_text(json.dumps(value), encoding="utf-8")
                    stderr = io.StringIO()
                    with contextlib.redirect_stderr(stderr):
                        exit_code = search_godot_docs.main(["Node", "--docs-root", str(root), "--no-log"])
                    self.assertEqual(exit_code, 2)
                    self.assertIn("manifest", stderr.getvalue())
                    self.assertNotIn("Traceback", stderr.getvalue())

    def test_dot_version_is_a_safe_directory_component(self) -> None:
        self.assertEqual(search_godot_docs.validate_version("4.7"), "4.7")

    def test_version_rejects_path_traversal(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            search_godot_docs.validate_version("../4.7")

    def test_manifest_rejects_parent_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = {
                "schema_version": 2,
                "godot_docs": {"version": "4.7", "source_commit": "fixture"},
                "files": [
                    {
                        "path": "../outside.md",
                        "title": "Outside",
                        "source_path": "outside.rst",
                        "license": "CC-BY-3.0",
                    }
                ],
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(search_godot_docs.CorpusError, "不安全"):
                search_godot_docs.load_corpus(root)

    def test_missing_corpus_reports_deployer_action_without_building(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = search_godot_docs.main(
                    ["Node", "--docs-root", str(Path(temporary) / "missing"), "--no-log"]
                )
            self.assertEqual(exit_code, 2)
            self.assertIn("部署者需要运行 scripts/build_godot_docs.py", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
