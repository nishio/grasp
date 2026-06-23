from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from textwrap import dedent
from typing import Any

from .cosense_cli import CosenseCliClient, sync_from_cosense
from .sqlite_store import SCHEMA_VERSION, SQLiteStore, import_export_to_sqlite


class GraspHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    pass


def grasp_home() -> Path:
    """Single global home for the store/seed. One AI owns one store, not per-cwd."""
    env_home = os.environ.get("GRASP_HOME")
    if env_home:
        return Path(env_home)
    return Path.home() / ".grasp"


def default_export_path() -> Path | None:
    env_path = os.environ.get("GRASP_EXPORT")
    if env_path:
        return Path(env_path)

    home_default = grasp_home() / "nishio.json"
    if home_default.exists():
        return home_default
    cwd_default = Path.cwd() / "raw" / "nishio.json"
    if cwd_default.exists():
        return cwd_default
    return None


def default_store_path() -> Path:
    env_path = os.environ.get("GRASP_STORE")
    if env_path:
        return Path(env_path)
    return grasp_home() / "grasp.sqlite"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grasp",
        formatter_class=GraspHelpFormatter,
        description=dedent(
            """
            Read a local Scrapbox/Cosense-style graph store.

            Mechanics SSoT: `grasp <cmd> --help` is the authoritative reference
            for command arguments, JSON return keys, text output shape, and examples.
            Global options must appear before the command.
            """
        ).strip(),
        epilog=dedent(
            """
            Global examples:
              grasp --store .grasp/grasp.sqlite stats
              grasp --json read 盲点カード --backlinks-limit 5 --related-limit 5
              grasp --export raw/nishio.json --store .grasp/grasp.sqlite import --force

            Output:
              Default output is compact text for agent reading.
              With --json, commands emit the return keys documented in each
              `grasp <cmd> --help`.
            """
        ).strip(),
    )
    parser.add_argument(
        "--export",
        type=Path,
        default=default_export_path(),
        help="Cosense JSON export path for initial/import rebuilds. Defaults to $GRASP_EXPORT, then ~/.grasp/nishio.json, then ./raw/nishio.json.",
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=default_store_path(),
        help="SQLite store path. Defaults to $GRASP_STORE or ~/.grasp/grasp.sqlite (one global store).",
    )
    parser.add_argument("--rebuild-store", action="store_true", help="Rebuild the SQLite store from --export before running.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")

    subparsers = parser.add_subparsers(dest="command", required=True, metavar="command")

    import_parser = add_command_parser(
        subparsers,
        "import",
        help="Import a Cosense JSON export into the SQLite store.",
        description="Build or replace the SQLite graph store from --export.",
        returns=(
            "store, schema_version, current_schema_version, schema_ok, "
            "source_export, imported_at, pages, lines, edges, unresolved_targets"
        ),
        examples=[
            "grasp import --force",
            "grasp --export raw/nishio.json --store .grasp/grasp.sqlite import --force",
        ],
        notes=[
            "Uses global --export and --store. Put global options before `import`.",
            "Without --force, refuses to replace an existing store.",
        ],
    )
    import_parser.add_argument("--force", action="store_true", help="Replace an existing store.")

    add_command_parser(
        subparsers,
        "stats",
        help="Show SQLite store stats and schema status.",
        description="Inspect the configured SQLite store without requiring schema compatibility.",
        returns=(
            "store, schema_version, current_schema_version, schema_ok, "
            "source_export, imported_at, pages, lines, edges, unresolved_targets"
        ),
        examples=[
            "grasp stats",
            "grasp --json stats",
            "grasp --store /tmp/grasp.sqlite stats",
        ],
        notes=["For old stores, unresolved_targets may be null and schema_ok will be false."],
    )

    read_parser = add_command_parser(
        subparsers,
        "read",
        help="Read a page with backlinks, related pages, and unresolved outgoing targets.",
        description=(
            "Open an existing page or missing linked target. Existing pages include "
            "page lines, line-level backlinks, related pages, and page-local "
            "unresolved targets. Missing targets include incoming link stats, "
            "backlinks, and related source pages."
        ),
        returns=(
            "query, page|null, link_stats, lines, lines_truncated, backlinks, "
            "backlink_count_returned, backlink_count_total, related, unresolved_targets"
        ),
        examples=[
            "grasp read 盲点カード",
            "grasp read 盲点カード --line-limit 20 --backlinks-limit 5 --related-limit 5 --unresolved-limit 5",
            "grasp --json read 民主主義 --backlinks-limit 3 --related-limit 5",
        ],
        notes=[
            "For missing targets, related[] contains source pages with relation=backlink-source.",
            "unresolved_targets[] is populated only for existing pages.",
        ],
    )
    read_parser.add_argument("title", help="Page title or missing linked target to open.")
    read_parser.add_argument("--line-limit", type=int, default=None, help="Maximum page lines to return; omit for all lines.")
    read_parser.add_argument("--backlinks-limit", type=int, default=20, help="Maximum backlink lines to return.")
    read_parser.add_argument("--related-limit", type=int, default=20, help="Maximum related pages/source pages to return.")
    read_parser.add_argument("--unresolved-limit", type=int, default=20, help="Maximum page-local unresolved targets to return.")

    backlinks_parser = add_command_parser(
        subparsers,
        "backlinks",
        help="List line-level backlinks to a page or missing target.",
        description="Return source lines whose parsed links point at title.",
        returns="query, backlinks[], count_returned, offset",
        examples=[
            "grasp backlinks 盲点 --limit 5",
            "grasp backlinks 民主主義 --limit 20 --offset 20",
            "grasp --json backlinks 盲点 --limit 2",
        ],
        notes=[
            "backlinks[] items: source_page_id, source_title, source_views, "
            "source_updated, line_id, line_index, line_text, target_title."
        ],
    )
    backlinks_parser.add_argument("title", help="Target page title or missing linked target.")
    backlinks_parser.add_argument("--limit", type=int, default=50, help="Maximum backlink lines to return.")
    backlinks_parser.add_argument("--offset", type=int, default=0, help="Number of ranked backlink lines to skip.")

    related_parser = add_command_parser(
        subparsers,
        "related",
        help="List 2-hop pages, or source pages for a missing linked target.",
        description=(
            "For an existing page, return deterministic 2-hop related pages. "
            "For a missing linked target, return source pages that link to it."
        ),
        returns="query, related[]",
        examples=[
            "grasp related 盲点カード --limit 10",
            "grasp related 民主主義 --limit 5",
            "grasp --json related 民主主義 --limit 5",
        ],
        notes=[
            "Existing-page related[] items include score and via[].",
            "Missing-target related[] items include relation=backlink-source and score=link count from that page.",
        ],
    )
    related_parser.add_argument("title", help="Existing page title or missing linked target.")
    related_parser.add_argument("--limit", type=int, default=50, help="Maximum related items to return.")

    link_stats_parser = add_command_parser(
        subparsers,
        "link-stats",
        help="Show incoming link count for an existing or missing target.",
        description="Classify a title as existing/missing and report incoming link multiplicity.",
        returns=(
            "query, title, normalized_title, page_exists, page|null, "
            "link_count, source_page_count, link_multiplicity"
        ),
        examples=[
            "grasp link-stats 盲点カード",
            "grasp link-stats 民主主義",
            "grasp --json link-stats 民主主義",
        ],
        notes=["link_multiplicity is one of: none, single, multi."],
    )
    link_stats_parser.add_argument("title", help="Existing page title or missing linked target.")

    peek_parser = add_command_parser(
        subparsers,
        "peek",
        help="Show page lines only.",
        description="Preview the body lines of an existing page without backlinks or related context.",
        returns="query, page|null, lines[], lines_truncated",
        examples=[
            "grasp peek 盲点カード --line-limit 12",
            "grasp --json peek 盲点カード --line-limit 3",
        ],
        notes=["For missing pages, page is null and lines[] is empty."],
    )
    peek_parser.add_argument("title", help="Existing page title to preview.")
    peek_parser.add_argument("--line-limit", type=int, default=None, help="Maximum page lines to return; omit for all lines.")

    suggest_parser = add_command_parser(
        subparsers,
        "suggest",
        help="Suggest page titles by partial text.",
        description="Search normalized page titles by substring and rank prefix matches first.",
        returns="query, suggestions[]",
        examples=[
            "grasp suggest 盲点 --limit 10",
            "grasp --json suggest scrap --limit 5",
        ],
        notes=["suggestions[] items are page summaries: id, title, created, updated, views, line_count."],
    )
    suggest_parser.add_argument("partial", help="Partial page title text.")
    suggest_parser.add_argument("--limit", type=int, default=20, help="Maximum title suggestions to return.")

    search_parser = add_command_parser(
        subparsers,
        "search",
        help="Search page body lines and return line-level hits.",
        description="Literal substring search over stored line text. Results are line-level hits.",
        returns="query, hits[], count_returned, offset",
        examples=[
            "grasp search 盲点 --limit 20",
            "grasp search \"民主主義\" --limit 10 --offset 10",
            "grasp --json search Scrapbox --limit 5",
        ],
        notes=[
            "hits[] items: source_page_id, source_title, source_views, "
            "source_updated, line_id, line_index, line_text."
        ],
    )
    search_parser.add_argument("query", help="Literal substring to find in line text.")
    search_parser.add_argument("--limit", type=int, default=50, help="Maximum line hits to return.")
    search_parser.add_argument("--offset", type=int, default=0, help="Number of ranked line hits to skip.")

    sync_parser = add_command_parser(
        subparsers,
        "sync",
        help="Incrementally sync recently updated hosted Cosense pages into the store.",
        description=(
            "Inspect hosted Cosense pages by updated time, fetch changed pages with "
            "cosense readPage, upsert them into the store, and rebuild unresolved targets."
        ),
        returns=(
            "project_url, dry_run, inspected, changed, updated, "
            "skipped_nonpersistent[], stopped_at|null, changed_pages[]"
        ),
        examples=[
            "grasp sync https://scrapbox.io/nishio/ --limit 20 --dry-run",
            "grasp sync https://scrapbox.io/nishio/ --limit 100 --batch-size 100",
            "grasp --store .grasp/grasp.sqlite sync https://scrapbox.io/nishio/ --cosense-command cosense",
        ],
        notes=[
            "Requires a working cosense CLI login unless --dry-run stops before fetches.",
            "Global --store selects the local store to update.",
        ],
    )
    sync_parser.add_argument("project_url", help="Hosted Cosense/Scrapbox project URL, e.g. https://scrapbox.io/nishio/.")
    sync_parser.add_argument("--limit", type=int, default=100, help="Maximum listPages entries to inspect.")
    sync_parser.add_argument("--batch-size", type=int, default=100, help="listPages page size.")
    sync_parser.add_argument("--cosense-command", default="cosense", help="cosense CLI binary.")
    sync_parser.add_argument("--dry-run", action="store_true", help="List changed pages without fetching/upserting them.")

    unresolved_parser = add_command_parser(
        subparsers,
        "unresolved",
        help="List ranked unresolved link targets.",
        description=(
            "List link targets that have incoming links but no page body. "
            "This is a graph-structure view, not a TODO list."
        ),
        returns="unresolved_targets[]",
        examples=[
            "grasp unresolved --limit 10",
            "grasp --json unresolved --limit 3",
        ],
        notes=[
            "unresolved_targets[] items: title, normalized_title, link_count, "
            "source_page_count, total_source_views, latest_source_updated, examples[]."
        ],
    )
    unresolved_parser.add_argument("--limit", type=int, default=50, help="Maximum unresolved targets to return.")

    return parser


