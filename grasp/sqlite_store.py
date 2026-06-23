from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape as escape_html
import json
from pathlib import Path
import os
import shutil
import sqlite3
import time
import unicodedata
from typing import Any
from urllib.parse import quote

from .cosense import CosenseStore, Edge, Line, Page, normalize_title, parse_cosense_links
from .markdown import MarkdownMirror, MarkdownPageRecord


SCHEMA_VERSION = "5"
IMPORT_CACHE_MANIFEST_VERSION = 1
PYTHON_LOOSE_SEARCH_MAX_LINES = 50_000


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
CREATE INDEX idx_lines_project_page_index ON lines(project, page_id, line_index);
CREATE INDEX idx_edges_project_target_norm ON edges(project, target_norm);
CREATE INDEX idx_edges_project_source_page ON edges(project, source_page_id);
CREATE INDEX idx_edges_project_line ON edges(project, line_id);
CREATE INDEX idx_unresolved_targets_project_rank ON unresolved_targets(project, link_count DESC, source_page_count DESC, total_source_views DESC, latest_source_updated DESC, title);
CREATE INDEX idx_unresolved_target_examples_project_norm_rank ON unresolved_target_examples(project, target_norm, rank);
"""


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
    connection = sqlite3.connect(store_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = NORMAL")
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
            connection.executemany(
                """
                INSERT INTO edges (project, source_page_id, line_id, target_title, target_norm)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    (
                        project,
                        edge.source_page_id,
                        edge.line_id,
                        edge.target_title,
                        edge.target_norm,
                    )
                    for edge in source.edges
                ),
            )
            rebuild_unresolved_targets(connection, project)
            unresolved_count = len(
                {
                    edge.target_norm
                    for edge in source.edges
                    if edge.target_norm not in source.pages_by_norm
                }
            )
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
) -> dict[str, Any]:
    folder_path = Path(folder_path)
    store_path = Path(store_path)
    source = MarkdownMirror.from_folder(folder_path)
    project = normalize_project_name(project_name or source.project_name or folder_path.name)
    if not project:
        raise ValueError(f"could not determine project name for Markdown folder: {folder_path}")

    ensure_store_schema(store_path)
    connection = sqlite3.connect(store_path)
    import_summary: dict[str, Any] = {}
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = NORMAL")
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
        if source_export and Path(source_export).exists():
            sources = [
                {
                    "project": metadata.get("last_imported_project"),
                    "path": source_export,
                    "source_export": source_export,
                }
            ]

    if not sources:
        return False

    for source in sources:
        source_path = Path(source["path"])
        if not source_path.exists():
            return False
    for source in sources:
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


