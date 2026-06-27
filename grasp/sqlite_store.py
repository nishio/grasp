from __future__ import annotations

from collections import Counter, deque
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape as escape_html
import difflib
import json
from pathlib import Path
import os
import shutil
import sqlite3
import time
import unicodedata
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from .journal import EVENT_TYPES, make_journal_event, read_journal_events, validate_journal_event
from .cosense import (
    CrossProjectLink,
    CosenseStore,
    Edge,
    Line,
    Page,
    edge_semantic_annotation,
    edge_semantic_annotation_from_fields,
    is_ascii_index_syntax,
    is_internal_cosense_link,
    normalize_title,
    parse_cosense_hash_tag,
    parse_cosense_cross_project_links,
    parse_cosense_links,
)
from .markdown import (
    MarkdownMirror,
    MarkdownPageRecord,
    first_markdown_h1_title,
    is_code_fence,
    iter_markdown_files,
    markdown_graph_role,
    markdown_graph_role_emits_edges,
    markdown_page_id,
    markdown_projection_text,
    markdown_title,
    markdown_wikilink_target,
    parse_frontmatter,
    parse_markdown_line_links,
    parse_markdown_links,
    parse_markdown_h1_title,
)


SCHEMA_VERSION = "8"
IMPORT_CACHE_MANIFEST_VERSION = 1
CANONICAL_STORE_ENV = "GRASP_CANONICAL_STORE"
SQLITE_BUSY_TIMEOUT_MS = 30_000
SQLITE_CONNECT_TIMEOUT_SECONDS = SQLITE_BUSY_TIMEOUT_MS / 1000
PYTHON_LOOSE_SEARCH_MAX_LINES = 50_000
STRUCTURAL_SPREAD_HANDLE_NORMS = frozenset(
    {
        "forest index",
        "index",
        "log",
        "overview",
        "readme",
        "wiki index",
        "wiki log",
    }
)


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE projects (
  name TEXT PRIMARY KEY,
  display_name TEXT NOT NULL DEFAULT '',
  source_export TEXT NOT NULL,
  exported INTEGER,
  imported_at INTEGER NOT NULL,
  pages INTEGER NOT NULL,
  lines INTEGER NOT NULL,
  edges INTEGER NOT NULL,
  unresolved_targets INTEGER NOT NULL
);

CREATE TABLE events (
  event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,
  schema_version INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  project TEXT NOT NULL,
  created_at TEXT NOT NULL,
  actor TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL
);

CREATE TABLE pages (
  project TEXT NOT NULL,
  id TEXT NOT NULL,
  title TEXT NOT NULL,
  norm_title TEXT NOT NULL,
  created INTEGER,
  updated INTEGER,
  views INTEGER NOT NULL DEFAULT 0,
  line_count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(project, id),
  FOREIGN KEY(project) REFERENCES projects(name) ON DELETE CASCADE
);

CREATE TABLE page_handles (
  project TEXT NOT NULL,
  handle_norm TEXT NOT NULL,
  page_id TEXT NOT NULL,
  handle TEXT NOT NULL,
  handle_source TEXT NOT NULL,
  source_path TEXT NOT NULL DEFAULT '',
  graph_role TEXT NOT NULL DEFAULT 'content',
  PRIMARY KEY(project, handle_norm, page_id, handle_source, handle),
  FOREIGN KEY(project) REFERENCES projects(name) ON DELETE CASCADE,
  FOREIGN KEY(project, page_id) REFERENCES pages(project, id) ON DELETE CASCADE
);

CREATE TABLE lines (
  project TEXT NOT NULL,
  line_id TEXT NOT NULL,
  page_id TEXT NOT NULL,
  line_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  created INTEGER,
  updated INTEGER,
  user_id TEXT,
  PRIMARY KEY(project, line_id),
  FOREIGN KEY(project) REFERENCES projects(name) ON DELETE CASCADE,
  FOREIGN KEY(project, page_id) REFERENCES pages(project, id) ON DELETE CASCADE
);

CREATE TABLE edges (
  id INTEGER PRIMARY KEY,
  project TEXT NOT NULL,
  source_page_id TEXT NOT NULL,
  line_id TEXT NOT NULL,
  target_title TEXT NOT NULL,
  target_norm TEXT NOT NULL,
  target_handle TEXT NOT NULL,
  target_handle_norm TEXT NOT NULL,
  target_page_id TEXT,
  resolution_status TEXT NOT NULL,
  FOREIGN KEY(project) REFERENCES projects(name) ON DELETE CASCADE,
  FOREIGN KEY(project, source_page_id) REFERENCES pages(project, id) ON DELETE CASCADE,
  FOREIGN KEY(project, line_id) REFERENCES lines(project, line_id) ON DELETE CASCADE
);

CREATE TABLE unresolved_targets (
  project TEXT NOT NULL,
  target_norm TEXT NOT NULL,
  title TEXT NOT NULL,
  link_count INTEGER NOT NULL,
  source_page_count INTEGER NOT NULL,
  total_source_views INTEGER NOT NULL,
  latest_source_updated INTEGER NOT NULL,
  PRIMARY KEY(project, target_norm),
  FOREIGN KEY(project) REFERENCES projects(name) ON DELETE CASCADE
);

CREATE TABLE unresolved_target_examples (
  project TEXT NOT NULL,
  target_norm TEXT NOT NULL,
  rank INTEGER NOT NULL,
  source_page_id TEXT NOT NULL,
  line_id TEXT NOT NULL,
  target_title TEXT NOT NULL,
  PRIMARY KEY(project, target_norm, rank),
  FOREIGN KEY(project) REFERENCES projects(name) ON DELETE CASCADE
);

CREATE INDEX idx_pages_project_norm_title ON pages(project, norm_title);
CREATE INDEX idx_pages_project_title ON pages(project, title);
CREATE INDEX idx_events_project_sequence ON events(project, event_sequence);
CREATE INDEX idx_events_project_type_sequence ON events(project, event_type, event_sequence);
CREATE INDEX idx_events_created_at ON events(created_at);
CREATE INDEX idx_page_handles_project_handle_norm ON page_handles(project, handle_norm);
CREATE INDEX idx_page_handles_project_source_path ON page_handles(project, source_path);
CREATE INDEX idx_lines_project_page_index ON lines(project, page_id, line_index);
CREATE INDEX idx_edges_project_target_norm ON edges(project, target_norm);
CREATE INDEX idx_edges_project_target_handle_norm ON edges(project, target_handle_norm);
CREATE INDEX idx_edges_project_target_page ON edges(project, target_page_id);
CREATE INDEX idx_edges_project_resolution ON edges(project, resolution_status);
CREATE INDEX idx_edges_project_source_page ON edges(project, source_page_id);
CREATE INDEX idx_edges_project_line ON edges(project, line_id);
CREATE INDEX idx_unresolved_targets_project_rank ON unresolved_targets(project, link_count DESC, source_page_count DESC, total_source_views DESC, latest_source_updated DESC, title);
CREATE INDEX idx_unresolved_target_examples_project_norm_rank ON unresolved_target_examples(project, target_norm, rank);
"""


def canonical_store_path(root: str | Path | None = None) -> Path:
    env_path = os.environ.get(CANONICAL_STORE_ENV)
    if env_path:
        return Path(env_path)
    if root is not None:
        return Path(root) / ".grasp" / "authority.sqlite"
    env_home = os.environ.get("GRASP_HOME")
    home = Path(env_home) if env_home else Path.home() / ".grasp"
    return home / "authority.sqlite"


def connect_sqlite_store(
    store_path: str | Path,
    *,
    row_factory: bool = False,
    for_write: bool = False,
    timeout: float | None = None,
    busy_timeout_ms: int = SQLITE_BUSY_TIMEOUT_MS,
) -> sqlite3.Connection:
    path = Path(store_path)
    if for_write:
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        path,
        timeout=SQLITE_CONNECT_TIMEOUT_SECONDS if timeout is None else timeout,
    )
    if row_factory:
        connection.row_factory = sqlite3.Row
    configure_sqlite_connection(
        connection,
        for_write=for_write,
        busy_timeout_ms=busy_timeout_ms,
    )
    return connection


def configure_sqlite_connection(
    connection: sqlite3.Connection,
    *,
    for_write: bool = False,
    busy_timeout_ms: int = SQLITE_BUSY_TIMEOUT_MS,
) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    busy_timeout_ms = max(0, int(busy_timeout_ms))
    connection.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
    if for_write:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")


@contextmanager
def sqlite_write_transaction(connection: sqlite3.Connection):
    if connection.in_transaction:
        raise RuntimeError("SQLite write transaction already active")
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()


def store_event_payload_json(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        raise ValueError("store event payload must be an object")
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def insert_store_event(
    connection: sqlite3.Connection,
    event: dict[str, Any],
    *,
    actor: str = "",
    session_id: str = "",
    if_exists: str = "error",
) -> bool:
    if if_exists not in {"error", "skip"}:
        raise ValueError(f"unsupported event duplicate policy: {if_exists!r}")
    validate_journal_event(event)
    project = normalize_project_name(event["project"])
    if not project:
        raise ValueError("store event requires non-empty project")
    payload_json = store_event_payload_json(event["payload"])
    try:
        connection.execute(
            """
            INSERT INTO events (
              event_id,
              schema_version,
              event_type,
              project,
              created_at,
              actor,
              session_id,
              payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                int(event["schema_version"]),
                event["event_type"],
                project,
                event["created_at"],
                str(actor or ""),
                str(session_id or ""),
                payload_json,
            ),
        )
    except sqlite3.IntegrityError:
        if if_exists == "skip" and _store_event_exists(connection, str(event["event_id"])):
            return False
        raise
    return True


def store_event_from_row(row: sqlite3.Row) -> dict[str, Any]:
    try:
        payload = json.loads(row["payload_json"])
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid store event payload JSON for {row['event_id']}: {exc}") from exc
    event = {
        "schema_version": int(row["schema_version"]),
        "event_id": row["event_id"],
        "event_type": row["event_type"],
        "project": row["project"],
        "created_at": row["created_at"],
        "payload": payload,
    }
    validate_journal_event(event)
    event["event_sequence"] = row["event_sequence"]
    event["actor"] = row["actor"]
    event["session_id"] = row["session_id"]
    return event


