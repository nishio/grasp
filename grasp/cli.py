from __future__ import annotations

import argparse
from datetime import datetime, timezone
from difflib import SequenceMatcher
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import sys
from textwrap import dedent
from typing import Any

from .cosense import normalize_title
from .cosense_cli import CosenseCliClient, acquire_from_cosense, sync_from_cosense
from .forest import import_forest_from_registry
from .journal import append_journal_event, make_journal_event, read_journal_events
from .markdown import (
    MarkdownCollisionError,
    MarkdownMirror,
    iter_markdown_files,
    markdown_projection_text,
    markdown_wikilink_target,
    parse_frontmatter_values,
    split_markdown_frontmatter,
)
from .sqlite_store import (
    SCHEMA_VERSION,
    SQLiteStore,
    ensure_store_schema,
    import_export_to_sqlite,
    import_markdown_folder_to_sqlite,
    insert_store_event,
    recover_store_from_import_cache,
)


LOG_ENTRY_HEADING_RE = re.compile(r"^## \[(?P<timestamp>[^\]]+)\]\s+(?P<op>[^|]+?)\s*\|\s*(?P<summary>.*)$")
LOG_ENTRY_MARKDOWN_PATH_RE = re.compile(r"(?<![\w/.-])(?P<path>[\w.-]+(?:/[\w.-]+)*\.md)(?![\w/.-])")
STORE_WRITE_COMMANDS = {
    "acquire",
    "append-log",
    "append-section",
    "import-log-records",
    "rename",
    "rename-page",
    "revert-event",
    "revert-events",
    "sync",
    "write-page",
}
REVERSIBLE_EVENT_TYPES = {"page_create", "section_append", "log_append", "page_update", "page_rename"}


class GraspCliError(ValueError):
    def __init__(self, message: str, *, diagnostic: dict[str, Any] | None = None):
        super().__init__(message)
        self.diagnostic = diagnostic


class ProjectionExportRollbackError(GraspCliError):
    pass


class ProjectionExportRollbackFailedError(GraspCliError):
    pass


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


def default_actor() -> str:
    return os.environ.get("GRASP_ACTOR", "")


def default_session_id() -> str:
    return os.environ.get("GRASP_SESSION_ID", "")


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
    parser.add_argument("--actor", default=default_actor(), help="Actor metadata for SQLite events written by write/revert/import-log/adopt commands. Defaults to $GRASP_ACTOR.")
    parser.add_argument("--session-id", default=default_session_id(), help="Session/work-unit metadata for SQLite events written by write/revert/import-log/adopt commands. Defaults to $GRASP_SESSION_ID.")

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

    adopt_parser = add_command_parser(
        subparsers,
        "adopt-markdown",
        help="Adopt an existing Markdown wiki into the store and event journal.",
        description=(
            "Import a Markdown folder into the SQLite materialized index, insert initial page_create/log_entry_import "
            "events into SQLite events, and append compatibility records to a durable JSONL journal. "
            "This is the Phase 1 bridge toward native authority + Markdown projection."
        ),
        returns=(
            "store, project, journal, journal_events, sqlite_events_inserted, sqlite_events_skipped, adopted_pages, log_entry_records, "
            "pages, lines, edges, unresolved_targets, markdown_import"
        ),
        examples=[
            "grasp adopt-markdown wiki --project grasp-wiki --journal wiki.grasp/events.jsonl",
            "grasp --store /tmp/grasp.sqlite adopt-markdown wiki --project grasp-wiki --replace-journal",
        ],
        notes=[
            "The default journal path is <markdown-folder-name>.grasp/events.jsonl beside the folder.",
            "Existing journals are not overwritten unless --replace-journal is supplied.",
            "Log section subjects are inferred from body wikilinks and Markdown paths; type: log-entry files can use frontmatter subjects/pages.",
            "The journal event contract is fixed in grasp.journal; replay/write surfaces are added later.",
        ],
    )
    adopt_parser.add_argument("folder", type=Path, help="Markdown folder to adopt.")
    adopt_parser.add_argument("--project", dest="adopt_project", default=None, help="Project namespace. Defaults to --project, then folder name.")
    adopt_parser.add_argument("--journal", type=Path, default=None, help="JSONL journal path. Defaults to <folder>.grasp/events.jsonl beside the Markdown folder.")
    adopt_parser.add_argument("--replace-journal", action="store_true", help="Replace an existing journal file before appending adoption events.")
    adopt_parser.add_argument(
        "--markdown-exclude-dir",
        action="append",
        default=[],
        metavar="NAME",
        help="Directory basename to skip when adopting the Markdown mirror. Repeat for multiple names.",
    )

    import_log_records_parser = add_command_parser(
        subparsers,
        "import-log-records",
        help="Import Markdown log sections into journal record events.",
        description=(
            "Split Markdown log pages and type: log-entry files into first-class log_entry_import journal records. "
            "This does not rewrite Markdown projection; it only appends missing record events to an existing journal."
        ),
        returns=(
            "project, folder, journal, log_pages, scanned_records, imported_records, updated_records, skipped_records, record_ids[]"
        ),
        examples=[
            "grasp --project grasp-wiki import-log-records wiki --journal wiki.grasp/events.jsonl",
            "grasp --project grasp-wiki --json import-log-records wiki --journal wiki.grasp/events.jsonl",
        ],
        notes=[
            "The journal must already exist, normally from adopt-markdown.",
            "Records are deduplicated by stable record_id and content_fingerprint within the selected project.",
            "If an existing record_id has a new content_fingerprint, a new version event is appended.",
            "type: log-entry files use frontmatter date/timestamp, op, summary, subjects/pages, and sources.",
        ],
    )
    import_log_records_parser.add_argument("folder", type=Path, help="Markdown folder containing log pages.")
    import_log_records_parser.add_argument("--journal", type=Path, default=None, help="Existing JSONL journal path. Defaults to <folder>.grasp/events.jsonl beside the Markdown folder.")
    import_log_records_parser.add_argument(
        "--markdown-exclude-dir",
        action="append",
        default=[],
        metavar="NAME",
        help="Directory basename to skip when scanning Markdown logs. Repeat for multiple names.",
    )

    log_records_parser = add_command_parser(
        subparsers,
        "log-records",
        help="Query first-class log entry records from SQLite events or a journal.",
        description=(
            "Read log_entry_import records from SQLite events when the selected store has them, "
            "falling back to a JSONL journal when it does not. "
            "This is the event-stream surface for log records; it does not read current page projection."
        ),
        returns=(
            "project, store, journal, event_source, total_records, matched_records, returned_records, offset, limit, order, filters, records[]. "
            "Records include subjects[], content_fingerprint, record_version, superseded_by, later_event_count, later_events[]"
        ),
        examples=[
            "grasp --project grasp-wiki log-records --journal wiki.grasp/events.jsonl --limit 5",
            "grasp --project grasp-wiki log-records --journal wiki.grasp/events.jsonl --query replay --op fix",
            "grasp --project grasp-wiki log-records --journal wiki.grasp/events.jsonl --subject grasp-v1-implemented",
        ],
        notes=[
            "Default order is newest first by timestamp, then journal order.",
            "Superseded record versions are hidden by default; use --include-superseded to inspect them.",
            "--query is whitespace-term AND search over heading, summary, op, source_path, subjects, and body lines.",
            "--subject matches extracted log subjects from wikilinks and mentioned Markdown paths.",
        ],
    )
    add_log_record_query_arguments(log_records_parser, include_positional_query=False)

    history_parser = add_command_parser(
        subparsers,
        "history",
        help="Search the log event stream for a page or topic.",
        description=(
            "Search log_entry_import records from SQLite events when available, falling back to JSONL journal records, "
            "by extracted subject without reading current page projection. "
            "This is the event-stream counterpart to read <page>."
        ),
        returns=(
            "project, store, journal, event_source, query, total_records, matched_records, returned_records, offset, limit, order, filters, records[]. "
            "Records include subjects[], content_fingerprint, record_version, superseded_by, later_event_count, later_events[]"
        ),
        examples=[
            "grasp --project grasp-wiki history grasp-v1-implemented --journal wiki.grasp/events.jsonl",
            "grasp --project grasp-wiki history grasp-backlog --journal wiki.grasp/events.jsonl --limit 10",
        ],
        notes=[
            "This command deliberately differs from read <page>: read returns current projection; history returns event-stream records.",
            "Matching uses extracted subjects from wikilinks and mentioned Markdown paths, not free text search.",
            "Superseded record versions are hidden by default; use --include-superseded to inspect them.",
            "Returned records include later events for the same subject so stale transitions are visible.",
        ],
    )
    history_parser.add_argument("query", help="Page/topic string to search for in log records.")
    add_log_record_query_arguments(history_parser, include_positional_query=True)

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

    export_markdown_parser = add_command_parser(
        subparsers,
        "export-markdown",
        help="Export a Markdown projection from a Markdown-backed project.",
        description=(
            "Project stored Markdown lines back to a folder. With --check, compare projection output to existing files "
            "without writing and return a non-zero exit status if the projection is not clean. "
            "Regeneration flags are explicit alpha overlays for generated navigation/log artifacts."
        ),
        returns=(
            "project, output, check, ok, file_count, checked_files, written_files, written_count, "
            "regenerated_files, log_event_source|null, log_event_count, projection_policy, "
            "changed_files, missing_files, extra_files"
        ),
        examples=[
            "grasp --project grasp-wiki export-markdown --output wiki --check",
            "grasp --project grasp-wiki --json export-markdown --output wiki --check",
            "grasp --project grasp-wiki export-markdown --output wiki --regenerate-index --regenerate-log --check",
            "grasp --project grasp-wiki export-markdown --output wiki --regenerate-log --journal /tmp/events.jsonl --check",
            "grasp --project grasp-wiki export-markdown --output wiki",
        ],
        notes=[
            "The projection authority is SQLite; Markdown is a git-tracked output for review, backup, publish, and recovery.",
            "This projection preserves stored lines and paths; formatting synthesis comes later.",
            "--check is the projection freshness gate for ship loops and file-back cutover.",
            "--regenerate-log replays SQLite log page events by default and appends latest record-per-file log_entry_import records.",
            "--journal switches --regenerate-log to a legacy JSONL event stream for ad hoc audits.",
        ],
    )
    export_markdown_parser.add_argument("--output", type=Path, required=True, help="Markdown projection output folder.")
    export_markdown_parser.add_argument("--check", action="store_true", help="Only compare projection output; do not write files.")
    export_markdown_parser.add_argument("--regenerate-index", action="store_true", help="Regenerate the primary navigation index page from the Markdown store catalog.")
    export_markdown_parser.add_argument("--regenerate-log", action="store_true", help="Regenerate the primary log page by replaying SQLite log page events and latest record-per-file records.")
    export_markdown_parser.add_argument("--journal", type=Path, default=None, help="Legacy JSONL event stream path for --regenerate-log ad hoc audits. Omit to use SQLite events.")

    append_section_parser = add_command_parser(
        subparsers,
        "append-section",
        help="Append a Markdown section through the alpha write path.",
        description=(
            "Append a section to a Markdown-backed page, update the SQLite materialized index, "
            "record a section_append SQLite event, optionally append the compatibility JSONL journal, "
            "and export the Markdown projection."
        ),
        returns=(
            "project, page, journal|null, journal_written, output, event_id, appended_lines[], appended_line_count, edge_count, projection"
        ),
        examples=[
            "grasp --project grasp-wiki append-section llm-wiki-infra-fast-path-plan --heading Updates --line '- note' --output wiki --journal wiki.grasp/events.jsonl",
            "grasp --project grasp-wiki --json append-section scratch --heading Updates --line '- first' --line '- second' --output wiki",
        ],
        notes=[
            "Alpha write surface: Markdown-backed projects only; rename is still out of scope.",
            "The default journal path is <output-folder-name>.grasp/events.jsonl beside the output folder.",
            "If projection export fails after the event write, the store is auto-reverted with event_revert; --json emits diagnostic.type=projection_export_rollback on stderr.",
        ],
    )
    append_section_parser.add_argument("title", help="Target page title or unique handle.")
    append_section_parser.add_argument("--heading", required=True, help="Section heading text without leading ##.")
    append_section_parser.add_argument("--line", action="append", default=[], help="Body line to append. Repeat for multiple lines.")
    append_section_parser.add_argument("--output", type=Path, required=True, help="Markdown projection output folder to update.")
    add_optional_write_journal_arguments(append_section_parser)

    append_log_parser = add_command_parser(
        subparsers,
        "append-log",
        help="Append a log entry through the alpha write path.",
        description=(
            "Append a dated log entry to a Markdown-backed log page, update the SQLite materialized index, "
            "record a log_append SQLite event, optionally append the compatibility JSONL journal, "
            "and export the Markdown projection."
        ),
        returns=(
            "project, page, journal|null, journal_written, output, event_id, timestamp, op, summary, appended_lines[], appended_line_count, edge_count, projection"
        ),
        examples=[
            "grasp --project grasp-wiki append-log --op implementation --summary 'append-section alpha' --line '- details' --output wiki",
            "grasp --project grasp-wiki --json append-log --timestamp '2026-06-26 01:00' --op test --summary 'smoke' --line '- ok' --output wiki",
        ],
        notes=[
            "Default target title is Log.",
            "Alpha write surface: Markdown-backed projects only; rename is still out of scope.",
            "If projection export fails after the event write, the store is auto-reverted with event_revert; --json emits diagnostic.type=projection_export_rollback on stderr.",
        ],
    )
    append_log_parser.add_argument("--title", default="Log", help="Target log page title or unique handle.")
    append_log_parser.add_argument("--timestamp", default=None, help="Timestamp text for the log heading. Defaults to local YYYY-MM-DD HH:MM.")
    append_log_parser.add_argument("--op", required=True, help="Operation label for the log heading.")
    append_log_parser.add_argument("--summary", required=True, help="Short summary for the log heading.")
    append_log_parser.add_argument("--line", action="append", default=[], help="Body line to append. Repeat for multiple lines.")
    append_log_parser.add_argument("--output", type=Path, required=True, help="Markdown projection output folder to update.")
    add_optional_write_journal_arguments(append_log_parser)

    write_page_parser = add_command_parser(
        subparsers,
        "write-page",
        help="Create or replace a Markdown page through the alpha write path.",
        description=(
            "Create a new Markdown-backed page with --create, or replace all stored lines of an existing page. "
            "The command records a page_create/page_update SQLite event, updates the SQLite materialized index, "
            "optionally appends the compatibility JSONL journal, and exports the Markdown projection."
        ),
        returns=(
            "project, page, journal|null, journal_written, output, event_id, event_type, source_path, previous_lines[], lines[], "
            "previous_line_count, line_count, edge_count, projection"
        ),
        examples=[
            "grasp --project grasp-wiki write-page 'New page' --create --path new-page.md --from-file /tmp/new-page.md --output wiki",
            "grasp --project grasp-wiki write-page scratch --from-file /tmp/scratch.md --output wiki",
            "grasp --project grasp-wiki --json write-page scratch --line '# scratch' --line '- updated' --output wiki",
        ],
        notes=[
            "Alpha write surface: Markdown-backed projects and unique handles only.",
            "--path is required with --create and deliberately ignored for existing-page updates.",
            "Rename and source-path changes for existing pages are handled by rename-page.",
            "If projection export fails after the event write, the store is auto-reverted with event_revert; --json emits diagnostic.type=projection_export_rollback on stderr.",
        ],
    )
    write_page_parser.add_argument("title", help="Target page title or unique handle.")
    input_group = write_page_parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--from-file", type=Path, default=None, help="Read replacement Markdown page body from this file.")
    input_group.add_argument("--line", action="append", default=None, help="Replacement body line. Repeat for multiple lines.")
    write_page_parser.add_argument("--create", action="store_true", help="Create a new Markdown-backed page instead of replacing an existing page.")
    write_page_parser.add_argument("--path", dest="source_path", default=None, help="New Markdown projection path for --create, relative to --output and ending in .md.")
    write_page_parser.add_argument("--message", default="", help="Optional update message stored in the journal payload.")
    write_page_parser.add_argument("--output", type=Path, required=True, help="Markdown projection output folder to update.")
    add_optional_write_journal_arguments(write_page_parser)

    rename_page_parser = add_command_parser(
        subparsers,
        "rename-page",
        aliases=["rename"],
        help="Rename a Markdown page identity through the alpha write path.",
        description=(
            "Rename an existing Markdown-backed page while preserving page id. "
            "Incoming link surface text is not rewritten; the old title becomes an alias handle. "
            "Optionally move the Markdown projection source path."
        ),
        returns=(
            "project, page, journal|null, journal_written, output, event_id, event_type, previous_title, title, previous_source_path, "
            "source_path, previous_lines[], lines[], aliases[], heading_updated, edge_count, projection"
        ),
        examples=[
            "grasp --project grasp-wiki rename-page old-title 'New Title' --new-path decisions/new-title.md --output wiki",
            "grasp --project grasp-wiki --json rename --target page-id <page-id> 'New Title' --output wiki",
        ],
        notes=[
            "Alpha write surface: Markdown-backed projects only.",
            "The first H1 is updated only when it currently matches the old title.",
            "References like [[old-title]] are preserved as text and resolve through the old-title alias.",
            "If projection export fails after the event write, the store is auto-reverted with event_revert; --json emits diagnostic.type=projection_export_rollback on stderr.",
        ],
    )
    rename_page_parser.add_argument("target", help="Target page handle by default, or page id/path with --target.")
    rename_page_parser.add_argument("new_title", help="New page title.")
    rename_page_parser.add_argument("--target", dest="target_kind", choices=["handle", "page-id", "path"], default="handle", help="How to interpret the target argument.")
    rename_page_parser.add_argument("--new-path", default=None, help="Optional new Markdown projection path, relative to --output and ending in .md.")
    rename_page_parser.add_argument("--no-heading-update", action="store_true", help="Do not update a matching first H1 line.")
    rename_page_parser.add_argument("--message", default="", help="Optional rename message stored in the journal payload.")
    rename_page_parser.add_argument("--output", type=Path, required=True, help="Markdown projection output folder to update.")
    add_optional_write_journal_arguments(rename_page_parser)

    write_status_parser = add_command_parser(
        subparsers,
        "write-status",
        help="Report alpha write journal and projection status.",
        description=(
            "Check whether the Markdown projection is clean for a Markdown-backed project and summarize "
            "the journal used by the alpha write path. When a journal is available, also compare the "
            "primary log page against the journal-regenerated projection so direct Markdown log edits "
            "can be reported as stale. With --strict, return exit status 1 when any write guard fails; "
            "a clean journal-regenerated log projection satisfies the log-page guard even if stored lines differ. "
            "With --no-journal, strict mode skips JSONL guards and checks the SQLite-authority projection plus "
            "the SQLite events-derived semantic log projection when a log page exists."
        ),
        returns=(
            "project, output, journal|null, journal_required, journal_exists, journal_event_count, last_event|null, "
            "journal_project_event_count, sqlite_event_count, sqlite_last_event|null, "
            "event_streams_match, event_stream_mismatch|null, "
            "projection, journal_log_record_count, journal_log_stale, journal_log_changed_files, "
            "journal_log_projection|null, journal_log_error|null, semantic_log_stale, semantic_log_changed_files, "
            "semantic_log_projection|null, semantic_log_error|null, strict_ok, strict_failures[]"
        ),
        examples=[
            "grasp --project grasp-wiki write-status --output wiki",
            "grasp --project grasp-wiki write-status --output wiki --journal wiki.grasp/events.jsonl --strict",
            "grasp --project grasp-wiki --json write-status --output wiki --journal wiki.grasp/events.jsonl",
        ],
        notes=[
            "This is an alpha recovery surface for Markdown-backed write dogfood.",
            "projection.ok=false means export-markdown --check would fail.",
            "journal_log_stale=true means the log page no longer matches the replayed journal log projection.",
            "semantic_log_stale=true means the log page no longer matches the SQLite events-derived log projection.",
            "event_streams_match=false means selected-project SQLite events are not an ordered subsequence of the legacy JSONL journal.",
            "--strict is intended for ship loops and CI-style gates.",
        ],
    )
    write_status_parser.add_argument("--output", type=Path, required=True, help="Markdown projection output folder to check.")
    add_optional_write_journal_arguments(
        write_status_parser,
        no_journal_help="Skip JSONL journal checks; --strict validates only the SQLite-authority Markdown projection.",
    )
    write_status_parser.add_argument("--strict", action="store_true", help="Exit 1 if projection, journal, or journal-derived log guards are not clean.")

    revert_event_parser = add_command_parser(
        subparsers,
        "revert-event",
        help="Revert a supported alpha write event.",
        description=(
            "Revert a supported alpha write event when the current page still matches the target event. "
            "SQLite events are searched first, then the legacy JSONL journal. SQLite-sourced reverts insert "
            "event_revert in the same transaction as the state change, then optionally append the legacy JSONL event "
            "and export projection. With --dry-run, run the same safety checks inside a rolled-back transaction and "
            "report whether the event is currently revertible without writing state, journal, or projection files. "
            "With --include-dependents, first revert later active same-page SQLite events that block the target."
        ),
        returns="project, journal|null, journal_written, output, dry_run, revertible, event_id|null, event_ids[]?, target_event_id, target_event_type, target_event_source, included_dependent_event_ids[]?, reverted_events[]?, page, removed_lines[]|restored_lines[], removed_line_count|restored_line_count, projection|null, reason?",
        examples=[
            "grasp --project grasp-wiki revert-event <event-id> --output wiki",
            "grasp --project grasp-wiki --json revert-event <event-id> --output wiki --no-journal --dry-run",
            "grasp --project grasp-wiki --json revert-event <event-id> --output wiki --no-journal --include-dependents",
            "grasp --project grasp-wiki --json revert-event <event-id> --output wiki --journal wiki.grasp/events.jsonl",
        ],
        notes=[
            "page_create requires current lines/title/path/aliases to match the created page before deletion.",
            "section_append/log_append require their inserted lines to remain at page tail.",
            "page_update/page_rename require the current lines and path/title state to match the target event.",
            "--dry-run is the planning surface for dependency-aware/general revert work: it never appends event_revert.",
            "--include-dependents is SQLite-only and reverts later active same-page events in reverse event order before the target.",
        ],
    )
    revert_event_parser.add_argument("event_id", help="Write event id to revert.")
    revert_event_parser.add_argument("--output", type=Path, required=True, help="Markdown projection output folder to update.")
    add_optional_write_journal_arguments(revert_event_parser)
    revert_event_parser.add_argument("--reason", default="", help="Optional reason stored in the revert event payload.")
    revert_event_parser.add_argument("--dry-run", action="store_true", help="Check whether the event is currently revertible without changing store, journal, or projection files.")
    revert_event_parser.add_argument("--include-dependents", action="store_true", help="Also revert later active same-page SQLite events that must be undone before the target.")

    revert_events_parser = add_command_parser(
        subparsers,
        "revert-events",
        help="Revert multiple supported SQLite alpha write events.",
        description=(
            "Revert explicitly selected SQLite alpha write events as one recovery operation. "
            "Targets must belong to the selected project, be active, and be supported reversible event types. "
            "The command applies reverts in reverse SQLite event_sequence order inside one transaction, then "
            "optionally appends compatibility JSONL event_revert records and exports projection. "
            "With --dry-run, run the same safety checks inside a rolled-back transaction."
        ),
        returns=(
            "project, journal|null, journal_written, output, dry_run, revertible, event_ids[], "
            "requested_event_ids[], target_event_ids[], revert_order_event_ids[], reverted_events[], "
            "projection|null, reason?"
        ),
        examples=[
            "grasp --project grasp-wiki revert-events <event-id-a> <event-id-b> --output wiki",
            "grasp --project grasp-wiki --json revert-events <event-id-a> <event-id-b> --output wiki --no-journal --dry-run",
        ],
        notes=[
            "SQLite-only: this command does not fall back to a legacy JSONL journal for target lookup.",
            "Use this for an explicit multi-page rollback plan; use revert-event --include-dependents for automatic same-page dependency rollback.",
            "The reverse event_sequence order is required so later page state changes are undone before earlier ones.",
        ],
    )
    revert_events_parser.add_argument("event_ids", nargs="+", help="SQLite write event ids to revert as one operation.")
    revert_events_parser.add_argument("--output", type=Path, required=True, help="Markdown projection output folder to update.")
    add_optional_write_journal_arguments(revert_events_parser)
    revert_events_parser.add_argument("--reason", default="", help="Optional reason stored in each revert event payload.")
    revert_events_parser.add_argument("--dry-run", action="store_true", help="Check whether all events are currently revertible without changing store, journal, or projection files.")

    revert_plan_parser = add_command_parser(
        subparsers,
        "revert-plan",
        help="Plan a rollback event set from SQLite history.",
        description=(
            "Infer a read-only rollback plan from selected-project SQLite events. "
            "The default scope is log-batch: find the log_append entry that closes the work unit containing "
            "the anchor event, then return active reversible events after the previous log_append through that "
            "closing log_append. Use --scope subject-log when the log-batch boundary is too broad but its closing "
            "log entry names the intended pages with wikilinks or Markdown paths. Use --scope log-page-subjects "
            "when legacy/direct Markdown history updated a log page with write-page instead of log_append. "
            "Use --scope content-subjects when page content changes share wikilinks or Markdown path subjects "
            "but no explicit log/session/window boundary describes the work unit. "
            "Use --scope same-page-dependents when no log-batch boundary exists and the "
            "anchor is blocked by later active events on the same page. Use --scope event-window with --before/--after "
            "when the intended multi-page unit is a small contiguous SQLite event_sequence window and no semantic "
            "boundary is available. Use --scope time-burst with --max-gap-seconds when the intended unit is a "
            "small burst of adjacent writes close in time and no log boundary exists. Use --scope session when write "
            "events carry a non-empty --session-id / GRASP_SESSION_ID work-unit marker. The result is intended to feed "
            "revert-events; it does not mutate store, journal, or projection files."
        ),
        returns=(
            "project, scope, anchor_event_id, complete, previous_log_event|null, closing_log_event|null, "
            "candidate_event_ids[], dependent_event_ids[]?, subject_log_subjects[]?, log_page_subjects[]?, "
            "content_subjects[]?, window_before?, window_after?, max_gap_seconds?, session_id?, session_actor?, boundary_events[]?, "
            "revert_order_event_ids[], candidate_events[], excluded_events[], revertible, reverted_events[], "
            "reason?, suggested_revert_events_args[]?"
        ),
        examples=[
            "grasp --project grasp-wiki revert-plan <event-id> --scope log-batch",
            "grasp --project grasp-wiki revert-plan <event-id> --scope subject-log",
            "grasp --project grasp-wiki revert-plan <event-id> --scope log-page-subjects",
            "grasp --project grasp-wiki revert-plan <event-id> --scope content-subjects",
            "grasp --project grasp-wiki revert-plan <event-id> --scope same-page-dependents",
            "grasp --project grasp-wiki revert-plan <event-id> --scope event-window --after 2",
            "grasp --project grasp-wiki revert-plan <event-id> --scope time-burst --max-gap-seconds 120",
            "grasp --project grasp-wiki revert-plan <event-id> --scope session",
            "grasp --project grasp-wiki --json revert-plan <event-id> --scope log-batch --output wiki",
        ],
        notes=[
            "Read-only: this command never appends event_revert and never exports Markdown.",
            "log-batch is for file-back style workflows that append one log entry after a group of page writes.",
            "subject-log filters a log-batch to page events named by the closing log entry subjects, and includes the closing log_append.",
            "log-page-subjects handles legacy/direct Markdown history where the closing log entry is inside a log page_update.",
            "content-subjects matches page events by subjects extracted from changed page lines; it is semantic but intentionally heuristic.",
            "same-page-dependents mirrors revert-event --include-dependents planning without mutating.",
            "event-window is explicit sequence planning: pass --before and/or --after to bound the event_sequence window.",
            "time-burst is explicit temporal planning: pass --max-gap-seconds to bound adjacent event gaps; it does not cross log_append boundaries.",
            "session is explicit metadata planning: it requires a non-empty session_id on the anchor event.",
            "Use the returned candidate_event_ids with revert-events, then run revert-events --dry-run before mutating.",
        ],
    )
    revert_plan_parser.add_argument("event_id", help="Anchor SQLite event id inside the work unit to plan.")
    revert_plan_parser.add_argument("--scope", choices=["log-batch", "subject-log", "log-page-subjects", "content-subjects", "same-page-dependents", "event-window", "time-burst", "session"], default="log-batch", help="Planning scope to infer around the anchor event.")
    revert_plan_parser.add_argument("--before", type=int, default=0, help="For --scope event-window, include this many SQLite events before the anchor.")
    revert_plan_parser.add_argument("--after", type=int, default=0, help="For --scope event-window, include this many SQLite events after the anchor.")
    revert_plan_parser.add_argument("--max-gap-seconds", type=float, default=None, help="For --scope time-burst, include adjacent SQLite events while created_at gaps are at most this many seconds.")
    revert_plan_parser.add_argument("--output", type=Path, help="Optional projection output folder to include in suggested revert-events args.")

    replay_journal_parser = add_command_parser(
        subparsers,
        "replay-journal",
        help="Replay an alpha write journal into a Markdown projection.",
        description=(
            "Replay page_create, page_update, page_rename, section_append, log_append, log_entry_import, and event_revert records from a JSONL journal "
            "to reconstruct a Markdown projection without reading SQLite."
        ),
        returns="project, journal, output, check, ok, event_count, applied_event_count, file_count, changed_files, missing_files, extra_files, written_files",
        examples=[
            "grasp replay-journal --journal wiki.grasp/events.jsonl --output wiki --project grasp-wiki --check",
            "grasp --json replay-journal --journal wiki.grasp/events.jsonl --output /tmp/wiki-replay --project grasp-wiki",
        ],
        notes=[
            "If the journal contains multiple projects, pass --project to select one.",
            "Replay is strict: reverted lines must be the current page tail in replay order.",
        ],
    )
    replay_journal_parser.add_argument("--journal", type=Path, required=True, help="JSONL journal path to replay.")
    replay_journal_parser.add_argument("--output", type=Path, required=True, help="Markdown projection output folder.")
    replay_journal_parser.add_argument("--check", action="store_true", help="Only compare replay output; do not write files.")

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