def _cache_import_source(export_path: Path, store_path: Path, project: str) -> None:
    cache_dir = import_cache_dir(store_path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{quote(project, safe='') or '_default'}.cosense.json"
    tmp_path = cache_path.with_name(f"{cache_path.name}.tmp")

    try:
        same_file = export_path.resolve() == cache_path.resolve()
    except FileNotFoundError:
        same_file = False
    if not same_file:
        shutil.copyfile(export_path, tmp_path)
        os.replace(tmp_path, cache_path)

    manifest = _read_import_cache_manifest(store_path)
    projects = manifest.setdefault("projects", {})
    now = int(time.time())
    projects[project] = {
        "project": project,
        "path": str(cache_path),
        "source_export": str(export_path),
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
                    }
                )
        if sources:
            return sources

    cache_dir = import_cache_dir(store_path)
    return [
        {"project": None, "path": str(path), "source_export": None}
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
    connection.execute("DELETE FROM pages WHERE project = ?", (project,))
    connection.execute("DELETE FROM projects WHERE name = ?", (project,))


def _project_exists(connection: sqlite3.Connection, project: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM projects WHERE name = ?",
        (project,),
    ).fetchone()
    return row is not None


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
    _insert_markdown_pages(connection, project, source.pages, source.edges)


def _insert_markdown_pages(
    connection: sqlite3.Connection,
    project: str,
    pages: list[Page],
    edges: list[Edge],
) -> None:
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
    connection.executemany(
        """
        INSERT INTO edges (project, source_page_id, line_id, target_title, target_norm)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            (
                project,
                edge.source_page_id,
                edge.line_id,
                edge.target_title,
                edge.target_norm,
            )
            for edge in edges
        ),
    )


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
    _insert_markdown_pages(connection, project, [record.page], edges)


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
    identity: dict[str, Any] = {}
    for relative_path, item in files.items():
        if not isinstance(item, dict):
            continue
        identity[str(relative_path)] = {
            "page_id": item.get("page_id"),
            "title": item.get("title"),
            "norm_title": item.get("norm_title"),
            "aliases": item.get("aliases") or [],
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
    def __init__(self, path: str | Path, project: str | None = None):
        self.path = Path(path)
        self.project = normalize_project_name(project) if project is not None else None
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

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
        project = self._require_project()
        norm_title = self._resolve_title_norm(title, project=project)
        row = self.connection.execute(
            """
            SELECT * FROM pages
            WHERE project = ? AND norm_title = ?
            ORDER BY rowid
            LIMIT 1
            """,
            (project, norm_title),
        ).fetchone()
        return self._page_from_row(row) if row is not None else None

    def page_lines(self, page: Page, limit: int | None = None) -> tuple[list[Line], bool]:
        project = self._require_project()
        if limit is None or limit < 0:
            rows = self.connection.execute(
                """
                SELECT * FROM lines
                WHERE project = ? AND page_id = ?
                ORDER BY line_index
                """,
                (project, page.id),
            ).fetchall()
            return [self._line_from_row(row) for row in rows], False

        rows = self.connection.execute(
            """
            SELECT * FROM lines
            WHERE project = ? AND page_id = ?
            ORDER BY line_index
            LIMIT ?
            """,
            (project, page.id, limit),
        ).fetchall()
        return [self._line_from_row(row) for row in rows], page.line_count > limit

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
        return [self._line_from_row(row) for row in rows], {
            "around_line_id": f"{page.id}:{center_index}",
            "center_index": center_index,
            "start_index": start_index,
            "end_index": end_index,
            "context": context,
            "truncated_before": start_index > 0,
            "truncated_after": end_index < page.line_count - 1,
        }

    def backlinks(self, title: str, limit: int | None = None, offset: int = 0) -> list[Edge]:
        project = self._require_project()
        norm_title = self._resolve_title_norm(title, project=project)
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
              e.target_norm
            FROM edges e
            JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
            JOIN lines line ON line.project = e.project AND line.line_id = e.line_id
            WHERE e.project = ? AND e.target_norm = ?
            ORDER BY source.views DESC, COALESCE(source.updated, 0) DESC, source.title, line.line_index
        """
        params: list[Any] = [project, norm_title]
        if limit is not None and limit >= 0:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        elif offset:
            query += " LIMIT -1 OFFSET ?"
            params.append(offset)
        return [self._edge_from_row(row) for row in self.connection.execute(query, params)]

    def link_stats(self, title: str) -> dict[str, Any]:
        project = self._require_project()
        page = self.resolve_page(title)
        norm = page.norm_title if page is not None else self._resolve_title_norm(title, project=project)
        if page is None:
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
                WHERE project = ? AND target_norm = ?
                """,
                (project, norm),
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
            "link_count": link_count,
            "source_page_count": source_page_count,
            "link_multiplicity": link_multiplicity(link_count),
            "recovery_hints": None,
        }
        if page is None and link_count == 0:
            result["recovery_hints"] = self.recovery_hints(title, limit=3)
        return result

    def unresolved_targets(self, limit: int | None = None) -> list[dict[str, Any]]:
        project = self._require_project()
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
                (project, limit),
            ).fetchall()
        return self._unresolved_target_materialized_rows_to_dicts(rows)

    def _unresolved_targets_dynamic(self, limit: int | None = None) -> list[dict[str, Any]]:
        project = self._require_project()
        params: list[Any] = [project]
        if limit is not None and limit >= 0:
            params.append(limit)
        rows = self.connection.execute(
            self._unresolved_target_stats_sql(limit),
            params,
        ).fetchall()
        return [self._unresolved_target_row_to_dict(row) for row in rows]

    def unresolved_targets_from_page(self, page: Page, limit: int | None = None) -> list[dict[str, Any]]:
        project = self._require_project()
        params: list[Any] = [project, page.id]
        if limit is not None and limit >= 0:
            params.append(limit)
        rows = self.connection.execute(
            self._unresolved_target_stats_sql(limit, source_page_id=page.id),
            params,
        ).fetchall()
        return [self._unresolved_target_row_to_dict(row, source_page_id=page.id) for row in rows]

    def related(self, title: str, limit: int | None = None) -> list[dict[str, Any]]:
        page = self.resolve_page(title)
        if page is None:
            return self._related_missing_target(title, limit)

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
            WHERE e.project = ? AND e.target_norm = ?
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
              e.target_norm
            FROM edges e
            JOIN pages source ON source.project = e.project AND source.id = e.source_page_id
            JOIN lines line ON line.project = e.project AND line.line_id = e.line_id
            WHERE e.project = ?
            ORDER BY source.views DESC, COALESCE(source.updated, 0) DESC, source.title, line.line_index
            """,
            (project,),
        ).fetchall()
        for row in edge_rows:
            source_key = self._page_node_key(row["source_page_id"])
            target_page_id = page_id_by_norm.get(row["target_norm"])
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
            edge_examples.setdefault(
                example_key,
                {
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
                },
            )
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

    def suggest(self, partial: str, limit: int = 20) -> list[dict[str, Any]]:
        project = self._require_project()
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
        return [self._page_from_row(row).to_summary() for row in rows]

    def search(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
        *,
        mode: str = "literal",
        scope: str = "line",
    ) -> list[dict[str, Any]]:
        project = self._require_project()
        if mode not in {"literal", "boolean"}:
            raise ValueError(f"unsupported search mode: {mode}")
        if scope not in {"line", "page"}:
            raise ValueError(f"unsupported search scope: {scope}")

        if mode == "boolean":
            expression = parse_search_boolean_query(query)
            return self._search_boolean(expression, limit=limit, offset=offset, scope=scope)

        hits = self._search_literal(query, limit=limit, offset=offset, scope=scope)
        if hits:
            return hits

        sql_loose_query = sql_loose_search_key(query)
        hits = self._search_sql_loose_literal(sql_loose_query, limit=limit, offset=offset, scope=scope)
        if hits:
            return hits

        loose_query = loose_search_key(query)
        terms = _search_terms(query)
        loose_terms = _loose_search_terms(query)
        if self._can_use_python_loose_search(project) and _needs_python_loose_fallback(query, terms, loose_terms):
            return self._search_loose_literal(loose_query, limit=limit, offset=offset, scope=scope)
        return hits

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
        title: str,
        *,
        line_limit: int | None = None,
        backlink_limit: int = 20,
        related_limit: int = 20,
        unresolved_limit: int = 20,
        related_snippets: bool = False,
        related_snippet_lines: int = 5,
    ) -> dict[str, Any]:
        page = self.resolve_page(title)
        backlinks = self.backlinks(title, backlink_limit)
        link_stats = self.link_stats(title)
        related = self.related(title if page is None else page.title, related_limit)
        if related_snippets:
            related = self._with_page_snippets(related, related_snippet_lines)

        if page is None:
            recovery_hints = link_stats.get("recovery_hints")
            return {
                "query": title,
                "page": None,
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
            "query": title,
            "page": page.to_summary(),
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
            related = self._with_page_snippets(related, related_snippet_lines)

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
    ) -> list[dict[str, Any]]:
        limit = max(0, line_limit)
        items: list[dict[str, Any]] = []
        for item in related:
            item_with_snippet = dict(item)
            page = self._page_by_id(item["id"])
            if page is None:
                item_with_snippet["snippet_lines"] = []
                item_with_snippet["snippet_truncated"] = False
            else:
                lines, truncated = self.page_lines(page, limit)
                item_with_snippet["snippet_lines"] = [line.to_dict() for line in lines]
                item_with_snippet["snippet_truncated"] = truncated
            items.append(item_with_snippet)
        return items

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
            JOIN pages target ON target.project = e.project AND target.norm_title = e.target_norm
            WHERE e.project = ? AND e.source_page_id = ? AND target.id != ?
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
            WHERE e.project = ? AND e.target_norm = ?
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
              LEFT JOIN pages target ON target.project = e.project AND target.norm_title = e.target_norm
              WHERE e.project = ? AND target.id IS NULL
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
        return {
            "title": row["target_title"],
            "normalized_title": norm,
            "link_count": row["link_count"],
            "source_page_count": row["source_page_count"],
            "total_source_views": row["total_source_views"],
            "latest_source_updated": row["latest_source_updated"],
            "examples": [edge.to_dict() for edge in examples],
        }

    def _unresolved_target_materialized_rows_to_dicts(self, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        target_norms = [row["target_norm"] for row in rows]
        examples_by_norm = self._unresolved_target_materialized_examples(target_norms)
        return [
            {
                "title": row["title"],
                "normalized_title": row["target_norm"],
                "link_count": row["link_count"],
                "source_page_count": row["source_page_count"],
                "total_source_views": row["total_source_views"],
                "latest_source_updated": row["latest_source_updated"],
                "examples": [edge.to_dict() for edge in examples_by_norm.get(row["target_norm"], [])],
            }
            for row in rows
        ]

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
              e.target_norm
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
            JOIN pages target ON target.project = e.project AND target.norm_title = e.target_norm
            WHERE e.project = ? AND e.source_page_id = ? AND target.id != ?
            UNION
            SELECT e.source_page_id AS page_id
            FROM edges e
            WHERE e.project = ? AND e.target_norm = ? AND e.source_page_id != ?
            """,
            (project, page_id, page_id, project, norm_title, page_id),
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
        self.connection.executemany(
            """
            INSERT INTO edges (project, source_page_id, line_id, target_title, target_norm)
            VALUES (?, ?, ?, ?, ?)
            """,
            edge_rows,
        )

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
          LEFT JOIN pages target ON target.project = e.project AND target.norm_title = e.target_norm
          WHERE e.project = ? AND target.id IS NULL
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
          LEFT JOIN pages target ON target.project = e.project AND target.norm_title = e.target_norm
          WHERE e.project = ? AND target.id IS NULL
        )
        SELECT ? AS project, target_norm, rank, source_page_id, line_id, target_title
        FROM ranked
        WHERE rank <= 5
        """,
        (project, project),
    )
