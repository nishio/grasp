import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from grasp.journal import journal_event_json, make_journal_event
from grasp.sqlite_store import (
    SCHEMA_VERSION,
    SQLiteStore,
    canonical_store_path,
    connect_sqlite_store,
    ensure_store_schema,
    import_cache_manifest_path,
    import_export_to_sqlite,
    import_markdown_folder_to_sqlite,
    sqlite_write_transaction,
)


FIXTURE = {
    "name": "fixture",
    "displayName": "fixture",
    "exported": 1,
    "users": [],
    "pages": [
        {
            "title": "A",
            "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
            "created": 1,
            "updated": 10,
            "views": 100,
            "lines": [
                {"text": "A", "created": 1, "updated": 1, "userId": "u"},
                {"text": "links to [B] and [Missing]", "created": 1, "updated": 2, "userId": "u"},
            ],
        },
        {
            "title": "B",
            "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
            "created": 1,
            "updated": 20,
            "views": 50,
            "lines": [
                {"text": "B", "created": 1, "updated": 1, "userId": "u"},
                {"text": "links to [A]", "created": 1, "updated": 2, "userId": "u"},
            ],
        },
        {
            "title": "C",
            "id": "cccccccccccccccccccccccc",
            "created": 1,
            "updated": 30,
            "views": 10,
            "lines": [
                {"text": "C", "created": 1, "updated": 1, "userId": "u"},
                {"text": "also links to [B] and [Missing]", "created": 1, "updated": 2, "userId": "u"},
            ],
        },
    ],
}


OTHER_FIXTURE = {
    "name": "other",
    "displayName": "other",
    "exported": 2,
    "users": [],
    "pages": [
        {
            "title": "A",
            "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
            "created": 2,
            "updated": 40,
            "views": 5,
            "lines": [
                {"text": "A", "created": 2, "updated": 2, "userId": "u"},
                {"text": "other project links to [OtherMissing]", "created": 2, "updated": 3, "userId": "u"},
            ],
        }
    ],
}