def add_log_record_query_arguments(command_parser: argparse.ArgumentParser, *, include_positional_query: bool) -> None:
    command_parser.add_argument(
        "--journal",
        type=Path,
        required=True,
        help="JSONL journal path containing log_entry_import records, used as a fallback when SQLite events are unavailable.",
    )
    if not include_positional_query:
        command_parser.add_argument("--query", default=None, help="Text query matched against record id, source, timestamp, op, summary, heading, and body lines.")
    command_parser.add_argument("--source-path", default=None, help="Only return records imported from this Markdown source path.")
    command_parser.add_argument("--subject", action="append", default=[], help="Only return records whose extracted subjects match this page/topic. Repeat for multiple subjects.")
    command_parser.add_argument("--op", action="append", default=[], help="Only return records with this op. Repeat for multiple ops.")
    command_parser.add_argument("--record-id", default=None, help="Only return a specific log record id.")
    command_parser.add_argument("--since", default=None, help="Only return records with timestamp >= this value. Lexical YYYY-MM-DD HH:MM comparison.")
    command_parser.add_argument("--until", default=None, help="Only return records with timestamp <= this value. Lexical YYYY-MM-DD HH:MM comparison.")
    command_parser.add_argument("--limit", type=int, default=20, help="Maximum records to return.")
    command_parser.add_argument("--offset", type=int, default=0, help="Number of matching records to skip after ordering.")
    command_parser.add_argument("--oldest-first", action="store_true", help="Return oldest matching records first instead of newest first.")
    command_parser.add_argument("--body-lines", type=int, default=3, help="Body lines to show in text output. JSON always returns full body_lines.")
    command_parser.add_argument("--later-limit", type=int, default=5, help="Maximum later same-subject event summaries to attach per returned record. Use 0 to return counts only.")
    command_parser.add_argument("--include-superseded", action="store_true", help="Include older versions of the same log record_id. Hidden by default.")


def add_optional_write_journal_arguments(
    command_parser: argparse.ArgumentParser,
    *,
    no_journal_help: str = "Do not append a compatibility JSONL journal record; SQLite events and Markdown projection are still updated.",
) -> None:
    journal_group = command_parser.add_mutually_exclusive_group()
    journal_group.add_argument(
        "--journal",
        type=Path,
        default=None,
        help="JSONL compatibility journal path. Defaults to <output>.grasp/events.jsonl beside the output folder.",
    )
    journal_group.add_argument("--no-journal", action="store_true", help=no_journal_help)


def default_journal_path(folder: Path) -> Path:
    return folder.parent / f"{folder.name}.grasp" / "events.jsonl"


def journal_path_for_output(output: Path, journal_path: Path | None) -> Path:
    return journal_path or default_journal_path(output)


def optional_journal_path_for_output(args: argparse.Namespace) -> Path | None:
    if getattr(args, "no_journal", False):
        return None
    return journal_path_for_output(args.output, args.journal)


def adopt_markdown(
    folder: Path,
    store_path: Path,
    *,
    project: str | None,
    journal_path: Path | None,
    replace_journal: bool,
    exclude_dirs: tuple[str, ...],
    actor: str = "",
    session_id: str = "",
) -> dict[str, Any]:
    folder = Path(folder)
    journal = journal_path or default_journal_path(folder)
    if journal.exists() and not replace_journal:
        raise ValueError(f"journal already exists: {journal}; use --replace-journal to overwrite")

    mirror = MarkdownMirror.from_folder(folder, exclude_dirs=exclude_dirs)
    stats = import_markdown_folder_to_sqlite(
        folder,
        store_path,
        project_name=project,
        exclude_dirs=exclude_dirs,
    )
    adopted_project = str(stats["project"])
    page_events = [
        make_journal_event(
            "page_create",
            project=adopted_project,
            payload=adopt_markdown_record_payload(record),
        )
        for record in mirror.records
    ]
    log_entry_events = markdown_log_entry_import_events(mirror.records, project=adopted_project)
    events = [*page_events, *log_entry_events]
    sqlite_event_summary = {"imported": 0, "skipped": 0}
    if events:
        event_store = SQLiteStore(store_path, project=adopted_project, for_write=True)
        try:
            sqlite_event_summary = event_store.import_journal_events(
                events,
                project=adopted_project,
                actor=actor,
                session_id=session_id,
            )
        finally:
            event_store.close()
    if replace_journal:
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text("", encoding="utf-8")
    for event in events:
        append_journal_event(journal, event)

    result = dict(stats)
    result.update(
        {
            "journal": str(journal),
            "journal_events": len(events),
            "sqlite_events_inserted": sqlite_event_summary["imported"],
            "sqlite_events_skipped": sqlite_event_summary["skipped"],
            "adopted_pages": len(page_events),
            "log_entry_records": len(log_entry_events),
        }
    )
    return result


def adopt_markdown_record_payload(record: Any) -> dict[str, Any]:
    return {
        "source_path": record.relative_path.as_posix(),
        "page_id": record.page.id,
        "title": record.page.title,
        "aliases": record.aliases,
        "graph_role": record.graph_role,
        "source_hash": record.source_hash,
        "lines": [journal_line_payload(line) for line in record.page.lines],
    }


def journal_line_payload(line: Any) -> dict[str, Any]:
    return {
        "line_id": line.line_id,
        "line_index": line.index,
        "text": line.text,
        "created": line.created,
        "updated": line.updated,
        "user_id": line.user_id,
    }


def markdown_log_entry_import_events(records: tuple[Any, ...], *, project: str) -> list[dict[str, Any]]:
    events = []
    for payload in markdown_log_entry_payloads(records):
        events.append(
            make_journal_event(
                "log_entry_import",
                project=project,
                event_id=log_entry_import_event_id(payload),
                payload=payload,
            )
        )
    return events


def log_entry_import_event_id(payload: dict[str, Any]) -> str:
    fingerprint = str(payload.get("content_fingerprint") or "")
    if fingerprint:
        return f"log-entry-{payload['record_id']}-{fingerprint[:12]}"
    return f"log-entry-{payload['record_id']}"


