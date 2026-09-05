import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from grasp.cli import main
from grasp.sqlite_store import SQLiteStore, import_markdown_folder_to_sqlite


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _bump_mtime(path: Path, delta_seconds: int = 5) -> None:
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + delta_seconds * 1_000_000_000))


class MarkdownRefreshStoreTests(unittest.TestCase):
    def _import(self, root: Path) -> tuple[Path, Path]:
        store_path = root / "store.sqlite"
        source = root / "wiki"
        source.mkdir()
        _write(source / "A.md", "# A\n[[B]]\nold line\n")
        _write(source / "B.md", "# B\nbody\n")
        import_markdown_folder_to_sqlite(source, store_path, project_name="wiki")
        return store_path, source

    def test_read_refresh_reparses_changed_source_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path, source = self._import(Path(tmpdir))
            _write(source / "A.md", "# A\n[[B]]\nnew line\n[[C]]\n")
            _bump_mtime(source / "A.md")

            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                result = store.read("A", refresh=True)
                second = store.read("A", refresh=True)
                c_links = store.link_stats("C")
            finally:
                store.close()

        refresh = result["markdown_refresh"]
        self.assertTrue(refresh["refreshed"])
        self.assertEqual(refresh["reason"], "source_changed")
        self.assertEqual(refresh["source_path"], "A.md")
        self.assertEqual([line["text"] for line in result["lines"]], ["# A", "[[B]]", "new line", "[[C]]"])
        self.assertEqual(c_links["link_count"], 1)
        self.assertEqual(second["markdown_refresh"]["reason"], "fresh")

    def test_read_refresh_picks_up_title_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path, source = self._import(Path(tmpdir))
            _write(source / "A.md", "# Renamed A\nbody\n")
            _bump_mtime(source / "A.md")

            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                result = store.read(None, page_id=result_page_id(store), refresh=True)
            finally:
                store.close()

        self.assertTrue(result["markdown_refresh"]["refreshed"])
        self.assertEqual(result["page"]["title"], "Renamed A")

    def test_read_refresh_is_noop_when_source_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path, _source = self._import(Path(tmpdir))

            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                result = store.read("A", refresh=True)
            finally:
                store.close()

        self.assertFalse(result["markdown_refresh"]["refreshed"])
        self.assertEqual(result["markdown_refresh"]["reason"], "fresh")

    def test_read_refresh_mtime_only_change_updates_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path, source = self._import(Path(tmpdir))
            _bump_mtime(source / "A.md")

            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                first = store.read("A", refresh=True)
                second = store.read("A", refresh=True)
            finally:
                store.close()

        self.assertFalse(first["markdown_refresh"]["refreshed"])
        self.assertEqual(first["markdown_refresh"]["reason"], "content_unchanged")
        self.assertEqual(second["markdown_refresh"]["reason"], "fresh")

    def test_read_refresh_missing_source_file_keeps_cached_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path, source = self._import(Path(tmpdir))
            (source / "A.md").unlink()

            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                result = store.read("A", refresh=True)
            finally:
                store.close()

        self.assertFalse(result["markdown_refresh"]["refreshed"])
        self.assertEqual(result["markdown_refresh"]["reason"], "source_file_missing")
        self.assertEqual([line["text"] for line in result["lines"]], ["# A", "[[B]]", "old line"])

    def test_read_refresh_hydrates_catalog_only_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store_path = root / "store.sqlite"
            source = root / "wiki"
            source.mkdir()
            _write(source / "A.md", "# A\n[[B]]\n")
            _write(source / "B.md", "# B\nbody\n")
            import_markdown_folder_to_sqlite(source, store_path, project_name="wiki", catalog_only=True)

            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                result = store.read("A", refresh=True)
            finally:
                store.close()

        refresh = result["markdown_refresh"]
        self.assertTrue(refresh["refreshed"])
        self.assertEqual(refresh["reason"], "hydrated_source")
        self.assertEqual([line["text"] for line in result["lines"]], ["# A", "[[B]]"])


def result_page_id(store: SQLiteStore) -> str:
    page = store.resolve_page("A")
    assert page is not None
    return page.id


class MarkdownRefreshCliTests(unittest.TestCase):
    def _import_cli(self, root: Path) -> tuple[Path, Path]:
        store_path = root / "store.sqlite"
        source = root / "wiki"
        source.mkdir()
        _write(source / "A.md", "# A\nold line\n")
        self.assertEqual(main(["--store", str(store_path), "import", "--markdown", str(source), "--project", "wiki"]), 0)
        return store_path, source

    def test_cli_read_refresh_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path, source = self._import_cli(Path(tmpdir))
            _write(source / "A.md", "# A\nnew line\n")
            _bump_mtime(source / "A.md")
            exit_code = main(["--store", str(store_path), "--project", "wiki", "read", "A", "--refresh"])
            self.assertEqual(exit_code, 0)

            store = SQLiteStore(store_path, project="wiki")
            try:
                page = store.resolve_page("A")
                lines, _truncated = store.page_lines(page)
            finally:
                store.close()
        self.assertEqual([line.text for line in lines], ["# A", "new line"])

    def test_cli_read_refresh_env_default_and_no_refresh_override(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path, source = self._import_cli(Path(tmpdir))
            _write(source / "A.md", "# A\nenv refreshed\n")
            _bump_mtime(source / "A.md")

            with patch.dict(os.environ, {"GRASP_READ_REFRESH": "1"}):
                self.assertEqual(
                    main(["--store", str(store_path), "--project", "wiki", "read", "A", "--no-refresh"]),
                    0,
                )
                store = SQLiteStore(store_path, project="wiki")
                try:
                    lines, _truncated = store.page_lines(store.resolve_page("A"))
                finally:
                    store.close()
                self.assertEqual([line.text for line in lines], ["# A", "old line"])

                self.assertEqual(main(["--store", str(store_path), "--project", "wiki", "read", "A"]), 0)
                store = SQLiteStore(store_path, project="wiki")
                try:
                    lines, _truncated = store.page_lines(store.resolve_page("A"))
                finally:
                    store.close()
                self.assertEqual([line.text for line in lines], ["# A", "env refreshed"])


if __name__ == "__main__":
    unittest.main()