class SQLiteStoreTests(unittest.TestCase):
    def test_schema_materializes_events_and_line_tombstone_tables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "store.sqlite"
            ensure_store_schema(store_path)
            connection = sqlite3.connect(store_path)
            try:
                schema_version = connection.execute(
                    "SELECT value FROM metadata WHERE key = 'schema_version'",
                ).fetchone()[0]
                events_table = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'events'",
                ).fetchone()
                line_tombstones_table = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'line_tombstones'",
                ).fetchone()
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(events)").fetchall()
                }
                line_tombstone_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(line_tombstones)").fetchall()
                }
            finally:
                connection.close()

        self.assertEqual(SCHEMA_VERSION, "13")
        self.assertEqual(schema_version, "13")
        self.assertIsNotNone(events_table)
        self.assertIsNotNone(line_tombstones_table)
        self.assertEqual(
            columns,
            {
                "event_sequence",
                "event_id",
                "schema_version",
                "event_type",
                "project",
                "created_at",
                "actor",
                "session_id",
                "payload_json",
            },
        )
        self.assertEqual(
            line_tombstone_columns,
            {
                "project",
                "line_id",
                "page_id",
                "line_index",
                "text",
                "created",
                "updated",
                "user_id",
                "tombstoned_at",
                "tombstone_reason",
            },
        )

    def test_canonical_store_path_prefers_env_then_repo_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "repo"
            env_path = Path(tmpdir) / "custom.sqlite"
            with patch.dict("os.environ", {"GRASP_CANONICAL_STORE": str(env_path)}):
                self.assertEqual(canonical_store_path(root), env_path)
            with patch.dict("os.environ", {}, clear=True):
                self.assertEqual(
                    canonical_store_path(root),
                    root / ".grasp" / "authority.sqlite",
                )

    def test_write_connection_uses_wal_and_busy_timeout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "store.sqlite"
            ensure_store_schema(store_path)
            connection = connect_sqlite_store(
                store_path,
                for_write=True,
                busy_timeout_ms=1234,
            )
            try:
                journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
                busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(journal_mode.lower(), "wal")
        self.assertEqual(busy_timeout, 1234)

    def test_sqlite_write_transaction_commits_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "store.sqlite"
            ensure_store_schema(store_path)
            connection = connect_sqlite_store(store_path, for_write=True)
            try:
                with sqlite_write_transaction(connection):
                    connection.execute(
                        "INSERT INTO metadata (key, value) VALUES (?, ?)",
                        ("committed", "yes"),
                    )
                committed = connection.execute(
                    "SELECT value FROM metadata WHERE key = ?",
                    ("committed",),
                ).fetchone()[0]
                with self.assertRaises(RuntimeError):
                    with sqlite_write_transaction(connection):
                        connection.execute(
                            "INSERT INTO metadata (key, value) VALUES (?, ?)",
                            ("rolled-back", "no"),
                        )
                        raise RuntimeError("force rollback")
                rolled_back = connection.execute(
                    "SELECT value FROM metadata WHERE key = ?",
                    ("rolled-back",),
                ).fetchone()
            finally:
                connection.close()

        self.assertEqual(committed, "yes")
        self.assertIsNone(rolled_back)

    def test_sqlite_write_transaction_serializes_competing_writers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "store.sqlite"
            ensure_store_schema(store_path)
            first = connect_sqlite_store(store_path, for_write=True, busy_timeout_ms=50, timeout=0.05)
            second = connect_sqlite_store(store_path, for_write=True, busy_timeout_ms=50, timeout=0.05)
            try:
                with sqlite_write_transaction(first):
                    first.execute(
                        "INSERT INTO metadata (key, value) VALUES (?, ?)",
                        ("first-writer", "active"),
                    )
                    with self.assertRaises(sqlite3.OperationalError):
                        with sqlite_write_transaction(second):
                            second.execute(
                                "INSERT INTO metadata (key, value) VALUES (?, ?)",
                                ("second-writer", "should-not-commit"),
                            )
                with sqlite_write_transaction(second):
                    second.execute(
                        "INSERT INTO metadata (key, value) VALUES (?, ?)",
                        ("second-writer", "after-first-commit"),
                    )
                values = dict(
                    second.execute(
                        "SELECT key, value FROM metadata WHERE key IN (?, ?)",
                        ("first-writer", "second-writer"),
                    ).fetchall()
                )
            finally:
                first.close()
                second.close()

        self.assertEqual(
            values,
            {
                "first-writer": "active",
                "second-writer": "after-first-commit",
            },
        )

    def test_imports_and_queries_legacy_journal_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "store.sqlite"
            ensure_store_schema(store_path)
            events = [
                make_journal_event(
                    "page_create",
                    project="wiki",
                    event_id="evt-1",
                    created_at="2026-06-27T00:00:00+00:00",
                    payload={
                        "page_id": "page-a",
                        "title": "A",
                        "source_path": "A.md",
                        "lines": [{"line_id": "page-a:0", "text": "# A"}],
                    },
                ),
                make_journal_event(
                    "page_update",
                    project="wiki",
                    event_id="evt-2",
                    created_at="2026-06-27T00:01:00+00:00",
                    payload={
                        "page_id": "page-a",
                        "title": "A",
                        "previous_lines": [{"line_id": "page-a:0", "text": "# A"}],
                        "lines": [{"line_id": "page-a:0", "text": "# A"}, {"line_id": "page-a:1", "text": "body"}],
                    },
                ),
                make_journal_event(
                    "log_append",
                    project="other",
                    event_id="evt-3",
                    created_at="2026-06-27T00:02:00+00:00",
                    payload={
                        "page_id": "log-page",
                        "title": "Log",
                        "inserted_lines": [{"line_id": "log-page:1", "text": "entry"}],
                    },
                ),
            ]

            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                summary = store.import_journal_events(events, actor="codex", session_id="s1")
                self.assertEqual(summary["events"], 3)
                self.assertEqual(summary["imported"], 2)
                self.assertEqual(summary["skipped"], 0)
                self.assertEqual(summary["filtered"], 1)
                self.assertEqual(summary["project"], "wiki")

                duplicate_summary = store.import_journal_events(events, actor="codex", session_id="s1")
                self.assertEqual(duplicate_summary["imported"], 0)
                self.assertEqual(duplicate_summary["skipped"], 2)
                self.assertEqual(duplicate_summary["filtered"], 1)

                stored_events = store.events(limit=None)
                self.assertEqual([event["event_id"] for event in stored_events], ["evt-1", "evt-2"])
                self.assertEqual([event["event_sequence"] for event in stored_events], [1, 2])
                self.assertEqual(stored_events[0]["actor"], "codex")
                self.assertEqual(stored_events[0]["session_id"], "s1")
                self.assertEqual(stored_events[1]["payload"]["lines"][1]["text"], "body")

                update_events = store.events(event_type="page_update")
                self.assertEqual([event["event_id"] for event in update_events], ["evt-2"])
                self.assertEqual(store.event_count(event_type="page_update"), 1)
                with self.assertRaisesRegex(ValueError, "unsupported journal event_type"):
                    store.events(event_type="unknown")
            finally:
                store.close()

    def test_imports_journal_events_from_jsonl_path_without_project_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "store.sqlite"
            journal_path = Path(tmpdir) / "events.jsonl"
            ensure_store_schema(store_path)
            events = [
                make_journal_event(
                    "section_append",
                    project="wiki",
                    event_id="evt-wiki",
                    created_at="2026-06-27T00:00:00+00:00",
                    payload={
                        "page_id": "page-a",
                        "title": "A",
                        "inserted_lines": [{"line_id": "page-a:1", "text": "body"}],
                    },
                ),
                make_journal_event(
                    "section_append",
                    project="other",
                    event_id="evt-other",
                    created_at="2026-06-27T00:01:00+00:00",
                    payload={
                        "page_id": "page-b",
                        "title": "B",
                        "inserted_lines": [{"line_id": "page-b:1", "text": "body"}],
                    },
                ),
            ]
            journal_path.write_text("".join(journal_event_json(event) for event in events), encoding="utf-8")

            store = SQLiteStore(store_path, for_write=True)
            try:
                summary = store.import_journal_events(journal_path, actor="migration")
                self.assertEqual(summary["source"], str(journal_path))
                self.assertEqual(summary["imported"], 2)
                self.assertEqual(summary["filtered"], 0)
                self.assertEqual(store.event_count(), 2)
                self.assertEqual([event["event_id"] for event in store.events(project="other")], ["evt-other"])
            finally:
                store.close()

    def test_write_markdown_page_rolls_back_state_when_event_insert_fails(self):
        class FixedUuid:
            hex = "fixed-event-id"

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                existing_event = make_journal_event(
                    "page_update",
                    project="wiki",
                    event_id="fixed-event-id",
                    created_at="2026-06-27T00:00:00+00:00",
                    payload={
                        "page_id": "preexisting",
                        "title": "Preexisting",
                        "previous_lines": [],
                        "lines": [],
                    },
                )
                store.import_journal_events([existing_event])
                page_before = store.resolve_page("A")
                self.assertEqual(
                    [line.text for line in store.page_lines(page_before)[0]],
                    ["# A"],
                )

                with patch("grasp.journal.uuid4", return_value=FixedUuid()):
                    with self.assertRaises(sqlite3.IntegrityError):
                        store.write_markdown_page_with_event("A", lines=["# A", "changed"])

                page_after = store.resolve_page("A")
                self.assertEqual(
                    [line.text for line in store.page_lines(page_after)[0]],
                    ["# A"],
                )
                self.assertEqual(store.event_count(), 1)
            finally:
                store.close()

    def test_append_markdown_lines_rolls_back_state_when_event_insert_fails(self):
        class FixedUuid:
            hex = "fixed-event-id"

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                existing_event = make_journal_event(
                    "section_append",
                    project="wiki",
                    event_id="fixed-event-id",
                    created_at="2026-06-27T00:00:00+00:00",
                    payload={
                        "page_id": "preexisting",
                        "title": "Preexisting",
                        "heading": "Existing",
                        "lines": [],
                        "inserted_lines": [],
                    },
                )
                store.import_journal_events([existing_event])
                page_before = store.resolve_page("A")
                self.assertEqual(
                    [line.text for line in store.page_lines(page_before)[0]],
                    ["# A"],
                )

                with patch("grasp.journal.uuid4", return_value=FixedUuid()):
                    with self.assertRaises(sqlite3.IntegrityError):
                        store.append_markdown_lines_with_event(
                            "A",
                            ["", "## Updates", "- changed"],
                            event_type="section_append",
                            payload={"heading": "Updates", "lines": ["- changed"]},
                        )

                page_after = store.resolve_page("A")
                self.assertEqual(
                    [line.text for line in store.page_lines(page_after)[0]],
                    ["# A"],
                )
                self.assertEqual(store.event_count(), 1)
            finally:
                store.close()

    def test_rename_markdown_page_rolls_back_state_when_event_insert_fails(self):
        class FixedUuid:
            hex = "fixed-event-id"

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nlink [[Old]]\n", encoding="utf-8")
            (root / "Old.md").write_text("# Old\nbody\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                existing_event = make_journal_event(
                    "page_rename",
                    project="wiki",
                    event_id="fixed-event-id",
                    created_at="2026-06-27T00:00:00+00:00",
                    payload={
                        "page_id": "preexisting",
                        "previous_title": "Previous",
                        "title": "Preexisting",
                        "previous_source_path": "Previous.md",
                        "source_path": "Preexisting.md",
                        "previous_aliases": [],
                        "aliases": [],
                        "previous_lines": [],
                        "lines": [],
                        "heading_updated": False,
                    },
                )
                store.import_journal_events([existing_event])
                old_before = store.resolve_page("Old")
                self.assertIsNotNone(old_before)
                self.assertEqual(old_before.title, "Old")

                with patch("grasp.journal.uuid4", return_value=FixedUuid()):
                    with self.assertRaises(sqlite3.IntegrityError):
                        store.rename_markdown_page_with_event("Old", "New")

                old_after = store.resolve_page("Old")
                new_after = store.resolve_page("New")
                self.assertIsNotNone(old_after)
                self.assertEqual(old_after.id, old_before.id)
                self.assertEqual(old_after.title, "Old")
                self.assertIsNone(new_after)
                self.assertEqual(
                    [line.text for line in store.page_lines(old_after)[0]],
                    ["# Old", "body"],
                )
                self.assertEqual(store.event_count(), 1)
            finally:
                store.close()

    def test_import_export_to_sqlite_and_query(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(FIXTURE), encoding="utf-8")

            stats = import_export_to_sqlite(export_path, store_path)
            self.assertTrue(stats["schema_ok"])
            self.assertEqual(stats["pages"], 3)
            self.assertEqual(stats["lines"], 6)
            self.assertEqual(stats["edges"], 5)
            self.assertEqual(stats["unresolved_targets"], 1)
            manifest = json.loads(import_cache_manifest_path(store_path).read_text(encoding="utf-8"))
            cached_path = Path(manifest["projects"]["fixture"]["path"])
            self.assertEqual(manifest["last_imported_project"], "fixture")
            self.assertTrue(cached_path.exists())

            store = SQLiteStore(store_path)
            try:
                page = store.resolve_page("a")
                self.assertIsNotNone(page)
                self.assertEqual(page.line_count, 2)
                self.assertTrue(store.schema_ok())

                lines, truncated = store.page_lines(page, limit=1)
                self.assertEqual([line.text for line in lines], ["A"])
                self.assertTrue(truncated)

                lines, truncated = store.page_lines(page, limit=1, offset=1)
                self.assertEqual([line.text for line in lines], ["links to [B] and [Missing]"])
                self.assertFalse(truncated)

                backlinks = store.backlinks("b")
                self.assertEqual([edge.source_title for edge in backlinks], ["A", "C"])

                hits = store.search("links", limit=2)
                self.assertEqual([hit["source_title"] for hit in hits], ["A", "B"])
                self.assertEqual(hits[0]["line_id"], "aaaaaaaaaaaaaaaaaaaaaaaa:1")
                self.assertEqual(hits[0]["match_mode"], "literal")

                unresolved_targets = store.unresolved_targets()
                self.assertEqual(unresolved_targets[0]["title"], "Missing")
                self.assertEqual(unresolved_targets[0]["link_count"], 2)

                existing_stats = store.link_stats("B")
                self.assertTrue(existing_stats["page_exists"])
                self.assertEqual(existing_stats["title"], "B")
                self.assertEqual(existing_stats["link_count"], 2)
                self.assertEqual(existing_stats["source_page_count"], 2)
                self.assertEqual(existing_stats["link_multiplicity"], "multi")

                missing_stats = store.link_stats("Missing")
                self.assertFalse(missing_stats["page_exists"])
                self.assertEqual(missing_stats["title"], "Missing")
                self.assertEqual(missing_stats["link_count"], 2)
                self.assertEqual(missing_stats["source_page_count"], 2)
                self.assertEqual(missing_stats["link_multiplicity"], "multi")

                top_links = store.top_internal_links(limit=2, sample_limit=1)
                self.assertEqual([item["title"] for item in top_links], ["B", "Missing"])
                self.assertTrue(top_links[0]["target_page_exists"])
                self.assertFalse(top_links[1]["target_page_exists"])
                self.assertEqual(top_links[0]["link_count"], 2)
                self.assertEqual(top_links[0]["examples"][0]["target_title"], "B")

                absent_stats = store.link_stats("Nope")
                self.assertFalse(absent_stats["page_exists"])
                self.assertEqual(absent_stats["link_count"], 0)
                self.assertEqual(absent_stats["source_page_count"], 0)
                self.assertEqual(absent_stats["link_multiplicity"], "none")

                missing_related = store.related("Missing")
                self.assertEqual([item["title"] for item in missing_related], ["A", "C"])
                self.assertEqual(missing_related[0]["relation"], "backlink-source")
                self.assertEqual(missing_related[0]["score"], 1)

                path = store.paths_between("A", "C", max_depth=2, limit=3)
                self.assertEqual(path["path_count"], 2)
                self.assertEqual(path["paths"][0]["distance"], 2)
                self.assertEqual(path["paths"][0]["nodes"][0]["title"], "A")
                self.assertEqual(path["paths"][0]["nodes"][-1]["title"], "C")
                self.assertIn(
                    ["page", "unresolved", "page"],
                    [[node["kind"] for node in path_item["nodes"]] for path_item in path["paths"]],
                )

                too_shallow_path = store.paths_between("A", "C", max_depth=1, limit=1)
                self.assertEqual(too_shallow_path["path_count"], 0)
                self.assertEqual(too_shallow_path["source"]["title"], "A")
                self.assertEqual(too_shallow_path["target"]["title"], "C")
                path_hints = too_shallow_path["recovery_hints"]["path"]
                self.assertEqual(path_hints["reason"], "no_path_within_max_depth")
                self.assertEqual(path_hints["next_max_depth"], 2)
                self.assertEqual(path_hints["source_link_stats"]["title"], "A")
                self.assertEqual(path_hints["target_link_stats"]["title"], "C")
                self.assertEqual(path_hints["source_related"][0]["title"], "C")
                self.assertTrue(path_hints["source_backlinks"])

                missing_hinge_path = store.paths_between("A", "Missing", max_depth=1, limit=1)
                self.assertEqual(missing_hinge_path["path_count"], 1)
                self.assertEqual(missing_hinge_path["paths"][0]["distance"], 1)
                self.assertEqual(missing_hinge_path["paths"][0]["nodes"][-1]["kind"], "unresolved")
                self.assertEqual(missing_hinge_path["paths"][0]["nodes"][-1]["title"], "Missing")

                no_path = store.paths_between("A", "Nope", max_depth=2, limit=1)
                self.assertEqual(no_path["path_count"], 0)
                self.assertIsNone(no_path["target"])
                self.assertIsNotNone(no_path["recovery_hints"]["target"])

                read = store.read("A", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertEqual(read["page"]["title"], "A")
                self.assertEqual(read["backlink_count_total"], 1)
                self.assertIsNone(read["line_window"])
                self.assertEqual(read["unresolved_targets"][0]["examples"][0]["source_title"], "A")
                self.assertNotIn("snippet_lines", read["related"][0])

                read_around_line = store.read_around_line(
                    "aaaaaaaaaaaaaaaaaaaaaaaa:1",
                    line_context=0,
                    backlink_limit=0,
                    related_limit=0,
                    unresolved_limit=0,
                )
                self.assertEqual(read_around_line["page"]["title"], "A")
                self.assertEqual([line["text"] for line in read_around_line["lines"]], ["links to [B] and [Missing]"])
                self.assertEqual(read_around_line["line_window"]["around_line_id"], "aaaaaaaaaaaaaaaaaaaaaaaa:1")
                self.assertEqual(read_around_line["line_window"]["start_index"], 1)
                self.assertEqual(read_around_line["line_window"]["end_index"], 1)
                self.assertTrue(read_around_line["lines_truncated"])

                with self.assertRaisesRegex(ValueError, "belongs to page A, not B"):
                    store.read_around_line("aaaaaaaaaaaaaaaaaaaaaaaa:1", title="B")

                read_with_snippets = store.read(
                    "A",
                    backlink_limit=10,
                    related_limit=10,
                    unresolved_limit=10,
                    related_snippets=True,
                    related_snippet_lines=1,
                )
                self.assertEqual(read_with_snippets["related"][0]["title"], "C")
                self.assertEqual(
                    [line["text"] for line in read_with_snippets["related"][0]["snippet_lines"]],
                    ["C"],
                )
                self.assertEqual(read_with_snippets["related"][0]["snippet_mode"], "lead")
                self.assertTrue(read_with_snippets["related"][0]["snippet_truncated"])

                read_with_edge_snippets = store.read(
                    "A",
                    backlink_limit=10,
                    related_limit=10,
                    unresolved_limit=10,
                    related_snippets=True,
                    related_snippet_lines=1,
                    related_snippet_mode="edge",
                )
                self.assertEqual(read_with_edge_snippets["related"][0]["title"], "C")
                self.assertEqual(
                    [line["text"] for line in read_with_edge_snippets["related"][0]["snippet_lines"]],
                    ["also links to [B] and [Missing]"],
                )
                self.assertEqual(read_with_edge_snippets["related"][0]["snippet_mode"], "edge")
                self.assertEqual(
                    read_with_edge_snippets["related"][0]["snippet_window"]["context_line_id"],
                    "cccccccccccccccccccccccc:1",
                )

                missing_read = store.read("Missing", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertIsNone(missing_read["page"])
                self.assertEqual(missing_read["backlink_count_total"], 2)
                self.assertEqual([item["title"] for item in missing_read["related"]], ["A", "C"])

                missing_read_with_snippets = store.read(
                    "Missing",
                    backlink_limit=10,
                    related_limit=10,
                    unresolved_limit=10,
                    related_snippets=True,
                    related_snippet_lines=1,
                )
                self.assertIsNone(missing_read_with_snippets["page"])
                self.assertEqual(
                    [line["text"] for line in missing_read_with_snippets["related"][0]["snippet_lines"]],
                    ["A"],
                )
                self.assertTrue(missing_read_with_snippets["related"][0]["snippet_truncated"])

                missing_read_with_edge_snippets = store.read(
                    "Missing",
                    backlink_limit=10,
                    related_limit=10,
                    unresolved_limit=10,
                    related_snippets=True,
                    related_snippet_lines=1,
                    related_snippet_mode="edge",
                )
                self.assertEqual(
                    [line["text"] for line in missing_read_with_edge_snippets["related"][0]["snippet_lines"]],
                    ["links to [B] and [Missing]"],
                )
                self.assertEqual(missing_read_with_edge_snippets["related"][0]["snippet_mode"], "edge")

                export_1hop = store.export_ai("A", depth=1, direct_limit=10)
                self.assertTrue(export_1hop["page_exists"])
                self.assertEqual(export_1hop["page_count"], 2)
                self.assertIn('type="mainpage"', export_1hop["text"])
                self.assertIn('<Page title="A"', export_1hop["text"])
                self.assertIn('<Page title="B"', export_1hop["text"])
                self.assertNotIn('<Page title="C"', export_1hop["text"])

                export_2hop = store.export_ai("A", depth=2, direct_limit=10, indirect_limit=10)
                self.assertEqual(export_2hop["page_count"], 3)
                self.assertEqual([page["title"] for page in export_2hop["pages"]], ["A", "B", "C"])
                self.assertIn('type="2hopLink"', export_2hop["text"])

                missing_export = store.export_ai("Missing", depth=1, direct_limit=10)
                self.assertFalse(missing_export["page_exists"])
                self.assertEqual([page["title"] for page in missing_export["pages"]], ["A", "C"])
                self.assertIn("main page not present in local store", missing_export["text"])
                self.assertNotIn('<Page title="Missing"', missing_export["text"])
            finally:
                store.close()

    def test_read_returns_ambiguity_for_duplicate_visible_handle(self):
        fixture = {
            "name": "fixture",
            "displayName": "fixture",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "Same",
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                    "created": 1,
                    "updated": 1,
                    "views": 1,
                    "lines": [{"text": "Same", "created": 1, "updated": 1, "userId": "u"}],
                },
                {
                    "title": "same",
                    "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                    "created": 1,
                    "updated": 2,
                    "views": 2,
                    "lines": [{"text": "same", "created": 1, "updated": 2, "userId": "u"}],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")

            import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path, project="fixture")
            try:
                ambiguous = store.read("Same")
                self.assertIsNone(ambiguous["page"])
                self.assertEqual(ambiguous["ambiguity"]["type"], "handle_ambiguity")
                self.assertEqual(ambiguous["ambiguity"]["candidate_count"], 2)
                self.assertEqual(
                    {candidate["page_id"] for candidate in ambiguous["ambiguity"]["candidates"]},
                    {"aaaaaaaaaaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbbbbbbbbbb"},
                )

                selected = store.read(page_id="bbbbbbbbbbbbbbbbbbbbbbbb")
                self.assertEqual(selected["page"]["title"], "same")
                self.assertIsNone(selected["ambiguity"])
            finally:
                store.close()

    def test_suggest_fuzzy_finds_long_sentence_titles(self):
        long_title = "再会は書字のタダの副産物で委譲が奪った-20260613"
        fixture = {
            "name": "fixture",
            "displayName": "fixture",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": long_title,
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                    "created": 1,
                    "updated": 10,
                    "views": 10,
                    "lines": [{"text": long_title, "created": 1, "updated": 1, "userId": "u"}],
                },
                {
                    "title": "書字の練習",
                    "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                    "created": 1,
                    "updated": 2,
                    "views": 100,
                    "lines": [{"text": "書字の練習", "created": 1, "updated": 1, "userId": "u"}],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path)
            try:
                suggestions = store.suggest("書字 副産物", limit=5)
                self.assertEqual(suggestions[0]["title"], long_title)
                self.assertEqual(suggestions[0]["match_mode"], "terms")
                self.assertEqual(suggestions[0]["matched_terms"], ["書字", "副産物"])

                compact = store.suggest("再会書字委譲", limit=5)
                self.assertEqual(compact[0]["title"], long_title)
                self.assertEqual(compact[0]["match_mode"], "subsequence")

                strict = store.suggest("書字 副産物", limit=5, mode="substring")
                self.assertEqual(strict, [])

                missing_read = store.read("再会 副産物", backlink_limit=0, related_limit=0, unresolved_limit=0)
                hint_titles = [
                    item["title"]
                    for item in missing_read["recovery_hints"]["suggest"]["suggestions"]
                ]
                self.assertIn(long_title, hint_titles)
            finally:
                store.close()

    def test_line_windows_return_stored_opaque_line_ids(self):
        fixture = {
            "name": "fixture",
            "displayName": "fixture",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "Opaque",
                    "id": "opaque-page",
                    "created": 1,
                    "updated": 10,
                    "views": 1,
                    "lines": [
                        {"text": "before", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "needle center", "created": 1, "updated": 2, "userId": "u"},
                        {"text": "after", "created": 1, "updated": 3, "userId": "u"},
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path)
            try:
                with store.connection:
                    store.connection.execute(
                        """
                        UPDATE lines
                        SET line_id = ?
                        WHERE project = ? AND page_id = ? AND line_index = ?
                        """,
                        ("opaque-line-b", "fixture", "opaque-page", 1),
                    )

                read = store.read_around_line(
                    "opaque-line-b",
                    line_context=1,
                    backlink_limit=0,
                    related_limit=0,
                    unresolved_limit=0,
                )
                self.assertEqual(read["line_window"]["around_line_id"], "opaque-line-b")
                self.assertEqual([line["text"] for line in read["lines"]], ["before", "needle center", "after"])

                hits = store.search("needle", limit=1, context=1)
                self.assertEqual(hits[0]["line_id"], "opaque-line-b")
                self.assertEqual(hits[0]["context_window"]["around_line_id"], "opaque-line-b")
            finally:
                store.close()

    def test_imports_multiple_projects_into_one_store_without_mixing_graphs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            other_export_path = Path(tmpdir) / "other.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(FIXTURE), encoding="utf-8")
            other_export_path.write_text(json.dumps(OTHER_FIXTURE), encoding="utf-8")

            fixture_stats = import_export_to_sqlite(export_path, store_path)
            other_stats = import_export_to_sqlite(other_export_path, store_path)

            self.assertEqual(fixture_stats["project"], "fixture")
            self.assertEqual(other_stats["project"], "other")
            self.assertEqual(other_stats["project_count"], 2)

            aggregate_store = SQLiteStore(store_path)
            fixture_store = SQLiteStore(store_path, project="fixture")
            other_store = SQLiteStore(store_path, project="other")
            try:
                aggregate_stats = aggregate_store.stats()
                self.assertIsNone(aggregate_stats["project"])
                self.assertEqual(aggregate_stats["project_count"], 2)
                self.assertEqual(aggregate_stats["pages"], 4)

                ambiguous_read = aggregate_store.read("A")
                self.assertEqual(ambiguous_read["ambiguity"]["candidate_count"], 2)
                self.assertEqual(
                    sorted(candidate["project"] for candidate in ambiguous_read["ambiguity"]["candidates"]),
                    ["fixture", "other"],
                )

                fixture_page = fixture_store.resolve_page("A")
                other_page = other_store.resolve_page("A")
                self.assertEqual(fixture_page.views, 100)
                self.assertEqual(other_page.views, 5)
                self.assertEqual(fixture_store.unresolved_targets()[0]["title"], "Missing")
                self.assertEqual(other_store.unresolved_targets()[0]["title"], "OtherMissing")
            finally:
                aggregate_store.close()
                fixture_store.close()
                other_store.close()

    def test_whole_store_cross_project_retrieval_materializes_strong_and_weak_edges(self):
        alpha = {
            "name": "alpha",
            "displayName": "alpha",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "Alpha",
                    "id": "alphaalphaalphaalphaaaaa",
                    "created": 1,
                    "updated": 50,
                    "views": 100,
                    "lines": [
                        {"text": "Alpha needle", "created": 1, "updated": 1, "userId": "u"},
                        {
                            "text": "explicit [/beta/Beta], weak [Beta], and [SharedMissing]",
                            "created": 1,
                            "updated": 2,
                            "userId": "u",
                        },
                    ],
                }
            ],
        }
        beta = {
            "name": "beta",
            "displayName": "beta",
            "exported": 2,
            "users": [],
            "pages": [
                {
                    "title": "Beta",
                    "id": "betabetabetabetabetabbbb",
                    "created": 2,
                    "updated": 60,
                    "views": 80,
                    "lines": [
                        {"text": "Beta needle", "created": 2, "updated": 1, "userId": "u"},
                        {"text": "also [SharedMissing]", "created": 2, "updated": 2, "userId": "u"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            alpha_path = Path(tmpdir) / "alpha.json"
            beta_path = Path(tmpdir) / "beta.json"
            store_path = Path(tmpdir) / "store.sqlite"
            alpha_path.write_text(json.dumps(alpha), encoding="utf-8")
            beta_path.write_text(json.dumps(beta), encoding="utf-8")
            import_export_to_sqlite(alpha_path, store_path)
            import_export_to_sqlite(beta_path, store_path)

            store = SQLiteStore(store_path)
            try:
                hits = store.search("needle", limit=10)
                self.assertEqual([hit["project"] for hit in hits], ["alpha", "beta"])

                beta_read = store.read("Beta", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertEqual(beta_read["page"]["project"], "beta")
                backlink_kinds = sorted(
                    (edge["connection_strength"], edge["link_kind"], edge["target_project"])
                    for edge in beta_read["backlinks"]
                )
                self.assertIn(("strong", "cross-semantic", "beta"), backlink_kinds)
                self.assertIn(("weak", "inferred-normalized-title", "beta"), backlink_kinds)

                shared = store.unresolved_targets(limit=10)[0]
                self.assertEqual(shared["title"], "SharedMissing")
                self.assertEqual(shared["link_count"], 2)
                self.assertEqual(shared["project_count"], 2)
                self.assertEqual(shared["projects"], ["alpha", "beta"])
                self.assertEqual(shared["examples"][0]["connection_strength"], "strong")
                self.assertEqual(shared["examples"][0]["link_kind"], "internal")

                shared_read = store.read("SharedMissing", backlink_limit=10, related_limit=10)
                self.assertEqual(shared_read["backlink_count_total"], 2)
                self.assertEqual(
                    sorted(item["project"] for item in shared_read["related"]),
                    ["alpha", "beta"],
                )

                path = store.paths_between("Alpha", "Beta", max_depth=1, limit=3)
                self.assertEqual(path["path_count"], 1)
                self.assertEqual(path["paths"][0]["distance"], 1)
                self.assertEqual(path["paths"][0]["edges"][0]["target_project"], "beta")
                self.assertIn(path["paths"][0]["edges"][0]["connection_strength"], {"strong", "weak"})
            finally:
                store.close()

    def test_import_materializes_hash_tags_and_numeric_links(self):
        fixture = {
            "name": "fixture",
            "displayName": "fixture",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "A",
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                    "created": 1,
                    "updated": 10,
                    "views": 100,
                    "lines": [
                        {"text": "A", "created": 1, "updated": 1, "userId": "u"},
                        {
                            "text": "links to [2024] and #topic but not xs[0] or https://example.com/#fragment",
                            "created": 1,
                            "updated": 2,
                            "userId": "u",
                        },
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            stats = import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path)
            try:
                self.assertEqual(stats["edges"], 2)
                self.assertEqual(stats["unresolved_targets"], 2)
                self.assertEqual(store.link_stats("2024")["link_count"], 1)
                self.assertEqual(store.link_stats("topic")["link_count"], 1)
                self.assertEqual(store.link_stats("0")["link_count"], 0)
                self.assertEqual(store.link_stats("fragment")["link_count"], 0)
            finally:
                store.close()

    def test_unresolved_ranks_issue_number_hashtags_as_non_semantic_edges(self):
        fixture = {
            "name": "fixture",
            "displayName": "fixture",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "A",
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                    "created": 1,
                    "updated": 10,
                    "views": 100,
                    "lines": [
                        {"text": "A", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "PR #2 fixes import and links to [Missing]", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
                {
                    "title": "B",
                    "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                    "created": 1,
                    "updated": 20,
                    "views": 50,
                    "lines": [
                        {"text": "B", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "Open Question #2 remains", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
                {
                    "title": "C",
                    "id": "cccccccccccccccccccccccc",
                    "created": 1,
                    "updated": 30,
                    "views": 10,
                    "lines": [
                        {"text": "C", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "notes for #2024", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            stats = import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path)
            try:
                self.assertEqual(stats["edges"], 4)
                self.assertEqual(store.link_stats("2")["link_count"], 2)
                unresolved_targets = store.unresolved_targets()
                self.assertEqual([item["title"] for item in unresolved_targets], ["Missing", "2024", "2"])

                issue_target = unresolved_targets[-1]
                self.assertEqual(issue_target["semantic_annotation"]["graph_scope"], "non-semantic")
                self.assertEqual(issue_target["semantic_annotation"]["semantic_role"], "issue-number")
                self.assertEqual(
                    issue_target["examples"][0]["semantic_annotation"]["semantic_role"],
                    "issue-number",
                )
                self.assertNotIn("semantic_annotation", unresolved_targets[1])
            finally:
                store.close()

    def test_mentions_co_links_and_gather_surface_hub_slices(self):
        fixture = {
            "name": "fixture",
            "displayName": "fixture",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "Root",
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                    "created": 1,
                    "updated": 40,
                    "views": 100,
                    "lines": [
                        {"text": "Root", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "KJ法 root [KJ法] with [表札づくり]", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
                {
                    "title": "Slice",
                    "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                    "created": 1,
                    "updated": 30,
                    "views": 80,
                    "lines": [
                        {"text": "Slice", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "KJ法 slice [グループ編成]", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
                {
                    "title": "LinkedOnly",
                    "id": "cccccccccccccccccccccccc",
                    "created": 1,
                    "updated": 20,
                    "views": 70,
                    "lines": [
                        {"text": "LinkedOnly", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "only [KJ法]", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
                {
                    "title": "QueryLink",
                    "id": "dddddddddddddddddddddddd",
                    "created": 1,
                    "updated": 10,
                    "views": 60,
                    "lines": [
                        {"text": "QueryLink", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "KJ法 app [KJ法応用]", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
                {
                    "title": "BroadQueryTitle",
                    "id": "eeeeeeeeeeeeeeeeeeeeeeee",
                    "created": 1,
                    "updated": 5,
                    "views": 50,
                    "lines": [
                        {"text": "BroadQueryTitle", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "KJ法 session [KJ法勉強会]", "created": 1, "updated": 2, "userId": "u"},
                        {"text": "KJ法 notes [KJ法勉強会]", "created": 1, "updated": 3, "userId": "u"},
                    ],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path)
            try:
                mentions = store.mentions("KJ法", limit=10)
                summary = mentions["summary"]
                self.assertEqual(summary["total_lines"], 6)
                self.assertEqual(summary["total_occurrences"], 10)
                self.assertEqual(summary["bare_lines"], 5)
                self.assertEqual(summary["bare_occurrences"], 5)
                self.assertEqual(summary["linked_occurrences"], 5)
                self.assertEqual(
                    [hit["source_title"] for hit in mentions["mentions"]],
                    ["Root", "Slice", "QueryLink", "BroadQueryTitle", "BroadQueryTitle"],
                )
                self.assertEqual(
                    [hit["classification"] for hit in mentions["mentions"]],
                    ["exact-link-page", "unlinked-page", "query-link-page", "query-link-page", "query-link-page"],
                )
                self.assertEqual(
                    summary["page_status_counts"]["unlinked-page"],
                    {"lines": 1, "pages": 1, "bare_occurrences": 1},
                )
                candidate = summary["come_from_candidate"]
                self.assertTrue(candidate["is_candidate"])
                self.assertGreaterEqual(candidate["score"], candidate["thresholds"]["score"])
                self.assertEqual(candidate["signals"]["unlinked_pages"], 1)

                all_mentions = store.mentions("KJ法", limit=10, include_linked=True)
                self.assertEqual(
                    [hit["source_title"] for hit in all_mentions["mentions"]],
                    ["Root", "Slice", "LinkedOnly", "QueryLink", "BroadQueryTitle", "BroadQueryTitle"],
                )

                unlinked_mentions = store.mentions("KJ法", limit=10, unlinked_only=True)
                self.assertEqual(unlinked_mentions["mode"], "unlinked")
                self.assertEqual(unlinked_mentions["summary"]["bare_occurrences"], 5)
                self.assertEqual(unlinked_mentions["summary"]["returned_lines"], 1)
                self.assertEqual([hit["source_title"] for hit in unlinked_mentions["mentions"]], ["Slice"])

                co_links = store.co_links("KJ法", limit=10, sample_limit=1)
                self.assertEqual([item["title"] for item in co_links], ["表札づくり", "グループ編成", "KJ法勉強会", "KJ法応用"])
                self.assertEqual(
                    [item["target_relation"] for item in co_links],
                    ["slice-handle", "slice-handle", "query-containing-title", "query-containing-title"],
                )
                self.assertEqual(co_links[0]["line_count"], 1)
                self.assertEqual(co_links[0]["examples"][0]["source_title"], "Root")
                raw_co_links = store.co_links("KJ法", limit=10, sample_limit=1, rank_mode="raw")
                self.assertEqual([item["title"] for item in raw_co_links[:2]], ["KJ法勉強会", "表札づくり"])

                gather = store.gather("KJ法", budget=1500, mention_limit=1, co_link_limit=1, backlink_limit=1)
                self.assertEqual(gather["limits"]["mentions"], 1)
                self.assertEqual(gather["mention_summary"]["bare_occurrences"], 5)
                self.assertTrue(gather["mention_summary"]["come_from_candidate"]["is_candidate"])
                self.assertEqual([item["title"] for item in gather["co_links"]], ["表札づくり"])
                self.assertEqual(gather["backlinks"][0]["source_title"], "Root")
                self.assertEqual(
                    gather["returned_counts"],
                    {"mentions": 1, "co_links": 1, "backlinks": 1},
                )
                self.assertEqual(
                    gather["total_counts"],
                    {"mentions": 5, "co_links": 4, "backlinks": 2},
                )
                self.assertEqual(
                    gather["omitted_counts"],
                    {"mentions": 4, "co_links": 3, "backlinks": 1},
                )
                self.assertEqual(gather["co_link_rank_mode"], "slice")
                self.assertEqual(gather["row_count_basis"]["mentions"], "bare mention lines")
                self.assertEqual(gather["recipes"][0]["command"][:2], ["grasp", "co-links"])
            finally:
                store.close()

    def test_cross_project_refs_classifies_and_ranks_slash_links(self):
        fixture = {
            "name": "nishio",
            "displayName": "nishio",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "A",
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                    "created": 1,
                    "updated": 20,
                    "views": 100,
                    "lines": [
                        {"text": "A", "created": 1, "updated": 1, "userId": "u"},
                        {
                            "text": "refs [/villagepump/Page A] and [/villagepump/nishio.icon] and [/plurality-japanese]",
                            "created": 1,
                            "updated": 2,
                            "userId": "u",
                        },
                    ],
                },
                {
                    "title": "B",
                    "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                    "created": 1,
                    "updated": 10,
                    "views": 50,
                    "lines": [
                        {"text": "B", "created": 1, "updated": 1, "userId": "u"},
                        {
                            "text": "self [/nishio/Self] and slash title [/takker/takker99/ScrapBubble]",
                            "created": 1,
                            "updated": 2,
                            "userId": "u",
                        },
                    ],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path)
            try:
                refs = store.cross_project_refs(limit=10, sample_limit=1)
                self.assertEqual(
                    refs["summary"]["target_class_counts"],
                    {"semantic": 2, "icon": 1, "project-root": 1, "self-project": 1},
                )
                self.assertEqual(refs["summary"]["filtered_refs"], 4)
                self.assertEqual([item["project"] for item in refs["projects"]], ["villagepump", "plurality-japanese", "takker"])
                self.assertEqual(refs["projects"][0]["mention_count"], 2)
                self.assertEqual(
                    refs["projects"][0]["target_class_counts"],
                    {"semantic": 1, "icon": 1, "project-root": 0, "self-project": 0},
                )
                self.assertEqual(refs["projects"][0]["seed_titles"], ["Page A"])
                self.assertEqual(refs["projects"][0]["examples"][0]["target_title"], "Page A")

                semantic_refs = store.cross_project_refs(limit=10, semantic_only=True, seed_limit=1)
                self.assertEqual(semantic_refs["summary"]["filtered_refs"], 2)
                self.assertEqual([item["project"] for item in semantic_refs["projects"]], ["villagepump", "takker"])
                self.assertEqual(semantic_refs["projects"][1]["top_targets"][0]["title"], "takker99/ScrapBubble")
                self.assertEqual(semantic_refs["projects"][1]["seed_titles"], ["takker99/ScrapBubble"])
                self.assertEqual(semantic_refs["projects"][1]["seed_title_limit"], 1)

                with_self = store.cross_project_refs(limit=10, include_self=True)
                self.assertEqual(with_self["summary"]["filtered_refs"], 5)
                self.assertIn("nishio", [item["project"] for item in with_self["projects"]])

                to_nishio = store.cross_project_refs_to("nishio", limit=2, sample_limit=1)
                self.assertEqual(to_nishio["mention_count"], 1)
                self.assertEqual(to_nishio["source_page_count"], 1)
                self.assertEqual(to_nishio["top_targets"][0]["title"], "Self")
                self.assertEqual(to_nishio["examples"][0]["target_project"], "nishio")
            finally:
                store.close()

    def test_search_boolean_mode_supports_line_and_page_scope(self):
        fixture = {
            "name": "fixture",
            "displayName": "fixture",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "Both",
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                    "created": 1,
                    "updated": 30,
                    "views": 100,
                    "lines": [
                        {"text": "Both", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "alpha appears here", "created": 1, "updated": 2, "userId": "u"},
                        {"text": "beta appears later", "created": 1, "updated": 3, "userId": "u"},
                    ],
                },
                {
                    "title": "AOnly",
                    "id": "bbbbbbbbbbbbbbbbbbbbbbbb",
                    "created": 1,
                    "updated": 20,
                    "views": 90,
                    "lines": [
                        {"text": "AOnly", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "alpha appears here too", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
                {
                    "title": "BOnly",
                    "id": "cccccccccccccccccccccccc",
                    "created": 1,
                    "updated": 10,
                    "views": 80,
                    "lines": [
                        {"text": "BOnly", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "beta appears here too", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path)
            try:
                literal_hits = store.search("alpha beta", limit=10)
                self.assertEqual(literal_hits, [])

                page_and_hits = store.search("alpha AND beta", mode="boolean", scope="page", limit=10)
                self.assertEqual([hit["source_title"] for hit in page_and_hits], ["Both", "Both"])
                self.assertEqual([hit["line_index"] for hit in page_and_hits], [1, 2])
                self.assertEqual(page_and_hits[0]["match_terms"], ["alpha"])
                self.assertEqual(page_and_hits[1]["match_terms"], ["beta"])
                self.assertEqual(page_and_hits[0]["match_mode"], "literal")

                implicit_page_and_hits = store.search("alpha beta", mode="boolean", scope="page", limit=10)
                self.assertEqual([hit["source_title"] for hit in implicit_page_and_hits], ["Both", "Both"])

                line_hits = store.search("alpha AND appears", mode="boolean", scope="line", limit=10)
                self.assertEqual([hit["source_title"] for hit in line_hits], ["Both", "AOnly"])

                page_not_hits = store.search("alpha AND NOT beta", mode="boolean", scope="page", limit=10)
                self.assertEqual([hit["source_title"] for hit in page_not_hits], ["AOnly"])

                line_or_hits = store.search("alpha OR beta", mode="boolean", scope="line", limit=10)
                self.assertEqual(
                    [hit["source_title"] for hit in line_or_hits],
                    ["Both", "Both", "AOnly", "BOnly"],
                )
            finally:
                store.close()

    def test_search_context_includes_bounded_line_window(self):
        fixture = {
            "name": "fixture",
            "displayName": "fixture",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "A",
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                    "created": 1,
                    "updated": 10,
                    "views": 100,
                    "lines": [
                        {"text": "title", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "before", "created": 1, "updated": 2, "userId": "u"},
                        {"text": "needle appears here", "created": 1, "updated": 3, "userId": "u"},
                        {"text": "after", "created": 1, "updated": 4, "userId": "u"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path)
            try:
                hits = store.search("needle", limit=10, context=1)
                self.assertEqual(len(hits), 1)
                self.assertEqual(
                    [line["text"] for line in hits[0]["context_lines"]],
                    ["before", "needle appears here", "after"],
                )
                self.assertEqual(
                    hits[0]["context_window"]["around_line_id"],
                    "aaaaaaaaaaaaaaaaaaaaaaaa:2",
                )
                self.assertEqual(hits[0]["context_window"]["start_index"], 1)
                self.assertEqual(hits[0]["context_window"]["end_index"], 3)
                self.assertTrue(hits[0]["context_window"]["truncated_before"])
                self.assertFalse(hits[0]["context_window"]["truncated_after"])

                compact_hits = store.search("needle", limit=10)
                self.assertNotIn("context_lines", compact_hits[0])
            finally:
                store.close()

    def test_search_loose_normalization_matches_long_vowel_and_kana_width(self):
        fixture = {
            "name": "fixture",
            "displayName": "fixture",
            "exported": 1,
            "users": [],
            "pages": [
                {
                    "title": "A",
                    "id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                    "created": 1,
                    "updated": 10,
                    "views": 100,
                    "lines": [
                        {"text": "A", "created": 1, "updated": 1, "userId": "u"},
                        {"text": "links to [ユーザーテスト]", "created": 1, "updated": 2, "userId": "u"},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "export.json"
            store_path = Path(tmpdir) / "store.sqlite"
            export_path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            import_export_to_sqlite(export_path, store_path)

            store = SQLiteStore(store_path)
            try:
                hits = store.search("ﾕｰｻﾞﾃｽﾄ", limit=3)
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0]["source_title"], "A")
                self.assertEqual(hits[0]["line_index"], 1)
                self.assertEqual(hits[0]["match_mode"], "normalized")
                self.assertEqual(hits[0]["match_terms"], ["ユザテスト"])

                result = store.read("ユーザテスト", backlink_limit=3, related_limit=3, unresolved_limit=3)
                self.assertIsNone(result["page"])
                self.assertEqual(result["backlink_count_total"], 0)
                hints = result["recovery_hints"]
                self.assertIsNotNone(hints)
                self.assertEqual(hints["unresolved_targets"]["targets"][0]["title"], "ユーザーテスト")
                self.assertEqual(hints["search"]["hits"][0]["match_mode"], "normalized")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
