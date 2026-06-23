from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from .cosense import CosenseStore


def default_export_path() -> Path | None:
    env_path = os.environ.get("GRASP_EXPORT")
    if env_path:
        return Path(env_path)

    cwd_default = Path.cwd() / "raw" / "nishio.json"
    if cwd_default.exists():
        return cwd_default
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="grasp", description="Read a Cosense/Scrapbox graph export from the CLI.")
    parser.add_argument(
        "--export",
        type=Path,
        default=default_export_path(),
        help="Cosense JSON export path. Defaults to $GRASP_EXPORT or raw/nishio.json in the current directory.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    read_parser = subparsers.add_parser("read", help="Read a page with backlinks, 2-hop related pages, and red links.")
    read_parser.add_argument("title")
    read_parser.add_argument("--line-limit", type=int, default=None)
    read_parser.add_argument("--backlinks-limit", type=int, default=20)
    read_parser.add_argument("--related-limit", type=int, default=20)
    read_parser.add_argument("--wanted-limit", type=int, default=20)

    backlinks_parser = subparsers.add_parser("backlinks", help="List line-level backlinks to a page or red link.")
    backlinks_parser.add_argument("title")
    backlinks_parser.add_argument("--limit", type=int, default=50)
    backlinks_parser.add_argument("--offset", type=int, default=0)

    related_parser = subparsers.add_parser("related", help="List 2-hop pages through existing graph links.")
    related_parser.add_argument("title")
    related_parser.add_argument("--limit", type=int, default=50)

    peek_parser = subparsers.add_parser("peek", help="Show page lines only.")
    peek_parser.add_argument("title")
    peek_parser.add_argument("--line-limit", type=int, default=None)

    suggest_parser = subparsers.add_parser("suggest", help="Suggest page titles by partial text.")
    suggest_parser.add_argument("partial")
    suggest_parser.add_argument("--limit", type=int, default=20)

    wanted_parser = subparsers.add_parser("wanted", help="List ranked red links.")
    wanted_parser.add_argument("--limit", type=int, default=50)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.export is None:
        parser.error("missing --export path and no raw/nishio.json default was found")
    if not args.export.exists():
        parser.error(f"export path does not exist: {args.export}")

    store = CosenseStore.from_cosense_export(args.export)
    result = run_command(store, args)

    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(format_result(args.command, result))
    return 0


def run_command(store: CosenseStore, args: argparse.Namespace) -> Any:
    if args.command == "read":
        return store.read(
            args.title,
            line_limit=args.line_limit,
            backlink_limit=args.backlinks_limit,
            related_limit=args.related_limit,
            wanted_limit=args.wanted_limit,
        )
    if args.command == "backlinks":
        edges = store.backlinks(args.title, limit=args.limit, offset=args.offset)
        return {
            "query": args.title,
            "backlinks": [edge.to_dict() for edge in edges],
            "count_returned": len(edges),
            "offset": args.offset,
        }
    if args.command == "related":
        return {
            "query": args.title,
            "related": store.related(args.title, limit=args.limit),
        }
    if args.command == "peek":
        page = store.resolve_page(args.title)
        if page is None:
            return {"query": args.title, "page": None, "lines": [], "lines_truncated": False}
        lines, truncated = store.page_lines(page, args.line_limit)
        return {
            "query": args.title,
            "page": page.to_summary(),
            "lines": [line.to_dict() for line in lines],
            "lines_truncated": truncated,
        }
    if args.command == "suggest":
        return {
            "query": args.partial,
            "suggestions": store.suggest(args.partial, limit=args.limit),
        }
    if args.command == "wanted":
        return {
            "wanted": store.wanted(limit=args.limit),
        }
    raise ValueError(f"unknown command: {args.command}")


def format_result(command: str, result: Any) -> str:
    if command == "read":
        return format_read(result)
    if command == "backlinks":
        return format_backlinks(result["query"], result["backlinks"], result.get("offset", 0))
    if command == "related":
        return format_related(result["query"], result["related"])
    if command == "peek":
        return format_peek(result)
    if command == "suggest":
        return format_suggest(result["query"], result["suggestions"])
    if command == "wanted":
        return format_wanted(result["wanted"])
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def format_read(result: dict[str, Any]) -> str:
    parts: list[str] = []
    page = result["page"]
    title = page["title"] if page else result["query"]
    parts.append(f"# {title}\n")

    if page is None:
        red_status = "red link" if result["red_link"] else "missing page"
        parts.append(f"page: {red_status}\n")
    else:
        parts.append(
            f"id: {page['id']}\nviews: {page['views']}\nlines: {page['line_count']}\n"
        )
        parts.append("\n## Lines\n")
        for line in result["lines"]:
            parts.append(f"{line['line_id']}  {line['text']}\n")
        if result["lines_truncated"]:
            parts.append("...\n")

    parts.append("\n## Backlinks\n")
    backlinks = result["backlinks"]
    if backlinks:
        parts.append(format_edge_list(backlinks))
    else:
        parts.append("(none)\n")

    parts.append("\n## Related 2-hop\n")
    related = result["related"]
    if related:
        for item in related:
            via = ", ".join(item["via"])
            parts.append(f"- {item['title']} (score {item['score']}, views {item['views']}; via {via})\n")
    else:
        parts.append("(none)\n")

    parts.append("\n## Wanted From This Page\n")
    wanted = result["wanted"]
    if wanted:
        parts.append(format_wanted(wanted))
    else:
        parts.append("(none)\n")

    return "".join(parts)


def format_backlinks(query: str, backlinks: list[dict[str, Any]], offset: int = 0) -> str:
    parts = [f"# Backlinks: {query}\n", f"offset: {offset}\n"]
    if not backlinks:
        parts.append("(none)\n")
    else:
        parts.append(format_edge_list(backlinks))
    return "".join(parts)


def format_edge_list(edges: list[dict[str, Any]]) -> str:
    parts = []
    for edge in edges:
        parts.append(f"- {edge['source_title']} {edge['line_id']}: {edge['line_text']}\n")
    return "".join(parts)


def format_related(query: str, related: list[dict[str, Any]]) -> str:
    parts = [f"# Related 2-hop: {query}\n"]
    if not related:
        parts.append("(none)\n")
    else:
        for item in related:
            via = ", ".join(item["via"])
            parts.append(f"- {item['title']} (score {item['score']}, views {item['views']}; via {via})\n")
    return "".join(parts)


def format_peek(result: dict[str, Any]) -> str:
    page = result["page"]
    if page is None:
        return f"# {result['query']}\npage: missing\n"

    parts = [f"# {page['title']}\n", f"id: {page['id']}\nviews: {page['views']}\nlines: {page['line_count']}\n\n"]
    for line in result["lines"]:
        parts.append(f"{line['line_id']}  {line['text']}\n")
    if result["lines_truncated"]:
        parts.append("...\n")
    return "".join(parts)


def format_suggest(query: str, suggestions: list[dict[str, Any]]) -> str:
    parts = [f"# Suggestions: {query}\n"]
    if not suggestions:
        parts.append("(none)\n")
    else:
        for page in suggestions:
            parts.append(f"- {page['title']} (views {page['views']}, lines {page['line_count']})\n")
    return "".join(parts)


def format_wanted(wanted: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    if not wanted:
        return "(none)\n"

    for item in wanted:
        parts.append(
            f"- {item['title']} (count {item['count']}, pages {item['source_page_count']}, views {item['total_source_views']})\n"
        )
        for example in item["examples"][:2]:
            parts.append(f"  - {example['source_title']} {example['line_id']}: {example['line_text']}\n")
    return "".join(parts)
