---
name: godot-local-docs-ref
description: Use locally generated, version-matched Godot documentation when the user requests documentation-backed guidance or when an answer or action materially depends on an engine fact that may vary by version, may have changed, is uncertain or disputed, or requires exact confirmation.
---

# Godot local documentation reference

Establish reliable, version-matched Godot engine knowledge from the locally generated documentation while keeping retrieval focused.

## Decide whether to search

Search when a reliable result materially depends on a Godot-specific fact and at least one of these conditions applies:

- The fact may differ across Godot versions or may have changed.
- An exact API contract, default, lifecycle rule, workflow, warning, or error meaning affects the result.
- The available context leaves the engine behavior uncertain or conflicting.
- The user requests documentation-backed or version-specific confirmation.

Use project inspection for facts about the user's files and runtime state. Combine project evidence with documentation when the observed state also depends on an engine contract.

Reuse facts already established in the current task. Start with one focused query and broaden only when its result is insufficient.

## Select the documentation version

- Determine the target version from the request or reliable project evidence, then use `references/godot-docs/<version>` with `--version <version>`.
- When the version is unknown and exactly one corpus is installed, use it and identify its version in the answer.
- When several corpora are installed and the version affects the conclusion, surface the version ambiguity before relying on one.
- If the matching `manifest.json` is missing, report that the requested corpus is unavailable. Corpus preparation belongs to the deployer; the runtime Agent must not run `scripts/build_godot_docs.py` automatically.

## Search

Use the read-only search helper to return bounded, ranked evidence.

```bash
python3 <skill-dir>/scripts/search_godot_docs.py "Node.queue_free" --version <version> --show-best
python3 <skill-dir>/scripts/search_godot_docs.py "Creating your first script" --version <version> --mode title
python3 <skill-dir>/scripts/search_godot_docs.py "Indented block expected" --version <version> --mode content
```

- Use the default `auto` mode for a class, `Class.member`, a constructor or instantiation expression such as `Vector2()` or `JSON.new()`, or initial discovery. Inherited members fall back to their defining class.
- Use `--mode title` for a known page, `--mode section` for a known heading, and `--mode content` for an exact phrase or error.
- Use `--show-best` when the query is precise; use the default ranked list while discovering the right source. The list includes excerpts for the top three results and compact indexes for the rest.
- When a result provides only an index, its excerpt is truncated, or the conclusion requires adjacent context, use its `path:line` to locate `references/godot-docs/<version>/<path>` and read the smallest local range that confirms the fact.
- Form queries with the official English terminology used by the documentation. Translate non-English concepts before searching, then refine an insufficient result or a lower indexed result with the bare member name, exact wording, or terms found in the ranked results.

Use class pages for signatures, defaults, inheritance, signals, warnings, and deprecations. Use manual pages for concepts, workflows, and examples. Consult both when reliable guidance requires the API contract and its intended usage.

## Apply the evidence

- Identify the source version and match it to the target before applying the evidence.
- Cite the reported local path and heading for non-obvious claims.
- Distinguish documented facts from inferences and project observations, and state any uncertainty the installed corpus does not resolve.