def markdown_log_entry_payloads(records: tuple[Any, ...]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for record in records:
        if record.graph_role != "log":
            continue
        log_lines = list(record.page.lines)
        frontmatter_values = parse_frontmatter_values([line.text for line in log_lines])
        if is_log_entry_file(frontmatter_values):
            payload = markdown_log_entry_file_payload(record, frontmatter_values)
            if payload is not None:
                payloads.append(payload)
            continue
        payloads.extend(markdown_log_section_payloads(record, log_lines))
    return payloads


def markdown_log_section_payloads(record: Any, log_lines: list[Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for index, line in enumerate(log_lines):
        match = LOG_ENTRY_HEADING_RE.match(line.text)
        if match is None:
            continue
        body = []
        for body_line in log_lines[index + 1:]:
            if LOG_ENTRY_HEADING_RE.match(body_line.text):
                break
            body.append(body_line)
        while body and not body[-1].text.strip():
            body.pop()
        timestamp = match.group("timestamp").strip()
        op = match.group("op").strip()
        summary = match.group("summary").strip()
        heuristic_subjects = log_entry_subjects_from_lines([line, *body])
        payloads.append(
            build_log_entry_payload(
                record,
                timestamp=timestamp,
                op=op,
                summary=summary,
                heading=line.text,
                heading_line=line,
                heading_line_index=line.index,
                body=body,
                record_format="section",
                record_identity="section_content",
                explicit_subjects=[],
                heuristic_subjects=heuristic_subjects,
                sources=[],
            )
        )
    return payloads


def markdown_log_entry_file_payload(
    record: Any,
    frontmatter_values: dict[str, list[tuple[str, int]]],
) -> dict[str, Any] | None:
    timestamp = first_log_frontmatter_value(frontmatter_values, ("date", "timestamp", "created_at", "created"))
    if not timestamp:
        return None
    op = first_log_frontmatter_value(frontmatter_values, ("op", "operation")) or "log-entry"
    summary = first_log_frontmatter_value(frontmatter_values, ("summary", "title")) or record.page.title
    body = log_entry_file_body_lines(record)
    explicit_subjects = log_entry_frontmatter_subjects(frontmatter_values)
    heuristic_subjects = log_entry_subjects_from_lines(body)
    sources = log_entry_frontmatter_values(frontmatter_values, ("sources", "source"))
    return build_log_entry_payload(
        record,
        timestamp=timestamp,
        op=op,
        summary=summary,
        heading=f"## [{timestamp}] {op} | {summary}",
        heading_line=None,
        heading_line_index=-1,
        body=body,
        record_format="file",
        record_identity="file_page",
        explicit_subjects=explicit_subjects,
        heuristic_subjects=heuristic_subjects,
        sources=sources,
    )


def build_log_entry_payload(
    record: Any,
    *,
    timestamp: str,
    op: str,
    summary: str,
    heading: str,
    heading_line: Any | None,
    heading_line_index: int,
    body: list[Any],
    record_format: str,
    record_identity: str,
    explicit_subjects: list[str],
    heuristic_subjects: list[str],
    sources: list[str],
) -> dict[str, Any]:
    body_text = "\n".join(body_line.text for body_line in body)
    subjects = explicit_subjects or heuristic_subjects
    record_key = "\n".join(
        [
            record.relative_path.as_posix(),
            timestamp,
            op,
            summary,
            body_text,
        ]
    )
    content_record_id = hashlib.sha1(record_key.encode("utf-8")).hexdigest()[:24]
    if record_identity == "file_page":
        identity_key = "\n".join(["log-file", record.page.id])
        record_id = hashlib.sha1(identity_key.encode("utf-8")).hexdigest()[:24]
    else:
        record_id = content_record_id
    payload = {
        "record_id": record_id,
        "record_identity": record_identity,
        "record_format": record_format,
        "source_path": record.relative_path.as_posix(),
        "page_id": record.page.id,
        "heading": heading,
        "heading_line": journal_line_payload(heading_line) if heading_line is not None else None,
        "heading_line_index": heading_line_index,
        "timestamp": timestamp,
        "op": op,
        "summary": summary,
        "subjects": subjects,
        "explicit_subjects": explicit_subjects,
        "heuristic_subjects": heuristic_subjects,
        "subject_source": "frontmatter" if explicit_subjects else "heuristic",
        "sources": sources,
        "body_lines": [journal_line_payload(body_line) for body_line in body],
        "body_line_count": len(body),
    }
    if content_record_id != record_id:
        payload["legacy_record_id"] = content_record_id
    payload["content_fingerprint"] = log_entry_content_fingerprint(payload)
    return payload


def log_entry_content_fingerprint(payload: dict[str, Any]) -> str:
    body_lines = [
        line
        for line in payload.get("body_lines") or []
        if isinstance(line, dict)
    ]
    body_text = "\n".join(str(line.get("text", "")) for line in body_lines)
    record_format = str(payload.get("record_format") or "section")
    record_identity = str(payload.get("record_identity") or ("file_page" if record_format == "file" else "section_content"))
    subjects = [str(subject) for subject in payload.get("subjects") or []]
    if not subjects:
        subjects = log_entry_subjects_from_lines(
            [
                {"text": str(payload.get("heading") or "")},
                *body_lines,
            ]
        )
    explicit_subjects = [str(subject) for subject in payload.get("explicit_subjects") or []]
    heuristic_subjects = [str(subject) for subject in payload.get("heuristic_subjects") or []]
    if not explicit_subjects and not heuristic_subjects and subjects:
        heuristic_subjects = list(subjects)
    fingerprint_payload = {
        "record_identity": record_identity,
        "record_format": record_format,
        "source_path": str(payload.get("source_path") or ""),
        "page_id": str(payload.get("page_id") or ""),
        "timestamp": str(payload.get("timestamp") or ""),
        "op": str(payload.get("op") or ""),
        "summary": str(payload.get("summary") or ""),
        "heading": str(payload.get("heading") or ""),
        "subjects": subjects,
        "explicit_subjects": explicit_subjects,
        "heuristic_subjects": heuristic_subjects,
        "subject_source": str(payload.get("subject_source") or ("frontmatter" if explicit_subjects else "heuristic")),
        "sources": [str(source) for source in payload.get("sources") or []],
        "body_text": body_text,
    }
    stable_json = json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(stable_json.encode("utf-8")).hexdigest()[:24]


def is_log_entry_file(frontmatter_values: dict[str, list[tuple[str, int]]]) -> bool:
    candidates = []
    for key in ("type", "role", "graph_role", "layer"):
        candidates.extend(value for value, _ in frontmatter_values.get(key, []))
    return any(normalize_log_frontmatter_token(value) == "log_entry" for value in candidates)


def normalize_log_frontmatter_token(value: str) -> str:
    return value.strip().casefold().replace("-", "_")


def first_log_frontmatter_value(
    frontmatter_values: dict[str, list[tuple[str, int]]],
    keys: tuple[str, ...],
) -> str | None:
    for value in log_entry_frontmatter_values(frontmatter_values, keys):
        return value
    return None


def log_entry_frontmatter_values(
    frontmatter_values: dict[str, list[tuple[str, int]]],
    keys: tuple[str, ...],
) -> list[str]:
    values: list[str] = []
    for key in keys:
        values.extend(value for value, _ in frontmatter_values.get(key, []))
    return list(dict.fromkeys(value for value in values if value))


def log_entry_frontmatter_subjects(frontmatter_values: dict[str, list[tuple[str, int]]]) -> list[str]:
    subjects: list[str] = []
    seen: set[str] = set()
    for raw_subject in log_entry_frontmatter_values(frontmatter_values, ("subjects", "subject", "pages", "page")):
        add_log_entry_subject(subjects, seen, raw_subject)
    return subjects


def log_entry_file_body_lines(record: Any) -> list[Any]:
    text_lines = [line.text for line in record.page.lines]
    frontmatter_lines, _ = split_markdown_frontmatter(text_lines)
    body = list(record.page.lines[len(frontmatter_lines):])
    while body and not body[0].text.strip():
        body.pop(0)
    if body and is_log_entry_file_title_line(body[0], record.page.title):
        body.pop(0)
    while body and not body[0].text.strip():
        body.pop(0)
    while body and not body[-1].text.strip():
        body.pop()
    return body


def is_log_entry_file_title_line(line: Any, title: str) -> bool:
    stripped = str(line.text).strip()
    return stripped.startswith("# ") and normalize_title(stripped[2:].strip()) == normalize_title(title)


def log_entry_subjects_from_lines(lines: list[Any]) -> list[str]:
    subjects: list[str] = []
    seen: set[str] = set()
    in_code_fence = False
    for line in lines:
        text = str(getattr(line, "text", line.get("text", "") if isinstance(line, dict) else line))
        links, in_code_fence = log_entry_markdown_wikilinks(text, in_code_fence=in_code_fence)
        for link in links:
            add_log_entry_subject(subjects, seen, link)
        for match in LOG_ENTRY_MARKDOWN_PATH_RE.finditer(text):
            path_subject = log_entry_subject_from_markdown_path(match.group("path"))
            if path_subject:
                add_log_entry_subject(subjects, seen, path_subject)
    return subjects


def log_entry_markdown_wikilinks(text: str, *, in_code_fence: bool) -> tuple[list[str], bool]:
    stripped = text.lstrip()
    if stripped.startswith("```") or stripped.startswith("~~~"):
        return [], not in_code_fence
    if in_code_fence:
        return [], in_code_fence

    links: list[str] = []
    index = 0
    while index < len(text):
        start = text.find("[[", index)
        if start == -1:
            break
        close = text.find("]]", start + 2)
        if close == -1:
            break
        if text[:start].count("`") % 2 == 0:
            target = markdown_wikilink_target(text[start + 2 : close])
            if target:
                links.append(target)
        index = close + 2
    return links, in_code_fence


def add_log_entry_subject(subjects: list[str], seen: set[str], raw_subject: str) -> None:
    subject = log_entry_subject_display(raw_subject)
    if not subject:
        return
    subject_norm = normalize_title(subject)
    if subject_norm in seen:
        return
    seen.add(subject_norm)
    subjects.append(subject)


def log_entry_subject_display(raw_subject: str) -> str | None:
    stripped = raw_subject.strip().strip("`'\"")
    if not stripped:
        return None
    if stripped.startswith("[[") and stripped.endswith("]]"):
        stripped = stripped[2:-2]
    target = markdown_wikilink_target(stripped)
    if target:
        return target
    if stripped.endswith(".md"):
        return log_entry_subject_from_markdown_path(stripped)
    return stripped


def log_entry_subject_from_markdown_path(raw_path: str) -> str | None:
    path = raw_path.strip().strip("`'\"")
    if not path.endswith(".md"):
        return None
    return Path(path).stem or None


def run_import_log_records(store: SQLiteStore, args: argparse.Namespace) -> dict[str, Any]:
    journal = journal_path_for_output(args.folder, args.journal)
    if not journal.exists():
        raise ValueError(f"journal does not exist: {journal}; run adopt-markdown first")
    project = store._require_project()
    events = read_journal_events(journal)
    existing_records = latest_log_entry_payloads_by_identity_key(events, project=project)
    mirror = MarkdownMirror.from_folder(
        args.folder,
        exclude_dirs=tuple(args.markdown_exclude_dir),
    )
    candidate_events = markdown_log_entry_import_events(mirror.records, project=project)
    imported_record_ids = []
    updated_record_ids = []
    skipped_record_ids = []
    log_pages = {
        record.relative_path.as_posix()
        for record in mirror.records
        if record.graph_role == "log"
    }
    events_to_import = []
    for event in candidate_events:
        payload = event.get("payload") or {}
        record_id = str(payload.get("record_id") or "")
        existing_payload = first_existing_log_entry_payload(payload, existing_records)
        if existing_payload is not None and log_entry_payload_content_fingerprint(existing_payload) == log_entry_payload_content_fingerprint(payload):
            skipped_record_ids.append(record_id)
            continue
        if existing_payload is not None:
            superseded_record_id = str(existing_payload.get("record_id") or "")
            if superseded_record_id and superseded_record_id != record_id:
                payload["supersedes_record_ids"] = [superseded_record_id]
            updated_record_ids.append(record_id)
        else:
            imported_record_ids.append(record_id)
        events_to_import.append(event)
        for key in log_entry_payload_identity_keys(payload):
            existing_records[key] = payload
    sqlite_events_inserted = 0
    if events_to_import:
        with store.write_transaction():
            for event in events_to_import:
                if insert_store_event(store.connection, event, if_exists="skip", **event_metadata(args)):
                    sqlite_events_inserted += 1
        for event in events_to_import:
            append_journal_event(journal, event)
    return {
        "project": project,
        "folder": str(args.folder),
        "journal": str(journal),
        "sqlite_events_inserted": sqlite_events_inserted,
        "log_pages": sorted(log_pages),
        "log_page_count": len(log_pages),
        "scanned_records": len(candidate_events),
        "imported_records": len(imported_record_ids) + len(updated_record_ids),
        "new_records": len(imported_record_ids),
        "updated_records": len(updated_record_ids),
        "skipped_records": len(skipped_record_ids),
        "record_ids": [*imported_record_ids, *updated_record_ids],
        "new_record_ids": imported_record_ids,
        "updated_record_ids": updated_record_ids,
        "skipped_record_ids": skipped_record_ids,
    }


def latest_log_entry_payloads_by_identity_key(
    events: list[dict[str, Any]],
    *,
    project: str,
) -> dict[str, dict[str, Any]]:
    existing: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("project") != project or event.get("event_type") != "log_entry_import":
            continue
        payload = event.get("payload") or {}
        for key in log_entry_payload_identity_keys(payload):
            existing[key] = payload
    return existing


def first_existing_log_entry_payload(
    payload: dict[str, Any],
    existing_records: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    for key in log_entry_payload_identity_keys(payload):
        if key in existing_records:
            return existing_records[key]
    return None


def log_entry_payload_identity_keys(payload: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for key in ("record_id", "legacy_record_id"):
        value = str(payload.get(key) or "")
        if value:
            keys.append(value)
    for value in payload.get("supersedes_record_ids") or []:
        if value:
            keys.append(str(value))
    return list(dict.fromkeys(keys))


def log_entry_payload_content_fingerprint(payload: dict[str, Any]) -> str:
    return str(payload.get("content_fingerprint") or log_entry_content_fingerprint(payload))


def run_log_records(args: argparse.Namespace, store: SQLiteStore | None = None) -> dict[str, Any]:
    events, selected_project, event_source, sqlite_event_count = log_record_source_events(args, store)
    query = getattr(args, "query", None)
    text_query = query if args.command == "log-records" else None
    subject_filters = list(args.subject or [])
    if args.command == "history":
        subject_filters.insert(0, query)
    records = [
        log_entry_record_from_event(event, journal_index=log_record_event_order_index(event, index))
        for index, event in enumerate(events)
        if (selected_project is None or event["project"] == selected_project)
        and event["event_type"] == "log_entry_import"
    ]
    versioned_records = annotate_log_entry_record_versions(records)
    visible_records = versioned_records if args.include_superseded else [
        record
        for record in versioned_records
        if record.get("superseded_by") is None
    ]
    ordered_records = sorted(
        visible_records,
        key=lambda record: (record["timestamp"], record["journal_index"]),
        reverse=not args.oldest_first,
    )
    filters = {
        "query": text_query,
        "subject": subject_filters,
        "source_path": args.source_path,
        "op": list(args.op or []),
        "record_id": args.record_id,
        "since": args.since,
        "until": args.until,
    }
    matched = [
        record
        for record in ordered_records
        if log_entry_record_matches(record, filters)
    ]
    if args.offset < 0:
        raise ValueError("--offset must be >= 0")
    if args.limit < 1:
        raise ValueError("--limit must be >= 1")
    if args.later_limit < 0:
        raise ValueError("--later-limit must be >= 0")
    limit_end = args.offset + args.limit
    returned = attach_later_log_events(
        matched[args.offset:limit_end],
        visible_records,
        later_limit=args.later_limit,
    )
    return {
        "project": selected_project,
        "store": str(store.path) if store is not None else None,
        "journal": str(args.journal),
        "event_source": event_source,
        "sqlite_event_count": sqlite_event_count,
        "query": query,
        "total_records": len(visible_records),
        "total_record_events": len(versioned_records),
        "superseded_record_events": sum(1 for record in versioned_records if record.get("superseded_by") is not None),
        "include_superseded": bool(args.include_superseded),
        "matched_records": len(matched),
        "returned_records": len(returned),
        "offset": args.offset,
        "limit": args.limit,
        "order": "oldest-first" if args.oldest_first else "newest-first",
        "filters": filters,
        "records": returned,
        "body_lines": args.body_lines,
        "later_limit": args.later_limit,
    }


def log_record_source_events(
    args: argparse.Namespace,
    store: SQLiteStore | None,
) -> tuple[list[dict[str, Any]], str | None, str, int]:
    sqlite_events: list[dict[str, Any]] = []
    if store is not None:
        sqlite_events = store.events(project=args.project, event_type="log_entry_import", limit=None)
        if sqlite_events:
            selected_project = select_event_project(sqlite_events, args.project, source_label="SQLite events")
            return sqlite_events, selected_project, "sqlite", len(sqlite_events)
    journal_events = read_journal_events(args.journal)
    selected_project = select_event_project(journal_events, args.project, source_label="journal")
    return journal_events, selected_project, "journal", len(sqlite_events)


def select_event_project(events: list[dict[str, Any]], project: str | None, *, source_label: str) -> str | None:
    event_projects = {event["project"] for event in events}
    if project is None and len(event_projects) > 1:
        available = ", ".join(sorted(event_projects))
        raise ValueError(f"{source_label} contains multiple projects; specify --project <name> (available: {available})")
    if project is not None and event_projects and project not in event_projects:
        available = ", ".join(sorted(event_projects))
        raise ValueError(f"project {project!r} is not present in {source_label} (available: {available})")
    return project or (next(iter(event_projects)) if event_projects else None)


def log_record_event_order_index(event: dict[str, Any], fallback_index: int) -> int:
    event_sequence = event.get("event_sequence")
    if event_sequence is None:
        return fallback_index
    return int(event_sequence)


def log_entry_record_from_event(event: dict[str, Any], *, journal_index: int) -> dict[str, Any]:
    payload = event.get("payload") or {}
    body_lines = [
        line
        for line in payload.get("body_lines") or []
        if isinstance(line, dict)
    ]
    body_text = "\n".join(str(line.get("text", "")) for line in body_lines)
    payload_subjects = payload.get("subjects") or []
    subjects: list[str] = []
    seen_subjects: set[str] = set()
    for subject in payload_subjects:
        add_log_entry_subject(subjects, seen_subjects, str(subject))
    if not subjects:
        subjects = log_entry_subjects_from_lines(
            [
                {"text": str(payload.get("heading") or "")},
                *body_lines,
            ]
        )
    explicit_subjects = [str(subject) for subject in payload.get("explicit_subjects") or []]
    heuristic_subjects = [str(subject) for subject in payload.get("heuristic_subjects") or []]
    if not explicit_subjects and not heuristic_subjects and subjects:
        heuristic_subjects = list(subjects)
    return {
        "journal_index": journal_index,
        "event_id": event["event_id"],
        "event_created_at": event["created_at"],
        "project": event["project"],
        "record_id": str(payload.get("record_id") or ""),
        "legacy_record_id": str(payload.get("legacy_record_id") or ""),
        "supersedes_record_ids": [str(record_id) for record_id in payload.get("supersedes_record_ids") or []],
        "record_identity": str(payload.get("record_identity") or ("file_page" if str(payload.get("record_format") or "section") == "file" else "section_content")),
        "record_format": str(payload.get("record_format") or "section"),
        "content_fingerprint": log_entry_payload_content_fingerprint(payload),
        "source_path": str(payload.get("source_path") or ""),
        "page_id": str(payload.get("page_id") or ""),
        "timestamp": str(payload.get("timestamp") or ""),
        "op": str(payload.get("op") or ""),
        "summary": str(payload.get("summary") or ""),
        "heading": str(payload.get("heading") or ""),
        "heading_line_index": int(payload.get("heading_line_index", -1)),
        "subjects": subjects,
        "explicit_subjects": explicit_subjects,
        "heuristic_subjects": heuristic_subjects,
        "subject_source": str(payload.get("subject_source") or ("frontmatter" if explicit_subjects else "heuristic")),
        "sources": [str(source) for source in payload.get("sources") or []],
        "body_lines": body_lines,
        "body_line_count": int(payload.get("body_line_count", len(body_lines))),
        "body_text": body_text,
    }


def annotate_log_entry_record_versions(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not records:
        return []

    parent: dict[str, str] = {}

    def find(value: str) -> str:
        parent.setdefault(value, value)
        if parent[value] != value:
            parent[value] = find(parent[value])
        return parent[value]

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for record in records:
        identity_keys = log_entry_record_identity_keys(record)
        if not identity_keys:
            continue
        first_key = identity_keys[0]
        for key in identity_keys[1:]:
            union(first_key, key)
        find(first_key)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        identity_keys = log_entry_record_identity_keys(record)
        group_key = find(identity_keys[0]) if identity_keys else f"journal:{record['journal_index']}"
        grouped.setdefault(group_key, []).append(record)

    annotated_by_index: dict[int, dict[str, Any]] = {}
    for group_records in grouped.values():
        ordered = sorted(group_records, key=lambda record: record["journal_index"])
        latest = ordered[-1]
        latest_summary = log_entry_version_summary(latest)
        for version_index, record in enumerate(ordered, start=1):
            annotated = dict(record)
            annotated["record_version"] = version_index
            annotated["record_version_count"] = len(ordered)
            annotated["superseded_by"] = None if record is latest else latest_summary
            if version_index > 1:
                annotated["supersedes"] = log_entry_version_summary(ordered[version_index - 2])
            else:
                annotated["supersedes"] = None
            annotated_by_index[int(record["journal_index"])] = annotated

    return [
        annotated_by_index[int(record["journal_index"])]
        for record in records
    ]


def log_entry_record_identity_keys(record: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for key in ("record_id", "legacy_record_id"):
        value = str(record.get(key) or "")
        if value:
            keys.append(value)
    for value in record.get("supersedes_record_ids") or []:
        if value:
            keys.append(str(value))
    return list(dict.fromkeys(keys))


def log_entry_version_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": record["record_id"],
        "event_id": record["event_id"],
        "journal_index": record["journal_index"],
        "timestamp": record["timestamp"],
        "op": record["op"],
        "summary": record["summary"],
        "source_path": record["source_path"],
        "content_fingerprint": record["content_fingerprint"],
    }


def log_entry_record_matches(record: dict[str, Any], filters: dict[str, Any]) -> bool:
    query = filters.get("query")
    if query and not log_entry_record_query_matches(record, str(query)):
        return False
    subjects = filters.get("subject") or []
    if subjects and not log_entry_record_subject_matches(record, subjects):
        return False
    source_path = filters.get("source_path")
    if source_path and record["source_path"] != str(source_path):
        return False
    ops = filters.get("op") or []
    if ops and record["op"] not in {str(op) for op in ops}:
        return False
    record_id = filters.get("record_id")
    if record_id and record["record_id"] != str(record_id):
        return False
    since = filters.get("since")
    if since and record["timestamp"] < str(since):
        return False
    until = filters.get("until")
    if until and record["timestamp"] > str(until):
        return False
    return True


def log_entry_record_query_matches(record: dict[str, Any], query: str) -> bool:
    terms = [term for term in query.casefold().split() if term]
    if not terms:
        return True
    search_text = log_entry_record_search_text(record).casefold()
    return all(term in search_text for term in terms)


def log_entry_record_subject_matches(record: dict[str, Any], subjects: list[str]) -> bool:
    record_subject_norms = {
        normalize_title(subject)
        for subject in record.get("subjects", [])
    }
    if not record_subject_norms:
        return False
    query_subject_norms = {
        normalize_title(subject)
        for subject in (log_entry_subject_display(str(subject)) for subject in subjects)
        if subject
    }
    return any(subject_norm in record_subject_norms for subject_norm in query_subject_norms)


def log_entry_record_search_text(record: dict[str, Any]) -> str:
    return "\n".join(
        [
            record.get("record_id", ""),
            record.get("content_fingerprint", ""),
            record.get("record_identity", ""),
            record.get("source_path", ""),
            record.get("page_id", ""),
            record.get("timestamp", ""),
            record.get("op", ""),
            record.get("summary", ""),
            record.get("heading", ""),
            "\n".join(record.get("subjects", [])),
            "\n".join(record.get("sources", [])),
            record.get("body_text", ""),
        ]
    )


def attach_later_log_events(
    returned_records: list[dict[str, Any]],
    all_records: list[dict[str, Any]],
    *,
    later_limit: int,
) -> list[dict[str, Any]]:
    chronological_records = sorted(
        all_records,
        key=lambda record: (record["timestamp"], record["journal_index"]),
    )
    annotated = []
    for record in returned_records:
        later_events = later_log_events_for_record(record, chronological_records)
        record_with_later = dict(record)
        record_with_later["later_event_count"] = len(later_events)
        record_with_later["later_events"] = [
            log_entry_later_event_summary(later_event, record)
            for later_event in later_events[:later_limit]
        ]
        record_with_later["later_events_omitted"] = max(0, len(later_events) - later_limit)
        annotated.append(record_with_later)
    return annotated


def later_log_events_for_record(
    record: dict[str, Any],
    chronological_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    record_subject_norms = {
        normalize_title(subject)
        for subject in record.get("subjects", [])
    }
    if not record_subject_norms:
        return []
    record_position = (record["timestamp"], record["journal_index"])
    later_events = []
    for candidate in chronological_records:
        candidate_position = (candidate["timestamp"], candidate["journal_index"])
        if candidate_position <= record_position:
            continue
        candidate_subject_norms = {
            normalize_title(subject)
            for subject in candidate.get("subjects", [])
        }
        if record_subject_norms & candidate_subject_norms:
            later_events.append(candidate)
    return later_events


def log_entry_later_event_summary(
    later_event: dict[str, Any],
    base_record: dict[str, Any],
) -> dict[str, Any]:
    base_subject_norms = {
        normalize_title(subject)
        for subject in base_record.get("subjects", [])
    }
    shared_subjects = [
        subject
        for subject in later_event.get("subjects", [])
        if normalize_title(subject) in base_subject_norms
    ]
    return {
        "record_id": later_event["record_id"],
        "event_id": later_event["event_id"],
        "timestamp": later_event["timestamp"],
        "op": later_event["op"],
        "summary": later_event["summary"],
        "source_path": later_event["source_path"],
        "subjects": later_event.get("subjects", []),
        "shared_subjects": shared_subjects,
    }


def run_export_markdown(store: SQLiteStore, args: argparse.Namespace) -> dict[str, Any]:
    log_events = None
    log_event_source = None
    log_overlay_name = None
    if args.regenerate_log:
        if args.journal is not None:
            log_events = read_journal_events(args.journal)
            log_event_source = "journal"
            log_overlay_name = "legacy-journal-log"
        else:
            log_events = store.events(project=args.project, limit=None)
            log_event_source = "sqlite"
            log_overlay_name = "sqlite-events-log"
    return store.export_markdown(
        args.output,
        check=args.check,
        regenerate_index=args.regenerate_index,
        log_events=log_events,
        log_event_source=log_event_source,
        log_overlay_name=log_overlay_name,
    )


def event_metadata(args: argparse.Namespace) -> dict[str, str]:
    return {
        "actor": str(getattr(args, "actor", "") or "").strip(),
        "session_id": str(getattr(args, "session_id", "") or "").strip(),
    }


def run_append_section(store: SQLiteStore, args: argparse.Namespace) -> dict[str, Any]:
    journal = optional_journal_path_for_output(args)
    section_lines = ["", f"## {args.heading}", *args.line]
    append_result, event = store.append_markdown_lines_with_event(
        args.title,
        section_lines,
        event_type="section_append",
        payload={
            "heading": args.heading,
            "lines": args.line,
        },
        **event_metadata(args),
    )
    projection = append_event_and_export_projection(
        store,
        journal,
        event,
        lambda: store.export_markdown(args.output, check=False),
        **event_metadata(args),
    )
    result = dict(append_result)
    result.update(
        {
            "journal": str(journal) if journal is not None else None,
            "journal_written": journal is not None,
            "output": str(args.output),
            "event_id": event["event_id"],
            "projection": projection,
        }
    )
    return result


def run_append_log(store: SQLiteStore, args: argparse.Namespace) -> dict[str, Any]:
    journal = optional_journal_path_for_output(args)
    timestamp = args.timestamp or datetime.now().strftime("%Y-%m-%d %H:%M")
    heading = f"[{timestamp}] {args.op} | {args.summary}"
    log_lines = ["", f"## {heading}", *args.line]
    append_result, event = store.append_markdown_lines_with_event(
        args.title,
        log_lines,
        event_type="log_append",
        payload={
            "timestamp": timestamp,
            "op": args.op,
            "summary": args.summary,
            "lines": args.line,
        },
        **event_metadata(args),
    )
    projection = append_event_and_export_projection(
        store,
        journal,
        event,
        lambda: store.export_markdown(args.output, check=False),
        **event_metadata(args),
    )
    result = dict(append_result)
    result.update(
        {
            "journal": str(journal) if journal is not None else None,
            "journal_written": journal is not None,
            "output": str(args.output),
            "event_id": event["event_id"],
            "timestamp": timestamp,
            "op": args.op,
            "summary": args.summary,
            "projection": projection,
        }
    )
    return result


def run_write_page(store: SQLiteStore, args: argparse.Namespace) -> dict[str, Any]:
    journal = optional_journal_path_for_output(args)
    replacement_lines = write_page_replacement_lines(args)
    update_result, event = store.write_markdown_page_with_event(
        args.title,
        lines=replacement_lines,
        create=args.create,
        source_path=args.source_path,
        message=args.message,
        **event_metadata(args),
    )
    projection = append_event_and_export_projection(
        store,
        journal,
        event,
        lambda: store.export_markdown(args.output, check=False),
        **event_metadata(args),
    )
    result = dict(update_result)
    result.update(
        {
            "journal": str(journal) if journal is not None else None,
            "journal_written": journal is not None,
            "output": str(args.output),
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "projection": projection,
        }
    )
    return result


def write_page_replacement_lines(args: argparse.Namespace) -> list[str]:
    if args.from_file is not None:
        if not args.from_file.exists():
            raise ValueError(f"replacement file does not exist: {args.from_file}")
        if args.from_file.is_dir():
            raise ValueError(f"replacement file is a directory: {args.from_file}")
        return args.from_file.read_text(encoding="utf-8").splitlines()
    return list(args.line or [])


def run_rename_page(store: SQLiteStore, args: argparse.Namespace) -> dict[str, Any]:
    journal = optional_journal_path_for_output(args)
    rename_result, event = store.rename_markdown_page_with_event(
        args.target,
        args.new_title,
        target_kind=args.target_kind,
        new_source_path=args.new_path,
        update_heading=not args.no_heading_update,
        message=args.message,
        **event_metadata(args),
    )
    def project_rename() -> dict[str, Any]:
        removed_files = remove_previous_projection_file(
            args.output,
            rename_result["previous_source_path"],
            rename_result["source_path"],
        )
        projection = store.export_markdown(args.output, check=False)
        projection["removed_files"] = removed_files
        projection["removed_count"] = len(removed_files)
        return projection

    projection = append_event_and_export_projection(store, journal, event, project_rename, **event_metadata(args))
    result = dict(rename_result)
    result.update(
        {
            "journal": str(journal) if journal is not None else None,
            "journal_written": journal is not None,
            "output": str(args.output),
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "projection": projection,
        }
    )
    return result


def remove_previous_projection_file(output: Path, previous_source_path: str, source_path: str) -> list[str]:
    if previous_source_path == source_path:
        return []
    previous = _safe_replay_output_path(output, previous_source_path)
    current = _safe_replay_output_path(output, source_path)
    if previous == current or not previous.exists():
        return []
    if previous.is_dir():
        raise ValueError(f"previous Markdown projection path is a directory: {previous_source_path}")
    previous.unlink()
    return [previous_source_path]


def remove_projection_file(output: Path, source_path: str) -> list[str]:
    target = _safe_replay_output_path(output, source_path)
    if not target.exists():
        return []
    if target.is_dir():
        raise ValueError(f"Markdown projection path is a directory: {source_path}")
    target.unlink()
    return [source_path]


def append_event_and_export_projection(
    store: SQLiteStore,
    journal: Path | None,
    event: dict[str, Any],
    export_projection: Any,
    *,
    actor: str = "",
    session_id: str = "",
) -> dict[str, Any]:
    if journal is not None:
        append_journal_event(journal, event)
    try:
        return export_projection()
    except Exception as error:
        rollback = rollback_event_after_projection_failure(
            store,
            journal,
            event,
            error,
            actor=actor,
            session_id=session_id,
        )
        raise ProjectionExportRollbackError(
            "projection export failed after event write; "
            f"store was reverted with event {rollback['rollback_event_id']}: {error}",
            diagnostic=rollback,
        ) from error


def rollback_event_after_projection_failure(
    store: SQLiteStore,
    journal: Path | None,
    target: dict[str, Any],
    error: Exception,
    *,
    actor: str = "",
    session_id: str = "",
) -> dict[str, Any]:
    reason = f"projection export failed: {type(error).__name__}: {error}"
    try:
        with store.write_transaction():
            rollback = revert_journal_event_in_store(store, target, reason=reason, uncommitted=True)
            event = make_journal_event(
                "event_revert",
                project=rollback["reverted"]["project"],
                payload=rollback["payload"],
            )
            insert_store_event(store.connection, event, actor=actor, session_id=session_id)
        if journal is not None:
            append_journal_event(journal, event)
        return {
            "type": "projection_export_rollback",
            "rolled_back": True,
            "target_event_id": target["event_id"],
            "target_event_type": target["event_type"],
            "target_event_project": target["project"],
            "rollback_event_id": event["event_id"],
            "rollback_event_type": event["event_type"],
            "rollback_event": event,
            "journal": str(journal) if journal is not None else None,
            "journal_written": journal is not None,
            "reason": reason,
            "original_error": {
                "type": type(error).__name__,
                "message": str(error),
            },
        }
    except Exception as rollback_error:
        diagnostic = {
            "type": "projection_export_rollback_failed",
            "rolled_back": False,
            "target_event_id": target.get("event_id"),
            "target_event_type": target.get("event_type"),
            "target_event_project": target.get("project"),
            "journal": str(journal) if journal is not None else None,
            "journal_written": False,
            "reason": reason,
            "original_error": {
                "type": type(error).__name__,
                "message": str(error),
            },
            "rollback_error": {
                "type": type(rollback_error).__name__,
                "message": str(rollback_error),
            },
        }
        raise ProjectionExportRollbackFailedError(
            "projection export failed and automatic store rollback failed; "
            f"original error: {error}; rollback error: {rollback_error}",
            diagnostic=diagnostic,
        ) from rollback_error


def run_write_status(store: SQLiteStore, args: argparse.Namespace) -> dict[str, Any]:
    journal = optional_journal_path_for_output(args)
    events = read_journal_events(journal) if journal is not None else []
    projection = store.export_markdown(args.output, check=True)
    journal_project_events = [
        event
        for event in events
        if event.get("project") == projection["project"]
    ]
    sqlite_events = store.events(project=projection["project"], limit=None)
    sqlite_event_count = len(sqlite_events)
    sqlite_last_event = sqlite_events[-1] if sqlite_events else None
    event_stream_mismatch = (
        compare_event_streams(journal_project_events, sqlite_events)
        if journal is not None
        else None
    )
    journal_log_projection = None
    journal_log_changed_files: list[str] = []
    journal_log_error = None
    if journal is not None and journal.exists() and events:
        try:
            journal_log_projection = store.export_markdown(
                args.output,
                check=True,
                log_events=events,
                log_event_source="journal",
                log_overlay_name="legacy-journal-log",
            )
            journal_log_changed_files = regenerated_projection_dirty_files(journal_log_projection)
        except ValueError as error:
            journal_log_error = str(error)
    semantic_log_projection = None
    semantic_log_changed_files: list[str] = []
    semantic_log_error = None
    semantic_log_policy_errors: list[str] = []
    try:
        semantic_log_projection = store.export_markdown(
            args.output,
            check=True,
            log_events=sqlite_events,
            log_event_source="sqlite",
            log_overlay_name="sqlite-events-log",
        )
        semantic_log_changed_files = regenerated_projection_dirty_files(semantic_log_projection)
        semantic_log_policy_errors = semantic_log_projection_contract_errors(semantic_log_projection)
    except ValueError as error:
        message = str(error)
        if "has no log page to regenerate" not in message:
            semantic_log_error = message
    strict_failures = write_status_strict_failures(
        projection=projection,
        journal_exists=journal.exists() if journal is not None else False,
        journal_required=journal is not None,
        journal_log_projection=journal_log_projection,
        journal_log_changed_files=journal_log_changed_files,
        journal_log_error=journal_log_error,
        semantic_log_projection=semantic_log_projection,
        semantic_log_changed_files=semantic_log_changed_files,
        semantic_log_error=semantic_log_error,
        semantic_log_policy_errors=semantic_log_policy_errors,
        event_stream_mismatch=event_stream_mismatch,
    )
    return {
        "project": projection["project"],
        "output": str(args.output),
        "journal": str(journal) if journal is not None else None,
        "journal_required": journal is not None,
        "journal_exists": journal.exists() if journal is not None else False,
        "journal_event_count": len(events),
        "journal_project_event_count": len(journal_project_events),
        "journal_log_record_count": journal_log_record_count(events, project=projection["project"]),
        "last_event": events[-1] if events else None,
        "sqlite_event_count": sqlite_event_count,
        "sqlite_last_event": sqlite_last_event,
        "event_streams_match": event_stream_mismatch is None,
        "event_stream_mismatch": event_stream_mismatch,
        "projection": projection,
        "journal_log_stale": bool(journal_log_changed_files),
        "journal_log_changed_files": journal_log_changed_files,
        "journal_log_projection": journal_log_projection,
        "journal_log_error": journal_log_error,
        "semantic_log_stale": bool(semantic_log_changed_files),
        "semantic_log_changed_files": semantic_log_changed_files,
        "semantic_log_projection": semantic_log_projection,
        "semantic_log_error": semantic_log_error,
        "semantic_log_policy_errors": semantic_log_policy_errors,
        "strict_ok": not strict_failures,
        "strict_failures": strict_failures,
    }


def compare_event_streams(
    journal_events: list[dict[str, Any]],
    sqlite_events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    def summary(event: dict[str, Any] | None) -> dict[str, Any] | None:
        if event is None:
            return None
        return {
            "event_id": event.get("event_id"),
            "event_type": event.get("event_type"),
            "project": event.get("project"),
        }

    if not sqlite_events:
        return None
    if len(sqlite_events) > len(journal_events):
        return {
            "kind": "count_mismatch",
            "index": len(journal_events),
            "journal_event_count": len(journal_events),
            "sqlite_event_count": len(sqlite_events),
            "journal_event": None,
            "sqlite_event": summary(sqlite_events[len(journal_events)]),
        }

    journal_index = 0
    for index, sqlite_event in enumerate(sqlite_events):
        sqlite = summary(sqlite_event)
        while journal_index < len(journal_events) and summary(journal_events[journal_index]) != sqlite:
            journal_index += 1
        if journal_index >= len(journal_events):
            return {
                "kind": "event_mismatch",
                "index": index,
                "journal_search_start": journal_index,
                "journal_event_count": len(journal_events),
                "sqlite_event_count": len(sqlite_events),
                "journal_event": None,
                "sqlite_event": sqlite,
            }
        journal_index += 1
    return None


def journal_log_record_count(events: list[dict[str, Any]], *, project: str) -> int:
    return sum(
        1
        for event in events
        if event.get("project") == project and event.get("event_type") == "log_entry_import"
    )


def write_status_strict_failures(
    *,
    projection: dict[str, Any],
    journal_exists: bool,
    journal_required: bool,
    journal_log_projection: dict[str, Any] | None,
    journal_log_changed_files: list[str],
    journal_log_error: str | None,
    semantic_log_projection: dict[str, Any] | None,
    semantic_log_changed_files: list[str],
    semantic_log_error: str | None,
    semantic_log_policy_errors: list[str],
    event_stream_mismatch: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    projection_changed_files = list(projection.get("changed_files") or [])
    projection_missing_files = list(projection.get("missing_files") or [])
    projection_extra_files = list(projection.get("extra_files") or [])
    if journal_log_projection and journal_log_projection.get("ok"):
        regenerated = set(journal_log_projection.get("regenerated_files") or [])
        projection_changed_files = [
            path
            for path in projection_changed_files
            if path not in regenerated
        ]
    if semantic_log_projection and semantic_log_projection.get("ok"):
        regenerated = set(semantic_log_projection.get("regenerated_files") or [])
        projection_changed_files = [
            path
            for path in projection_changed_files
            if path not in regenerated
        ]
    if projection_changed_files or projection_missing_files or projection_extra_files:
        failures.append(
            {
                "type": "projection_dirty",
                "changed_files": projection_changed_files,
                "missing_files": projection_missing_files,
                "extra_files": projection_extra_files,
            }
        )
    if journal_required and not journal_exists:
        failures.append({"type": "journal_missing"})
    if event_stream_mismatch is not None:
        failures.append(
            {
                "type": "event_stream_mismatch",
                "mismatch": event_stream_mismatch,
            }
        )
    if journal_log_changed_files:
        failures.append(
            {
                "type": "journal_log_stale",
                "changed_files": journal_log_changed_files,
            }
        )
    if journal_log_error:
        failures.append(
            {
                "type": "journal_log_error",
                "message": journal_log_error,
            }
        )
    if semantic_log_changed_files:
        failures.append(
            {
                "type": "semantic_log_stale",
                "changed_files": semantic_log_changed_files,
            }
        )
    if semantic_log_error:
        failures.append(
            {
                "type": "semantic_log_error",
                "message": semantic_log_error,
            }
        )
    if semantic_log_policy_errors:
        failures.append(
            {
                "type": "semantic_log_policy",
                "errors": semantic_log_policy_errors,
            }
        )
    return failures


def semantic_log_projection_contract_errors(projection: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if projection.get("log_event_source") != "sqlite":
        errors.append(f"log_event_source={projection.get('log_event_source')!r}, expected 'sqlite'")
    policy = projection.get("projection_policy")
    if not isinstance(policy, dict):
        errors.append("missing projection_policy object")
        return errors
    overlays = policy.get("generated_overlays")
    if not isinstance(overlays, list):
        errors.append("projection_policy.generated_overlays must be a list")
    elif "sqlite-events-log" not in overlays:
        errors.append("projection_policy.generated_overlays is missing 'sqlite-events-log'")
    regenerated_files = projection.get("regenerated_files")
    if not isinstance(regenerated_files, list) or not regenerated_files:
        errors.append("regenerated_files must include the semantic log projection")
    return errors


def regenerated_projection_dirty_files(projection: dict[str, Any]) -> list[str]:
    regenerated = set(projection.get("regenerated_files") or [])
    dirty = set(projection.get("changed_files") or [])
    dirty.update(projection.get("missing_files") or [])
    dirty.update(projection.get("extra_files") or [])
    return sorted(regenerated & dirty)


def run_revert_event(store: SQLiteStore, args: argparse.Namespace) -> dict[str, Any]:
    journal = optional_journal_path_for_output(args)
    journal_events = read_journal_events(journal) if journal is not None else []
    selected_project = store._require_project()
    sqlite_events = store.events(project=selected_project, limit=None)
    target = next((event for event in sqlite_events if event["event_id"] == args.event_id), None)
    target_source = "sqlite"
    if target is None:
        target = next((event for event in journal_events if event["event_id"] == args.event_id), None)
        target_source = "journal"
    if target is None:
        if args.dry_run:
            return non_revertible_dry_run_result(
                args,
                journal=journal,
                project=selected_project,
                target=None,
                target_source=None,
                reason=f"event not found: {args.event_id}",
            )
        raise ValueError(f"event not found: {args.event_id}")
    if target["event_type"] not in REVERSIBLE_EVENT_TYPES:
        if args.dry_run:
            return non_revertible_dry_run_result(
                args,
                journal=journal,
                project=selected_project,
                target=target,
                target_source=target_source,
                reason=f"cannot revert event_type with this alpha command: {target['event_type']}",
            )
        raise ValueError(f"cannot revert event_type with this alpha command: {target['event_type']}")
    if target["project"] != selected_project:
        if args.dry_run:
            return non_revertible_dry_run_result(
                args,
                journal=journal,
                project=selected_project,
                target=target,
                target_source=target_source,
                reason=f"event belongs to project {target['project']!r}; selected project is {selected_project!r}",
            )
        raise ValueError(f"event belongs to project {target['project']!r}; selected project is {selected_project!r}")
    if any(
        event["event_type"] == "event_revert"
        and event.get("payload", {}).get("target_event_id") == args.event_id
        for event in [*sqlite_events, *journal_events]
    ):
        if args.dry_run:
            return non_revertible_dry_run_result(
                args,
                journal=journal,
                project=selected_project,
                target=target,
                target_source=target_source,
                reason=f"event is already reverted: {args.event_id}",
            )
        raise ValueError(f"event is already reverted: {args.event_id}")
    if args.include_dependents:
        return run_revert_event_with_dependents(
            store,
            args,
            journal=journal,
            target=target,
            target_source=target_source,
            sqlite_events=sqlite_events,
        )
    if args.dry_run:
        return run_revert_event_dry_run(
            store,
            args,
            journal=journal,
            target=target,
            target_source=target_source,
        )
    if target_source == "sqlite":
        with store.write_transaction():
            rollback = revert_journal_event_in_store(store, target, reason=args.reason, uncommitted=True)
            reverted = rollback["reverted"]
            event = make_journal_event(
                "event_revert",
                project=reverted["project"],
                payload=rollback["payload"],
            )
            insert_store_event(store.connection, event, **event_metadata(args))
    else:
        rollback = revert_journal_event_in_store(store, target, reason=args.reason)
        reverted = rollback["reverted"]
        event = make_journal_event(
            "event_revert",
            project=reverted["project"],
            payload=rollback["payload"],
        )
    reverted = rollback["reverted"]
    source_path = rollback["source_path"]
    previous_source_path = rollback["previous_source_path"]
    if journal is not None:
        append_journal_event(journal, event)
    removed_files = []
    if target["event_type"] == "page_rename":
        removed_files = remove_previous_projection_file(args.output, source_path, previous_source_path)
    elif target["event_type"] == "page_create":
        removed_files = remove_projection_file(args.output, source_path)
    projection = store.export_markdown(args.output, check=False)
    projection["removed_files"] = removed_files
    projection["removed_count"] = len(removed_files)
    result = dict(reverted)
    result.update(
        {
            "journal": str(journal) if journal is not None else None,
            "journal_written": journal is not None,
            "output": str(args.output),
            "event_id": event["event_id"],
            "target_event_id": target["event_id"],
            "target_event_type": target["event_type"],
            "target_event_source": target_source,
            "projection": projection,
        }
    )
    return result


def run_revert_events(store: SQLiteStore, args: argparse.Namespace) -> dict[str, Any]:
    journal = optional_journal_path_for_output(args)
    selected_project = store._require_project()
    sqlite_events = store.events(project=selected_project, limit=None)
    try:
        targets = selected_multi_revert_targets(sqlite_events, args.event_ids, selected_project=selected_project)
    except ValueError as error:
        if args.dry_run:
            return non_revertible_multi_revert_result(
                args,
                journal=journal,
                project=selected_project,
                reason=str(error),
            )
        raise
    if args.dry_run:
        return run_revert_events_dry_run(
            store,
            args,
            journal=journal,
            project=selected_project,
            targets=targets,
        )

    records: list[dict[str, Any]] = []
    with store.write_transaction():
        for target in targets:
            rollback = revert_journal_event_in_store(store, target, reason=args.reason, uncommitted=True)
            reverted = rollback["reverted"]
            event = make_journal_event(
                "event_revert",
                project=reverted["project"],
                payload=rollback["payload"],
            )
            insert_store_event(store.connection, event, **event_metadata(args))
            records.append({"target": target, "rollback": rollback, "event": event})
    if journal is not None:
        for record in records:
            append_journal_event(journal, record["event"])
    removed_files = remove_projection_files_for_revert_records(args.output, records)
    projection = store.export_markdown(args.output, check=False)
    projection["removed_files"] = removed_files
    projection["removed_count"] = len(removed_files)
    return multi_revert_result(
        args,
        journal=journal,
        project=selected_project,
        targets=targets,
        records=records,
        projection=projection,
        dry_run=False,
        journal_written=journal is not None,
    )


def selected_multi_revert_targets(
    sqlite_events: list[dict[str, Any]],
    event_ids: list[str],
    *,
    selected_project: str,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    duplicate_ids: list[str] = []
    for event_id in event_ids:
        if event_id in seen:
            duplicate_ids.append(event_id)
        seen.add(event_id)
    if duplicate_ids:
        duplicates = ", ".join(duplicate_ids)
        raise ValueError(f"duplicate event ids: {duplicates}")

    events_by_id = {str(event["event_id"]): event for event in sqlite_events}
    missing_ids = [event_id for event_id in event_ids if event_id not in events_by_id]
    if missing_ids:
        missing = ", ".join(missing_ids)
        raise ValueError(f"SQLite event not found: {missing}")
    reverted_ids = reverted_target_event_ids(sqlite_events)
    targets = [events_by_id[event_id] for event_id in event_ids]
    for target in targets:
        event_id = str(target["event_id"])
        event_type = target.get("event_type")
        if target.get("project") != selected_project:
            raise ValueError(
                f"event belongs to project {target.get('project')!r}; selected project is {selected_project!r}: {event_id}"
            )
        if event_type not in REVERSIBLE_EVENT_TYPES:
            raise ValueError(f"cannot revert event_type with this alpha command: {event_type} ({event_id})")
        if event_id in reverted_ids:
            raise ValueError(f"event is already reverted: {event_id}")
    return sorted(targets, key=lambda event: int(event.get("event_sequence") or 0), reverse=True)


def run_revert_events_dry_run(
    store: SQLiteStore,
    args: argparse.Namespace,
    *,
    journal: Path | None,
    project: str,
    targets: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        with store.write_transaction():
            records: list[dict[str, Any]] = []
            for target in targets:
                rollback = revert_journal_event_in_store(store, target, reason=args.reason, uncommitted=True)
                records.append({"target": target, "rollback": rollback, "event": None})
            result = multi_revert_result(
                args,
                journal=journal,
                project=project,
                targets=targets,
                records=records,
                projection=None,
                dry_run=True,
                journal_written=False,
                would_remove_files=projection_files_removed_for_revert_records(args.output, records),
            )
            raise RevertDryRunComplete(result)
    except RevertDryRunComplete as complete:
        return complete.result
    except ValueError as error:
        return non_revertible_multi_revert_result(
            args,
            journal=journal,
            project=project,
            reason=str(error),
            targets=targets,
        )


def multi_revert_result(
    args: argparse.Namespace,
    *,
    journal: Path | None,
    project: str,
    targets: list[dict[str, Any]],
    records: list[dict[str, Any]],
    projection: dict[str, Any] | None,
    dry_run: bool,
    journal_written: bool,
    would_remove_files: list[str] | None = None,
) -> dict[str, Any]:
    event_ids = [
        record["event"]["event_id"]
        for record in records
        if record.get("event") is not None
    ]
    result = {
        "project": project,
        "journal": str(journal) if journal is not None else None,
        "journal_written": journal_written,
        "would_write_journal": journal is not None if dry_run else None,
        "output": str(args.output),
        "dry_run": dry_run,
        "revertible": True,
        "event_ids": event_ids,
        "would_event_type": "event_revert",
        "would_event_count": len(records) if dry_run else None,
        "reverted_event_count": 0 if dry_run else len(records),
        "requested_event_ids": list(args.event_ids),
        "target_event_ids": [target["event_id"] for target in targets],
        "target_event_source": "sqlite",
        "revert_order_event_ids": [target["event_id"] for target in targets],
        "reverted_events": [
            revert_record_summary(record, dry_run=dry_run)
            for record in records
        ],
        "projection": projection,
        "would_export_projection": True if dry_run else None,
        "would_remove_files": would_remove_files if dry_run else None,
    }
    if not dry_run:
        result.pop("would_write_journal", None)
        result.pop("would_event_count", None)
        result.pop("would_export_projection", None)
        result.pop("would_remove_files", None)
    return result


def non_revertible_multi_revert_result(
    args: argparse.Namespace,
    *,
    journal: Path | None,
    project: str | None,
    reason: str,
    targets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    targets = targets or []
    return {
        "project": project,
        "journal": str(journal) if journal is not None else None,
        "journal_written": False,
        "would_write_journal": False,
        "output": str(args.output),
        "dry_run": True,
        "revertible": False,
        "event_ids": [],
        "would_event_type": "event_revert",
        "would_event_count": 0,
        "reverted_event_count": 0,
        "requested_event_ids": list(args.event_ids),
        "target_event_ids": [target["event_id"] for target in targets],
        "target_event_source": "sqlite",
        "revert_order_event_ids": [target["event_id"] for target in targets],
        "reverted_events": [],
        "projection": None,
        "would_export_projection": False,
        "would_remove_files": [],
        "reason": reason,
    }


def run_revert_plan(store: SQLiteStore, args: argparse.Namespace) -> dict[str, Any]:
    selected_project = store._require_project()
    sqlite_events = store.events(project=selected_project, limit=None)
    events_by_id = {str(event["event_id"]): event for event in sqlite_events}
    anchor = events_by_id.get(args.event_id)
    if anchor is None:
        raise ValueError(f"SQLite event not found: {args.event_id}")
    if anchor.get("project") != selected_project:
        raise ValueError(
            f"event belongs to project {anchor.get('project')!r}; selected project is {selected_project!r}: {args.event_id}"
        )
    window_before = int(getattr(args, "before", 0) or 0)
    window_after = int(getattr(args, "after", 0) or 0)
    if args.scope != "event-window" and (window_before or window_after):
        raise ValueError("--before/--after are only valid with --scope event-window")
    max_gap_seconds = getattr(args, "max_gap_seconds", None)
    if args.scope != "time-burst" and max_gap_seconds is not None:
        raise ValueError("--max-gap-seconds is only valid with --scope time-burst")
    if args.scope == "log-batch":
        return log_batch_revert_plan(store, args, selected_project, sqlite_events, anchor)
    if args.scope == "subject-log":
        return subject_log_revert_plan(store, args, selected_project, sqlite_events, anchor)
    if args.scope == "log-page-subjects":
        return log_page_subjects_revert_plan(store, args, selected_project, sqlite_events, anchor)
    if args.scope == "content-subjects":
        return content_subjects_revert_plan(store, args, selected_project, sqlite_events, anchor)
    if args.scope == "same-page-dependents":
        return same_page_dependents_revert_plan(store, args, selected_project, sqlite_events, anchor)
    if args.scope == "event-window":
        return event_window_revert_plan(store, args, selected_project, sqlite_events, anchor)
    if args.scope == "time-burst":
        return time_burst_revert_plan(store, args, selected_project, sqlite_events, anchor)
    if args.scope == "session":
        return session_revert_plan(store, args, selected_project, sqlite_events, anchor)
    raise ValueError(f"unsupported revert-plan scope: {args.scope}")


def log_batch_revert_plan(
    store: SQLiteStore,
    args: argparse.Namespace,
    project: str,
    sqlite_events: list[dict[str, Any]],
    anchor: dict[str, Any],
) -> dict[str, Any]:
    events = sorted(sqlite_events, key=event_sequence)
    anchor_sequence = event_sequence(anchor)
    closing_log = first_log_append_at_or_after(events, anchor_sequence)
    end_sequence = event_sequence(closing_log) if closing_log is not None else event_sequence(events[-1])
    previous_log = last_log_append_before(events, end_sequence)
    start_sequence = event_sequence(previous_log) if previous_log is not None else 0
    reverted_ids = reverted_target_event_ids(sqlite_events)

    batch_events = [
        event
        for event in events
        if start_sequence < event_sequence(event) <= end_sequence
    ]
    candidates: list[dict[str, Any]] = []
    excluded_events: list[dict[str, Any]] = []
    for event in batch_events:
        exclusion_reason = revert_plan_exclusion_reason(event, reverted_ids)
        if exclusion_reason:
            excluded_events.append(revert_plan_event_summary(event, reason=exclusion_reason))
            continue
        candidates.append(event)

    targets = sorted(candidates, key=event_sequence, reverse=True)
    check = check_revert_plan_revertible(store, targets)
    candidate_event_ids = [event["event_id"] for event in candidates]
    result: dict[str, Any] = {
        "project": project,
        "scope": args.scope,
        "anchor_event_id": anchor["event_id"],
        "anchor_event": revert_plan_event_summary(anchor),
        "complete": closing_log is not None,
        "previous_log_event": revert_plan_event_summary(previous_log) if previous_log is not None else None,
        "closing_log_event": revert_plan_event_summary(closing_log) if closing_log is not None else None,
        "batch_start_after_event_sequence": start_sequence,
        "batch_end_event_sequence": end_sequence,
        "candidate_event_ids": candidate_event_ids,
        "revert_order_event_ids": [event["event_id"] for event in targets],
        "candidate_events": [revert_plan_event_summary(event) for event in candidates],
        "excluded_events": excluded_events,
        "revertible": check["revertible"],
        "reverted_events": check["reverted_events"],
    }
    if not result["complete"]:
        result["reason"] = "no closing log_append found after anchor; treating events through current SQLite tail as an incomplete log-batch"
    if not check["revertible"]:
        result["reason"] = check["reason"]
    if args.output is not None and candidate_event_ids:
        result["suggested_revert_events_args"] = [
            "revert-events",
            *candidate_event_ids,
            "--output",
            str(args.output),
        ]
    return result


def subject_log_revert_plan(
    store: SQLiteStore,
    args: argparse.Namespace,
    project: str,
    sqlite_events: list[dict[str, Any]],
    anchor: dict[str, Any],
) -> dict[str, Any]:
    events = sorted(sqlite_events, key=event_sequence)
    anchor_sequence = event_sequence(anchor)
    closing_log = first_log_append_at_or_after(events, anchor_sequence)
    end_sequence = event_sequence(closing_log) if closing_log is not None else event_sequence(events[-1])
    previous_log = last_log_append_before(events, end_sequence)
    start_sequence = event_sequence(previous_log) if previous_log is not None else 0
    batch_events = [
        event
        for event in events
        if start_sequence < event_sequence(event) <= end_sequence
    ]
    reverted_ids = reverted_target_event_ids(sqlite_events)
    excluded_events: list[dict[str, Any]] = []
    anchor_exclusion = revert_plan_exclusion_reason(anchor, reverted_ids)
    if anchor_exclusion:
        excluded_events.append(revert_plan_event_summary(anchor, reason=anchor_exclusion))
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": closing_log is not None,
            "previous_log_event": revert_plan_event_summary(previous_log) if previous_log is not None else None,
            "closing_log_event": revert_plan_event_summary(closing_log) if closing_log is not None else None,
            "subject_log_subjects": [],
            "candidate_event_ids": [],
            "revert_order_event_ids": [],
            "candidate_events": [],
            "excluded_events": excluded_events,
            "revertible": False,
            "reverted_events": [],
            "reason": f"anchor event is not an active reversible target: {anchor_exclusion}",
        }
    if closing_log is None:
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": False,
            "previous_log_event": revert_plan_event_summary(previous_log) if previous_log is not None else None,
            "closing_log_event": None,
            "subject_log_subjects": [],
            "candidate_event_ids": [],
            "revert_order_event_ids": [],
            "candidate_events": [],
            "excluded_events": [],
            "revertible": False,
            "reverted_events": [],
            "reason": "no closing log_append found after anchor; subject-log needs a closing log entry to read subjects",
        }

    subjects = log_append_event_subjects(closing_log)
    subject_norms = {normalize_title(subject) for subject in subjects}
    page_target_norms = event_page_target_norms_by_id(store, project)
    if not subject_norms:
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": False,
            "previous_log_event": revert_plan_event_summary(previous_log) if previous_log is not None else None,
            "closing_log_event": revert_plan_event_summary(closing_log),
            "subject_log_subjects": subjects,
            "candidate_event_ids": [],
            "revert_order_event_ids": [],
            "candidate_events": [],
            "excluded_events": [],
            "revertible": False,
            "reverted_events": [],
            "reason": "closing log_append has no wikilink or Markdown path subjects",
        }

    anchor_is_closing_log = anchor.get("event_id") == closing_log.get("event_id")
    if not anchor_is_closing_log and not event_matches_subject_norms(anchor, subject_norms, page_target_norms):
        excluded_events.append(
            revert_plan_event_summary(
                anchor,
                reason="anchor event target does not match closing log subjects",
            )
        )
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": False,
            "previous_log_event": revert_plan_event_summary(previous_log) if previous_log is not None else None,
            "closing_log_event": revert_plan_event_summary(closing_log),
            "subject_log_subjects": subjects,
            "subject_log_subject_norms": sorted(subject_norms),
            "candidate_event_ids": [],
            "revert_order_event_ids": [],
            "candidate_events": [],
            "excluded_events": excluded_events,
            "revertible": False,
            "reverted_events": [],
            "reason": "anchor event target does not match closing log subjects",
        }

    candidates: list[dict[str, Any]] = []
    for event in batch_events:
        is_closing_log = event.get("event_id") == closing_log.get("event_id")
        if not is_closing_log and not event_matches_subject_norms(event, subject_norms, page_target_norms):
            excluded_events.append(
                revert_plan_event_summary(
                    event,
                    reason="event target does not match closing log subjects",
                )
            )
            continue
        exclusion_reason = revert_plan_exclusion_reason(event, reverted_ids)
        if exclusion_reason:
            excluded_events.append(revert_plan_event_summary(event, reason=exclusion_reason))
            continue
        candidates.append(event)

    targets = sorted(candidates, key=event_sequence, reverse=True)
    check = check_revert_plan_revertible(store, targets)
    candidate_event_ids = [event["event_id"] for event in candidates]
    result: dict[str, Any] = {
        "project": project,
        "scope": args.scope,
        "anchor_event_id": anchor["event_id"],
        "anchor_event": revert_plan_event_summary(anchor),
        "complete": True,
        "previous_log_event": revert_plan_event_summary(previous_log) if previous_log is not None else None,
        "closing_log_event": revert_plan_event_summary(closing_log),
        "batch_start_after_event_sequence": start_sequence,
        "batch_end_event_sequence": end_sequence,
        "subject_log_subjects": subjects,
        "subject_log_subject_norms": sorted(subject_norms),
        "candidate_event_ids": candidate_event_ids,
        "revert_order_event_ids": [event["event_id"] for event in targets],
        "candidate_events": [revert_plan_event_summary(event) for event in candidates],
        "excluded_events": excluded_events,
        "revertible": check["revertible"],
        "reverted_events": check["reverted_events"],
    }
    if not candidate_event_ids:
        result["revertible"] = False
        result["reason"] = "subject-log contains no active reversible events"
    if not check["revertible"]:
        result["reason"] = check["reason"]
    if args.output is not None and candidate_event_ids:
        result["suggested_revert_events_args"] = [
            "revert-events",
            *candidate_event_ids,
            "--output",
            str(args.output),
        ]
    return result


def log_page_subjects_revert_plan(
    store: SQLiteStore,
    args: argparse.Namespace,
    project: str,
    sqlite_events: list[dict[str, Any]],
    anchor: dict[str, Any],
) -> dict[str, Any]:
    events = sorted(sqlite_events, key=event_sequence)
    anchor_sequence = event_sequence(anchor)
    closing_log = first_log_page_update_at_or_after(events, anchor_sequence)
    previous_log = (
        last_log_boundary_before(events, event_sequence(closing_log))
        if closing_log is not None
        else None
    )
    baseline_sequence = initial_baseline_end_sequence_before(events, anchor_sequence)
    start_sequence = (
        max(event_sequence(previous_log), baseline_sequence)
        if previous_log is not None
        else baseline_sequence
    )
    reverted_ids = reverted_target_event_ids(sqlite_events)
    excluded_events: list[dict[str, Any]] = []
    anchor_exclusion = revert_plan_exclusion_reason(anchor, reverted_ids)
    if anchor_exclusion:
        excluded_events.append(revert_plan_event_summary(anchor, reason=anchor_exclusion))
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": closing_log is not None,
            "previous_log_event": revert_plan_event_summary(previous_log) if previous_log is not None else None,
            "closing_log_event": revert_plan_event_summary(closing_log) if closing_log is not None else None,
            "log_page_subjects": [],
            "candidate_event_ids": [],
            "revert_order_event_ids": [],
            "candidate_events": [],
            "excluded_events": excluded_events,
            "revertible": False,
            "reverted_events": [],
            "reason": f"anchor event is not an active reversible target: {anchor_exclusion}",
        }
    if closing_log is None:
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": False,
            "previous_log_event": None,
            "closing_log_event": None,
            "log_page_subjects": [],
            "candidate_event_ids": [],
            "revert_order_event_ids": [],
            "candidate_events": [],
            "excluded_events": [],
            "revertible": False,
            "reverted_events": [],
            "reason": "no closing log page_update found after anchor; log-page-subjects needs a direct log page update to read subjects",
        }

    subjects = log_page_update_event_subjects(closing_log)
    subject_norms = {normalize_title(subject) for subject in subjects}
    page_target_norms = event_page_target_norms_by_id(store, project)
    if not subject_norms:
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": False,
            "previous_log_event": revert_plan_event_summary(previous_log) if previous_log is not None else None,
            "closing_log_event": revert_plan_event_summary(closing_log),
            "log_page_subjects": subjects,
            "candidate_event_ids": [],
            "revert_order_event_ids": [],
            "candidate_events": [],
            "excluded_events": [],
            "revertible": False,
            "reverted_events": [],
            "reason": "closing log page_update has no newly added wikilink or Markdown path subjects",
        }

    anchor_is_closing_log = anchor.get("event_id") == closing_log.get("event_id")
    if not anchor_is_closing_log and not event_matches_subject_norms(anchor, subject_norms, page_target_norms):
        excluded_events.append(
            revert_plan_event_summary(
                anchor,
                reason="anchor event target does not match closing log page subjects",
            )
        )
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": False,
            "previous_log_event": revert_plan_event_summary(previous_log) if previous_log is not None else None,
            "closing_log_event": revert_plan_event_summary(closing_log),
            "batch_start_after_event_sequence": start_sequence,
            "batch_end_event_sequence": event_sequence(closing_log),
            "log_page_subjects": subjects,
            "log_page_subject_norms": sorted(subject_norms),
            "candidate_event_ids": [],
            "revert_order_event_ids": [],
            "candidate_events": [],
            "excluded_events": excluded_events,
            "revertible": False,
            "reverted_events": [],
            "reason": "anchor event target does not match closing log page subjects",
        }

    candidates: list[dict[str, Any]] = []
    end_sequence = event_sequence(closing_log)
    batch_events = [
        event
        for event in events
        if start_sequence < event_sequence(event) <= end_sequence
    ]
    for event in batch_events:
        is_closing_log = event.get("event_id") == closing_log.get("event_id")
        if not is_closing_log and not event_matches_subject_norms(event, subject_norms, page_target_norms):
            excluded_events.append(
                revert_plan_event_summary(
                    event,
                    reason="event target does not match closing log page subjects",
                )
            )
            continue
        exclusion_reason = revert_plan_exclusion_reason(event, reverted_ids)
        if exclusion_reason:
            excluded_events.append(revert_plan_event_summary(event, reason=exclusion_reason))
            continue
        candidates.append(event)

    targets = sorted(candidates, key=event_sequence, reverse=True)
    check = check_revert_plan_revertible(store, targets)
    candidate_event_ids = [event["event_id"] for event in candidates]
    result: dict[str, Any] = {
        "project": project,
        "scope": args.scope,
        "anchor_event_id": anchor["event_id"],
        "anchor_event": revert_plan_event_summary(anchor),
        "complete": True,
        "previous_log_event": revert_plan_event_summary(previous_log) if previous_log is not None else None,
        "closing_log_event": revert_plan_event_summary(closing_log),
        "batch_start_after_event_sequence": start_sequence,
        "batch_end_event_sequence": end_sequence,
        "log_page_subjects": subjects,
        "log_page_subject_norms": sorted(subject_norms),
        "candidate_event_ids": candidate_event_ids,
        "revert_order_event_ids": [event["event_id"] for event in targets],
        "candidate_events": [revert_plan_event_summary(event) for event in candidates],
        "excluded_events": excluded_events,
        "revertible": check["revertible"],
        "reverted_events": check["reverted_events"],
    }
    if not candidate_event_ids:
        result["revertible"] = False
        result["reason"] = "log-page-subjects contains no active reversible events"
    if not check["revertible"]:
        result["reason"] = check["reason"]
    if args.output is not None and candidate_event_ids:
        result["suggested_revert_events_args"] = [
            "revert-events",
            *candidate_event_ids,
            "--output",
            str(args.output),
        ]
    return result


def content_subjects_revert_plan(
    store: SQLiteStore,
    args: argparse.Namespace,
    project: str,
    sqlite_events: list[dict[str, Any]],
    anchor: dict[str, Any],
) -> dict[str, Any]:
    events = sorted(sqlite_events, key=event_sequence)
    anchor_sequence = event_sequence(anchor)
    baseline_sequence = initial_baseline_end_sequence_before(events, anchor_sequence)
    closing_log = first_log_boundary_at_or_after(events, anchor_sequence)
    previous_log = (
        last_log_boundary_before(events, event_sequence(closing_log))
        if closing_log is not None
        else None
    )
    start_sequence = (
        max(event_sequence(previous_log), baseline_sequence)
        if previous_log is not None
        else baseline_sequence
    )
    end_sequence = event_sequence(closing_log) if closing_log is not None else event_sequence(events[-1])
    page_target_norms = event_page_target_norms_by_id(store, project)
    reverted_ids = reverted_target_event_ids(sqlite_events)
    excluded_events: list[dict[str, Any]] = []
    anchor_exclusion = revert_plan_exclusion_reason(anchor, reverted_ids)
    anchor_subjects = event_changed_content_subjects(anchor)
    anchor_subject_norms = {normalize_title(subject) for subject in anchor_subjects}
    anchor_target_norms = event_target_subject_norms(anchor, page_target_norms)
    if anchor_exclusion:
        excluded_events.append(revert_plan_event_summary(anchor, reason=anchor_exclusion))
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": bool(anchor_subject_norms),
            "previous_log_event": revert_plan_event_summary(previous_log) if previous_log is not None else None,
            "closing_log_event": revert_plan_event_summary(closing_log) if closing_log is not None else None,
            "content_subjects": anchor_subjects,
            "content_subject_norms": sorted(anchor_subject_norms),
            "anchor_target_norms": sorted(anchor_target_norms),
            "candidate_event_ids": [],
            "revert_order_event_ids": [],
            "candidate_events": [],
            "excluded_events": excluded_events,
            "revertible": False,
            "reverted_events": [],
            "reason": f"anchor event is not an active reversible target: {anchor_exclusion}",
        }
    if not anchor_subject_norms:
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": False,
            "previous_log_event": revert_plan_event_summary(previous_log) if previous_log is not None else None,
            "closing_log_event": revert_plan_event_summary(closing_log) if closing_log is not None else None,
            "content_subjects": anchor_subjects,
            "content_subject_norms": [],
            "anchor_target_norms": sorted(anchor_target_norms),
            "candidate_event_ids": [],
            "revert_order_event_ids": [],
            "candidate_events": [],
            "excluded_events": [],
            "revertible": False,
            "reverted_events": [],
            "reason": "anchor event changed lines have no wikilink or Markdown path subjects",
        }

    candidates: list[dict[str, Any]] = []
    for event in events:
        if not (start_sequence < event_sequence(event) <= end_sequence):
            continue
        event_changed_subjects = event_changed_content_subjects(event)
        event_changed_norms = {normalize_title(subject) for subject in event_changed_subjects}
        event_target_norms = event_target_subject_norms(event, page_target_norms)
        is_anchor = event.get("event_id") == anchor.get("event_id")
        matches_subject = bool(event_changed_norms & anchor_subject_norms)
        matches_target = bool(event_target_norms & anchor_subject_norms)
        mentions_anchor_target = bool(event_changed_norms & anchor_target_norms)
        if not (is_anchor or matches_subject or matches_target or mentions_anchor_target):
            excluded_events.append(
                revert_plan_event_summary(
                    event,
                    reason="event changed subjects and target do not overlap anchor content subjects",
                )
            )
            continue
        exclusion_reason = revert_plan_exclusion_reason(event, reverted_ids)
        if exclusion_reason:
            excluded_events.append(revert_plan_event_summary(event, reason=exclusion_reason))
            continue
        candidates.append(event)

    targets = sorted(candidates, key=event_sequence, reverse=True)
    check = check_revert_plan_revertible(store, targets)
    candidate_event_ids = [event["event_id"] for event in candidates]
    result: dict[str, Any] = {
        "project": project,
        "scope": args.scope,
        "anchor_event_id": anchor["event_id"],
        "anchor_event": revert_plan_event_summary(anchor),
        "complete": True,
        "previous_log_event": revert_plan_event_summary(previous_log) if previous_log is not None else None,
        "closing_log_event": revert_plan_event_summary(closing_log) if closing_log is not None else None,
        "content_start_after_event_sequence": start_sequence,
        "content_end_event_sequence": end_sequence,
        "content_subjects": anchor_subjects,
        "content_subject_norms": sorted(anchor_subject_norms),
        "anchor_target_norms": sorted(anchor_target_norms),
        "candidate_event_ids": candidate_event_ids,
        "revert_order_event_ids": [event["event_id"] for event in targets],
        "candidate_events": [revert_plan_event_summary(event) for event in candidates],
        "excluded_events": excluded_events,
        "revertible": check["revertible"],
        "reverted_events": check["reverted_events"],
    }
    if not candidate_event_ids:
        result["revertible"] = False
        result["reason"] = "content-subjects contains no active reversible events"
    if not check["revertible"]:
        result["reason"] = check["reason"]
    if args.output is not None and candidate_event_ids:
        result["suggested_revert_events_args"] = [
            "revert-events",
            *candidate_event_ids,
            "--output",
            str(args.output),
        ]
    return result


def same_page_dependents_revert_plan(
    store: SQLiteStore,
    args: argparse.Namespace,
    project: str,
    sqlite_events: list[dict[str, Any]],
    anchor: dict[str, Any],
) -> dict[str, Any]:
    reverted_ids = reverted_target_event_ids(sqlite_events)
    excluded_events: list[dict[str, Any]] = []
    anchor_exclusion = revert_plan_exclusion_reason(anchor, reverted_ids)
    if anchor_exclusion:
        excluded_events.append(revert_plan_event_summary(anchor, reason=anchor_exclusion))
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": True,
            "previous_log_event": None,
            "closing_log_event": None,
            "candidate_event_ids": [],
            "dependent_event_ids": [],
            "revert_order_event_ids": [],
            "candidate_events": [],
            "excluded_events": excluded_events,
            "revertible": False,
            "reverted_events": [],
            "reason": anchor_exclusion,
        }
    try:
        dependent_events = dependent_revert_events(sqlite_events, anchor)
    except ValueError as error:
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": False,
            "previous_log_event": None,
            "closing_log_event": None,
            "candidate_event_ids": [anchor["event_id"]],
            "dependent_event_ids": [],
            "revert_order_event_ids": [anchor["event_id"]],
            "candidate_events": [revert_plan_event_summary(anchor)],
            "excluded_events": excluded_events,
            "revertible": False,
            "reverted_events": [],
            "reason": str(error),
        }

    chronological_dependents = list(reversed(dependent_events))
    candidates = [anchor, *chronological_dependents]
    targets = [*dependent_events, anchor]
    check = check_revert_plan_revertible(store, targets)
    candidate_event_ids = [event["event_id"] for event in candidates]
    result: dict[str, Any] = {
        "project": project,
        "scope": args.scope,
        "anchor_event_id": anchor["event_id"],
        "anchor_event": revert_plan_event_summary(anchor),
        "complete": True,
        "previous_log_event": None,
        "closing_log_event": None,
        "candidate_event_ids": candidate_event_ids,
        "dependent_event_ids": [event["event_id"] for event in dependent_events],
        "revert_order_event_ids": [event["event_id"] for event in targets],
        "candidate_events": [revert_plan_event_summary(event) for event in candidates],
        "excluded_events": excluded_events,
        "revertible": check["revertible"],
        "reverted_events": check["reverted_events"],
    }
    if not check["revertible"]:
        result["reason"] = check["reason"]
    if args.output is not None and candidate_event_ids:
        result["suggested_revert_events_args"] = [
            "revert-events",
            *candidate_event_ids,
            "--output",
            str(args.output),
        ]
    return result


def event_window_revert_plan(
    store: SQLiteStore,
    args: argparse.Namespace,
    project: str,
    sqlite_events: list[dict[str, Any]],
    anchor: dict[str, Any],
) -> dict[str, Any]:
    before = int(args.before or 0)
    after = int(args.after or 0)
    if before < 0 or after < 0:
        raise ValueError("--before/--after must be non-negative")
    if before == 0 and after == 0:
        raise ValueError("--scope event-window requires --before or --after to be positive")

    events = sorted(sqlite_events, key=event_sequence)
    anchor_index = next(
        index
        for index, event in enumerate(events)
        if event.get("event_id") == anchor.get("event_id")
    )
    requested_start_index = anchor_index - before
    requested_end_index = anchor_index + after + 1
    start_index = max(0, requested_start_index)
    end_index = min(len(events), requested_end_index)
    window_events = events[start_index:end_index]
    complete = start_index == requested_start_index and end_index == requested_end_index
    reverted_ids = reverted_target_event_ids(sqlite_events)
    excluded_events: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    anchor_exclusion = revert_plan_exclusion_reason(anchor, reverted_ids)
    if anchor_exclusion:
        excluded_events.append(revert_plan_event_summary(anchor, reason=anchor_exclusion))
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": complete,
            "previous_log_event": None,
            "closing_log_event": None,
            "window_before": before,
            "window_after": after,
            "window_start_event_sequence": event_sequence(window_events[0]) if window_events else None,
            "window_end_event_sequence": event_sequence(window_events[-1]) if window_events else None,
            "candidate_event_ids": [],
            "revert_order_event_ids": [],
            "candidate_events": [],
            "excluded_events": excluded_events,
            "revertible": False,
            "reverted_events": [],
            "reason": f"anchor event is not an active reversible target: {anchor_exclusion}",
        }

    for event in window_events:
        exclusion_reason = revert_plan_exclusion_reason(event, reverted_ids)
        if exclusion_reason:
            excluded_events.append(revert_plan_event_summary(event, reason=exclusion_reason))
            continue
        candidates.append(event)

    targets = sorted(candidates, key=event_sequence, reverse=True)
    check = check_revert_plan_revertible(store, targets)
    candidate_event_ids = [event["event_id"] for event in candidates]
    result: dict[str, Any] = {
        "project": project,
        "scope": args.scope,
        "anchor_event_id": anchor["event_id"],
        "anchor_event": revert_plan_event_summary(anchor),
        "complete": complete,
        "previous_log_event": None,
        "closing_log_event": None,
        "window_before": before,
        "window_after": after,
        "window_start_event_sequence": event_sequence(window_events[0]) if window_events else None,
        "window_end_event_sequence": event_sequence(window_events[-1]) if window_events else None,
        "candidate_event_ids": candidate_event_ids,
        "revert_order_event_ids": [event["event_id"] for event in targets],
        "candidate_events": [revert_plan_event_summary(event) for event in candidates],
        "excluded_events": excluded_events,
        "revertible": check["revertible"],
        "reverted_events": check["reverted_events"],
    }
    if not complete:
        result["reason"] = "event-window clipped by SQLite event stream boundary"
    if not candidate_event_ids:
        result["revertible"] = False
        result["reason"] = "event-window contains no active reversible events"
    if not check["revertible"]:
        result["reason"] = check["reason"]
    if args.output is not None and candidate_event_ids:
        result["suggested_revert_events_args"] = [
            "revert-events",
            *candidate_event_ids,
            "--output",
            str(args.output),
        ]
    return result


