import tempfile
import unittest
from pathlib import Path

from grasp.markdown import MarkdownMirror, parse_markdown_links
from grasp.sqlite_store import SQLiteStore, import_markdown_folder_to_sqlite


class MarkdownParsingTests(unittest.TestCase):
    def test_parse_markdown_links_handles_wikilinks_aliases_headings_embeds_and_tags(self):
        text = (
            "[[Page]] [[Page|alias]] [[Folder/Other.md#Heading]] ![[Embed]] "
            "`[[Code]]` `parent wiki` #tag #2024 [anchor](#local) # https://example.com/#fragment"
        )

        self.assertEqual(
            parse_markdown_links(text),
            ["Page", "Page", "Other", "Embed", "tag", "2024"],
        )

    def test_markdown_mirror_skips_fenced_code_links(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text(
                "\n".join(
                    [
                        "# A",
                        "[[B]]",
                        "```",
                        "[[NoEdge]]",
                        "```",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "B.md").write_text("# B\n", encoding="utf-8")

            mirror = MarkdownMirror.from_folder(root)

        self.assertEqual([edge.target_title for edge in mirror.edges], ["B"])


class MarkdownImportTests(unittest.TestCase):
    def test_import_markdown_folder_materializes_graph_without_cross_wiki_backticks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text(
                "\n".join(
                    [
                        "---",
                        "type: note",
                        "sources:",
                        "  - [[B]]",
                        "---",
                        "# A",
                        "links to [[B]] and [[Missing|visible text]] and `ParentWiki`",
                        "tagged #topic",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "B.md").write_text("# B\nlinks back to [[A]]\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            stats = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            self.assertEqual(stats["project"], "wiki")
            self.assertEqual(stats["pages"], 2)
            self.assertEqual(stats["edges"], 5)
            self.assertEqual(stats["unresolved_targets"], 2)

            store = SQLiteStore(store_path, project="wiki")
            try:
                read = store.read("A", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertEqual(read["page"]["title"], "A")
                self.assertEqual(read["backlink_count_total"], 1)
                self.assertEqual(read["backlinks"][0]["source_title"], "B")
                unresolved_titles = {item["title"] for item in read["unresolved_targets"]}
                self.assertEqual(unresolved_titles, {"Missing", "topic"})
                self.assertEqual(store.link_stats("ParentWiki")["link_count"], 0)
            finally:
                store.close()

    def test_duplicate_file_stem_titles_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "one").mkdir()
            (root / "two").mkdir()
            (root / "one" / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "two" / "A.md").write_text("# A\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate Markdown page titles"):
                MarkdownMirror.from_folder(root)


if __name__ == "__main__":
    unittest.main()
