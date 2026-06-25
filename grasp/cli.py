from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import sys
from textwrap import dedent
from typing import Any

from .cosense_cli import CosenseCliClient, acquire_from_cosense, sync_from_cosense
from .forest import import_forest_from_registry
from .markdown import MarkdownCollisionError
from .sqlite_store import (
    SCHEMA_VERSION,
    SQLiteStore,
    ensure_store_schema,
    import_export_to_sqlite,
    import_markdown_folder_to_sqlite,
    recover_store_from_import_cache,
)


class GraspHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    pass


def grasp_home() -> Path:
    """Single global home for the store. One AI owns one store, not per-cwd."""
    env_home = os.environ.get("GRASP_HOME")
    if env_home:
        return Path(env_home)
    return Path.home() / ".grasp"


def default_store_path() -> Path:
    env_path = os.environ.get("GRASP_STORE")
    if env_path:
        return Path(env_path)
    return grasp_home() / "grasp.sqlite"


def default_project() -> str | None:
    return os.environ.get("GRASP_PROJECT")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grasp",
        formatter_class=GraspHelpFormatter,
        description=dedent(
            """
            Read a local Scrapbox/Cosense-style graph store.

            Mechanics SSoT: `grasp <cmd> --help` is the authoritative reference
            for command arguments, JSON return keys, text output shape, and examples.
            Global options normally appear before the command; --json is also
            accepted after a command for recovery from common agent mistakes.
            Text output uses compact local line-id aliases by default; use
            --full-ids for stable full line ids.
            """
        ).strip(),
        epilog=dedent(
            """
            Global examples:
              grasp stats
              grasp read 盲点カード --json --backlinks-limit 5 --related-limit 5
              grasp import --cosense raw/nishio.json
              grasp import --markdown wiki --project grasp-wiki
              grasp import-forest /Users/nishio/llm-wiki/wikis.yaml --markdown-exclude-dir raw
              grasp --project nishio:search acquire https://scrapbox.io/nishio/ --search "[nishio.icon]" --limit 20

            Output:
              Default output is compact text for agent reading.
              Text line ids are shortened to local aliases such as P1:12.
              With --json, commands emit the return keys documented in each
              `grasp <cmd> --help`.
            """
        ).strip(),
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=default_store_path(),
        help="SQLite store path. Defaults to $GRASP_STORE or ~/.grasp/grasp.sqlite (one global store).",
    )
    parser.add_argument(
        "--project",
        default=default_project(),
        help="Project namespace to read/update. Defaults to $GRASP_PROJECT, or the only project in the store.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--full-ids", action="store_true", help="In text output, show full stable line ids instead of local aliases.")

    subparsers = parser.add_subparsers(dest="command", required=True, metavar="command")

    import_parser = add_command_parser(
        subparsers,
        "import",
        help="Import a Cosense JSON export or Markdown folder into the SQLite store.",
        description="Build or replace one SQLite graph project from a Cosense JSON export or read-only Markdown folder mirror.",
        returns=(
            "store, project, project_count, projects[], schema_version, current_schema_version, schema_ok, "
            "source_export, imported_at, pages, lines, edges, unresolved_targets, markdown_import|null"
        ),
        examples=[
            "grasp import --cosense raw/nishio.json",
            "grasp import --markdown wiki --project grasp-wiki",
            "grasp --store /tmp/grasp-task.sqlite import --cosense raw/nishio.json",
        ],
        notes=[
            "Uses --cosense for a Cosense JSON export file, or --markdown for a read-only Markdown folder mirror.",
            "Import replaces only the selected project namespace. Other projects in the same store are preserved.",
            "Project name defaults to the export's name field or folder name. Use --project to override.",
            "Markdown mirror uses frontmatter title/id/aliases/tags when present, falls back to first H1 then file stem, and parses [[wikilinks]] plus #tags as internal edges.",
            "Use --markdown-exclude-dir to skip heavy raw/generated directories. source/ is kept as source-backed digest content.",
            "Markdown re-import uses a manifest: content-only file changes update incrementally; title/alias/id/graph-role/exclude-dir/file-set changes trigger a safe full rebuild.",
            "A cached copy of each imported Cosense JSON is kept beside the store for automatic schema recovery.",
        ],
    )
    import_parser.add_argument(
        "--project",
        dest="import_project",
        default=None,
        help="Project namespace to store this source under. Defaults to the export name or folder name.",
    )
    import_source = import_parser.add_mutually_exclusive_group(required=True)
    import_source.add_argument(
        "--cosense",
        dest="cosense_export",
        type=Path,
        help="Cosense JSON export path to import.",
    )
    import_source.add_argument(
        "--markdown",
        dest="markdown_folder",
        type=Path,
        help="Markdown folder to index as a read-only mirror.",
    )
    import_parser.add_argument(
        "--markdown-exclude-dir",
        action="append",
        default=[],
        metavar="NAME",
        help="Directory basename to skip when importing a Markdown mirror. Repeat for multiple names, e.g. --markdown-exclude-dir raw.",
    )

    import_forest_parser = add_command_parser(
        subparsers,
        "import-forest",
        help="Import a wikis.yaml registry of Markdown wiki folders into one store.",
        description=(
            "Read a wiki-forest registry and import each entry's Markdown wiki folder as a separate project. "
            "Per-entry failures are collected as diagnostics instead of stopping the whole forest."
        ),
        returns=(
            "registry, store, wiki_dir, markdown_exclude_dirs, entry_count, success_count, failure_count, "
            "missing_count, skipped_count, aggregate, projects[], ambiguities|null, wall_seconds"
        ),
        examples=[
            "grasp import-forest /Users/nishio/llm-wiki/wikis.yaml --markdown-exclude-dir raw",
            "grasp --store /tmp/grasp-forest.sqlite --json import-forest /Users/nishio/llm-wiki/wikis.yaml --markdown-exclude-dir raw",
        ],
        notes=[
            "Registry entries are expected under top-level wikis: with name and path fields.",
            "Each entry imports <path>/<wiki-dir> as project <name>. Default --wiki-dir is wiki.",
            "Registry names must be unique because project name is the local namespace.",
            "Other projects already in the store are preserved.",
            "The result includes an ambiguities summary so duplicate handles can be reviewed immediately after import.",
        ],
    )
    import_forest_parser.add_argument("registry", type=Path, help="Path to wikis.yaml registry.")
    import_forest_parser.add_argument("--wiki-dir", default="wiki", help="Directory name under each registry path to import. Use '.' when the path itself is the wiki.")
    import_forest_parser.add_argument(
        "--markdown-exclude-dir",
        action="append",
        default=[],
        metavar="NAME",
        help="Directory basename to skip when importing each Markdown mirror. Repeat for multiple names.",
    )
    import_forest_parser.add_argument("--ambiguity-limit", type=int, default=50, help="Maximum ambiguous handles to include in the post-import summary.")
    import_forest_parser.add_argument("--ambiguity-candidate-limit", type=int, default=5, help="Maximum candidate pages per ambiguous handle in the post-import summary.")

    add_command_parser(
        subparsers,
        "stats",
        help="Show SQLite store stats and schema status.",
        description="Inspect the configured SQLite store without requiring schema compatibility.",
        returns=(
            "store, project, project_count, projects[], schema_version, current_schema_version, schema_ok, "
            "source_export, imported_at, pages, lines, edges, unresolved_targets"
        ),
        examples=[
            "grasp stats",
            "grasp --json stats",
            "grasp --store /tmp/grasp.sqlite stats",
        ],
        notes=[
            "If --project is omitted and the store contains one project, stats shows that project.",
            "If --project is omitted and the store contains multiple projects, stats shows aggregate counts and projects[].",
            "For old stores, unresolved_targets may be null and schema_ok will be false.",
        ],
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
            "line_window|null, backlink_count_returned, backlink_count_total, related, "
            "unresolved_targets, recovery_hints|null, ambiguity|null; with --around-line, lines[] is the bounded "
            "window around that line; with --related-snippets, related[] items also include "
            "snippet_lines[], snippet_truncated, and snippet_mode"
        ),
        examples=[
            "grasp read 盲点カード",
            "grasp read 盲点カード --line-limit 20 --backlinks-limit 5 --related-limit 5 --unresolved-limit 5",
            "grasp read --around-line 5928725cba093700118fa5b2:12 --line-context 4",
            "grasp read 盲点カード --related-snippets --related-snippet-lines 5",
            "grasp read 盲点カード --related-snippets --related-snippet-mode edge",
            "grasp read --page-id 5928725cba093700118fa5b2",
            "grasp read --path source/Digest.md",
            "grasp --json read 民主主義 --backlinks-limit 3 --related-limit 5",
        ],
        notes=[
            "For missing targets, related[] contains source pages with relation=backlink-source.",
            "unresolved_targets[] is populated only for existing pages.",
            "--around-line accepts a full line_id from JSON or --full-ids text output. Local aliases like P1:12 are per-output only.",
            "--page-id and --path select a page identity directly when a visible handle is ambiguous.",
            "--related-snippets includes the first N lines of each related/source page, matching the Cosense related-pane reading pattern.",
            "--related-snippet-mode edge centers snippets on the link line that explains each related/source item.",
        ],
    )
    read_parser.add_argument("title", nargs="?", help="Page title or missing linked target to open. Optional when --around-line is set.")
    read_parser.add_argument("--around-line", default=None, help="Open the page containing this full line_id and return a bounded line window around it.")
    read_parser.add_argument("--page-id", default=None, help="Open a materialized page by stable page id instead of visible title/alias.")
    read_parser.add_argument("--path", dest="source_path", default=None, help="Open a Markdown mirror page by source path relative to the imported folder.")
    read_parser.add_argument("--line-context", type=int, default=5, help="Number of lines before and after --around-line to return.")
    read_parser.add_argument("--line-limit", type=int, default=None, help="Maximum page lines to return; omit for all lines.")
    read_parser.add_argument("--backlinks-limit", type=int, default=20, help="Maximum backlink lines to return.")
    read_parser.add_argument("--related-limit", type=int, default=20, help="Maximum related pages/source pages to return.")
    read_parser.add_argument("--unresolved-limit", type=int, default=20, help="Maximum page-local unresolved targets to return.")
    read_parser.add_argument("--related-snippets", action="store_true", help="Include leading page lines for each related/source page.")
    read_parser.add_argument("--related-snippet-lines", type=int, default=5, help="Number of leading lines per related/source page when --related-snippets is set.")
    read_parser.add_argument("--related-snippet-mode", choices=["lead", "edge"], default="lead", help="How to choose related/source snippets.")

    backlinks_parser = add_command_parser(
        subparsers,
        "backlinks",
        help="List line-level backlinks to a page, missing target, or ambiguous handle.",
        description="Return source lines whose parsed links point at title.",
        returns="query, resolution_status, ambiguity|null, backlinks[], count_returned, count_total, offset",
        examples=[
            "grasp backlinks 盲点 --limit 5",
            "grasp backlinks 民主主義 --limit 20 --offset 20",
            "grasp --json backlinks 盲点 --limit 2",
        ],
        notes=[
            "backlinks[] items: source_page_id, source_title, source_views, "
            "source_updated, line_id, line_index, line_text, target_title. "
            "For ambiguous handles, backlinks[] are incoming lines to the handle; "
            "candidate_backlinks[] contains resolved backlinks to each candidate page."
        ],
    )
    backlinks_parser.add_argument("title", help="Target page title or missing linked target.")
    backlinks_parser.add_argument("--limit", type=int, default=50, help="Maximum backlink lines to return.")
    backlinks_parser.add_argument("--offset", type=int, default=0, help="Number of ranked backlink lines to skip.")

    ambiguities_parser = add_command_parser(
        subparsers,
        "ambiguities",
        help="List ambiguous visible handles across the selected scope.",
        description=(
            "Report duplicate page handles where one visible title/alias/file stem maps to multiple page identities. "
            "Without --project, this command scans all projects in the store."
        ),
        returns=(
            "scope, project|null, project_count, projects[], handle_count, handles_returned, "
            "limit, offset, candidate_limit, ambiguities[]"
        ),
        examples=[
            "grasp ambiguities --limit 20",
            "grasp --project notes ambiguities --limit 20 --candidate-limit 3",
            "grasp --json ambiguities --limit 5",
        ],
        notes=[
            "ambiguities[] items include project, handle, handle_norm, candidate_count, candidates[], "
            "ambiguous_link_count, ambiguous_source_page_count, and graph_role_counts.",
            "ambiguous_link_count counts incoming links whose target handle is ambiguous; candidates[] is bounded by --candidate-limit.",
        ],
    )
    ambiguities_parser.add_argument("--limit", type=int, default=50, help="Maximum ambiguous handles to return.")
    ambiguities_parser.add_argument("--offset", type=int, default=0, help="Number of ranked ambiguous handles to skip.")
    ambiguities_parser.add_argument("--candidate-limit", type=int, default=5, help="Maximum candidate pages to include per ambiguous handle.")

    cross_project_spread_parser = add_command_parser(
        subparsers,
        "cross-project-spread",
        help="Report where a normalized handle appears across project namespaces.",
        description=(
            "Scan the selected scope for a title/handle as materialized page handles, unresolved targets, "
            "and incoming link handles. This is a weak normalized-title spread signal; page identities are not merged."
        ),
        returns=(
            "query, handle_norm, scope, project|null, project_count, signal_project_count, projects_returned, "
            "connection_strength, totals, top_source_projects[], projects[]"
        ),
        examples=[
            "grasp cross-project-spread KJ法 --limit 20",
            "grasp cross-project-spread README --candidate-limit 3",
            "grasp --json cross-project-spread KJ法 --limit 10",
        ],
        notes=[
            "Without --project, scans all projects in the store; with --project, scans only that namespace.",
            "projects[] items include materialized candidate pages, unresolved target stats, and incoming link resolution counts.",
            "connection_strength=weak-normalized-title means the command reports a retrieval hint, not an authored merge.",
        ],
    )
    cross_project_spread_parser.add_argument("title", help="Title or visible link handle to scan across projects.")
    cross_project_spread_parser.add_argument("--limit", type=int, default=50, help="Maximum project rows to return.")
    cross_project_spread_parser.add_argument("--offset", type=int, default=0, help="Number of ranked project rows to skip.")
    cross_project_spread_parser.add_argument("--candidate-limit", type=int, default=5, help="Maximum materialized candidate pages per project.")

    cross_project_spreads_parser = add_command_parser(
        subparsers,
        "cross-project-spreads",
        help="Rank normalized handles by weak cross-project spread.",
        description=(
            "List title/handle norms that appear across multiple project namespaces as materialized page handles, "
            "unresolved targets, or incoming link handles. This is a discovery surface for weak normalized-title signals."
        ),
        returns=(
            "scope, project|null, project_count, total_handle_count, handle_count, handles_returned, "
            "connection_strength, rank_basis, spreads[]"
        ),
        examples=[
            "grasp cross-project-spreads --limit 20",
            "grasp cross-project-spreads --min-projects 3 --project-limit 5",
            "grasp --json cross-project-spreads --limit 10",
        ],
        notes=[
            "spreads[] items include title, handle_norm, project_spread, materialized/unresolved/incoming counts, rank_band, and project_samples[].",
            "Concept-like handles rank before structural-name, numeric-only, and artifact-only handles; lower bands are still reported when they enter the bounded result set.",
            "Use cross-project-spread <title> to inspect one returned handle in detail.",
        ],
    )
    cross_project_spreads_parser.add_argument("--limit", type=int, default=50, help="Maximum handle rows to return.")
    cross_project_spreads_parser.add_argument("--offset", type=int, default=0, help="Number of ranked handle rows to skip.")
    cross_project_spreads_parser.add_argument("--min-projects", type=int, default=2, help="Minimum project_spread required for a handle.")
    cross_project_spreads_parser.add_argument("--project-limit", type=int, default=3, help="Maximum project samples to include per handle.")
    cross_project_spreads_parser.add_argument("--candidate-limit", type=int, default=1, help="Maximum materialized candidate pages per sampled project.")

    related_parser = add_command_parser(
        subparsers,
        "related",
        help="List 2-hop pages, source pages for a missing target, or source pages for an ambiguous handle.",
        description=(
            "For an existing page, return deterministic 2-hop related pages. "
            "For a missing linked target, return source pages that link to it. "
            "For an ambiguous handle, return source pages that link to the handle and candidate page related sets."
        ),
        returns="query, resolution_status, ambiguity|null, related[], candidate_related[], recovery_hints|null",
        examples=[
            "grasp related 盲点カード --limit 10",
            "grasp related 民主主義 --limit 5",
            "grasp --json related 民主主義 --limit 5",
        ],
        notes=[
            "Existing-page related[] items include score and via[].",
            "Missing-target related[] items include relation=backlink-source and score=link count from that page.",
            "Ambiguous-handle related[] items are incoming source pages for the handle; candidate_related[] keeps each candidate page separate.",
            "If related[] is empty, recovery_hints gives title/search/unresolved suggestions.",
        ],
    )
    related_parser.add_argument("title", help="Existing page title or missing linked target.")
    related_parser.add_argument("--limit", type=int, default=50, help="Maximum related items to return.")

    path_parser = add_command_parser(
        subparsers,
        "path",
        help="Find a short undirected graph path between two pages or unresolved targets.",
        description=(
            "Find shortest paths in the local graph using pages and unresolved targets as nodes. "
            "Materialized internal links are treated as undirected edges, so the result explains "
            "how two concepts are connected through links or co-citation hinges."
        ),
        returns=(
            "query, source|null, target|null, max_depth, paths[], path_count, truncated, recovery_hints|null; "
            "paths[] items include distance, nodes[], and edge example lines"
        ),
        examples=[
            "grasp path KJ法 弱い紐帯 --max-depth 4",
            "grasp path KJ法 民主主義 --max-depth 4 --limit 1",
            "grasp --json path KJ法 弱い紐帯 --max-depth 4 --limit 3",
        ],
        notes=[
            "Nodes are pages plus unresolved targets. This is intentionally broader than page-only traversal.",
            "The search is bounded by --max-depth; use small depths first because dense hubs can expand quickly.",
            "Edges include example source lines so the bridge can be checked against source context.",
            "If both endpoints resolve but no path is found, recovery_hints.path includes next-depth, related, backlinks, and link stats cues.",
        ],
    )
    path_parser.add_argument("source", help="Start page title or unresolved target.")
    path_parser.add_argument("target", help="End page title or unresolved target.")
    path_parser.add_argument("--max-depth", type=int, default=4, help="Maximum hop count to search.")
    path_parser.add_argument("--limit", type=int, default=3, help="Maximum shortest paths to return.")

    link_stats_parser = add_command_parser(
        subparsers,
        "link-stats",
        help="Show incoming link count for an existing or missing target.",
        description="Classify a title as existing/missing and report incoming link multiplicity.",
        returns=(
            "query, title, normalized_title, page_exists, page|null, "
            "link_count, source_page_count, link_multiplicity, recovery_hints|null"
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
        returns="query, page|null, line_offset, lines[], lines_truncated, lines_truncated_before, lines_truncated_after",
        examples=[
            "grasp peek 盲点カード --line-limit 12",
            "grasp peek 盲点カード --line-offset 120 --line-limit 20",
            "grasp --json peek 盲点カード --line-limit 3",
        ],
        notes=[
            "For missing pages, page is null and lines[] is empty.",
            "lines_truncated is kept for compatibility and has the same value as lines_truncated_after.",
        ],
    )
    peek_parser.add_argument("title", help="Existing page title to preview.")
    peek_parser.add_argument("--line-limit", type=int, default=None, help="Maximum page lines to return; omit for all lines.")
    peek_parser.add_argument("--line-offset", type=int, default=0, help="Number of page lines to skip before returning lines.")

    suggest_parser = add_command_parser(
        subparsers,
        "suggest",
        help="Suggest page titles by fuzzy or partial text.",
        description=(
            "Search normalized page titles. The default fuzzy mode keeps exact/substring matches first, "
            "then also matches separated terms and compact character-subsequence queries for long sentence titles."
        ),
        returns="query, mode, suggestions[]",
        examples=[
            "grasp suggest 盲点 --limit 10",
            "grasp suggest '書字 副産物' --limit 10",
            "grasp suggest '再会書字委譲' --limit 10",
            "grasp --json suggest scrap --limit 5",
        ],
        notes=[
            "suggestions[] items are page summaries plus match_mode, match_score, and matched_terms.",
            "--mode substring restores strict normalized substring matching.",
            "Fuzzy mode is lexical and asearch-style; semantic embedding search is a later retrieval layer.",
        ],
    )
    suggest_parser.add_argument("partial", help="Partial page title text.")
    suggest_parser.add_argument("--limit", type=int, default=20, help="Maximum title suggestions to return.")
    suggest_parser.add_argument("--mode", choices=["fuzzy", "substring"], default="fuzzy", help="Title suggestion mode.")

    search_parser = add_command_parser(
        subparsers,
        "search",
        help="Search page body lines and return line-level hits.",
        description=(
            "Search stored line text. By default, the query is a literal line substring, "
            "including spaces. Use --mode boolean for AND/OR/NOT expressions, and --scope "
            "line or page to choose where the expression must hold. If literal search "
            "returns no hits, search retries with normalized fallback matching."
        ),
        returns="query, mode, scope, context, hits[], count_returned, offset, recovery_hints|null",
        examples=[
            "grasp search 盲点 --limit 20",
            "grasp search \"weak ties\" --limit 20",
            "grasp search KJ法 --context 2 --limit 10",
            "grasp search \"KJ法 AND 表札\" --mode boolean --scope page --limit 20",
            "grasp search \"(KJ法 OR 発想法) AND NOT 古い\" --mode boolean --scope line",
            "grasp search \"民主主義\" --limit 10 --offset 10",
            "grasp --json search Scrapbox --limit 5",
        ],
        notes=[
            "hits[] items: source_page_id, source_title, source_views, "
            "source_updated, line_id, line_index, line_text, match_mode, match_terms.",
            "With --context N, each hit also includes context_lines[] and context_window.",
            "Default mode is literal: spaces are part of the searched string.",
            "Boolean mode supports AND, OR, NOT, parentheses, quoted phrases, and implicit AND between adjacent terms.",
            "--scope line evaluates the expression per line. --scope page evaluates it across all lines in a page, then returns matching lines from those pages.",
            "match_mode is literal for direct substring hits and normalized for loose fallback matches. Normalized fallback applies to literal mode.",
        ],
    )
    search_parser.add_argument("query", help="Literal substring, or a boolean expression when --mode boolean is set.")
    search_parser.add_argument("--mode", choices=["literal", "boolean"], default="literal", help="Query interpretation mode.")
    search_parser.add_argument("--scope", choices=["line", "page"], default="line", help="Where the query must match.")
    search_parser.add_argument("--limit", type=int, default=50, help="Maximum line hits to return.")
    search_parser.add_argument("--offset", type=int, default=0, help="Number of ranked line hits to skip.")
    search_parser.add_argument("--context", type=int, default=0, help="Number of lines before and after each hit to include.")

    mentions_parser = add_command_parser(
        subparsers,
        "mentions",
        help="Find bare literal mentions outside parsed internal-link spans.",
        description=(
            "Audit literal mentions of a query and classify them by whether the source page "
            "already has an exact link, a query-containing link target, or no link handle. "
            "By default only lines with bare occurrences are returned."
        ),
        returns="query, mode, context, summary, mentions[]",
        examples=[
            "grasp mentions KJ法 --limit 20",
            "grasp mentions KJ法 --unlinked --limit 20",
            "grasp mentions KJ法 --include-linked --limit 20",
            "grasp mentions KJ法 --context 2 --limit 10",
            "grasp --json mentions KJ法 --limit 5",
        ],
        notes=[
            "mentions[] items include line fields plus occurrence counts, classification, page link status, query_link_targets[], and line_link_targets[].",
            "summary counts all literal line hits before limit/offset; returned lines are bounded by --limit.",
            "This is a link-gap and come-from audit primitive, not a bulk-link instruction.",
        ],
    )
    mentions_parser.add_argument("query", help="Literal text to find.")
    mentions_parser.add_argument("--limit", type=int, default=50, help="Maximum mention lines to return.")
    mentions_parser.add_argument("--offset", type=int, default=0, help="Number of ranked mention lines to skip.")
    mentions_parser.add_argument("--include-linked", action="store_true", help="Also return lines where every occurrence is inside a parsed internal link span.")
    mentions_parser.add_argument("--unlinked", action="store_true", help="Only return bare mention lines from pages with no query-containing link target.")
    mentions_parser.add_argument("--context", type=int, default=0, help="Number of lines before and after each returned mention to include.")

    co_links_parser = add_command_parser(
        subparsers,
        "co-links",
        help="Rank internal links that co-occur on lines containing a query.",
        description=(
            "For lines containing a literal query, rank the other internal links on those lines. "
            "This surfaces narrower slice handles for broad hubs."
        ),
        returns="query, rank_mode, include_self, co_links[], count_returned",
        examples=[
            "grasp co-links KJ法 --limit 20",
            "grasp co-links KJ法 --rank raw --limit 20",
            "grasp co-links KJ法 --sample-limit 2 --limit 10",
            "grasp --json co-links KJ法 --limit 5",
        ],
        notes=[
            "co_links[] items include title, normalized_title, target_relation, link_count, line_count, source_page_count, total_source_views, latest_source_updated, and examples[].",
            "Default --rank slice demotes query-containing target titles so narrower handles surface first; --rank raw preserves count order.",
            "The exact query target is excluded by default; use --include-self to include it.",
        ],
    )
    co_links_parser.add_argument("query", help="Literal text to find in source lines.")
    co_links_parser.add_argument("--limit", type=int, default=50, help="Maximum co-link targets to return.")
    co_links_parser.add_argument("--sample-limit", type=int, default=3, help="Maximum example lines per co-link target.")
    co_links_parser.add_argument("--include-self", action="store_true", help="Include links whose target exactly matches the query.")
    co_links_parser.add_argument("--rank", choices=["slice", "raw"], default="slice", help="Ranking mode: slice demotes query-containing target titles; raw keeps count order.")

    cross_project_refs_parser = add_command_parser(
        subparsers,
        "cross-project-refs",
        help="Rank parsed Cosense cross-project slash links.",
        description=(
            "Extract target-aware Cosense shorthand links like [/project/Page] from stored line text, "
            "classify semantic/icon/project-root/self-project targets, and rank target projects. "
            "This is parsed link extraction, not line text search."
        ),
        returns="project, filters, limit, sample_limit, seed_limit, summary, acquire_plan, projects[]",
        examples=[
            "grasp cross-project-refs --limit 20",
            "grasp cross-project-refs --semantic-only --limit 12",
            "grasp cross-project-refs --semantic-only --seed-dir /tmp/grasp-seeds --limit 12",
            "grasp cross-project-refs --exclude-icons --sample-limit 5",
            "grasp --json cross-project-refs --semantic-only --limit 10",
        ],
        notes=[
            "projects[] items include project, mention_count, unique_target_count, source_page_count, total_source_views, target_class_counts, seed_titles[], top_targets[], and examples[].",
            "Default output excludes refs back to the selected source project; use --include-self to keep them.",
            "--semantic-only keeps only non-self, non-icon, non-root page refs for acquisition seed analysis.",
            "--seed-dir writes one seed file per returned project and adds runnable acquire commands.",
        ],
    )
    cross_project_refs_parser.add_argument("--limit", type=int, default=50, help="Maximum target projects to return.")
    cross_project_refs_parser.add_argument("--sample-limit", type=int, default=3, help="Maximum example lines per target project.")
    cross_project_refs_parser.add_argument("--seed-limit", type=int, default=20, help="Maximum semantic target titles to include per project for seed files/recipes.")
    cross_project_refs_parser.add_argument("--seed-dir", type=Path, default=None, help="Write one acquire seed file per returned project into this folder.")
    cross_project_refs_parser.add_argument("--project-url-base", default="https://scrapbox.io/", help="Base URL used in generated acquire commands.")
    cross_project_refs_parser.add_argument("--acquire-limit", type=int, default=None, help="Limit value used in generated acquire commands; defaults to --seed-limit.")
    cross_project_refs_parser.add_argument("--include-self", action="store_true", help="Include slash refs back to the selected source project.")
    cross_project_refs_parser.add_argument("--exclude-icons", action="store_true", help="Exclude .icon/.img target refs from returned project ranking.")
    cross_project_refs_parser.add_argument("--semantic-only", action="store_true", help="Return only semantic cross-project page refs, excluding icons, project roots, and self-project refs.")

    cross_project_acquire_parser = add_command_parser(
        subparsers,
        "cross-project-acquire",
        help="Acquire semantic slices from projects referenced by slash links.",
        description=(
            "Use parsed cross-project refs from the selected source project as seed titles, then "
            "acquire each target project into an explicit local namespace such as <project>:semantic. "
            "This mutates the local store unless --dry-run is used."
        ),
        returns=(
            "source_project, dry_run, limits, project_url_base, local_suffix, refs_summary, "
            "summary, projects[]"
        ),
        examples=[
            "grasp --project nishio cross-project-acquire --limit 5 --seed-limit 10",
            "grasp --project nishio cross-project-acquire --limit 12 --seed-limit 20 --acquire-limit 20",
            "grasp --project nishio cross-project-acquire --limit 5 --dry-run --json",
        ],
        notes=[
            "This is the executing counterpart to cross-project-refs --semantic-only.",
            "Each target project is acquired from its semantic seed_titles only; searchFullText/listPages are not used.",
            "The local namespace defaults to <target-project>:semantic so full export namespaces are not overwritten.",
            "Returned project rows are bounded summaries, not full acquire payloads.",
            "Successful project rows include reciprocal_refs back to the source project and top_internal_links from the acquired slice.",
        ],
    )
    cross_project_acquire_parser.add_argument("--limit", type=int, default=5, help="Maximum target projects to acquire.")
    cross_project_acquire_parser.add_argument("--sample-limit", type=int, default=2, help="Maximum source example lines per target project.")
    cross_project_acquire_parser.add_argument("--seed-limit", type=int, default=20, help="Maximum semantic target titles to use per target project.")
    cross_project_acquire_parser.add_argument("--acquire-limit", type=int, default=None, help="Maximum persistent pages to fetch per target project; defaults to --seed-limit.")
    cross_project_acquire_parser.add_argument("--page-sample-limit", type=int, default=5, help="Maximum acquired page titles to include per project summary.")
    cross_project_acquire_parser.add_argument("--failed-sample-limit", type=int, default=3, help="Maximum failed page entries to include per project summary.")
    cross_project_acquire_parser.add_argument("--top-links-limit", type=int, default=5, help="Maximum top internal link targets to include from each acquired slice.")
    cross_project_acquire_parser.add_argument("--summary-sample-limit", type=int, default=2, help="Maximum reciprocal/internal-link example lines per acquired slice.")
    cross_project_acquire_parser.add_argument("--project-url-base", default="https://scrapbox.io/", help="Base URL used to fetch target projects.")
    cross_project_acquire_parser.add_argument("--local-suffix", default="semantic", help="Local namespace suffix; target project X becomes X:<suffix>.")
    cross_project_acquire_parser.add_argument("--cosense-command", default="cosense", help="cosense CLI binary.")
    cross_project_acquire_parser.add_argument("--dry-run", action="store_true", help="Return the acquire plan without fetching or mutating the store.")

    gather_parser = add_command_parser(
        subparsers,
        "gather",
        help="Return a bounded retrieval bundle for a query.",
        description=(
            "Compose link stats, bare mention summary, co-link slices, representative mentions, "
            "and backlinks into one small bundle. This is an initial thin gather surface, not "
            "exact token packing."
        ),
        returns="query, budget, limits, co_link_rank_mode, returned_counts, total_counts, omitted_counts, banner|null, link_stats, mention_summary, mentions[], co_links[], backlinks[], recipes[]",
        examples=[
            "grasp gather KJ法",
            "grasp gather KJ法 --budget 8000",
            "grasp gather KJ法 --mentions-limit 5 --co-links-limit 10 --backlinks-limit 5",
            "grasp --json gather KJ法 --budget 4000",
        ],
        notes=[
            "--budget selects bounded row limits approximately; JSON returns budget_note to make this explicit.",
            "For huge hubs, banner explains that bulk-linking bare mentions is the wrong direction.",
        ],
    )
    gather_parser.add_argument("query", help="Literal query to gather around.")
    gather_parser.add_argument("--budget", type=int, default=4000, help="Approximate token budget used to choose default row limits.")
    gather_parser.add_argument("--mentions-limit", type=int, default=None, help="Maximum bare mention lines to include; defaults from --budget.")
    gather_parser.add_argument("--co-links-limit", type=int, default=None, help="Maximum co-link targets to include; defaults from --budget.")
    gather_parser.add_argument("--backlinks-limit", type=int, default=None, help="Maximum backlink lines to include; defaults from --budget.")

    export_ai_parser = add_command_parser(
        subparsers,
        "export-ai",
        aliases=["export-for-ai"],
        help="Export a page neighborhood as Cosense Export for AI-style text.",
        description=(
            "Render a page and its related pages into one AI-readable text file. "
            "Existing pages include the main page plus 1-hop pages; depth 2 also "
            "includes pages reachable through those 1-hop pages and shared link targets. "
            "Missing targets export pages that link to the requested title."
        ),
        returns=(
            "query, depth, page_exists, project_url, page_count, direct_count, "
            "indirect_count, pages[], text"
        ),
        examples=[
            "grasp export-ai 巨人の肩に登るコストの減少 > out.txt",
            "grasp export-ai 巨人の肩に登るコストの減少 --depth 2 --output out.txt",
            "grasp export-for-ai 民主主義 --direct-limit 100",
            "grasp --json export-ai 民主主義 --depth 1",
        ],
        notes=[
            "Default text output is the export body. With --output, text is written to the file and stdout is a short summary.",
            "The generated format follows the raw Export for AI samples; ordering is deterministic from the local graph store.",
        ],
    )
    export_ai_parser.add_argument("title", help="Existing page title or missing linked target to export.")
    export_ai_parser.add_argument("--depth", type=int, choices=[1, 2], default=1, help="Neighborhood depth to include.")
    export_ai_parser.add_argument(
        "--direct-limit",
        type=int,
        default=argparse.SUPPRESS,
        help="Maximum 1-hop pages to include; omit for no limit.",
    )
    export_ai_parser.add_argument(
        "--indirect-limit",
        type=int,
        default=argparse.SUPPRESS,
        help="Maximum 2-hop pages to include when --depth 2; omit for no limit.",
    )
    export_ai_parser.add_argument(
        "--project-url",
        default="https://scrapbox.io/nishio/",
        help="Project URL used to render page URLs in the export text.",
    )
    export_ai_parser.add_argument("--output", type=Path, default=None, help="Write export text to this file instead of stdout.")

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
            "grasp sync https://scrapbox.io/nishio/ --cosense-command cosense",
        ],
        notes=[
            "Requires @helpfeel/cosense-cli's `cosense` binary in PATH and a working login.",
            "Global --store selects the local store to update.",
        ],
    )
    sync_parser.add_argument("project_url", help="Hosted Cosense/Scrapbox project URL, e.g. https://scrapbox.io/nishio/.")
    sync_parser.add_argument("--limit", type=int, default=100, help="Maximum listPages entries to inspect.")
    sync_parser.add_argument("--batch-size", type=int, default=100, help="listPages page size.")
    sync_parser.add_argument("--cosense-command", default="cosense", help="cosense CLI binary.")
    sync_parser.add_argument("--dry-run", action="store_true", help="List changed pages without fetching/upserting them.")

    acquire_parser = add_command_parser(
        subparsers,
        "acquire",
        help="Acquire hosted Cosense pages without an admin JSON export.",
        description=(
            "Seed or replace a local project namespace by reading hosted Cosense pages "
            "through @helpfeel/cosense-cli. This is for non-admin or partial-corpus "
            "acquisition, distinct from sync of an already seeded full export."
        ),
        returns=(
            "project_url, project, modes[], coverage, limit, depth, search_results[], "
            "list_results[], criteria_fingerprint, candidate_window, fetched, updated, remote_fetched, "
            "reused, same_criteria_as_previous, skipped_nonpersistent[], failed_pages[], diagnostic|null, pages[], stats"
        ),
        examples=[
            "grasp --project nishio:search acquire https://scrapbox.io/nishio/ --search '[nishio.icon]' --limit 50",
            "grasp --project nishio:crawl acquire https://scrapbox.io/nishio/ --from-page 盲点カード --depth 1 --limit 100",
            "grasp --project nishio:mine acquire https://scrapbox.io/nishio/ --filter nishio --limit 200",
            "grasp acquire https://scrapbox.io/nishio/ --seed-file pages.txt",
        ],
        notes=[
            "Requires @helpfeel/cosense-cli's `cosense` binary in PATH and a working login.",
            "The acquired project namespace is replaced, not appended, so slice coverage stays explicit.",
            "If --project is omitted, the local namespace defaults to <remote-project>:acquire to avoid overwriting a full export.",
            "For the same acquisition criteria, pages with unchanged hosted updated timestamps are reused from the local store instead of read again.",
            "For partial corpora, backlinks/related/unresolved describe only acquired pages.",
        ],
    )
    acquire_parser.add_argument("project_url", help="Hosted Cosense/Scrapbox project URL, e.g. https://scrapbox.io/nishio/.")
    acquire_parser.add_argument("--search", action="append", default=[], help="searchFullText query to seed pages. May be repeated.")
    acquire_parser.add_argument("--from-page", action="append", default=[], help="Start page title or URL for link crawl. May be repeated.")
    acquire_parser.add_argument("--seed-file", type=Path, default=None, help="Text file of page titles or URLs, one per line.")
    acquire_parser.add_argument("--filter", dest="filter_name", default=None, help="listPages --filter name for author/icon related pages.")
    acquire_parser.add_argument("--full-list", action="store_true", help="Use listPages pagination as a full-list seed, bounded by --limit.")
    acquire_parser.add_argument("--depth", type=int, default=1, help="Link crawl depth for --from-page. 0 fetches only seed pages.")
    acquire_parser.add_argument("--limit", type=int, default=100, help="Maximum persistent pages to fetch and store.")
    acquire_parser.add_argument("--batch-size", type=int, default=100, help="listPages page size for --filter/--full-list.")
    acquire_parser.add_argument("--sort", default="updated", choices=["updated", "created", "accessed", "linked", "views", "title"], help="listPages sort for --filter/--full-list.")
    acquire_parser.add_argument("--cosense-command", default="cosense", help="cosense CLI binary.")

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
    aliases: list[str] | None = None,
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
    command_parser = subparsers.add_parser(
        name,
        aliases=aliases or [],
        help=help,
        description=description,
        epilog="\n".join(epilog_parts),
        formatter_class=GraspHelpFormatter,
    )
    command_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    command_parser.add_argument("--full-ids", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return command_parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "import":
        project = args.import_project or args.project
        try:
            if args.cosense_export is not None:
                export_path = args.cosense_export
                if not export_path.exists():
                    parser.error(f"export path does not exist: {export_path}")
                if export_path.is_dir():
                    parser.error(
                        "import --cosense expects a Cosense JSON export file, not a folder. "
                        "Use `grasp import --markdown <folder>` for a read-only Markdown mirror."
                    )
                result = import_export_to_sqlite(export_path, args.store, project_name=project)
            else:
                markdown_folder = args.markdown_folder
                if not markdown_folder.exists():
                    parser.error(f"Markdown folder does not exist: {markdown_folder}")
                if not markdown_folder.is_dir():
                    parser.error(f"import --markdown expects a folder, not a file: {markdown_folder}")
                result = import_markdown_folder_to_sqlite(
                    markdown_folder,
                    args.store,
                    project_name=project,
                    exclude_dirs=tuple(args.markdown_exclude_dir),
                )
        except MarkdownCollisionError as error:
            if args.json:
                emit_error_result(error)
                return 2
            parser.error(str(error))
        except ValueError as error:
            parser.error(str(error))
        emit_result(args, result)
        return 0

    if args.command == "import-forest":
        try:
            result = import_forest_from_registry(
                args.registry,
                args.store,
                wiki_dir=args.wiki_dir,
                exclude_dirs=tuple(args.markdown_exclude_dir),
                ambiguity_limit=args.ambiguity_limit,
                ambiguity_candidate_limit=args.ambiguity_candidate_limit,
            )
        except ValueError as error:
            parser.error(str(error))
        emit_result(args, result)
        return 0

    if args.command == "acquire" and not args.store.exists():
        ensure_store_schema(args.store)

    if not args.store.exists():
        if args.command == "stats":
            emit_result(args, store_missing_stats(args.store))
            return 0
        parser.error(store_missing_error(args.store))

    store: SQLiteStore | None = SQLiteStore(args.store, project=args.project)
    try:
        if args.command != "stats" and not store.schema_ok():
            schema_version = store.schema_version()
            store.close()
            store = None
            if not recover_store_from_import_cache(args.store):
                parser.error(
                    f"store schema is {schema_version}, current is {SCHEMA_VERSION}; "
                    "run `grasp import --cosense <json>` or `grasp import --markdown <folder>` to rebuild"
                )
            store = SQLiteStore(args.store, project=args.project)
        try:
            result = run_command(store, args)
        except ValueError as error:
            parser.error(str(error))
    finally:
        if store is not None:
            store.close()
    emit_result(args, result)
    return 0


def store_missing_stats(store_path: Path) -> dict[str, Any]:
    return {
        "store": str(store_path),
        "project": None,
        "project_count": 0,
        "projects": [],
        "schema_version": None,
        "current_schema_version": SCHEMA_VERSION,
        "schema_ok": False,
        "source_export": None,
        "imported_at": None,
        "pages": 0,
        "lines": 0,
        "edges": 0,
        "unresolved_targets": 0,
        "acquisition": None,
        "diagnostic": {
            "type": "store_missing",
            "message": f"store does not exist: {store_path}",
            "next_actions": [
                "Create the store from a Cosense JSON export: grasp import --cosense <json>",
                "Index a read-only Markdown folder mirror: grasp import --markdown <folder>",
                "Acquire hosted pages without admin export: grasp acquire <project-url> --search <query>",
                "Use another store path: grasp --store <path> stats",
            ],
            "markdown_folder_import": "Markdown folder import is available as a read-only mirror: grasp import --markdown <folder>.",
        },
    }


def store_missing_error(store_path: Path) -> str:
    return (
        f"store does not exist: {store_path}\n"
        "Create it from a Cosense JSON export: grasp import --cosense <json>\n"
        "Or index a read-only Markdown folder mirror: grasp import --markdown <folder>\n"
        "Or acquire hosted pages without admin export: grasp acquire <project-url> --search <query>\n"
        "Or choose another store: grasp --store <path> <command>"
    )


def emit_result(args: argparse.Namespace, result: Any) -> None:
    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        aliases = LineIdAliases(enabled=not args.full_ids)
        sys.stdout.write(format_result(args.command, result, aliases=aliases))


def emit_error_result(error: MarkdownCollisionError) -> None:
    json.dump(
        {
            "error": str(error),
            "diagnostic": error.to_diagnostic(),
        },
        sys.stderr,
        ensure_ascii=False,
        indent=2,
    )
    sys.stderr.write("\n")


def run_command(store: SQLiteStore, args: argparse.Namespace) -> Any:
    if args.command == "stats":
        return store.stats()
    if args.command == "read":
        if args.around_line:
            if args.page_id or args.source_path:
                raise ValueError("--around-line cannot be combined with --page-id or --path")
            if args.line_limit is not None:
                raise ValueError("--line-limit cannot be combined with --around-line; use --line-context")
            return store.read_around_line(
                args.around_line,
                title=args.title,
                line_context=args.line_context,
                backlink_limit=args.backlinks_limit,
                related_limit=args.related_limit,
                unresolved_limit=args.unresolved_limit,
                related_snippets=args.related_snippets,
                related_snippet_lines=args.related_snippet_lines,
                related_snippet_mode=args.related_snippet_mode,
            )
        if args.page_id and args.source_path:
            raise ValueError("read accepts only one of --page-id or --path")
        if args.title is None and args.page_id is None and args.source_path is None:
            raise ValueError("read requires a title, --page-id, --path, or --around-line <line-id>")
        return store.read(
            args.title,
            page_id=args.page_id,
            source_path=args.source_path,
            line_limit=args.line_limit,
            backlink_limit=args.backlinks_limit,
            related_limit=args.related_limit,
            unresolved_limit=args.unresolved_limit,
            related_snippets=args.related_snippets,
            related_snippet_lines=args.related_snippet_lines,
            related_snippet_mode=args.related_snippet_mode,
        )
    if args.command == "backlinks":
        return store.backlinks_report(args.title, limit=args.limit, offset=args.offset)
    if args.command == "ambiguities":
        return store.ambiguities(limit=args.limit, offset=args.offset, candidate_limit=args.candidate_limit)
    if args.command == "cross-project-spread":
        return store.cross_project_spread(
            args.title,
            limit=args.limit,
            offset=args.offset,
            candidate_limit=args.candidate_limit,
        )
    if args.command == "cross-project-spreads":
        return store.cross_project_spreads(
            limit=args.limit,
            offset=args.offset,
            min_projects=args.min_projects,
            project_limit=args.project_limit,
            candidate_limit=args.candidate_limit,
        )
    if args.command == "related":
        return store.related_report(args.title, limit=args.limit)
    if args.command == "path":
        return store.paths_between(
            args.source,
            args.target,
            max_depth=args.max_depth,
            limit=args.limit,
        )
    if args.command == "link-stats":
        return store.link_stats(args.title)
    if args.command == "peek":
        page = store.resolve_page(args.title)
        line_offset = max(0, args.line_offset)
        if page is None:
            return {
                "query": args.title,
                "page": None,
                "line_offset": line_offset,
                "lines": [],
                "lines_truncated": False,
                "lines_truncated_before": False,
                "lines_truncated_after": False,
            }
        lines, truncated_after = store.page_lines(page, args.line_limit, offset=line_offset)
        truncated_before = line_offset > 0
        return {
            "query": args.title,
            "page": page.to_summary(),
            "line_offset": line_offset,
            "lines": [line.to_dict() for line in lines],
            "lines_truncated": truncated_after,
            "lines_truncated_before": truncated_before,
            "lines_truncated_after": truncated_after,
        }
    if args.command == "suggest":
        return {
            "query": args.partial,
            "mode": args.mode,
            "suggestions": store.suggest(args.partial, limit=args.limit, mode=args.mode),
        }
    if args.command == "search":
        hits = store.search(
            args.query,
            limit=args.limit,
            offset=args.offset,
            mode=args.mode,
            scope=args.scope,
            context=args.context,
        )
        return {
            "query": args.query,
            "mode": args.mode,
            "scope": args.scope,
            "context": max(0, args.context),
            "hits": hits,
            "count_returned": len(hits),
            "offset": args.offset,
            "recovery_hints": None if hits else store.recovery_hints(args.query, limit=3),
        }
    if args.command == "mentions":
        result = store.mentions(
            args.query,
            limit=args.limit,
            offset=args.offset,
            include_linked=args.include_linked,
            unlinked_only=args.unlinked,
            context=args.context,
        )
        result["offset"] = args.offset
        return result
    if args.command == "co-links":
        co_links = store.co_links(
            args.query,
            limit=args.limit,
            sample_limit=args.sample_limit,
            include_self=args.include_self,
            rank_mode=args.rank,
        )
        return {
            "query": args.query,
            "co_links": co_links,
            "count_returned": len(co_links),
            "include_self": args.include_self,
            "rank_mode": args.rank,
        }
    if args.command == "cross-project-refs":
        result = store.cross_project_refs(
            limit=args.limit,
            sample_limit=args.sample_limit,
            seed_limit=args.seed_limit,
            include_self=args.include_self,
            exclude_icons=args.exclude_icons,
            semantic_only=args.semantic_only,
        )
        add_cross_project_acquire_recipes(
            result,
            seed_dir=args.seed_dir,
            project_url_base=args.project_url_base,
            acquire_limit=args.acquire_limit if args.acquire_limit is not None else args.seed_limit,
        )
        return result
    if args.command == "cross-project-acquire":
        return run_cross_project_acquire(
            store,
            client=CosenseCliClient(args.cosense_command),
            limit=args.limit,
            sample_limit=args.sample_limit,
            seed_limit=args.seed_limit,
            acquire_limit=args.acquire_limit if args.acquire_limit is not None else args.seed_limit,
            page_sample_limit=args.page_sample_limit,
            failed_sample_limit=args.failed_sample_limit,
            top_links_limit=args.top_links_limit,
            summary_sample_limit=args.summary_sample_limit,
            project_url_base=args.project_url_base,
            local_suffix=args.local_suffix,
            dry_run=args.dry_run,
        )
    if args.command == "gather":
        return store.gather(
            args.query,
            budget=args.budget,
            backlink_limit=args.backlinks_limit,
            mention_limit=args.mentions_limit,
            co_link_limit=args.co_links_limit,
        )
    if args.command in {"export-ai", "export-for-ai"}:
        result = store.export_ai(
            args.title,
            depth=args.depth,
            direct_limit=getattr(args, "direct_limit", None),
            indirect_limit=getattr(args, "indirect_limit", None),
            project_url=args.project_url,
        )
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(result["text"], encoding="utf-8")
            result["output"] = str(args.output)
        return result
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
    if args.command == "acquire":
        seed_titles = read_seed_file(args.seed_file) if args.seed_file is not None else []
        return acquire_from_cosense(
            store,
            args.project_url,
            client=CosenseCliClient(args.cosense_command),
            project=args.project,
            searches=args.search,
            from_pages=args.from_page,
            seed_titles=seed_titles,
            filter_name=args.filter_name,
            full_list=args.full_list,
            depth=args.depth,
            limit=args.limit,
            batch_size=args.batch_size,
            sort=args.sort,
        )
    raise ValueError(f"unknown command: {args.command}")


def read_seed_file(path: Path) -> list[str]:
    if not path.exists():
        raise ValueError(f"seed file does not exist: {path}")
    if path.is_dir():
        raise ValueError(f"seed file must be a text file, not a folder: {path}")
    titles: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        titles.append(line)
    return titles


def add_cross_project_acquire_recipes(
    result: dict[str, Any],
    *,
    seed_dir: Path | None,
    project_url_base: str,
    acquire_limit: int,
) -> None:
    acquire_limit = max(0, acquire_limit)
    seed_files_written = 0
    if seed_dir is not None:
        if seed_dir.exists() and not seed_dir.is_dir():
            raise ValueError(f"--seed-dir must be a folder, not a file: {seed_dir}")
        seed_dir.mkdir(parents=True, exist_ok=True)

    for item in result.get("projects", []):
        seed_titles = item.get("seed_titles") or []
        if not seed_titles:
            item["acquire_recipe"] = None
            continue

        target_project = item["project"]
        project_url = cross_project_url(project_url_base, target_project)
        local_project = f"{target_project}:semantic"
        seed_file: Path | None = None
        seed_file_for_command = "<seed-file>"
        if seed_dir is not None:
            seed_file = seed_dir / f"{safe_seed_filename(target_project)}.txt"
            seed_file.write_text("\n".join(seed_titles) + "\n", encoding="utf-8")
            seed_file_for_command = str(seed_file)
            seed_files_written += 1

        item["acquire_recipe"] = {
            "project_url": project_url,
            "local_project": local_project,
            "seed_file": str(seed_file) if seed_file is not None else None,
            "seed_file_written": seed_file is not None,
            "command": [
                "grasp",
                "--project",
                local_project,
                "acquire",
                project_url,
                "--seed-file",
                seed_file_for_command,
                "--limit",
                str(acquire_limit),
            ],
        }

    result["acquire_plan"] = {
        "project_url_base": project_url_base,
        "acquire_limit": acquire_limit,
        "seed_dir": str(seed_dir) if seed_dir is not None else None,
        "seed_files_written": seed_files_written,
    }


def cross_project_url(project_url_base: str, target_project: str) -> str:
    return project_url_base.rstrip("/") + "/" + target_project.strip("/") + "/"


def safe_seed_filename(value: str) -> str:
    safe = "".join(
        char if char.isalnum() or char in "._-" else "_"
        for char in value.strip()
    ).strip("._")
    return safe or "project"


def run_cross_project_acquire(
    store: SQLiteStore,
    *,
    client: CosenseCliClient,
    limit: int,
    sample_limit: int,
    seed_limit: int,
    acquire_limit: int,
    page_sample_limit: int,
    failed_sample_limit: int,
    top_links_limit: int,
    summary_sample_limit: int,
    project_url_base: str,
    local_suffix: str,
    dry_run: bool,
) -> dict[str, Any]:
    limit = max(0, limit)
    sample_limit = max(0, sample_limit)
    seed_limit = max(0, seed_limit)
    if acquire_limit <= 0:
        raise ValueError("--acquire-limit must be > 0")
    page_sample_limit = max(0, page_sample_limit)
    failed_sample_limit = max(0, failed_sample_limit)
    top_links_limit = max(0, top_links_limit)
    summary_sample_limit = max(0, summary_sample_limit)
    suffix = normalize_local_suffix(local_suffix)

    refs = store.cross_project_refs(
        limit=limit,
        sample_limit=sample_limit,
        seed_limit=seed_limit,
        semantic_only=True,
    )
    source_project = refs["project"]
    projects: list[dict[str, Any]] = []
    for ref_project in refs.get("projects", []):
        if ref_project.get("seed_titles"):
            projects.append(
                cross_project_acquire_plan_item(
                    ref_project,
                    project_url_base=project_url_base,
                    local_suffix=suffix,
                    acquire_limit=acquire_limit,
                )
            )

    summary = {
        "planned_projects": len(projects),
        "attempted_projects": 0,
        "succeeded_projects": 0,
        "empty_projects": 0,
        "error_projects": 0,
        "fetched_pages": 0,
        "failed_pages": 0,
        "skipped_nonpersistent": 0,
        "diagnostic_counts": {},
    }

    try:
        if not dry_run:
            for item in projects:
                summary["attempted_projects"] += 1
                try:
                    acquisition = acquire_from_cosense(
                        store,
                        item["project_url"],
                        client=client,
                        project=item["local_project"],
                        seed_titles=item["seed_titles"],
                        limit=acquire_limit,
                    )
                except Exception as error:  # Keep the batch bounded even if one project fails before page fetch reporting.
                    item.update(cross_project_acquire_error_summary(error))
                    summary["error_projects"] += 1
                    bump_count(summary["diagnostic_counts"], "orchestration_error")
                    continue

                item.update(
                    cross_project_acquire_result_summary(
                        acquisition,
                        store=store,
                        source_project=source_project,
                        page_sample_limit=page_sample_limit,
                        failed_sample_limit=failed_sample_limit,
                        top_links_limit=top_links_limit,
                        summary_sample_limit=summary_sample_limit,
                    )
                )
                fetched = int(item["fetched"])
                failed = int(item["failed"])
                skipped = int(item["skipped_nonpersistent"])
                summary["fetched_pages"] += fetched
                summary["failed_pages"] += failed
                summary["skipped_nonpersistent"] += skipped
                diagnostic_type = item.get("diagnostic_type")
                if diagnostic_type:
                    bump_count(summary["diagnostic_counts"], diagnostic_type)
                if fetched > 0:
                    summary["succeeded_projects"] += 1
                elif item["status"] == "empty":
                    summary["empty_projects"] += 1
                elif item["status"] == "error":
                    summary["error_projects"] += 1
    finally:
        store.project = source_project
    return {
        "source_project": source_project,
        "dry_run": dry_run,
        "limits": {
            "projects": limit,
            "source_examples": sample_limit,
            "seed_titles": seed_limit,
            "acquire_pages": acquire_limit,
            "page_sample": page_sample_limit,
            "failed_sample": failed_sample_limit,
            "top_links": top_links_limit,
            "summary_sample": summary_sample_limit,
        },
        "project_url_base": project_url_base,
        "local_suffix": suffix,
        "refs_summary": refs["summary"],
        "summary": summary,
        "projects": projects,
    }


def normalize_local_suffix(value: str) -> str:
    suffix = value.strip().strip(":")
    if not suffix:
        raise ValueError("--local-suffix must not be empty")
    return suffix


def cross_project_acquire_plan_item(
    ref_project: dict[str, Any],
    *,
    project_url_base: str,
    local_suffix: str,
    acquire_limit: int,
) -> dict[str, Any]:
    target_project = ref_project["project"]
    project_url = cross_project_url(project_url_base, target_project)
    local_project = f"{target_project}:{local_suffix}"
    seed_titles = list(ref_project.get("seed_titles") or [])
    return {
        "project": target_project,
        "project_url": project_url,
        "local_project": local_project,
        "status": "planned",
        "mention_count": ref_project["mention_count"],
        "unique_target_count": ref_project["unique_target_count"],
        "source_page_count": ref_project["source_page_count"],
        "seed_title_count": ref_project["seed_title_count"],
        "seed_title_limit": ref_project["seed_title_limit"],
        "omitted_seed_title_count": ref_project["omitted_seed_title_count"],
        "seed_titles": seed_titles,
        "top_targets": ref_project.get("top_targets", [])[:5],
        "examples": ref_project.get("examples", []),
        "command": [
            "grasp",
            "--project",
            local_project,
            "acquire",
            project_url,
            "--seed-file",
            "<seed-file>",
            "--limit",
            str(acquire_limit),
        ],
    }


def cross_project_acquire_result_summary(
    acquisition: dict[str, Any],
    *,
    store: SQLiteStore,
    source_project: str,
    page_sample_limit: int,
    failed_sample_limit: int,
    top_links_limit: int,
    summary_sample_limit: int,
) -> dict[str, Any]:
    fetched = int(acquisition.get("fetched", 0))
    failed_pages = acquisition.get("failed_pages") or []
    skipped_nonpersistent = acquisition.get("skipped_nonpersistent") or []
    diagnostic = acquisition.get("diagnostic")
    status = "acquired" if fetched > 0 else "empty"
    return {
        "status": status,
        "coverage": acquisition.get("coverage"),
        "fetched": fetched,
        "updated": int(acquisition.get("updated", 0)),
        "failed": len(failed_pages),
        "skipped_nonpersistent": len(skipped_nonpersistent),
        "diagnostic": diagnostic,
        "diagnostic_type": diagnostic.get("type") if diagnostic else None,
        "page_sample": (acquisition.get("pages") or [])[:page_sample_limit],
        "failed_page_sample": failed_pages[:failed_sample_limit],
        "skipped_nonpersistent_sample": skipped_nonpersistent[:failed_sample_limit],
        "reciprocal_refs": store.cross_project_refs_to(
            source_project,
            limit=top_links_limit,
            sample_limit=summary_sample_limit,
        ),
        "top_internal_links": store.top_internal_links(
            limit=top_links_limit,
            sample_limit=summary_sample_limit,
        ),
    }


def cross_project_acquire_error_summary(error: Exception) -> dict[str, Any]:
    return {
        "status": "error",
        "coverage": "none",
        "fetched": 0,
        "updated": 0,
        "failed": 0,
        "skipped_nonpersistent": 0,
        "diagnostic": {
            "type": "orchestration_error",
            "severity": "error",
            "message": str(error),
            "next_actions": ["Inspect the project entry, cosense command, and local store state; retry the failed project alone with grasp acquire."],
        },
        "diagnostic_type": "orchestration_error",
        "page_sample": [],
        "failed_page_sample": [],
        "skipped_nonpersistent_sample": [],
        "reciprocal_refs": None,
        "top_internal_links": [],
    }


def bump_count(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


class LineIdAliases:
    def __init__(self, *, enabled: bool):
        self.enabled = enabled
        self._page_to_alias: dict[str, str] = {}

    def format_line_id(self, line_id: str | None) -> str:
        if line_id is None:
            return "(none)"
        if not self.enabled:
            return line_id
        page_id, separator, line_index = line_id.rpartition(":")
        if not separator or not page_id or not line_index:
            return line_id
        alias = self._page_to_alias.get(page_id)
        if alias is None:
            alias = f"P{len(self._page_to_alias) + 1}"
            self._page_to_alias[page_id] = alias
        return f"{alias}:{line_index}"

    def legend(self) -> str:
        if not self.enabled or not self._page_to_alias:
            return ""
        items = ", ".join(
            f"{alias}={page_id}"
            for page_id, alias in self._page_to_alias.items()
        )
        return f"line-id aliases: {items}\n"


def with_alias_legend(text: str, aliases: LineIdAliases) -> str:
    legend = aliases.legend()
    if not legend:
        return text
    if not text.startswith("#"):
        return f"{legend}{text}"
    newline_index = text.find("\n")
    if newline_index < 0:
        return f"{text}\n{legend}"
    return f"{text[:newline_index + 1]}{legend}{text[newline_index + 1:]}"


def format_result(command: str, result: Any, aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    if command == "import":
        return format_import(result)
    if command == "import-forest":
        return format_import_forest(result)
    if command == "stats":
        return format_stats(result)
    if command == "read":
        return format_read(result, aliases=aliases)
    if command == "backlinks":
        return format_backlinks(result, aliases=aliases)
    if command == "ambiguities":
        return format_ambiguities(result)
    if command == "cross-project-spread":
        return format_cross_project_spread(result)
    if command == "cross-project-spreads":
        return format_cross_project_spreads(result)
    if command == "related":
        return format_related_result(result, aliases=aliases)
    if command == "path":
        return format_path(result, aliases=aliases)
    if command == "link-stats":
        return format_link_stats(result, aliases=aliases)
    if command == "peek":
        return format_peek(result, aliases=aliases)
    if command == "suggest":
        return format_suggest(result["query"], result["suggestions"], mode=result.get("mode"))
    if command == "search":
        return format_search(
            result["query"],
            result["hits"],
            result.get("offset", 0),
            result.get("recovery_hints"),
            mode=result.get("mode", "literal"),
            scope=result.get("scope", "line"),
            context=result.get("context", 0),
            aliases=aliases,
        )
    if command == "mentions":
        return format_mentions(result, aliases=aliases)
    if command == "co-links":
        return format_co_links(result, aliases=aliases)
    if command == "cross-project-refs":
        return format_cross_project_refs(result, aliases=aliases)
    if command == "cross-project-acquire":
        return format_cross_project_acquire(result, aliases=aliases)
    if command == "gather":
        return format_gather(result, aliases=aliases)
    if command in {"export-ai", "export-for-ai"}:
        return format_export_ai(result)
    if command == "unresolved":
        return with_alias_legend(format_unresolved_targets(result["unresolved_targets"], aliases=aliases), aliases)
    if command == "sync":
        return format_sync(result)
    if command == "acquire":
        return format_acquire(result)
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def format_import(result: dict[str, Any]) -> str:
    markdown_import = result.get("markdown_import")
    markdown_section = ""
    if markdown_import:
        markdown_section = (
            f"markdown_import: {markdown_import['mode']}\n"
            f"changed_files: {markdown_import['changed_files']}\n"
        )
        if markdown_import.get("full_rebuild_reason"):
            markdown_section += f"full_rebuild_reason: {markdown_import['full_rebuild_reason']}\n"
    return (
        f"store: {result['store']}\n"
        f"project: {result['project']}\n"
        f"schema: {result['schema_version']}\n"
        f"pages: {result['pages']}\n"
        f"lines: {result['lines']}\n"
        f"edges: {result['edges']}\n"
        f"unresolved_targets: {result['unresolved_targets']}\n"
        f"{markdown_section}"
    )


def format_import_forest(result: dict[str, Any]) -> str:
    aggregate = result["aggregate"]
    parts = [
        "# Import Forest\n",
        f"registry: {result['registry']}\n",
        f"store: {result['store']}\n",
        f"wiki_dir: {result['wiki_dir']}\n",
        f"entries: {result['entry_count']}\n",
        f"success: {result['success_count']}\n",
        f"failure: {result['failure_count']}\n",
        f"missing: {result['missing_count']}\n",
        f"skipped: {result['skipped_count']}\n",
        f"pages: {aggregate['pages']}\n",
        f"lines: {aggregate['lines']}\n",
        f"edges: {aggregate['edges']}\n",
        f"unresolved_targets: {aggregate['unresolved_targets']}\n",
        f"wall_seconds: {result['wall_seconds']}\n",
    ]
    ambiguities = result.get("ambiguities")
    if ambiguities:
        if "diagnostic" in ambiguities:
            parts.append(f"ambiguities: unavailable ({ambiguities['diagnostic']['type']})\n")
        else:
            parts.append(
                f"ambiguities: {ambiguities['handles_returned']} / {ambiguities['handle_count']} handles returned\n"
            )
    failures = [project for project in result["projects"] if project["status"] in {"failure", "missing", "skipped"}]
    if failures:
        parts.append("\n## Failures\n")
        for project in failures[:20]:
            diagnostic = project.get("diagnostic") or {}
            label = project.get("name") or f"entry-{project['index']}"
            parts.append(f"- {label}: {project['status']} ({diagnostic.get('type')}) {diagnostic.get('message', '')}\n")
        if len(failures) > 20:
            parts.append(f"- ... {len(failures) - 20} more\n")
    successes = [project for project in result["projects"] if project["status"] == "success"]
    if successes:
        parts.append("\n## Imported Projects\n")
        for project in successes[:20]:
            parts.append(
                f"- {project['project']}: pages={project['pages']}, lines={project['lines']}, "
                f"edges={project['edges']}, unresolved={project['unresolved_targets']}\n"
            )
        if len(successes) > 20:
            parts.append(f"- ... {len(successes) - 20} more\n")
    return "".join(parts)


def format_stats(result: dict[str, Any]) -> str:
    project_lines = "".join(
        f"- {project['name']} (pages {project['pages']}, source {project['source_export']})\n"
        for project in result.get("projects", [])
    )
    project_section = project_lines if project_lines else "(none)\n"
    diagnostic = format_diagnostic(result.get("diagnostic"))
    acquisition = result.get("acquisition")
    acquisition_section = ""
    if acquisition:
        window = acquisition.get("candidate_window") or {}
        updated_range = window.get("updated_range") or {}
        range_line = ""
        if updated_range:
            range_line = (
                "candidate_updated_range: "
                f"{updated_range.get('newest')} .. {updated_range.get('oldest')}\n"
            )
        acquisition_section = (
            "\n## Acquisition\n"
            f"mode: {acquisition.get('mode')}\n"
            f"coverage: {acquisition.get('coverage')}\n"
            f"project_url: {acquisition.get('project_url')}\n"
            f"criteria_fingerprint: {acquisition.get('criteria_fingerprint')}\n"
            f"fetched: {acquisition.get('fetched')}\n"
            f"remote_fetched: {acquisition.get('remote_fetched')}\n"
            f"reused: {acquisition.get('reused')}\n"
            f"{range_line}"
            "note: backlinks/related/unresolved are within the acquired corpus.\n"
        )
    return (
        f"store: {result['store']}\n"
        f"project: {result['project']}\n"
        f"project_count: {result['project_count']}\n"
        f"schema: {result['schema_version']}\n"
        f"current_schema: {result['current_schema_version']}\n"
        f"schema_ok: {result['schema_ok']}\n"
        f"source_export: {result['source_export']}\n"
        f"imported_at: {result['imported_at']}\n"
        f"pages: {result['pages']}\n"
        f"lines: {result['lines']}\n"
        f"edges: {result['edges']}\n"
        f"unresolved_targets: {result['unresolved_targets']}\n"
        f"\n## Projects\n{project_section}"
        f"{acquisition_section}"
        f"{diagnostic}"
    )


def format_diagnostic(diagnostic: dict[str, Any] | None) -> str:
    if not diagnostic:
        return ""

    parts = ["\n## Diagnostic\n"]
    message = diagnostic.get("message")
    if message:
        parts.append(f"{message}\n")

    next_actions = diagnostic.get("next_actions") or []
    if next_actions:
        parts.append("\nNext actions:\n")
        for action in next_actions:
            parts.append(f"- {action}\n")

    markdown_note = diagnostic.get("markdown_folder_import")
    if markdown_note:
        parts.append(f"\n{markdown_note}\n")
    return "".join(parts)


def format_read(result: dict[str, Any], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    parts: list[str] = []
    ambiguity = result.get("ambiguity")
    if ambiguity:
        parts.append(f"# {result['query']}\n")
        parts.append("page: ambiguous handle\n")
        parts.append(f"handle_norm: {ambiguity['handle_norm']}\n")
        parts.append(f"candidates: {ambiguity['candidate_count']}\n")
        parts.append("\n## Candidates\n")
        for candidate in ambiguity.get("candidates") or []:
            path = candidate.get("path")
            path_text = f" path={path}" if path else ""
            parts.append(
                f"- {candidate['title']} id={candidate['page_id']}"
                f" role={candidate.get('graph_role') or 'content'}{path_text}\n"
            )
        parts.append("\nUse `read --page-id <id>` or `read --path <path>` to choose one.\n")
        return "".join(parts)

    page = result["page"]
    title = page["title"] if page else result["query"]
    parts.append(f"# {title}\n")

    if page is None:
        link_stats = result.get("link_stats", {})
        linked = link_stats.get("link_count", 0) > 0
        page_status = "linked target without page" if linked else "missing page"
        parts.append(f"page: {page_status}\n")
        parts.append(format_link_stats_summary(link_stats))
        parts.append(format_recovery_hints(result["query"], result.get("recovery_hints"), aliases=aliases))
    else:
        parts.append(
            f"id: {page['id']}\nviews: {page['views']}\nlines: {page['line_count']}\n"
        )
        parts.append(format_link_stats_summary(result.get("link_stats", {})))
        line_window = result.get("line_window")
        if line_window:
            parts.append(
                f"line_window: {aliases.format_line_id(line_window['around_line_id'])} "
                f"(lines {line_window['start_index']}-{line_window['end_index']}, "
                f"context {line_window['context']})\n"
            )
        parts.append("\n## Lines\n")
        for line in result["lines"]:
            parts.append(f"{aliases.format_line_id(line['line_id'])}  {line['text']}\n")
        if result["lines_truncated"]:
            parts.append("...\n")

    parts.append("\n## Backlinks\n")
    backlinks = result["backlinks"]
    if backlinks:
        parts.append(format_edge_list(backlinks, aliases=aliases))
    else:
        parts.append("(none)\n")

    related_heading = "Related Source Pages" if page is None else "Related 2-hop"
    parts.append(f"\n## {related_heading}\n")
    related = result["related"]
    if related:
        parts.append(format_related_items(related, aliases=aliases))
    else:
        parts.append("(none)\n")

    if page is not None:
        parts.append("\n## Unresolved Targets From This Page\n")
        unresolved_targets = result["unresolved_targets"]
        if unresolved_targets:
            parts.append(format_unresolved_targets(unresolved_targets, aliases=aliases))
        else:
            parts.append("(none)\n")

    return with_alias_legend("".join(parts), aliases)


def format_backlinks(result: dict[str, Any], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    query = result["query"]
    backlinks = result["backlinks"]
    offset = result.get("offset", 0)
    parts = [f"# Backlinks: {query}\n", f"offset: {offset}\n"]
    if result.get("resolution_status") == "ambiguous":
        ambiguity = result.get("ambiguity") or {}
        parts.append(f"resolution: ambiguous ({ambiguity.get('candidate_count', 0)} candidates)\n")
        parts.append("\n## Incoming links to ambiguous handle\n")
        handle_backlinks = result.get("handle_backlinks") or {}
        handle_items = handle_backlinks.get("items", backlinks)
        if not handle_items:
            parts.append("(none)\n")
        else:
            parts.append(format_edge_list(handle_items, aliases=aliases))
        parts.append("\n## Candidate pages\n")
        for candidate_result in result.get("candidate_backlinks", []):
            candidate = candidate_result["candidate"]
            suffix = f" path={candidate['path']}" if candidate.get("path") else ""
            parts.append(
                f"- {candidate['title']} id={candidate['page_id']}{suffix}; "
                f"resolved_backlinks={candidate_result['count_total']}\n"
            )
            resolved = candidate_result.get("resolved_backlinks", [])
            if resolved:
                parts.append(format_edge_list(resolved, aliases=aliases))
        return with_alias_legend("".join(parts), aliases)

    if not backlinks:
        parts.append("(none)\n")
    else:
        parts.append(format_edge_list(backlinks, aliases=aliases))
    return with_alias_legend("".join(parts), aliases)


def format_ambiguities(result: dict[str, Any]) -> str:
    parts = [
        "# Ambiguous Handles\n",
        f"scope: {result['scope']}\n",
        f"project_count: {result['project_count']}\n",
        f"handles: {result['handles_returned']} / {result['handle_count']} returned\n",
        f"offset: {result['offset']}\n",
        f"candidate_limit: {result['candidate_limit']}\n",
    ]
    projects = result.get("projects", [])
    if projects:
        parts.append("\n## Projects\n")
        for project in projects:
            parts.append(
                f"- {project['project']}: handles={project['ambiguous_handle_count']}, "
                f"ambiguous_links={project['ambiguous_link_count']}, "
                f"source_pages={project['ambiguous_source_page_count']}, "
                f"max_candidates={project['max_candidate_count']}\n"
            )
    parts.append("\n## Handles\n")
    if not result.get("ambiguities"):
        parts.append("(none)\n")
        return "".join(parts)
    for item in result["ambiguities"]:
        parts.append(
            f"- [{item['project']}] {item['handle']} ({item['handle_norm']}): "
            f"candidates={item['candidate_count']}, "
            f"ambiguous_links={item['ambiguous_link_count']}, "
            f"source_pages={item['ambiguous_source_page_count']}\n"
        )
        for candidate in item.get("candidates", []):
            suffix = f" path={candidate['path']}" if candidate.get("path") else ""
            parts.append(
                f"  - {candidate['title']} id={candidate['page_id']} "
                f"role={candidate['graph_role']}{suffix}\n"
            )
        if item.get("candidates_truncated"):
            omitted = item["candidate_count"] - item["candidates_returned"]
            parts.append(f"  - ... {omitted} more candidates\n")
    return "".join(parts)


def format_cross_project_spread(result: dict[str, Any]) -> str:
    totals = result["totals"]
    resolution_counts = totals.get("resolution_counts", {})
    parts = [
        f"# Cross-project spread: {result['query']}\n",
        f"normalized: {result['handle_norm']}\n",
        f"scope: {result['scope']}\n",
        f"connection_strength: {result['connection_strength']}\n",
        f"projects: {result['signal_project_count']} / {result['project_count']} with signal\n",
        (
            "totals: "
            f"materialized_projects={totals['materialized_project_count']}, "
            f"ambiguous_projects={totals['ambiguous_project_count']}, "
            f"unresolved_projects={totals['unresolved_project_count']}, "
            f"incoming_links={totals['incoming_link_count']}\n"
        ),
        (
            "resolution_counts: "
            f"resolved={resolution_counts.get('resolved_unique', 0)}, "
            f"ambiguous={resolution_counts.get('ambiguous', 0)}, "
            f"unresolved={resolution_counts.get('unresolved', 0)}\n"
        ),
        f"note: {result['note']}\n",
    ]
    top_sources = result.get("top_source_projects") or []
    if top_sources:
        parts.append("\n## Top Source Projects\n")
        for item in top_sources:
            counts = item["resolution_counts"]
            parts.append(
                f"- {item['project']}: links={item['incoming_link_count']}, "
                f"source_pages={item['incoming_source_page_count']}, "
                f"resolved={counts.get('resolved_unique', 0)}, "
                f"ambiguous={counts.get('ambiguous', 0)}, unresolved={counts.get('unresolved', 0)}\n"
            )
    projects = result.get("projects") or []
    parts.append("\n## Projects\n")
    if not projects:
        parts.append("(none)\n")
    for item in projects:
        materialized = item["materialized"]
        incoming = item["incoming"]
        counts = incoming["resolution_counts"]
        unresolved = item.get("unresolved")
        unresolved_text = f", unresolved_links={unresolved['link_count']}" if unresolved else ""
        parts.append(
            f"- {item['project']}: candidates={materialized['candidate_count']}, "
            f"incoming={incoming['incoming_link_count']} "
            f"(resolved={counts.get('resolved_unique', 0)}, ambiguous={counts.get('ambiguous', 0)}, "
            f"unresolved={counts.get('unresolved', 0)}){unresolved_text}\n"
        )
        for candidate in materialized.get("candidates") or []:
            suffix = f" path={candidate['path']}" if candidate.get("path") else ""
            parts.append(
                f"  - {candidate['title']} id={candidate['page_id']} "
                f"role={candidate.get('graph_role') or 'content'}{suffix}\n"
            )
        if materialized.get("candidates_truncated"):
            parts.append("  - ...\n")
    return "".join(parts)


def format_cross_project_spreads(result: dict[str, Any]) -> str:
    parts = [
        "# Cross-project spreads\n",
        f"scope: {result['scope']}\n",
        f"connection_strength: {result['connection_strength']}\n",
        f"handles: {result['handles_returned']} / {result['handle_count']} returned",
        f" (total scanned: {result['total_handle_count']}, min_projects={result['min_projects']})\n",
        f"rank_basis: {result['rank_basis']}\n",
        f"note: {result['note']}\n",
        "\n## Spreads\n",
    ]
    spreads = result.get("spreads") or []
    if not spreads:
        parts.append("(none)\n")
        return "".join(parts)
    for item in spreads:
        counts = item["resolution_counts"]
        parts.append(
            f"- {item['title']} ({item['handle_norm']}): "
            f"spread={item['project_spread']}, band={item['rank_band']}, "
            f"materialized_projects={item['materialized_project_count']}, "
            f"unresolved_projects={item['unresolved_project_count']}, "
            f"incoming_links={item['incoming_link_count']} "
            f"(resolved={counts.get('resolved_unique', 0)}, ambiguous={counts.get('ambiguous', 0)}, "
            f"unresolved={counts.get('unresolved', 0)})\n"
        )
        for project in item.get("project_samples") or []:
            materialized = project["materialized"]
            incoming = project["incoming"]
            unresolved = project.get("unresolved")
            unresolved_text = f", unresolved_links={unresolved['link_count']}" if unresolved else ""
            parts.append(
                f"  - {project['project']}: candidates={materialized['candidate_count']}, "
                f"incoming={incoming['incoming_link_count']}{unresolved_text}\n"
            )
    return "".join(parts)


def format_edge_list(edges: list[dict[str, Any]], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    parts = []
    for edge in edges:
        parts.append(f"- {edge['source_title']} {aliases.format_line_id(edge['line_id'])}: {edge['line_text']}\n")
    return "".join(parts)


def format_related_result(result: dict[str, Any], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    if result.get("resolution_status") == "ambiguous":
        return format_ambiguous_related(result, aliases=aliases)
    return format_related(
        result["query"],
        result["related"],
        result.get("recovery_hints"),
        aliases=aliases,
    )


def format_ambiguous_related(result: dict[str, Any], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    query = result["query"]
    ambiguity = result.get("ambiguity") or {}
    parts = [
        f"# Related source pages: {query}\n",
        f"resolution: ambiguous ({ambiguity.get('candidate_count', 0)} candidates)\n",
        "\n## Source pages linking to ambiguous handle\n",
    ]
    related = result.get("related") or []
    if not related:
        parts.append("(none)\n")
    else:
        parts.append(format_related_items(related, aliases=aliases))
    parts.append("\n## Candidate pages\n")
    for candidate_result in result.get("candidate_related", []):
        candidate = candidate_result["candidate"]
        suffix = f" path={candidate['path']}" if candidate.get("path") else ""
        parts.append(
            f"- {candidate['title']} id={candidate['page_id']}{suffix}; "
            f"related={candidate_result['count_returned']}\n"
        )
        candidate_related = candidate_result.get("related", [])
        if candidate_related:
            parts.append(indent_lines(format_related_items(candidate_related, aliases=aliases), "  "))
    return with_alias_legend("".join(parts), aliases)


def format_related(
    query: str,
    related: list[dict[str, Any]],
    recovery_hints: dict[str, Any] | None = None,
    aliases: LineIdAliases | None = None,
) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    heading = "Related source pages" if is_source_page_related(related) else "Related 2-hop"
    parts = [f"# {heading}: {query}\n"]
    if not related:
        parts.append("(none)\n")
    else:
        parts.append(format_related_items(related, aliases=aliases))
    parts.append(format_recovery_hints(query, recovery_hints, aliases=aliases))
    return with_alias_legend("".join(parts), aliases)


def format_related_items(related: list[dict[str, Any]], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    parts: list[str] = []
    for item in related:
        via = ", ".join(item["via"])
        if item.get("relation") in {"backlink-source", "ambiguous-handle-source"}:
            parts.append(f"- {item['title']} (links {item['score']}, views {item['views']}; target {via})\n")
        else:
            parts.append(f"- {item['title']} (score {item['score']}, views {item['views']}; via {via})\n")
        if "snippet_lines" in item:
            window = item.get("snippet_window")
            if window and window.get("mode") == "edge":
                parts.append(
                    f"  snippet: edge {aliases.format_line_id(window['context_line_id'])} "
                    f"-> {window.get('target_title', '')}\n"
                )
            elif item.get("snippet_mode") == "lead-fallback":
                parts.append("  snippet: lead-fallback\n")
            for line in item["snippet_lines"]:
                parts.append(f"  {aliases.format_line_id(line['line_id'])}  {line['text']}\n")
            if item.get("snippet_truncated"):
                parts.append("  ...\n")
    return "".join(parts)


def indent_lines(text: str, prefix: str) -> str:
    return "".join(f"{prefix}{line}" if line.strip() else line for line in text.splitlines(keepends=True))


def is_source_page_related(related: list[dict[str, Any]]) -> bool:
    return bool(related) and all(
        item.get("relation") in {"backlink-source", "ambiguous-handle-source"}
        for item in related
    )


def format_path(result: dict[str, Any], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    source_title = result["query"]["source"]
    target_title = result["query"]["target"]
    parts = [
        f"# Path: {source_title} -> {target_title}\n",
        f"max_depth: {result['max_depth']}\n",
    ]
    if result.get("source") is None:
        parts.append(f"source: missing ({source_title})\n")
    if result.get("target") is None:
        parts.append(f"target: missing ({target_title})\n")

    paths = result.get("paths") or []
    if not paths:
        parts.append("(none)\n")
        recovery = result.get("recovery_hints") or {}
        parts.append(format_recovery_hints(source_title, recovery.get("source"), aliases=aliases))
        parts.append(format_recovery_hints(target_title, recovery.get("target"), aliases=aliases))
        parts.append(format_path_recovery_hints(source_title, target_title, recovery.get("path"), aliases=aliases))
        return with_alias_legend("".join(parts), aliases)

    for index, path in enumerate(paths, start=1):
        titles = " -> ".join(node["title"] for node in path["nodes"])
        parts.append(f"\n## Path {index} (distance {path['distance']})\n")
        parts.append(f"{titles}\n")
        for edge in path["edges"]:
            direction = "<-" if edge["direction"] == "reverse" else "->"
            parts.append(
                f"- {edge['source_title']} {aliases.format_line_id(edge['line_id'])} {direction} "
                f"[{edge['target_title']}]: {edge['line_text']}\n"
            )
    if result.get("truncated"):
        parts.append("\ntruncated: true\n")
    return with_alias_legend("".join(parts), aliases)


def format_path_recovery_hints(
    source_title: str,
    target_title: str,
    recovery_hints: dict[str, Any] | None,
    aliases: LineIdAliases | None = None,
) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    if not recovery_hints:
        return ""

    related_limit = recovery_hints.get("related_limit", 3)
    backlinks_limit = recovery_hints.get("backlinks_limit", 3)
    next_max_depth = recovery_hints.get("next_max_depth")
    parts = [
        "\n## Path Recovery Hints\n",
        f"reason: {recovery_hints.get('reason', 'no_path')}\n",
    ]
    if next_max_depth is not None:
        parts.append(
            f"try: grasp path {shlex.quote(source_title)} {shlex.quote(target_title)} "
            f"--max-depth {next_max_depth}\n"
        )
    parts.extend(
        [
            f"try: grasp related {shlex.quote(source_title)} --limit {related_limit}\n",
            f"try: grasp related {shlex.quote(target_title)} --limit {related_limit}\n",
            f"try: grasp backlinks {shlex.quote(source_title)} --limit {backlinks_limit}\n",
            f"try: grasp backlinks {shlex.quote(target_title)} --limit {backlinks_limit}\n",
        ]
    )

    source_stats = recovery_hints.get("source_link_stats")
    target_stats = recovery_hints.get("target_link_stats")
    if source_stats or target_stats:
        parts.append("\nLink stats:\n")
        if source_stats:
            parts.append(f"- source {source_stats['title']}: {format_link_stats_summary(source_stats)}")
        if target_stats:
            parts.append(f"- target {target_stats['title']}: {format_link_stats_summary(target_stats)}")

    source_related = recovery_hints.get("source_related") or []
    if source_related:
        parts.append("\nSource related:\n")
        parts.append(format_related_items(source_related, aliases=aliases))

    target_related = recovery_hints.get("target_related") or []
    if target_related:
        parts.append("\nTarget related:\n")
        parts.append(format_related_items(target_related, aliases=aliases))

    source_backlinks = recovery_hints.get("source_backlinks") or []
    if source_backlinks:
        parts.append("\nBacklinks to source:\n")
        parts.append(format_edge_list(source_backlinks, aliases=aliases))

    target_backlinks = recovery_hints.get("target_backlinks") or []
    if target_backlinks:
        parts.append("\nBacklinks to target:\n")
        parts.append(format_edge_list(target_backlinks, aliases=aliases))

    return "".join(parts)


def format_link_stats(result: dict[str, Any], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
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
    ambiguity = result.get("ambiguity")
    if ambiguity is not None:
        parts.append(f"ambiguity: {ambiguity['candidate_count']} candidates\n")
        for candidate in ambiguity.get("candidates", [])[:10]:
            suffix = f" path={candidate['path']}" if candidate.get("path") else ""
            parts.append(f"- {candidate['title']} id={candidate['page_id']}{suffix}\n")
    parts.append(format_recovery_hints(result["query"], result.get("recovery_hints"), aliases=aliases))
    return with_alias_legend("".join(parts), aliases)


def format_link_stats_summary(result: dict[str, Any]) -> str:
    if not result:
        return ""
    return (
        f"links_to_this: {result['link_count']} from {result['source_page_count']} pages "
        f"({result['link_multiplicity']})\n"
    )


def format_recovery_hints(
    query: str,
    recovery_hints: dict[str, Any] | None,
    aliases: LineIdAliases | None = None,
) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    if not recovery_hints:
        return ""

    quoted_query = shlex.quote(query)
    suggest = recovery_hints.get("suggest", {})
    search = recovery_hints.get("search", {})
    unresolved = recovery_hints.get("unresolved_targets", {})
    suggest_limit = suggest.get("limit", 3)
    search_limit = search.get("limit", 3)

    parts = [
        "\n## Recovery Hints\n",
        f"try: grasp suggest {quoted_query} --limit {suggest_limit}\n",
        f"try: grasp search {quoted_query} --limit {search_limit}\n",
    ]

    suggestions = suggest.get("suggestions") or []
    if suggestions:
        parts.append("\nTitle suggestions:\n")
        for page in suggestions:
            parts.append(f"- {page['title']} (views {page['views']}, lines {page['line_count']})\n")

    targets = unresolved.get("targets") or []
    if targets:
        parts.append("\nUnresolved target suggestions:\n")
        for target in targets:
            parts.append(f"- {target['title']} (links {target['link_count']}, pages {target['source_page_count']})\n")

    hits = search.get("hits") or []
    if hits:
        parts.append("\nSearch hits:\n")
        for hit in hits:
            parts.append(f"- {hit['source_title']} {aliases.format_line_id(hit['line_id'])}: {hit['line_text']}\n")

    if not suggestions and not targets and not hits:
        parts.append("\n(no nearby title suggestions or line hits)\n")
    return "".join(parts)


def format_peek(result: dict[str, Any], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    page = result["page"]
    if page is None:
        return f"# {result['query']}\npage: missing\n"

    parts = [f"# {page['title']}\n", f"id: {page['id']}\nviews: {page['views']}\nlines: {page['line_count']}\n"]
    line_offset = result.get("line_offset", 0)
    if line_offset:
        parts.append(f"line_offset: {line_offset}\n")
    parts.append("\n")
    if result.get("lines_truncated_before"):
        parts.append("...\n")
    for line in result["lines"]:
        parts.append(f"{aliases.format_line_id(line['line_id'])}  {line['text']}\n")
    if result.get("lines_truncated_after", result["lines_truncated"]):
        parts.append("...\n")
    return with_alias_legend("".join(parts), aliases)


def format_suggest(query: str, suggestions: list[dict[str, Any]], *, mode: str | None = None) -> str:
    parts = [f"# Suggestions: {query}\n"]
    if mode:
        parts.append(f"mode: {mode}\n")
    if not suggestions:
        parts.append("(none)\n")
    else:
        for page in suggestions:
            match = ""
            if page.get("match_mode"):
                match = f", match={page['match_mode']}, score={page.get('match_score', 0)}"
            parts.append(f"- {page['title']} (views {page['views']}, lines {page['line_count']}{match})\n")
    return "".join(parts)


def format_search(
    query: str,
    hits: list[dict[str, Any]],
    offset: int = 0,
    recovery_hints: dict[str, Any] | None = None,
    *,
    mode: str = "literal",
    scope: str = "line",
    context: int = 0,
    aliases: LineIdAliases | None = None,
) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    parts = [f"# Search: {query}\n", f"mode: {mode}\n", f"scope: {scope}\n"]
    if context:
        parts.append(f"context: {context}\n")
    parts.append(f"offset: {offset}\n")
    if not hits:
        parts.append("(none)\n")
    else:
        for hit in hits:
            match_note = " [normalized]" if hit.get("match_mode") == "normalized" else ""
            parts.append(f"- {hit['source_title']} {aliases.format_line_id(hit['line_id'])}{match_note}: {hit['line_text']}\n")
            window = hit.get("context_window")
            if window:
                parts.append(
                    f"  context: lines {window['start_index']}-{window['end_index']} "
                    f"(around {aliases.format_line_id(window['around_line_id'])})\n"
                )
                for line in hit.get("context_lines", []):
                    parts.append(f"  {aliases.format_line_id(line['line_id'])}  {line['text']}\n")
    parts.append(format_recovery_hints(query, recovery_hints, aliases=aliases))
    return with_alias_legend("".join(parts), aliases)


def format_mentions(result: dict[str, Any], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    parts = [
        f"# Mentions: {result['query']}\n",
        f"mode: {result['mode']}\n",
        f"offset: {result.get('offset', 0)}\n",
    ]
    if result.get("context"):
        parts.append(f"context: {result['context']}\n")
    parts.append(format_mention_summary(result["summary"]))
    mentions = result.get("mentions") or []
    parts.append("\n## Lines\n")
    if mentions:
        parts.append(format_mention_items(mentions, aliases=aliases))
    else:
        parts.append("(none)\n")
    return with_alias_legend("".join(parts), aliases)


def format_mention_summary(summary: dict[str, Any]) -> str:
    parts = [
        "\n## Summary\n",
        f"total: {summary['total_occurrences']} occurrences on {summary['total_lines']} lines / {summary['total_pages']} pages\n",
        f"bare: {summary['bare_occurrences']} occurrences on {summary['bare_lines']} lines / {summary['bare_pages']} pages\n",
        f"linked: {summary['linked_occurrences']} occurrences\n",
        f"returned_lines: {summary['returned_lines']}\n",
    ]
    status_counts = summary.get("page_status_counts") or {}
    if status_counts:
        parts.append("page_status_counts:\n")
        for key in ("exact-link-page", "query-link-page", "unlinked-page"):
            item = status_counts.get(key) or {}
            parts.append(
                f"- {key}: {item.get('bare_occurrences', 0)} bare occurrences, "
                f"{item.get('lines', 0)} lines, {item.get('pages', 0)} pages\n"
            )
    candidate = summary.get("come_from_candidate")
    if candidate:
        label = "yes" if candidate.get("is_candidate") else "no"
        parts.append(f"come_from_candidate: {label} (score {candidate.get('score', 0)})\n")
        for reason in (candidate.get("rationale") or [])[:3]:
            parts.append(f"- {reason}\n")
    return "".join(parts)


def format_mention_items(mentions: list[dict[str, Any]], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    parts: list[str] = []
    for hit in mentions:
        parts.append(
            f"- {hit['source_title']} {aliases.format_line_id(hit['line_id'])} "
            f"[{hit['classification']}; bare {hit['bare_occurrence_count']}; linked {hit['linked_occurrence_count']}]: "
            f"{hit['line_text']}\n"
        )
        query_targets = hit.get("query_link_targets") or []
        if query_targets:
            parts.append("  query_link_targets: " + ", ".join(target["title"] for target in query_targets[:5]) + "\n")
        line_targets = hit.get("line_link_targets") or []
        if line_targets:
            parts.append("  line_link_targets: " + ", ".join(target["title"] for target in line_targets[:5]) + "\n")
        window = hit.get("context_window")
        if window:
            parts.append(
                f"  context: lines {window['start_index']}-{window['end_index']} "
                f"(around {aliases.format_line_id(window['around_line_id'])})\n"
            )
            for line in hit.get("context_lines", []):
                parts.append(f"  {aliases.format_line_id(line['line_id'])}  {line['text']}\n")
    return "".join(parts)


def format_co_links(result: dict[str, Any], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    parts = [f"# Co-links: {result['query']}\n"]
    parts.append(f"rank_mode: {result.get('rank_mode', 'slice')}\n")
    if result.get("include_self"):
        parts.append("include_self: true\n")
    co_links = result.get("co_links") or []
    if co_links:
        parts.append(format_co_link_items(co_links, aliases=aliases))
    else:
        parts.append("(none)\n")
    return with_alias_legend("".join(parts), aliases)


def format_co_link_items(co_links: list[dict[str, Any]], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    parts: list[str] = []
    for item in co_links:
        parts.append(
            f"- {item['title']} (links {item['link_count']}, lines {item['line_count']}, "
            f"pages {item['source_page_count']}, views {item['total_source_views']}, "
            f"relation {item.get('target_relation', 'slice-handle')})\n"
        )
        for example in item.get("examples", [])[:2]:
            parts.append(f"  - {example['source_title']} {aliases.format_line_id(example['line_id'])}: {example['line_text']}\n")
    return "".join(parts)


def format_cross_project_refs(result: dict[str, Any], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    summary = result["summary"]
    filters = result["filters"]
    parts = [
        f"# Cross-project refs: {result['project']}\n",
        f"filters: include_self={filters['include_self']}, exclude_icons={filters['exclude_icons']}, semantic_only={filters['semantic_only']}\n",
        (
            f"refs: {summary['filtered_refs']}/{summary['total_refs']} returned after filters; "
            f"projects: {summary['filtered_projects']} filtered, {summary['returned_projects']} returned\n"
        ),
        "target_class_counts: " + format_count_map(summary["target_class_counts"]) + "\n",
        "filtered_target_class_counts: " + format_count_map(summary["filtered_target_class_counts"]) + "\n",
    ]
    acquire_plan = result.get("acquire_plan")
    if acquire_plan:
        seed_dir = acquire_plan.get("seed_dir") or "(not writing files)"
        parts.append(
            f"acquire_plan: limit {acquire_plan.get('acquire_limit')}, "
            f"seed_dir {seed_dir}, files_written {acquire_plan.get('seed_files_written', 0)}\n"
        )
    projects = result.get("projects") or []
    if not projects:
        parts.append("(none)\n")
        return "".join(parts)

    parts.append("\n## Projects\n")
    for item in projects:
        parts.append(
            f"- {item['project']} (refs {item['mention_count']}, targets {item['unique_target_count']}, "
            f"source_pages {item['source_page_count']}, views {item['total_source_views']}; "
            f"classes {format_count_map(item['target_class_counts'])})\n"
        )
        top_targets = item.get("top_targets") or []
        if top_targets:
            formatted_targets = []
            for target in top_targets[:5]:
                title = target["title"] or "(project root)"
                formatted_targets.append(f"{title} [{target['target_class']}] x{target['mention_count']}")
            parts.append("  top_targets: " + "; ".join(formatted_targets) + "\n")
        seed_titles = item.get("seed_titles") or []
        if seed_titles:
            omitted = item.get("omitted_seed_title_count", 0)
            seed_note = f" (+{omitted} omitted)" if omitted else ""
            parts.append("  seed_titles: " + "; ".join(seed_titles[:5]) + seed_note + "\n")
        recipe = item.get("acquire_recipe")
        if recipe:
            label = "acquire" if recipe.get("seed_file_written") else "acquire_template"
            command = " ".join(shlex.quote(str(part)) for part in recipe["command"])
            parts.append(f"  {label}: {command}\n")
        for example in (item.get("examples") or [])[:2]:
            target_title = example["target_title"] or "(project root)"
            parts.append(
                f"  - {example['source_title']} {aliases.format_line_id(example['line_id'])} "
                f"-> /{example['target_project']}/{target_title} [{example['target_class']}]: "
                f"{example['line_text']}\n"
            )
    return with_alias_legend("".join(parts), aliases)


def format_count_map(counts: dict[str, int]) -> str:
    return ", ".join(
        f"{key} {counts.get(key, 0)}"
        for key in ("semantic", "icon", "project-root", "self-project")
    )


def format_cross_project_acquire(result: dict[str, Any], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    summary = result["summary"]
    parts = [
        f"# Cross-project acquire: {result['source_project']}\n",
        f"dry_run: {result['dry_run']}\n",
        (
            "projects: "
            f"planned {summary['planned_projects']}, attempted {summary['attempted_projects']}, "
            f"succeeded {summary['succeeded_projects']}, empty {summary['empty_projects']}, "
            f"errors {summary['error_projects']}\n"
        ),
        (
            "pages: "
            f"fetched {summary['fetched_pages']}, failed {summary['failed_pages']}, "
            f"skipped_nonpersistent {summary['skipped_nonpersistent']}\n"
        ),
    ]
    diagnostic_counts = summary.get("diagnostic_counts") or {}
    if diagnostic_counts:
        parts.append("diagnostics: " + ", ".join(f"{key}={value}" for key, value in sorted(diagnostic_counts.items())) + "\n")
    projects = result.get("projects") or []
    if not projects:
        parts.append("(none)\n")
        return "".join(parts)

    parts.append("\n## Projects\n")
    for item in projects:
        parts.append(
            f"- {item['project']} -> {item['local_project']} "
            f"({item['status']}; seeds {len(item.get('seed_titles') or [])}/{item['seed_title_count']}, "
            f"refs {item['mention_count']}, source_pages {item['source_page_count']})\n"
        )
        if result["dry_run"]:
            command = " ".join(shlex.quote(str(part)) for part in item["command"])
            parts.append(f"  acquire_template: {command}\n")
        else:
            parts.append(
                f"  fetched {item.get('fetched', 0)}, failed {item.get('failed', 0)}, "
                f"skipped_nonpersistent {item.get('skipped_nonpersistent', 0)}\n"
            )
            diagnostic = item.get("diagnostic")
            if diagnostic:
                parts.append(f"  diagnostic: {diagnostic.get('severity')}: {diagnostic.get('type')} - {diagnostic.get('message')}\n")
            page_sample = item.get("page_sample") or []
            if page_sample:
                parts.append("  pages: " + "; ".join(page["title"] for page in page_sample) + "\n")
            reciprocal_refs = item.get("reciprocal_refs") or {}
            if reciprocal_refs.get("mention_count"):
                top_targets = reciprocal_refs.get("top_targets") or []
                target_note = ""
                if top_targets:
                    target_note = " (" + "; ".join(
                        f"{target['title'] or '(project root)'} [{target['target_class']}] x{target['mention_count']}"
                        for target in top_targets[:3]
                    ) + ")"
                parts.append(
                    f"  reciprocal_refs_to_source: {reciprocal_refs['mention_count']} "
                    f"from {reciprocal_refs['source_page_count']} pages{target_note}\n"
                )
            top_internal_links = item.get("top_internal_links") or []
            if top_internal_links:
                formatted_links = []
                for link in top_internal_links[:5]:
                    exists_note = "" if link.get("target_page_exists") else "?"
                    formatted_links.append(f"{link['title']}{exists_note} x{link['link_count']}")
                parts.append("  top_internal_links: " + "; ".join(formatted_links) + "\n")
            failed_sample = item.get("failed_page_sample") or []
            if failed_sample:
                formatted = []
                for page in failed_sample:
                    label = page.get("title_or_url") or page.get("url")
                    error_class = page.get("error_class") or "unknown"
                    formatted.append(f"{label} [{error_class}]")
                parts.append("  failed: " + "; ".join(formatted) + "\n")
        for example in (item.get("examples") or [])[:1]:
            target_title = example["target_title"] or "(project root)"
            parts.append(
                f"  - seed source: {example['source_title']} {aliases.format_line_id(example['line_id'])} "
                f"-> /{example['target_project']}/{target_title}: {example['line_text']}\n"
            )
    return with_alias_legend("".join(parts), aliases)


def format_gather(result: dict[str, Any], aliases: LineIdAliases | None = None) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    parts = [
        f"# Gather: {result['query']}\n",
        f"budget: {result['budget']} ({result['budget_note']})\n",
    ]
    limits = result.get("limits") or {}
    parts.append(
        "limits: "
        f"mentions {limits.get('mentions')}, co_links {limits.get('co_links')}, backlinks {limits.get('backlinks')}\n"
    )
    parts.append(f"co_link_rank_mode: {result.get('co_link_rank_mode', 'slice')}\n")
    returned_counts = result.get("returned_counts") or {}
    total_counts = result.get("total_counts") or {}
    omitted_counts = result.get("omitted_counts") or {}
    if returned_counts and total_counts and omitted_counts:
        parts.append(
            "row_counts: "
            f"mentions {returned_counts.get('mentions', 0)}/{total_counts.get('mentions', 0)}, "
            f"co_links {returned_counts.get('co_links', 0)}/{total_counts.get('co_links', 0)}, "
            f"backlinks {returned_counts.get('backlinks', 0)}/{total_counts.get('backlinks', 0)}\n"
        )
        parts.append(
            "omitted_rows: "
            f"mentions {omitted_counts.get('mentions', 0)}, "
            f"co_links {omitted_counts.get('co_links', 0)}, "
            f"backlinks {omitted_counts.get('backlinks', 0)}\n"
        )
    row_count_basis = result.get("row_count_basis") or {}
    if row_count_basis:
        parts.append(
            "row_count_basis: "
            f"mentions={row_count_basis.get('mentions')}; "
            f"co_links={row_count_basis.get('co_links')}; "
            f"backlinks={row_count_basis.get('backlinks')}\n"
        )
    banner = result.get("banner")
    if banner:
        parts.append(f"\n## Banner\n{banner['kind']}: {banner['message']}\n")

    parts.append("\n## Link Stats\n")
    parts.append(format_link_stats_summary(result.get("link_stats", {})))

    parts.append(format_mention_summary(result["mention_summary"]))

    parts.append("\n## Co-link Slices\n")
    co_links = result.get("co_links") or []
    parts.append(format_co_link_items(co_links, aliases=aliases) if co_links else "(none)\n")

    parts.append("\n## Bare Mention Samples\n")
    mentions = result.get("mentions") or []
    parts.append(format_mention_items(mentions, aliases=aliases) if mentions else "(none)\n")

    parts.append("\n## Backlinks\n")
    backlinks = result.get("backlinks") or []
    parts.append(format_edge_list(backlinks, aliases=aliases) if backlinks else "(none)\n")

    recipes = result.get("recipes") or []
    if recipes:
        parts.append("\n## Recipes\n")
        for recipe in recipes:
            command = " ".join(shlex.quote(str(part)) for part in recipe["command"])
            parts.append(f"- {command}\n  {recipe['why']}\n")
    return with_alias_legend("".join(parts), aliases)


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


def format_acquire(result: dict[str, Any]) -> str:
    window = result.get("candidate_window") or {}
    updated_range = window.get("updated_range") or {}
    parts = [
        f"project: {result['project']}\n",
        f"project_url: {result['project_url']}\n",
        f"modes: {', '.join(result['modes'])}\n",
        f"coverage: {result['coverage']}\n",
        f"criteria_fingerprint: {result['criteria_fingerprint']}\n",
        f"same_criteria_as_previous: {result['same_criteria_as_previous']}\n",
        f"fetched: {result['fetched']}\n",
        f"updated: {result['updated']}\n",
        f"remote_fetched: {result['remote_fetched']}\n",
        f"reused: {result['reused']}\n",
        "note: backlinks/related/unresolved now describe only the acquired corpus for this project namespace.\n",
    ]
    if updated_range:
        parts.append(
            "candidate_updated_range: "
            f"{updated_range.get('newest')} .. {updated_range.get('oldest')}\n"
        )
    diagnostic = result.get("diagnostic")
    if diagnostic:
        parts.append(
            "\n## Diagnostic\n"
            f"{diagnostic['severity']}: {diagnostic['type']} - {diagnostic['message']}\n"
            f"failed: {diagnostic['failed']} / candidates: {diagnostic['candidate_count']}\n"
        )
        error_classes = diagnostic.get("error_classes") or {}
        if error_classes:
            parts.append("error_classes: " + ", ".join(f"{key}={value}" for key, value in sorted(error_classes.items())) + "\n")
        next_actions = diagnostic.get("next_actions") or []
        if next_actions:
            parts.append("next_actions:\n")
            for action in next_actions:
                parts.append(f"- {action}\n")
    if result["pages"]:
        parts.append("\n## Acquired Pages\n")
        for page in result["pages"][:20]:
            suffix = " reused" if page.get("reused") else ""
            parts.append(f"- {page['title']} ({page['updated']}){suffix}\n")
        if len(result["pages"]) > 20:
            parts.append(f"... {len(result['pages']) - 20} more\n")
    if result["skipped_nonpersistent"]:
        parts.append("\n## Skipped Nonpersistent\n")
        for page in result["skipped_nonpersistent"]:
            parts.append(f"- {page['title']} {page['url']}\n")
    if result["failed_pages"]:
        parts.append("\n## Failed Pages\n")
        for page in result["failed_pages"]:
            parts.append(f"- {page['title_or_url']}: {page['error']}\n")
    return "".join(parts)


def format_export_ai(result: dict[str, Any]) -> str:
    output = result.get("output")
    if output:
        return (
            f"wrote: {output}\n"
            f"pages: {result['page_count']}\n"
            f"direct: {result['direct_count']}\n"
            f"indirect: {result['indirect_count']}\n"
        )
    return result["text"]


def format_unresolved_targets(
    unresolved_targets: list[dict[str, Any]],
    aliases: LineIdAliases | None = None,
) -> str:
    aliases = aliases or LineIdAliases(enabled=False)
    parts: list[str] = []
    if not unresolved_targets:
        return "(none)\n"

    for item in unresolved_targets:
        parts.append(
            f"- {item['title']} (links {item['link_count']}, pages {item['source_page_count']}, views {item['total_source_views']})\n"
        )
        for example in item["examples"][:2]:
            parts.append(f"  - {example['source_title']} {aliases.format_line_id(example['line_id'])}: {example['line_text']}\n")
    return "".join(parts)