def time_burst_revert_plan(
    store: SQLiteStore,
    args: argparse.Namespace,
    project: str,
    sqlite_events: list[dict[str, Any]],
    anchor: dict[str, Any],
) -> dict[str, Any]:
    max_gap_seconds = float(args.max_gap_seconds or 0)
    if not math.isfinite(max_gap_seconds) or max_gap_seconds <= 0:
        raise ValueError("--scope time-burst requires --max-gap-seconds to be a finite positive number")

    events = sorted(sqlite_events, key=event_sequence)
    anchor_index = next(
        index
        for index, event in enumerate(events)
        if event.get("event_id") == anchor.get("event_id")
    )
    reverted_ids = reverted_target_event_ids(sqlite_events)
    excluded_events: list[dict[str, Any]] = []
    anchor_exclusion = revert_plan_exclusion_reason(anchor, reverted_ids)
    if anchor_exclusion:
        excluded_events.append(revert_plan_event_summary(anchor, reason=anchor_exclusion))
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": True,
            "previous_log_event": None,
            "closing_log_event": None,
            "max_gap_seconds": max_gap_seconds,
            "candidate_event_ids": [],
            "revert_order_event_ids": [],
            "candidate_events": [],
            "excluded_events": excluded_events,
            "boundary_events": [],
            "revertible": False,
            "reverted_events": [],
            "reason": f"anchor event is not an active reversible target: {anchor_exclusion}",
        }

    start_index = anchor_index
    end_index = anchor_index + 1
    boundary_events: list[dict[str, Any]] = []

    while start_index > 0:
        outside = events[start_index - 1]
        current = events[start_index]
        boundary_reason = time_burst_boundary_reason(outside, current, max_gap_seconds, anchor)
        if boundary_reason:
            boundary_events.append(revert_plan_event_summary(outside, reason=boundary_reason))
            break
        start_index -= 1

    while end_index < len(events):
        previous = events[end_index - 1]
        outside = events[end_index]
        boundary_reason = time_burst_boundary_reason(previous, outside, max_gap_seconds, anchor)
        if boundary_reason:
            boundary_events.append(revert_plan_event_summary(outside, reason=boundary_reason))
            break
        end_index += 1

    burst_events = events[start_index:end_index]
    candidates: list[dict[str, Any]] = []
    for event in burst_events:
        exclusion_reason = revert_plan_exclusion_reason(event, reverted_ids)
        if exclusion_reason:
            excluded_events.append(revert_plan_event_summary(event, reason=exclusion_reason))
            continue
        candidates.append(event)

    targets = sorted(candidates, key=event_sequence, reverse=True)
    check = check_revert_plan_revertible(store, targets)
    candidate_event_ids = [event["event_id"] for event in candidates]
    result: dict[str, Any] = {
        "project": project,
        "scope": args.scope,
        "anchor_event_id": anchor["event_id"],
        "anchor_event": revert_plan_event_summary(anchor),
        "complete": True,
        "previous_log_event": None,
        "closing_log_event": None,
        "max_gap_seconds": max_gap_seconds,
        "burst_start_event_sequence": event_sequence(burst_events[0]) if burst_events else None,
        "burst_end_event_sequence": event_sequence(burst_events[-1]) if burst_events else None,
        "burst_start_created_at": burst_events[0].get("created_at") if burst_events else None,
        "burst_end_created_at": burst_events[-1].get("created_at") if burst_events else None,
        "candidate_event_ids": candidate_event_ids,
        "revert_order_event_ids": [event["event_id"] for event in targets],
        "candidate_events": [revert_plan_event_summary(event) for event in candidates],
        "excluded_events": excluded_events,
        "boundary_events": boundary_events,
        "revertible": check["revertible"],
        "reverted_events": check["reverted_events"],
    }
    if not candidate_event_ids:
        result["revertible"] = False
        result["reason"] = "time-burst contains no active reversible events"
    if not check["revertible"]:
        result["reason"] = check["reason"]
    if args.output is not None and candidate_event_ids:
        result["suggested_revert_events_args"] = [
            "revert-events",
            *candidate_event_ids,
            "--output",
            str(args.output),
        ]
    return result


