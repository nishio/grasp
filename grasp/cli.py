from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from .cosense_cli import CosenseCliClient, sync_from_cosense
from .sqlite_store import SQLiteStore, import_export_to_sqlite


def default_export_path() -> Path | None:
    env_path = os.environ.get("GRASP_EXPORT")
    if env_path:
        return Path(env_path)

    cwd_default = Path.cwd() / "raw" / "nishio.json"
    if cwd_default.exists():
        return cwd_default
    return None


def default_store_path() -> Path:
    env_path = os.environ.get("GRASP_STORE")
    if env_path:
        return Path(env_path)
    return Path.cwd() / ".grasp" / "grasp.sqlite"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="grasp", description="Read a local Scrapbox/Cosense-style graph store.")
    parser.add_argument(
        "--export",
        type=Path,
        default=default_export_path(),
        help="Cosense JSON export path for initial/import rebuilds. Defaults to $GRASP_EXPORT or raw/nishio.json.",
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=default_store_path(),
        help="SQLite store path. Defaults to $GRASP_STORE or .grasp/grasp.sqlite.",
    )
    parser.add_argument("--rebuild-store", action="store_true", help="Rebuild the SQLite store from --export before running.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import", help="Import a Cosense JSON export into the SQLite store.")
    import_parser.add_argument("--force", action="store_true", help="Replace an existing store.")

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

    search_parser = subparsers.add_parser("search", help="Search page body lines and return line-level hits.")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=50)
    search_parser.add_argument("--offset", type=int, default=0)

    sync_parser = subparsers.add_parser("sync", help="Incrementally sync recently updated hosted Cosense pages into the store.")
    sync_parser.add_argument("project_url")
    sync_parser.add_argument("--limit", type=int, default=100, help="Maximum listPages entries to inspect.")
    sync_parser.add_argument("--batch-size", type=int, default=100, help="listPages page size.")
    sync_parser.add_argument("--cosense-command", default="cosense", help="cosense CLI binary.")
    sync_parser.add_argument("--dry-run", action="store_true", help="List changed pages without fetching/upserting them.")

    wanted_parser = subparsers.add_parser("wanted", help="List ranked red links.")
    wanted_parser.add_argument("--limit", type=int, default=50)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "import":
        if args.export is None:
            parser.error("import requires --export or raw/nishio.json")
        if not args.export.exists():
            parser.error(f"export path does not exist: {args.export}")
        if args.store.exists() and not args.force:
            parser.error(f"store already exists: {args.store} (use import --force to replace it)")
        result = import_export_to_sqlite(args.export, args.store)
        emit_result(args, result)
        return 0

    if args.rebuild_store or not args.store.exists():
        if args.export is None:
            parser.error(f"store does not exist and no --export was found: {args.store}")
        if not args.export.exists():
            parser.error(f"export path does not exist: {args.export}")
        import_export_to_sqlite(args.export, args.store)

    store = SQLiteStore(args.store)
    try:
        result = run_command(store, args)
    finally:
        store.close()
    emit_result(args, result)
    return 0


def emit_result(args: argparse.Namespace, result: Any) -> None:
    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(format_result(args.command, result))


def run_command(store: SQLiteStore, args: argparse.Namespace) -> Any:
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
    if args.command == "search":
        hits = store.search(args.query, limit=args.limit, offset=args.offset)
        return {
            "query": args.query,
            "hits": hits,
            "count_returned": len(hits),
            "offset": args.offset,
        }
    if args.command == "wanted":
        return {
            "wanted": store.wanted(limit=args.limit),
        }
    if args.command == "sync":
        return sync_from_cosense(
            store,
            args.project_url,
            client=CosenseCliClient(args.cosense_command),
            limit=args.limit,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
    raise ValueError(f"unknown command: {args.command}")


def format_result(command: str, result: Any) -> str:
    if command == "import":
        return format_import(result)
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
    if command == "search":
        return format_search(result["query"], result["hits"], result.get("offset", 0))
    if command == "wanted":
        return format_wanted(result["wanted"])
    if command == "sync":
        return format_sync(result)
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def format_import(result: dict[str, Any]) -> str:
    return (
        f"store: {result['store']}\n"
        f"schema: {result['schema_version']}\n"
        f"pages: {result['pages']}\n"
        f"lines: {result['lines']}\n"
        f"edges: {result['edges']}\n"
        f"wanted: {result['wanted']}\n"
    )


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


def format_search(query: str, hits: list[dict[str, Any]], offset: int = 0) -> str:
    parts = [f"# Search: {query}\n", f"offset: {offset}\n"]
    if not hits:
        parts.append("(none)\n")
    else:
        for hit in hits:
            parts.append(f"- {hit['source_title']} {hit['line_id']}: {hit['line_text']}\n")
    return "".join(parts)


def format_sync(result: dict[str, Any]) -> str:
    parts = [
        f"project: {result['project_url']}\n",
        f"dry_run: {result['dry_run']}\n",
        f"inspected: {result['inspected']}\n",
        f"changed: {result['changed']}\n",
        f"updated: {result['updated']}\n",
    ]
    if result["stopped_at"]:
        stopped = result["stopped_at"]
        parts.append(f"stopped_at: {stopped['title']} ({stopped['updated']})\n")
    if result["changed_pages"]:
        parts.append("\n## Changed Pages\n")
        for page in result["changed_pages"]:
            parts.append(f"- {page['title']} ({page['updated']})\n")
    if result["skipped_nonpersistent"]:
        parts.append("\n## Skipped Nonpersistent\n")
        for page in result["skipped_nonpersistent"]:
            parts.append(f"- {page['title']} {page['url']}\n")
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