def add_command_parser(
    subparsers: argparse._SubParsersAction,
    name: str,
    *,
    help: str,
    description: str,
    returns: str,
    examples: list[str],
    notes: list[str] | None = None,
) -> argparse.ArgumentParser:
    epilog_parts = [
        "Returns (--json):",
        f"  {returns}",
        "",
        "Examples:",
        *(f"  {example}" for example in examples),
    ]
    if notes:
        epilog_parts.extend(["", "Notes:", *(f"  {note}" for note in notes)])
    return subparsers.add_parser(
        name,
        help=help,
        description=description,
        epilog="\n".join(epilog_parts),
        formatter_class=GraspHelpFormatter,
    )


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
        if args.command != "stats" and not store.schema_ok():
            parser.error(
                f"store schema is {store.schema_version()}, current is {SCHEMA_VERSION}; "
                "run with --rebuild-store or `grasp import --force` to rebuild"
            )
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
    if args.command == "stats":
        return store.stats()
    if args.command == "read":
        return store.read(
            args.title,
            line_limit=args.line_limit,
            backlink_limit=args.backlinks_limit,
            related_limit=args.related_limit,
            unresolved_limit=args.unresolved_limit,
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
    if args.command == "link-stats":
        return store.link_stats(args.title)
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
    if args.command == "unresolved":
        return {
            "unresolved_targets": store.unresolved_targets(limit=args.limit),
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
    if command == "stats":
        return format_stats(result)
    if command == "read":
        return format_read(result)
    if command == "backlinks":
        return format_backlinks(result["query"], result["backlinks"], result.get("offset", 0))
    if command == "related":
        return format_related(result["query"], result["related"])
    if command == "link-stats":
        return format_link_stats(result)
    if command == "peek":
        return format_peek(result)
    if command == "suggest":
        return format_suggest(result["query"], result["suggestions"])
    if command == "search":
        return format_search(result["query"], result["hits"], result.get("offset", 0))
    if command == "unresolved":
        return format_unresolved_targets(result["unresolved_targets"])
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
        f"unresolved_targets: {result['unresolved_targets']}\n"
    )


def format_stats(result: dict[str, Any]) -> str:
    return (
        f"store: {result['store']}\n"
        f"schema: {result['schema_version']}\n"
        f"current_schema: {result['current_schema_version']}\n"
        f"schema_ok: {result['schema_ok']}\n"
        f"source_export: {result['source_export']}\n"
        f"imported_at: {result['imported_at']}\n"
        f"pages: {result['pages']}\n"
        f"lines: {result['lines']}\n"
        f"edges: {result['edges']}\n"
        f"unresolved_targets: {result['unresolved_targets']}\n"
    )


def format_read(result: dict[str, Any]) -> str:
    parts: list[str] = []
    page = result["page"]
    title = page["title"] if page else result["query"]
    parts.append(f"# {title}\n")

    if page is None:
        link_stats = result.get("link_stats", {})
        linked = link_stats.get("link_count", 0) > 0
        page_status = "linked target without page" if linked else "missing page"
        parts.append(f"page: {page_status}\n")
        parts.append(format_link_stats_summary(link_stats))
    else:
        parts.append(
            f"id: {page['id']}\nviews: {page['views']}\nlines: {page['line_count']}\n"
        )
        parts.append(format_link_stats_summary(result.get("link_stats", {})))
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

    related_heading = "Related Source Pages" if page is None else "Related 2-hop"
    parts.append(f"\n## {related_heading}\n")
    related = result["related"]
    if related:
        parts.append(format_related_items(related))
    else:
        parts.append("(none)\n")

    if page is not None:
        parts.append("\n## Unresolved Targets From This Page\n")
        unresolved_targets = result["unresolved_targets"]
        if unresolved_targets:
            parts.append(format_unresolved_targets(unresolved_targets))
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
    heading = "Related source pages" if is_source_page_related(related) else "Related 2-hop"
    parts = [f"# {heading}: {query}\n"]
    if not related:
        parts.append("(none)\n")
    else:
        parts.append(format_related_items(related))
    return "".join(parts)


def format_related_items(related: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in related:
        via = ", ".join(item["via"])
        if item.get("relation") == "backlink-source":
            parts.append(f"- {item['title']} (links {item['score']}, views {item['views']}; target {via})\n")
        else:
            parts.append(f"- {item['title']} (score {item['score']}, views {item['views']}; via {via})\n")
    return "".join(parts)


def is_source_page_related(related: list[dict[str, Any]]) -> bool:
    return bool(related) and all(item.get("relation") == "backlink-source" for item in related)


def format_link_stats(result: dict[str, Any]) -> str:
    page_status = "exists" if result["page_exists"] else "missing"
    parts = [
        f"# Link stats: {result['title']}\n",
        f"query: {result['query']}\n",
        f"normalized: {result['normalized_title']}\n",
        f"page: {page_status}\n",
        format_link_stats_summary(result),
    ]
    page = result.get("page")
    if page is not None:
        parts.append(f"id: {page['id']}\nviews: {page['views']}\nlines: {page['line_count']}\n")
    return "".join(parts)


def format_link_stats_summary(result: dict[str, Any]) -> str:
    if not result:
        return ""
    return (
        f"links_to_this: {result['link_count']} from {result['source_page_count']} pages "
        f"({result['link_multiplicity']})\n"
    )


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


def format_unresolved_targets(unresolved_targets: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    if not unresolved_targets:
        return "(none)\n"

    for item in unresolved_targets:
        parts.append(
            f"- {item['title']} (links {item['link_count']}, pages {item['source_page_count']}, views {item['total_source_views']})\n"
        )
        for example in item["examples"][:2]:
            parts.append(f"  - {example['source_title']} {example['line_id']}: {example['line_text']}\n")
    return "".join(parts)