def session_revert_plan(
    store: SQLiteStore,
    args: argparse.Namespace,
    project: str,
    sqlite_events: list[dict[str, Any]],
    anchor: dict[str, Any],
) -> dict[str, Any]:
    session_id = str(anchor.get("session_id") or "")
    session_actor = str(anchor.get("actor") or "")
    reverted_ids = reverted_target_event_ids(sqlite_events)
    excluded_events: list[dict[str, Any]] = []
    anchor_exclusion = revert_plan_exclusion_reason(anchor, reverted_ids)
    if anchor_exclusion:
        excluded_events.append(revert_plan_event_summary(anchor, reason=anchor_exclusion))
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": bool(session_id),
            "previous_log_event": None,
            "closing_log_event": None,
            "session_id": session_id,
            "session_actor": session_actor,
            "session_event_ids": [event["event_id"] for event in sqlite_events if event.get("session_id") == session_id] if session_id else [],
            "candidate_event_ids": [],
            "revert_order_event_ids": [],
            "candidate_events": [],
            "excluded_events": excluded_events,
            "revertible": False,
            "reverted_events": [],
            "reason": f"anchor event is not an active reversible target: {anchor_exclusion}",
        }
    if not session_id:
        return {
            "project": project,
            "scope": args.scope,
            "anchor_event_id": anchor["event_id"],
            "anchor_event": revert_plan_event_summary(anchor),
            "complete": False,
            "previous_log_event": None,
            "closing_log_event": None,
            "session_id": "",
            "session_actor": session_actor,
            "session_event_ids": [],
            "candidate_event_ids": [],
            "revert_order_event_ids": [],
            "candidate_events": [],
            "excluded_events": [],
            "revertible": False,
            "reverted_events": [],
            "reason": "anchor event has no session_id; write with --session-id or GRASP_SESSION_ID to enable session planning",
        }

    session_events = [
        event
        for event in sorted(sqlite_events, key=event_sequence)
        if event.get("session_id") == session_id
    ]
    candidates: list[dict[str, Any]] = []
    for event in session_events:
        exclusion_reason = revert_plan_exclusion_reason(event, reverted_ids)
        if exclusion_reason:
            excluded_events.append(revert_plan_event_summary(event, reason=exclusion_reason))
            continue
        candidates.append(event)

    targets = sorted(candidates, key=event_sequence, reverse=True)
    check = check_revert_plan_revertible(store, targets)
    candidate_event_ids = [event["event_id"] for event in candidates]
    result: dict[str, Any] = {
        "project": project,
        "scope": args.scope,
        "anchor_event_id": anchor["event_id"],
        "anchor_event": revert_plan_event_summary(anchor),
        "complete": True,
        "previous_log_event": None,
        "closing_log_event": None,
        "session_id": session_id,
        "session_actor": session_actor,
        "session_event_ids": [event["event_id"] for event in session_events],
        "session_start_event_sequence": event_sequence(session_events[0]) if session_events else None,
        "session_end_event_sequence": event_sequence(session_events[-1]) if session_events else None,
        "candidate_event_ids": candidate_event_ids,
        "revert_order_event_ids": [event["event_id"] for event in targets],
        "candidate_events": [revert_plan_event_summary(event) for event in candidates],
        "excluded_events": excluded_events,
        "revertible": check["revertible"],
        "reverted_events": check["reverted_events"],
    }
    if not candidate_event_ids:
        result["revertible"] = False
        result["reason"] = "session contains no active reversible events"
    if not check["revertible"]:
        result["reason"] = check["reason"]
    if args.output is not None and candidate_event_ids:
        result["suggested_revert_events_args"] = [
            "revert-events",
            *candidate_event_ids,
            "--output",
            str(args.output),
        ]
    return result