def _store_event_exists(connection: sqlite3.Connection, event_id: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM events WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    return row is not None


def import_export_to_sqlite(
    export_path: str | Path,
    store_path: str | Path,
    *,
    project_name: str | None = None,
) -> dict[str, Any]:
    export_path = Path(export_path)
    store_path = Path(store_path)
    source = CosenseStore.from_cosense_export(export_path)
    project = normalize_project_name(project_name or source.project_name or export_path.stem)
    if not project:
        raise ValueError(f"could not determine project name for export: {export_path}")

    ensure_store_schema(store_path)
    connection = connect_sqlite_store(store_path, for_write=True)
    try:
        with connection:
            _delete_project(connection, project)
            connection.execute(
                """
                INSERT INTO projects (
                  name,
                  display_name,
                  source_export,
                  exported,
                  imported_at,
                  pages,
                  lines,
                  edges,
                  unresolved_targets
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    project,
                    source.display_name or project,
                    str(export_path),
                    _int_or_none(source.exported),
                    int(time.time()),
                    len(source.pages),
                    sum(page.line_count for page in source.pages),
                    len(source.edges),
                ),
            )
            connection.executemany(
                """
                INSERT INTO pages (project, id, title, norm_title, created, updated, views, line_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        project,
                        page.id,
                        page.title,
                        page.norm_title,
                        page.created,
                        page.updated,
                        page.views,
                        page.line_count,
                    )
                    for page in source.pages
                ),
            )
            _insert_page_handles(connection, _page_handle_rows_for_pages(project, source.pages))
            connection.executemany(
                """
                INSERT INTO lines (project, line_id, page_id, line_index, text, created, updated, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        project,
                        line.line_id,
                        page.id,
                        line.index,
                        line.text,
                        line.created,
                        line.updated,
                        line.user_id,
                    )
                    for page in source.pages
                    for line in page.lines
                ),
            )
            _insert_edges(connection, project, source.edges)
            refresh_edge_resolutions(connection, project)
            rebuild_unresolved_targets(connection, project)
            unresolved_count = connection.execute(
                "SELECT COUNT(*) FROM unresolved_targets WHERE project = ?",
                (project,),
            ).fetchone()[0]
            connection.execute(
                """
                UPDATE projects
                SET unresolved_targets = ?
                WHERE name = ?
                """,
                (unresolved_count, project),
            )
            _write_metadata(
                connection,
                {
                    "schema_version": SCHEMA_VERSION,
                    "last_imported_project": project,
                    "last_source_export": str(export_path),
                    "last_source_type": "cosense",
                    "last_imported_at": str(int(time.time())),
                    f"project.{project}.source_type": "cosense",
                    f"project.{project}.title_aliases": "{}",
                },
            )
    finally:
        connection.close()

    _cache_import_source(export_path, store_path, project)
    store = SQLiteStore(store_path, project=project)
    try:
        return store.stats()
    finally:
        store.close()


def import_markdown_folder_to_sqlite(
    folder_path: str | Path,
    store_path: str | Path,
    *,
    project_name: str | None = None,
    exclude_dirs: tuple[str, ...] = (),
) -> dict[str, Any]:
    folder_path = Path(folder_path)
    store_path = Path(store_path)
    source = MarkdownMirror.from_folder(folder_path, exclude_dirs=exclude_dirs)
    project = normalize_project_name(project_name or source.project_name or folder_path.name)
    if not project:
        raise ValueError(f"could not determine project name for Markdown folder: {folder_path}")

    ensure_store_schema(store_path)
    connection = connect_sqlite_store(store_path, for_write=True)
    import_summary: dict[str, Any] = {}
    try:
        with connection:
            now = int(time.time())
            metadata = _connection_metadata(connection)
            old_manifest = _json_metadata(metadata, f"project.{project}.markdown_manifest")
            old_aliases = _json_metadata(metadata, f"project.{project}.title_aliases") or {}
            full_rebuild_reason = _markdown_full_rebuild_reason(
                project_exists=_project_exists(connection, project),
                old_source_type=metadata.get(f"project.{project}.source_type"),
                old_manifest=old_manifest,
                new_manifest=source.file_manifest,
                old_aliases=old_aliases,
                new_aliases=source.title_aliases,
            )

            if full_rebuild_reason is not None:
                _delete_project(connection, project)
                _insert_markdown_project(connection, project, source, folder_path, now)
                refresh_edge_resolutions(connection, project)
                rebuild_unresolved_targets(connection, project)
                unresolved_count = connection.execute(
                    "SELECT COUNT(*) FROM unresolved_targets WHERE project = ?",
                    (project,),
                ).fetchone()[0]
                connection.execute(
                    """
                    UPDATE projects
                    SET unresolved_targets = ?
                    WHERE name = ?
                    """,
                    (unresolved_count, project),
                )
                import_summary = {
                    "mode": "full",
                    "changed_files": len(source.records),
                    "full_rebuild_reason": full_rebuild_reason,
                }
            else:
                changed_paths = _changed_markdown_paths(old_manifest, source.file_manifest)
                records_by_path = {record.relative_path.as_posix(): record for record in source.records}
                edges_by_page_id = _markdown_edges_by_page_id(source.edges)
                for relative_path in changed_paths:
                    record = records_by_path[relative_path]
                    _replace_markdown_record(
                        connection,
                        project,
                        record,
                        edges_by_page_id.get(record.page.id, []),
                    )
                if changed_paths:
                    refresh_edge_resolutions(connection, project)
                    rebuild_unresolved_targets(connection, project)
                    _refresh_project_counts_sql(connection, project)
                    connection.execute(
                        """
                        UPDATE projects
                        SET display_name = ?, source_export = ?, imported_at = ?
                        WHERE name = ?
                        """,
                        (source.display_name or project, str(folder_path), now, project),
                    )
                import_summary = {
                    "mode": "incremental",
                    "changed_files": len(changed_paths),
                    "full_rebuild_reason": None,
                }

            _write_metadata(
                connection,
                {
                    "schema_version": SCHEMA_VERSION,
                    "last_imported_project": project,
                    "last_source_export": str(folder_path),
                    "last_source_type": "markdown",
                    "last_imported_at": str(now),
                    f"project.{project}.source_type": "markdown",
                    f"project.{project}.title_aliases": json.dumps(
                        source.title_aliases,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    f"project.{project}.markdown_manifest": json.dumps(
                        source.file_manifest,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    f"project.{project}.markdown_last_import": json.dumps(
                        import_summary,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            )
    finally:
        connection.close()

    _cache_import_source(folder_path, store_path, project, source_type="markdown", exclude_dirs=exclude_dirs)
    store = SQLiteStore(store_path, project=project)
    try:
        stats = store.stats()
        stats["markdown_import"] = import_summary
        return stats
    finally:
        store.close()


def ensure_store_schema(store_path: str | Path) -> None:
    store_path = Path(store_path)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    if store_path.exists() and _store_schema_version(store_path) == SCHEMA_VERSION:
        return

    tmp_path = store_path.with_name(f"{store_path.name}.tmp")
    if tmp_path.exists():
        tmp_path.unlink()
    connection = sqlite3.connect(tmp_path)
    try:
        connection.executescript(SCHEMA)
        _write_metadata(connection, {"schema_version": SCHEMA_VERSION})
        connection.commit()
    finally:
        connection.close()
    os.replace(tmp_path, store_path)


def _store_schema_version(store_path: Path) -> str | None:
    try:
        connection = sqlite3.connect(store_path)
        try:
            row = connection.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()
            return None if row is None else str(row[0])
        finally:
            connection.close()
    except sqlite3.Error:
        return None


def recover_store_from_import_cache(store_path: str | Path) -> bool:
    """Rebuild an outdated store from cached import JSONs kept beside it."""
    store_path = Path(store_path)
    if _store_schema_version(store_path) == SCHEMA_VERSION:
        return True

    sources = _cached_import_sources(store_path)
    if not sources:
        metadata = _read_metadata_if_possible(store_path)
        source_export = metadata.get("last_source_export") or metadata.get("source_export")
        last_project = metadata.get("last_imported_project")
        source_type = metadata.get(f"project.{last_project}.source_type") or metadata.get("last_source_type")
        old_manifest = _json_metadata(metadata, f"project.{last_project}.markdown_manifest") if last_project else None
        exclude_dirs = old_manifest.get("exclude_dirs") if old_manifest else ()
        if source_export and Path(source_export).exists():
            sources = [
                {
                    "project": last_project,
                    "path": source_export,
                    "source_export": source_export,
                    "source_type": source_type or "cosense",
                    "exclude_dirs": exclude_dirs if isinstance(exclude_dirs, list) else (),
                }
            ]

    if not sources:
        return False

    for source in sources:
        source_path = Path(source["path"])
        if not source_path.exists():
            return False
    for source in sources:
        if source.get("source_type") == "markdown":
            import_markdown_folder_to_sqlite(
                source["path"],
                store_path,
                project_name=source.get("project") or None,
                exclude_dirs=tuple(source.get("exclude_dirs") or ()),
            )
        else:
            import_export_to_sqlite(
                source["path"],
                store_path,
                project_name=source.get("project") or None,
            )
    return _store_schema_version(store_path) == SCHEMA_VERSION


def import_cache_dir(store_path: str | Path) -> Path:
    store_path = Path(store_path)
    return store_path.with_name(f"{store_path.name}.imports")


def import_cache_manifest_path(store_path: str | Path) -> Path:
    return import_cache_dir(store_path) / "manifest.json"


def _cache_import_source(
    source_path: Path,
    store_path: Path,
    project: str,
    *,
    source_type: str = "cosense",
    exclude_dirs: tuple[str, ...] = (),
) -> None:
    cache_dir = import_cache_dir(store_path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    if source_type == "cosense":
        cache_path = cache_dir / f"{quote(project, safe='') or '_default'}.cosense.json"
        tmp_path = cache_path.with_name(f"{cache_path.name}.tmp")

        try:
            same_file = source_path.resolve() == cache_path.resolve()
        except FileNotFoundError:
            same_file = False
        if not same_file:
            shutil.copyfile(source_path, tmp_path)
            os.replace(tmp_path, cache_path)
    else:
        cache_path = source_path

    manifest = _read_import_cache_manifest(store_path)
    projects = manifest.setdefault("projects", {})
    now = int(time.time())
    projects[project] = {
        "project": project,
        "path": str(cache_path),
        "source_export": str(source_path),
        "source_type": source_type,
        "exclude_dirs": list(exclude_dirs),
        "cached_at": now,
    }
    manifest["version"] = IMPORT_CACHE_MANIFEST_VERSION
    manifest["last_imported_project"] = project
    manifest["last_cached_at"] = now
    _write_import_cache_manifest(store_path, manifest)


def _cached_import_sources(store_path: Path) -> list[dict[str, Any]]:
    manifest = _read_import_cache_manifest(store_path)
    projects = manifest.get("projects")
    if isinstance(projects, dict):
        sources = []
        for project in sorted(projects):
            item = projects[project]
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            if path:
                sources.append(
                    {
                        "project": item.get("project") or project,
                        "path": path,
                        "source_export": item.get("source_export"),
                        "source_type": item.get("source_type") or "cosense",
                        "exclude_dirs": item.get("exclude_dirs") or (),
                    }
                )
        if sources:
            return sources

    cache_dir = import_cache_dir(store_path)
    return [
        {"project": None, "path": str(path), "source_export": None, "source_type": "cosense"}
        for path in sorted(cache_dir.glob("*.cosense.json"))
    ]


def _read_import_cache_manifest(store_path: str | Path) -> dict[str, Any]:
    manifest_path = import_cache_manifest_path(store_path)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": IMPORT_CACHE_MANIFEST_VERSION, "projects": {}}
    if not isinstance(data, dict):
        return {"version": IMPORT_CACHE_MANIFEST_VERSION, "projects": {}}
    if not isinstance(data.get("projects"), dict):
        data["projects"] = {}
    return data


def _write_import_cache_manifest(store_path: str | Path, manifest: dict[str, Any]) -> None:
    manifest_path = import_cache_manifest_path(store_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = manifest_path.with_name(f"{manifest_path.name}.tmp")
    tmp_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, manifest_path)


def _read_metadata_if_possible(store_path: Path) -> dict[str, str]:
    if not store_path.exists():
        return {}
    try:
        connection = sqlite3.connect(store_path)
        connection.row_factory = sqlite3.Row
        try:
            return {
                str(row["key"]): str(row["value"])
                for row in connection.execute("SELECT key, value FROM metadata")
            }
        finally:
            connection.close()
    except sqlite3.Error:
        return {}


def normalize_project_name(project_name: str) -> str:
    return project_name.strip()


def _delete_project(connection: sqlite3.Connection, project: str) -> None:
    connection.execute("DELETE FROM unresolved_target_examples WHERE project = ?", (project,))
    connection.execute("DELETE FROM unresolved_targets WHERE project = ?", (project,))
    connection.execute("DELETE FROM edges WHERE project = ?", (project,))
    connection.execute("DELETE FROM lines WHERE project = ?", (project,))
    connection.execute("DELETE FROM page_handles WHERE project = ?", (project,))
    connection.execute("DELETE FROM pages WHERE project = ?", (project,))
    connection.execute("DELETE FROM projects WHERE name = ?", (project,))


def _project_exists(connection: sqlite3.Connection, project: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM projects WHERE name = ?",
        (project,),
    ).fetchone()
    return row is not None


def _insert_page_handles(connection: sqlite3.Connection, rows: list[tuple[str, str, str, str, str, str, str]]) -> None:
    connection.executemany(
        """
        INSERT OR IGNORE INTO page_handles (
          project,
          handle_norm,
          page_id,
          handle,
          handle_source,
          source_path,
          graph_role
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def _page_handle_rows_for_pages(project: str, pages: list[Page]) -> list[tuple[str, str, str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str, str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for page in pages:
        key = (project, page.norm_title, page.id, "title", page.title)
        if page.norm_title and key not in seen:
            rows.append((project, page.norm_title, page.id, page.title, "title", "", "content"))
            seen.add(key)
    return rows


def _page_handle_rows_for_markdown_records(
    project: str,
    records: list[MarkdownPageRecord],
) -> list[tuple[str, str, str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str, str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for record in records:
        page = record.page
        source_path = record.relative_path.as_posix()
        handles = [("title", page.title), *(("alias", alias) for alias in record.aliases)]
        for handle_source, handle in handles:
            handle_norm = normalize_title(handle)
            key = (project, handle_norm, page.id, handle_source, handle)
            if not handle_norm or key in seen:
                continue
            rows.append((project, handle_norm, page.id, handle, handle_source, source_path, record.graph_role))
            seen.add(key)
    return rows


def _page_handle_rows_for_markdown_page(
    project: str,
    *,
    page_id: str,
    title: str,
    aliases: list[str],
    source_path: str,
    graph_role: str,
) -> list[tuple[str, str, str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str, str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    handles = [("title", title), *(("alias", alias) for alias in aliases)]
    for handle_source, handle in handles:
        handle_norm = normalize_title(handle)
        key = (project, handle_norm, page_id, handle_source, handle)
        if not handle_norm or key in seen:
            continue
        rows.append((project, handle_norm, page_id, handle, handle_source, source_path, graph_role))
        seen.add(key)
    return rows


def _insert_edges(connection: sqlite3.Connection, project: str, edges: list[Edge]) -> None:
    connection.executemany(
        """
        INSERT INTO edges (
          project,
          source_page_id,
          line_id,
          target_title,
          target_norm,
          target_handle,
          target_handle_norm,
          target_page_id,
          resolution_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                project,
                edge.source_page_id,
                edge.line_id,
                edge.target_title,
                edge.target_norm,
                edge.target_handle or edge.target_title,
                edge.target_handle_norm or normalize_title(edge.target_handle or edge.target_title),
                edge.target_page_id,
                edge.resolution_status,
            )
            for edge in edges
        ),
    )


def _insert_edge_rows(connection: sqlite3.Connection, rows: list[tuple[str, str, str, str, str]]) -> None:
    connection.executemany(
        """
        INSERT INTO edges (
          project,
          source_page_id,
          line_id,
          target_title,
          target_norm,
          target_handle,
          target_handle_norm,
          target_page_id,
          resolution_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'unresolved')
        """,
        (
            (
                project,
                source_page_id,
                line_id,
                target_title,
                normalize_title(target_title),
                target_title,
                normalize_title(target_title),
            )
            for project, source_page_id, line_id, target_title, _target_norm in rows
        ),
    )


def refresh_edge_resolutions(connection: sqlite3.Connection, project: str) -> None:
    connection.execute(
        """
        WITH handle_counts AS (
          SELECT project, handle_norm, COUNT(DISTINCT page_id) AS page_count, MIN(page_id) AS page_id
          FROM page_handles
          WHERE project = ?
          GROUP BY project, handle_norm
        )
        UPDATE edges
        SET
          resolution_status = CASE
            WHEN COALESCE((SELECT page_count FROM handle_counts WHERE handle_counts.handle_norm = edges.target_handle_norm), 0) = 0
              THEN 'unresolved'
            WHEN (SELECT page_count FROM handle_counts WHERE handle_counts.handle_norm = edges.target_handle_norm) = 1
              THEN 'resolved_unique'
            ELSE 'ambiguous'
          END,
          target_page_id = CASE
            WHEN (SELECT page_count FROM handle_counts WHERE handle_counts.handle_norm = edges.target_handle_norm) = 1
              THEN (SELECT page_id FROM handle_counts WHERE handle_counts.handle_norm = edges.target_handle_norm)
            ELSE NULL
          END
        WHERE project = ?
        """,
        (project, project),
    )
    connection.execute(
        """
        UPDATE edges
        SET
          target_title = COALESCE((SELECT title FROM pages WHERE pages.project = edges.project AND pages.id = edges.target_page_id), target_handle),
          target_norm = COALESCE((SELECT norm_title FROM pages WHERE pages.project = edges.project AND pages.id = edges.target_page_id), target_handle_norm)
        WHERE project = ?
        """,
        (project,),
    )


def _connection_metadata(connection: sqlite3.Connection) -> dict[str, str]:
    try:
        rows = connection.execute("SELECT key, value FROM metadata").fetchall()
    except sqlite3.OperationalError:
        return {}
    return {str(row[0]): str(row[1]) for row in rows}


def _json_metadata(metadata: dict[str, str], key: str) -> dict[str, Any] | None:
    raw = metadata.get(key)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _insert_markdown_project(
    connection: sqlite3.Connection,
    project: str,
    source: MarkdownMirror,
    folder_path: Path,
    imported_at: int,
) -> None:
    connection.execute(
        """
        INSERT INTO projects (
          name,
          display_name,
          source_export,
          exported,
          imported_at,
          pages,
          lines,
          edges,
          unresolved_targets
        )
        VALUES (?, ?, ?, NULL, ?, ?, ?, ?, 0)
        """,
        (
            project,
            source.display_name or project,
            str(folder_path),
            imported_at,
            len(source.pages),
            sum(page.line_count for page in source.pages),
            len(source.edges),
        ),
    )
    _insert_markdown_records(connection, project, list(source.records), source.edges)


def _insert_markdown_records(
    connection: sqlite3.Connection,
    project: str,
    records: list[MarkdownPageRecord],
    edges: list[Edge],
) -> None:
    pages = [record.page for record in records]
    connection.executemany(
        """
        INSERT INTO pages (project, id, title, norm_title, created, updated, views, line_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                project,
                page.id,
                page.title,
                page.norm_title,
                page.created,
                page.updated,
                page.views,
                page.line_count,
            )
            for page in pages
        ),
    )
    _insert_page_handles(connection, _page_handle_rows_for_markdown_records(project, records))
    connection.executemany(
        """
        INSERT INTO lines (project, line_id, page_id, line_index, text, created, updated, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                project,
                line.line_id,
                page.id,
                line.index,
                line.text,
                line.created,
                line.updated,
                line.user_id,
            )
            for page in pages
            for line in page.lines
        ),
    )
    _insert_edges(connection, project, edges)


def _replace_markdown_record(
    connection: sqlite3.Connection,
    project: str,
    record: MarkdownPageRecord,
    edges: list[Edge],
) -> None:
    connection.execute(
        "DELETE FROM pages WHERE project = ? AND id = ?",
        (project, record.page.id),
    )
    _insert_markdown_records(connection, project, [record], edges)


def _markdown_edges_by_page_id(edges: list[Edge]) -> dict[str, list[Edge]]:
    by_page_id: dict[str, list[Edge]] = {}
    for edge in edges:
        by_page_id.setdefault(edge.source_page_id, []).append(edge)
    return by_page_id


def _markdown_full_rebuild_reason(
    *,
    project_exists: bool,
    old_source_type: str | None,
    old_manifest: dict[str, Any] | None,
    new_manifest: dict[str, Any],
    old_aliases: dict[str, Any],
    new_aliases: dict[str, str],
) -> str | None:
    if not project_exists:
        return "project_missing"
    if old_source_type != "markdown":
        return "source_type_changed"
    if not old_manifest or old_manifest.get("version") != new_manifest.get("version"):
        return "manifest_missing"
    if old_aliases != new_aliases:
        return "alias_map_changed"
    if _markdown_manifest_identity(old_manifest) != _markdown_manifest_identity(new_manifest):
        return "identity_changed"
    return None


def _markdown_manifest_identity(manifest: dict[str, Any]) -> dict[str, Any]:
    files = manifest.get("files")
    if not isinstance(files, dict):
        return {}
    identity: dict[str, Any] = {
        "__exclude_dirs__": sorted(str(item) for item in manifest.get("exclude_dirs") or []),
    }
    for relative_path, item in files.items():
        if not isinstance(item, dict):
            continue
        identity[str(relative_path)] = {
            "page_id": item.get("page_id"),
            "title": item.get("title"),
            "norm_title": item.get("norm_title"),
            "aliases": item.get("aliases") or [],
            "graph_role": item.get("graph_role") or "content",
        }
    return identity


def _changed_markdown_paths(old_manifest: dict[str, Any] | None, new_manifest: dict[str, Any]) -> list[str]:
    if old_manifest is None:
        return sorted((new_manifest.get("files") or {}).keys())
    old_files = old_manifest.get("files") if isinstance(old_manifest.get("files"), dict) else {}
    new_files = new_manifest.get("files") if isinstance(new_manifest.get("files"), dict) else {}
    changed = []
    for relative_path, item in new_files.items():
        old_item = old_files.get(relative_path)
        if not isinstance(item, dict) or not isinstance(old_item, dict):
            changed.append(str(relative_path))
            continue
        if item.get("hash") != old_item.get("hash"):
            changed.append(str(relative_path))
    return sorted(changed)


def _safe_markdown_output_path(output: Path, relative_path: str) -> Path:
    path = Path(_safe_markdown_relative_path(relative_path))
    return output / path


def _safe_markdown_relative_path(relative_path: str | Path) -> str:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts or not path.name:
        raise ValueError(f"unsafe Markdown projection path: {relative_path}")
    if path.suffix.casefold() != ".md":
        raise ValueError(f"Markdown projection path must end with .md: {relative_path}")
    return path.as_posix()


def _markdown_primary_role_path(files: dict[str, Any], graph_role: str, preferred_name: str) -> str | None:
    candidates = [
        str(relative_path)
        for relative_path, item in files.items()
        if isinstance(item, dict) and str(item.get("graph_role") or "content") == graph_role
    ]
    if not candidates:
        return None
    preferred = preferred_name.casefold()
    for relative_path in sorted(candidates):
        path = Path(relative_path)
        if len(path.parts) == 1 and path.name.casefold() == preferred:
            return relative_path
    for relative_path in sorted(candidates):
        if Path(relative_path).name.casefold() == preferred:
            return relative_path
    return sorted(candidates)[0]


def _markdown_index_group(relative_path: str) -> str:
    path = Path(relative_path)
    if len(path.parts) <= 1:
        return "root"
    return path.parts[0] + "/"


def _markdown_table_cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _markdown_link_path(relative_path: str) -> str:
    return quote(Path(relative_path).as_posix(), safe="/#.-_")


def _markdown_frontmatter_summary(lines: list[str]) -> str:
    if not lines or lines[0].strip() != "---":
        return ""
    in_summary_list = False
    summary_parts: list[str] = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped in {"---", "..."}:
            break
        if in_summary_list:
            if stripped.startswith("- "):
                summary_parts.append(stripped[2:].strip())
                continue
            if line.startswith((" ", "\t")):
                continue
            in_summary_list = False
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        if key.strip().casefold() != "summary":
            continue
        value = raw_value.strip().strip('"').strip("'")
        if value:
            return value
        in_summary_list = True
    return " ".join(part for part in summary_parts if part)


def _journal_lines_to_text(lines: Any) -> list[str]:
    if not isinstance(lines, list):
        raise ValueError("journal line payload must be a list")
    texts: list[str] = []
    for line in lines:
        if not isinstance(line, dict):
            raise ValueError("journal line payload entries must be objects")
        texts.append(str(line.get("text", "")))
    return texts


def _journal_record_file_log_projection_lines(project: str, events: list[dict[str, Any]]) -> list[str]:
    records = _latest_record_file_log_payloads(project, events)
    if not records:
        return []
    lines: list[str] = []
    for index, record in enumerate(sorted(records, key=_record_file_log_sort_key)):
        if index > 0:
            lines.append("")
        timestamp = str(record.get("timestamp") or "")
        op = str(record.get("op") or "log-entry")
        summary = str(record.get("summary") or "")
        lines.append(f"## [{timestamp}] {op} | {summary}".rstrip())
        lines.extend(_journal_lines_to_text(record.get("body_lines") or []))
    return lines


def _latest_record_file_log_payloads(project: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    key_to_group: dict[str, int] = {}
    for index, event in enumerate(events):
        if event.get("project") != project or event.get("event_type") != "log_entry_import":
            continue
        payload = event.get("payload") or {}
        if str(payload.get("record_format") or "section") != "file":
            continue
        keys = _record_file_identity_keys(payload)
        if not keys:
            continue
        matched_group_ids = sorted({key_to_group[key] for key in keys if key in key_to_group})
        if matched_group_ids:
            group_id = matched_group_ids[0]
            for other_group_id in reversed(matched_group_ids[1:]):
                if other_group_id == group_id:
                    continue
                groups[group_id]["keys"].update(groups[other_group_id]["keys"])
                if int(groups[other_group_id]["index"]) > int(groups[group_id]["index"]):
                    groups[group_id]["index"] = groups[other_group_id]["index"]
                    groups[group_id]["payload"] = groups[other_group_id]["payload"]
                groups[other_group_id]["deleted"] = True
        else:
            group_id = len(groups)
            groups.append({"keys": set(), "index": -1, "payload": {}, "deleted": False})
        groups[group_id]["keys"].update(keys)
        if index > int(groups[group_id]["index"]):
            groups[group_id]["index"] = index
            groups[group_id]["payload"] = payload
        for key in groups[group_id]["keys"]:
            key_to_group[str(key)] = group_id
    return [
        group["payload"]
        for group in sorted(groups, key=lambda item: int(item["index"]))
        if not group.get("deleted") and group.get("payload")
    ]


def _record_file_identity_keys(payload: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for key in ("record_id", "legacy_record_id"):
        value = str(payload.get(key) or "")
        if value:
            keys.append(value)
    for value in payload.get("supersedes_record_ids") or []:
        if value:
            keys.append(str(value))
    return list(dict.fromkeys(keys))


def _record_file_log_sort_key(payload: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(payload.get("timestamp") or ""),
        str(payload.get("source_path") or ""),
        str(payload.get("record_id") or ""),
    )


def _markdown_lines_to_text(lines: list[str]) -> str:
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _markdown_rename_aliases(
    *,
    previous_title: str,
    new_title: str,
    previous_source_path: str,
    new_source_path: str,
    previous_aliases: list[str],
) -> list[str]:
    aliases: list[str] = []
    for alias in [
        *previous_aliases,
        previous_title,
        Path(previous_source_path).stem,
        Path(new_source_path).stem,
    ]:
        alias = str(alias).strip()
        if not alias:
            continue
        if normalize_title(alias) == normalize_title(new_title):
            continue
        if normalize_title(alias) in {normalize_title(existing) for existing in aliases}:
            continue
        aliases.append(alias)
    return aliases


def _matching_markdown_h1_line_index(lines: list[str], expected_title: str) -> int | None:
    expected_norm = normalize_title(expected_title)
    in_frontmatter = bool(lines and lines[0].strip() == "---")
    in_code_fence = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if index == 0 and in_frontmatter:
            continue
        if in_frontmatter:
            if stripped in {"---", "..."}:
                in_frontmatter = False
            continue
        if is_code_fence(line.lstrip()):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        title = parse_markdown_h1_title(line)
        if title is None:
            continue
        if normalize_title(title) == expected_norm:
            return index
        return None
    return None


def _refresh_project_counts_sql(connection: sqlite3.Connection, project: str) -> None:
    connection.execute(
        """
        UPDATE projects
        SET
          pages = (SELECT COUNT(*) FROM pages WHERE project = ?),
          lines = (SELECT COUNT(*) FROM lines WHERE project = ?),
          edges = (SELECT COUNT(*) FROM edges WHERE project = ?),
          unresolved_targets = (SELECT COUNT(*) FROM unresolved_targets WHERE project = ?)
        WHERE name = ?
        """,
        (project, project, project, project, project),
    )


class SQLiteStore:
    def __init__(self, path: str | Path, project: str | None = None, *, for_write: bool = False):
        self.path = Path(path)
        self.project = normalize_project_name(project) if project is not None else None
        self.connection = connect_sqlite_store(
            self.path,
            row_factory=True,
            for_write=for_write,
        )

    def write_transaction(self):
        return sqlite_write_transaction(self.connection)

    def close(self) -> None:
        self.connection.close()

    def stats(self) -> dict[str, Any]:
        metadata = self.metadata()
        schema_version = metadata.get("schema_version")
        project = self._selected_project_or_none()
        projects = self.projects()
        project_row = self.project_metadata(project) if project is not None else None
        source_export = metadata.get("last_source_export") or metadata.get("source_export")
        imported_at = _int_or_none(metadata.get("last_imported_at") or metadata.get("imported_at"))
        acquisition = self.project_acquisition_metadata(project) if project is not None else None
        return {
            "store": str(self.path),
            "project": project,
            "project_count": len(projects),
            "projects": projects,
            "schema_version": schema_version,
            "current_schema_version": SCHEMA_VERSION,
            "schema_ok": schema_version == SCHEMA_VERSION,
            "source_export": project_row.get("source_export") if project_row is not None else source_export,
            "imported_at": project_row.get("imported_at") if project_row is not None else imported_at,
            "pages": self._count_if_exists("pages", project=project),
            "lines": self._count_if_exists("lines", project=project),
            "edges": self._count_if_exists("edges", project=project),
            "unresolved_targets": self._count_if_exists("unresolved_targets", project=project),
            "acquisition": acquisition,
        }

    def import_journal_events(
        self,
        events_or_path: str | Path | list[dict[str, Any]],
        *,
        actor: str = "",
        session_id: str = "",
        project: str | None = None,
    ) -> dict[str, Any]:
        source_path: Path | None = None
        if isinstance(events_or_path, (str, Path)):
            source_path = Path(events_or_path)
            events = read_journal_events(source_path)
        else:
            events = list(events_or_path)

        project_filter = normalize_project_name(project) if project is not None else self.project
        imported = 0
        skipped = 0
        filtered = 0
        with self.write_transaction():
            for event in events:
                validate_journal_event(event)
                event_project = normalize_project_name(event["project"])
                if project_filter and event_project != project_filter:
                    filtered += 1
                    continue
                if insert_store_event(
                    self.connection,
                    event,
                    actor=actor,
                    session_id=session_id,
                    if_exists="skip",
                ):
                    imported += 1
                else:
                    skipped += 1
        summary: dict[str, Any] = {
            "events": len(events),
            "imported": imported,
            "skipped": skipped,
            "filtered": filtered,
            "project": project_filter,
        }
        if source_path is not None:
            summary["source"] = str(source_path)
        return summary

    def events(
        self,
        *,
        project: str | None = None,
        event_type: str | None = None,
        limit: int | None = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        project_filter = normalize_project_name(project) if project is not None else self._selected_project_or_none()
        clauses: list[str] = []
        params: list[Any] = []
        if project_filter:
            clauses.append("project = ?")
            params.append(project_filter)
        if event_type is not None:
            if event_type not in EVENT_TYPES:
                raise ValueError(f"unsupported journal event_type: {event_type!r}")
            clauses.append("event_type = ?")
            params.append(event_type)
        query = """
            SELECT
              event_sequence,
              event_id,
              schema_version,
              event_type,
              project,
              created_at,
              actor,
              session_id,
              payload_json
            FROM events
        """
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY event_sequence"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([max(0, int(limit)), max(0, int(offset))])
        rows = self.connection.execute(query, params).fetchall()
        return [store_event_from_row(row) for row in rows]

    def event_count(
        self,
        *,
        project: str | None = None,
        event_type: str | None = None,
    ) -> int:
        project_filter = normalize_project_name(project) if project is not None else self._selected_project_or_none()
        clauses: list[str] = []
        params: list[Any] = []
        if project_filter:
            clauses.append("project = ?")
            params.append(project_filter)
        if event_type is not None:
            if event_type not in EVENT_TYPES:
                raise ValueError(f"unsupported journal event_type: {event_type!r}")
            clauses.append("event_type = ?")
            params.append(event_type)
        query = "SELECT COUNT(*) FROM events"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        return int(self.connection.execute(query, params).fetchone()[0])

    def metadata(self) -> dict[str, str]:
        return {
            row["key"]: row["value"]
            for row in self.connection.execute("SELECT key, value FROM metadata")
        }

    def projects(self) -> list[dict[str, Any]]:
        try:
            rows = self.connection.execute(
                """
                SELECT
                  name,
                  display_name,
                  source_export,
                  exported,
                  imported_at,
                  pages,
                  lines,
                  edges,
                  unresolved_targets
                FROM projects
                ORDER BY name
                """
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(row) for row in rows]

    def project_names(self) -> list[str]:
        return [project["name"] for project in self.projects()]

    def project_metadata(self, project: str | None = None) -> dict[str, Any] | None:
        project = self._require_project(project)
        row = self.connection.execute(
            """
            SELECT
              name,
              display_name,
              source_export,
              exported,
              imported_at,
              pages,
              lines,
              edges,
              unresolved_targets
            FROM projects
            WHERE name = ?
            """,
            (project,),
        ).fetchone()
        return None if row is None else dict(row)

    def project_acquisition_metadata(self, project: str | None = None) -> dict[str, Any] | None:
        project = self._require_project(project)
        return self.project_acquisition_metadata_by_name(project)

    def project_acquisition_metadata_by_name(self, project: str) -> dict[str, Any] | None:
        project = normalize_project_name(project)
        raw = self.metadata().get(f"project.{project}.acquisition")
        if raw is None:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def project_title_aliases(self, project: str | None = None) -> dict[str, str]:
        project = self._require_project(project)
        raw = self.metadata().get(f"project.{project}.title_aliases")
        if raw is None:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        return {
            str(alias_norm): str(title)
            for alias_norm, title in data.items()
            if isinstance(alias_norm, str) and isinstance(title, str)
        }

    def _resolve_title_norm(self, title: str, *, project: str) -> str:
        norm_title = normalize_title(title)
        alias_title = self.project_title_aliases(project).get(norm_title)
        if alias_title is None:
            return norm_title
        return normalize_title(alias_title)

    def page_handle_candidates(self, handle: str, project: str | None = None) -> list[dict[str, Any]]:
        project = self._require_project(project)
        handle_norm = normalize_title(handle)
        rows = self.connection.execute(
            """
            SELECT
              h.handle,
              h.handle_source,
              h.source_path,
              h.graph_role,
              page.id AS page_id,
              page.title,
              page.norm_title,
              page.views,
              page.updated,
              page.line_count
            FROM page_handles h
            JOIN pages page ON page.project = h.project AND page.id = h.page_id
            WHERE h.project = ? AND h.handle_norm = ?
            ORDER BY
              CASE h.handle_source WHEN 'title' THEN 0 WHEN 'alias' THEN 1 ELSE 2 END,
              CASE h.graph_role WHEN 'content' THEN 0 WHEN 'source' THEN 1 ELSE 2 END,
              page.title,
              h.source_path,
              h.handle
            """,
            (project, handle_norm),
        ).fetchall()
        candidates: dict[str, dict[str, Any]] = {}
        for row in rows:
            page_id = str(row["page_id"])
            candidate = candidates.setdefault(
                page_id,
                {
                    "page_id": page_id,
                    "title": row["title"],
                    "normalized_title": row["norm_title"],
                    "views": row["views"],
                    "updated": row["updated"],
                    "line_count": row["line_count"],
                    "path": row["source_path"] or None,
                    "graph_role": row["graph_role"],
                    "matched_handles": [],
                },
            )
            if candidate["path"] is None and row["source_path"]:
                candidate["path"] = row["source_path"]
            if candidate["graph_role"] == "artifact" and row["graph_role"] != "artifact":
                candidate["graph_role"] = row["graph_role"]
            candidate["matched_handles"].append(
                {
                    "handle": row["handle"],
                    "source": row["handle_source"],
                    "path": row["source_path"] or None,
                    "graph_role": row["graph_role"],
                }
            )
        return list(candidates.values())

    def _handle_ambiguity(self, handle: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "type": "handle_ambiguity",
            "handle": handle,
            "handle_norm": normalize_title(handle),
            "candidate_count": len(candidates),
            "candidates": candidates,
        }

    def ambiguities(self, limit: int = 50, offset: int = 0, candidate_limit: int = 5) -> dict[str, Any]:
        projects = self._ambiguity_scope_projects()
        limit = max(0, limit)
        offset = max(0, offset)
        candidate_limit = max(0, candidate_limit)
        scope = "project" if self.project else "all-projects"
        if not projects:
            return {
                "scope": scope,
                "project": self.project,
                "project_count": 0,
                "projects": [],
                "handle_count": 0,
                "handles_returned": 0,
                "limit": limit,
                "offset": offset,
                "candidate_limit": candidate_limit,
                "ambiguities": [],
            }

        rows = self.connection.execute(
            self._ambiguities_sql(projects),
            [*projects, *projects, limit, offset],
        ).fetchall()
        items = [self._ambiguity_item_from_row(row, candidate_limit) for row in rows]
        return {
            "scope": scope,
            "project": projects[0] if scope == "project" else None,
            "project_count": len(projects),
            "projects": self._ambiguity_project_summaries(projects),
            "handle_count": self._ambiguity_count(projects),
            "handles_returned": len(items),
            "limit": limit,
            "offset": offset,
            "candidate_limit": candidate_limit,
            "ambiguities": items,
        }

    def cross_project_spread(
        self,
        title: str,
        *,
        limit: int = 50,
        offset: int = 0,
        candidate_limit: int = 5,
    ) -> dict[str, Any]:
        projects = self._ambiguity_scope_projects()
        limit = max(0, limit)
        offset = max(0, offset)
        candidate_limit = max(0, candidate_limit)
        handle_norm = normalize_title(title)
        scope = "project" if self.project else "all-projects"
        edge_stats = self._spread_edge_stats(projects, handle_norm)
        unresolved = self._spread_unresolved_targets(projects, handle_norm)
        items = []
        for project in projects:
            candidates = self.page_handle_candidates(handle_norm, project=project)
            stats = edge_stats.get(project, _empty_spread_edge_stats())
            unresolved_item = unresolved.get(project)
            if not candidates and not unresolved_item and stats["incoming_link_count"] == 0:
                continue
            returned_candidates = candidates[:candidate_limit] if candidate_limit else []
            items.append(
                {
                    "project": project,
                    "materialized": {
                        "candidate_count": len(candidates),
                        "candidates": returned_candidates,
                        "candidates_returned": len(returned_candidates),
                        "candidates_truncated": len(candidates) > len(returned_candidates),
                        "ambiguous": len(candidates) > 1,
                    },
                    "unresolved": unresolved_item,
                    "incoming": stats,
                    "signals": {
                        "has_materialized_page": bool(candidates),
                        "has_unresolved_target": unresolved_item is not None,
                        "has_incoming_links": stats["incoming_link_count"] > 0,
                    },
                }
            )
        items.sort(key=_spread_project_rank_key)
        returned_items = items[offset : offset + limit] if limit else []
        totals = _spread_totals(items)
        return {
            "query": title,
            "handle_norm": handle_norm,
            "scope": scope,
            "project": projects[0] if scope == "project" and projects else None,
            "project_count": len(projects),
            "signal_project_count": len(items),
            "projects_returned": len(returned_items),
            "limit": limit,
            "offset": offset,
            "candidate_limit": candidate_limit,
            "connection_strength": "weak-normalized-title",
            "note": "Spread is a weak normalized-title signal. Page identities stay project-scoped and are not merged.",
            "totals": totals,
            "top_source_projects": [
                {
                    "project": item["project"],
                    "incoming_link_count": item["incoming"]["incoming_link_count"],
                    "incoming_source_page_count": item["incoming"]["incoming_source_page_count"],
                    "resolution_counts": item["incoming"]["resolution_counts"],
                }
                for item in items
                if item["incoming"]["incoming_link_count"] > 0
            ][:10],
            "projects": returned_items,
        }

    def cross_project_spreads(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        min_projects: int = 2,
        project_limit: int = 3,
        candidate_limit: int = 1,
    ) -> dict[str, Any]:
        projects = self._ambiguity_scope_projects()
        limit = max(0, limit)
        offset = max(0, offset)
        min_projects = max(1, min_projects)
        project_limit = max(0, project_limit)
        candidate_limit = max(0, candidate_limit)
        scope = "project" if self.project else "all-projects"
        rows = self._cross_project_spread_rows(projects)
        all_items = [_spread_summary_from_row(row) for row in rows]
        items = [item for item in all_items if item["project_spread"] >= min_projects]
        items.sort(key=_cross_project_spread_summary_rank_key)
        returned_base = items[offset : offset + limit] if limit else []
        returned_items = []
        for item in returned_base:
            spread = self.cross_project_spread(
                item["title"],
                limit=project_limit,
                candidate_limit=candidate_limit,
            )
            detailed = dict(item)
            detailed["project_samples"] = spread["projects"]
            detailed["project_samples_returned"] = len(spread["projects"])
            returned_items.append(detailed)
        return {
            "scope": scope,
            "project": projects[0] if scope == "project" and projects else None,
            "project_count": len(projects),
            "total_handle_count": len(all_items),
            "handle_count": len(items),
            "handles_returned": len(returned_items),
            "limit": limit,
            "offset": offset,
            "min_projects": min_projects,
            "project_limit": project_limit,
            "candidate_limit": candidate_limit,
            "connection_strength": "weak-normalized-title",
            "rank_basis": (
                "Concept-like handles rank before structural-name, numeric-only, and artifact-only handles; "
                "within each band, project_spread and incoming links rank higher."
            ),
            "note": "Spread ranking is a weak normalized-title discovery surface. Page identities stay project-scoped and are not merged.",
            "spreads": returned_items,
        }

    def _ambiguity_scope_projects(self) -> list[str]:
        names = self.project_names()
        if self.project:
            if self.project not in names:
                available = ", ".join(names) or "(none)"
                raise ValueError(f"project does not exist: {self.project}; available projects: {available}")
            return [self.project]
        return names

    def _spread_edge_stats(self, projects: list[str], handle_norm: str) -> dict[str, dict[str, Any]]:
        if not projects:
            return {}
        placeholders = ",".join("?" for _ in projects)
        rows = self.connection.execute(
            f"""
            SELECT
              project,
              COUNT(*) AS incoming_link_count,
              COUNT(DISTINCT source_page_id) AS incoming_source_page_count,
              SUM(CASE WHEN resolution_status = 'resolved_unique' THEN 1 ELSE 0 END) AS resolved_unique,
              SUM(CASE WHEN resolution_status = 'ambiguous' THEN 1 ELSE 0 END) AS ambiguous,
              SUM(CASE WHEN resolution_status = 'unresolved' THEN 1 ELSE 0 END) AS unresolved
            FROM edges
            WHERE project IN ({placeholders})
              AND target_handle_norm = ?
            GROUP BY project
            """,
            [*projects, handle_norm],
        ).fetchall()
        return {
            row["project"]: {
                "incoming_link_count": int(row["incoming_link_count"]),
                "incoming_source_page_count": int(row["incoming_source_page_count"]),
                "resolution_counts": {
                    "resolved_unique": int(row["resolved_unique"] or 0),
                    "ambiguous": int(row["ambiguous"] or 0),
                    "unresolved": int(row["unresolved"] or 0),
                },
            }
            for row in rows
        }

    def _spread_unresolved_targets(self, projects: list[str], handle_norm: str) -> dict[str, dict[str, Any]]:
        if not projects:
            return {}
        placeholders = ",".join("?" for _ in projects)
        rows = self.connection.execute(
            f"""
            SELECT *
            FROM unresolved_targets
            WHERE project IN ({placeholders})
              AND target_norm = ?
            """,
            [*projects, handle_norm],
        ).fetchall()
        return {
            row["project"]: {
                "project": row["project"],
                "title": row["title"],
                "normalized_title": row["target_norm"],
                "link_count": int(row["link_count"]),
                "source_page_count": int(row["source_page_count"]),
                "total_source_views": int(row["total_source_views"]),
                "latest_source_updated": int(row["latest_source_updated"]),
            }
            for row in rows
        }

    def _cross_project_spread_rows(self, projects: list[str]) -> list[sqlite3.Row]:
        if not projects:
            return []
        placeholders = ",".join("?" for _ in projects)
        return self.connection.execute(
            f"""
            WITH handle_project_stats AS (
              SELECT
                handle_norm,
                project,
                COUNT(DISTINCT page_id) AS candidate_count,
                MIN(handle) AS sample_handle,
                SUM(CASE WHEN graph_role IN ('navigation', 'log', 'artifact') THEN 1 ELSE 0 END) AS artifact_handle_count,
                SUM(CASE WHEN graph_role NOT IN ('navigation', 'log', 'artifact') THEN 1 ELSE 0 END) AS content_handle_count
              FROM page_handles
              WHERE project IN ({placeholders})
              GROUP BY handle_norm, project
            ),
            handle_stats AS (
              SELECT
                handle_norm,
                COUNT(*) AS materialized_project_count,
                SUM(candidate_count) AS page_candidate_count,
                SUM(CASE WHEN candidate_count > 1 THEN 1 ELSE 0 END) AS ambiguous_project_count,
                SUM(CASE WHEN content_handle_count = 0 THEN 1 ELSE 0 END) AS artifact_project_count,
                SUM(CASE WHEN content_handle_count > 0 THEN 1 ELSE 0 END) AS content_project_count,
                MIN(sample_handle) AS sample_handle
              FROM handle_project_stats
              GROUP BY handle_norm
            ),
            unresolved_project_rows AS (
              SELECT
                target_norm AS handle_norm,
                project,
                title,
                link_count
              FROM unresolved_targets
              WHERE project IN ({placeholders})
            ),
            unresolved_stats AS (
              SELECT
                handle_norm,
                COUNT(DISTINCT project) AS unresolved_project_count,
                SUM(link_count) AS unresolved_link_count,
                MIN(title) AS sample_unresolved_title
              FROM unresolved_project_rows
              GROUP BY handle_norm
            ),
            edge_project_rows AS (
              SELECT
                target_handle_norm AS handle_norm,
                project,
                source_page_id,
                resolution_status
              FROM edges
              WHERE project IN ({placeholders})
            ),
            edge_stats AS (
              SELECT
                handle_norm,
                COUNT(DISTINCT project) AS incoming_project_count,
                COUNT(*) AS incoming_link_count,
                COUNT(DISTINCT project || char(31) || source_page_id) AS incoming_source_page_count,
                SUM(CASE WHEN resolution_status = 'resolved_unique' THEN 1 ELSE 0 END) AS resolved_unique,
                SUM(CASE WHEN resolution_status = 'ambiguous' THEN 1 ELSE 0 END) AS ambiguous,
                SUM(CASE WHEN resolution_status = 'unresolved' THEN 1 ELSE 0 END) AS unresolved
              FROM edge_project_rows
              GROUP BY handle_norm
            ),
            signal_projects AS (
              SELECT handle_norm, project FROM handle_project_stats
              UNION
              SELECT handle_norm, project FROM unresolved_project_rows
              UNION
              SELECT handle_norm, project FROM edge_project_rows
            ),
            signal_stats AS (
              SELECT handle_norm, COUNT(DISTINCT project) AS project_spread
              FROM signal_projects
              GROUP BY handle_norm
            ),
            all_norms AS (
              SELECT handle_norm FROM handle_stats
              UNION
              SELECT handle_norm FROM unresolved_stats
              UNION
              SELECT handle_norm FROM edge_stats
            )
            SELECT
              all_norms.handle_norm,
              COALESCE(handle_stats.sample_handle, unresolved_stats.sample_unresolved_title, all_norms.handle_norm) AS title,
              COALESCE(signal_stats.project_spread, 0) AS project_spread,
              COALESCE(handle_stats.materialized_project_count, 0) AS materialized_project_count,
              COALESCE(handle_stats.page_candidate_count, 0) AS page_candidate_count,
              COALESCE(handle_stats.ambiguous_project_count, 0) AS ambiguous_project_count,
              COALESCE(handle_stats.artifact_project_count, 0) AS artifact_project_count,
              COALESCE(handle_stats.content_project_count, 0) AS content_project_count,
              COALESCE(unresolved_stats.unresolved_project_count, 0) AS unresolved_project_count,
              COALESCE(unresolved_stats.unresolved_link_count, 0) AS unresolved_link_count,
              COALESCE(edge_stats.incoming_project_count, 0) AS incoming_project_count,
              COALESCE(edge_stats.incoming_link_count, 0) AS incoming_link_count,
              COALESCE(edge_stats.incoming_source_page_count, 0) AS incoming_source_page_count,
              COALESCE(edge_stats.resolved_unique, 0) AS resolved_unique,
              COALESCE(edge_stats.ambiguous, 0) AS ambiguous,
              COALESCE(edge_stats.unresolved, 0) AS unresolved
            FROM all_norms
            LEFT JOIN signal_stats ON signal_stats.handle_norm = all_norms.handle_norm
            LEFT JOIN handle_stats ON handle_stats.handle_norm = all_norms.handle_norm
            LEFT JOIN unresolved_stats ON unresolved_stats.handle_norm = all_norms.handle_norm
            LEFT JOIN edge_stats ON edge_stats.handle_norm = all_norms.handle_norm
            """,
            [*projects, *projects, *projects],
        ).fetchall()

    def _ambiguities_sql(self, projects: list[str]) -> str:
        placeholders = ",".join("?" for _ in projects)
        return f"""
            WITH ambiguous AS (
              SELECT
                h.project,
                h.handle_norm,
                COUNT(DISTINCT h.page_id) AS candidate_count
              FROM page_handles h
              WHERE h.project IN ({placeholders})
              GROUP BY h.project, h.handle_norm
              HAVING COUNT(DISTINCT h.page_id) > 1
            ),
            edge_stats AS (
              SELECT
                e.project,
                e.target_handle_norm AS handle_norm,
                COUNT(*) AS ambiguous_link_count,
                COUNT(DISTINCT e.source_page_id) AS ambiguous_source_page_count
              FROM edges e
              WHERE e.project IN ({placeholders})
                AND e.resolution_status = 'ambiguous'
              GROUP BY e.project, e.target_handle_norm
            )
            SELECT
              ambiguous.project,
              ambiguous.handle_norm,
              ambiguous.candidate_count,
              COALESCE(edge_stats.ambiguous_link_count, 0) AS ambiguous_link_count,
              COALESCE(edge_stats.ambiguous_source_page_count, 0) AS ambiguous_source_page_count
            FROM ambiguous
            LEFT JOIN edge_stats
              ON edge_stats.project = ambiguous.project
             AND edge_stats.handle_norm = ambiguous.handle_norm
            ORDER BY
              ambiguous_link_count DESC,
              ambiguous_source_page_count DESC,
              ambiguous.candidate_count DESC,
              ambiguous.project,
              ambiguous.handle_norm
            LIMIT ? OFFSET ?
        """

    def _ambiguity_count(self, projects: list[str]) -> int:
        placeholders = ",".join("?" for _ in projects)
        row = self.connection.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM (
              SELECT h.project, h.handle_norm
              FROM page_handles h
              WHERE h.project IN ({placeholders})
              GROUP BY h.project, h.handle_norm
              HAVING COUNT(DISTINCT h.page_id) > 1
            )
            """,
            projects,
        ).fetchone()
        return int(row["count"])

    def _ambiguity_project_summaries(self, projects: list[str]) -> list[dict[str, Any]]:
        placeholders = ",".join("?" for _ in projects)
        rows = self.connection.execute(
            f"""
            WITH ambiguous AS (
              SELECT
                h.project,
                h.handle_norm,
                COUNT(DISTINCT h.page_id) AS candidate_count
              FROM page_handles h
              WHERE h.project IN ({placeholders})
              GROUP BY h.project, h.handle_norm
              HAVING COUNT(DISTINCT h.page_id) > 1
            ),
            edge_stats AS (
              SELECT
                e.project,
                e.target_handle_norm AS handle_norm,
                COUNT(*) AS ambiguous_link_count,
                COUNT(DISTINCT e.source_page_id) AS ambiguous_source_page_count
              FROM edges e
              WHERE e.project IN ({placeholders})
                AND e.resolution_status = 'ambiguous'
              GROUP BY e.project, e.target_handle_norm
            )
            SELECT
              ambiguous.project,
              COUNT(*) AS ambiguous_handle_count,
              COALESCE(SUM(edge_stats.ambiguous_link_count), 0) AS ambiguous_link_count,
              COALESCE(SUM(edge_stats.ambiguous_source_page_count), 0) AS ambiguous_source_page_count,
              MAX(ambiguous.candidate_count) AS max_candidate_count
            FROM ambiguous
            LEFT JOIN edge_stats
              ON edge_stats.project = ambiguous.project
             AND edge_stats.handle_norm = ambiguous.handle_norm
            GROUP BY ambiguous.project
            ORDER BY ambiguous_handle_count DESC, ambiguous_link_count DESC, ambiguous.project
            """,
            [*projects, *projects],
        ).fetchall()
        return [dict(row) for row in rows]

    def _ambiguity_item_from_row(self, row: sqlite3.Row, candidate_limit: int) -> dict[str, Any]:
        project = row["project"]
        handle_norm = row["handle_norm"]
        candidates = self.page_handle_candidates(handle_norm, project=project)
        returned_candidates = candidates[:candidate_limit] if candidate_limit else []
        return {
            "project": project,
            "handle": self._preferred_ambiguity_handle(handle_norm, candidates),
            "handle_norm": handle_norm,
            "candidate_count": row["candidate_count"],
            "candidates": returned_candidates,
            "candidates_returned": len(returned_candidates),
            "candidates_truncated": len(candidates) > len(returned_candidates),
            "ambiguous_link_count": row["ambiguous_link_count"],
            "ambiguous_source_page_count": row["ambiguous_source_page_count"],
            "graph_role_counts": dict(Counter(candidate["graph_role"] for candidate in candidates)),
        }

    def _preferred_ambiguity_handle(self, handle_norm: str, candidates: list[dict[str, Any]]) -> str:
        source_rank = {"title": 0, "alias": 1, "path": 2}
        role_rank = {"content": 0, "source": 1, "artifact": 2}
        handles = [
            matched
            for candidate in candidates
            for matched in candidate["matched_handles"]
            if normalize_title(matched["handle"]) == handle_norm
        ]
        if not handles:
            return handle_norm
        handles.sort(
            key=lambda matched: (
                source_rank.get(matched["source"], 9),
                role_rank.get(matched["graph_role"], 9),
                matched["handle"].casefold(),
                matched.get("path") or "",
            )
        )
        return handles[0]["handle"]

    def _selected_project_or_none(self) -> str | None:
        if self.project:
            return self.project
        names = self.project_names()
        if len(names) == 1:
            return names[0]
        return None

    def _require_project(self, project: str | None = None) -> str:
        names = self.project_names()
        if project:
            if project not in names:
                available = ", ".join(names) or "(none)"
                raise ValueError(f"project does not exist: {project}; available projects: {available}")
            return project
        selected = self._selected_project_or_none()
        if selected is not None:
            if selected not in names:
                available = ", ".join(names) or "(none)"
                raise ValueError(f"project does not exist: {selected}; available projects: {available}")
            return selected
        if not names:
            raise ValueError("store has no projects; run `grasp import --cosense <json>` or `grasp import --markdown <folder>` first")
        available = ", ".join(names)
        raise ValueError(f"multiple projects in store; specify --project <name> (available: {available})")

    def schema_version(self) -> str | None:
        return self.metadata().get("schema_version")

    def schema_ok(self) -> bool:
        return self.schema_version() == SCHEMA_VERSION

    def set_metadata(self, values: dict[str, str]) -> None:
        with self.connection:
            self.connection.executemany(
                """
                INSERT INTO metadata (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                values.items(),
            )

    def replace_project_with_cosense_pages(
        self,
        project: str,
        pages: list[dict[str, Any]],
        *,
        display_name: str | None = None,
        source_export: str = "",
        acquisition_metadata: dict[str, Any] | None = None,
    ) -> None:
        project = normalize_project_name(project)
        if not project:
            raise ValueError("project name is required")

        now = int(time.time())
        with self.connection:
            _delete_project(self.connection, project)
            self.connection.execute(
                """
                INSERT INTO projects (
                  name,
                  display_name,
                  source_export,
                  exported,
                  imported_at,
                  pages,
                  lines,
                  edges,
                  unresolved_targets
                )
                VALUES (?, ?, ?, NULL, ?, 0, 0, 0, 0)
                """,
                (
                    project,
                    display_name or project,
                    source_export,
                    now,
                ),
            )
            for page in pages:
                self._upsert_cosense_page(page, project)
            rebuild_unresolved_targets(self.connection, project)
            self._refresh_project_counts(project)

            metadata: dict[str, str] = {
                "schema_version": SCHEMA_VERSION,
                "last_acquired_project": project,
                "last_acquired_source": source_export,
                "last_acquired_at": str(now),
                f"project.{project}.source_type": "cosense",
                f"project.{project}.title_aliases": "{}",
            }
            if acquisition_metadata is not None:
                metadata[f"project.{project}.acquisition"] = json.dumps(
                    acquisition_metadata,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            _write_metadata(self.connection, metadata)

        self.project = project

    def cosense_page_dict_by_norm(self, project: str, norm_title: str) -> dict[str, Any] | None:
        project = normalize_project_name(project)
        row = self.connection.execute(
            """
            SELECT *
            FROM pages
            WHERE project = ? AND norm_title = ?
            ORDER BY rowid
            LIMIT 1
            """,
            (project, norm_title),
        ).fetchone()
        if row is None:
            return None

        line_rows = self.connection.execute(
            """
            SELECT *
            FROM lines
            WHERE project = ? AND page_id = ?
            ORDER BY line_index
            """,
            (project, row["id"]),
        ).fetchall()
        lines = []
        for line in line_rows:
            user_id = line["user_id"]
            lines.append(
                {
                    "text": line["text"],
                    "created": line["created"],
                    "updated": line["updated"],
                    "user": {"id": user_id} if user_id is not None else {},
                }
            )
        return {
            "id": row["id"],
            "title": row["title"],
            "persistent": True,
            "created": row["created"],
            "updated": row["updated"],
            "views": row["views"],
            "lines": lines,
        }

    def page_updated(self, page_id: str) -> int | None:
        project = self._require_project()
        row = self.connection.execute(
            "SELECT updated FROM pages WHERE project = ? AND id = ?",
            (project, page_id),
        ).fetchone()
        if row is None:
            return None
        return row["updated"]

    def upsert_cosense_pages(self, pages: list[dict[str, Any]]) -> None:
        if not pages:
            return
        project = self._require_project()
        with self.connection:
            for page in pages:
                self._upsert_cosense_page(page, project)
            rebuild_unresolved_targets(self.connection, project)
            self._refresh_project_counts(project)

    def resolve_page(self, title: str) -> Page | None:
        candidates = self.page_handle_candidates(title)
        if len(candidates) != 1:
            return None
        return self._page_by_id(candidates[0]["page_id"])

    def page_lines(self, page: Page, limit: int | None = None, offset: int = 0) -> tuple[list[Line], bool]:
        project = self._require_project()
        offset = max(0, offset)
        if limit is None or limit < 0:
            rows = self.connection.execute(
                """
                SELECT * FROM lines
                WHERE project = ? AND page_id = ? AND line_index >= ?
                ORDER BY line_index
                """,
                (project, page.id, offset),
            ).fetchall()
            return [self._line_from_row(row) for row in rows], False

        rows = self.connection.execute(
            """
            SELECT * FROM lines
            WHERE project = ? AND page_id = ? AND line_index >= ?
            ORDER BY line_index
            LIMIT ?
            """,
            (project, page.id, offset, limit),
        ).fetchall()
        return [self._line_from_row(row) for row in rows], offset + len(rows) < page.line_count

    def export_markdown(
        self,
        output_folder: str | Path,
        *,
        check: bool = False,
        regenerate_index: bool = False,
        log_journal_events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        project = self._require_project()
        output = Path(output_folder)
        manifest = self._markdown_manifest_for_project(project)
        files = manifest.get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError(f"project is not a Markdown mirror project or has no Markdown manifest: {project}")

        projections = self._markdown_projection_files(project, files)
        regenerated_files: list[str] = []
        if regenerate_index:
            index_path = _markdown_primary_role_path(files, "navigation", "index.md")
            if index_path is None:
                raise ValueError(f"project has no navigation index page to regenerate: {project}")
            projections[index_path] = self._markdown_index_projection_text(project, files)
            regenerated_files.append(index_path)
        if log_journal_events is not None:
            log_path = _markdown_primary_role_path(files, "log", "log.md")
            if log_path is None:
                raise ValueError(f"project has no log page to regenerate: {project}")
            projections[log_path] = self._markdown_log_projection_text_from_journal(
                project,
                log_path,
                files,
                log_journal_events,
            )
            regenerated_files.append(log_path)
        changed_files: list[str] = []
        missing_files: list[str] = []
        written_files: list[str] = []
        for relative_path, text in projections.items():
            target = _safe_markdown_output_path(output, relative_path)
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

        exclude_dirs = tuple(str(item) for item in manifest.get("exclude_dirs") or [])
        existing_files = {
            path.relative_to(output).as_posix()
            for path in iter_markdown_files(output, exclude_dirs=exclude_dirs)
        } if output.exists() else set()
        extra_files = sorted(existing_files - set(projections))
        ok = not changed_files and not missing_files and not extra_files
        return {
            "project": project,
            "output": str(output),
            "check": check,
            "ok": ok,
            "file_count": len(projections),
            "checked_files": len(projections) if check else 0,
            "written_files": written_files,
            "written_count": len(written_files),
            "regenerated_files": sorted(regenerated_files),
            "regenerated_count": len(regenerated_files),
            "changed_files": sorted(changed_files),
            "missing_files": sorted(missing_files),
            "extra_files": extra_files,
        }

    def _markdown_manifest_for_project(self, project: str) -> dict[str, Any]:
        metadata = self.metadata()
        if metadata.get(f"project.{project}.source_type") != "markdown":
            return {}
        manifest = _json_metadata(metadata, f"project.{project}.markdown_manifest")
        return manifest if isinstance(manifest, dict) else {}

    def _markdown_projection_files(self, project: str, files: dict[str, Any]) -> dict[str, str]:
        projections: dict[str, str] = {}
        for relative_path in sorted(str(path) for path in files):
            item = files.get(relative_path)
            if not isinstance(item, dict):
                continue
            page_id = str(item.get("page_id") or "")
            if not page_id:
                continue
            lines = self.connection.execute(
                """
                SELECT text
                FROM lines
                WHERE project = ? AND page_id = ?
                ORDER BY line_index
                """,
                (project, page_id),
            ).fetchall()
            projections[relative_path] = markdown_projection_text(
                relative_path,
                page_id=page_id,
                title=str(item.get("title") or ""),
                aliases=[str(alias) for alias in item.get("aliases") or []],
                lines=[row["text"] for row in lines],
            )
        return projections

    def _markdown_index_projection_text(self, project: str, files: dict[str, Any]) -> str:
        groups: dict[str, list[tuple[str, str, str]]] = {}
        for relative_path in sorted(str(path) for path in files):
            item = files.get(relative_path)
            if not isinstance(item, dict):
                continue
            graph_role = str(item.get("graph_role") or "content")
            if graph_role not in {"content", "source"}:
                continue
            page_id = str(item.get("page_id") or "")
            if not page_id:
                continue
            title = str(item.get("title") or Path(relative_path).stem)
            group = _markdown_index_group(relative_path)
            summary = self._markdown_page_summary(project, page_id)
            groups.setdefault(group, []).append((title, relative_path, summary))

        lines = ["# Index", ""]
        for group in sorted(groups):
            lines.extend([f"## {group}", "", "| Page | Summary |", "|---|---|"])
            for title, relative_path, summary in sorted(groups[group], key=lambda row: (normalize_title(row[0]), row[1])):
                lines.append(
                    f"| [{_markdown_table_cell(title)}]({_markdown_link_path(relative_path)}) | "
                    f"{_markdown_table_cell(summary)} |"
                )
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _markdown_page_summary(self, project: str, page_id: str) -> str:
        rows = self.connection.execute(
            """
            SELECT text
            FROM lines
            WHERE project = ? AND page_id = ?
            ORDER BY line_index
            """,
            (project, page_id),
        ).fetchall()
        return _markdown_frontmatter_summary([row["text"] for row in rows])

    def _markdown_log_projection_text_from_journal(
        self,
        project: str,
        log_path: str,
        files: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> str:
        item = files.get(log_path)
        if not isinstance(item, dict):
            raise ValueError(f"Markdown manifest has no log page entry: {log_path}")
        log_page_id = str(item.get("page_id") or "")
        if not log_page_id:
            raise ValueError(f"Markdown log page entry is missing page_id: {log_path}")

        lines: list[str] | None = None
        for event in events:
            if event.get("project") != project:
                continue
            payload = event.get("payload") or {}
            event_type = event.get("event_type")
            if event_type == "page_create" and str(payload.get("page_id") or "") == log_page_id:
                lines = _journal_lines_to_text(payload.get("lines"))
            elif event_type == "page_update" and str(payload.get("page_id") or "") == log_page_id:
                if lines is None:
                    raise ValueError(f"page_update references log page before page_create in event {event.get('event_id')}")
                lines = _journal_lines_to_text(payload.get("lines"))
            elif event_type == "page_rename" and str(payload.get("page_id") or "") == log_page_id:
                if lines is None:
                    raise ValueError(f"page_rename references log page before page_create in event {event.get('event_id')}")
                source_path = str(payload.get("source_path") or "")
                if source_path and _safe_markdown_relative_path(source_path) != log_path:
                    continue
                lines = _journal_lines_to_text(payload.get("lines"))
            elif event_type == "log_append" and str(payload.get("page_id") or "") == log_page_id:
                if lines is None:
                    raise ValueError(f"log_append references log page before page_create in event {event.get('event_id')}")
                lines.extend(_journal_lines_to_text(payload.get("inserted_lines")))
            elif event_type == "event_revert" and str(payload.get("page_id") or "") == log_page_id:
                if lines is None:
                    raise ValueError(f"event_revert references log page before page_create in event {event.get('event_id')}")
                target_event_type = payload.get("target_event_type")
                if target_event_type == "log_append":
                    removed = _journal_lines_to_text(payload.get("removed_lines"))
                    if not removed or lines[-len(removed):] != removed:
                        raise ValueError(f"event_revert does not match log page tail in event {event.get('event_id')}")
                    del lines[-len(removed):]
                elif target_event_type == "page_update":
                    current = _journal_lines_to_text(payload.get("current_lines"))
                    if lines != current:
                        raise ValueError(f"event_revert current_lines do not match log page in event {event.get('event_id')}")
                    lines = _journal_lines_to_text(payload.get("previous_lines"))
                elif target_event_type == "page_rename":
                    current = _journal_lines_to_text(payload.get("current_lines"))
                    previous_source_path = str(payload.get("previous_source_path") or "")
                    if lines != current:
                        raise ValueError(f"event_revert current_lines do not match log page in event {event.get('event_id')}")
                    if previous_source_path and _safe_markdown_relative_path(previous_source_path) != log_path:
                        continue
                    lines = _journal_lines_to_text(payload.get("previous_lines"))
        if lines is None:
            raise ValueError(f"journal does not contain a page_create event for log page: {log_page_id}")
        record_file_lines = _journal_record_file_log_projection_lines(project, events)
        if record_file_lines:
            if lines and lines[-1].strip():
                lines.append("")
            while lines and len(lines) >= 2 and not lines[-1].strip() and not lines[-2].strip():
                lines.pop()
            lines.extend(record_file_lines)
        return markdown_projection_text(
            log_path,
            page_id=log_page_id,
            title=str(item.get("title") or ""),
            aliases=[str(alias) for alias in item.get("aliases") or []],
            lines=lines,
        )

    def markdown_projection_diff(self, output_folder: str | Path, *, context: int = 3) -> dict[str, Any]:
        project = self._require_project()
        output = Path(output_folder)
        manifest = self._markdown_manifest_for_project(project)
        files = manifest.get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError(f"project is not a Markdown mirror project or has no Markdown manifest: {project}")

        projections = self._markdown_projection_files(project, files)
        status = self.export_markdown(output, check=True)
        diffs = []
        for relative_path, projected in projections.items():
            target = _safe_markdown_output_path(output, relative_path)
            if target.exists():
                current = target.read_text(encoding="utf-8")
                if current == projected:
                    continue
                kind = "changed"
                current_lines = current.splitlines(keepends=True)
            else:
                kind = "missing"
                current_lines = []
            diff_lines = list(
                difflib.unified_diff(
                    current_lines,
                    projected.splitlines(keepends=True),
                    fromfile=f"current/{relative_path}",
                    tofile=f"projection/{relative_path}",
                    n=max(0, context),
                )
            )
            diffs.append({"path": relative_path, "kind": kind, "diff": diff_lines})

        exclude_dirs = tuple(str(item) for item in manifest.get("exclude_dirs") or [])
        existing_files = {
            path.relative_to(output).as_posix(): path
            for path in iter_markdown_files(output, exclude_dirs=exclude_dirs)
        } if output.exists() else {}
        for relative_path in status["extra_files"]:
            current = existing_files.get(relative_path)
            current_lines = current.read_text(encoding="utf-8").splitlines(keepends=True) if current else []
            diff_lines = list(
                difflib.unified_diff(
                    current_lines,
                    [],
                    fromfile=f"current/{relative_path}",
                    tofile=f"projection/{relative_path}",
                    n=max(0, context),
                )
            )
            diffs.append({"path": relative_path, "kind": "extra", "diff": diff_lines})

        result = dict(status)
        result.update({"diffs": diffs, "diff_count": len(diffs)})
        return result

    def append_markdown_lines(self, title: str, lines: list[str]) -> dict[str, Any]:
        with self.connection:
            return self._append_markdown_lines_uncommitted(title, lines)

    def _append_markdown_lines_uncommitted(self, title: str, lines: list[str]) -> dict[str, Any]:
        project = self._require_project()
        if not lines:
            raise ValueError("append requires at least one line")
        if not self._markdown_manifest_for_project(project):
            raise ValueError(f"project is not a Markdown-backed project: {project}")

        candidates = self.page_handle_candidates(title)
        if not candidates:
            raise ValueError(f"page not found: {title}")
        if len(candidates) > 1:
            raise ValueError(f"page handle is ambiguous: {title}; use a unique title for append alpha")
        page_id = str(candidates[0]["page_id"])
        now = int(time.time())
        start_row = self.connection.execute(
            """
            SELECT COALESCE(MAX(line_index) + 1, 0) AS start_index
            FROM lines
            WHERE project = ? AND page_id = ?
            """,
            (project, page_id),
        ).fetchone()
        start_index = int(start_row["start_index"])
        appended = []
        edge_rows = []
        for offset, text in enumerate(lines):
            line_index = start_index + offset
            line_id = f"line-{uuid4().hex}"
            appended.append(
                {
                    "line_id": line_id,
                    "line_index": line_index,
                    "text": text,
                    "created": now,
                    "updated": now,
                    "user_id": "grasp",
                }
            )
            self.connection.execute(
                """
                INSERT INTO lines (project, line_id, page_id, line_index, text, created, updated, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (project, line_id, page_id, line_index, text, now, now, "grasp"),
            )
            for target_title in parse_markdown_links(text):
                edge_rows.append((project, page_id, line_id, target_title, normalize_title(target_title)))
        _insert_edge_rows(self.connection, edge_rows)
        refresh_edge_resolutions(self.connection, project)
        rebuild_unresolved_targets(self.connection, project)
        self.connection.execute(
            """
            UPDATE pages
            SET updated = ?,
                line_count = (SELECT COUNT(*) FROM lines WHERE project = ? AND page_id = ?)
            WHERE project = ? AND id = ?
            """,
            (now, project, page_id, project, page_id),
        )
        _refresh_project_counts_sql(self.connection, project)
        page = self._page_by_id(page_id)
        return {
            "project": project,
            "page": page.to_summary() if page is not None else {"id": page_id, "title": title},
            "start_index": start_index,
            "appended_lines": appended,
            "appended_line_count": len(appended),
            "edge_count": len(edge_rows),
        }

    def append_markdown_lines_with_event(
        self,
        title: str,
        lines: list[str],
        *,
        event_type: str,
        payload: dict[str, Any],
        actor: str = "",
        session_id: str = "",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if event_type not in {"section_append", "log_append"}:
            raise ValueError(f"unsupported append event_type: {event_type!r}")
        with self.write_transaction():
            append_result = self._append_markdown_lines_uncommitted(title, lines)
            event_payload = {
                "page_id": append_result["page"]["id"],
                "title": append_result["page"]["title"],
                **payload,
                "inserted_lines": append_result["appended_lines"],
            }
            event = make_journal_event(
                event_type,
                project=append_result["project"],
                payload=event_payload,
            )
            insert_store_event(self.connection, event, actor=actor, session_id=session_id)
        return append_result, event

    def create_markdown_page(
        self,
        title: str,
        *,
        source_path: str | Path,
        lines: list[str],
    ) -> dict[str, Any]:
        with self.connection:
            return self._create_markdown_page_uncommitted(
                title,
                source_path=source_path,
                lines=lines,
            )

    def _create_markdown_page_uncommitted(
        self,
        title: str,
        *,
        source_path: str | Path,
        lines: list[str],
    ) -> dict[str, Any]:
        project = self._require_project()
        manifest = self._markdown_manifest_for_project(project)
        files = manifest.get("files")
        if not isinstance(files, dict):
            raise ValueError(f"project is not a Markdown-backed project: {project}")

        source_path = _safe_markdown_relative_path(source_path)
        if source_path in files:
            raise ValueError(f"Markdown source path already belongs to another page: {source_path}")

        metadata = parse_frontmatter(lines)
        file_title = markdown_title(Path(source_path))
        title = (title or metadata.title or first_markdown_h1_title(lines) or file_title).strip()
        if not title:
            raise ValueError("new page title must not be empty")
        norm_title = normalize_title(title)
        if not norm_title:
            raise ValueError("new page title normalizes to empty")

        collision = self.connection.execute(
            """
            SELECT page_id
            FROM page_handles
            WHERE project = ? AND handle_norm = ?
            LIMIT 1
            """,
            (project, norm_title),
        ).fetchone()
        if collision is not None:
            raise ValueError(f"page handle already belongs to another page: {title}")

        page_id = metadata.page_id or markdown_page_id(Path(source_path))
        if self._page_by_id(page_id) is not None:
            raise ValueError(f"page id already exists: {page_id}")

        aliases = []
        for alias in [file_title, *metadata.aliases]:
            alias = str(alias).strip()
            if not alias or normalize_title(alias) == norm_title:
                continue
            if normalize_title(alias) in {normalize_title(existing) for existing in aliases}:
                continue
            aliases.append(alias)

        graph_role = markdown_graph_role(Path(source_path), metadata)
        now = int(time.time())
        line_payloads = [
            {
                "line_id": f"line-{uuid4().hex}",
                "line_index": line_index,
                "text": text,
                "created": now,
                "updated": now,
                "user_id": "grasp",
            }
            for line_index, text in enumerate(lines)
        ]
        edge_rows = []
        emits_edges = markdown_graph_role_emits_edges(graph_role)
        in_code_fence = False
        if emits_edges:
            for line in line_payloads:
                targets, in_code_fence = parse_markdown_line_links(
                    str(line["text"]),
                    in_code_fence=in_code_fence,
                )
                for target_title in targets:
                    edge_rows.append((project, page_id, line["line_id"], target_title, normalize_title(target_title)))

        new_files = {str(path): dict(item) for path, item in files.items() if isinstance(item, dict)}
        new_files[source_path] = {
            "page_id": page_id,
            "title": title,
            "norm_title": norm_title,
            "aliases": aliases,
            "graph_role": graph_role,
            "hash": "",
            "mtime_ns": 0,
        }
        manifest = dict(manifest)
        manifest["files"] = new_files

        alias_map = dict(self.project_title_aliases(project))
        for alias in aliases:
            alias_norm = normalize_title(alias)
            if alias_norm and alias_norm != norm_title:
                alias_map[alias_norm] = title

        self.connection.execute(
            """
            INSERT INTO pages (project, id, title, norm_title, created, updated, views, line_count)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (project, page_id, title, norm_title, now, now, len(line_payloads)),
        )
        self.connection.executemany(
            """
            INSERT INTO lines (project, line_id, page_id, line_index, text, created, updated, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    project,
                    line["line_id"],
                    page_id,
                    line["line_index"],
                    line["text"],
                    line["created"],
                    line["updated"],
                    line["user_id"],
                )
                for line in line_payloads
            ),
        )
        _insert_edge_rows(self.connection, edge_rows)
        _insert_page_handles(
            self.connection,
            _page_handle_rows_for_markdown_page(
                project,
                page_id=page_id,
                title=title,
                aliases=aliases,
                source_path=source_path,
                graph_role=graph_role,
            ),
        )
        refresh_edge_resolutions(self.connection, project)
        rebuild_unresolved_targets(self.connection, project)
        _refresh_project_counts_sql(self.connection, project)
        _write_metadata(
            self.connection,
            {
                f"project.{project}.title_aliases": json.dumps(
                    alias_map,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                f"project.{project}.markdown_manifest": json.dumps(
                    manifest,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            },
        )

        page = self._page_by_id(page_id)
        return {
            "project": project,
            "page": page.to_summary() if page is not None else {"id": page_id, "title": title},
            "source_path": source_path,
            "aliases": aliases,
            "graph_role": graph_role,
            "previous_lines": [],
            "lines": self._markdown_line_payloads(project, page_id),
            "previous_line_count": 0,
            "line_count": len(line_payloads),
            "edge_count": len(edge_rows),
        }

    def replace_markdown_page_lines(self, title: str, lines: list[str]) -> dict[str, Any]:
        with self.connection:
            return self._replace_markdown_page_lines_uncommitted(title, lines)

    def _replace_markdown_page_lines_uncommitted(self, title: str, lines: list[str]) -> dict[str, Any]:
        project = self._require_project()
        manifest = self._markdown_manifest_for_project(project)
        if not manifest:
            raise ValueError(f"project is not a Markdown-backed project: {project}")

        candidates = self.page_handle_candidates(title)
        if not candidates:
            raise ValueError(f"page not found: {title}")
        if len(candidates) > 1:
            raise ValueError(f"page handle is ambiguous: {title}; use a unique title for write-page alpha")
        page_id = str(candidates[0]["page_id"])
        source_path, _ = self._markdown_manifest_entry_for_page(manifest, page_id)
        graph_role = self._markdown_graph_role_for_page(project, page_id)
        previous_lines = self._markdown_line_payloads(project, page_id)
        previous_by_index = {line["line_index"]: line for line in previous_lines}
        now = int(time.time())
        next_lines = []
        for line_index, text in enumerate(lines):
            previous = previous_by_index.get(line_index)
            if previous is not None and previous["text"] == text:
                next_lines.append(dict(previous))
                next_lines[-1]["line_index"] = line_index
                continue
            next_lines.append(
                {
                    "line_id": f"line-{uuid4().hex}",
                    "line_index": line_index,
                    "text": text,
                    "created": now,
                    "updated": now,
                    "user_id": "grasp",
                }
            )
        edge_count = self._replace_markdown_page_line_payloads_uncommitted(
            project,
            page_id,
            next_lines,
            graph_role=graph_role,
            updated=now,
        )
        page = self._page_by_id(page_id)
        return {
            "project": project,
            "page": page.to_summary() if page is not None else {"id": page_id, "title": title},
            "source_path": source_path,
            "previous_lines": previous_lines,
            "lines": self._markdown_line_payloads(project, page_id),
            "previous_line_count": len(previous_lines),
            "line_count": len(next_lines),
            "edge_count": edge_count,
        }

    def write_markdown_page_with_event(
        self,
        title: str,
        *,
        lines: list[str],
        create: bool = False,
        source_path: str | Path | None = None,
        message: str = "",
        actor: str = "",
        session_id: str = "",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if create and not source_path:
            raise ValueError("write-page --create requires --path")
        if not create and source_path:
            raise ValueError("write-page --path is only valid with --create")

        with self.write_transaction():
            if create:
                update_result = self._create_markdown_page_uncommitted(
                    title,
                    source_path=source_path or "",
                    lines=lines,
                )
                event_type = "page_create"
                payload = {
                    "page_id": update_result["page"]["id"],
                    "title": update_result["page"]["title"],
                    "source_path": update_result["source_path"],
                    "aliases": update_result["aliases"],
                    "graph_role": update_result["graph_role"],
                    "message": message,
                    "lines": update_result["lines"],
                }
            else:
                update_result = self._replace_markdown_page_lines_uncommitted(title, lines)
                event_type = "page_update"
                payload = {
                    "page_id": update_result["page"]["id"],
                    "title": update_result["page"]["title"],
                    "message": message,
                    "previous_lines": update_result["previous_lines"],
                    "lines": update_result["lines"],
                }
            event = make_journal_event(
                event_type,
                project=update_result["project"],
                payload=payload,
            )
            insert_store_event(self.connection, event, actor=actor, session_id=session_id)
        return update_result, event

    def rename_markdown_page(
        self,
        target: str,
        new_title: str,
        *,
        target_kind: str = "handle",
        new_source_path: str | None = None,
        update_heading: bool = True,
    ) -> dict[str, Any]:
        project = self._require_project()
        manifest = self._markdown_manifest_for_project(project)
        files = manifest.get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError(f"project is not a Markdown-backed project: {project}")

        new_title = new_title.strip()
        if not new_title:
            raise ValueError("new title must not be empty")
        new_norm_title = normalize_title(new_title)
        if not new_norm_title:
            raise ValueError("new title normalizes to empty")

        page = self._resolve_markdown_rename_target(target, target_kind)
        if page is None:
            raise ValueError(f"page not found for rename target: {target}")
        page_id = page.id
        previous_source_path, item = self._markdown_manifest_entry_for_page(manifest, page_id)
        graph_role = str(item.get("graph_role") or self._markdown_graph_role_for_page(project, page_id))
        source_path = (
            _safe_markdown_relative_path(new_source_path)
            if new_source_path is not None
            else previous_source_path
        )
        if source_path in files and str(files[source_path].get("page_id") or "") != page_id:
            raise ValueError(f"Markdown source path already belongs to another page: {source_path}")
        collision_rows = self.connection.execute(
            """
            SELECT DISTINCT page_id
            FROM page_handles
            WHERE project = ? AND handle_norm = ? AND page_id != ?
            """,
            (project, new_norm_title, page_id),
        ).fetchall()
        if collision_rows:
            raise ValueError(f"new title handle already belongs to another page: {new_title}")

        previous_lines = self._markdown_line_payloads(project, page_id)
        next_lines = [dict(line) for line in previous_lines]
        now = int(time.time())
        heading_updated = False
        if update_heading:
            heading_index = _matching_markdown_h1_line_index(
                [str(line.get("text", "")) for line in next_lines],
                page.title,
            )
            if heading_index is not None:
                next_lines[heading_index]["text"] = f"# {new_title}"
                next_lines[heading_index]["updated"] = now
                heading_updated = True

        previous_aliases = [str(alias) for alias in item.get("aliases") or []]
        aliases = _markdown_rename_aliases(
            previous_title=page.title,
            new_title=new_title,
            previous_source_path=previous_source_path,
            new_source_path=source_path,
            previous_aliases=previous_aliases,
        )
        edge_count = self._apply_markdown_page_identity(
            project,
            page_id,
            title=new_title,
            source_path=source_path,
            aliases=aliases,
            lines=next_lines,
            graph_role=graph_role,
            updated=now,
        )
        renamed_page = self._page_by_id(page_id)
        return {
            "project": project,
            "page": renamed_page.to_summary() if renamed_page is not None else {"id": page_id, "title": new_title},
            "previous_title": page.title,
            "title": new_title,
            "previous_source_path": previous_source_path,
            "source_path": source_path,
            "previous_aliases": previous_aliases,
            "aliases": aliases,
            "previous_lines": previous_lines,
            "lines": self._markdown_line_payloads(project, page_id),
            "heading_updated": heading_updated,
            "edge_count": edge_count,
        }

    def revert_markdown_page_rename(
        self,
        page_id: str,
        *,
        previous_title: str,
        title: str,
        previous_source_path: str,
        source_path: str,
        previous_aliases: list[str],
        aliases: list[str],
        previous_lines: list[dict[str, Any]],
        current_lines: list[dict[str, Any]],
    ) -> dict[str, Any]:
        project = self._require_project()
        if not self._markdown_manifest_for_project(project):
            raise ValueError(f"project is not a Markdown-backed project: {project}")
        page = self._page_by_id(page_id)
        if page is None:
            raise ValueError(f"page id not found: {page_id}")
        expected_current = self._normalized_journal_lines(current_lines)
        restored = self._normalized_journal_lines(previous_lines)
        actual_current = self._line_compare_payloads(self._markdown_line_payloads(project, page_id))
        if actual_current != self._line_compare_payloads(expected_current):
            raise ValueError("page_rename current lines no longer match the current page")
        if page.title != title:
            raise ValueError("page_rename title no longer matches the current page")
        current_source_path, item = self._markdown_manifest_entry_for_page(
            self._markdown_manifest_for_project(project),
            page_id,
        )
        if current_source_path != source_path:
            raise ValueError("page_rename source path no longer matches the current page")
        graph_role = str(item.get("graph_role") or self._markdown_graph_role_for_page(project, page_id))
        now = int(time.time())
        edge_count = self._apply_markdown_page_identity(
            project,
            page_id,
            title=previous_title,
            source_path=_safe_markdown_relative_path(previous_source_path),
            aliases=[str(alias) for alias in previous_aliases],
            lines=restored,
            graph_role=graph_role,
            updated=now,
        )
        restored_page = self._page_by_id(page_id)
        return {
            "project": project,
            "page": restored_page.to_summary() if restored_page is not None else {"id": page_id, "title": previous_title},
            "previous_title": previous_title,
            "title": title,
            "previous_source_path": previous_source_path,
            "source_path": source_path,
            "previous_aliases": previous_aliases,
            "aliases": aliases,
            "lines": self._markdown_line_payloads(project, page_id),
            "restored_line_count": len(restored),
            "edge_count": edge_count,
        }

    def revert_markdown_page_create(
        self,
        page_id: str,
        *,
        title: str,
        source_path: str,
        aliases: list[str],
        current_lines: list[dict[str, Any]],
    ) -> dict[str, Any]:
        project = self._require_project()
        manifest = self._markdown_manifest_for_project(project)
        files = manifest.get("files")
        if not isinstance(files, dict):
            raise ValueError(f"project is not a Markdown-backed project: {project}")
        page = self._page_by_id(page_id)
        if page is None:
            raise ValueError(f"page id not found: {page_id}")
        expected_current = self._normalized_journal_lines(current_lines)
        actual_current = self._line_compare_payloads(self._markdown_line_payloads(project, page_id))
        if actual_current != self._line_compare_payloads(expected_current):
            raise ValueError("page_create current lines no longer match the current page")
        if page.title != title:
            raise ValueError("page_create title no longer matches the current page")
        current_source_path, item = self._markdown_manifest_entry_for_page(manifest, page_id)
        source_path = _safe_markdown_relative_path(source_path)
        if current_source_path != source_path:
            raise ValueError("page_create source path no longer matches the current page")
        current_aliases = [str(alias) for alias in item.get("aliases") or []]
        aliases = [str(alias) for alias in aliases]
        if current_aliases != aliases:
            raise ValueError("page_create aliases no longer match the current page")

        new_files = {
            str(path): dict(file_item)
            for path, file_item in files.items()
            if isinstance(file_item, dict) and str(file_item.get("page_id") or "") != page_id
        }
        manifest = dict(manifest)
        manifest["files"] = new_files

        alias_map = dict(self.project_title_aliases(project))
        for alias in aliases:
            alias_norm = normalize_title(alias)
            if alias_norm and alias_map.get(alias_norm) == title:
                alias_map.pop(alias_norm, None)

        with self.connection:
            self.connection.execute(
                "DELETE FROM pages WHERE project = ? AND id = ?",
                (project, page_id),
            )
            refresh_edge_resolutions(self.connection, project)
            rebuild_unresolved_targets(self.connection, project)
            _refresh_project_counts_sql(self.connection, project)
            _write_metadata(
                self.connection,
                {
                    f"project.{project}.title_aliases": json.dumps(
                        alias_map,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    f"project.{project}.markdown_manifest": json.dumps(
                        manifest,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            )
        return {
            "project": project,
            "page": {"id": page_id, "title": title},
            "source_path": source_path,
            "removed_lines": expected_current,
            "removed_line_count": len(expected_current),
        }

    def revert_markdown_append(self, page_id: str, inserted_lines: list[dict[str, Any]]) -> dict[str, Any]:
        project = self._require_project()
        if not self._markdown_manifest_for_project(project):
            raise ValueError(f"project is not a Markdown-backed project: {project}")
        if not inserted_lines:
            raise ValueError("append event has no inserted lines")

        expected = []
        for item in inserted_lines:
            if not isinstance(item, dict):
                raise ValueError("inserted_lines items must be objects")
            line_id = str(item.get("line_id") or "")
            if not line_id:
                raise ValueError("inserted line is missing line_id")
            expected.append(
                {
                    "line_id": line_id,
                    "line_index": int(item.get("line_index", -1)),
                    "text": str(item.get("text", "")),
                }
            )

        placeholders = ",".join("?" for _ in expected)
        rows = self.connection.execute(
            f"""
            SELECT line_id, line_index, text
            FROM lines
            WHERE project = ? AND page_id = ? AND line_id IN ({placeholders})
            ORDER BY line_index
            """,
            (project, page_id, *(item["line_id"] for item in expected)),
        ).fetchall()
        actual = [
            {"line_id": row["line_id"], "line_index": row["line_index"], "text": row["text"]}
            for row in rows
        ]
        if actual != expected:
            raise ValueError("event lines no longer match the current page")

        max_row = self.connection.execute(
            "SELECT MAX(line_index) AS max_index FROM lines WHERE project = ? AND page_id = ?",
            (project, page_id),
        ).fetchone()
        max_index = max_row["max_index"]
        expected_indexes = [item["line_index"] for item in expected]
        tail_start = int(max_index) - len(expected) + 1 if max_index is not None else 0
        if expected_indexes != list(range(tail_start, int(max_index) + 1)):
            raise ValueError("event is not at the page tail; refusing non-tail revert")

        now = int(time.time())
        line_ids = [item["line_id"] for item in expected]
        placeholders = ",".join("?" for _ in line_ids)
        with self.connection:
            self.connection.execute(
                f"DELETE FROM edges WHERE project = ? AND line_id IN ({placeholders})",
                (project, *line_ids),
            )
            self.connection.execute(
                f"DELETE FROM lines WHERE project = ? AND page_id = ? AND line_id IN ({placeholders})",
                (project, page_id, *line_ids),
            )
            refresh_edge_resolutions(self.connection, project)
            rebuild_unresolved_targets(self.connection, project)
            self.connection.execute(
                """
                UPDATE pages
                SET updated = ?,
                    line_count = (SELECT COUNT(*) FROM lines WHERE project = ? AND page_id = ?)
                WHERE project = ? AND id = ?
                """,
                (now, project, page_id, project, page_id),
            )
            _refresh_project_counts_sql(self.connection, project)
        page = self._page_by_id(page_id)
        return {
            "project": project,
            "page": page.to_summary() if page is not None else {"id": page_id},
            "removed_lines": expected,
            "removed_line_count": len(expected),
        }

    def revert_markdown_page_update(
        self,
        page_id: str,
        previous_lines: list[dict[str, Any]],
        current_lines: list[dict[str, Any]],
    ) -> dict[str, Any]:
        project = self._require_project()
        if not self._markdown_manifest_for_project(project):
            raise ValueError(f"project is not a Markdown-backed project: {project}")
        expected_current = self._normalized_journal_lines(current_lines)
        restored = self._normalized_journal_lines(previous_lines)
        actual_current = self._line_compare_payloads(self._markdown_line_payloads(project, page_id))
        if actual_current != self._line_compare_payloads(expected_current):
            raise ValueError("page_update current lines no longer match the current page")
        graph_role = self._markdown_graph_role_for_page(project, page_id)
        now = int(time.time())
        edge_count = self._replace_markdown_page_line_payloads(
            project,
            page_id,
            restored,
            graph_role=graph_role,
            updated=now,
        )
        page = self._page_by_id(page_id)
        return {
            "project": project,
            "page": page.to_summary() if page is not None else {"id": page_id},
            "lines": self._markdown_line_payloads(project, page_id),
            "restored_line_count": len(restored),
            "edge_count": edge_count,
        }

    def _markdown_graph_role_for_page(self, project: str, page_id: str) -> str:
        manifest = self._markdown_manifest_for_project(project)
        files = manifest.get("files") if isinstance(manifest, dict) else None
        if isinstance(files, dict):
            for item in files.values():
                if isinstance(item, dict) and str(item.get("page_id") or "") == page_id:
                    return str(item.get("graph_role") or "content")
        return "content"

    def _resolve_markdown_rename_target(self, target: str, target_kind: str) -> Page | None:
        if target_kind == "page-id":
            return self._page_by_id(target)
        if target_kind == "path":
            return self._page_by_source_path(_safe_markdown_relative_path(target))
        if target_kind != "handle":
            raise ValueError("rename target kind must be one of: handle, page-id, path")
        candidates = self.page_handle_candidates(target)
        if len(candidates) > 1:
            raise ValueError(f"page handle is ambiguous: {target}; use --target page-id or --target path")
        if not candidates:
            return None
        return self._page_by_id(str(candidates[0]["page_id"]))

    def _markdown_manifest_entry_for_page(
        self,
        manifest: dict[str, Any],
        page_id: str,
    ) -> tuple[str, dict[str, Any]]:
        files = manifest.get("files")
        if not isinstance(files, dict):
            raise ValueError("Markdown manifest has no files")
        for source_path, item in files.items():
            if isinstance(item, dict) and str(item.get("page_id") or "") == page_id:
                return str(source_path), dict(item)
        raise ValueError(f"Markdown manifest has no source path for page_id: {page_id}")

    def _markdown_line_payloads(self, project: str, page_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT line_id, line_index, text, created, updated, user_id
            FROM lines
            WHERE project = ? AND page_id = ?
            ORDER BY line_index
            """,
            (project, page_id),
        ).fetchall()
        return [
            {
                "line_id": row["line_id"],
                "line_index": row["line_index"],
                "text": row["text"],
                "created": row["created"],
                "updated": row["updated"],
                "user_id": row["user_id"],
            }
            for row in rows
        ]

    def _normalized_journal_lines(self, lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        now = int(time.time())
        for line_index, item in enumerate(lines):
            if not isinstance(item, dict):
                raise ValueError("journal line payload must be an object")
            line_id = str(item.get("line_id") or "")
            if not line_id:
                raise ValueError("journal line payload is missing line_id")
            normalized.append(
                {
                    "line_id": line_id,
                    "line_index": line_index,
                    "text": str(item.get("text", "")),
                    "created": item.get("created", now),
                    "updated": item.get("updated", now),
                    "user_id": item.get("user_id"),
                }
            )
        return normalized

    def _line_compare_payloads(self, lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "line_id": str(line.get("line_id") or ""),
                "line_index": int(line.get("line_index", -1)),
                "text": str(line.get("text", "")),
            }
            for line in lines
        ]

    def _replace_markdown_page_line_payloads(
        self,
        project: str,
        page_id: str,
        lines: list[dict[str, Any]],
        *,
        graph_role: str,
        updated: int,
    ) -> int:
        with self.connection:
            return self._replace_markdown_page_line_payloads_uncommitted(
                project,
                page_id,
                lines,
                graph_role=graph_role,
                updated=updated,
            )

    def _replace_markdown_page_line_payloads_uncommitted(
        self,
        project: str,
        page_id: str,
        lines: list[dict[str, Any]],
        *,
        graph_role: str,
        updated: int,
    ) -> int:
        edge_rows = []
        emits_edges = markdown_graph_role_emits_edges(graph_role)
        in_code_fence = False
        self.connection.execute(
            "DELETE FROM edges WHERE project = ? AND source_page_id = ?",
            (project, page_id),
        )
        self.connection.execute(
            "DELETE FROM lines WHERE project = ? AND page_id = ?",
            (project, page_id),
        )
        for line_index, item in enumerate(lines):
            line_id = str(item.get("line_id") or f"line-{uuid4().hex}")
            text = str(item.get("text", ""))
            created = item.get("created")
            line_updated = item.get("updated")
            user_id = item.get("user_id")
            self.connection.execute(
                """
                INSERT INTO lines (project, line_id, page_id, line_index, text, created, updated, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (project, line_id, page_id, line_index, text, created, line_updated, user_id),
            )
            if not emits_edges:
                continue
            targets, in_code_fence = parse_markdown_line_links(text, in_code_fence=in_code_fence)
            for target_title in targets:
                edge_rows.append((project, page_id, line_id, target_title, normalize_title(target_title)))
        _insert_edge_rows(self.connection, edge_rows)
        refresh_edge_resolutions(self.connection, project)
        rebuild_unresolved_targets(self.connection, project)
        self.connection.execute(
            """
            UPDATE pages
            SET updated = ?,
                line_count = (SELECT COUNT(*) FROM lines WHERE project = ? AND page_id = ?)
            WHERE project = ? AND id = ?
            """,
            (updated, project, page_id, project, page_id),
        )
        _refresh_project_counts_sql(self.connection, project)
        return len(edge_rows)

    def _apply_markdown_page_identity(
        self,
        project: str,
        page_id: str,
        *,
        title: str,
        source_path: str,
        aliases: list[str],
        lines: list[dict[str, Any]],
        graph_role: str,
        updated: int,
    ) -> int:
        title = title.strip()
        source_path = _safe_markdown_relative_path(source_path)
        norm_title = normalize_title(title)
        manifest = self._markdown_manifest_for_project(project)
        files = manifest.get("files")
        if not isinstance(files, dict):
            raise ValueError("Markdown manifest has no files")
        _, previous_item = self._markdown_manifest_entry_for_page(manifest, page_id)
        new_files = {
            str(path): dict(item)
            for path, item in files.items()
            if isinstance(item, dict) and str(item.get("page_id") or "") != page_id
        }
        if source_path in new_files:
            raise ValueError(f"Markdown source path already belongs to another page: {source_path}")
        manifest_item = dict(previous_item)
        manifest_item.update(
            {
                "page_id": page_id,
                "title": title,
                "norm_title": norm_title,
                "aliases": aliases,
                "graph_role": graph_role,
            }
        )
        new_files[source_path] = manifest_item
        manifest = dict(manifest)
        manifest["files"] = new_files

        old_alias_norms = {
            row["handle_norm"]
            for row in self.connection.execute(
                """
                SELECT handle_norm
                FROM page_handles
                WHERE project = ? AND page_id = ? AND handle_source = 'alias'
                """,
                (project, page_id),
            ).fetchall()
        }
        alias_map = dict(self.project_title_aliases(project))
        for alias_norm in old_alias_norms:
            alias_map.pop(str(alias_norm), None)
        for alias in aliases:
            alias_norm = normalize_title(alias)
            if alias_norm and alias_norm != norm_title:
                alias_map[alias_norm] = title
        alias_map.pop(norm_title, None)

        handle_rows = _page_handle_rows_for_markdown_page(
            project,
            page_id=page_id,
            title=title,
            aliases=aliases,
            source_path=source_path,
            graph_role=graph_role,
        )
        with self.connection:
            self.connection.execute(
                """
                UPDATE pages
                SET title = ?, norm_title = ?, updated = ?
                WHERE project = ? AND id = ?
                """,
                (title, norm_title, updated, project, page_id),
            )
            edge_count = self._replace_markdown_page_line_payloads_uncommitted(
                project,
                page_id,
                lines,
                graph_role=graph_role,
                updated=updated,
            )
            self.connection.execute(
                "DELETE FROM page_handles WHERE project = ? AND page_id = ?",
                (project, page_id),
            )
            _insert_page_handles(self.connection, handle_rows)
            refresh_edge_resolutions(self.connection, project)
            rebuild_unresolved_targets(self.connection, project)
            _refresh_project_counts_sql(self.connection, project)
            _write_metadata(
                self.connection,
                {
                    f"project.{project}.title_aliases": json.dumps(
                        alias_map,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    f"project.{project}.markdown_manifest": json.dumps(
                        manifest,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            )
        return edge_count

    def page_lines_around(
        self,
        page: Page,
        *,
        center_index: int,
        context: int,
    ) -> tuple[list[Line], dict[str, Any]]:
        project = self._require_project()
        context = max(0, context)
        start_index = max(0, center_index - context)
        end_index = min(page.line_count - 1, center_index + context)
        rows = self.connection.execute(
            """
            SELECT * FROM lines
            WHERE project = ? AND page_id = ? AND line_index BETWEEN ? AND ?
            ORDER BY line_index
            """,
            (project, page.id, start_index, end_index),
        ).fetchall()
        center_line_id = next(
            (row["line_id"] for row in rows if row["line_index"] == center_index),
            None,
        )
        return [self._line_from_row(row) for row in rows], {
            "around_line_id": center_line_id,
            "center_index": center_index,
            "start_index": start_index,
            "end_index": end_index,
            "context": context,
            "truncated_before": start_index > 0,
            "truncated_after": end_index < page.line_count - 1,
        }

    def backlinks(self, title: str, limit: int | None = None, offset: int = 0) -> list[Edge]:
        project = self._require_project()
        candidates = self.page_handle_candidates(title)
        if len(candidates) > 1:
            target_filter = "e.resolution_status = 'ambiguous' AND e.target_handle_norm = ?"
            target_value = normalize_title(title)
        elif len(candidates) == 1:
            target_filter = "e.resolution_status = 'resolved_unique' AND e.target_page_id = ?"
            target_value = candidates[0]["page_id"]
        else:
            target_filter = "e.resolution_status = 'unresolved' AND e.target_handle_norm = ?"
            target_value = self._resolve_title_norm(title, project=project)
        return self._backlinks_by_filter(project, target_filter, target_value, limit=limit, offset=offset)

    def backlinks_report(self, title: str, limit: int | None = None, offset: int = 0) -> dict[str, Any]:
        project = self._require_project()
        candidates = self.page_handle_candidates(title)
        if len(candidates) <= 1:
            edges = self.backlinks(title, limit=limit, offset=offset)
            resolution_status = "resolved_unique" if candidates else "unresolved"
            return {
                "query": title,
                "resolution_status": resolution_status,
                "ambiguity": None,
                "backlinks": [edge.to_dict() for edge in edges],
                "count_returned": len(edges),
                "count_total": self._backlink_count_for_status(title, resolution_status, candidates),
                "offset": offset,
            }

        handle_norm = normalize_title(title)
        target_filter = "e.resolution_status = 'ambiguous' AND e.target_handle_norm = ?"
        handle_edges = self._backlinks_by_filter(project, target_filter, handle_norm, limit=limit, offset=offset)
        handle_items = [edge.to_dict() for edge in handle_edges]
        handle_count_total = self._backlink_count_by_filter(project, target_filter, handle_norm)
        candidate_backlinks = []
        for candidate in candidates:
            candidate_filter = "e.resolution_status = 'resolved_unique' AND e.target_page_id = ?"
            candidate_edges = self._backlinks_by_filter(
                project,
                candidate_filter,
                candidate["page_id"],
                limit=limit,
                offset=0,
            )
            candidate_backlinks.append(
                {
                    "candidate": candidate,
                    "resolved_backlinks": [edge.to_dict() for edge in candidate_edges],
                    "count_returned": len(candidate_edges),
                    "count_total": self._backlink_count_by_filter(project, candidate_filter, candidate["page_id"]),
                    "offset": 0,
                }
            )
        return {
            "query": title,
            "resolution_status": "ambiguous",
            "ambiguity": self._handle_ambiguity(title, candidates),
            "backlinks": handle_items,
            "count_returned": len(handle_items),
            "count_total": handle_count_total,
            "offset": offset,
            "handle_backlinks": {
                "items": handle_items,
                "count_returned": len(handle_items),
                "count_total": handle_count_total,
                "offset": offset,
            },
            "candidate_backlinks": candidate_backlinks,
        }

    def _backlink_count_for_status(
        self,
        title: str,
        resolution_status: str,
        candidates: list[dict[str, Any]],
    ) -> int:
        project = self._require_project()
        if resolution_status == "resolved_unique" and candidates:
            return self._backlink_count_by_filter(
                project,
                "e.resolution_status = 'resolved_unique' AND e.target_page_id = ?",
                candidates[0]["page_id"],
            )
        return self._backlink_count_by_filter(
            project,
            "e.resolution_status = 'unresolved' AND e.target_handle_norm = ?",
            self._resolve_title_norm(title, project=project),
        )

    def _backlink_count_by_filter(self, project: str, target_filter: str, target_value: str) -> int:
        row = self.connection.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM edges e
            WHERE e.project = ? AND {target_filter}
            """,
            (project, target_value),
        ).fetchone()
        return int(row["count"])

    def _backlinks_by_filter(
        self,
        project: str,
        target_filter: str,
        target_value: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Edge]:
        query = """
            SELECT
              e.source_page_id,
              source.title AS source_title,
              source.views AS source_views,
              source.updated AS source_updated,
              e.line_id,
              line.line_index,
              line.text AS line_text,
              e.target_title,
              e.target_norm,
              e.target_handle,
              e.target_handle_norm,
              e.target_page_id,
              e.resolution_status
            FROM edges e
            JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
            JOIN lines line ON line.project = e.project AND line.line_id = e.line_id
            WHERE e.project = ? AND {target_filter}
            ORDER BY source.views DESC, COALESCE(source.updated, 0) DESC, source.title, line.line_index
        """.format(target_filter=target_filter)
        params: list[Any] = [project, target_value]
        if limit is not None and limit >= 0:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        elif offset:
            query += " LIMIT -1 OFFSET ?"
            params.append(offset)
        return [self._edge_from_row(row) for row in self.connection.execute(query, params)]

    def link_stats(self, title: str) -> dict[str, Any]:
        project = self._require_project()
        candidates = self.page_handle_candidates(title)
        ambiguity = self._handle_ambiguity(title, candidates) if len(candidates) > 1 else None
        page = self._page_by_id(candidates[0]["page_id"]) if len(candidates) == 1 else None
        norm = page.norm_title if page is not None else self._resolve_title_norm(title, project=project)
        if page is None and ambiguity is not None:
            link_count = 0
            source_page_count = 0
            canonical_title = title
        elif page is None:
            unresolved_target = self.connection.execute(
                "SELECT * FROM unresolved_targets WHERE project = ? AND target_norm = ?",
                (project, norm),
            ).fetchone()
            link_count = int(unresolved_target["link_count"]) if unresolved_target is not None else 0
            source_page_count = int(unresolved_target["source_page_count"]) if unresolved_target is not None else 0
            canonical_title = unresolved_target["title"] if unresolved_target is not None else title
        else:
            row = self.connection.execute(
                """
                SELECT COUNT(*) AS link_count, COUNT(DISTINCT source_page_id) AS source_page_count
                FROM edges
                WHERE project = ? AND resolution_status = 'resolved_unique' AND target_page_id = ?
                """,
                (project, page.id),
            ).fetchone()
            link_count = int(row["link_count"])
            source_page_count = int(row["source_page_count"])
            canonical_title = page.title

        result = {
            "query": title,
            "title": canonical_title,
            "normalized_title": norm,
            "page_exists": page is not None,
            "page": page.to_summary() if page is not None else None,
            "ambiguity": ambiguity,
            "link_count": link_count,
            "source_page_count": source_page_count,
            "link_multiplicity": link_multiplicity(link_count),
            "recovery_hints": None,
        }
        if page is None and link_count == 0 and ambiguity is None:
            result["recovery_hints"] = self.recovery_hints(title, limit=3)
        return result

    def unresolved_targets(self, limit: int | None = None) -> list[dict[str, Any]]:
        project = self._require_project()
        fetch_limit = _expanded_unresolved_fetch_limit(limit)
        if limit is None or limit < 0:
            rows = self.connection.execute(
                """
                SELECT * FROM unresolved_targets
                WHERE project = ?
                ORDER BY link_count DESC, source_page_count DESC, total_source_views DESC, latest_source_updated DESC, title
                """,
                (project,),
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT * FROM unresolved_targets
                WHERE project = ?
                ORDER BY link_count DESC, source_page_count DESC, total_source_views DESC, latest_source_updated DESC, title
                LIMIT ?
                """,
                (project, fetch_limit),
            ).fetchall()
        items = self._unresolved_target_materialized_rows_to_dicts(rows)
        items.sort(key=_unresolved_target_output_rank_key)
        if limit is not None and limit >= 0:
            return items[:limit]
        return items

    def _unresolved_targets_dynamic(self, limit: int | None = None) -> list[dict[str, Any]]:
        project = self._require_project()
        fetch_limit = _expanded_unresolved_fetch_limit(limit)
        params: list[Any] = [project]
        if limit is not None and limit >= 0:
            params.append(fetch_limit)
        rows = self.connection.execute(
            self._unresolved_target_stats_sql(fetch_limit),
            params,
        ).fetchall()
        items = [self._unresolved_target_row_to_dict(row) for row in rows]
        items.sort(key=_unresolved_target_output_rank_key)
        if limit is not None and limit >= 0:
            return items[:limit]
        return items

    def unresolved_targets_from_page(self, page: Page, limit: int | None = None) -> list[dict[str, Any]]:
        project = self._require_project()
        fetch_limit = _expanded_unresolved_fetch_limit(limit)
        params: list[Any] = [project, page.id]
        if limit is not None and limit >= 0:
            params.append(fetch_limit)
        rows = self.connection.execute(
            self._unresolved_target_stats_sql(fetch_limit, source_page_id=page.id),
            params,
        ).fetchall()
        items = [self._unresolved_target_row_to_dict(row, source_page_id=page.id) for row in rows]
        items.sort(key=_unresolved_target_output_rank_key)
        if limit is not None and limit >= 0:
            return items[:limit]
        return items

    def related(self, title: str, limit: int | None = None) -> list[dict[str, Any]]:
        candidates = self.page_handle_candidates(title)
        if len(candidates) > 1:
            return self._related_ambiguous_handle(title, limit)
        if len(candidates) == 1:
            page = self._page_by_id(candidates[0]["page_id"])
        else:
            page = None
        if page is None:
            return self._related_missing_target(title, limit)
        return self._related_existing_page(page, limit)

    def related_report(self, title: str, limit: int | None = None) -> dict[str, Any]:
        candidates = self.page_handle_candidates(title)
        related = self.related(title, limit=limit)
        if len(candidates) > 1:
            candidate_related = []
            for candidate in candidates:
                page = self._page_by_id(candidate["page_id"])
                candidate_items = self._related_existing_page(page, limit) if page is not None else []
                candidate_related.append(
                    {
                        "candidate": candidate,
                        "related": candidate_items,
                        "count_returned": len(candidate_items),
                    }
                )
            return {
                "query": title,
                "resolution_status": "ambiguous",
                "ambiguity": self._handle_ambiguity(title, candidates),
                "related": related,
                "count_returned": len(related),
                "limit": limit,
                "recovery_hints": None,
                "candidate_related": candidate_related,
            }

        resolution_status = "resolved_unique" if candidates else "unresolved"
        return {
            "query": title,
            "resolution_status": resolution_status,
            "ambiguity": None,
            "related": related,
            "count_returned": len(related),
            "limit": limit,
            "recovery_hints": None if related else self.recovery_hints(title, limit=3),
            "candidate_related": [],
        }

    def _related_existing_page(self, page: Page, limit: int | None = None) -> list[dict[str, Any]]:
        direct = self._neighbor_ids(page.id, page.norm_title)
        scores: Counter[str] = Counter()
        via: dict[str, list[str]] = {}
        for neighbor_id in self._sort_page_ids(direct):
            neighbor = self._page_by_id(neighbor_id)
            if neighbor is None:
                continue
            for related_id in self._sort_page_ids(self._neighbor_ids(neighbor.id, neighbor.norm_title)):
                if related_id == page.id or related_id in direct:
                    continue
                scores[related_id] += 1
                via.setdefault(related_id, [])
                if len(via[related_id]) < 3:
                    via[related_id].append(neighbor.title)

        related_pages = []
        for related_id, score in scores.items():
            related_page = self._page_by_id(related_id)
            if related_page is None:
                continue
            related_pages.append({**related_page.to_summary(), "score": score, "via": via[related_id]})

        related_pages.sort(key=lambda item: (-item["score"], -item["views"], item["title"].casefold()))
        if limit is not None and limit >= 0:
            return related_pages[:limit]
        return related_pages

    def _related_ambiguous_handle(self, title: str, limit: int | None = None) -> list[dict[str, Any]]:
        project = self._require_project()
        norm = normalize_title(title)
        query = """
            SELECT
              source.*,
              COUNT(*) AS score,
              MIN(e.target_handle) AS target_title
            FROM edges e
            JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
            WHERE e.project = ? AND e.resolution_status = 'ambiguous' AND e.target_handle_norm = ?
            GROUP BY source.id
            ORDER BY score DESC, source.views DESC, COALESCE(source.updated, 0) DESC, source.title
        """
        params: list[Any] = [project, norm]
        if limit is not None and limit >= 0:
            query += " LIMIT ?"
            params.append(limit)

        rows = self.connection.execute(query, params).fetchall()
        return [
            {
                **self._page_from_row(row).to_summary(),
                "score": int(row["score"]),
                "relation": "ambiguous-handle-source",
                "via": [row["target_title"]],
            }
            for row in rows
        ]

    def _related_missing_target(self, title: str, limit: int | None = None) -> list[dict[str, Any]]:
        project = self._require_project()
        norm = normalize_title(title)
        query = """
            SELECT
              source.*,
              COUNT(*) AS score,
              MIN(e.target_title) AS target_title
            FROM edges e
            JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
            WHERE e.project = ? AND e.resolution_status = 'unresolved' AND e.target_handle_norm = ?
            GROUP BY source.id
            ORDER BY score DESC, source.views DESC, COALESCE(source.updated, 0) DESC, source.title
        """
        params: list[Any] = [project, norm]
        if limit is not None and limit >= 0:
            query += " LIMIT ?"
            params.append(limit)

        rows = self.connection.execute(query, params).fetchall()
        return [
            {
                **self._page_from_row(row).to_summary(),
                "score": int(row["score"]),
                "relation": "backlink-source",
                "via": [row["target_title"]],
            }
            for row in rows
        ]

    def paths_between(
        self,
        source_title: str,
        target_title: str,
        *,
        max_depth: int = 4,
        limit: int = 3,
    ) -> dict[str, Any]:
        max_depth = max(0, max_depth)
        limit = max(0, limit)
        source_node = self._resolve_graph_node(source_title)
        target_node = self._resolve_graph_node(target_title)
        recovery_hints = {
            "source": None if source_node is not None else self.recovery_hints(source_title, limit=3),
            "target": None if target_node is not None else self.recovery_hints(target_title, limit=3),
            "path": None,
        }
        result = {
            "query": {"source": source_title, "target": target_title},
            "source": source_node,
            "target": target_node,
            "max_depth": max_depth,
            "paths": [],
            "path_count": 0,
            "truncated": False,
            "recovery_hints": _nonempty_recovery_hints(recovery_hints),
        }
        if source_node is None or target_node is None or limit == 0:
            return result

        source_key = source_node["node_key"]
        target_key = target_node["node_key"]
        graph = self._path_graph()
        nodes = graph["nodes"]
        adjacency = graph["adjacency"]
        edge_examples = graph["edge_examples"]

        if source_key == target_key:
            result["paths"] = [
                {
                    "distance": 0,
                    "nodes": [nodes[source_key]],
                    "edges": [],
                }
            ]
            result["path_count"] = 1
            return result

        paths: list[list[str]] = []
        queue: deque[list[str]] = deque([[source_key]])
        best_depth_by_node: dict[str, int] = {source_key: 0}
        shortest_depth: int | None = None
        expansions = 0
        expansion_limit = 50_000

        while queue and len(paths) < limit:
            path = queue.popleft()
            depth = len(path) - 1
            if shortest_depth is not None and depth >= shortest_depth:
                continue
            if depth >= max_depth:
                continue

            current = path[-1]
            expansions += 1
            if expansions > expansion_limit:
                result["truncated"] = True
                break

            for neighbor in self._sorted_path_neighbors(current, adjacency, nodes):
                if neighbor in path:
                    continue
                next_depth = depth + 1
                known_depth = best_depth_by_node.get(neighbor)
                if known_depth is not None and known_depth < next_depth:
                    continue
                best_depth_by_node[neighbor] = next_depth
                next_path = [*path, neighbor]
                if neighbor == target_key:
                    shortest_depth = next_depth if shortest_depth is None else shortest_depth
                    paths.append(next_path)
                    if len(paths) >= limit:
                        break
                elif shortest_depth is None:
                    queue.append(next_path)

        result["paths"] = [
            self._format_path(node_path, nodes=nodes, edge_examples=edge_examples)
            for node_path in paths
        ]
        result["path_count"] = len(result["paths"])
        if queue and len(paths) >= limit:
            result["truncated"] = True
        if not result["paths"]:
            recovery_hints["path"] = self._path_no_path_recovery_hints(
                source_title,
                target_title,
                max_depth=max_depth,
                truncated=bool(result["truncated"]),
            )
            result["recovery_hints"] = _nonempty_recovery_hints(recovery_hints)
        return result

    def _path_no_path_recovery_hints(
        self,
        source_title: str,
        target_title: str,
        *,
        max_depth: int,
        truncated: bool,
        related_limit: int = 3,
        backlinks_limit: int = 3,
    ) -> dict[str, Any]:
        return {
            "reason": "search_truncated" if truncated else "no_path_within_max_depth",
            "max_depth": max_depth,
            "next_max_depth": max_depth + 1,
            "related_limit": related_limit,
            "backlinks_limit": backlinks_limit,
            "source_link_stats": self.link_stats(source_title),
            "target_link_stats": self.link_stats(target_title),
            "source_related": self.related(source_title, limit=related_limit),
            "target_related": self.related(target_title, limit=related_limit),
            "source_backlinks": [
                edge.to_dict()
                for edge in self.backlinks(source_title, limit=backlinks_limit)
            ],
            "target_backlinks": [
                edge.to_dict()
                for edge in self.backlinks(target_title, limit=backlinks_limit)
            ],
        }

    def _resolve_graph_node(self, title: str) -> dict[str, Any] | None:
        page = self.resolve_page(title)
        if page is not None:
            return self._page_graph_node(page)

        project = self._require_project()
        row = self.connection.execute(
            "SELECT * FROM unresolved_targets WHERE project = ? AND target_norm = ?",
            (project, normalize_title(title)),
        ).fetchone()
        if row is None:
            return None
        return self._unresolved_graph_node_from_row(row)

    def _path_graph(self) -> dict[str, Any]:
        project = self._require_project()
        page_rows = self.connection.execute(
            """
            SELECT id, title, norm_title, created, updated, views, line_count
            FROM pages
            WHERE project = ?
            """,
            (project,),
        ).fetchall()
        nodes: dict[str, dict[str, Any]] = {}
        page_id_by_norm: dict[str, str] = {}
        for row in page_rows:
            node_key = self._page_node_key(row["id"])
            page_id_by_norm[row["norm_title"]] = row["id"]
            nodes[node_key] = {
                "node_key": node_key,
                "kind": "page",
                "id": row["id"],
                "title": row["title"],
                "normalized_title": row["norm_title"],
                "created": row["created"],
                "updated": row["updated"],
                "views": row["views"],
                "line_count": row["line_count"],
            }

        unresolved_rows = self.connection.execute(
            "SELECT * FROM unresolved_targets WHERE project = ?",
            (project,),
        ).fetchall()
        for row in unresolved_rows:
            node_key = self._unresolved_node_key(row["target_norm"])
            nodes[node_key] = self._unresolved_graph_node_from_row(row)

        adjacency: dict[str, set[str]] = {}
        edge_examples: dict[tuple[str, str], dict[str, Any]] = {}
        edge_rows = self.connection.execute(
            """
            SELECT
              e.source_page_id,
              source.title AS source_title,
              source.views AS source_views,
              source.updated AS source_updated,
              e.line_id,
              line.line_index,
              line.text AS line_text,
              e.target_title,
              e.target_norm,
              e.target_handle,
              e.target_handle_norm,
              e.target_page_id,
              e.resolution_status
            FROM edges e
            JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
            JOIN lines line ON line.project = e.project AND line.line_id = e.line_id
            WHERE e.project = ? AND e.resolution_status IN ('resolved_unique', 'unresolved')
            ORDER BY source.views DESC, COALESCE(source.updated, 0) DESC, source.title, line.line_index
            """,
            (project,),
        ).fetchall()
        for row in edge_rows:
            source_key = self._page_node_key(row["source_page_id"])
            target_page_id = row["target_page_id"] if row["resolution_status"] == "resolved_unique" else None
            target_key = (
                self._page_node_key(target_page_id)
                if target_page_id is not None
                else self._unresolved_node_key(row["target_norm"])
            )
            if source_key == target_key:
                continue
            if source_key not in nodes or target_key not in nodes:
                continue

            adjacency.setdefault(source_key, set()).add(target_key)
            adjacency.setdefault(target_key, set()).add(source_key)
            example_key = self._undirected_edge_key(source_key, target_key)
            if example_key not in edge_examples:
                example = {
                    "stored_source_node": source_key,
                    "stored_target_node": target_key,
                    "source_page_id": row["source_page_id"],
                    "source_title": row["source_title"],
                    "source_views": row["source_views"],
                    "source_updated": row["source_updated"],
                    "line_id": row["line_id"],
                    "line_index": row["line_index"],
                    "line_text": row["line_text"],
                    "target_title": row["target_title"],
                    "target_norm": row["target_norm"],
                    "target_handle": row["target_handle"],
                    "target_handle_norm": row["target_handle_norm"],
                    "target_page_id": row["target_page_id"],
                    "resolution_status": row["resolution_status"],
                }
                annotation = edge_semantic_annotation_from_fields(row["target_title"], row["line_text"])
                if annotation is not None:
                    example["semantic_annotation"] = annotation
                edge_examples[example_key] = example
        return {"nodes": nodes, "adjacency": adjacency, "edge_examples": edge_examples}

    def _format_path(
        self,
        node_path: list[str],
        *,
        nodes: dict[str, dict[str, Any]],
        edge_examples: dict[tuple[str, str], dict[str, Any]],
    ) -> dict[str, Any]:
        edges = []
        for source_key, target_key in zip(node_path, node_path[1:]):
            example = dict(edge_examples[self._undirected_edge_key(source_key, target_key)])
            example["from_node"] = source_key
            example["to_node"] = target_key
            example["direction"] = (
                "forward"
                if example["stored_source_node"] == source_key and example["stored_target_node"] == target_key
                else "reverse"
            )
            edges.append(example)
        return {
            "distance": len(node_path) - 1,
            "nodes": [nodes[node_key] for node_key in node_path],
            "edges": edges,
        }

    def _sorted_path_neighbors(
        self,
        node_key: str,
        adjacency: dict[str, set[str]],
        nodes: dict[str, dict[str, Any]],
    ) -> list[str]:
        return sorted(
            adjacency.get(node_key, set()),
            key=lambda key: (
                -int(nodes[key].get("views") or 0),
                nodes[key].get("title", "").casefold(),
                nodes[key].get("kind", ""),
                key,
            ),
        )

    def _page_graph_node(self, page: Page) -> dict[str, Any]:
        node = page.to_summary()
        node["node_key"] = self._page_node_key(page.id)
        node["kind"] = "page"
        node["normalized_title"] = page.norm_title
        return node

    def _unresolved_graph_node_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "node_key": self._unresolved_node_key(row["target_norm"]),
            "kind": "unresolved",
            "title": row["title"],
            "normalized_title": row["target_norm"],
            "link_count": row["link_count"],
            "source_page_count": row["source_page_count"],
            "total_source_views": row["total_source_views"],
            "latest_source_updated": row["latest_source_updated"],
        }

    @staticmethod
    def _page_node_key(page_id: str) -> str:
        return f"page:{page_id}"

    @staticmethod
    def _unresolved_node_key(target_norm: str) -> str:
        return f"unresolved:{target_norm}"

    @staticmethod
    def _undirected_edge_key(source_key: str, target_key: str) -> tuple[str, str]:
        first, second = sorted((source_key, target_key))
        return first, second

    def suggest(self, partial: str, limit: int = 20, mode: str = "fuzzy") -> list[dict[str, Any]]:
        project = self._require_project()
        limit = max(0, limit)
        if mode not in {"substring", "fuzzy"}:
            raise ValueError("suggest mode must be one of: substring, fuzzy")
        if mode == "fuzzy":
            return self._suggest_fuzzy(project, partial, limit)
        return self._suggest_substring(project, partial, limit)

    def _suggest_substring(self, project: str, partial: str, limit: int) -> list[dict[str, Any]]:
        norm_partial = normalize_title(partial)
        like = f"%{_escape_like(norm_partial)}%"
        prefix = f"{_escape_like(norm_partial)}%"
        rows = self.connection.execute(
            """
            SELECT * FROM pages
            WHERE project = ? AND norm_title LIKE ? ESCAPE '\\'
            ORDER BY
              CASE WHEN norm_title LIKE ? ESCAPE '\\' THEN 0 ELSE 1 END,
              views DESC,
              title
            LIMIT ?
            """,
            (project, like, prefix, limit),
        ).fetchall()
        return [self._suggestion_from_row(row, norm_partial) for row in rows]

    def _suggest_fuzzy(self, project: str, query: str, limit: int) -> list[dict[str, Any]]:
        norm_query = normalize_title(query)
        if not norm_query or limit == 0:
            return []
        rows = self.connection.execute(
            """
            SELECT * FROM pages
            WHERE project = ?
            """,
            (project,),
        ).fetchall()
        suggestions = []
        for row in rows:
            match = _title_suggestion_match(norm_query, row["norm_title"])
            if match is None:
                continue
            summary = self._page_from_row(row).to_summary()
            summary.update(match)
            suggestions.append(summary)
        suggestions.sort(
            key=lambda item: (
                -int(item["match_score"]),
                -int(item["views"]),
                str(item["title"]).casefold(),
            )
        )
        return suggestions[:limit]

    def _suggestion_from_row(self, row: sqlite3.Row, norm_query: str) -> dict[str, Any]:
        summary = self._page_from_row(row).to_summary()
        match = _title_suggestion_match(norm_query, row["norm_title"]) or {
            "match_mode": "substring",
            "match_score": 0,
            "matched_terms": [],
        }
        summary.update(match)
        return summary

    def cross_project_refs(
        self,
        limit: int = 50,
        *,
        sample_limit: int = 3,
        seed_limit: int = 20,
        include_self: bool = False,
        exclude_icons: bool = False,
        semantic_only: bool = False,
    ) -> dict[str, Any]:
        project = self._require_project()
        limit = max(0, limit)
        sample_limit = max(0, sample_limit)
        seed_limit = max(0, seed_limit)
        source_project_names = _source_project_names(project)
        rows = self.connection.execute(
            """
            SELECT
              page.id AS source_page_id,
              page.title AS source_title,
              page.views AS source_views,
              page.updated AS source_updated,
              line.line_id,
              line.line_index,
              line.text AS line_text
            FROM lines line
            JOIN pages page ON page.project = line.project AND page.id = line.page_id
            WHERE line.project = ? AND line.text LIKE '%[/%'
            ORDER BY page.views DESC, COALESCE(page.updated, 0) DESC, page.title, line.line_index
            """,
            (project,),
        ).fetchall()

        refs_by_project: dict[str, list[dict[str, Any]]] = {}
        total_class_counts: Counter[str] = Counter()
        filtered_class_counts: Counter[str] = Counter()
        all_target_projects: set[str] = set()
        filtered_target_projects: set[str] = set()
        total_refs = 0
        filtered_refs = 0
        for row in rows:
            for link in parse_cosense_cross_project_links(row["line_text"]):
                total_refs += 1
                target_project_norm = normalize_title(link.project)
                target_class = (
                    "self-project"
                    if target_project_norm in source_project_names
                    else link.target_class
                )
                total_class_counts[target_class] += 1
                all_target_projects.add(link.project)

                if target_class == "self-project" and not include_self:
                    continue
                if target_class == "icon" and exclude_icons:
                    continue
                if semantic_only and target_class != "semantic":
                    continue

                filtered_refs += 1
                filtered_class_counts[target_class] += 1
                filtered_target_projects.add(link.project)
                refs_by_project.setdefault(link.project, []).append(
                    _cross_project_ref_from_row(row, link, target_class=target_class)
                )

        projects = [
            _cross_project_project_entry(
                target_project,
                refs,
                sample_limit=sample_limit,
                seed_limit=seed_limit,
            )
            for target_project, refs in refs_by_project.items()
        ]
        projects.sort(
            key=lambda item: (
                -item["mention_count"],
                -item["source_page_count"],
                -item["unique_target_count"],
                -item["total_source_views"],
                item["project"].casefold(),
            )
        )
        returned_projects = projects[:limit]
        return {
            "project": project,
            "filters": {
                "include_self": include_self,
                "exclude_icons": exclude_icons,
                "semantic_only": semantic_only,
            },
            "limit": limit,
            "sample_limit": sample_limit,
            "seed_limit": seed_limit,
            "summary": {
                "total_refs": total_refs,
                "total_projects": len(all_target_projects),
                "filtered_refs": filtered_refs,
                "filtered_projects": len(filtered_target_projects),
                "returned_projects": len(returned_projects),
                "target_class_counts": _count_map(total_class_counts),
                "filtered_target_class_counts": _count_map(filtered_class_counts),
            },
            "projects": returned_projects,
        }

    def cross_project_refs_to(
        self,
        target_project: str,
        *,
        limit: int = 5,
        sample_limit: int = 2,
    ) -> dict[str, Any]:
        project = self._require_project()
        limit = max(0, limit)
        sample_limit = max(0, sample_limit)
        target_project_names = _source_project_names(target_project)
        rows = self.connection.execute(
            """
            SELECT
              page.id AS source_page_id,
              page.title AS source_title,
              page.views AS source_views,
              page.updated AS source_updated,
              line.line_id,
              line.line_index,
              line.text AS line_text
            FROM lines line
            JOIN pages page ON page.project = line.project AND page.id = line.page_id
            WHERE line.project = ? AND line.text LIKE '%[/%'
            ORDER BY page.views DESC, COALESCE(page.updated, 0) DESC, page.title, line.line_index
            """,
            (project,),
        ).fetchall()

        refs: list[dict[str, Any]] = []
        class_counts: Counter[str] = Counter()
        for row in rows:
            for link in parse_cosense_cross_project_links(row["line_text"]):
                if normalize_title(link.project) not in target_project_names:
                    continue
                class_counts[link.target_class] += 1
                refs.append(_cross_project_ref_from_row(row, link, target_class=link.target_class))

        target_counts: Counter[tuple[str, str]] = Counter(
            (ref["target_title"], ref["target_class"])
            for ref in refs
        )
        source_page_ids = {ref["source_page_id"] for ref in refs}
        top_targets = [
            {
                "title": title,
                "target_class": target_class,
                "mention_count": mention_count,
            }
            for (title, target_class), mention_count in target_counts.most_common(limit)
        ]
        return {
            "project": project,
            "target_project": target_project,
            "mention_count": len(refs),
            "source_page_count": len(source_page_ids),
            "unique_target_count": len(target_counts),
            "target_class_counts": _count_map(class_counts),
            "top_targets": top_targets,
            "examples": refs[:sample_limit],
        }

    def top_internal_links(self, limit: int = 10, *, sample_limit: int = 2) -> list[dict[str, Any]]:
        project = self._require_project()
        limit = max(0, limit)
        sample_limit = max(0, sample_limit)
        if limit == 0:
            return []
        rows = self.connection.execute(
            """
            WITH edge_stats AS (
              SELECT
                e.target_norm,
                COUNT(*) AS link_count,
                COUNT(DISTINCT e.line_id) AS line_count,
                COUNT(DISTINCT e.source_page_id) AS source_page_count,
                MAX(CASE WHEN e.resolution_status = 'resolved_unique' THEN 1 ELSE 0 END) AS target_page_exists,
                MAX(COALESCE(source.updated, 0)) AS latest_source_updated
              FROM edges e
              JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
              WHERE e.project = ?
              GROUP BY e.target_norm
            ),
            source_stats AS (
              SELECT target_norm, SUM(views) AS total_source_views
              FROM (
                SELECT DISTINCT e.target_norm, e.source_page_id, source.views
                FROM edges e
                JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
                WHERE e.project = ?
              )
              GROUP BY target_norm
            ),
            title_choice AS (
              SELECT target_norm, target_title
              FROM (
                SELECT
                  target_norm,
                  target_title,
                  ROW_NUMBER() OVER (
                    PARTITION BY target_norm
                    ORDER BY COUNT(*) DESC, target_title
                  ) AS rn
                FROM edges
                WHERE project = ?
                GROUP BY target_norm, target_title
              )
              WHERE rn = 1
            )
            SELECT
              edge_stats.target_norm,
              title_choice.target_title,
              edge_stats.link_count,
              edge_stats.line_count,
              edge_stats.source_page_count,
              COALESCE(source_stats.total_source_views, 0) AS total_source_views,
              edge_stats.latest_source_updated,
              edge_stats.target_page_exists
            FROM edge_stats
            JOIN source_stats ON source_stats.target_norm = edge_stats.target_norm
            JOIN title_choice ON title_choice.target_norm = edge_stats.target_norm
            ORDER BY
              edge_stats.link_count DESC,
              edge_stats.source_page_count DESC,
              total_source_views DESC,
              edge_stats.latest_source_updated DESC,
              title_choice.target_title
            LIMIT ?
            """,
            (project, project, project, limit),
        ).fetchall()
        return [
            {
                "title": row["target_title"],
                "normalized_title": row["target_norm"],
                "target_page_exists": bool(row["target_page_exists"]),
                "link_count": row["link_count"],
                "line_count": row["line_count"],
                "source_page_count": row["source_page_count"],
                "total_source_views": row["total_source_views"],
                "latest_source_updated": row["latest_source_updated"],
                "examples": [
                    edge.to_dict()
                    for edge in self.backlinks_by_norm_query(row["target_norm"], limit=sample_limit)
                ],
            }
            for row in rows
        ]

    def mentions(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
        *,
        include_linked: bool = False,
        unlinked_only: bool = False,
        context: int = 0,
    ) -> dict[str, Any]:
        if not query:
            raise ValueError("mentions query is empty")

        offset = max(0, offset)
        context = max(0, context)
        rows = self._literal_line_rows(query)
        line_targets = self._line_link_targets_for_literal_query(query)
        page_targets = self._page_link_targets_containing_query(query)
        norm_query = normalize_title(query)

        all_page_ids: set[str] = set()
        bare_page_ids: set[str] = set()
        status_line_counts: Counter[str] = Counter()
        status_page_ids: dict[str, set[str]] = {}
        status_bare_occurrences: Counter[str] = Counter()
        filtered_hits: list[dict[str, Any]] = []
        total_occurrences = 0
        bare_occurrences = 0
        linked_occurrences = 0
        total_line_count = 0
        bare_line_count = 0

        for row in rows:
            occurrence_spans = _literal_occurrence_spans(row["line_text"], query)
            if not occurrence_spans:
                continue

            total_line_count += 1
            all_page_ids.add(row["source_page_id"])
            edge_targets = line_targets.get(row["line_id"], [])
            edge_norms = {target["normalized_title"] for target in edge_targets}
            link_spans = _line_internal_link_spans(row["line_text"], edge_norms)
            line_linked_occurrences = sum(
                1
                for span in occurrence_spans
                if _span_is_inside_any(span, link_spans)
            )
            line_total_occurrences = len(occurrence_spans)
            line_bare_occurrences = line_total_occurrences - line_linked_occurrences

            total_occurrences += line_total_occurrences
            linked_occurrences += line_linked_occurrences
            bare_occurrences += line_bare_occurrences

            page_query_targets = page_targets.get(row["source_page_id"], {})
            page_has_exact_link = norm_query in page_query_targets
            page_has_query_link = bool(page_query_targets)
            classification = (
                "exact-link-page"
                if page_has_exact_link
                else "query-link-page"
                if page_has_query_link
                else "unlinked-page"
            )

            if line_bare_occurrences:
                bare_line_count += 1
                bare_page_ids.add(row["source_page_id"])
                status_line_counts[classification] += 1
                status_page_ids.setdefault(classification, set()).add(row["source_page_id"])
                status_bare_occurrences[classification] += line_bare_occurrences

            if not include_linked and line_bare_occurrences == 0:
                continue
            if unlinked_only and classification != "unlinked-page":
                continue

            filtered_hits.append(
                self._mention_hit_from_row(
                    row,
                    occurrence_count=line_total_occurrences,
                    bare_occurrence_count=line_bare_occurrences,
                    linked_occurrence_count=line_linked_occurrences,
                    page_has_exact_link=page_has_exact_link,
                    page_has_query_link=page_has_query_link,
                    query_link_targets=[
                        {"title": target_title, "normalized_title": target_norm}
                        for target_norm, target_title in sorted(page_query_targets.items(), key=lambda item: item[1].casefold())
                    ],
                    line_link_targets=edge_targets,
                    classification=classification,
                )
            )

        if limit is not None and limit >= 0:
            returned_hits = filtered_hits[offset : offset + limit]
        else:
            returned_hits = filtered_hits[offset:]
        returned_hits = self._search_hits_with_context(returned_hits, context=context)

        page_status_counts = {
            classification: {
                "lines": status_line_counts[classification],
                "pages": len(status_page_ids.get(classification, set())),
                "bare_occurrences": status_bare_occurrences[classification],
            }
            for classification in ("exact-link-page", "query-link-page", "unlinked-page")
        }
        come_from_candidate = _score_come_from_candidate(
            query,
            bare_occurrences=bare_occurrences,
            bare_pages=len(bare_page_ids),
            page_status_counts=page_status_counts,
        )
        return {
            "query": query,
            "mode": "unlinked" if unlinked_only else "all" if include_linked else "bare",
            "context": context,
            "summary": {
                "total_lines": total_line_count,
                "total_pages": len(all_page_ids),
                "total_occurrences": total_occurrences,
                "bare_lines": bare_line_count,
                "bare_pages": len(bare_page_ids),
                "bare_occurrences": bare_occurrences,
                "linked_occurrences": linked_occurrences,
                "returned_lines": len(returned_hits),
                "page_status_counts": page_status_counts,
                "come_from_candidate": come_from_candidate,
            },
            "mentions": returned_hits,
        }

    def _literal_line_rows(self, query: str) -> list[sqlite3.Row]:
        project = self._require_project()
        like = f"%{_escape_like(query)}%"
        return self.connection.execute(
            """
            SELECT
              page.id AS source_page_id,
              page.title AS source_title,
              page.views AS source_views,
              page.updated AS source_updated,
              line.line_id,
              line.line_index,
              line.text AS line_text
            FROM lines line
            JOIN pages page ON page.project = line.project AND page.id = line.page_id
            WHERE line.project = ? AND line.text LIKE ? ESCAPE '\\'
            ORDER BY page.views DESC, COALESCE(page.updated, 0) DESC, page.title, line.line_index
            """,
            (project, like),
        ).fetchall()

    def _line_link_targets_for_literal_query(self, query: str) -> dict[str, list[dict[str, str]]]:
        project = self._require_project()
        like = f"%{_escape_like(query)}%"
        rows = self.connection.execute(
            """
            SELECT e.line_id, e.target_title, e.target_norm
            FROM edges e
            JOIN lines line ON line.project = e.project AND line.line_id = e.line_id
            WHERE e.project = ? AND line.text LIKE ? ESCAPE '\\'
            ORDER BY e.line_id, e.id
            """,
            (project, like),
        ).fetchall()
        targets_by_line: dict[str, list[dict[str, str]]] = {}
        seen_by_line: dict[str, set[str]] = {}
        for row in rows:
            line_id = row["line_id"]
            seen = seen_by_line.setdefault(line_id, set())
            if row["target_norm"] in seen:
                continue
            seen.add(row["target_norm"])
            targets_by_line.setdefault(line_id, []).append(
                {
                    "title": row["target_title"],
                    "normalized_title": row["target_norm"],
                }
            )
        return targets_by_line

    def _page_link_targets_containing_query(self, query: str) -> dict[str, dict[str, str]]:
        project = self._require_project()
        norm_query = normalize_title(query)
        if not norm_query:
            return {}
        rows = self.connection.execute(
            """
            SELECT source_page_id, target_norm, MIN(target_title) AS target_title
            FROM edges
            WHERE project = ? AND target_norm LIKE ? ESCAPE '\\'
            GROUP BY source_page_id, target_norm
            ORDER BY source_page_id, target_title
            """,
            (project, f"%{_escape_like(norm_query)}%"),
        ).fetchall()
        targets_by_page: dict[str, dict[str, str]] = {}
        for row in rows:
            targets_by_page.setdefault(row["source_page_id"], {})[row["target_norm"]] = row["target_title"]
        return targets_by_page

    @staticmethod
    def _mention_hit_from_row(
        row: sqlite3.Row,
        *,
        occurrence_count: int,
        bare_occurrence_count: int,
        linked_occurrence_count: int,
        page_has_exact_link: bool,
        page_has_query_link: bool,
        query_link_targets: list[dict[str, str]],
        line_link_targets: list[dict[str, str]],
        classification: str,
    ) -> dict[str, Any]:
        hit = SQLiteStore._search_hit_from_row(row, match_terms=[], match_mode="literal")
        hit.update(
            {
                "occurrence_count": occurrence_count,
                "bare_occurrence_count": bare_occurrence_count,
                "linked_occurrence_count": linked_occurrence_count,
                "page_has_exact_link": page_has_exact_link,
                "page_has_query_link": page_has_query_link,
                "query_link_targets": query_link_targets,
                "line_link_targets": line_link_targets,
                "classification": classification,
            }
        )
        return hit

    def co_links(
        self,
        query: str,
        limit: int = 50,
        *,
        sample_limit: int = 3,
        include_self: bool = False,
        rank_mode: str = "slice",
    ) -> list[dict[str, Any]]:
        if not query:
            raise ValueError("co-links query is empty")
        if rank_mode not in {"slice", "raw"}:
            raise ValueError(f"unsupported co-links rank_mode: {rank_mode}")

        project = self._require_project()
        norm_query = normalize_title(query)
        target_filter = "" if include_self else "AND e.target_norm != ?"
        params: list[Any] = [project, f"%{_escape_like(query)}%"]
        if not include_self:
            params.append(norm_query)
        params.extend([norm_query, f"%{_escape_like(norm_query)}%"])
        if limit is not None and limit >= 0:
            params.append(limit)

        limit_clause = "" if limit is None or limit < 0 else "LIMIT ?"
        order_clause = (
            """
              target_relation_rank ASC,
              edge_stats.line_count DESC,
              edge_stats.source_page_count DESC,
              total_source_views DESC,
              edge_stats.latest_source_updated DESC,
              title_choice.target_title
            """
            if rank_mode == "slice"
            else
            """
              edge_stats.line_count DESC,
              edge_stats.source_page_count DESC,
              total_source_views DESC,
              edge_stats.latest_source_updated DESC,
              title_choice.target_title
            """
        )
        rows = self.connection.execute(
            f"""
            WITH query_edges AS (
              SELECT
                e.target_norm,
                e.target_title,
                e.line_id,
                e.source_page_id,
                source.views,
                source.updated
              FROM lines line
              JOIN edges e ON e.project = line.project AND e.line_id = line.line_id
              JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
              WHERE line.project = ? AND line.text LIKE ? ESCAPE '\\'
              {target_filter}
            ),
            edge_stats AS (
              SELECT
                target_norm,
                COUNT(*) AS link_count,
                COUNT(DISTINCT line_id) AS line_count,
                COUNT(DISTINCT source_page_id) AS source_page_count,
                MAX(COALESCE(updated, 0)) AS latest_source_updated
              FROM query_edges
              GROUP BY target_norm
            ),
            source_stats AS (
              SELECT target_norm, SUM(views) AS total_source_views
              FROM (
                SELECT DISTINCT target_norm, source_page_id, views
                FROM query_edges
              )
              GROUP BY target_norm
            ),
            title_choice AS (
              SELECT target_norm, target_title
              FROM (
                SELECT
                  target_norm,
                  target_title,
                  ROW_NUMBER() OVER (
                    PARTITION BY target_norm
                    ORDER BY COUNT(*) DESC, target_title
                  ) AS rn
                FROM query_edges
                GROUP BY target_norm, target_title
              )
              WHERE rn = 1
            )
            SELECT
              edge_stats.target_norm,
              title_choice.target_title,
              edge_stats.link_count,
              edge_stats.line_count,
              edge_stats.source_page_count,
              COALESCE(source_stats.total_source_views, 0) AS total_source_views,
              edge_stats.latest_source_updated,
              CASE
                WHEN edge_stats.target_norm = ? THEN 2
                WHEN edge_stats.target_norm LIKE ? ESCAPE '\\' THEN 1
                ELSE 0
              END AS target_relation_rank
            FROM edge_stats
            JOIN source_stats ON source_stats.target_norm = edge_stats.target_norm
            JOIN title_choice ON title_choice.target_norm = edge_stats.target_norm
            ORDER BY
            {order_clause}
            {limit_clause}
            """,
            params,
        ).fetchall()
        return [
            {
                "title": row["target_title"],
                "normalized_title": row["target_norm"],
                "link_count": row["link_count"],
                "line_count": row["line_count"],
                "source_page_count": row["source_page_count"],
                "total_source_views": row["total_source_views"],
                "latest_source_updated": row["latest_source_updated"],
                "target_relation": _co_link_target_relation(row["target_relation_rank"]),
                "target_relation_rank": row["target_relation_rank"],
                "examples": [
                    edge.to_dict()
                    for edge in self._co_link_examples(query, row["target_norm"], limit=sample_limit)
                ],
            }
            for row in rows
        ]

    def _co_link_examples(self, query: str, target_norm: str, limit: int = 3) -> list[Edge]:
        if limit <= 0:
            return []
        project = self._require_project()
        rows = self.connection.execute(
            """
            SELECT
              e.source_page_id,
              source.title AS source_title,
              source.views AS source_views,
              source.updated AS source_updated,
              e.line_id,
              line.line_index,
              line.text AS line_text,
              e.target_title,
              e.target_norm,
              e.target_handle,
              e.target_handle_norm,
              e.target_page_id,
              e.resolution_status
            FROM edges e
            JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
            JOIN lines line ON line.project = e.project AND line.line_id = e.line_id
            WHERE e.project = ? AND e.target_norm = ? AND line.text LIKE ? ESCAPE '\\'
            ORDER BY source.views DESC, COALESCE(source.updated, 0) DESC, source.title, line.line_index
            LIMIT ?
            """,
            (project, target_norm, f"%{_escape_like(query)}%", limit),
        ).fetchall()
        return [self._edge_from_row(row) for row in rows]

    def _co_link_total_count(self, query: str, *, include_self: bool = False) -> int:
        project = self._require_project()
        norm_query = normalize_title(query)
        target_filter = "" if include_self else "AND e.target_norm != ?"
        params: list[Any] = [project, f"%{_escape_like(query)}%"]
        if not include_self:
            params.append(norm_query)
        row = self.connection.execute(
            f"""
            WITH query_edges AS (
              SELECT DISTINCT e.target_norm
              FROM lines line
              JOIN edges e ON e.project = line.project AND e.line_id = line.line_id
              WHERE line.project = ? AND line.text LIKE ? ESCAPE '\\'
              {target_filter}
            )
            SELECT COUNT(*) AS count FROM query_edges
            """,
            params,
        ).fetchone()
        return int(row["count"] if row is not None else 0)

    def gather(
        self,
        query: str,
        *,
        budget: int = 4000,
        backlink_limit: int | None = None,
        mention_limit: int | None = None,
        co_link_limit: int | None = None,
    ) -> dict[str, Any]:
        if not query:
            raise ValueError("gather query is empty")

        budget = max(0, budget)
        default_limit = _gather_default_limit(budget)
        backlink_limit = default_limit if backlink_limit is None else max(0, backlink_limit)
        mention_limit = default_limit if mention_limit is None else max(0, mention_limit)
        co_link_limit = default_limit if co_link_limit is None else max(0, co_link_limit)

        link_stats = self.link_stats(query)
        mention_result = self.mentions(query, limit=mention_limit, include_linked=False)
        co_links = self.co_links(query, limit=co_link_limit, sample_limit=2)
        backlinks = [
            edge.to_dict()
            for edge in self.backlinks(query, limit=backlink_limit)
        ]
        mention_summary = mention_result["summary"]
        returned_counts = {
            "mentions": len(mention_result["mentions"]),
            "co_links": len(co_links),
            "backlinks": len(backlinks),
        }
        total_counts = {
            "mentions": mention_summary["bare_lines"],
            "co_links": self._co_link_total_count(query),
            "backlinks": link_stats["link_count"],
        }
        omitted_counts = {
            key: max(0, total_counts[key] - returned_counts[key])
            for key in total_counts
        }
        huge_hub = (
            link_stats["link_count"] >= 100
            or mention_summary["bare_pages"] >= 100
            or mention_summary["total_pages"] >= 100
        )
        banner = None
        if huge_hub:
            banner = {
                "kind": "huge-hub",
                "message": (
                    "This query is a broad hub. Do not bulk-link every bare mention; "
                    "use co-link slices, representative backlinks, and come-from candidates."
                ),
                "thresholds": {
                    "link_count": 100,
                    "bare_pages": 100,
                    "total_pages": 100,
                },
            }

        recipes = [
            {
                "command": ["grasp", "co-links", query, "--limit", str(co_link_limit)],
                "why": "Find narrower slice handles that co-occur with this query.",
            },
            {
                "command": ["grasp", "mentions", query, "--limit", str(mention_limit)],
                "why": "Inspect bare mentions and page-level link status before adding links.",
            },
            {
                "command": ["grasp", "backlinks", query, "--limit", str(backlink_limit)],
                "why": "Read already linked, author-declared retrieval context.",
            },
        ]
        return {
            "query": query,
            "budget": budget,
            "budget_note": (
                "budget is an approximate selector for bounded rows; "
                "returned_counts/omitted_counts are row counts, not token counts"
            ),
            "limits": {
                "backlinks": backlink_limit,
                "mentions": mention_limit,
                "co_links": co_link_limit,
            },
            "co_link_rank_mode": "slice",
            "row_count_basis": {
                "mentions": "bare mention lines",
                "co_links": "ranked co-link targets",
                "backlinks": "incoming link rows",
            },
            "returned_counts": returned_counts,
            "total_counts": total_counts,
            "omitted_counts": omitted_counts,
            "banner": banner,
            "link_stats": link_stats,
            "mention_summary": mention_summary,
            "mentions": mention_result["mentions"],
            "co_links": co_links,
            "backlinks": backlinks,
            "recipes": recipes,
        }

    def search(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
        *,
        mode: str = "literal",
        scope: str = "line",
        context: int = 0,
    ) -> list[dict[str, Any]]:
        project = self._require_project()
        if mode not in {"literal", "boolean"}:
            raise ValueError(f"unsupported search mode: {mode}")
        if scope not in {"line", "page"}:
            raise ValueError(f"unsupported search scope: {scope}")

        if mode == "boolean":
            expression = parse_search_boolean_query(query)
            hits = self._search_boolean(expression, limit=limit, offset=offset, scope=scope)
            return self._search_hits_with_context(hits, context=context)

        hits = self._search_literal(query, limit=limit, offset=offset, scope=scope)
        if hits:
            return self._search_hits_with_context(hits, context=context)

        sql_loose_query = sql_loose_search_key(query)
        hits = self._search_sql_loose_literal(sql_loose_query, limit=limit, offset=offset, scope=scope)
        if hits:
            return self._search_hits_with_context(hits, context=context)

        loose_query = loose_search_key(query)
        terms = _search_terms(query)
        loose_terms = _loose_search_terms(query)
        if self._can_use_python_loose_search(project) and _needs_python_loose_fallback(query, terms, loose_terms):
            hits = self._search_loose_literal(loose_query, limit=limit, offset=offset, scope=scope)
        return self._search_hits_with_context(hits, context=context)

    def _search_literal(self, query: str, limit: int = 50, offset: int = 0, scope: str = "line") -> list[dict[str, Any]]:
        project = self._require_project()
        like = f"%{_escape_like(query)}%"
        if scope == "page":
            return self._search_page_expression(
                "EXISTS (SELECT 1 FROM lines term_line WHERE term_line.project = page.project AND term_line.page_id = page.id AND term_line.text LIKE ? ESCAPE '\\')",
                [like],
                positive_terms=[query],
                limit=limit,
                offset=offset,
                match_mode="literal",
            )

        rows = self.connection.execute(
            """
            SELECT
              page.id AS source_page_id,
              page.title AS source_title,
              page.views AS source_views,
              page.updated AS source_updated,
              line.line_id,
              line.line_index,
              line.text AS line_text
            FROM lines line
            JOIN pages page ON page.project = line.project AND page.id = line.page_id
            WHERE line.project = ? AND line.text LIKE ? ESCAPE '\\'
            ORDER BY page.views DESC, COALESCE(page.updated, 0) DESC, page.title, line.line_index
            LIMIT ? OFFSET ?
            """,
            (project, like, limit, offset),
        ).fetchall()
        normalized_terms = _normalized_unique_terms([query])
        return [
            self._search_hit_from_row(
                row,
                match_terms=_matched_search_terms(row["line_text"], normalized_terms),
                match_mode="literal",
            )
            for row in rows
        ]

    def _search_sql_loose_literal(self, query: str, limit: int = 50, offset: int = 0, scope: str = "line") -> list[dict[str, Any]]:
        project = self._require_project()
        if not query:
            return []
        like = f"%{_escape_like(query)}%"
        if scope == "page":
            return self._search_page_expression(
                "EXISTS (SELECT 1 FROM lines term_line WHERE term_line.project = page.project AND term_line.page_id = page.id AND REPLACE(term_line.text, ?, '') LIKE ? ESCAPE '\\')",
                ["\u30fc", like],
                positive_terms=[query],
                limit=limit,
                offset=offset,
                match_mode="normalized",
                line_transform="sql_loose",
            )

        rows = self.connection.execute(
            """
            SELECT
              page.id AS source_page_id,
              page.title AS source_title,
              page.views AS source_views,
              page.updated AS source_updated,
              line.line_id,
              line.line_index,
              line.text AS line_text
            FROM lines line
            JOIN pages page ON page.project = line.project AND page.id = line.page_id
            WHERE line.project = ? AND REPLACE(line.text, ?, '') LIKE ? ESCAPE '\\'
            ORDER BY page.views DESC, COALESCE(page.updated, 0) DESC, page.title, line.line_index
            LIMIT ? OFFSET ?
            """,
            (project, "\u30fc", like, limit, offset),
        ).fetchall()
        return [
            self._search_hit_from_row(
                row,
                match_terms=_matched_sql_loose_search_terms(row["line_text"], [query]),
                match_mode="normalized",
            )
            for row in rows
        ]

    def _search_loose_literal(self, query: str, limit: int = 50, offset: int = 0, scope: str = "line") -> list[dict[str, Any]]:
        project = self._require_project()
        if not query:
            return []

        rows = self.connection.execute(
            """
            SELECT
              page.id AS source_page_id,
              page.title AS source_title,
              page.views AS source_views,
              page.updated AS source_updated,
              line.line_id,
              line.line_index,
              line.text AS line_text
            FROM lines line
            JOIN pages page ON page.project = line.project AND page.id = line.page_id
            WHERE line.project = ?
            ORDER BY page.views DESC, COALESCE(page.updated, 0) DESC, page.title, line.line_index
            """,
            (project,),
        ).fetchall()

        if scope == "page":
            matching_page_ids = {
                row["source_page_id"]
                for row in rows
                if query in loose_search_key(row["line_text"])
            }
            candidate_rows = [
                row
                for row in rows
                if row["source_page_id"] in matching_page_ids and query in loose_search_key(row["line_text"])
            ]
        else:
            candidate_rows = [row for row in rows if query in loose_search_key(row["line_text"])]

        hits: list[dict[str, Any]] = []
        for row in candidate_rows[offset:]:
            hits.append(
                self._search_hit_from_row(
                    row,
                    match_terms=_matched_loose_search_terms(row["line_text"], [query]),
                    match_mode="normalized",
                )
            )
            if limit >= 0 and len(hits) >= limit:
                break
        return hits

    def _search_boolean(
        self,
        expression: SearchExpression,
        *,
        limit: int = 50,
        offset: int = 0,
        scope: str = "line",
    ) -> list[dict[str, Any]]:
        if scope == "page":
            sql, params = _search_expression_page_sql(expression)
            return self._search_page_expression(
                sql,
                params,
                positive_terms=_search_positive_terms(expression),
                limit=limit,
                offset=offset,
                match_mode="literal",
            )

        project = self._require_project()
        sql, params = _search_expression_line_sql(expression)
        rows = self.connection.execute(
            f"""
            SELECT
              page.id AS source_page_id,
              page.title AS source_title,
              page.views AS source_views,
              page.updated AS source_updated,
              line.line_id,
              line.line_index,
              line.text AS line_text
            FROM lines line
            JOIN pages page ON page.project = line.project AND page.id = line.page_id
            WHERE line.project = ? AND ({sql})
            ORDER BY page.views DESC, COALESCE(page.updated, 0) DESC, page.title, line.line_index
            LIMIT ? OFFSET ?
            """,
            [project, *params, limit, offset],
        ).fetchall()
        positive_terms = _normalized_unique_terms(_search_positive_terms(expression))
        return [
            self._search_hit_from_row(
                row,
                match_terms=_matched_search_terms(row["line_text"], positive_terms),
                match_mode="literal",
            )
            for row in rows
        ]

    def _search_page_expression(
        self,
        page_sql: str,
        page_params: list[Any],
        *,
        positive_terms: list[str],
        limit: int = 50,
        offset: int = 0,
        match_mode: str,
        line_transform: str = "literal",
    ) -> list[dict[str, Any]]:
        project = self._require_project()
        if positive_terms:
            if line_transform == "sql_loose":
                line_filter = " OR ".join("REPLACE(line.text, ?, '') LIKE ? ESCAPE '\\'" for _ in positive_terms)
                line_params: list[Any] = []
                for term in positive_terms:
                    line_params.extend(["\u30fc", f"%{_escape_like(term)}%"])
                normalized_terms = positive_terms
                match_fn = _matched_sql_loose_search_terms
            else:
                line_filter = " OR ".join("line.text LIKE ? ESCAPE '\\'" for _ in positive_terms)
                line_params = [f"%{_escape_like(term)}%" for term in positive_terms]
                normalized_terms = _normalized_unique_terms(positive_terms)
                match_fn = _matched_search_terms
        else:
            line_filter = "line.line_index = 0"
            line_params = []
            normalized_terms = []
            match_fn = _matched_search_terms

        rows = self.connection.execute(
            f"""
            WITH matching_pages AS (
              SELECT page.id AS page_id
              FROM pages page
              WHERE page.project = ? AND ({page_sql})
            )
            SELECT
              page.id AS source_page_id,
              page.title AS source_title,
              page.views AS source_views,
              page.updated AS source_updated,
              line.line_id,
              line.line_index,
              line.text AS line_text
            FROM lines line
            JOIN pages page ON page.project = line.project AND page.id = line.page_id
            JOIN matching_pages matched ON matched.page_id = line.page_id
            WHERE line.project = ? AND ({line_filter})
            ORDER BY page.views DESC, COALESCE(page.updated, 0) DESC, page.title, line.line_index
            LIMIT ? OFFSET ?
            """,
            [project, *page_params, project, *line_params, limit, offset],
        ).fetchall()
        return [
            self._search_hit_from_row(
                row,
                match_terms=match_fn(row["line_text"], normalized_terms),
                match_mode=match_mode,
            )
            for row in rows
        ]

    @staticmethod
    def _search_hit_from_row(row: sqlite3.Row, *, match_terms: list[str], match_mode: str) -> dict[str, Any]:
        return {
            "source_page_id": row["source_page_id"],
            "source_title": row["source_title"],
            "source_views": row["source_views"],
            "source_updated": row["source_updated"],
            "line_id": row["line_id"],
            "line_index": row["line_index"],
            "line_text": row["line_text"],
            "match_mode": match_mode,
            "match_terms": match_terms,
        }

    def _search_hits_with_context(self, hits: list[dict[str, Any]], *, context: int) -> list[dict[str, Any]]:
        context = max(0, context)
        if context == 0:
            return hits

        enriched: list[dict[str, Any]] = []
        for hit in hits:
            hit_with_context = dict(hit)
            page = self._page_by_id(hit["source_page_id"])
            if page is None:
                hit_with_context["context_lines"] = []
                hit_with_context["context_window"] = None
            else:
                lines, window = self.page_lines_around(page, center_index=hit["line_index"], context=context)
                hit_with_context["context_lines"] = [line.to_dict() for line in lines]
                hit_with_context["context_window"] = window
            enriched.append(hit_with_context)
        return enriched

    def _can_use_python_loose_search(self, project: str) -> bool:
        row = self.connection.execute(
            "SELECT lines FROM projects WHERE name = ?",
            (project,),
        ).fetchone()
        return row is not None and int(row["lines"]) <= PYTHON_LOOSE_SEARCH_MAX_LINES

    def recovery_hints(self, query: str, limit: int = 3) -> dict[str, Any]:
        return {
            "suggest": {
                "query": query,
                "limit": limit,
                "suggestions": self.suggest(query, limit=limit),
            },
            "search": {
                "query": query,
                "limit": limit,
                "hits": self.search(query, limit=limit, offset=0),
            },
            "unresolved_targets": {
                "query": query,
                "limit": limit,
                "targets": self.suggest_unresolved_targets(query, limit=limit),
            },
        }

    def suggest_unresolved_targets(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        project = self._require_project()
        norm_query = normalize_title(query)
        like = f"%{_escape_like(norm_query)}%"
        loose_query = loose_recovery_key(norm_query)

        clauses = ["target_norm LIKE ? ESCAPE '\\'"]
        params: list[Any] = [project, like]
        if loose_query and loose_query != norm_query:
            clauses.append("REPLACE(target_norm, ?, '') LIKE ? ESCAPE '\\'")
            params.extend(["\u30fc", f"%{_escape_like(loose_query)}%"])

        params.append(limit)
        rows = self.connection.execute(
            f"""
            SELECT * FROM unresolved_targets
            WHERE project = ? AND ({" OR ".join(clauses)})
            ORDER BY link_count DESC, source_page_count DESC, total_source_views DESC, latest_source_updated DESC, title
            LIMIT ?
            """,
            params,
        ).fetchall()
        return self._unresolved_target_materialized_rows_to_dicts(rows)

    def read(
        self,
        title: str | None = None,
        *,
        page_id: str | None = None,
        source_path: str | None = None,
        line_limit: int | None = None,
        backlink_limit: int = 20,
        related_limit: int = 20,
        unresolved_limit: int = 20,
        related_snippets: bool = False,
        related_snippet_lines: int = 5,
        related_snippet_mode: str = "lead",
    ) -> dict[str, Any]:
        if page_id and source_path:
            raise ValueError("read accepts only one of --page-id or --path")

        explicit_page = False
        if page_id:
            page = self._page_by_id(page_id)
            if page is None:
                raise ValueError(f"page id not found in selected project: {page_id}")
            query = title or page.title
            lookup_title = page.title
            explicit_page = True
        elif source_path:
            page = self._page_by_source_path(source_path)
            if page is None:
                raise ValueError(f"Markdown source path not found in selected project: {source_path}")
            query = title or source_path
            lookup_title = page.title
            explicit_page = True
        else:
            if title is None:
                raise ValueError("read requires a title, --page-id, --path, or --around-line <line-id>")
            query = title
            candidates = self.page_handle_candidates(title)
            if len(candidates) > 1:
                return {
                    "query": title,
                    "page": None,
                    "ambiguity": self._handle_ambiguity(title, candidates),
                    "link_stats": None,
                    "lines": [],
                    "lines_truncated": False,
                    "line_window": None,
                    "backlinks": [],
                    "backlink_count_returned": 0,
                    "backlink_count_total": 0,
                    "related": [],
                    "unresolved_targets": [],
                    "recovery_hints": None,
                }
            if len(candidates) == 1:
                page = self._page_by_id(candidates[0]["page_id"])
            else:
                page = None
            lookup_title = title

        if page is not None and not explicit_page:
            lookup_title = title or page.title

        backlinks = self.backlinks(lookup_title, backlink_limit)
        link_stats = self.link_stats(lookup_title)
        related = self.related(lookup_title if page is None else page.title, related_limit)
        if related_snippets:
            related = self._with_page_snippets(related, related_snippet_lines, mode=related_snippet_mode)

        if page is None:
            recovery_hints = link_stats.get("recovery_hints")
            return {
                "query": query,
                "page": None,
                "ambiguity": None,
                "link_stats": link_stats,
                "lines": [],
                "lines_truncated": False,
                "line_window": None,
                "backlinks": [edge.to_dict() for edge in backlinks],
                "backlink_count_returned": len(backlinks),
                "backlink_count_total": link_stats["link_count"],
                "related": related,
                "unresolved_targets": [],
                "recovery_hints": recovery_hints,
            }

        lines, lines_truncated = self.page_lines(page, line_limit)
        return {
            "query": query,
            "page": page.to_summary(),
            "ambiguity": None,
            "link_stats": link_stats,
            "lines": [line.to_dict() for line in lines],
            "lines_truncated": lines_truncated,
            "line_window": None,
            "backlinks": [edge.to_dict() for edge in backlinks],
            "backlink_count_returned": len(backlinks),
            "backlink_count_total": link_stats["link_count"],
            "related": related,
            "unresolved_targets": self.unresolved_targets_from_page(page, unresolved_limit),
            "recovery_hints": None,
        }

    def read_around_line(
        self,
        line_id: str,
        *,
        title: str | None = None,
        line_context: int = 5,
        backlink_limit: int = 20,
        related_limit: int = 20,
        unresolved_limit: int = 20,
        related_snippets: bool = False,
        related_snippet_lines: int = 5,
        related_snippet_mode: str = "lead",
    ) -> dict[str, Any]:
        if line_context < 0:
            raise ValueError("--line-context must be >= 0")

        line_page = self._line_and_page_by_id(line_id)
        if line_page is None:
            raise ValueError(
                f"line-id not found in selected project: {line_id}; "
                "use a full line_id from --json or --full-ids output"
            )
        page, center_line = line_page

        if title is not None:
            requested_page = self.resolve_page(title)
            if requested_page is None or requested_page.id != page.id:
                raise ValueError(
                    f"--around-line {line_id} belongs to page {page.title}, not {title}"
                )

        lines, line_window = self.page_lines_around(
            page,
            center_index=center_line.index,
            context=line_context,
        )
        backlinks = self.backlinks(page.title, backlink_limit)
        link_stats = self.link_stats(page.title)
        related = self.related(page.title, related_limit)
        if related_snippets:
            related = self._with_page_snippets(related, related_snippet_lines, mode=related_snippet_mode)

        return {
            "query": title or page.title,
            "page": page.to_summary(),
            "link_stats": link_stats,
            "lines": [line.to_dict() for line in lines],
            "lines_truncated": line_window["truncated_before"] or line_window["truncated_after"],
            "line_window": line_window,
            "backlinks": [edge.to_dict() for edge in backlinks],
            "backlink_count_returned": len(backlinks),
            "backlink_count_total": link_stats["link_count"],
            "related": related,
            "unresolved_targets": self.unresolved_targets_from_page(page, unresolved_limit),
            "recovery_hints": None,
        }

    def _with_page_snippets(
        self,
        related: list[dict[str, Any]],
        line_limit: int,
        *,
        mode: str = "lead",
    ) -> list[dict[str, Any]]:
        if mode not in {"lead", "edge"}:
            raise ValueError(f"unsupported related snippet mode: {mode}")

        limit = max(0, line_limit)
        items: list[dict[str, Any]] = []
        for item in related:
            item_with_snippet = dict(item)
            page = self._page_by_id(item["id"])
            if page is None:
                item_with_snippet["snippet_lines"] = []
                item_with_snippet["snippet_truncated"] = False
                item_with_snippet["snippet_mode"] = mode
                item_with_snippet["snippet_window"] = None
            else:
                if mode == "edge":
                    lines, truncated, window = self._related_edge_snippet(page, item, limit)
                    item_with_snippet["snippet_mode"] = window["mode"]
                    item_with_snippet["snippet_window"] = window
                else:
                    lines, truncated = self.page_lines(page, limit)
                    item_with_snippet["snippet_mode"] = "lead"
                    item_with_snippet["snippet_window"] = {
                        "mode": "lead",
                        "start_index": 0,
                        "end_index": lines[-1].index if lines else None,
                        "context_line_id": None,
                        "truncated_before": False,
                        "truncated_after": truncated,
                    }
                item_with_snippet["snippet_lines"] = [line.to_dict() for line in lines]
                item_with_snippet["snippet_truncated"] = truncated
            items.append(item_with_snippet)
        return items

    def _related_edge_snippet(
        self,
        page: Page,
        item: dict[str, Any],
        limit: int,
    ) -> tuple[list[Line], bool, dict[str, Any]]:
        edge = self._related_snippet_edge(item)
        if edge is None or limit == 0:
            lines, truncated = self.page_lines(page, limit)
            return lines, truncated, {
                "mode": "lead-fallback" if edge is None else "edge",
                "start_index": 0,
                "end_index": lines[-1].index if lines else None,
                "context_line_id": None if edge is None else edge.line_id,
                "truncated_before": False,
                "truncated_after": truncated,
            }

        start_index = max(0, edge.line_index - (limit // 2))
        if page.line_count > limit:
            start_index = min(start_index, page.line_count - limit)
        lines, truncated_after = self.page_lines(page, limit, offset=start_index)
        truncated_before = start_index > 0
        return lines, truncated_before or truncated_after, {
            "mode": "edge",
            "start_index": start_index,
            "end_index": lines[-1].index if lines else None,
            "context_line_id": edge.line_id,
            "center_index": edge.line_index,
            "target_title": edge.target_title,
            "target_norm": edge.target_norm,
            "truncated_before": truncated_before,
            "truncated_after": truncated_after,
        }

    def _related_snippet_edge(self, item: dict[str, Any]) -> Edge | None:
        via = item.get("via") or []
        if not via:
            return None
        project = self._require_project()
        target_norms = [normalize_title(title) for title in via if normalize_title(title)]
        if not target_norms:
            return None
        placeholders = ",".join("?" for _ in target_norms)
        rows = self.connection.execute(
            f"""
            SELECT
              e.source_page_id,
              source.title AS source_title,
              source.views AS source_views,
              source.updated AS source_updated,
              e.line_id,
              line.line_index,
              line.text AS line_text,
              e.target_title,
              e.target_norm,
              e.target_handle,
              e.target_handle_norm,
              e.target_page_id,
              e.resolution_status
            FROM edges e
            JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
            JOIN lines line ON line.project = e.project AND line.line_id = e.line_id
            WHERE e.project = ? AND e.source_page_id = ? AND e.target_norm IN ({placeholders})
            ORDER BY line.line_index, e.id
            LIMIT 1
            """,
            [project, item["id"], *target_norms],
        ).fetchall()
        return self._edge_from_row(rows[0]) if rows else None

    def export_ai(
        self,
        title: str,
        *,
        depth: int = 1,
        direct_limit: int | None = None,
        indirect_limit: int | None = None,
        project_url: str = "https://scrapbox.io/nishio/",
    ) -> dict[str, Any]:
        page = self.resolve_page(title)
        if page is None:
            direct_pages = self._pages_from_backlink_sources(title, direct_limit)
            indirect_pages = (
                self._indirect_export_ai_pages(None, direct_pages, indirect_limit)
                if depth >= 2
                else []
            )
        else:
            direct_pages = self._direct_export_ai_pages(page, direct_limit)
            indirect_pages = (
                self._indirect_export_ai_pages(page, direct_pages, indirect_limit)
                if depth >= 2
                else []
            )

        entries: list[dict[str, Any]] = []
        if page is not None:
            entries.append(self._export_ai_page_entry(page, "mainpage"))
        entries.extend(self._export_ai_page_entry(direct_page, "1hopLink") for direct_page in direct_pages)
        entries.extend(self._export_ai_page_entry(indirect_page, "2hopLink") for indirect_page in indirect_pages)

        text = format_export_ai_text(
            query=title,
            page_exists=page is not None,
            entries=entries,
            direct_count=len(direct_pages),
            indirect_count=len(indirect_pages),
            depth=depth,
            project_url=project_url,
        )
        return {
            "query": title,
            "depth": depth,
            "page_exists": page is not None,
            "project_url": project_url,
            "page_count": len(entries),
            "direct_count": len(direct_pages),
            "indirect_count": len(indirect_pages),
            "pages": [
                {
                    "title": entry["page"].title,
                    "type": entry["type"],
                    "created": entry["page"].created,
                    "updated": entry["page"].updated,
                    "line_count": entry["page"].line_count,
                }
                for entry in entries
            ],
            "text": text,
        }

    def _direct_export_ai_pages(self, page: Page, limit: int | None) -> list[Page]:
        if limit == 0:
            return []
        pages: list[Page] = []
        seen = {page.id}
        for direct_page in self._outgoing_existing_pages(page):
            if direct_page.id not in seen:
                pages.append(direct_page)
                seen.add(direct_page.id)
                if _limit_reached(pages, limit):
                    return pages

        for source_page in self._pages_from_backlink_sources(page.title, None):
            if source_page.id not in seen:
                pages.append(source_page)
                seen.add(source_page.id)
                if _limit_reached(pages, limit):
                    return pages
        return pages

    def _indirect_export_ai_pages(
        self,
        main_page: Page | None,
        direct_pages: list[Page],
        limit: int | None,
    ) -> list[Page]:
        if limit == 0:
            return []
        pages: list[Page] = []
        seen = {page.id for page in direct_pages}
        if main_page is not None:
            seen.add(main_page.id)
            for candidate in self._pages_sharing_outgoing_targets(main_page):
                if candidate.id not in seen:
                    pages.append(candidate)
                    seen.add(candidate.id)
                    if _limit_reached(pages, limit):
                        return pages

        for direct_page in direct_pages:
            for candidate in self._direct_export_ai_pages(direct_page, limit=-1):
                if candidate.id not in seen:
                    pages.append(candidate)
                    seen.add(candidate.id)
                    if _limit_reached(pages, limit):
                        return pages
            for candidate in self._pages_sharing_outgoing_targets(direct_page):
                if candidate.id not in seen:
                    pages.append(candidate)
                    seen.add(candidate.id)
                    if _limit_reached(pages, limit):
                        return pages
        return pages

    def _outgoing_existing_pages(self, page: Page) -> list[Page]:
        project = self._require_project()
        rows = self.connection.execute(
            """
            SELECT DISTINCT
              target.*,
              MIN(line.line_index) AS first_line_index,
              MIN(e.id) AS first_edge_id
            FROM edges e
            JOIN lines line ON line.project = e.project AND line.line_id = e.line_id
            JOIN pages target ON target.project = e.project AND target.id = e.target_page_id
            WHERE e.project = ? AND e.source_page_id = ? AND target.id != ?
              AND e.resolution_status = 'resolved_unique'
            GROUP BY target.id
            ORDER BY first_line_index, first_edge_id
            """,
            (project, page.id, page.id),
        ).fetchall()
        return [self._page_from_row(row) for row in rows]

    def _pages_from_backlink_sources(self, title: str, limit: int | None) -> list[Page]:
        project = self._require_project()
        norm = normalize_title(title)
        query = """
            SELECT
              source.*,
              COUNT(*) AS link_count,
              MIN(line.line_index) AS first_line_index
            FROM edges e
            JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
            JOIN lines line ON line.project = e.project AND line.line_id = e.line_id
            WHERE e.project = ? AND e.resolution_status = 'unresolved' AND e.target_handle_norm = ?
            GROUP BY source.id
            ORDER BY link_count DESC, source.views DESC, COALESCE(source.updated, 0) DESC, source.title, first_line_index
        """
        params: list[Any] = [project, norm]
        if limit is not None and limit >= 0:
            query += " LIMIT ?"
            params.append(limit)
        rows = self.connection.execute(query, params).fetchall()
        return [self._page_from_row(row) for row in rows]

    def _pages_sharing_outgoing_targets(self, page: Page) -> list[Page]:
        project = self._require_project()
        rows = self.connection.execute(
            """
            SELECT DISTINCT
              source.*,
              e.target_norm,
              MIN(seed_line.line_index) AS seed_line_index,
              MIN(seed.id) AS seed_edge_id,
              MIN(source_line.line_index) AS first_source_line_index,
              MIN(e.id) AS first_edge_id
            FROM edges seed
            JOIN lines seed_line ON seed_line.project = seed.project AND seed_line.line_id = seed.line_id
            JOIN edges e ON e.project = seed.project AND e.target_norm = seed.target_norm
            JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
            JOIN lines source_line ON source_line.project = e.project AND source_line.line_id = e.line_id
            WHERE seed.project = ? AND seed.source_page_id = ? AND source.id != ?
              AND seed.resolution_status = 'resolved_unique'
              AND e.resolution_status = 'resolved_unique'
            GROUP BY source.id, e.target_norm
            ORDER BY seed_line_index, seed_edge_id, source.views DESC, COALESCE(source.updated, 0) DESC, source.title, first_source_line_index
            """,
            (project, page.id, page.id),
        ).fetchall()
        pages: list[Page] = []
        seen: set[str] = set()
        for row in rows:
            source_page = self._page_from_row(row)
            if source_page.id not in seen:
                pages.append(source_page)
                seen.add(source_page.id)
        return pages

    def _export_ai_page_entry(self, page: Page, page_type: str) -> dict[str, Any]:
        lines, _ = self.page_lines(page)
        return {
            "page": page,
            "type": page_type,
            "lines": lines,
        }

    def _unresolved_target_stats_sql(self, limit: int | None, source_page_id: str | None = None) -> str:
        source_filter = "AND e.source_page_id = ?" if source_page_id is not None else ""
        limit_clause = "" if limit is None or limit < 0 else "LIMIT ?"
        return f"""
            WITH unresolved_edges AS (
              SELECT e.target_norm, e.target_title, e.source_page_id, source.views, source.updated
              FROM edges e
              JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
              WHERE e.project = ? AND e.resolution_status = 'unresolved'
              {source_filter}
            ),
            edge_stats AS (
              SELECT
                target_norm,
                COUNT(*) AS link_count,
                COUNT(DISTINCT source_page_id) AS source_page_count,
                MAX(COALESCE(updated, 0)) AS latest_source_updated
              FROM unresolved_edges
              GROUP BY target_norm
            ),
            source_stats AS (
              SELECT target_norm, SUM(views) AS total_source_views
              FROM (
                SELECT DISTINCT target_norm, source_page_id, views
                FROM unresolved_edges
              )
              GROUP BY target_norm
            ),
            title_choice AS (
              SELECT target_norm, target_title
              FROM (
                SELECT
                  target_norm,
                  target_title,
                  ROW_NUMBER() OVER (
                    PARTITION BY target_norm
                    ORDER BY COUNT(*) DESC, target_title
                  ) AS rn
                FROM unresolved_edges
                GROUP BY target_norm, target_title
              )
              WHERE rn = 1
            )
            SELECT
              edge_stats.target_norm,
              title_choice.target_title,
              edge_stats.link_count,
              edge_stats.source_page_count,
              COALESCE(source_stats.total_source_views, 0) AS total_source_views,
              edge_stats.latest_source_updated
            FROM edge_stats
            JOIN source_stats ON source_stats.target_norm = edge_stats.target_norm
            JOIN title_choice ON title_choice.target_norm = edge_stats.target_norm
            ORDER BY
              edge_stats.link_count DESC,
              edge_stats.source_page_count DESC,
              total_source_views DESC,
              edge_stats.latest_source_updated DESC,
              title_choice.target_title
            {limit_clause}
        """

    def _unresolved_target_row_to_dict(self, row: sqlite3.Row, source_page_id: str | None = None) -> dict[str, Any]:
        norm = row["target_norm"]
        examples = self._unresolved_target_examples(norm, source_page_id=source_page_id)
        item = {
            "title": row["target_title"],
            "normalized_title": norm,
            "link_count": row["link_count"],
            "source_page_count": row["source_page_count"],
            "total_source_views": row["total_source_views"],
            "latest_source_updated": row["latest_source_updated"],
            "examples": [edge.to_dict() for edge in examples],
        }
        return _annotate_unresolved_target_item(item, examples)

    def _unresolved_target_materialized_rows_to_dicts(self, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        target_norms = [row["target_norm"] for row in rows]
        examples_by_norm = self._unresolved_target_materialized_examples(target_norms)
        items = []
        for row in rows:
            examples = examples_by_norm.get(row["target_norm"], [])
            item = {
                "title": row["title"],
                "normalized_title": row["target_norm"],
                "link_count": row["link_count"],
                "source_page_count": row["source_page_count"],
                "total_source_views": row["total_source_views"],
                "latest_source_updated": row["latest_source_updated"],
                "examples": [edge.to_dict() for edge in examples],
            }
            items.append(_annotate_unresolved_target_item(item, examples))
        return items

    def _unresolved_target_materialized_examples(self, target_norms: list[str]) -> dict[str, list[Edge]]:
        if not target_norms:
            return {}
        project = self._require_project()
        placeholders = ",".join("?" for _ in target_norms)
        try:
            rows = self.connection.execute(
                f"""
                SELECT
                  example.target_norm,
                  example.source_page_id,
                  source.title AS source_title,
                  source.views AS source_views,
                  source.updated AS source_updated,
                  example.line_id,
                  line.line_index,
                  line.text AS line_text,
                  example.target_title,
                  example.rank
                FROM unresolved_target_examples example
                JOIN pages source ON source.project = example.project AND source.id = example.source_page_id
                JOIN lines line ON line.project = example.project AND line.line_id = example.line_id
                WHERE example.project = ? AND example.target_norm IN ({placeholders})
                ORDER BY example.target_norm, example.rank
                """,
                [project, *target_norms],
            ).fetchall()
        except sqlite3.OperationalError:
            return {norm: self._unresolved_target_examples(norm) for norm in target_norms}

        examples: dict[str, list[Edge]] = {}
        for row in rows:
            examples.setdefault(row["target_norm"], []).append(self._edge_from_row(row))
        return examples

    def _unresolved_target_examples(self, target_norm: str, source_page_id: str | None = None) -> list[Edge]:
        return self.backlinks_by_norm_query(target_norm, limit=5, source_page_id=source_page_id)

    def backlinks_by_norm_query(
        self,
        target_norm: str,
        limit: int | None = None,
        source_page_id: str | None = None,
    ) -> list[Edge]:
        project = self._require_project()
        source_filter = "AND e.source_page_id = ?" if source_page_id is not None else ""
        query = """
            SELECT
              e.source_page_id,
              source.title AS source_title,
              source.views AS source_views,
              source.updated AS source_updated,
              e.line_id,
              line.line_index,
              line.text AS line_text,
              e.target_title,
              e.target_norm,
              e.target_handle,
              e.target_handle_norm,
              e.target_page_id,
              e.resolution_status
            FROM edges e
            JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
            JOIN lines line ON line.project = e.project AND line.line_id = e.line_id
            WHERE e.project = ? AND e.target_norm = ?
            {source_filter}
            ORDER BY source.views DESC, COALESCE(source.updated, 0) DESC, source.title, line.line_index
        """.format(source_filter=source_filter)
        params: list[Any] = [project, target_norm]
        if source_page_id is not None:
            params.append(source_page_id)
        if limit is not None and limit >= 0:
            query += " LIMIT ?"
            params.append(limit)
        return [self._edge_from_row(row) for row in self.connection.execute(query, params)]

    def _neighbor_ids(self, page_id: str, norm_title: str) -> set[str]:
        project = self._require_project()
        rows = self.connection.execute(
            """
            SELECT target.id AS page_id
            FROM edges e
            JOIN pages target ON target.project = e.project AND target.id = e.target_page_id
            WHERE e.project = ? AND e.source_page_id = ? AND target.id != ?
              AND e.resolution_status = 'resolved_unique'
            UNION
            SELECT e.source_page_id AS page_id
            FROM edges e
            WHERE e.project = ? AND e.resolution_status = 'resolved_unique' AND e.target_page_id = ? AND e.source_page_id != ?
            """,
            (project, page_id, page_id, project, page_id, page_id),
        ).fetchall()
        return {row["page_id"] for row in rows}

    def _sort_page_ids(self, page_ids: set[str]) -> list[str]:
        project = self._require_project()
        rows = self.connection.execute(
            f"""
            SELECT id, title, views
            FROM pages
            WHERE project = ? AND id IN ({",".join("?" for _ in page_ids)})
            ORDER BY title, views DESC
            """,
            [project, *page_ids],
        ).fetchall() if page_ids else []
        return [row["id"] for row in rows]

    def _page_by_id(self, page_id: str) -> Page | None:
        project = self._require_project()
        row = self.connection.execute(
            "SELECT * FROM pages WHERE project = ? AND id = ?",
            (project, page_id),
        ).fetchone()
        return self._page_from_row(row) if row is not None else None

    def _page_by_source_path(self, source_path: str) -> Page | None:
        project = self._require_project()
        row = self.connection.execute(
            """
            SELECT page.*
            FROM page_handles handle
            JOIN pages page ON page.project = handle.project AND page.id = handle.page_id
            WHERE handle.project = ? AND handle.source_path = ?
            ORDER BY page.title
            LIMIT 1
            """,
            (project, source_path),
        ).fetchone()
        return self._page_from_row(row) if row is not None else None

    def _line_and_page_by_id(self, line_id: str) -> tuple[Page, Line] | None:
        project = self._require_project()
        line_row = self.connection.execute(
            "SELECT * FROM lines WHERE project = ? AND line_id = ?",
            (project, line_id),
        ).fetchone()
        if line_row is None:
            return None
        page = self._page_by_id(line_row["page_id"])
        if page is None:
            return None
        return page, self._line_from_row(line_row)

    def _upsert_cosense_page(self, page: dict[str, Any], project: str) -> None:
        page_id = str(page["id"])
        title = str(page["title"])
        lines = page.get("lines") or []
        self.connection.execute("DELETE FROM pages WHERE project = ? AND id = ?", (project, page_id))
        self.connection.execute(
            """
            INSERT INTO pages (project, id, title, norm_title, created, updated, views, line_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project,
                page_id,
                title,
                normalize_title(title),
                parse_cosense_time(page.get("created")),
                parse_cosense_time(page.get("updated")),
                int(page.get("views") or 0),
                len(lines),
            ),
        )
        page_handle_row = (
            project,
            normalize_title(title),
            page_id,
            title,
            "title",
            "",
            "content",
        )
        _insert_page_handles(self.connection, [page_handle_row])

        line_rows = []
        edge_rows = []
        for line_index, line in enumerate(lines):
            line_id = f"{page_id}:{line_index}"
            text = str(line.get("text", ""))
            user = line.get("user") or {}
            line_rows.append(
                (
                    project,
                    line_id,
                    page_id,
                    line_index,
                    text,
                    parse_cosense_time(line.get("created")),
                    parse_cosense_time(line.get("updated")),
                    user.get("id"),
                )
            )
            for target_title in parse_cosense_links(text):
                edge_rows.append((project, page_id, line_id, target_title, normalize_title(target_title)))

        self.connection.executemany(
            """
            INSERT INTO lines (project, line_id, page_id, line_index, text, created, updated, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            line_rows,
        )
        _insert_edge_rows(self.connection, edge_rows)
        refresh_edge_resolutions(self.connection, project)

    def _refresh_project_counts(self, project: str) -> None:
        self.connection.execute(
            """
            UPDATE projects
            SET
              pages = (SELECT COUNT(*) FROM pages WHERE project = ?),
              lines = (SELECT COUNT(*) FROM lines WHERE project = ?),
              edges = (SELECT COUNT(*) FROM edges WHERE project = ?),
              unresolved_targets = (SELECT COUNT(*) FROM unresolved_targets WHERE project = ?)
            WHERE name = ?
            """,
            (project, project, project, project, project),
        )

    def _page_from_row(self, row: sqlite3.Row) -> Page:
        return Page(
            id=row["id"],
            title=row["title"],
            norm_title=row["norm_title"],
            created=row["created"],
            updated=row["updated"],
            views=row["views"],
            lines=(),
            stored_line_count=row["line_count"],
        )

    def _line_from_row(self, row: sqlite3.Row) -> Line:
        return Line(
            line_id=row["line_id"],
            index=row["line_index"],
            text=row["text"],
            created=row["created"],
            updated=row["updated"],
            user_id=row["user_id"],
        )

    def _edge_from_row(self, row: sqlite3.Row) -> Edge:
        keys = set(row.keys())
        return Edge(
            source_page_id=row["source_page_id"],
            source_title=row["source_title"],
            source_views=row["source_views"],
            source_updated=row["source_updated"],
            line_id=row["line_id"],
            line_index=row["line_index"],
            line_text=row["line_text"],
            target_title=row["target_title"],
            target_norm=row["target_norm"],
            target_handle=row["target_handle"] if "target_handle" in keys else row["target_title"],
            target_handle_norm=row["target_handle_norm"] if "target_handle_norm" in keys else row["target_norm"],
            target_page_id=row["target_page_id"] if "target_page_id" in keys else None,
            resolution_status=row["resolution_status"] if "resolution_status" in keys else "unresolved",
        )

    def _count(self, table: str, *, project: str | None = None) -> int:
        if project is None:
            return self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return self.connection.execute(f"SELECT COUNT(*) FROM {table} WHERE project = ?", (project,)).fetchone()[0]

    def _count_if_exists(self, table: str, *, project: str | None = None) -> int | None:
        try:
            return self._count(table, project=project)
        except sqlite3.OperationalError:
            return None


@dataclass(frozen=True)
class SearchTerm:
    value: str


@dataclass(frozen=True)
class SearchNot:
    expression: "SearchExpression"


@dataclass(frozen=True)
class SearchBinary:
    operator: str
    left: "SearchExpression"
    right: "SearchExpression"


SearchExpression = SearchTerm | SearchNot | SearchBinary


@dataclass(frozen=True)
class _SearchToken:
    kind: str
    value: str


def parse_search_boolean_query(query: str) -> SearchExpression:
    tokens = _tokenize_search_boolean_query(query)
    if not tokens:
        raise ValueError("boolean search query is empty")
    parser = _SearchBooleanParser(tokens)
    return parser.parse()


def _tokenize_search_boolean_query(query: str) -> list[_SearchToken]:
    tokens: list[_SearchToken] = []
    index = 0
    while index < len(query):
        char = query[index]
        if char.isspace():
            index += 1
            continue
        if char in "()":
            tokens.append(_SearchToken(char, char))
            index += 1
            continue
        if char in {"'", '"'}:
            quote_char = char
            index += 1
            value_chars: list[str] = []
            while index < len(query):
                char = query[index]
                if char == "\\" and index + 1 < len(query):
                    value_chars.append(query[index + 1])
                    index += 2
                    continue
                if char == quote_char:
                    break
                value_chars.append(char)
                index += 1
            if index >= len(query) or query[index] != quote_char:
                raise ValueError("unterminated quoted phrase in boolean search query")
            value = "".join(value_chars)
            if not value:
                raise ValueError("empty quoted phrase in boolean search query")
            tokens.append(_SearchToken("TERM", value))
            index += 1
            continue

        start = index
        while index < len(query) and not query[index].isspace() and query[index] not in "()":
            index += 1
        value = query[start:index]
        upper = value.upper()
        if upper in {"AND", "OR", "NOT"}:
            tokens.append(_SearchToken(upper, upper))
        else:
            tokens.append(_SearchToken("TERM", value))
    return tokens


class _SearchBooleanParser:
    def __init__(self, tokens: list[_SearchToken]):
        self.tokens = tokens
        self.index = 0

    def parse(self) -> SearchExpression:
        expression = self._parse_or()
        if self._peek() is not None:
            raise ValueError(f"unexpected token in boolean search query: {self._peek().value}")
        return expression

    def _parse_or(self) -> SearchExpression:
        left = self._parse_and()
        while self._match("OR"):
            right = self._parse_and()
            left = SearchBinary("OR", left, right)
        return left

    def _parse_and(self) -> SearchExpression:
        left = self._parse_not()
        while True:
            if self._match("AND"):
                right = self._parse_not()
                left = SearchBinary("AND", left, right)
                continue
            token = self._peek()
            if token is not None and token.kind in {"TERM", "NOT", "("}:
                right = self._parse_not()
                left = SearchBinary("AND", left, right)
                continue
            return left

    def _parse_not(self) -> SearchExpression:
        if self._match("NOT"):
            return SearchNot(self._parse_not())
        return self._parse_primary()

    def _parse_primary(self) -> SearchExpression:
        token = self._peek()
        if token is None:
            raise ValueError("unexpected end of boolean search query")
        if token.kind == "TERM":
            self.index += 1
            return SearchTerm(token.value)
        if self._match("("):
            expression = self._parse_or()
            if not self._match(")"):
                raise ValueError("missing closing parenthesis in boolean search query")
            return expression
        raise ValueError(f"unexpected token in boolean search query: {token.value}")

    def _peek(self) -> _SearchToken | None:
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index]

    def _match(self, kind: str) -> bool:
        token = self._peek()
        if token is None or token.kind != kind:
            return False
        self.index += 1
        return True


def _search_expression_line_sql(expression: SearchExpression) -> tuple[str, list[Any]]:
    if isinstance(expression, SearchTerm):
        return "line.text LIKE ? ESCAPE '\\'", [f"%{_escape_like(expression.value)}%"]
    if isinstance(expression, SearchNot):
        sql, params = _search_expression_line_sql(expression.expression)
        return f"NOT ({sql})", params
    left_sql, left_params = _search_expression_line_sql(expression.left)
    right_sql, right_params = _search_expression_line_sql(expression.right)
    return f"({left_sql}) {expression.operator} ({right_sql})", [*left_params, *right_params]


def _search_expression_page_sql(expression: SearchExpression) -> tuple[str, list[Any]]:
    if isinstance(expression, SearchTerm):
        return (
            "EXISTS (SELECT 1 FROM lines term_line WHERE term_line.project = page.project "
            "AND term_line.page_id = page.id AND term_line.text LIKE ? ESCAPE '\\')",
            [f"%{_escape_like(expression.value)}%"],
        )
    if isinstance(expression, SearchNot):
        sql, params = _search_expression_page_sql(expression.expression)
        return f"NOT ({sql})", params
    left_sql, left_params = _search_expression_page_sql(expression.left)
    right_sql, right_params = _search_expression_page_sql(expression.right)
    return f"({left_sql}) {expression.operator} ({right_sql})", [*left_params, *right_params]


def _search_positive_terms(expression: SearchExpression, *, positive: bool = True) -> list[str]:
    if isinstance(expression, SearchTerm):
        return [expression.value] if positive else []
    if isinstance(expression, SearchNot):
        return _search_positive_terms(expression.expression, positive=not positive)
    return [
        *_search_positive_terms(expression.left, positive=positive),
        *_search_positive_terms(expression.right, positive=positive),
    ]


def _normalized_unique_terms(terms: list[str]) -> list[str]:
    normalized_terms = [normalize_title(term) for term in terms if normalize_title(term)]
    return list(dict.fromkeys(normalized_terms))


def _literal_occurrence_spans(text: str, query: str) -> list[tuple[int, int]]:
    if not query:
        return []
    folded_text = text.casefold()
    folded_query = query.casefold()
    spans: list[tuple[int, int]] = []
    start = 0
    while True:
        index = folded_text.find(folded_query, start)
        if index < 0:
            return spans
        end = index + len(query)
        spans.append((index, end))
        start = end


def _span_is_inside_any(span: tuple[int, int], containers: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(container_start <= start and end <= container_end for container_start, container_end in containers)


def _line_internal_link_spans(text: str, edge_norms: set[str]) -> list[tuple[int, int]]:
    if not edge_norms:
        return []

    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "#":
            tag = parse_cosense_hash_tag(text, index)
            if tag is not None:
                target, end = tag
                if normalize_title(target) in edge_norms:
                    spans.append((index, end))
                index = end
                continue
            index += 1
            continue

        if char != "[":
            index += 1
            continue

        start = index
        if start + 1 < len(text) and text[start + 1] == "[":
            close = text.find("]]", start + 2)
            if close == -1:
                break
            if not _is_inside_inline_code(text, start):
                target = markdown_wikilink_target(text[start + 2 : close])
                if target and normalize_title(target) in edge_norms:
                    spans.append((start, close + 2))
            index = close + 2
            continue

        close = text.find("]", start + 1)
        if close == -1:
            break
        if not _is_inside_inline_code(text, start) and not is_ascii_index_syntax(text, start):
            content = text[start + 1 : close].strip()
            if is_internal_cosense_link(content) and normalize_title(content) in edge_norms:
                spans.append((start, close + 1))
        index = close + 1

    return spans


def _is_inside_inline_code(text: str, position: int) -> bool:
    return text[:position].count("`") % 2 == 1


def _gather_default_limit(budget: int) -> int:
    if budget <= 1500:
        return 5
    if budget <= 4000:
        return 10
    if budget <= 8000:
        return 20
    return 30


def _score_come_from_candidate(
    query: str,
    *,
    bare_occurrences: int,
    bare_pages: int,
    page_status_counts: dict[str, dict[str, int]],
) -> dict[str, Any]:
    normalized = normalize_title(query)
    compact = "".join(normalized.split())
    compact_length = len(compact)
    has_non_ascii = any(ord(char) > 127 for char in query)
    has_ascii_alnum = any(char.isascii() and char.isalnum() for char in query)
    has_ascii_upper = any("A" <= char <= "Z" for char in query)
    has_digit = any(char.isdigit() for char in query)
    has_mixed_script = has_non_ascii and has_ascii_alnum

    frequency_score = min(35, bare_occurrences)
    spread_score = min(25, bare_pages * 3)
    unlinked_pages = page_status_counts.get("unlinked-page", {}).get("pages", 0)
    unlinked_bare_occurrences = page_status_counts.get("unlinked-page", {}).get("bare_occurrences", 0)
    unlinked_score = min(20, unlinked_pages * 5)
    if has_mixed_script:
        uncommon_score = 25
    elif has_non_ascii and compact_length >= 3:
        uncommon_score = 20
    elif has_ascii_upper and compact_length >= 2:
        uncommon_score = 15
    elif has_digit and compact_length >= 2:
        uncommon_score = 12
    elif compact_length >= 8:
        uncommon_score = 10
    elif has_non_ascii and compact_length >= 2:
        uncommon_score = 8
    else:
        uncommon_score = 0

    score = frequency_score + spread_score + unlinked_score + uncommon_score
    thresholds = {
        "score": 30,
        "bare_occurrences": 3,
        "bare_pages": 2,
        "uncommon_score": 10,
    }
    is_candidate = (
        score >= thresholds["score"]
        and bare_occurrences >= thresholds["bare_occurrences"]
        and bare_pages >= thresholds["bare_pages"]
        and uncommon_score >= thresholds["uncommon_score"]
    )

    rationale: list[str] = []
    if bare_occurrences >= thresholds["bare_occurrences"] and bare_pages >= thresholds["bare_pages"]:
        rationale.append("bare mentions recur across multiple pages")
    else:
        rationale.append("bare mention volume is still low")
    if uncommon_score >= thresholds["uncommon_score"]:
        rationale.append("query shape looks uncommon enough for come-from review")
    else:
        rationale.append("query shape looks too common without more evidence")
    if unlinked_pages:
        rationale.append("some bare mentions occur on pages without a query-containing link handle")
    rationale.append("heuristic only; review ambiguity before declaring come-from")

    return {
        "score": score,
        "is_candidate": is_candidate,
        "thresholds": thresholds,
        "signals": {
            "bare_occurrences": bare_occurrences,
            "bare_pages": bare_pages,
            "unlinked_pages": unlinked_pages,
            "unlinked_bare_occurrences": unlinked_bare_occurrences,
            "exact_link_pages": page_status_counts.get("exact-link-page", {}).get("pages", 0),
            "query_link_pages": page_status_counts.get("query-link-page", {}).get("pages", 0),
            "query_length": compact_length,
            "has_non_ascii": has_non_ascii,
            "has_ascii_upper": has_ascii_upper,
            "has_digit": has_digit,
            "has_mixed_script": has_mixed_script,
            "frequency_score": frequency_score,
            "spread_score": spread_score,
            "unlinked_score": unlinked_score,
            "uncommon_score": uncommon_score,
        },
        "rationale": rationale,
    }


def _source_project_names(project: str) -> set[str]:
    names = {normalize_title(project)}
    base, separator, _rest = project.partition(":")
    if separator and base:
        names.add(normalize_title(base))
    return {name for name in names if name}


def _cross_project_ref_from_row(
    row: sqlite3.Row,
    link: CrossProjectLink,
    *,
    target_class: str,
) -> dict[str, Any]:
    return {
        "target_project": link.project,
        "target_title": link.title,
        "target_raw": link.raw,
        "target_class": target_class,
        "source_page_id": row["source_page_id"],
        "source_title": row["source_title"],
        "source_views": row["source_views"],
        "source_updated": row["source_updated"],
        "line_id": row["line_id"],
        "line_index": row["line_index"],
        "line_text": row["line_text"],
    }


def _cross_project_project_entry(
    target_project: str,
    refs: list[dict[str, Any]],
    *,
    sample_limit: int,
    seed_limit: int,
) -> dict[str, Any]:
    target_counts: Counter[tuple[str, str]] = Counter(
        (ref["target_title"], ref["target_class"])
        for ref in refs
    )
    source_page_ids = {ref["source_page_id"] for ref in refs}
    source_views_by_page = {
        ref["source_page_id"]: int(ref["source_views"] or 0)
        for ref in refs
    }
    class_counts = Counter(ref["target_class"] for ref in refs)
    top_targets = [
        {
            "title": title,
            "target_class": target_class,
            "mention_count": mention_count,
        }
        for (title, target_class), mention_count in target_counts.most_common(10)
    ]
    seed_candidates = _cross_project_seed_candidates(refs)
    returned_seed_candidates = seed_candidates[:seed_limit]
    return {
        "project": target_project,
        "mention_count": len(refs),
        "unique_target_count": len(target_counts),
        "source_page_count": len(source_page_ids),
        "total_source_views": sum(source_views_by_page.values()),
        "target_class_counts": _count_map(class_counts),
        "top_targets": top_targets,
        "seed_title_count": len(seed_candidates),
        "seed_title_limit": seed_limit,
        "omitted_seed_title_count": max(0, len(seed_candidates) - len(returned_seed_candidates)),
        "seed_titles": [item["title"] for item in returned_seed_candidates],
        "seed_candidates": returned_seed_candidates,
        "examples": refs[:sample_limit],
    }


def _cross_project_seed_candidates(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs_by_title: dict[str, list[dict[str, Any]]] = {}
    for ref in refs:
        if ref["target_class"] != "semantic" or not ref["target_title"]:
            continue
        refs_by_title.setdefault(ref["target_title"], []).append(ref)

    candidates: list[dict[str, Any]] = []
    for title, title_refs in refs_by_title.items():
        source_page_ids = {ref["source_page_id"] for ref in title_refs}
        source_views_by_page = {
            ref["source_page_id"]: int(ref["source_views"] or 0)
            for ref in title_refs
        }
        candidates.append(
            {
                "title": title,
                "mention_count": len(title_refs),
                "source_page_count": len(source_page_ids),
                "total_source_views": sum(source_views_by_page.values()),
                "examples": title_refs[:2],
            }
        )
    candidates.sort(
        key=lambda item: (
            -item["mention_count"],
            -item["source_page_count"],
            -item["total_source_views"],
            item["title"].casefold(),
        )
    )
    return candidates


def _count_map(counter: Counter[str]) -> dict[str, int]:
    return {
        key: counter.get(key, 0)
        for key in ("semantic", "icon", "project-root", "self-project")
    }


def _co_link_target_relation(target_relation_rank: int) -> str:
    if target_relation_rank == 2:
        return "self"
    if target_relation_rank == 1:
        return "query-containing-title"
    return "slice-handle"


def _nonempty_recovery_hints(recovery_hints: dict[str, Any]) -> dict[str, Any] | None:
    compact = {key: value for key, value in recovery_hints.items() if value}
    return compact or None


def _write_metadata(connection: sqlite3.Connection, values: dict[str, str]) -> None:
    connection.executemany(
        """
        INSERT INTO metadata (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        values.items(),
    )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _search_terms(query: str) -> list[str]:
    normalized = normalize_title(query)
    return [term for term in normalized.split(" ") if term]


def _loose_search_terms(query: str) -> list[str]:
    terms = [term for term in loose_search_key(query).split(" ") if term]
    return list(dict.fromkeys(terms))


def _title_suggestion_match(query_norm: str, title_norm: str) -> dict[str, Any] | None:
    if not query_norm:
        return None
    if query_norm == title_norm:
        return {
            "match_mode": "exact",
            "match_score": 100_000 + len(query_norm),
            "matched_terms": [query_norm],
        }
    if title_norm.startswith(query_norm):
        return {
            "match_mode": "prefix",
            "match_score": 90_000 + len(query_norm) * 10,
            "matched_terms": [query_norm],
        }
    if query_norm in title_norm:
        return {
            "match_mode": "substring",
            "match_score": 80_000 + len(query_norm) * 10 - title_norm.find(query_norm),
            "matched_terms": [query_norm],
        }

    terms = _search_terms(query_norm)
    if len(terms) > 1:
        term_matches = []
        for term in terms:
            match = _title_term_match(term, title_norm)
            if match is None:
                return None
            term_matches.append(match)
        score = 70_000 + sum(int(match["score"]) for match in term_matches)
        return {
            "match_mode": "terms",
            "match_score": score,
            "matched_terms": terms,
        }

    match = _title_term_match(query_norm, title_norm)
    if match is None or match["mode"] == "substring":
        return None
    return {
        "match_mode": match["mode"],
        "match_score": 60_000 + int(match["score"]),
        "matched_terms": [query_norm],
    }


def _title_term_match(term: str, title_norm: str) -> dict[str, Any] | None:
    if not term:
        return None
    if term in title_norm:
        return {
            "mode": "substring",
            "score": 2_000 + len(term) * 20 - title_norm.find(term),
        }
    score = _fuzzy_subsequence_score(term, title_norm)
    if score is None:
        return None
    return {
        "mode": "subsequence",
        "score": score,
    }


def _fuzzy_subsequence_score(pattern: str, text: str) -> int | None:
    if len(pattern) < 2 or len(text) < len(pattern):
        return None
    positions = []
    start = 0
    for char in pattern:
        found = text.find(char, start)
        if found < 0:
            return None
        positions.append(found)
        start = found + 1
    span = positions[-1] - positions[0] + 1
    gaps = span - len(pattern)
    if gaps > max(8, len(pattern) * 3):
        return None
    leading_gap = positions[0]
    return max(1, 1_500 + len(pattern) * 20 - gaps * 30 - leading_gap)


def _sql_loose_search_terms(query: str) -> list[str]:
    terms = [term for term in sql_loose_search_key(query).split(" ") if term]
    return list(dict.fromkeys(terms))


def _matched_search_terms(line_text: str, terms: list[str]) -> list[str]:
    normalized_line = normalize_title(line_text)
    return [term for term in terms if term in normalized_line]


def _matched_sql_loose_search_terms(line_text: str, terms: list[str]) -> list[str]:
    normalized_line = sql_loose_search_key(line_text)
    return [term for term in terms if term in normalized_line]


def _matched_loose_search_terms(line_text: str, terms: list[str]) -> list[str]:
    normalized_line = loose_search_key(line_text)
    return [term for term in terms if term in normalized_line]


def sql_loose_search_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalize_title(normalized)
    return normalized.replace("\u30fc", "")


def loose_search_key(value: str) -> str:
    normalized = sql_loose_search_key(value)
    normalized = "".join(_katakana_to_hiragana(char) for char in normalized)
    return normalized


def _katakana_to_hiragana(char: str) -> str:
    codepoint = ord(char)
    if 0x30A1 <= codepoint <= 0x30F6:
        return chr(codepoint - 0x60)
    return char


def _needs_python_loose_fallback(query: str, terms: list[str], loose_terms: list[str]) -> bool:
    return bool(loose_terms) and (loose_terms != terms or _contains_kana(query))


def _contains_kana(value: str) -> bool:
    for char in value:
        codepoint = ord(char)
        if 0x3040 <= codepoint <= 0x30FF or 0xFF66 <= codepoint <= 0xFF9F:
            return True
    return False


def loose_recovery_key(value: str) -> str:
    return value.replace("\u30fc", "")


def _int_or_none(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def format_export_ai_text(
    *,
    query: str,
    page_exists: bool,
    entries: list[dict[str, Any]],
    direct_count: int,
    indirect_count: int,
    depth: int,
    project_url: str,
) -> str:
    url = cosense_page_url(project_url, query)
    total_line = export_ai_total_line(
        page_count=len(entries),
        page_exists=page_exists,
        direct_count=direct_count,
        indirect_count=indirect_count,
        depth=depth,
    )
    parts = [
        f"This text contains the content of {url} (a page on Cosense, formerly known as Scrapbox) and its related pages in one file.\n",
        f"{total_line}\n",
        "\n",
        "IMPORTANT: Bracketed [page title] are internal links. Most linked pages exist within this document - use them to navigate between related concepts.\n",
        "\n",
        "== GUIDE FOR AI AGENTS ==\n",
    ]
    if page_exists:
        parts.append(f"1. START with the first page (main topic: \"{query}\") - marked as type=\"mainpage\"\n")
    else:
        parts.append(
            f"1. START with the first listed page - it links to the requested topic \"{query}\", whose page is not present in the local store\n"
        )
    parts.extend(
        [
            "2. READ the <PageList> in order - pages are sorted by relevance and importance\n",
            "3. USE internal links [page title] to understand connections between concepts\n",
            "4. NAVIGATE by searching for \"<Page title=\" to jump to specific pages\n",
            "5. REFERENCE created/updated timestamps when handling conflicting information\n",
            "6. UNDERSTAND page relationships using type attribute:\n",
            "   - type=\"mainpage\": The primary page you requested\n",
            "   - type=\"1hopLink\": Pages directly linked from the main page (most relevant)\n",
            "   - type=\"2hopLink\": Pages linked from 1-hop pages (contextually relevant)\n",
        ]
    )
    if not page_exists:
        parts.append("\nNOTE: The requested page is not present in the local store; this export starts with pages that link to the requested title.\n")

    parts.append("\n<PageList>\n")
    for entry in entries:
        page: Page = entry["page"]
        page_type = entry["type"]
        parts.append(
            f'<Page title="{escape_html(page.title, quote=True)}" '
            f'url="{escape_html(cosense_page_url(project_url, page.title), quote=True)}" '
            f'updated="{escape_html(format_export_ai_time(page.updated), quote=True)}" '
            f'created="{escape_html(format_export_ai_time(page.created), quote=True)}" '
            f'type="{escape_html(page_type, quote=True)}">\n'
        )
        lines: list[Line] = entry["lines"]
        for line in lines:
            parts.append(f"{line.text}\n")
        parts.append("</Page>\n\n\n\n")
    parts.append("</PageList>\n")
    return "".join(parts)


def export_ai_total_line(
    *,
    page_count: int,
    page_exists: bool,
    direct_count: int,
    indirect_count: int,
    depth: int,
) -> str:
    if not page_exists:
        if depth >= 2 and indirect_count:
            return (
                f"Total pages included: {page_count} "
                f"({direct_count} directly linked + {indirect_count} indirectly linked pages; main page not present in local store)."
            )
        return (
            f"Total pages included: {page_count} "
            f"({direct_count} directly linked pages; main page not present in local store)."
        )
    if depth >= 2 and indirect_count:
        return (
            f"Total pages included: {page_count} "
            f"(main page + {direct_count} directly linked + {indirect_count} indirectly linked pages)."
        )
    return f"Total pages included: {page_count} (main page + {direct_count} directly linked pages)."


def cosense_page_url(project_url: str, title: str) -> str:
    base_url = project_url.rstrip("/") + "/"
    return base_url + quote(title, safe="")


def format_export_ai_time(value: int | None) -> str:
    if value is None:
        return ""
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _limit_reached(items: list[Any], limit: int | None) -> bool:
    return limit is not None and limit >= 0 and len(items) >= limit


def parse_cosense_time(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if not isinstance(value, str):
        return None

    iso_part = value.split(" ", 1)[0]
    try:
        return int(datetime.fromisoformat(iso_part).timestamp())
    except ValueError:
        return None


def link_multiplicity(link_count: int) -> str:
    if link_count <= 0:
        return "none"
    if link_count == 1:
        return "single"
    return "multi"


def _expanded_unresolved_fetch_limit(limit: int | None) -> int | None:
    if limit is None or limit < 0:
        return None
    if limit == 0:
        return 0
    return max(limit * 10, limit + 20)


def _annotate_unresolved_target_item(item: dict[str, Any], examples: list[Edge]) -> dict[str, Any]:
    if not examples:
        return item

    annotations = [edge_semantic_annotation(edge) for edge in examples]
    if any(annotation is None for annotation in annotations):
        return item

    annotation = dict(annotations[0] or {})
    annotation["reason"] = "all sampled unresolved edge examples are system-classified as non-semantic"
    item["semantic_annotation"] = annotation
    return item


def _unresolved_target_output_rank_key(item: dict[str, Any]) -> tuple[Any, ...]:
    annotation = item.get("semantic_annotation") or {}
    is_non_semantic = annotation.get("graph_scope") == "non-semantic"
    return (
        is_non_semantic,
        -int(item.get("link_count") or 0),
        -int(item.get("source_page_count") or 0),
        -int(item.get("total_source_views") or 0),
        -int(item.get("latest_source_updated") or 0),
        str(item.get("title") or "").casefold(),
    )


def _empty_spread_edge_stats() -> dict[str, Any]:
    return {
        "incoming_link_count": 0,
        "incoming_source_page_count": 0,
        "resolution_counts": {
            "resolved_unique": 0,
            "ambiguous": 0,
            "unresolved": 0,
        },
    }


def _spread_project_rank_key(item: dict[str, Any]) -> tuple[Any, ...]:
    incoming = item["incoming"]
    materialized = item["materialized"]
    unresolved = item.get("unresolved")
    return (
        -int(incoming["incoming_link_count"]),
        -int(incoming["incoming_source_page_count"]),
        -int(materialized["candidate_count"]),
        0 if unresolved is not None else 1,
        item["project"],
    )


def _spread_totals(items: list[dict[str, Any]]) -> dict[str, Any]:
    resolution_counts = Counter()
    incoming_link_count = 0
    incoming_source_page_count = 0
    page_candidate_count = 0
    materialized_project_count = 0
    ambiguous_project_count = 0
    unresolved_project_count = 0
    incoming_project_count = 0
    for item in items:
        materialized = item["materialized"]
        incoming = item["incoming"]
        page_candidate_count += int(materialized["candidate_count"])
        if materialized["candidate_count"]:
            materialized_project_count += 1
        if materialized["ambiguous"]:
            ambiguous_project_count += 1
        if item.get("unresolved") is not None:
            unresolved_project_count += 1
        if incoming["incoming_link_count"]:
            incoming_project_count += 1
        incoming_link_count += int(incoming["incoming_link_count"])
        incoming_source_page_count += int(incoming["incoming_source_page_count"])
        resolution_counts.update(incoming["resolution_counts"])
    return {
        "signal_project_count": len(items),
        "materialized_project_count": materialized_project_count,
        "ambiguous_project_count": ambiguous_project_count,
        "unresolved_project_count": unresolved_project_count,
        "incoming_project_count": incoming_project_count,
        "page_candidate_count": page_candidate_count,
        "incoming_link_count": incoming_link_count,
        "incoming_source_page_count": incoming_source_page_count,
        "resolution_counts": dict(resolution_counts),
    }


def _spread_summary_from_row(row: sqlite3.Row) -> dict[str, Any]:
    handle_norm = row["handle_norm"]
    rank_band = _spread_summary_rank_band(
        handle_norm,
        int(row["page_candidate_count"]),
        int(row["artifact_project_count"]),
        int(row["content_project_count"]),
        int(row["incoming_link_count"]),
        int(row["unresolved_link_count"]),
    )
    return {
        "title": row["title"],
        "handle_norm": handle_norm,
        "project_spread": int(row["project_spread"]),
        "materialized_project_count": int(row["materialized_project_count"]),
        "page_candidate_count": int(row["page_candidate_count"]),
        "ambiguous_project_count": int(row["ambiguous_project_count"]),
        "artifact_project_count": int(row["artifact_project_count"]),
        "content_project_count": int(row["content_project_count"]),
        "unresolved_project_count": int(row["unresolved_project_count"]),
        "unresolved_link_count": int(row["unresolved_link_count"]),
        "incoming_project_count": int(row["incoming_project_count"]),
        "incoming_link_count": int(row["incoming_link_count"]),
        "incoming_source_page_count": int(row["incoming_source_page_count"]),
        "resolution_counts": {
            "resolved_unique": int(row["resolved_unique"]),
            "ambiguous": int(row["ambiguous"]),
            "unresolved": int(row["unresolved"]),
        },
        "rank_band": rank_band,
        "rank_reason": _spread_summary_rank_reason(rank_band),
        "connection_strength": "weak-normalized-title",
    }


def _spread_summary_rank_band(
    handle_norm: str,
    page_candidate_count: int,
    artifact_project_count: int,
    content_project_count: int,
    incoming_link_count: int,
    unresolved_link_count: int,
) -> str:
    if handle_norm in STRUCTURAL_SPREAD_HANDLE_NORMS:
        return "structural-name"
    if page_candidate_count > 0 and content_project_count == 0:
        return "artifact-only"
    if handle_norm.isdecimal():
        return "numeric-only"
    return "concept-like"


def _spread_summary_rank_reason(rank_band: str) -> str:
    if rank_band == "structural-name":
        return "common wiki structural handle, ranked below concept-like handles"
    if rank_band == "artifact-only":
        return "materialized only as navigation/log/artifact handles, with no incoming or unresolved signal"
    if rank_band == "numeric-only":
        return "numeric-only handles are often issue/list markers, so they rank below concept-like handles"
    return "concept-like handle"


def _cross_project_spread_summary_rank_key(item: dict[str, Any]) -> tuple[Any, ...]:
    band_order = {"concept-like": 0, "structural-name": 1, "numeric-only": 2, "artifact-only": 3}
    return (
        band_order.get(item["rank_band"], 9),
        -int(item["project_spread"]),
        -int(item["incoming_link_count"]),
        -int(item["unresolved_link_count"]),
        -int(item["materialized_project_count"]),
        str(item["title"]).casefold(),
    )


def rebuild_unresolved_targets(connection: sqlite3.Connection, project: str) -> None:
    connection.execute("DELETE FROM unresolved_targets WHERE project = ?", (project,))
    connection.execute("DELETE FROM unresolved_target_examples WHERE project = ?", (project,))
    connection.execute(
        """
        INSERT INTO unresolved_targets (
          project,
          target_norm,
          title,
          link_count,
          source_page_count,
          total_source_views,
          latest_source_updated
        )
        WITH unresolved_edges AS (
          SELECT e.target_norm, e.target_title, e.source_page_id, source.views, source.updated
          FROM edges e
          JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
          WHERE e.project = ? AND e.resolution_status = 'unresolved'
        ),
        edge_stats AS (
          SELECT
            target_norm,
            COUNT(*) AS link_count,
            COUNT(DISTINCT source_page_id) AS source_page_count,
            MAX(COALESCE(updated, 0)) AS latest_source_updated
          FROM unresolved_edges
          GROUP BY target_norm
        ),
        source_stats AS (
          SELECT target_norm, SUM(views) AS total_source_views
          FROM (
            SELECT DISTINCT target_norm, source_page_id, views
            FROM unresolved_edges
          )
          GROUP BY target_norm
        ),
        title_choice AS (
          SELECT target_norm, target_title
          FROM (
            SELECT
              target_norm,
              target_title,
              ROW_NUMBER() OVER (
                PARTITION BY target_norm
                ORDER BY COUNT(*) DESC, target_title
              ) AS rn
            FROM unresolved_edges
            GROUP BY target_norm, target_title
          )
          WHERE rn = 1
        )
        SELECT
          ? AS project,
          edge_stats.target_norm,
          title_choice.target_title,
          edge_stats.link_count,
          edge_stats.source_page_count,
          COALESCE(source_stats.total_source_views, 0) AS total_source_views,
          edge_stats.latest_source_updated
        FROM edge_stats
        JOIN source_stats ON source_stats.target_norm = edge_stats.target_norm
        JOIN title_choice ON title_choice.target_norm = edge_stats.target_norm
        """,
        (project, project),
    )
    rebuild_unresolved_target_examples(connection, project)


def rebuild_unresolved_target_examples(connection: sqlite3.Connection, project: str) -> None:
    connection.execute(
        """
        INSERT INTO unresolved_target_examples (
          project,
          target_norm,
          rank,
          source_page_id,
          line_id,
          target_title
        )
        WITH ranked AS (
          SELECT
            e.target_norm,
            ROW_NUMBER() OVER (
              PARTITION BY e.target_norm
              ORDER BY source.views DESC, COALESCE(source.updated, 0) DESC, source.title, line.line_index
            ) AS rank,
            e.source_page_id,
            e.line_id,
            e.target_title
          FROM edges e
          JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
          JOIN lines line ON line.project = e.project AND line.line_id = e.line_id
          WHERE e.project = ? AND e.resolution_status = 'unresolved'
        )
        SELECT ? AS project, target_norm, rank, source_page_id, line_id, target_title
        FROM ranked
        WHERE rank <= 5
        """,
        (project, project),
    )
