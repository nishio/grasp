import tempfile
import unittest
from pathlib import Path

from grasp.markdown import (
    MarkdownMirror,
    first_markdown_h1_title,
    markdown_graph_role,
    parse_frontmatter,
    parse_markdown_links,
)
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

    def test_parse_frontmatter_reads_title_id_aliases_and_tags(self):
        metadata = parse_frontmatter(
            [
                "---",
                "id: stable-id",
                'title: "Canonical Page"',
                "aliases:",
                "  - Old Page",
                "  - Legacy Page",
                "tags: [graph, '#wiki']",
                "---",
                "# Body",
            ]
        )

        self.assertEqual(metadata.page_id, "stable-id")
        self.assertEqual(metadata.title, "Canonical Page")
        self.assertEqual(metadata.aliases, ["Old Page", "Legacy Page"])
        self.assertEqual(metadata.tags, [("graph", 6), ("wiki", 6)])
        self.assertEqual(metadata.graph_role, "content")

    def test_markdown_graph_role_uses_path_and_frontmatter_hints(self):
        self.assertEqual(markdown_graph_role(Path("index.md"), parse_frontmatter([])), "navigation")
        self.assertEqual(markdown_graph_role(Path("log.md"), parse_frontmatter([])), "log")
        self.assertEqual(markdown_graph_role(Path("maps") / "A.md", parse_frontmatter([])), "navigation")
        self.assertEqual(
            markdown_graph_role(
                Path("A.md"),
                parse_frontmatter(["---", "role: navigation", "---", "# A"]),
            ),
            "navigation",
        )

    def test_first_markdown_h1_title_skips_frontmatter_and_code_fences(self):
        self.assertEqual(
            first_markdown_h1_title(
                [
                    "---",
                    "title: Frontmatter Wins Elsewhere",
                    "---",
                    "```",
                    "# Not A Title",
                    "```",
                    "## Section",
                    "# First H1 #",
                ]
            ),
            "First H1",
        )
        self.assertEqual(first_markdown_h1_title(["# C#"]), "C#")
        self.assertEqual(first_markdown_h1_title(["# C# #"]), "C#")


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

    def test_navigation_and_log_artifacts_are_searchable_but_not_content_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "index.md").write_text("# Index\n[[A]]\n", encoding="utf-8")
            (root / "log.md").write_text("## [2026-06-25 00:00] event | touched [[A]]\n", encoding="utf-8")
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "Source.md").write_text("links to [[A]]\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            stats = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            self.assertEqual(stats["pages"], 4)
            self.assertEqual(stats["edges"], 1)
            self.assertEqual(stats["unresolved_targets"], 0)

            store = SQLiteStore(store_path, project="wiki")
            try:
                read = store.read("A", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertEqual(read["backlink_count_total"], 1)
                self.assertEqual(read["backlinks"][0]["source_title"], "Source")
                hits = store.search("touched", limit=5)
                self.assertEqual([hit["source_title"] for hit in hits], ["log"])
            finally:
                store.close()

    def test_first_h1_is_title_when_frontmatter_title_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "alpha-file.md").write_text(
                "# Alpha Title\nbody\n",
                encoding="utf-8",
            )
            (root / "Source.md").write_text(
                "links to [[Alpha Title]] and [[alpha-file]]\n",
                encoding="utf-8",
            )
            store_path = Path(tmpdir) / "store.sqlite"

            stats = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            self.assertEqual(stats["pages"], 2)
            self.assertEqual(stats["edges"], 2)
            self.assertEqual(stats["unresolved_targets"], 0)

            store = SQLiteStore(store_path, project="wiki")
            try:
                read = store.read("alpha-file", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertEqual(read["page"]["title"], "Alpha Title")
                self.assertEqual(read["backlink_count_total"], 2)
                self.assertEqual(store.link_stats("Alpha Title")["page_exists"], True)
                self.assertEqual(store.link_stats("alpha-file")["title"], "Alpha Title")
            finally:
                store.close()

    def test_frontmatter_title_takes_precedence_over_first_h1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text(
                "\n".join(
                    [
                        "---",
                        "title: Frontmatter Title",
                        "---",
                        "# First H1",
                    ]
                ),
                encoding="utf-8",
            )

            mirror = MarkdownMirror.from_folder(root)

        self.assertEqual(mirror.pages[0].title, "Frontmatter Title")
        self.assertEqual(mirror.title_aliases["a"], "Frontmatter Title")

    def test_reimport_h1_title_change_triggers_full_rebuild(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            page_a = root / "A.md"
            page_a.write_text("# Old Title\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")
            page_a.write_text("# New Title\n", encoding="utf-8")
            result = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            self.assertEqual(result["markdown_import"]["mode"], "full")
            self.assertIn(
                result["markdown_import"]["full_rebuild_reason"],
                {"alias_map_changed", "identity_changed"},
            )

    def test_duplicate_file_stem_titles_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "one").mkdir()
            (root / "two").mkdir()
            (root / "one" / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "two" / "A.md").write_text("# A\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate Markdown page titles"):
                MarkdownMirror.from_folder(root)

    def test_frontmatter_title_id_aliases_and_tags_are_indexed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "canonical-file.md").write_text(
                "\n".join(
                    [
                        "---",
                        "id: stable-page-id",
                        "title: Canonical Page",
                        "aliases:",
                        "  - Old Page",
                        "tags: [graph, '#wiki']",
                        "---",
                        "# Canonical Page",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "Source.md").write_text("links to [[Old Page]] and [[canonical-file]]\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            stats = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            self.assertEqual(stats["pages"], 2)
            self.assertEqual(stats["edges"], 4)
            self.assertEqual(stats["unresolved_targets"], 2)

            store = SQLiteStore(store_path, project="wiki")
            try:
                read_by_alias = store.read("Old Page", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertEqual(read_by_alias["page"]["id"], "stable-page-id")
                self.assertEqual(read_by_alias["page"]["title"], "Canonical Page")
                self.assertEqual(read_by_alias["backlink_count_total"], 2)
                self.assertEqual(
                    {edge["target_title"] for edge in read_by_alias["backlinks"]},
                    {"Canonical Page"},
                )
                self.assertEqual(store.link_stats("canonical-file")["title"], "Canonical Page")
                unresolved_titles = {item["title"] for item in read_by_alias["unresolved_targets"]}
                self.assertEqual(unresolved_titles, {"graph", "wiki"})
            finally:
                store.close()

    def test_alias_collision_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text(
                "\n".join(["---", "aliases: [Shared]", "---", "# A"]),
                encoding="utf-8",
            )
            (root / "B.md").write_text(
                "\n".join(["---", "aliases: [Shared]", "---", "# B"]),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "duplicate Markdown page aliases"):
                MarkdownMirror.from_folder(root)

    def test_reimport_updates_content_only_changes_incrementally(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            page_a = root / "A.md"
            page_a.write_text("# A\nlinks to [[B]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            first = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")
            page_a.write_text("# A\nlinks to [[B]] and [[Missing]]\n", encoding="utf-8")
            second = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            self.assertEqual(first["markdown_import"]["mode"], "full")
            self.assertEqual(second["markdown_import"]["mode"], "incremental")
            self.assertEqual(second["markdown_import"]["changed_files"], 1)
            self.assertEqual(second["edges"], 2)
            self.assertEqual(second["unresolved_targets"], 1)

            store = SQLiteStore(store_path, project="wiki")
            try:
                read = store.read("A", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertEqual({item["title"] for item in read["unresolved_targets"]}, {"Missing"})
            finally:
                store.close()

    def test_reimport_falls_back_to_full_when_alias_map_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            page_a = root / "A.md"
            page_a.write_text(
                "\n".join(["---", "aliases: [Old A]", "---", "# A"]),
                encoding="utf-8",
            )
            (root / "Source.md").write_text("links to [[Old A]]\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")
            page_a.write_text(
                "\n".join(["---", "aliases: [New A]", "---", "# A"]),
                encoding="utf-8",
            )
            result = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            self.assertEqual(result["markdown_import"]["mode"], "full")
            self.assertEqual(result["markdown_import"]["full_rebuild_reason"], "alias_map_changed")
            self.assertEqual(result["unresolved_targets"], 1)

            store = SQLiteStore(store_path, project="wiki")
            try:
                self.assertEqual(store.link_stats("Old A")["link_count"], 1)
                self.assertFalse(store.link_stats("Old A")["page_exists"])
                self.assertTrue(store.link_stats("New A")["page_exists"])
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