def log_append_event_subjects(event: dict[str, Any]) -> list[str]:
    payload = event.get("payload") or {}
    existing_subjects = [str(subject) for subject in payload.get("subjects") or []]
    if existing_subjects:
        subjects: list[str] = []
        seen: set[str] = set()
        for subject in existing_subjects:
            add_log_entry_subject(subjects, seen, subject)
        return subjects

    lines: list[dict[str, str]] = []
    heading = str(payload.get("heading") or "")
    if not heading and (payload.get("timestamp") or payload.get("op") or payload.get("summary")):
        heading = f"## [{payload.get('timestamp', '')}] {payload.get('op', '')} | {payload.get('summary', '')}"
    if heading:
        lines.append({"text": heading})
    for line in payload.get("lines") or []:
        lines.append({"text": str(line)})
    if not payload.get("lines"):
        for line in payload.get("inserted_lines") or []:
            if isinstance(line, dict):
                lines.append({"text": str(line.get("text") or "")})
            else:
                lines.append({"text": str(line)})
    return log_entry_subjects_from_lines(lines)


def log_page_update_event_subjects(event: dict[str, Any]) -> list[str]:
    return log_entry_subjects_from_lines(
        [{"text": text} for text in event_changed_content_line_texts(event)]
    )


def event_changed_content_subjects(event: dict[str, Any]) -> list[str]:
    return log_entry_subjects_from_lines(
        [{"text": text} for text in event_changed_content_line_texts(event)]
    )


def event_changed_content_line_texts(event: dict[str, Any]) -> list[str]:
    payload = event.get("payload") or {}
    event_type = event.get("event_type")
    if event_type == "page_create":
        return event_payload_line_texts(payload.get("lines") or [])
    if event_type in {"section_append", "log_append"}:
        if payload.get("inserted_lines"):
            return event_payload_line_texts(payload.get("inserted_lines") or [])
        return [str(line) for line in payload.get("lines") or []]
    if event_type != "page_update":
        return []
    previous_texts = event_payload_line_texts(payload.get("previous_lines") or [])
    current_texts = event_payload_line_texts(payload.get("lines") or [])
    changed_lines: list[str] = []
    matcher = SequenceMatcher(a=previous_texts, b=current_texts, autojunk=False)
    for tag, _old_start, _old_end, new_start, new_end in matcher.get_opcodes():
        if tag not in {"insert", "replace"}:
            continue
        for text in current_texts[new_start:new_end]:
            changed_lines.append(text)
    return changed_lines


def event_payload_line_texts(lines: list[Any]) -> list[str]:
    texts: list[str] = []
    for line in lines:
        if isinstance(line, dict):
            texts.append(str(line.get("text") or ""))
        else:
            texts.append(str(getattr(line, "text", line)))
    return texts


def event_matches_subject_norms(
    event: dict[str, Any],
    subject_norms: set[str],
    page_target_norms: dict[str, set[str]] | None = None,
) -> bool:
    return bool(event_target_subject_norms(event, page_target_norms) & subject_norms)


def event_page_target_norms_by_id(store: SQLiteStore, project: str) -> dict[str, set[str]]:
    rows = store.connection.execute(
        """
        SELECT
          page.id AS page_id,
          page.title AS title,
          handle.handle AS handle,
          handle.source_path AS source_path
        FROM pages page
        LEFT JOIN page_handles handle
          ON handle.project = page.project
         AND handle.page_id = page.id
        WHERE page.project = ?
        """,
        (project,),
    ).fetchall()
    targets_by_id: dict[str, set[str]] = {}
    for row in rows:
        page_id = str(row["page_id"] or "")
        if not page_id:
            continue
        targets = targets_by_id.setdefault(page_id, set())
        for raw_target in (row["title"], row["handle"]):
            if str(raw_target or "").strip():
                targets.add(normalize_title(str(raw_target)))
        raw_path = str(row["source_path"] or "")
        if raw_path:
            targets.add(normalize_title(Path(raw_path).stem))
    return targets_by_id


def event_targets_log_page(event: dict[str, Any]) -> bool:
    payload = event.get("payload") or {}
    for key in ("source_path", "previous_source_path"):
        raw_path = str(payload.get(key) or "")
        if raw_path and Path(raw_path).name.casefold() == "log.md":
            return True
    for key in ("title", "previous_title"):
        raw_title = str(payload.get(key) or "")
        if raw_title and normalize_title(raw_title) == "log":
            return True
    return False


def event_target_subject_norms(
    event: dict[str, Any],
    page_target_norms: dict[str, set[str]] | None = None,
) -> set[str]:
    payload = event.get("payload") or {}
    raw_targets = [
        payload.get("title"),
        payload.get("previous_title"),
    ]
    for key in ("source_path", "previous_source_path"):
        raw_path = payload.get(key)
        if raw_path:
            raw_targets.append(Path(str(raw_path)).stem)
    targets = {
        normalize_title(str(target))
        for target in raw_targets
        if str(target or "").strip()
    }
    page_id = str(payload.get("page_id") or "")
    if page_target_norms is not None and page_id:
        targets.update(page_target_norms.get(page_id, set()))
    return targets


def event_sequence(event: dict[str, Any]) -> int:
    return int(event.get("event_sequence") or 0)


def event_created_at_epoch(event: dict[str, Any]) -> float:
    value = str(event.get("created_at") or "")
    if not value:
        raise ValueError(f"event has no created_at timestamp: {event.get('event_id')}")
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"event has invalid created_at timestamp: {event.get('event_id')}: {event.get('created_at')}") from error
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.timestamp()


def event_time_gap_seconds(first: dict[str, Any], second: dict[str, Any]) -> float:
    return abs(event_created_at_epoch(second) - event_created_at_epoch(first))


def time_burst_boundary_reason(
    first: dict[str, Any],
    second: dict[str, Any],
    max_gap_seconds: float,
    anchor: dict[str, Any],
) -> str | None:
    if first.get("event_type") == "log_append" and first.get("event_id") != anchor.get("event_id"):
        return "log_append boundary"
    if second.get("event_type") == "log_append" and second.get("event_id") != anchor.get("event_id"):
        return "log_append boundary"
    gap_seconds = event_time_gap_seconds(first, second)
    if gap_seconds > max_gap_seconds:
        return f"time gap {gap_seconds:g}s exceeds max_gap_seconds {max_gap_seconds:g}"
    return None


def first_log_append_at_or_after(events: list[dict[str, Any]], sequence: int) -> dict[str, Any] | None:
    for event in events:
        if event_sequence(event) < sequence:
            continue
        if event.get("event_type") == "log_append":
            return event
    return None


def first_log_page_update_at_or_after(events: list[dict[str, Any]], sequence: int) -> dict[str, Any] | None:
    for event in events:
        if event_sequence(event) < sequence:
            continue
        if event.get("event_type") == "page_update" and event_targets_log_page(event):
            return event
    return None


def first_log_boundary_at_or_after(events: list[dict[str, Any]], sequence: int) -> dict[str, Any] | None:
    for event in events:
        if event_sequence(event) < sequence:
            continue
        if event.get("event_type") == "log_append" or (
            event.get("event_type") in {"page_create", "page_update"} and event_targets_log_page(event)
        ):
            return event
    return None


def last_log_append_before(events: list[dict[str, Any]], sequence: int) -> dict[str, Any] | None:
    previous: dict[str, Any] | None = None
    for event in events:
        if event_sequence(event) >= sequence:
            break
        if event.get("event_type") == "log_append":
            previous = event
    return previous


def last_log_boundary_before(events: list[dict[str, Any]], sequence: int) -> dict[str, Any] | None:
    previous: dict[str, Any] | None = None
    for event in events:
        if event_sequence(event) >= sequence:
            break
        if event.get("event_type") == "log_append" or (
            event.get("event_type") in {"page_create", "page_update"} and event_targets_log_page(event)
        ):
            previous = event
    return previous


def initial_baseline_end_sequence_before(events: list[dict[str, Any]], sequence: int) -> int:
    end_sequence = 0
    saw_log_entry_import = False
    for event in events:
        if event_sequence(event) >= sequence:
            break
        event_type = event.get("event_type")
        if (
            event_type == "page_create"
            and not saw_log_entry_import
            and event_is_initial_markdown_page_create(event)
        ):
            end_sequence = event_sequence(event)
            continue
        if event_type == "log_entry_import":
            saw_log_entry_import = True
            end_sequence = event_sequence(event)
            continue
        break
    return end_sequence


def event_is_initial_markdown_page_create(event: dict[str, Any]) -> bool:
    if event.get("event_type") != "page_create":
        return False
    payload = event.get("payload") or {}
    if not isinstance(payload, dict):
        return False
    if payload.get("source_hash"):
        return True
    if "message" in payload:
        return False
    return True


def revert_plan_exclusion_reason(event: dict[str, Any], reverted_ids: set[str]) -> str | None:
    event_id = str(event.get("event_id") or "")
    event_type = event.get("event_type")
    if event_type == "event_revert":
        return "event_revert records are rollback records, not rollback targets"
    if event_id in reverted_ids:
        return "event is already reverted"
    if event_type not in REVERSIBLE_EVENT_TYPES:
        return f"event_type is not reversible with this alpha command: {event_type}"
    return None


def revert_plan_event_summary(event: dict[str, Any] | None, *, reason: str | None = None) -> dict[str, Any]:
    if event is None:
        return {}
    payload = event.get("payload") or {}
    summary = {
        "event_id": event.get("event_id"),
        "event_sequence": event.get("event_sequence"),
        "event_type": event.get("event_type"),
        "created_at": event.get("created_at"),
        "title": payload.get("title") or payload.get("previous_title"),
        "page_id": payload.get("page_id"),
        "source_path": payload.get("source_path") or payload.get("previous_source_path"),
    }
    if payload.get("summary"):
        summary["summary"] = payload.get("summary")
    if event.get("actor"):
        summary["actor"] = event.get("actor")
    if event.get("session_id"):
        summary["session_id"] = event.get("session_id")
    if reason:
        summary["reason"] = reason
    return summary


