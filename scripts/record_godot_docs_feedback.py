#!/usr/bin/env python3
"""追加 Agent 对检索帮助程度的简短评价，不读取文档或修改语料。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from typing import Optional, Sequence

from search_godot_docs import append_usage_log, default_docs_root, validate_version


SCRIPT_VERSION = "1.1.0"


def short_text(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 400:
        raise argparse.ArgumentTypeError("内容必须为 1～400 个字符")
    return value


def query_text(value: str) -> str:
    if not value.strip() or len(value) > 2000:
        raise argparse.ArgumentTypeError("查询必须为 1～2000 个字符")
    return value


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="记录可选的 Agent 检索评价；默认关闭，不读取语料。")
    parser.add_argument("--query", action="append", type=query_text, required=True,
                        help="实际使用的查询，可重复指定，最多 10 项")
    parser.add_argument("--outcome", default="uncertain",
                        choices=("helpful", "partial", "unhelpful", "uncertain"),
                        help="可选的帮助程度：有帮助、部分有帮助、无帮助或尚无法判断（默认：uncertain）")
    parser.add_argument("--reason", type=short_text, required=True,
                        help="简短中文理由，说明证据如何帮助任务或具体缺口，最多 400 字符")
    parser.add_argument("--source", action="append", type=short_text, default=[],
                        help="实际参考或遇到问题的结果 path:line，最多 10 项，不校验文件内容")
    parser.add_argument("--follow-up", type=short_text,
                        help="实际采取的补读、改写查询或其他解决办法，最多 400 字符")
    parser.add_argument("--version", type=validate_version, required=True,
                        help="本次评价对应的文档版本，不同版本分别记录")
    parser.add_argument("--docs-root", type=Path,
                        help="使用自定义语料时指定其根目录，仅用于阻止日志写入该目录")
    parser.add_argument("--task-id", type=short_text,
                        help="与检索日志相同的任务标识，默认读取 GODOT_DOCS_TASK_ID")
    logging = parser.add_mutually_exclusive_group()
    logging.add_argument("--log-file", type=Path,
                         help="反馈 JSONL 路径，默认读取 GODOT_DOCS_FEEDBACK_FILE，未配置则不写入")
    logging.add_argument("--no-log", action="store_true", help="禁用本次记录，覆盖环境配置")
    args = parser.parse_args(argv)
    if len(args.query) > 10 or len(args.source) > 10:
        parser.error("query 和 source 均最多允许 10 项")
    configured_path = args.log_file or os.environ.get("GODOT_DOCS_FEEDBACK_FILE")
    if args.no_log or not configured_path:
        print("反馈记录未启用，已跳过。", file=sys.stderr)
        return 0

    record = {
        "schema_version": 1,
        "script_version": SCRIPT_VERSION,
        "event_type": "feedback",
        "author": "agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "godot_version": args.version,
        "queries": args.query,
        "outcome": args.outcome,
        "reason": args.reason,
        "sources": args.source,
    }
    task_id = args.task_id or os.environ.get("GODOT_DOCS_TASK_ID")
    if task_id:
        record["task_id"] = task_id[:200]
    if args.follow_up:
        record["follow_up"] = args.follow_up
    root = args.docs_root if args.docs_root else default_docs_root(args.version)
    append_usage_log(Path(configured_path), root, record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
