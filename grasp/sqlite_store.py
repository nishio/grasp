from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
import os
import sqlite3
import time
from typing import Any

from .cosense import CosenseStore, Edge, Line, Page, normalize_title, parse_cosense_links


SCHEMA_VERSION = "2"


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE pages (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  norm_title TEXT NOT NULL,
  created INTEGER,
  updated INTEGER,
  views INTEGER NOT NULL DEFAULT 0,
  line_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE lines (
  line_id TEXT PRIMARY KEY,
  page_id TEXT NOT NULL,
  line_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  created INTEGER,
  updated INTEGER,
  user_id TEXT,
  FOREIGN KEY(page_id) REFERENCES pages(id) ON DELETE CASCADE
);

CREATE TABLE edges (
  id INTEGER PRIMARY KEY,
  source_page_id TEXT NOT NULL,
  line_id TEXT NOT NULL,
  target_title TEXT NOT NULL,
  target_norm TEXT NOT NULL,
  FOREIGN KEY(source_page_id) REFERENCES pages(id) ON DELETE CASCADE,
  FOREIGN KEY(line_id) REFERENCES lines(line_id) ON DELETE CASCADE
);

CREATE TABLE wanted (
  target_norm TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  count INTEGER NOT NULL,
  source_page_count INTEGER NOT NULL,
  total_source_views INTEGER NOT NULL,
  latest_source_updated INTEGER NOT NULL
);

CREATE TABLE wanted_examples (
  target_norm TEXT NOT NULL,
  rank INTEGER NOT NULL,
  source_page_id TEXT NOT NULL,
  line_id TEXT NOT NULL,
  target_title TEXT NOT NULL,
  PRIMARY KEY(target_norm, rank)
);

CREATE INDEX idx_pages_norm_title ON pages(norm_title);
CREATE INDEX idx_pages_title ON pages(title);
CREATE INDEX idx_lines_page_index ON lines(page_id, line_index);
CREATE INDEX idx_edges_target_norm ON edges(target_norm);
CREATE INDEX idx_edges_source_page ON edges(source_page_id);
CREATE INDEX idx_edges_line ON edges(line_id);
CREATE INDEX idx_wanted_rank ON wanted(count DESC, source_page_count DESC, total_source_views DESC, latest_source_updated DESC, title);
CREATE INDEX idx_wanted_examples_norm_rank ON wanted_examples(target_norm, rank);
"""


def import_export_to_sqlite(export_path: str | Path, store_path: str | Path) -> dict[str, Any]:
    export_path = Path(export_path)
    store_path = Path(store_path)
    store_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = store_path.with_name(f"{store_path.name}.tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    source = CosenseStore.from_cosense_export(export_path)
    connection = sqlite3.connect(tmp_path)
    try:
        connection.executescript(SCHEMA)
        connection.execute("PRAGMA synchronous = NORMAL")
        with connection:
            connection.executemany(
                """
                INSERT INTO pages (id, title, norm_title, created, updated, views, line_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
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
                INSERT INTO lines (line_id, page_id, line_index, text, created, updated, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
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
                INSERT INTO edges (source_page_id, line_id, target_title, target_norm)
                VALUES (?, ?, ?, ?)
                """,
                (
                    (
                        edge.source_page_id,
                        edge.line_id,
                        edge.target_title,
                        edge.target_norm,
                    )
                    for edge in source.edges
                ),
            )
            rebuild_wanted(connection)
            _write_metadata(
                connection,
                {
                    "schema_version": SCHEMA_VERSION,
                    "source_export": str(export_path),
                    "imported_at": str(int(time.time())),
                    "pages": str(len(source.pages)),
                    "lines": str(sum(page.line_count for page in source.pages)),
                    "edges": str(len(source.edges)),
                    "wanted": str(
                        len(
                            {
                                edge.target_norm
                                for edge in source.edges
                                if edge.target_norm not in source.pages_by_norm
                            }
                        )
                    ),
                },
            )
    finally:
        connection.close()

    os.replace(tmp_path, store_path)
    return SQLiteStore(store_path).stats()


class SQLiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self.connection.close()

    def stats(self) -> dict[str, Any]:
        metadata = self.metadata()
        schema_version = metadata.get("schema_version")
        return {
            "store": str(self.path),
            "schema_version": schema_version,
            "current_schema_version": SCHEMA_VERSION,
            "schema_ok": schema_version == SCHEMA_VERSION,
            "source_export": metadata.get("source_export"),
            "imported_at": _int_or_none(metadata.get("imported_at")),
            "pages": self._count("pages"),
            "lines": self._count("lines"),
            "edges": self._count("edges"),
            "wanted": self._count("wanted"),
        }

    def metadata(self) -> dict[str, str]:
        return {
            row["key"]: row["value"]
            for row in self.connection.execute("SELECT key, value FROM metadata")
        }

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

    def page_updated(self, page_id: str) -> int | None:
        row = self.connection.execute("SELECT updated FROM pages WHERE id = ?", (page_id,)).fetchone()
        if row is None:
            return None
        return row["updated"]

    def upsert_cosense_pages(self, pages: list[dict[str, Any]]) -> None:
        if not pages:
            return
        with self.connection:
            for page in pages:
                self._upsert_cosense_page(page)
            rebuild_wanted(self.connection)

    def resolve_page(self, title: str) -> Page | None:
        row = self.connection.execute(
            """
            SELECT * FROM pages
            WHERE norm_title = ?
            ORDER BY rowid
            LIMIT 1
            """,
            (normalize_title(title),),
        ).fetchone()
        return self._page_from_row(row) if row is not None else None

    def page_lines(self, page: Page, limit: int | None = None) -> tuple[list[Line], bool]:
        if limit is None or limit < 0:
            rows = self.connection.execute(
                """
                SELECT * FROM lines
                WHERE page_id = ?
                ORDER BY line_index
                """,
                (page.id,),
            ).fetchall()
            return [self._line_from_row(row) for row in rows], False

        rows = self.connection.execute(
            """
            SELECT * FROM lines
            WHERE page_id = ?
            ORDER BY line_index
            LIMIT ?
            """,
            (page.id, limit),
        ).fetchall()
        return [self._line_from_row(row) for row in rows], page.line_count > limit

    def backlinks(self, title: str, limit: int | None = None, offset: int = 0) -> list[Edge]:
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
            JOIN pages source ON source.id = e.source_page_id
            JOIN lines line ON line.line_id = e.line_id
            WHERE e.target_norm = ?
            ORDER BY source.views DESC, COALESCE(source.updated, 0) DESC, source.title, line.line_index
        """
        params: list[Any] = [normalize_title(title)]
        if limit is not None and limit >= 0:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        elif offset:
            query += " LIMIT -1 OFFSET ?"
            params.append(offset)
        return [self._edge_from_row(row) for row in self.connection.execute(query, params)]

    def wanted(self, limit: int | None = None) -> list[dict[str, Any]]:
        if limit is None or limit < 0:
            rows = self.connection.execute(
                """
                SELECT * FROM wanted
                ORDER BY count DESC, source_page_count DESC, total_source_views DESC, latest_source_updated DESC, title
                """
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT * FROM wanted
                ORDER BY count DESC, source_page_count DESC, total_source_views DESC, latest_source_updated DESC, title
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return self._wanted_materialized_rows_to_dicts(rows)

    def _wanted_dynamic(self, limit: int | None = None) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            self._wanted_stats_sql(limit),
            [] if limit is None or limit < 0 else [limit],
        ).fetchall()
        return [self._wanted_row_to_dict(row) for row in rows]

    def wanted_from_page(self, page: Page, limit: int | None = None) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            self._wanted_stats_sql(limit, source_page_id=page.id),
            [page.id] if limit is None or limit < 0 else [page.id, limit],
        ).fetchall()
        return [self._wanted_row_to_dict(row, source_page_id=page.id) for row in rows]

    def related(self, title: str, limit: int | None = None) -> list[dict[str, Any]]:
        page = self.resolve_page(title)
        if page is None:
            return []

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

    def suggest(self, partial: str, limit: int = 20) -> list[dict[str, Any]]:
        norm_partial = normalize_title(partial)
        like = f"%{_escape_like(norm_partial)}%"
        prefix = f"{_escape_like(norm_partial)}%"
        rows = self.connection.execute(
            """
            SELECT * FROM pages
            WHERE norm_title LIKE ? ESCAPE '\\'
            ORDER BY
              CASE WHEN norm_title LIKE ? ESCAPE '\\' THEN 0 ELSE 1 END,
              views DESC,
              title
            LIMIT ?
            """,
            (like, prefix, limit),
        ).fetchall()
        return [self._page_from_row(row).to_summary() for row in rows]

    def search(self, query: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        like = f"%{_escape_like(query)}%"
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
            JOIN pages page ON page.id = line.page_id
            WHERE line.text LIKE ? ESCAPE '\\'
            ORDER BY page.views DESC, COALESCE(page.updated, 0) DESC, page.title, line.line_index
            LIMIT ? OFFSET ?
            """,
            (like, limit, offset),
        ).fetchall()
        return [
            {
                "source_page_id": row["source_page_id"],
                "source_title": row["source_title"],
                "source_views": row["source_views"],
                "source_updated": row["source_updated"],
                "line_id": row["line_id"],
                "line_index": row["line_index"],
                "line_text": row["line_text"],
            }
            for row in rows
        ]

    def read(
        self,
        title: str,
        *,
        line_limit: int | None = None,
        backlink_limit: int = 20,
        related_limit: int = 20,
        wanted_limit: int = 20,
    ) -> dict[str, Any]:
        page = self.resolve_page(title)
        backlinks = self.backlinks(title, backlink_limit)

        if page is None:
            return {
                "query": title,
                "page": None,
                "lines": [],
                "lines_truncated": False,
                "backlinks": [edge.to_dict() for edge in backlinks],
                "backlink_count_returned": len(backlinks),
                "related": [],
                "wanted": [],
                "red_link": bool(backlinks),
            }

        lines, lines_truncated = self.page_lines(page, line_limit)
        return {
            "query": title,
            "page": page.to_summary(),
            "lines": [line.to_dict() for line in lines],
            "lines_truncated": lines_truncated,
            "backlinks": [edge.to_dict() for edge in backlinks],
            "backlink_count_returned": len(backlinks),
            "related": self.related(page.title, related_limit),
            "wanted": self.wanted_from_page(page, wanted_limit),
            "red_link": False,
        }

    def _wanted_stats_sql(self, limit: int | None, source_page_id: str | None = None) -> str:
        source_filter = "AND e.source_page_id = ?" if source_page_id is not None else ""
        limit_clause = "" if limit is None or limit < 0 else "LIMIT ?"
        return f"""
            WITH wanted_edges AS (
              SELECT e.target_norm, e.target_title, e.source_page_id, source.views, source.updated
              FROM edges e
              JOIN pages source ON source.id = e.source_page_id
              LEFT JOIN pages target ON target.norm_title = e.target_norm
              WHERE target.id IS NULL
              {source_filter}
            ),
            edge_stats AS (
              SELECT
                target_norm,
                COUNT(*) AS count,
                COUNT(DISTINCT source_page_id) AS source_page_count,
                MAX(COALESCE(updated, 0)) AS latest_source_updated
              FROM wanted_edges
              GROUP BY target_norm
            ),
            source_stats AS (
              SELECT target_norm, SUM(views) AS total_source_views
              FROM (
                SELECT DISTINCT target_norm, source_page_id, views
                FROM wanted_edges
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
                FROM wanted_edges
                GROUP BY target_norm, target_title
              )
              WHERE rn = 1
            )
            SELECT
              edge_stats.target_norm,
              title_choice.target_title,
              edge_stats.count,
              edge_stats.source_page_count,
              COALESCE(source_stats.total_source_views, 0) AS total_source_views,
              edge_stats.latest_source_updated
            FROM edge_stats
            JOIN source_stats ON source_stats.target_norm = edge_stats.target_norm
            JOIN title_choice ON title_choice.target_norm = edge_stats.target_norm
            ORDER BY
              edge_stats.count DESC,
              edge_stats.source_page_count DESC,
              total_source_views DESC,
              edge_stats.latest_source_updated DESC,
              title_choice.target_title
            {limit_clause}
        """

    def _wanted_row_to_dict(self, row: sqlite3.Row, source_page_id: str | None = None) -> dict[str, Any]:
        norm = row["target_norm"]
        examples = self._wanted_examples(norm, source_page_id=source_page_id)
        return {
            "title": row["target_title"],
            "normalized_title": norm,
            "count": row["count"],
            "source_page_count": row["source_page_count"],
            "total_source_views": row["total_source_views"],
            "latest_source_updated": row["latest_source_updated"],
            "examples": [edge.to_dict() for edge in examples],
        }

    def _wanted_materialized_rows_to_dicts(self, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        target_norms = [row["target_norm"] for row in rows]
        examples_by_norm = self._wanted_materialized_examples(target_norms)
        return [
            {
                "title": row["title"],
                "normalized_title": row["target_norm"],
                "count": row["count"],
                "source_page_count": row["source_page_count"],
                "total_source_views": row["total_source_views"],
                "latest_source_updated": row["latest_source_updated"],
                "examples": [edge.to_dict() for edge in examples_by_norm.get(row["target_norm"], [])],
            }
            for row in rows
        ]

    def _wanted_materialized_examples(self, target_norms: list[str]) -> dict[str, list[Edge]]:
        if not target_norms:
            return {}
        placeholders = ",".join("?" for _ in target_norms)
        try:
            rows = self.connection.execute(
                f"""
                SELECT
                  we.target_norm,
                  we.source_page_id,
                  source.title AS source_title,
                  source.views AS source_views,
                  source.updated AS source_updated,
                  we.line_id,
                  line.line_index,
                  line.text AS line_text,
                  we.target_title,
                  we.rank
                FROM wanted_examples we
                JOIN pages source ON source.id = we.source_page_id
                JOIN lines line ON line.line_id = we.line_id
                WHERE we.target_norm IN ({placeholders})
                ORDER BY we.target_norm, we.rank
                """,
                target_norms,
            ).fetchall()
        except sqlite3.OperationalError:
            return {norm: self._wanted_examples(norm) for norm in target_norms}

        examples: dict[str, list[Edge]] = {}
        for row in rows:
            examples.setdefault(row["target_norm"], []).append(self._edge_from_row(row))
        return examples

    def _wanted_examples(self, target_norm: str, source_page_id: str | None = None) -> list[Edge]:
        return self.backlinks_by_norm_query(target_norm, limit=5, source_page_id=source_page_id)

    def backlinks_by_norm_query(
        self,
        target_norm: str,
        limit: int | None = None,
        source_page_id: str | None = None,
    ) -> list[Edge]:
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
            JOIN pages source ON source.id = e.source_page_id
            JOIN lines line ON line.line_id = e.line_id
            WHERE e.target_norm = ?
            {source_filter}
            ORDER BY source.views DESC, COALESCE(source.updated, 0) DESC, source.title, line.line_index
        """.format(source_filter=source_filter)
        params: list[Any] = [target_norm]
        if source_page_id is not None:
            params.append(source_page_id)
        if limit is not None and limit >= 0:
            query += " LIMIT ?"
            params.append(limit)
        return [self._edge_from_row(row) for row in self.connection.execute(query, params)]

    def _neighbor_ids(self, page_id: str, norm_title: str) -> set[str]:
        rows = self.connection.execute(
            """
            SELECT target.id AS page_id
            FROM edges e
            JOIN pages target ON target.norm_title = e.target_norm
            WHERE e.source_page_id = ? AND target.id != ?
            UNION
            SELECT e.source_page_id AS page_id
            FROM edges e
            WHERE e.target_norm = ? AND e.source_page_id != ?
            """,
            (page_id, page_id, norm_title, page_id),
        ).fetchall()
        return {row["page_id"] for row in rows}

    def _sort_page_ids(self, page_ids: set[str]) -> list[str]:
        rows = self.connection.execute(
            f"""
            SELECT id, title, views
            FROM pages
            WHERE id IN ({",".join("?" for _ in page_ids)})
            ORDER BY title, views DESC
            """,
            list(page_ids),
        ).fetchall() if page_ids else []
        return [row["id"] for row in rows]

    def _page_by_id(self, page_id: str) -> Page | None:
        row = self.connection.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
        return self._page_from_row(row) if row is not None else None

    def _upsert_cosense_page(self, page: dict[str, Any]) -> None:
        page_id = str(page["id"])
        title = str(page["title"])
        lines = page.get("lines") or []
        self.connection.execute("DELETE FROM pages WHERE id = ?", (page_id,))
        self.connection.execute(
            """
            INSERT INTO pages (id, title, norm_title, created, updated, views, line_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
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
                edge_rows.append((page_id, line_id, target_title, normalize_title(target_title)))

        self.connection.executemany(
            """
            INSERT INTO lines (line_id, page_id, line_index, text, created, updated, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            line_rows,
        )
        self.connection.executemany(
            """
            INSERT INTO edges (source_page_id, line_id, target_title, target_norm)
            VALUES (?, ?, ?, ?)
            """,
            edge_rows,
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

    def _count(self, table: str) -> int:
        return self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _write_metadata(connection: sqlite3.Connection, values: dict[str, str]) -> None:
    connection.executemany(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        values.items(),
    )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _int_or_none(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


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


def rebuild_wanted(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM wanted")
    try:
        connection.execute("DELETE FROM wanted_examples")
    except sqlite3.OperationalError:
        pass
    connection.execute(
        """
        INSERT INTO wanted (
          target_norm,
          title,
          count,
          source_page_count,
          total_source_views,
          latest_source_updated
        )
        WITH wanted_edges AS (
          SELECT e.target_norm, e.target_title, e.source_page_id, source.views, source.updated
          FROM edges e
          JOIN pages source ON source.id = e.source_page_id
          LEFT JOIN pages target ON target.norm_title = e.target_norm
          WHERE target.id IS NULL
        ),
        edge_stats AS (
          SELECT
            target_norm,
            COUNT(*) AS count,
            COUNT(DISTINCT source_page_id) AS source_page_count,
            MAX(COALESCE(updated, 0)) AS latest_source_updated
          FROM wanted_edges
          GROUP BY target_norm
        ),
        source_stats AS (
          SELECT target_norm, SUM(views) AS total_source_views
          FROM (
            SELECT DISTINCT target_norm, source_page_id, views
            FROM wanted_edges
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
            FROM wanted_edges
            GROUP BY target_norm, target_title
          )
          WHERE rn = 1
        )
        SELECT
          edge_stats.target_norm,
          title_choice.target_title,
          edge_stats.count,
          edge_stats.source_page_count,
          COALESCE(source_stats.total_source_views, 0) AS total_source_views,
          edge_stats.latest_source_updated
        FROM edge_stats
        JOIN source_stats ON source_stats.target_norm = edge_stats.target_norm
        JOIN title_choice ON title_choice.target_norm = edge_stats.target_norm
        """
    )
    try:
        rebuild_wanted_examples(connection)
    except sqlite3.OperationalError:
        pass


def rebuild_wanted_examples(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO wanted_examples (
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
          JOIN pages source ON source.id = e.source_page_id
          JOIN lines line ON line.line_id = e.line_id
          LEFT JOIN pages target ON target.norm_title = e.target_norm
          WHERE target.id IS NULL
        )
        SELECT target_norm, rank, source_page_id, line_id, target_title
        FROM ranked
        WHERE rank <= 5
        """
    )