def check_revert_plan_revertible(store: SQLiteStore, targets: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        with store.write_transaction():
            records: list[dict[str, Any]] = []
            for target in targets:
                rollback = revert_journal_event_in_store(store, target, reason="revert-plan dry-run", uncommitted=True)
                records.append({"target": target, "rollback": rollback, "event": None})
            result = {
                "revertible": True,
                "reverted_events": [
                    revert_record_summary(record, dry_run=True)
                    for record in records
                ],
            }
            raise RevertDryRunComplete(result)
    except RevertDryRunComplete as complete:
        return complete.result
    except ValueError as error:
        return {
            "revertible": False,
            "reverted_events": [],
            "reason": str(error),
        }


def run_revert_event_with_dependents(
    store: SQLiteStore,
    args: argparse.Namespace,
    *,
    journal: Path | None,
    target: dict[str, Any],
    target_source: str,
    sqlite_events: list[dict[str, Any]],
) -> dict[str, Any]:
    if target_source != "sqlite":
        reason = "--include-dependents requires a SQLite-sourced target event"
        if args.dry_run:
            return non_revertible_dry_run_result(
                args,
                journal=journal,
                project=target.get("project"),
                target=target,
                target_source=target_source,
                reason=reason,
            )
        raise ValueError(reason)
    try:
        dependent_events = dependent_revert_events(sqlite_events, target)
    except ValueError as error:
        if args.dry_run:
            return non_revertible_dry_run_result(
                args,
                journal=journal,
                project=target.get("project"),
                target=target,
                target_source=target_source,
                reason=str(error),
            )
        raise
    targets = [*dependent_events, target]
    if args.dry_run:
        return run_revert_event_sequence_dry_run(
            store,
            args,
            journal=journal,
            targets=targets,
            requested_target=target,
            dependent_events=dependent_events,
        )

    records: list[dict[str, Any]] = []
    with store.write_transaction():
        for current_target in targets:
            rollback = revert_journal_event_in_store(store, current_target, reason=args.reason, uncommitted=True)
            reverted = rollback["reverted"]
            event = make_journal_event(
                "event_revert",
                project=reverted["project"],
                payload=rollback["payload"],
            )
            insert_store_event(store.connection, event, **event_metadata(args))
            records.append({"target": current_target, "rollback": rollback, "event": event})
    if journal is not None:
        for record in records:
            append_journal_event(journal, record["event"])
    removed_files = remove_projection_files_for_revert_records(args.output, records)
    projection = store.export_markdown(args.output, check=False)
    projection["removed_files"] = removed_files
    projection["removed_count"] = len(removed_files)
    return revert_sequence_result(
        args,
        journal=journal,
        requested_target=target,
        target_source="sqlite",
        dependent_events=dependent_events,
        records=records,
        projection=projection,
        dry_run=False,
        journal_written=journal is not None,
    )


class RevertDryRunComplete(Exception):
    def __init__(self, result: dict[str, Any]):
        super().__init__("revert dry run complete")
        self.result = result


def dependent_revert_events(
    sqlite_events: list[dict[str, Any]],
    target: dict[str, Any],
) -> list[dict[str, Any]]:
    target_page_id = event_payload_page_id(target)
    if not target_page_id:
        raise ValueError("target event payload is missing page_id")
    target_sequence = int(target.get("event_sequence") or -1)
    reverted_event_ids = reverted_target_event_ids(sqlite_events)
    dependents: list[dict[str, Any]] = []
    for event in sqlite_events:
        sequence = int(event.get("event_sequence") or -1)
        if sequence <= target_sequence:
            continue
        event_type = event.get("event_type")
        if event_type == "event_revert":
            continue
        if event.get("event_id") in reverted_event_ids:
            continue
        if event_payload_page_id(event) != target_page_id:
            continue
        if event_type not in REVERSIBLE_EVENT_TYPES:
            raise ValueError(
                f"later same-page event is not reversible with this alpha command: {event.get('event_id')} ({event_type})"
            )
        dependents.append(event)
    return sorted(dependents, key=lambda event: int(event.get("event_sequence") or 0), reverse=True)


def reverted_target_event_ids(events: list[dict[str, Any]]) -> set[str]:
    return {
        str(event.get("payload", {}).get("target_event_id") or "")
        for event in events
        if event.get("event_type") == "event_revert"
    }


def event_payload_page_id(event: dict[str, Any]) -> str:
    return str(event.get("payload", {}).get("page_id") or "")


def run_revert_event_sequence_dry_run(
    store: SQLiteStore,
    args: argparse.Namespace,
    *,
    journal: Path | None,
    targets: list[dict[str, Any]],
    requested_target: dict[str, Any],
    dependent_events: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        with store.write_transaction():
            records: list[dict[str, Any]] = []
            for current_target in targets:
                rollback = revert_journal_event_in_store(store, current_target, reason=args.reason, uncommitted=True)
                records.append({"target": current_target, "rollback": rollback, "event": None})
            result = revert_sequence_result(
                args,
                journal=journal,
                requested_target=requested_target,
                target_source="sqlite",
                dependent_events=dependent_events,
                records=records,
                projection=None,
                dry_run=True,
                journal_written=False,
                would_remove_files=projection_files_removed_for_revert_records(args.output, records),
            )
            raise RevertDryRunComplete(result)
    except RevertDryRunComplete as complete:
        return complete.result
    except ValueError as error:
        return non_revertible_dry_run_result(
            args,
            journal=journal,
            project=requested_target.get("project"),
            target=requested_target,
            target_source="sqlite",
            reason=str(error),
        )


def revert_sequence_result(
    args: argparse.Namespace,
    *,
    journal: Path | None,
    requested_target: dict[str, Any],
    target_source: str,
    dependent_events: list[dict[str, Any]],
    records: list[dict[str, Any]],
    projection: dict[str, Any] | None,
    dry_run: bool,
    journal_written: bool,
    would_remove_files: list[str] | None = None,
) -> dict[str, Any]:
    requested_record = records[-1]
    reverted = requested_record["rollback"]["reverted"]
    result = dict(reverted)
    event_ids = [
        record["event"]["event_id"]
        for record in records
        if record.get("event") is not None
    ]
    result.update(
        {
            "journal": str(journal) if journal is not None else None,
            "journal_written": journal_written,
            "would_write_journal": journal is not None if dry_run else None,
            "output": str(args.output),
            "dry_run": dry_run,
            "revertible": True,
            "event_id": None if dry_run else event_ids[-1],
            "event_ids": event_ids,
            "would_event_type": "event_revert",
            "would_event_count": len(records) if dry_run else None,
            "reverted_event_count": 0 if dry_run else len(records),
            "target_event_id": requested_target["event_id"],
            "target_event_type": requested_target["event_type"],
            "target_event_source": target_source,
            "included_dependent_event_ids": [event["event_id"] for event in dependent_events],
            "included_dependent_count": len(dependent_events),
            "reverted_events": [
                revert_record_summary(record, dry_run=dry_run)
                for record in records
            ],
            "projection": projection,
            "would_export_projection": True if dry_run else None,
            "would_remove_files": would_remove_files if dry_run else None,
        }
    )
    if not dry_run:
        result.pop("would_write_journal", None)
        result.pop("would_event_count", None)
        result.pop("would_export_projection", None)
        result.pop("would_remove_files", None)
    return result


def revert_record_summary(record: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    target = record["target"]
    event = record.get("event")
    return {
        "event_id": None if dry_run or event is None else event["event_id"],
        "would_event_type": "event_revert",
        "target_event_id": target["event_id"],
        "target_event_type": target["event_type"],
        "target_event_source": "sqlite",
    }


def projection_files_removed_for_revert_records(output: Path, records: list[dict[str, Any]]) -> list[str]:
    removed: list[str] = []
    for record in records:
        target = record["target"]
        rollback = record["rollback"]
        for source_path in projection_files_removed_by_revert(
            output,
            target["event_type"],
            source_path=rollback["source_path"],
            previous_source_path=rollback["previous_source_path"],
        ):
            if source_path not in removed:
                removed.append(source_path)
    return removed


def remove_projection_files_for_revert_records(output: Path, records: list[dict[str, Any]]) -> list[str]:
    removed: list[str] = []
    for record in records:
        target = record["target"]
        rollback = record["rollback"]
        event_type = target["event_type"]
        if event_type == "page_rename":
            file_paths = remove_previous_projection_file(
                output,
                rollback["source_path"],
                rollback["previous_source_path"],
            )
        elif event_type == "page_create":
            file_paths = remove_projection_file(output, rollback["source_path"])
        else:
            file_paths = []
        for source_path in file_paths:
            if source_path not in removed:
                removed.append(source_path)
    return removed


def run_revert_event_dry_run(
    store: SQLiteStore,
    args: argparse.Namespace,
    *,
    journal: Path | None,
    target: dict[str, Any],
    target_source: str,
) -> dict[str, Any]:
    try:
        with store.write_transaction():
            rollback = revert_journal_event_in_store(store, target, reason=args.reason, uncommitted=True)
            reverted = rollback["reverted"]
            source_path = rollback["source_path"]
            previous_source_path = rollback["previous_source_path"]
            result = dict(reverted)
            result.update(
                {
                    "journal": str(journal) if journal is not None else None,
                    "journal_written": False,
                    "would_write_journal": journal is not None,
                    "output": str(args.output),
                    "dry_run": True,
                    "revertible": True,
                    "event_id": None,
                    "would_event_type": "event_revert",
                    "target_event_id": target["event_id"],
                    "target_event_type": target["event_type"],
                    "target_event_source": target_source,
                    "projection": None,
                    "would_export_projection": True,
                    "would_remove_files": projection_files_removed_by_revert(
                        args.output,
                        target["event_type"],
                        source_path=source_path,
                        previous_source_path=previous_source_path,
                    ),
                }
            )
            raise RevertDryRunComplete(result)
    except RevertDryRunComplete as complete:
        return complete.result
    except ValueError as error:
        return non_revertible_dry_run_result(
            args,
            journal=journal,
            project=target.get("project"),
            target=target,
            target_source=target_source,
            reason=str(error),
        )


def projection_files_removed_by_revert(
    output: Path,
    event_type: str,
    *,
    source_path: str,
    previous_source_path: str,
) -> list[str]:
    if event_type == "page_rename":
        return removable_previous_projection_file(output, source_path, previous_source_path)
    if event_type == "page_create":
        return removable_projection_file(output, source_path)
    return []


def removable_previous_projection_file(output: Path, previous_source_path: str, source_path: str) -> list[str]:
    if previous_source_path == source_path:
        return []
    previous = _safe_replay_output_path(output, previous_source_path)
    current = _safe_replay_output_path(output, source_path)
    if previous == current or not previous.exists():
        return []
    if previous.is_dir():
        raise ValueError(f"previous Markdown projection path is a directory: {previous_source_path}")
    return [previous_source_path]


def removable_projection_file(output: Path, source_path: str) -> list[str]:
    target = _safe_replay_output_path(output, source_path)
    if not target.exists():
        return []
    if target.is_dir():
        raise ValueError(f"Markdown projection path is a directory: {source_path}")
    return [source_path]


def non_revertible_dry_run_result(
    args: argparse.Namespace,
    *,
    journal: Path | None,
    project: str | None,
    target: dict[str, Any] | None,
    target_source: str | None,
    reason: str,
) -> dict[str, Any]:
    target = target or {}
    return {
        "project": project,
        "journal": str(journal) if journal is not None else None,
        "journal_written": False,
        "would_write_journal": False,
        "output": str(args.output),
        "dry_run": True,
        "revertible": False,
        "event_id": None,
        "would_event_type": "event_revert",
        "target_event_id": target.get("event_id", args.event_id),
        "target_event_type": target.get("event_type"),
        "target_event_source": target_source,
        "page": {},
        "projection": None,
        "would_export_projection": False,
        "would_remove_files": [],
        "reason": reason,
    }


def revert_journal_event_in_store(
    store: SQLiteStore,
    target: dict[str, Any],
    *,
    reason: str,
    uncommitted: bool = False,
) -> dict[str, Any]:
    payload = target["payload"]
    page_id = str(payload.get("page_id") or "")
    if not page_id:
        raise ValueError("target event payload is missing page_id")
    source_path = ""
    previous_source_path = ""
    if target["event_type"] == "page_create":
        current_lines = payload.get("lines")
        title = str(payload.get("title") or "")
        source_path = str(payload.get("source_path") or "")
        aliases = payload.get("aliases") or []
        if not isinstance(current_lines, list) or not title or not source_path or not isinstance(aliases, list):
            raise ValueError("page_create payload is incomplete")
        revert_page_create = (
            store._revert_markdown_page_create_uncommitted
            if uncommitted
            else store.revert_markdown_page_create
        )
        reverted = revert_page_create(
            page_id,
            title=title,
            source_path=source_path,
            aliases=[str(alias) for alias in aliases],
            current_lines=current_lines,
        )
        revert_payload = {
            "target_event_id": target["event_id"],
            "target_event_type": target["event_type"],
            "page_id": page_id,
            "title": title,
            "source_path": source_path,
            "aliases": aliases,
            "current_lines": current_lines,
            "removed_lines": reverted["removed_lines"],
            "reason": reason,
        }
    elif target["event_type"] == "page_update":
        previous_lines = payload.get("previous_lines")
        current_lines = payload.get("lines")
        if not isinstance(previous_lines, list) or not isinstance(current_lines, list):
            raise ValueError("page_update payload is missing previous_lines or lines")
        revert_page_update = (
            store._revert_markdown_page_update_uncommitted
            if uncommitted
            else store.revert_markdown_page_update
        )
        reverted = revert_page_update(page_id, previous_lines, current_lines)
        revert_payload = {
            "target_event_id": target["event_id"],
            "target_event_type": target["event_type"],
            "page_id": page_id,
            "title": payload.get("title") or reverted["page"].get("title"),
            "previous_lines": previous_lines,
            "current_lines": current_lines,
            "restored_lines": reverted["lines"],
            "reason": reason,
        }
    elif target["event_type"] == "page_rename":
        previous_lines = payload.get("previous_lines")
        current_lines = payload.get("lines")
        previous_aliases = payload.get("previous_aliases") or []
        aliases = payload.get("aliases") or []
        previous_title = str(payload.get("previous_title") or "")
        title = str(payload.get("title") or "")
        previous_source_path = str(payload.get("previous_source_path") or "")
        source_path = str(payload.get("source_path") or "")
        if (
            not previous_title
            or not title
            or not previous_source_path
            or not source_path
            or not isinstance(previous_lines, list)
            or not isinstance(current_lines, list)
            or not isinstance(previous_aliases, list)
            or not isinstance(aliases, list)
        ):
            raise ValueError("page_rename payload is incomplete")
        revert_page_rename = (
            store._revert_markdown_page_rename_uncommitted
            if uncommitted
            else store.revert_markdown_page_rename
        )
        reverted = revert_page_rename(
            page_id,
            previous_title=previous_title,
            title=title,
            previous_source_path=previous_source_path,
            source_path=source_path,
            previous_aliases=[str(alias) for alias in previous_aliases],
            aliases=[str(alias) for alias in aliases],
            previous_lines=previous_lines,
            current_lines=current_lines,
        )
        revert_payload = {
            "target_event_id": target["event_id"],
            "target_event_type": target["event_type"],
            "page_id": page_id,
            "previous_title": previous_title,
            "title": title,
            "previous_source_path": previous_source_path,
            "source_path": source_path,
            "previous_aliases": previous_aliases,
            "aliases": aliases,
            "previous_lines": previous_lines,
            "current_lines": current_lines,
            "restored_lines": reverted["lines"],
            "reason": reason,
        }
    else:
        inserted_lines = payload.get("inserted_lines")
        if not isinstance(inserted_lines, list):
            raise ValueError("target event payload is missing inserted_lines")
        revert_append = store._revert_markdown_append_uncommitted if uncommitted else store.revert_markdown_append
        reverted = revert_append(page_id, inserted_lines)
        revert_payload = {
            "target_event_id": target["event_id"],
            "target_event_type": target["event_type"],
            "page_id": page_id,
            "title": payload.get("title") or reverted["page"].get("title"),
            "removed_lines": reverted["removed_lines"],
            "reason": reason,
        }
    return {
        "reverted": reverted,
        "payload": revert_payload,
        "source_path": source_path,
        "previous_source_path": previous_source_path,
    }


def replay_journal_projection(
    journal: Path,
    output: Path,
    *,
    project: str | None,
    check: bool,
) -> dict[str, Any]:
    events = read_journal_events(journal)
    event_projects = {event["project"] for event in events}
    if project is None and len(event_projects) > 1:
        available = ", ".join(sorted(event_projects))
        raise ValueError(f"journal contains multiple projects; specify --project <name> (available: {available})")
    if project is not None and event_projects and project not in event_projects:
        available = ", ".join(sorted(event_projects))
        raise ValueError(f"project {project!r} is not present in journal (available: {available})")
    selected_project = project or (next(iter(event_projects)) if event_projects else None)
    pages: dict[str, dict[str, Any]] = {}
    applied_event_count = 0
    skipped_event_count = 0

    for event in events:
        if selected_project is not None and event["project"] != selected_project:
            skipped_event_count += 1
            continue
        payload = event["payload"]
        event_type = event["event_type"]
        if event_type == "page_create":
            page_id = str(payload.get("page_id") or "")
            source_path = str(payload.get("source_path") or "")
            lines = payload.get("lines")
            if not page_id or not source_path or not isinstance(lines, list):
                raise ValueError(f"invalid page_create payload in event {event['event_id']}")
            pages[page_id] = {
                "page_id": page_id,
                "title": str(payload.get("title") or ""),
                "aliases": [str(alias) for alias in payload.get("aliases") or []],
                "source_path": _safe_replay_relative_path(source_path),
                "lines": [_journal_line_for_replay(line) for line in lines],
            }
            applied_event_count += 1
        elif event_type in {"section_append", "log_append"}:
            page_id = str(payload.get("page_id") or "")
            inserted_lines = payload.get("inserted_lines")
            if page_id not in pages:
                raise ValueError(f"{event_type} references unknown page_id {page_id!r} in event {event['event_id']}")
            if not isinstance(inserted_lines, list):
                raise ValueError(f"{event_type} payload is missing inserted_lines in event {event['event_id']}")
            pages[page_id]["lines"].extend(_journal_line_for_replay(line) for line in inserted_lines)
            applied_event_count += 1
        elif event_type == "page_update":
            page_id = str(payload.get("page_id") or "")
            previous_lines = payload.get("previous_lines")
            lines = payload.get("lines")
            if page_id not in pages:
                raise ValueError(f"page_update references unknown page_id {page_id!r} in event {event['event_id']}")
            if not isinstance(previous_lines, list) or not isinstance(lines, list):
                raise ValueError(f"page_update payload is missing previous_lines or lines in event {event['event_id']}")
            expected_previous = [_journal_line_for_replay(line) for line in previous_lines]
            if not _journal_lines_match_for_replay(pages[page_id]["lines"], expected_previous):
                raise ValueError(f"page_update previous_lines do not match current page in event {event['event_id']}")
            pages[page_id]["lines"] = [_journal_line_for_replay(line) for line in lines]
            applied_event_count += 1
        elif event_type == "page_rename":
            page_id = str(payload.get("page_id") or "")
            previous_lines = payload.get("previous_lines")
            lines = payload.get("lines")
            previous_source_path = str(payload.get("previous_source_path") or "")
            source_path = str(payload.get("source_path") or "")
            title = str(payload.get("title") or "")
            if page_id not in pages:
                raise ValueError(f"page_rename references unknown page_id {page_id!r} in event {event['event_id']}")
            if not isinstance(previous_lines, list) or not isinstance(lines, list):
                raise ValueError(f"page_rename payload is missing previous_lines or lines in event {event['event_id']}")
            if not previous_source_path or not source_path or not title:
                raise ValueError(f"page_rename payload is missing title or source_path in event {event['event_id']}")
            if pages[page_id]["source_path"] != _safe_replay_relative_path(previous_source_path):
                raise ValueError(f"page_rename previous_source_path does not match current page in event {event['event_id']}")
            expected_previous = [_journal_line_for_replay(line) for line in previous_lines]
            if not _journal_lines_match_for_replay(pages[page_id]["lines"], expected_previous):
                raise ValueError(f"page_rename previous_lines do not match current page in event {event['event_id']}")
            pages[page_id]["title"] = title
            pages[page_id]["aliases"] = [str(alias) for alias in payload.get("aliases") or []]
            pages[page_id]["source_path"] = _safe_replay_relative_path(source_path)
            pages[page_id]["lines"] = [_journal_line_for_replay(line) for line in lines]
            applied_event_count += 1
        elif event_type == "event_revert":
            page_id = str(payload.get("page_id") or "")
            target_event_type = payload.get("target_event_type")
            if page_id not in pages:
                raise ValueError(f"event_revert references unknown page_id {page_id!r} in event {event['event_id']}")
            if target_event_type == "page_create":
                current_lines = payload.get("current_lines")
                source_path = str(payload.get("source_path") or "")
                title = str(payload.get("title") or "")
                if not isinstance(current_lines, list):
                    raise ValueError(f"event_revert payload is missing page_create lines in event {event['event_id']}")
                if not source_path or not title:
                    raise ValueError(f"event_revert payload is missing page_create title or source_path in event {event['event_id']}")
                if pages[page_id]["source_path"] != _safe_replay_relative_path(source_path):
                    raise ValueError(f"event_revert source_path does not match page in event {event['event_id']}")
                if pages[page_id]["title"] != title:
                    raise ValueError(f"event_revert title does not match page in event {event['event_id']}")
                aliases = [str(alias) for alias in payload.get("aliases") or []]
                if pages[page_id]["aliases"] != aliases:
                    raise ValueError(f"event_revert aliases do not match page in event {event['event_id']}")
                expected_current = [_journal_line_for_replay(line) for line in current_lines]
                if not _journal_lines_match_for_replay(pages[page_id]["lines"], expected_current):
                    raise ValueError(f"event_revert current_lines do not match page in event {event['event_id']}")
                del pages[page_id]
            elif target_event_type in {"section_append", "log_append"}:
                removed_lines = payload.get("removed_lines")
                if not isinstance(removed_lines, list) or not removed_lines:
                    raise ValueError(f"event_revert payload is missing removed_lines in event {event['event_id']}")
                expected_tail = [_journal_line_for_replay(line) for line in removed_lines]
                current_lines = pages[page_id]["lines"]
                if not _journal_lines_match_for_replay(current_lines[-len(expected_tail):], expected_tail):
                    raise ValueError(f"event_revert does not match page tail in event {event['event_id']}")
                del current_lines[-len(expected_tail):]
            elif target_event_type == "page_update":
                previous_lines = payload.get("previous_lines")
                current_lines = payload.get("current_lines")
                if not isinstance(previous_lines, list) or not isinstance(current_lines, list):
                    raise ValueError(f"event_revert payload is missing page_update lines in event {event['event_id']}")
                expected_current = [_journal_line_for_replay(line) for line in current_lines]
                if not _journal_lines_match_for_replay(pages[page_id]["lines"], expected_current):
                    raise ValueError(f"event_revert current_lines do not match page in event {event['event_id']}")
                pages[page_id]["lines"] = [_journal_line_for_replay(line) for line in previous_lines]
            elif target_event_type == "page_rename":
                previous_lines = payload.get("previous_lines")
                current_lines = payload.get("current_lines")
                previous_source_path = str(payload.get("previous_source_path") or "")
                source_path = str(payload.get("source_path") or "")
                previous_title = str(payload.get("previous_title") or "")
                if not isinstance(previous_lines, list) or not isinstance(current_lines, list):
                    raise ValueError(f"event_revert payload is missing page_rename lines in event {event['event_id']}")
                if not previous_source_path or not source_path or not previous_title:
                    raise ValueError(f"event_revert payload is missing page_rename title or source_path in event {event['event_id']}")
                if pages[page_id]["source_path"] != _safe_replay_relative_path(source_path):
                    raise ValueError(f"event_revert source_path does not match page in event {event['event_id']}")
                expected_current = [_journal_line_for_replay(line) for line in current_lines]
                if not _journal_lines_match_for_replay(pages[page_id]["lines"], expected_current):
                    raise ValueError(f"event_revert current_lines do not match page in event {event['event_id']}")
                pages[page_id]["title"] = previous_title
                pages[page_id]["aliases"] = [str(alias) for alias in payload.get("previous_aliases") or []]
                pages[page_id]["source_path"] = _safe_replay_relative_path(previous_source_path)
                pages[page_id]["lines"] = [_journal_line_for_replay(line) for line in previous_lines]
            else:
                raise ValueError(f"event_revert target_event_type is unsupported: {target_event_type!r}")
            applied_event_count += 1
        elif event_type == "projection_export":
            applied_event_count += 1
        elif event_type == "log_entry_import":
            applied_event_count += 1
        else:
            raise ValueError(f"replay-journal does not support event_type yet: {event_type}")

    projections = {
        page["source_path"]: _markdown_text_from_replay_page(page)
        for page in pages.values()
    }
    return _compare_or_write_replay_projection(
        projections,
        output,
        journal=journal,
        project=selected_project,
        check=check,
        event_count=len(events),
        applied_event_count=applied_event_count,
        skipped_event_count=skipped_event_count,
    )


def _journal_line_for_replay(line: Any) -> dict[str, Any]:
    if not isinstance(line, dict):
        raise ValueError("journal line payload must be an object")
    line_id = str(line.get("line_id") or "")
    if not line_id:
        raise ValueError("journal line payload is missing line_id")
    return {
        "line_id": line_id,
        "line_index": int(line.get("line_index", -1)),
        "text": str(line.get("text", "")),
    }


def _journal_lines_match_for_replay(actual: list[dict[str, Any]], expected: list[dict[str, Any]]) -> bool:
    if len(actual) != len(expected):
        return False
    return all(
        (int(left.get("line_index", -1)), str(left.get("text", "")))
        == (int(right.get("line_index", -1)), str(right.get("text", "")))
        for left, right in zip(actual, expected)
    )


def _markdown_text_from_replay_page(page: dict[str, Any]) -> str:
    return markdown_projection_text(
        page["source_path"],
        page_id=str(page["page_id"]),
        title=str(page.get("title") or ""),
        aliases=[str(alias) for alias in page.get("aliases") or []],
        lines=[str(line["text"]) for line in page["lines"]],
    )


def _safe_replay_relative_path(relative_path: str) -> str:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe journal source_path: {relative_path}")
    return path.as_posix()


def _safe_replay_output_path(output: Path, relative_path: str) -> Path:
    relative = Path(_safe_replay_relative_path(relative_path))
    return output / relative


def _compare_or_write_replay_projection(
    projections: dict[str, str],
    output: Path,
    *,
    journal: Path,
    project: str | None,
    check: bool,
    event_count: int,
    applied_event_count: int,
    skipped_event_count: int,
) -> dict[str, Any]:
    changed_files: list[str] = []
    missing_files: list[str] = []
    written_files: list[str] = []
    for relative_path, text in sorted(projections.items()):
        target = _safe_replay_output_path(output, relative_path)
        if not target.exists():
            missing_files.append(relative_path)
            if not check:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
                written_files.append(relative_path)
            continue
        current = target.read_text(encoding="utf-8")
        if current != text:
            changed_files.append(relative_path)
            if not check:
                target.write_text(text, encoding="utf-8")
                written_files.append(relative_path)

    existing_files = {
        path.relative_to(output).as_posix()
        for path in iter_markdown_files(output)
    } if output.exists() else set()
    extra_files = sorted(existing_files - set(projections))
    ok = not changed_files and not missing_files and not extra_files
    return {
        "project": project,
        "journal": str(journal),
        "output": str(output),
        "check": check,
        "ok": ok,
        "event_count": event_count,
        "applied_event_count": applied_event_count,
        "skipped_event_count": skipped_event_count,
        "file_count": len(projections),
        "checked_files": len(projections) if check else 0,
        "written_files": written_files,
        "written_count": len(written_files),
        "changed_files": sorted(changed_files),
        "missing_files": sorted(missing_files),
        "extra_files": extra_files,
    }


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

    if args.command == "adopt-markdown":
        project = args.adopt_project or args.project
        try:
            result = adopt_markdown(
                args.folder,
                args.store,
                project=project,
                journal_path=args.journal,
                replace_journal=args.replace_journal,
                exclude_dirs=tuple(args.markdown_exclude_dir),
                **event_metadata(args),
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

    if args.command == "import-log-records" and not args.store.exists():
        parser.error(store_missing_error(args.store))

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

    if args.command == "replay-journal":
        try:
            result = replay_journal_projection(
                args.journal,
                args.output,
                project=args.project,
                check=args.check,
            )
        except ValueError as error:
            parser.error(str(error))
        emit_result(args, result)
        if args.check and not result.get("ok"):
            return 1
        return 0

    if args.command in {"log-records", "history"}:
        store: SQLiteStore | None = None
        try:
            if args.store.exists():
                store = SQLiteStore(args.store, project=args.project, for_write=False)
                if not store.schema_ok():
                    store.close()
                    store = None
            result = run_log_records(args, store=store)
        except ValueError as error:
            parser.error(str(error))
        finally:
            if store is not None:
                store.close()
        emit_result(args, result)
        return 0

    if args.command == "acquire" and not args.store.exists():
        ensure_store_schema(args.store)

    if not args.store.exists():
        if args.command == "stats":
            emit_result(args, store_missing_stats(args.store))
            return 0
        parser.error(store_missing_error(args.store))

    store_for_write = args.command in STORE_WRITE_COMMANDS
    store: SQLiteStore | None = SQLiteStore(args.store, project=args.project, for_write=store_for_write)
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
            store = SQLiteStore(args.store, project=args.project, for_write=store_for_write)
        try:
            result = run_command(store, args)
        except GraspCliError as error:
            if args.json:
                emit_cli_error_result(error)
                return 2
            parser.error(str(error))
        except ValueError as error:
            parser.error(str(error))
    finally:
        if store is not None:
            store.close()
    emit_result(args, result)
    if args.command == "export-markdown" and args.check and not result.get("ok"):
        return 1
    if args.command == "write-status" and args.strict and not result.get("strict_ok"):
        return 1
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


def emit_cli_error_result(error: GraspCliError) -> None:
    result: dict[str, Any] = {"error": str(error)}
    if error.diagnostic is not None:
        result["diagnostic"] = error.diagnostic
    json.dump(result, sys.stderr, ensure_ascii=False, indent=2)
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
    if args.command == "export-markdown":
        return run_export_markdown(store, args)
    if args.command == "import-log-records":
        return run_import_log_records(store, args)
    if args.command == "append-section":
        return run_append_section(store, args)
    if args.command == "append-log":
        return run_append_log(store, args)
    if args.command == "write-page":
        return run_write_page(store, args)
    if args.command in {"rename-page", "rename"}:
        return run_rename_page(store, args)
    if args.command == "write-status":
        return run_write_status(store, args)
    if args.command == "revert-event":
        return run_revert_event(store, args)
    if args.command == "revert-events":
        return run_revert_events(store, args)
    if args.command == "revert-plan":
        return run_revert_plan(store, args)
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
    if command == "adopt-markdown":
        return format_adopt_markdown(result)
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
    if command == "export-markdown":
        return format_export_markdown(result)
    if command == "import-log-records":
        return format_import_log_records(result)
    if command in {"log-records", "history"}:
        return format_log_records(result)
    if command in {"append-section", "append-log"}:
        return format_append_result(result)
    if command == "write-page":
        return format_write_page_result(result)
    if command in {"rename-page", "rename"}:
        return format_rename_page_result(result)
    if command == "write-status":
        return format_write_status(result)
    if command == "revert-event":
        return format_revert_event(result)
    if command == "revert-events":
        return format_revert_events(result)
    if command == "revert-plan":
        return format_revert_plan(result)
    if command == "replay-journal":
        return format_replay_journal(result)
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


def format_adopt_markdown(result: dict[str, Any]) -> str:
    return (
        format_import(result)
        + f"journal: {result['journal']}\n"
        + f"journal_events: {result['journal_events']}\n"
        + f"sqlite_events_inserted: {result.get('sqlite_events_inserted', 0)}\n"
        + f"sqlite_events_skipped: {result.get('sqlite_events_skipped', 0)}\n"
        + f"adopted_pages: {result['adopted_pages']}\n"
    )


def format_export_markdown(result: dict[str, Any]) -> str:
    policy = result.get("projection_policy") or {}
    parts = [
        "# Markdown Projection\n",
        f"project: {result['project']}\n",
        f"output: {result['output']}\n",
        f"check: {str(result['check']).lower()}\n",
        f"authority: {policy.get('authority', '')}\n",
        f"base: {policy.get('base', '')}\n",
        f"output_role: {policy.get('output_role', '')}\n",
        f"write_mode: {policy.get('write_mode', '')}\n",
        f"ok: {str(result['ok']).lower()}\n",
        f"files: {result['file_count']}\n",
        f"written: {result['written_count']}\n",
    ]
    generated_overlays = policy.get("generated_overlays") or []
    if generated_overlays:
        parts.append("generated_overlays:\n")
        parts.extend(f"- {overlay}\n" for overlay in generated_overlays)
    if result.get("log_event_source"):
        parts.append(f"log_event_source: {result['log_event_source']}\n")
        parts.append(f"log_event_count: {result.get('log_event_count', 0)}\n")
    for key, label in (
        ("regenerated_files", "regenerated"),
        ("changed_files", "changed"),
        ("missing_files", "missing"),
        ("extra_files", "extra"),
        ("written_files", "written_files"),
    ):
        files = result.get(key) or []
        if files:
            parts.append(f"{label}:\n")
            parts.extend(f"- {path}\n" for path in files)
    return "".join(parts)


def format_import_log_records(result: dict[str, Any]) -> str:
    return (
        "# Log Records Import\n"
        f"project: {result['project']}\n"
        f"folder: {result['folder']}\n"
        f"journal: {result['journal']}\n"
        f"sqlite_events_inserted: {result.get('sqlite_events_inserted', 0)}\n"
        f"log_pages: {result['log_page_count']}\n"
        f"scanned_records: {result['scanned_records']}\n"
        f"imported_records: {result['imported_records']}\n"
        f"new_records: {result.get('new_records', result['imported_records'])}\n"
        f"updated_records: {result.get('updated_records', 0)}\n"
        f"skipped_records: {result['skipped_records']}\n"
    )


def format_log_records(result: dict[str, Any]) -> str:
    body_line_limit = int(result.get("body_lines", 3))
    parts = [
        "# Log Records\n",
        f"project: {result.get('project') or ''}\n",
        f"store: {result.get('store') or ''}\n",
        f"journal: {result['journal']}\n",
        f"event_source: {result.get('event_source', 'journal')}\n",
        f"query: {result.get('query') or ''}\n",
        f"total_records: {result['total_records']}\n",
        f"total_record_events: {result.get('total_record_events', result['total_records'])}\n",
        f"superseded_record_events: {result.get('superseded_record_events', 0)}\n",
        f"matched_records: {result['matched_records']}\n",
        f"returned_records: {result['returned_records']}\n",
        f"order: {result['order']}\n",
    ]
    records = result.get("records") or []
    if records:
        parts.append("records:\n")
    for record in records:
        parts.append(f"- [{record['timestamp']}] {record['op']} | {record['summary']}\n")
        parts.append(f"  record_id: {record['record_id']}\n")
        parts.append(f"  event_id: {record['event_id']}\n")
        parts.append(f"  content_fingerprint: {record.get('content_fingerprint', '')}\n")
        parts.append(f"  record_format: {record.get('record_format', 'section')}\n")
        if int(record.get("record_version_count", 1)) > 1:
            parts.append(f"  record_version: {record.get('record_version', 1)}/{record.get('record_version_count', 1)}\n")
        if record.get("superseded_by"):
            superseded_by = record["superseded_by"]
            parts.append(f"  superseded_by: {superseded_by.get('event_id', '')}\n")
        parts.append(f"  source_path: {record['source_path']}:{record['heading_line_index']}\n")
        if record.get("subjects"):
            parts.append(f"  subjects ({record.get('subject_source', 'heuristic')}): {', '.join(record['subjects'])}\n")
        if record.get("sources"):
            parts.append(f"  sources: {', '.join(record['sources'])}\n")
        later_event_count = int(record.get("later_event_count", 0))
        if later_event_count:
            parts.append(f"  later_events: {later_event_count}\n")
            for later_event in record.get("later_events") or []:
                shared_subjects = ", ".join(later_event.get("shared_subjects") or [])
                shared_suffix = f" ({shared_subjects})" if shared_subjects else ""
                parts.append(
                    f"    - [{later_event['timestamp']}] {later_event['op']} | {later_event['summary']}"
                    f"{shared_suffix}\n"
                )
            omitted = int(record.get("later_events_omitted", 0))
            if omitted > 0:
                parts.append(f"    ... {omitted} more later events\n")
        body_lines = record.get("body_lines") or []
        if body_line_limit > 0 and body_lines:
            parts.append("  body:\n")
            for line in body_lines[:body_line_limit]:
                parts.append(f"    {line.get('text', '')}\n")
            omitted = len(body_lines) - body_line_limit
            if omitted > 0:
                parts.append(f"    ... {omitted} more lines\n")
    return "".join(parts)


def format_append_result(result: dict[str, Any]) -> str:
    projection = result.get("projection") or {}
    journal = result.get("journal") or "(none)"
    return (
        "# Markdown Append\n"
        f"project: {result['project']}\n"
        f"page: {result['page']['title']}\n"
        f"journal: {journal}\n"
        f"journal_written: {str(result.get('journal_written', True)).lower()}\n"
        f"event_id: {result['event_id']}\n"
        f"appended_lines: {result['appended_line_count']}\n"
        f"edges: {result['edge_count']}\n"
        f"projection_written: {projection.get('written_count', 0)}\n"
    )


def format_write_page_result(result: dict[str, Any]) -> str:
    projection = result.get("projection") or {}
    journal = result.get("journal") or "(none)"
    return (
        "# Write Page\n"
        f"project: {result['project']}\n"
        f"page: {result['page']['title']}\n"
        f"journal: {journal}\n"
        f"journal_written: {str(result.get('journal_written', True)).lower()}\n"
        f"event_id: {result['event_id']}\n"
        f"event_type: {result.get('event_type', '')}\n"
        f"source_path: {result.get('source_path', '')}\n"
        f"previous_lines: {result['previous_line_count']}\n"
        f"lines: {result['line_count']}\n"
        f"edges: {result['edge_count']}\n"
        f"projection_written: {projection.get('written_count', 0)}\n"
    )


def format_rename_page_result(result: dict[str, Any]) -> str:
    projection = result.get("projection") or {}
    journal = result.get("journal") or "(none)"
    return (
        "# Rename Page\n"
        f"project: {result['project']}\n"
        f"page_id: {result['page']['id']}\n"
        f"previous_title: {result['previous_title']}\n"
        f"title: {result['title']}\n"
        f"previous_source_path: {result['previous_source_path']}\n"
        f"source_path: {result['source_path']}\n"
        f"journal: {journal}\n"
        f"journal_written: {str(result.get('journal_written', True)).lower()}\n"
        f"event_id: {result['event_id']}\n"
        f"heading_updated: {str(result['heading_updated']).lower()}\n"
        f"edges: {result['edge_count']}\n"
        f"projection_written: {projection.get('written_count', 0)}\n"
        f"projection_removed: {projection.get('removed_count', 0)}\n"
    )


def format_write_status(result: dict[str, Any]) -> str:
    projection = result["projection"]
    journal_log_projection = result.get("journal_log_projection") or {}
    semantic_log_projection = result.get("semantic_log_projection") or {}
    last_event = result.get("last_event") or {}
    sqlite_last_event = result.get("sqlite_last_event") or {}
    journal = result.get("journal") or "(none)"
    text = (
        "# Write Status\n"
        f"project: {result['project']}\n"
        f"output: {result['output']}\n"
        f"journal: {journal}\n"
        f"journal_required: {str(result.get('journal_required', True)).lower()}\n"
        f"journal_exists: {str(result['journal_exists']).lower()}\n"
        f"journal_events: {result['journal_event_count']}\n"
        f"journal_project_events: {result.get('journal_project_event_count', 0)}\n"
        f"journal_log_records: {result.get('journal_log_record_count', 0)}\n"
        f"last_event: {last_event.get('event_type', '')} {last_event.get('event_id', '')}\n"
        f"sqlite_events: {result.get('sqlite_event_count', 0)}\n"
        f"sqlite_last_event: {sqlite_last_event.get('event_type', '')} {sqlite_last_event.get('event_id', '')}\n"
        f"event_streams_match: {str(result.get('event_streams_match', False)).lower()}\n"
        f"projection_ok: {str(projection['ok']).lower()}\n"
        f"changed: {len(projection.get('changed_files') or [])}\n"
        f"missing: {len(projection.get('missing_files') or [])}\n"
        f"extra: {len(projection.get('extra_files') or [])}\n"
        f"strict_ok: {str(result.get('strict_ok', False)).lower()}\n"
    )
    if journal_log_projection:
        text += (
            f"journal_log_stale: {str(result.get('journal_log_stale', False)).lower()}\n"
            f"journal_log_changed: {len(result.get('journal_log_changed_files') or [])}\n"
        )
    elif result.get("journal_log_error"):
        text += f"journal_log_error: {result['journal_log_error']}\n"
    if semantic_log_projection:
        text += (
            f"semantic_log_stale: {str(result.get('semantic_log_stale', False)).lower()}\n"
            f"semantic_log_changed: {len(result.get('semantic_log_changed_files') or [])}\n"
            f"semantic_log_source: {semantic_log_projection.get('log_event_source', '')}\n"
        )
    elif result.get("semantic_log_error"):
        text += f"semantic_log_error: {result['semantic_log_error']}\n"
    failures = result.get("strict_failures") or []
    if failures:
        text += "strict_failures:\n"
        text += "".join(f"- {failure.get('type', '')}\n" for failure in failures)
    return text


def format_revert_event(result: dict[str, Any]) -> str:
    projection = result.get("projection") or {}
    line_count = result.get("removed_line_count", result.get("restored_line_count", 0))
    journal = result.get("journal") or "(none)"
    text = (
        "# Revert Event\n"
        f"project: {result['project']}\n"
        f"page: {result['page'].get('title', result['page'].get('id', ''))}\n"
        f"journal: {journal}\n"
        f"dry_run: {str(result.get('dry_run', False)).lower()}\n"
        f"revertible: {str(result.get('revertible', True)).lower()}\n"
        f"journal_written: {str(result.get('journal_written', True)).lower()}\n"
        f"event_id: {result['event_id']}\n"
        f"target_event_id: {result['target_event_id']}\n"
        f"target_event_type: {result['target_event_type']}\n"
        f"target_event_source: {result.get('target_event_source', '')}\n"
        f"lines: {line_count}\n"
        f"projection_written: {projection.get('written_count', 0)}\n"
    )
    if "included_dependent_count" in result:
        text += f"included_dependents: {result.get('included_dependent_count', 0)}\n"
    if result.get("reverted_event_count"):
        text += f"reverted_events: {result.get('reverted_event_count', 0)}\n"
    if result.get("dry_run"):
        if result.get("would_event_count"):
            text += f"would_events: {result.get('would_event_count', 0)}\n"
        text += f"would_write_journal: {str(result.get('would_write_journal', False)).lower()}\n"
        text += f"would_export_projection: {str(result.get('would_export_projection', False)).lower()}\n"
        would_remove_files = result.get("would_remove_files") or []
        text += f"would_remove_files: {len(would_remove_files)}\n"
        if result.get("reason"):
            text += f"reason: {result['reason']}\n"
    return text


def format_revert_events(result: dict[str, Any]) -> str:
    projection = result.get("projection") or {}
    journal = result.get("journal") or "(none)"
    text = (
        "# Revert Events\n"
        f"project: {result['project']}\n"
        f"journal: {journal}\n"
        f"dry_run: {str(result.get('dry_run', False)).lower()}\n"
        f"revertible: {str(result.get('revertible', True)).lower()}\n"
        f"journal_written: {str(result.get('journal_written', True)).lower()}\n"
        f"events: {len(result.get('target_event_ids') or [])}\n"
        f"reverted_events: {result.get('reverted_event_count', 0)}\n"
        f"projection_written: {projection.get('written_count', 0)}\n"
        f"projection_removed: {projection.get('removed_count', 0)}\n"
    )
    order = result.get("revert_order_event_ids") or []
    if order:
        text += "revert_order:\n"
        text += "".join(f"- {event_id}\n" for event_id in order)
    if result.get("dry_run"):
        text += f"would_events: {result.get('would_event_count', 0)}\n"
        text += f"would_write_journal: {str(result.get('would_write_journal', False)).lower()}\n"
        text += f"would_export_projection: {str(result.get('would_export_projection', False)).lower()}\n"
        text += f"would_remove_files: {len(result.get('would_remove_files') or [])}\n"
        if result.get("reason"):
            text += f"reason: {result['reason']}\n"
    return text


def format_revert_plan(result: dict[str, Any]) -> str:
    text = (
        "# Revert Plan\n"
        f"project: {result['project']}\n"
        f"scope: {result['scope']}\n"
        f"anchor_event: {result['anchor_event_id']}\n"
        f"complete: {str(result.get('complete', False)).lower()}\n"
        f"revertible: {str(result.get('revertible', False)).lower()}\n"
        f"candidate_events: {len(result.get('candidate_event_ids') or [])}\n"
    )
    if result.get("previous_log_event"):
        text += f"previous_log_event: {result['previous_log_event'].get('event_id')}\n"
    if result.get("closing_log_event"):
        text += f"closing_log_event: {result['closing_log_event'].get('event_id')}\n"
    if "window_before" in result or "window_after" in result:
        text += f"window: before={result.get('window_before', 0)} after={result.get('window_after', 0)}\n"
    if "max_gap_seconds" in result:
        text += f"time_burst_max_gap_seconds: {result.get('max_gap_seconds')}\n"
    if result.get("session_id"):
        text += f"session_id: {result.get('session_id')}\n"
        if result.get("session_actor"):
            text += f"session_actor: {result.get('session_actor')}\n"
    if result.get("subject_log_subjects"):
        text += "subject_log_subjects: " + ", ".join(result.get("subject_log_subjects") or []) + "\n"
    if result.get("log_page_subjects"):
        text += "log_page_subjects: " + ", ".join(result.get("log_page_subjects") or []) + "\n"
    if result.get("content_subjects"):
        text += "content_subjects: " + ", ".join(result.get("content_subjects") or []) + "\n"
    order = result.get("revert_order_event_ids") or []
    if order:
        text += "revert_order:\n"
        text += "".join(f"- {event_id}\n" for event_id in order)
    excluded = result.get("excluded_events") or []
    if excluded:
        text += "excluded:\n"
        text += "".join(f"- {event.get('event_id')} ({event.get('reason')})\n" for event in excluded)
    boundaries = result.get("boundary_events") or []
    if boundaries:
        text += "boundaries:\n"
        text += "".join(f"- {event.get('event_id')} ({event.get('reason')})\n" for event in boundaries)
    if result.get("suggested_revert_events_args"):
        text += "suggested_revert_events_args:\n"
        text += " ".join(result["suggested_revert_events_args"]) + "\n"
    if result.get("reason"):
        text += f"reason: {result['reason']}\n"
    return text


def format_replay_journal(result: dict[str, Any]) -> str:
    parts = [
        "# Replay Journal\n",
        f"project: {result['project'] or ''}\n",
        f"journal: {result['journal']}\n",
        f"output: {result['output']}\n",
        f"check: {str(result['check']).lower()}\n",
        f"ok: {str(result['ok']).lower()}\n",
        f"events: {result['applied_event_count']}/{result['event_count']}\n",
        f"files: {result['file_count']}\n",
        f"written: {result['written_count']}\n",
    ]
    for key, label in (
        ("changed_files", "changed"),
        ("missing_files", "missing"),
        ("extra_files", "extra"),
        ("written_files", "written_files"),
    ):
        files = result.get(key) or []
        if files:
            parts.append(f"{label}:\n")
            parts.extend(f"- {path}\n" for path in files)
    return "".join(parts)


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
