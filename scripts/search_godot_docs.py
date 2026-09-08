#!/usr/bin/env python3
"""从本地 Godot 文档语料中检索并提取范围受限的章节。

此工具只读访问 build_godot_docs.py 生成的 manifest 和 Markdown 文件，
不下载或构建文档；显式启用日志时，仅在语料目录之外追加使用记录。
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCRIPT_VERSION = "1.5.0"
DEFAULT_VERSION = "4.7"
RANKED_EXCERPT_LIMIT = 3
SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DOCS_PARENT = SKILL_DIR / "references" / "godot-docs"
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^(?:> ?)*```")
BOLD_NAME_RE = re.compile(r"\*\*((?:\\.|(?!\*\*).)+?)\*\*")
ENUM_HEADER_RE = re.compile(
    r"^(?:enum|flags)\s+\*\*((?:\\.|(?!\*\*).)+?)\*\*:\s*$"
)
ASSIGNMENT_DECLARATION_RE = re.compile(
    r"^.*?\*\*((?:\\.|(?!\*\*).)+?)\*\*\s*="
)
INHERITS_RE = re.compile(r"^\*\*Inherits:\*\*\s*(.+?)\s*$")
EMPTY_CALL_SUFFIX_RE = re.compile(r"\(\s*\)\s*$")
CALL_EXPRESSION_RE = re.compile(
    r"^(@?[A-Za-z_][A-Za-z0-9_]*(?:\.@?[A-Za-z_][A-Za-z0-9_]*)*)\s*\((.*)\)\s*$",
    re.DOTALL,
)
CAMEL_BOUNDARY_RE = re.compile(
    r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Za-z])(?=[0-9])|(?<=[0-9])(?=[A-Za-z])"
)
CAMEL_IDENTIFIER_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9]*[a-z0-9][A-Z][A-Za-z0-9]*\b")
SEARCH_SEPARATOR_RE = re.compile(r"[^\w@]+", flags=re.UNICODE)
CLASS_MEMBER_SECTIONS = {
    "signals": "signal",
    "enumerations": "enumeration",
    "constants": "constant",
    "annotations": "annotation",
    "property descriptions": "property",
    "method descriptions": "method",
    "constructor descriptions": "constructor",
    "operator descriptions": "operator",
    "theme property descriptions": "theme-property",
}
STRUCTURED_RESULT_KINDS = frozenset(CLASS_MEMBER_SECTIONS.values())
CLASS_SECTION_ALIASES = {
    "signal": "Signals",
    "signals": "Signals",
    "enumeration": "Enumerations",
    "enumerations": "Enumerations",
    "enum": "Enumerations",
    "enums": "Enumerations",
    "constant": "Constants",
    "constants": "Constants",
    "annotation": "Annotations",
    "annotations": "Annotations",
    "property": "Property Descriptions",
    "properties": "Property Descriptions",
    "method": "Method Descriptions",
    "methods": "Method Descriptions",
    "constructor": "Constructor Descriptions",
    "constructors": "Constructor Descriptions",
    "operator": "Operator Descriptions",
    "operators": "Operator Descriptions",
    "theme property": "Theme Property Descriptions",
    "theme properties": "Theme Property Descriptions",
}


class CorpusError(RuntimeError):
    """查找或校验语料时可向用户报告的失败。"""


@dataclass(frozen=True)
class Document:
    root: Path
    relative_path: str
    title: str
    source_path: str
    license: str

    @property
    def path(self) -> Path:
        return self.root / self.relative_path

    @property
    def is_class_reference(self) -> bool:
        return self.relative_path.startswith("classes/")


@dataclass(frozen=True)
class Corpus:
    root: Path
    version: str
    commit: str
    schema_version: int
    documents: Tuple[Document, ...]


@dataclass(frozen=True)
class Section:
    level: int
    title: str
    start: int
    end: int


@dataclass(frozen=True)
class MemberBlock:
    kind: str
    heading: str
    start: int
    end: int
    declared_names: Tuple[str, ...]
    callable_names: Tuple[str, ...] = ()
    container: Optional[str] = None


@dataclass(frozen=True)
class ParsedQuery:
    raw: str
    normalized: str
    terms: Tuple[str, ...]
    class_document: Optional[Document] = None
    member: Optional[str] = None
    constructor_arity: Optional[int] = None
    invalid_explicit_call: bool = False


@dataclass(frozen=True)
class SearchResult:
    document: Document
    kind: str
    score: int
    line: int
    heading: Optional[str]
    excerpt: str
    truncated: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.document.title,
            "path": self.document.relative_path,
            "line": self.line,
            "heading": self.heading,
            "score": self.score,
            "excerpt": self.excerpt,
            "truncated": self.truncated,
        }


def validate_version(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", value):
        raise argparse.ArgumentTypeError(
            "version 必须以字母或数字开头，且只能包含字母、数字、'.'、'_'、'+' 或 '-'"
        )
    return value


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="检索本地 Godot Markdown，提取范围受限的类成员或手册章节。"
    )
    parser.add_argument("query", help="类、成员、章节、概念、错误文本或精确短语")
    parser.add_argument(
        "--mode",
        choices=("auto", "title", "member", "section", "content"),
        default="auto",
        help="检索策略（默认：auto）",
    )
    parser.add_argument("--version", type=validate_version, default=DEFAULT_VERSION)
    parser.add_argument(
        "--docs-root",
        type=Path,
        help="显式指定生成的语料目录（默认：<skill>/references/godot-docs/<version>）",
    )
    parser.add_argument("--limit", type=int, default=5, help="排序结果数量上限（默认：5）")
    parser.add_argument(
        "--context",
        type=int,
        default=2,
        help="非结构化内容匹配的上下文行数（默认：2）",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        help="每项结果的摘要字符数上限（默认：800，使用 --show-best 时为 6000）",
    )
    parser.add_argument(
        "--show-best",
        action="store_true",
        help="仅输出最佳结构块，并提供更长摘要",
    )
    parser.add_argument("--json", action="store_true", help="以格式确定的 JSON 输出结果")
    logging = parser.add_mutually_exclusive_group()
    logging.add_argument(
        "--log-file", type=Path,
        help="追加 JSONL 使用日志；也可通过 GODOT_DOCS_LOG_FILE 配置，默认关闭",
    )
    logging.add_argument("--no-log", action="store_true", help="本次关闭日志，覆盖环境变量配置")
    return parser.parse_args(argv)


def normalize(value: str) -> str:
    value = CAMEL_BOUNDARY_RE.sub(" ", value)
    return normalize_prose(value)


def normalize_prose(value: str) -> str:
    value = value.casefold().replace("_", " ")
    return SEARCH_SEPARATOR_RE.sub(" ", value).strip()


def split_top_level_arguments(value: str) -> Optional[Tuple[str, ...]]:
    """拆分调用参数列表，同时保留嵌套集合与字符串的完整性。"""
    if not value.strip():
        return ()

    arguments: List[str] = []
    stack: List[str] = []
    quote: Optional[str] = None
    escaped = False
    start = 0
    closing_to_opening = {")": "(", "]": "[", "}": "{"}

    for index, character in enumerate(value):
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue

        if character in {'"', "'"}:
            quote = character
        elif character in "([{":
            stack.append(character)
        elif character in ")]}":
            if not stack or stack[-1] != closing_to_opening[character]:
                return None
            stack.pop()
        elif character == "," and not stack:
            argument = value[start:index].strip()
            if not argument:
                return None
            arguments.append(argument)
            start = index + 1

    if quote is not None or stack:
        return None
    argument = value[start:].strip()
    if not argument:
        return None
    arguments.append(argument)
    return tuple(arguments)


def parse_call_expression(value: str) -> Optional[Tuple[str, Tuple[str, ...]]]:
    """解析带限定名称的调用表达式，返回被调用对象与参数。"""
    candidate = re.sub(r"::", ".", value.strip())
    match = CALL_EXPRESSION_RE.fullmatch(candidate)
    if not match:
        return None
    arguments = split_top_level_arguments(match.group(2))
    if arguments is None:
        return None
    return match.group(1), arguments


def constructor_declaration_arity(value: str) -> Optional[int]:
    """从一条生成的构造函数声明中读取位置参数数量。"""
    match = BOLD_NAME_RE.search(value)
    if not match:
        return None
    parsed = parse_call_expression("Constructor" + value[match.end() :].strip())
    return len(parsed[1]) if parsed else None


def searchable_text(value: str) -> str:
    """以较低开销规范化文本，并提取 CamelCase 标识符内部的词项。"""
    base = SEARCH_SEPARATOR_RE.sub(" ", value.casefold().replace("_", " "))
    expansions = [
        CAMEL_BOUNDARY_RE.sub(" ", identifier).casefold()
        for identifier in CAMEL_IDENTIFIER_RE.findall(value)
    ]
    return f"{base} {' '.join(expansions)}".strip()


def canonical_term(value: str) -> str:
    """不依赖语言处理库，归并几种常见的英文词形变化。"""
    if len(value) > 4 and value.endswith("ied"):
        return value[:-3] + "y"
    if len(value) > 4 and value.endswith("ed"):
        stem = value[:-2]
        if stem.endswith(("at", "iz", "ov", "us")):
            stem += "e"
        return stem
    if len(value) > 6 and value.endswith("ing"):
        stem = value[:-3]
        if len(stem) > 2 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        elif stem.endswith(("at", "iz", "ov", "us")):
            stem += "e"
        return stem
    if len(value) > 4 and value.endswith("ies"):
        return value[:-3] + "y"
    if len(value) > 4 and value.endswith(("sses", "xes", "zes", "ches", "shes")):
        return value[:-2]
    if (
        len(value) > 4
        and value.endswith("s")
        and not value.endswith(("as", "ics", "is", "ss", "us"))
    ):
        return value[:-1]
    return value


def query_terms(value: str) -> Tuple[str, ...]:
    normalized = normalize(value)
    return tuple(
        dict.fromkeys(canonical_term(part) for part in normalized.split() if part)
    )


def class_section_alias(value: str) -> Optional[str]:
    """解析章节词项，同时保留成员名中有意义的标点。"""
    candidate = value.casefold().replace("_", " ")
    candidate = re.sub(r"(?<=\w)-(?=\w)", " ", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip()
    return CLASS_SECTION_ALIASES.get(candidate)


def term_coverage(terms: Sequence[str], text: str) -> Tuple[int, int]:
    expected = set(terms)
    counts = term_counts(expected, text)
    return sum(bool(counts[term]) for term in expected), len(expected)


@lru_cache(maxsize=512)
def term_pattern(term: str) -> re.Pattern[str]:
    forms = {term}
    if len(term) > 2:
        if term.endswith("y") and term[-2] not in "aeiou":
            forms.add(term[:-1] + "ies")
        else:
            forms.add(term + "s")
        forms.add(term + "es")
        if term.endswith("e"):
            forms.add(term + "d")
            forms.add(term[:-1] + "ing")
        else:
            forms.add(term + "ed")
            forms.add(term + "ing")
    alternatives = "|".join(
        re.escape(form) for form in sorted(forms, key=lambda item: (-len(item), item))
    )
    return re.compile(rf"\b(?:{alternatives})\b")


def term_counts(terms: Iterable[str], text: str) -> Counter[str]:
    normalized = searchable_text(text)
    return Counter(
        {
            term: len(term_pattern(term).findall(normalized))
            for term in set(terms)
        }
    )


def safe_relative_path(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def load_corpus(root: Path) -> Corpus:
    root = root.expanduser().resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise CorpusError(
            f"{root} 未安装生成的 Godot 文档（缺少 manifest.json）；"
            "部署者需要运行 scripts/build_godot_docs.py"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusError(f"无法读取生成文档的 manifest {manifest_path}：{error}") from error

    if not isinstance(manifest, dict):
        raise CorpusError(f"生成文档的 manifest 顶层必须为对象：{manifest_path}")
    schema = manifest.get("schema_version")
    docs_metadata = manifest.get("godot_docs")
    file_entries = manifest.get("files")
    if not isinstance(schema, int) or schema < 1:
        raise CorpusError(f"{manifest_path} 中的 manifest schema_version 无效")
    if not isinstance(docs_metadata, dict) or not isinstance(file_entries, list):
        raise CorpusError(f"生成文档的 manifest 结构无效：{manifest_path}")
    version = docs_metadata.get("version")
    commit = docs_metadata.get("source_commit")
    if not isinstance(version, str) or not isinstance(commit, str):
        raise CorpusError(f"manifest 缺少 Godot 版本或来源 commit：{manifest_path}")

    documents: List[Document] = []
    seen: set[str] = set()
    for entry in file_entries:
        if not isinstance(entry, dict):
            raise CorpusError(f"{manifest_path} 中的文件条目无效")
        relative = entry.get("path")
        title = entry.get("title")
        source_path = entry.get("source_path")
        license_id = entry.get("license")
        if not all(isinstance(value, str) for value in (relative, title, source_path, license_id)):
            raise CorpusError(f"manifest 文件条目缺少必需的字符串：{entry!r}")
        if not safe_relative_path(relative) or not relative.endswith(".md"):
            raise CorpusError(f"manifest 中的 Markdown 路径不安全或无效：{relative!r}")
        if relative in seen:
            raise CorpusError(f"manifest 中的 Markdown 路径重复：{relative}")
        seen.add(relative)
        documents.append(Document(root, relative, title, source_path, license_id))
    if not documents:
        raise CorpusError(f"生成文档的 manifest 不包含任何页面：{manifest_path}")
    return Corpus(root, version, commit, schema, tuple(documents))


def default_docs_root(version: str) -> Path:
    return DEFAULT_DOCS_PARENT / version


def read_lines(document: Document, cache: Dict[str, List[str]]) -> List[str]:
    if document.relative_path not in cache:
        try:
            cache[document.relative_path] = document.path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        except OSError as error:
            raise CorpusError(f"无法读取 manifest 中的页面 {document.path}：{error}") from error
    return cache[document.relative_path]


def body_start(lines: Sequence[str]) -> int:
    if lines and lines[0].strip() == "---":
        for index in range(1, min(len(lines), 100)):
            if lines[index].strip() == "---":
                return index + 1
    return 0


def fenced_lines(lines: Sequence[str]) -> List[bool]:
    states: List[bool] = []
    inside = False
    for line in lines:
        states.append(inside)
        if FENCE_RE.match(line):
            inside = not inside
    return states


def parse_sections(lines: Sequence[str]) -> List[Section]:
    fenced = fenced_lines(lines)
    headings: List[Tuple[int, int, str]] = []
    start = body_start(lines)
    for index in range(start, len(lines)):
        if fenced[index]:
            continue
        match = HEADING_RE.match(lines[index])
        if match:
            headings.append((index, len(match.group(1)), match.group(2).strip()))
    sections: List[Section] = []
    for position, (line_index, level, title) in enumerate(headings):
        end = len(lines)
        for next_index, next_level, _ in headings[position + 1 :]:
            if next_level <= level:
                end = next_index
                break
        sections.append(Section(level, title, line_index, end))
    return sections


def unescape_markdown_name(value: str) -> str:
    return re.sub(r"\\(.)", r"\1", value).strip()


def declared_names(value: str) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """返回加粗的声明名称，以及其中后接调用签名的名称子集。"""
    names: List[str] = []
    callable_names: List[str] = []
    for match in BOLD_NAME_RE.finditer(value):
        name = unescape_markdown_name(match.group(1))
        if not name:
            continue
        names.append(name)
        if value[match.end() :].lstrip().startswith("("):
            callable_names.append(name)
    return tuple(dict.fromkeys(names)), tuple(dict.fromkeys(callable_names))


def declaration_aliases(
    lines: Sequence[str], start: int, end: int
) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """返回主声明及其紧邻的可调用访问器别名。"""
    primary_names, primary_callables = declared_names(lines[start])
    names: List[str] = list(primary_names)
    callable_names: List[str] = list(primary_callables)
    index = start + 1
    while index < end:
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        if not stripped.startswith("- "):
            break
        aliases, callable_aliases = declared_names(stripped)
        names.extend(aliases)
        callable_names.extend(callable_aliases)
        index += 1
    return tuple(dict.fromkeys(names)), tuple(dict.fromkeys(callable_names))


def assignment_declarations(
    lines: Sequence[str], start: int, end: int, fenced: Sequence[bool]
) -> List[Tuple[int, str]]:
    declarations: List[Tuple[int, str]] = []
    for index in range(start, end):
        if fenced[index]:
            continue
        match = ASSIGNMENT_DECLARATION_RE.match(lines[index].strip())
        if match:
            declarations.append((index, unescape_markdown_name(match.group(1))))
    return declarations


def class_member_blocks(lines: Sequence[str], sections: Sequence[Section]) -> List[MemberBlock]:
    fenced = fenced_lines(lines)
    blocks: List[MemberBlock] = []
    for section in sections:
        if section.level != 2:
            continue
        kind = CLASS_MEMBER_SECTIONS.get(normalize(section.title))
        if not kind:
            continue
        boundaries = [section.start + 1]
        boundaries.extend(
            index
            for index in range(section.start + 1, section.end)
            if not fenced[index] and lines[index].strip() == "---"
        )
        boundaries.append(section.end)
        for begin, end in zip(boundaries, boundaries[1:]):
            if begin < end and lines[begin].strip() == "---":
                begin += 1
            while begin < end and not lines[begin].strip():
                begin += 1
            while end > begin and not lines[end - 1].strip():
                end -= 1
            if begin >= end:
                continue

            if kind == "enumeration":
                header = ENUM_HEADER_RE.match(lines[begin].strip())
                if not header:
                    continue
                container = unescape_markdown_name(header.group(1))
                blocks.append(
                    MemberBlock(
                        kind=kind,
                        heading=section.title,
                        start=begin,
                        end=end,
                        declared_names=(container,),
                        container=container,
                    )
                )
                declarations = assignment_declarations(lines, begin + 1, end, fenced)
                for position, (item_start, name) in enumerate(declarations):
                    item_end = (
                        declarations[position + 1][0]
                        if position + 1 < len(declarations)
                        else end
                    )
                    blocks.append(
                        MemberBlock(
                            kind=kind,
                            heading=section.title,
                            start=item_start,
                            end=item_end,
                            declared_names=(name,),
                            container=container,
                        )
                    )
                continue

            if kind == "constant":
                declarations = assignment_declarations(lines, begin, end, fenced)
                for position, (item_start, name) in enumerate(declarations):
                    item_end = (
                        declarations[position + 1][0]
                        if position + 1 < len(declarations)
                        else end
                    )
                    blocks.append(
                        MemberBlock(
                            kind=kind,
                            heading=section.title,
                            start=item_start,
                            end=item_end,
                            declared_names=(name,),
                        )
                    )
                continue

            names, callable_names = declaration_aliases(lines, begin, end)
            if names:
                blocks.append(
                    MemberBlock(
                        kind=kind,
                        heading=section.title,
                        start=begin,
                        end=end,
                        declared_names=names,
                        callable_names=callable_names,
                    )
                )
    return blocks


def containing_section(sections: Sequence[Section], line_index: int) -> Optional[Section]:
    candidates = [section for section in sections if section.start <= line_index < section.end]
    if not candidates:
        return None
    return max(candidates, key=lambda section: section.level)


def truncate_text(text: str, max_chars: int) -> Tuple[str, bool]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(text) <= max_chars:
        return text, False
    cut = text.rfind("\n", 0, max_chars)
    if cut < max_chars // 2:
        cut = text.rfind(" ", 0, max_chars)
    if cut < max_chars // 2:
        cut = max_chars
    return text[:cut].rstrip() + "\n…", True


def text_for_range(lines: Sequence[str], start: int, end: int, max_chars: int) -> Tuple[str, bool]:
    return truncate_text("\n".join(lines[start:end]), max_chars)


def score_title(document: Document, parsed: ParsedQuery) -> int:
    title = normalize(document.title)
    path = normalize(document.relative_path)
    query = parsed.normalized
    if not query:
        return 0
    score = 0
    if title == query:
        score += 1000
    elif title.startswith(query) or query.startswith(title + " "):
        score += 550
    elif query in title:
        score += 350
    elif len(query) >= 5 and len(title) >= 5:
        similarity = SequenceMatcher(None, title, query).ratio()
        if similarity >= 0.90:
            score += 650
        elif similarity >= 0.82:
            score += 380
        elif similarity >= 0.72:
            score += 180
    if query in path:
        score += 180
    title_hits, term_count = term_coverage(parsed.terms, document.title)
    path_hits, _ = term_coverage(parsed.terms, document.relative_path)
    if term_count and title_hits == term_count:
        score += 650
    elif term_count:
        coverage = title_hits / term_count
        if coverage >= 2 / 3:
            score += 260
        elif coverage >= 1 / 2:
            score += 140
        elif title_hits:
            score += 60
    if term_count and path_hits == term_count:
        score += 160
    return score


def split_explicit_class_member(
    raw_query: str, class_documents: Sequence[Document]
) -> Tuple[Optional[Document], Optional[str]]:
    value = re.sub(r"::", ".", raw_query.strip())
    folded = value.casefold()
    for document in sorted(class_documents, key=lambda item: len(item.title), reverse=True):
        title = document.title.casefold()
        dotted_prefix = title + "."
        if folded.startswith(dotted_prefix):
            member = value[len(dotted_prefix) :].strip()
            if member:
                return document, member

        spaced_prefix = title + " "
        if folded.startswith(spaced_prefix):
            member = value[len(spaced_prefix) :].strip()
            if class_section_alias(member):
                return document, member
    return None, None


def parse_query(raw_query: str, corpus: Corpus) -> ParsedQuery:
    raw = raw_query.strip()
    normalized = normalize(raw)
    terms = query_terms(raw)
    class_documents = [document for document in corpus.documents if document.is_class_reference]
    classes_by_name = {
        document.title.casefold(): document for document in class_documents
    }

    call = parse_call_expression(raw)
    if call:
        callee, arguments = call
        class_document = classes_by_name.get(callee.casefold())
        if class_document:
            return ParsedQuery(
                raw,
                normalized,
                terms,
                class_document,
                class_document.title,
                len(arguments),
            )

        class_document, member = split_explicit_class_member(
            callee, class_documents
        )
        if class_document and member:
            qualifier, name = split_member_target(member)
            if (
                qualifier is None
                and canonical_member_name(name)
                == canonical_member_name(class_document.title)
            ):
                return ParsedQuery(
                    raw,
                    normalized,
                    terms,
                    class_document,
                    member,
                    len(arguments),
                )
            return ParsedQuery(
                raw,
                normalized,
                terms,
                class_document,
                member + "()",
            )
        if "." not in callee:
            return ParsedQuery(raw, normalized, terms, member=callee + "()")
        return ParsedQuery(
            raw,
            normalized,
            terms,
            invalid_explicit_call=True,
        )

    normalized_separators = re.sub(r"::", ".", raw)
    for document in sorted(class_documents, key=lambda item: len(item.title), reverse=True):
        if re.match(
            rf"^{re.escape(document.title)}\s*\(",
            normalized_separators,
            flags=re.IGNORECASE,
        ):
            return ParsedQuery(
                raw,
                normalized,
                terms,
                document,
                document.title,
                invalid_explicit_call=True,
            )

    class_document, member = split_explicit_class_member(raw, class_documents)
    return ParsedQuery(raw, normalized, terms, class_document, member)


def canonical_member_name(value: str) -> str:
    candidate = unescape_markdown_name(value)
    candidate = EMPTY_CALL_SUFFIX_RE.sub("", candidate).rstrip()
    return re.sub(r"\s+", " ", candidate).casefold()


def split_member_target(value: str) -> Tuple[Optional[str], str]:
    candidate = re.sub(r"::", ".", value.strip())
    candidate = EMPTY_CALL_SUFFIX_RE.sub("", candidate).rstrip()
    if "." not in candidate:
        return None, candidate
    qualifier, name = candidate.rsplit(".", 1)
    return qualifier.strip() or None, name.strip()


def member_block_matches(block: MemberBlock, document: Document, target: str) -> bool:
    qualifier, name = split_member_target(target)
    expected = canonical_member_name(name)
    if not expected or expected not in {
        canonical_member_name(candidate) for candidate in block.declared_names
    }:
        return False
    if EMPTY_CALL_SUFFIX_RE.search(target) and expected not in {
        canonical_member_name(candidate) for candidate in block.callable_names
    }:
        return False
    if qualifier is None:
        return True
    allowed_qualifiers = {canonical_member_name(document.title)}
    if block.container:
        allowed_qualifiers.add(canonical_member_name(block.container))
    return canonical_member_name(qualifier) in allowed_qualifiers


def inheritance_names(lines: Sequence[str]) -> Tuple[str, ...]:
    for line in lines[body_start(lines) : min(len(lines), body_start(lines) + 40)]:
        match = INHERITS_RE.match(line.strip())
        if not match:
            continue
        plain = match.group(1).replace("**", "")
        return tuple(
            name
            for name in (unescape_markdown_name(part) for part in plain.split("<"))
            if name
        )
    return ()


def class_lineage(
    corpus: Corpus,
    document: Document,
    cache: Dict[str, List[str]],
) -> Tuple[Document, ...]:
    by_title = {
        canonical_member_name(candidate.title): candidate
        for candidate in corpus.documents
        if candidate.is_class_reference
    }
    lineage: List[Document] = [document]
    seen = {document.relative_path}
    for name in inheritance_names(read_lines(document, cache)):
        ancestor = by_title.get(canonical_member_name(name))
        if ancestor is None or ancestor.relative_path in seen:
            continue
        lineage.append(ancestor)
        seen.add(ancestor.relative_path)
    return tuple(lineage)


def title_results(
    corpus: Corpus, parsed: ParsedQuery, max_chars: int, cache: Dict[str, List[str]]
) -> List[SearchResult]:
    results: List[SearchResult] = []
    for document in corpus.documents:
        score = score_title(document, parsed)
        if not score:
            continue
        results.append(document_result(document, score, max_chars, cache))
    return results


def document_result(
    document: Document,
    score: int,
    max_chars: int,
    cache: Dict[str, List[str]],
) -> SearchResult:
    lines = read_lines(document, cache)
    start = body_start(lines)
    end = min(len(lines), start + 24)
    excerpt, truncated = text_for_range(
        lines, start, end, max_chars
    )
    return SearchResult(
        document, "document", score, start + 1, None, excerpt, truncated or end < len(lines)
    )


def implicit_new_document_result(
    parsed: ParsedQuery,
    max_chars: int,
    cache: Dict[str, List[str]],
) -> Optional[SearchResult]:
    if not parsed.class_document or not parsed.member:
        return None
    qualifier, name = split_member_target(parsed.member)
    if qualifier is not None or canonical_member_name(name) != "new":
        return None

    document = parsed.class_document
    lines = read_lines(document, cache)
    object_type = canonical_member_name(document.title) == "object" or any(
        canonical_member_name(ancestor) == "object"
        for ancestor in inheritance_names(lines)
    )
    if not object_type:
        return None
    return document_result(document, 2500, max_chars, cache)


def member_results(
    corpus: Corpus, parsed: ParsedQuery, max_chars: int, cache: Dict[str, List[str]]
) -> List[SearchResult]:
    target = parsed.member or parsed.raw
    if parsed.class_document:
        documents: Iterable[Document] = class_lineage(
            corpus, parsed.class_document, cache
        )
    else:
        documents = (document for document in corpus.documents if document.is_class_reference)
    results: List[SearchResult] = []
    for distance, document in enumerate(documents):
        lines = read_lines(document, cache)
        sections = parse_sections(lines)
        for block in class_member_blocks(lines, sections):
            if not member_block_matches(block, document, target):
                continue
            if parsed.constructor_arity is not None:
                if block.kind != "constructor":
                    continue
                declaration_arity = constructor_declaration_arity(
                    lines[block.start].strip()
                )
                if declaration_arity != parsed.constructor_arity:
                    continue
            block_text = "\n".join(lines[block.start : block.end])
            score = 1800
            if parsed.class_document:
                score += 800 - min(distance, 20) * 20
            if block.kind == "theme-property":
                score -= 400
            else:
                score += 400
            _, requested_name = split_member_target(target)
            if (
                block.declared_names
                and canonical_member_name(block.declared_names[0])
                == canonical_member_name(requested_name)
            ):
                score += 100
            excerpt, truncated = truncate_text(block_text, max_chars)
            results.append(
                SearchResult(
                    document,
                    block.kind,
                    score,
                    block.start + 1,
                    block.heading,
                    excerpt,
                    truncated,
                )
            )
    if parsed.class_document:
        api_results = [result for result in results if result.kind != "theme-property"]
        if api_results:
            return api_results
    return results


def section_results(
    corpus: Corpus,
    parsed: ParsedQuery,
    max_chars: int,
    cache: Dict[str, List[str]],
    documents: Optional[Iterable[Document]] = None,
    target: Optional[str] = None,
) -> List[SearchResult]:
    target_value = target or parsed.raw
    target_normalized = normalize(target_value)
    terms = query_terms(target_value)
    results: List[SearchResult] = []
    for document in documents or corpus.documents:
        lines = read_lines(document, cache)
        for section in parse_sections(lines):
            heading = normalize(section.title)
            score = 0
            if heading == target_normalized:
                score += 850
            elif target_normalized and target_normalized in heading:
                score += 500
            elif terms and term_coverage(terms, section.title)[0] == len(set(terms)):
                score += 260
            if not score:
                continue
            score += min(score_title(document, parsed), 300)
            excerpt, truncated = text_for_range(lines, section.start, section.end, max_chars)
            results.append(
                SearchResult(
                    document,
                    "section",
                    score,
                    section.start + 1,
                    section.title,
                    excerpt,
                    truncated,
                )
            )
    return results


def content_blocks(lines: Sequence[str]) -> List[Tuple[int, int]]:
    blocks: List[Tuple[int, int]] = []
    start = body_start(lines)
    index = start
    while index < len(lines):
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index >= len(lines):
            break
        begin = index
        while index < len(lines) and lines[index].strip():
            index += 1
        blocks.append((begin, index))
    return blocks


def score_content_text(
    text: str,
    target: str,
    terms: Sequence[str],
    flexible_terms: bool = False,
) -> int:
    normalized_line = normalize_prose(text)
    normalized_target = normalize_prose(target)
    if not normalized_line or not normalized_target:
        return 0
    score = 0
    if flexible_terms:
        counts = term_counts(terms, text)
    else:
        counts = Counter(
            {term: normalized_line.count(term) for term in set(terms)}
        )
    covered = sum(bool(counts[term]) for term in set(terms))
    if normalized_line == normalized_target:
        score += 500
    elif normalized_target in normalized_line:
        score += 330
    elif not terms or covered != len(set(terms)):
        return 0
    if terms and covered == len(set(terms)):
        score += 140
    score += sum(min(counts[term], 3) * 8 for term in set(terms))
    return score


def score_page_relevance(
    document: Document,
    parsed: ParsedQuery,
    lines: Sequence[str],
) -> int:
    """对分布在整页中的概念词项评分，不局限于单个段落。"""
    expected = set(parsed.terms)
    if len(expected) < 2:
        return 0

    start = body_start(lines)
    counts = term_counts(expected, "\n".join(lines[start:]))
    if not all(counts[term] for term in expected):
        return 0

    title_hits, _ = term_coverage(expected, document.title)
    heading_text = "\n".join(section.title for section in parse_sections(lines))
    heading_hits, _ = term_coverage(expected, heading_text)

    score = 120
    score += title_hits * 70
    score += heading_hits * 30
    score += sum(min(counts[term], 4) * 8 for term in expected)
    if title_hits == len(expected):
        score += 300
    elif heading_hits == len(expected):
        score += 160
    return score


def best_partial_block(
    lines: Sequence[str], terms: Sequence[str]
) -> Optional[Tuple[int, int]]:
    expected = set(terms)
    best: Optional[Tuple[int, int]] = None
    best_key = (0, 0)
    for begin, end in content_blocks(lines):
        block_text = "\n".join(lines[begin:end])
        counts = term_counts(expected, block_text)
        overlap = sum(bool(counts[term]) for term in expected)
        if not overlap:
            continue
        key = (overlap, -len(block_text))
        if key > best_key:
            best_key = key
            best = (begin, end)
    return best


def content_results(
    corpus: Corpus,
    parsed: ParsedQuery,
    max_chars: int,
    context: int,
    cache: Dict[str, List[str]],
    documents: Optional[Iterable[Document]] = None,
    target: Optional[str] = None,
    page_level: bool = False,
) -> List[SearchResult]:
    target_value = target or parsed.raw
    terms = query_terms(target_value)
    results: List[SearchResult] = []
    for document in documents or corpus.documents:
        lines = read_lines(document, cache)
        fenced = fenced_lines(lines)
        page_score = score_page_relevance(document, parsed, lines) if page_level else 0
        if page_level and len(set(parsed.terms)) >= 2 and not page_score:
            continue
        best_score = 0
        best_range: Optional[Tuple[int, int]] = None
        for begin, end in content_blocks(lines):
            score = score_content_text(
                "\n".join(lines[begin:end]),
                target_value,
                terms,
                flexible_terms=page_level,
            )
            if score and any(fenced[begin:end]):
                score += 25
            if score > best_score:
                best_score = score
                best_range = (begin, end)
        if best_range is None and page_score:
            best_range = best_partial_block(lines, terms)
        if best_range is None:
            continue
        best_start, best_end = best_range
        sections = parse_sections(lines)
        section = containing_section(sections, best_start)
        excerpt, truncated = text_for_range(
            lines,
            max(body_start(lines), best_start - context),
            min(len(lines), best_end + context),
            max_chars,
        )
        best_score = max(best_score, page_score)
        best_score += min(score_title(document, parsed), 220)
        results.append(
            SearchResult(
                document,
                "content",
                best_score,
                best_start + 1,
                section.title if section else None,
                excerpt,
                truncated,
            )
        )
    return results


def identifier_like(value: str) -> bool:
    candidate = value.strip()
    return bool(
        re.fullmatch(
            r"@?[A-Za-z_][A-Za-z0-9_]*(?:(?:\.|::)[A-Za-z_][A-Za-z0-9_]*)*(?:\(\))?",
            candidate,
        )
    )


def sort_and_deduplicate(
    results: Iterable[SearchResult],
    limit: int,
    one_per_document: bool = False,
) -> List[SearchResult]:
    unique: Dict[Tuple[Any, ...], SearchResult] = {}
    for result in results:
        if one_per_document:
            key = (result.document.relative_path,)
        else:
            key = (result.document.relative_path, result.kind, result.line)
        previous = unique.get(key)
        if previous is None or result.score > previous.score:
            unique[key] = result
    ordered = sorted(
        unique.values(),
        key=lambda result: (
            -result.score,
            result.document.relative_path.casefold(),
            result.line,
        ),
    )
    return ordered[:limit]


def search_corpus(
    corpus: Corpus,
    parsed: ParsedQuery,
    mode: str,
    limit: int,
    context: int,
    max_chars: int,
) -> List[SearchResult]:
    cache: Dict[str, List[str]] = {}
    if parsed.invalid_explicit_call and mode in {"auto", "member"}:
        return []
    if mode == "title":
        return sort_and_deduplicate(title_results(corpus, parsed, max_chars, cache), limit)
    if mode == "member":
        return sort_and_deduplicate(member_results(corpus, parsed, max_chars, cache), limit)
    if mode == "section":
        if parsed.class_document and parsed.member:
            section_target = class_section_alias(parsed.member) or parsed.member
            candidates = section_results(
                corpus, parsed, max_chars, cache, (parsed.class_document,), section_target
            )
        else:
            candidates = section_results(corpus, parsed, max_chars, cache)
        return sort_and_deduplicate(candidates, limit)
    if mode == "content":
        if parsed.class_document and parsed.member:
            candidates = content_results(
                corpus,
                parsed,
                max_chars,
                context,
                cache,
                (parsed.class_document,),
                parsed.member,
            )
        else:
            candidates = content_results(corpus, parsed, max_chars, context, cache)
        return sort_and_deduplicate(candidates, limit)

    if parsed.class_document and parsed.member:
        section_target = (
            None
            if parsed.constructor_arity is not None
            else class_section_alias(parsed.member)
        )
        if section_target:
            candidates = section_results(
                corpus, parsed, max_chars, cache, (parsed.class_document,), section_target
            )
            if candidates:
                return sort_and_deduplicate(candidates, limit)
        candidates = member_results(corpus, parsed, max_chars, cache)
        if candidates:
            return sort_and_deduplicate(candidates, limit)
        new_document = implicit_new_document_result(parsed, max_chars, cache)
        return [new_document] if new_document else []

    exact_title = any(normalize(document.title) == parsed.normalized for document in corpus.documents)
    if exact_title:
        return sort_and_deduplicate(title_results(corpus, parsed, max_chars, cache), limit)

    if parsed.member or identifier_like(parsed.raw):
        candidates = member_results(corpus, parsed, max_chars, cache)
        if candidates:
            return sort_and_deduplicate(candidates, limit)
        if parsed.member or "." in re.sub(r"::", ".", parsed.raw.strip()):
            return []

    candidates = title_results(corpus, parsed, max_chars, cache)
    candidates.extend(section_results(corpus, parsed, max_chars, cache))
    candidates.extend(
        content_results(
            corpus,
            parsed,
            max_chars,
            context,
            cache,
            page_level=True,
        )
    )
    return sort_and_deduplicate(candidates, limit, one_per_document=True)


def render_text(
    corpus: Corpus,
    parsed: ParsedQuery,
    mode: str,
    results: Sequence[SearchResult],
    show_best: bool,
    warnings: Sequence[str] = (),
) -> None:
    print(f"Godot {corpus.version} @ {corpus.commit[:12]} | {mode} | {parsed.raw}")
    for warning in warnings:
        print(f"提示：{warning}")
    if not results:
        qualified_identifier = identifier_like(parsed.raw) and "." in re.sub(
            r"::", ".", parsed.raw.strip()
        )
        if mode in {"auto", "member"} and parsed.class_document and parsed.member:
            print(
                "未找到匹配的 API 声明，检索范围为 "
                f"{parsed.class_document.title} 及其文档中的继承链。"
            )
        elif mode in {"auto", "member"} and qualified_identifier:
            print("未找到与此限定标识符匹配的 API 声明。")
        else:
            print("未找到匹配项。请尝试更精确的标题短语或 --mode content。")
        return
    if show_best:
        result = results[0]
        heading = f" — {result.heading}" if result.heading else ""
        print(f"Result: [{result.kind}] {result.document.title}{heading}")
        print(f"Path: {result.document.relative_path}:{result.line}")
        print("---")
        print(result.excerpt)
        if result.truncated:
            print("[摘要已截断；请按 Path 所示位置读取原文]")
        return

    if len(results) > RANKED_EXCERPT_LIMIT:
        print(
            f"Results: {len(results)} "
            f"（前 {RANKED_EXCERPT_LIMIT} 项提供摘要，其余条目仅提供索引）"
        )
    else:
        print(f"Results: {len(results)}")
    for number, result in enumerate(results, 1):
        heading = f" — {result.heading}" if result.heading else ""
        print(f"{number}. [{result.kind}] {result.document.title}{heading}")
        print(f"   {result.document.relative_path}:{result.line}  score={result.score}")
        if number > RANKED_EXCERPT_LIMIT:
            if result.kind in STRUCTURED_RESULT_KINDS:
                declaration = next(
                    (
                        line.strip()
                        for line in result.excerpt.splitlines()
                        if line.strip() and line.strip() != "---"
                    ),
                    None,
                )
                if declaration:
                    print(f"   Declaration: {declaration}")
            continue
        for line in result.excerpt.splitlines():
            print(f"      {line}")
        if result.truncated:
            print("      [摘要已截断]")


def render_json(
    corpus: Corpus,
    parsed: ParsedQuery,
    mode: str,
    results: Sequence[SearchResult],
    warnings: Sequence[str] = (),
) -> None:
    payload = {
        "script_version": SCRIPT_VERSION,
        "godot_version": corpus.version,
        "source_commit": corpus.commit,
        "docs_root": str(corpus.root),
        "query": parsed.raw,
        "mode": mode,
        "results": [result.as_dict() for result in results],
        "warnings": list(warnings),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def run_search(args: argparse.Namespace, record: Dict[str, Any]) -> int:
    def fail(message: str) -> int:
        record["error"] = message[:1000]
        print(f"error: {message}", file=sys.stderr)
        return 2

    if not args.query.strip() or not query_terms(args.query):
        return fail("query 必须包含可检索的字符")
    if not 1 <= args.limit <= 50:
        return fail("--limit 必须介于 1 和 50 之间")
    if not 0 <= args.context <= 20:
        return fail("--context 必须介于 0 和 20 之间")
    max_chars = args.max_chars if args.max_chars is not None else (6000 if args.show_best else 800)
    if not 200 <= max_chars <= 50000:
        return fail("--max-chars 必须介于 200 和 50000 之间")

    root = args.docs_root if args.docs_root else default_docs_root(args.version)
    try:
        corpus = load_corpus(root)
        record.update(godot_version=corpus.version, source_commit=corpus.commit)
        parsed = parse_query(args.query, corpus)
        # 多取一项以识别构造重载歧义，最终仍只展示一项。
        result_limit = 2 if args.show_best else args.limit
        results = search_corpus(
            corpus,
            parsed,
            args.mode,
            result_limit,
            args.context,
            max_chars,
        )
    except CorpusError as error:
        return fail(str(error))

    warnings: List[str] = []
    if args.show_best:
        if (
            len(results) > 1
            and results[0].kind == results[1].kind == "constructor"
            and results[0].document == results[1].document
        ):
            warnings.append(
                "存在多个匹配的构造重载；当前结果仅为排序首项，尚未按参数类型消歧。"
                "请移除 --show-best 查看候选，并按来源路径核实适用签名。"
            )
        results = results[:1]

    record.update(
        warnings=warnings,
        results=[{
            "path": result.document.relative_path,
            "line": result.line,
            "kind": result.kind,
            "score": result.score,
            "truncated": result.truncated,
        } for result in results],
        result_count=len(results),
    )
    if args.json:
        render_json(corpus, parsed, args.mode, results, warnings)
    else:
        render_text(corpus, parsed, args.mode, results, args.show_best, warnings)
    return 0 if results else 1


def append_usage_log(path: Path, docs_root: Path, record: Dict[str, Any]) -> None:
    """日志失败仅报告到 stderr，不改变检索结果；禁止写入语料和 references。"""
    try:
        destination = path.expanduser().resolve()
        corpus_root = docs_root.expanduser().resolve()
        if (
            destination.suffix != ".jsonl"
            or "references" in destination.parts
            or destination == corpus_root
            or corpus_root in destination.parents
        ):
            raise ValueError("日志必须是语料目录和 references 之外的 .jsonl 文件")
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        # 单次追加写入，避免多个 Agent 在正常本地文件系统上交错写入一条记录。
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            if os.write(descriptor, payload) != len(payload):
                raise OSError("日志记录未完整写入")
        finally:
            os.close(descriptor)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"日志写入失败：{error}", file=sys.stderr)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    configured_path = args.log_file or os.environ.get("GODOT_DOCS_LOG_FILE")
    log_path = Path(configured_path) if configured_path and not args.no_log else None
    started = time.perf_counter()
    record: Dict[str, Any] = {}
    exit_code = run_search(args, record)
    if log_path is not None:
        record.update(
            schema_version=1,
            script_version=SCRIPT_VERSION,
            timestamp=datetime.now(timezone.utc).isoformat(),
            query=args.query[:2000],
            query_truncated=len(args.query) > 2000,
            requested_version=args.version,
            mode=args.mode,
            limit=args.limit,
            context=args.context,
            max_chars=args.max_chars if args.max_chars is not None else (6000 if args.show_best else 800),
            show_best=args.show_best,
            output_format="json" if args.json else "text",
            exit_code=exit_code,
            status={0: "ok", 1: "no_matches", 2: "error"}[exit_code],
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
        )
        task_id = os.environ.get("GODOT_DOCS_TASK_ID")
        if task_id:
            record["task_id"] = task_id[:200]
        root = args.docs_root if args.docs_root else default_docs_root(args.version)
        append_usage_log(log_path, root, record)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
