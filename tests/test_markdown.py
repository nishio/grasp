import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import grasp.sqlite_store as sqlite_store
from grasp.cli import (
    format_ambiguities,
    format_backlinks,
    format_cross_project_spread,
    format_cross_project_spreads,
    format_related_result,
)
from grasp.markdown import (
    MarkdownCollisionError,
    MarkdownMirror,
    first_markdown_h1_title,
    markdown_graph_role,
    markdown_page_id,
    markdown_projection_text,
    parse_frontmatter,
    parse_markdown_links,
)
from grasp.sqlite_store import SQLiteStore, import_markdown_folder_to_sqlite


class MarkdownParsingTests(unittest.TestCase):
    def test_parse_markdown_links_handles_wikilinks_aliases_headings_embeds_and_tags(self):
        text = (
            "[[Page]] [[Page|alias]] [[Folder/Other.md#Heading]] ![[Embed]] "
            "[heading](Folder/Std.md#Heading) [block](Block.md#^block-id) "
            "[encoded](Space%20Page.md) [remote](https://example.com/Remote.md) "
            "![image](Image.md) `[[Code]]` `parent wiki` #tag #2024 [anchor](#local) # https://example.com/#fragment"
        )

        self.assertEqual(
            parse_markdown_links(text),
            ["Page", "Page", "Other", "Embed", "Std", "Block", "Space Page", "tag", "2024"],
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

    def test_markdown_mirror_materializes_relative_markdown_links_as_page_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            notes = root / "notes"
            notes.mkdir()
            (root / "A.md").write_text(
                "# A\n"
                "[heading](B.md#Section) [block](notes/C.md#^block-id) "
                "[remote](https://example.com/D.md) [local](#section)\n",
                encoding="utf-8",
            )
            (root / "B.md").write_text("# B\n## Section\n", encoding="utf-8")
            (notes / "C.md").write_text("# C\nblock target ^block-id\n", encoding="utf-8")

            mirror = MarkdownMirror.from_folder(root)

        edges_by_target = {edge.target_title: edge for edge in mirror.edges}
        self.assertEqual(set(edges_by_target), {"B", "C"})
        self.assertIn("[heading](B.md#Section)", edges_by_target["B"].line_text)
        self.assertIn("[block](notes/C.md#^block-id)", edges_by_target["C"].line_text)
        self.assertEqual(edges_by_target["B"].target_fragment, "Section")
        self.assertEqual(edges_by_target["B"].target_line_id, f"{markdown_page_id(Path('B.md'))}:1")
        self.assertEqual(edges_by_target["C"].target_fragment, "^block-id")
        self.assertEqual(edges_by_target["C"].target_line_id, f"{markdown_page_id(Path('notes') / 'C.md')}:1")

    def test_markdown_mirror_materializes_resolved_local_anchor_as_self_line_edge(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text("# A\n## Section\n[local](#Section)\n[missing](#Missing)\n", encoding="utf-8")

            mirror = MarkdownMirror.from_folder(root)

        self.assertEqual(len(mirror.edges), 1)
        edge = mirror.edges[0]
        self.assertEqual(edge.target_title, "A")
        self.assertEqual(edge.target_fragment, "Section")
        self.assertEqual(edge.target_line_id, f"{markdown_page_id(Path('A.md'))}:1")

    def test_markdown_import_persists_target_line_ids_for_anchor_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store_path = root / "store.sqlite"
            source = root / "wiki"
            source.mkdir()
            (source / "A.md").write_text("# A\n[heading](B.md#Section)\n[block](C.md#^block-id)\n", encoding="utf-8")
            (source / "B.md").write_text("# B\n## Section\n", encoding="utf-8")
            (source / "C.md").write_text("# C\nblock target ^block-id\n", encoding="utf-8")

            import_markdown_folder_to_sqlite(source, store_path)
            store = SQLiteStore(store_path, project="wiki")
            try:
                b_backlinks = store.backlinks_report("B")
                c_backlinks = store.backlinks_report("C")
            finally:
                store.close()

        self.assertEqual(b_backlinks["backlinks"][0]["target_fragment"], "Section")
        self.assertEqual(b_backlinks["backlinks"][0]["target_line_id"], f"{markdown_page_id(Path('B.md'))}:1")
        self.assertEqual(c_backlinks["backlinks"][0]["target_fragment"], "^block-id")
        self.assertEqual(c_backlinks["backlinks"][0]["target_line_id"], f"{markdown_page_id(Path('C.md'))}:1")

    def test_markdown_incremental_import_keeps_target_line_ids_stable_across_insertion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store_path = root / "store.sqlite"
            source = root / "wiki"
            source.mkdir()
            (source / "A.md").write_text("# A\n[heading](B.md#Section)\n", encoding="utf-8")
            (source / "B.md").write_text("# B\n## Section\n", encoding="utf-8")

            import_markdown_folder_to_sqlite(source, store_path)
            old_target_line_id = f"{markdown_page_id(Path('B.md'))}:1"
            (source / "B.md").write_text("# B\nintro\n## Section\n", encoding="utf-8")
            import_markdown_folder_to_sqlite(source, store_path)
            store = SQLiteStore(store_path, project="wiki")
            try:
                backlinks = store.backlinks_report("B")
                page = store.resolve_page("B")
                lines, _aliases = store.page_lines(page)
            finally:
                store.close()

        self.assertEqual(backlinks["backlinks"][0]["target_fragment"], "Section")
        self.assertEqual(backlinks["backlinks"][0]["target_line_id"], old_target_line_id)
        self.assertEqual(lines[2].text, "## Section")
        self.assertEqual(lines[2].line_id, old_target_line_id)

    def test_markdown_write_page_persists_target_fragments_for_anchor_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store_path = root / "store.sqlite"
            source = root / "wiki"
            source.mkdir()
            (source / "A.md").write_text("# A\nold\n", encoding="utf-8")
            (source / "B.md").write_text(
                "# B\n## API: Overview!\n## Repeat Heading?\n## Repeat Heading?\n",
                encoding="utf-8",
            )

            import_markdown_folder_to_sqlite(source, store_path)
            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                update_result, _ = store.write_markdown_page_with_event(
                    "A",
                    lines=[
                        "# A",
                        "[slug](B.md#api-overview)",
                        "[duplicate](B.md#repeat-heading-1)",
                        "[local](#Section)",
                        "[missing](#Missing)",
                        "## Section",
                    ],
                )
                b_backlinks = store.backlinks_report("B")
                a_backlinks = store.backlinks_report("A")
            finally:
                store.close()

        edges_by_fragment = {edge["target_fragment"]: edge for edge in b_backlinks["backlinks"]}
        self.assertEqual(edges_by_fragment["api-overview"]["target_line_id"], f"{markdown_page_id(Path('B.md'))}:1")
        self.assertEqual(edges_by_fragment["repeat-heading-1"]["target_line_id"], f"{markdown_page_id(Path('B.md'))}:3")
        section_line = next(line for line in update_result["lines"] if line["text"] == "## Section")
        local_edges = [edge for edge in a_backlinks["backlinks"] if edge.get("target_fragment") == "Section"]
        self.assertEqual(len(local_edges), 1)
        self.assertEqual(local_edges[0]["target_line_id"], section_line["line_id"])
        self.assertNotIn("Missing", {edge.get("target_fragment") for edge in a_backlinks["backlinks"]})

    def test_markdown_write_page_create_persists_target_fragments_for_anchor_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store_path = root / "store.sqlite"
            source = root / "wiki"
            source.mkdir()
            (source / "B.md").write_text("# B\n## Section\n", encoding="utf-8")

            import_markdown_folder_to_sqlite(source, store_path)
            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                create_result, _ = store.write_markdown_page_with_event(
                    "New",
                    create=True,
                    source_path="New.md",
                    lines=[
                        "# New",
                        "[heading](B.md#Section)",
                        "## Local",
                        "[local](#Local)",
                        "[missing](#Missing)",
                    ],
                )
                b_backlinks = store.backlinks_report("B")
                new_backlinks = store.backlinks_report("New")
            finally:
                store.close()

        self.assertEqual(b_backlinks["backlinks"][0]["target_fragment"], "Section")
        self.assertEqual(b_backlinks["backlinks"][0]["target_line_id"], f"{markdown_page_id(Path('B.md'))}:1")
        local_line = next(line for line in create_result["lines"] if line["text"] == "## Local")
        local_edges = [edge for edge in new_backlinks["backlinks"] if edge.get("target_fragment") == "Local"]
        self.assertEqual(len(local_edges), 1)
        self.assertEqual(local_edges[0]["target_line_id"], local_line["line_id"])
        self.assertNotIn("Missing", {edge.get("target_fragment") for edge in new_backlinks["backlinks"]})

    def test_markdown_append_persists_target_fragments_for_anchor_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store_path = root / "store.sqlite"
            source = root / "wiki"
            source.mkdir()
            (source / "A.md").write_text("# A\n## Existing\n", encoding="utf-8")
            (source / "B.md").write_text("# B\n## Section\n", encoding="utf-8")

            import_markdown_folder_to_sqlite(source, store_path)
            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                store.append_markdown_lines(
                    "A",
                    [
                        "[heading](B.md#Section)",
                        "[local](#Existing)",
                        "[missing](#Missing)",
                    ],
                )
                b_backlinks = store.backlinks_report("B")
                a_backlinks = store.backlinks_report("A")
            finally:
                store.close()

        self.assertEqual(b_backlinks["backlinks"][0]["target_fragment"], "Section")
        self.assertEqual(b_backlinks["backlinks"][0]["target_line_id"], f"{markdown_page_id(Path('B.md'))}:1")
        local_edges = [edge for edge in a_backlinks["backlinks"] if edge.get("target_fragment") == "Existing"]
        self.assertEqual(len(local_edges), 1)
        self.assertEqual(local_edges[0]["target_line_id"], f"{markdown_page_id(Path('A.md'))}:1")
        self.assertNotIn("Missing", {edge.get("target_fragment") for edge in a_backlinks["backlinks"]})

    def test_markdown_heading_anchors_match_github_style_slugs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text(
                "# A\n"
                "[slug](B.md#api-overview)\n"
                "[duplicate](B.md#repeat-heading-1)\n",
                encoding="utf-8",
            )
            (root / "B.md").write_text(
                "# B\n"
                "## API: Overview!\n"
                "## Repeat Heading?\n"
                "## Repeat Heading?\n",
                encoding="utf-8",
            )

            mirror = MarkdownMirror.from_folder(root)

        edges_by_fragment = {edge.target_fragment: edge for edge in mirror.edges}
        self.assertEqual(edges_by_fragment["api-overview"].target_line_id, f"{markdown_page_id(Path('B.md'))}:1")
        self.assertEqual(edges_by_fragment["repeat-heading-1"].target_line_id, f"{markdown_page_id(Path('B.md'))}:3")

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
        self.assertEqual(markdown_graph_role(Path("source") / "Digest.md", parse_frontmatter([])), "source")
        self.assertEqual(markdown_graph_role(Path("drafts") / "Draft.md", parse_frontmatter([])), "artifact")
        self.assertEqual(
            markdown_graph_role(
                Path("A.md"),
                parse_frontmatter(["---", "role: navigation", "---", "# A"]),
            ),
            "navigation",
        )
        self.assertEqual(
            markdown_graph_role(
                Path("A.md"),
                parse_frontmatter(["---", "type: source", "---", "# A"]),
            ),
            "source",
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

    def test_projection_frontmatter_persists_rename_identity_only_when_needed(self):
        path_id = markdown_page_id(Path("New.md"))
        self.assertEqual(
            markdown_projection_text(
                "New.md",
                page_id=path_id,
                title="New",
                aliases=["New"],
                lines=["# New", "body"],
            ),
            "# New\nbody\n",
        )
        self.assertEqual(
            markdown_projection_text(
                "New.md",
                page_id=path_id,
                title="Renamed",
                aliases=["New"],
                lines=["# Renamed", "body"],
            ),
            "# Renamed\nbody\n",
        )
        self.assertEqual(
            markdown_projection_text(
                "New.md",
                page_id=path_id,
                title="New",
                aliases=["Old"],
                lines=["# New", "body"],
            ),
            "\n".join(
                [
                    "---",
                    f"id: {path_id}",
                    "title: New",
                    "aliases:",
                    "  - Old",
                    "---",
                    "# New",
                    "body",
                    "",
                ]
            ),
        )
        self.assertEqual(
            markdown_projection_text(
                "New.md",
                page_id="old-stable-id",
                title="New",
                aliases=["Old"],
                lines=["# New", "body"],
            ),
            "\n".join(
                [
                    "---",
                    "id: old-stable-id",
                    "title: New",
                    "aliases:",
                    "  - Old",
                    "---",
                    "# New",
                    "body",
                    "",
                ]
            ),
        )
        existing = ["---", "id: old-stable-id", "title: New", "aliases:", "  - Old", "---", "# New"]
        self.assertEqual(
            markdown_projection_text(
                "New.md",
                page_id="old-stable-id",
                title="New",
                aliases=["Old"],
                lines=existing,
            ),
            "\n".join([*existing, ""]),
        )

    def test_projection_frontmatter_merges_identity_fields_into_existing_metadata(self):
        self.assertEqual(
            markdown_projection_text(
                "Renamed.md",
                page_id="old-stable-id",
                title="Renamed",
                aliases=["Old"],
                lines=[
                    "---",
                    "type: decision",
                    "summary: keep this",
                    "sources:",
                    "  - raw/session.md",
                    "id: stale-id",
                    "title: Stale",
                    "alias: Stale Alias",
                    "aliases:",
                    "  - Another Stale Alias",
                    "# preserve this comment",
                    "",
                    "---",
                    "# Renamed",
                    "body",
                ],
            ),
            "\n".join(
                [
                    "---",
                    "type: decision",
                    "summary: keep this",
                    "sources:",
                    "  - raw/session.md",
                    "# preserve this comment",
                    "",
                    "id: old-stable-id",
                    "title: Renamed",
                    "aliases:",
                    "  - Old",
                    "---",
                    "# Renamed",
                    "body",
                    "",
                ]
            ),
        )


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
            (root / "source").mkdir()
            (root / "source" / "Digest.md").write_text("# Digest\nsource-backed [[A]]\n", encoding="utf-8")
            (root / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "Source.md").write_text("links to [[A]]\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            stats = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            self.assertEqual(stats["pages"], 5)
            self.assertEqual(stats["edges"], 2)
            self.assertEqual(stats["unresolved_targets"], 0)

            store = SQLiteStore(store_path, project="wiki")
            try:
                read = store.read("A", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertEqual(read["backlink_count_total"], 2)
                self.assertEqual(
                    {backlink["source_title"] for backlink in read["backlinks"]},
                    {"Digest", "Source"},
                )
                hits = store.search("touched", limit=5)
                self.assertEqual([hit["source_title"] for hit in hits], ["log"])
            finally:
                store.close()

    def test_markdown_import_excludes_named_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text("# A\nlinks to [[B]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            (root / "raw").mkdir()
            (root / "raw" / "Raw.md").write_text("# Raw\nraw-only links to [[A]]\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            first = import_markdown_folder_to_sqlite(
                root,
                store_path,
                project_name="wiki",
                exclude_dirs=("raw",),
            )

            self.assertEqual(first["pages"], 2)
            self.assertEqual(first["edges"], 1)

            store = SQLiteStore(store_path, project="wiki")
            try:
                self.assertEqual(store.search("raw-only", limit=5), [])
                self.assertEqual(store.link_stats("A")["link_count"], 0)
            finally:
                store.close()

            second = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            self.assertEqual(second["markdown_import"]["mode"], "full")
            self.assertEqual(second["markdown_import"]["full_rebuild_reason"], "identity_changed")
            self.assertEqual(second["pages"], 3)
            self.assertEqual(second["edges"], 2)

            store = SQLiteStore(store_path, project="wiki")
            try:
                self.assertEqual([hit["source_title"] for hit in store.search("raw-only", limit=5)], ["Raw"])
                self.assertEqual(store.link_stats("A")["link_count"], 1)
            finally:
                store.close()

    def test_markdown_exclude_dir_rejects_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text("# A\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "directory basename"):
                MarkdownMirror.from_folder(root, exclude_dirs=("raw/private",))

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

    def test_duplicate_file_stem_titles_import_as_ambiguous_handles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "one").mkdir()
            (root / "two").mkdir()
            (root / "one" / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "two" / "A.md").write_text("# A\n", encoding="utf-8")
            (root / "Source.md").write_text("links to [[A]]\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            stats = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            self.assertEqual(stats["pages"], 3)
            self.assertEqual(stats["edges"], 1)
            self.assertEqual(stats["unresolved_targets"], 0)

            store = SQLiteStore(store_path, project="wiki")
            try:
                read = store.read("A")
                self.assertIsNone(read["page"])
                self.assertEqual(read["ambiguity"]["type"], "handle_ambiguity")
                self.assertEqual(read["ambiguity"]["candidate_count"], 2)
                self.assertEqual(
                    {candidate["path"] for candidate in read["ambiguity"]["candidates"]},
                    {"one/A.md", "two/A.md"},
                )
                source = store.read("Source", unresolved_limit=10)
                self.assertEqual(source["unresolved_targets"], [])
            finally:
                store.close()

    def test_duplicate_frontmatter_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text("---\nid: same-id\n---\n# A\n", encoding="utf-8")
            (root / "B.md").write_text("---\nid: same-id\n---\n# B\n", encoding="utf-8")

            with self.assertRaisesRegex(MarkdownCollisionError, "duplicate Markdown page ids") as caught:
                MarkdownMirror.from_folder(root)

            diagnostic = caught.exception.to_diagnostic()
            self.assertEqual(diagnostic["collision_counts"], {"id": 1})
            self.assertEqual(diagnostic["collisions"][0]["kind"], "id")

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

    def test_alias_collision_imports_as_ambiguous_handle(self):
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
            (root / "Source.md").write_text("links to [[Shared]]\n", encoding="utf-8")
            (root / "Direct.md").write_text("links to [[A]] and [[B]]\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            stats = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            self.assertEqual(stats["pages"], 4)
            self.assertEqual(stats["edges"], 3)
            self.assertEqual(stats["unresolved_targets"], 0)

            store = SQLiteStore(store_path, project="wiki")
            try:
                read = store.read("Shared")
                self.assertIsNone(read["page"])
                self.assertEqual(read["ambiguity"]["type"], "handle_ambiguity")
                self.assertEqual(read["ambiguity"]["candidate_count"], 2)
                candidates = {candidate["title"] for candidate in read["ambiguity"]["candidates"]}
                self.assertEqual(candidates, {"A", "B"})
                edge = store.backlinks_by_norm_query("shared")[0]
                self.assertEqual(edge.resolution_status, "ambiguous")
                self.assertIsNone(edge.target_page_id)
                link_stats = store.link_stats("Shared")
                self.assertEqual(link_stats["ambiguity"]["candidate_count"], 2)
                self.assertIsNone(link_stats["recovery_hints"])
                backlinks = store.backlinks("Shared", limit=10)
                self.assertEqual([edge.source_title for edge in backlinks], ["Source"])
                self.assertEqual(backlinks[0].resolution_status, "ambiguous")

                report = store.backlinks_report("Shared", limit=10)
                self.assertEqual(report["resolution_status"], "ambiguous")
                self.assertEqual(report["handle_backlinks"]["count_total"], 1)
                self.assertEqual(report["handle_backlinks"]["items"][0]["source_title"], "Source")
                candidate_counts = {
                    item["candidate"]["title"]: item["count_total"]
                    for item in report["candidate_backlinks"]
                }
                self.assertEqual(candidate_counts, {"A": 1, "B": 1})
                candidate_sources = {
                    item["candidate"]["title"]: {
                        edge["source_title"]
                        for edge in item["resolved_backlinks"]
                    }
                    for item in report["candidate_backlinks"]
                }
                self.assertEqual(candidate_sources, {"A": {"Direct"}, "B": {"Direct"}})
                text = format_backlinks(report)
                self.assertIn("resolution: ambiguous (2 candidates)", text)
                self.assertIn("## Incoming links to ambiguous handle", text)
                self.assertIn("resolved_backlinks=1", text)

                related_report = store.related_report("Shared", limit=10)
                self.assertEqual(related_report["resolution_status"], "ambiguous")
                self.assertEqual(related_report["ambiguity"]["candidate_count"], 2)
                self.assertEqual(
                    [(item["title"], item["relation"]) for item in related_report["related"]],
                    [("Source", "ambiguous-handle-source")],
                )
                candidate_related = {
                    item["candidate"]["title"]: [related["title"] for related in item["related"]]
                    for item in related_report["candidate_related"]
                }
                self.assertEqual(candidate_related, {"A": ["B"], "B": ["A"]})
                related_text = format_related_result(related_report)
                self.assertIn("resolution: ambiguous (2 candidates)", related_text)
                self.assertIn("## Source pages linking to ambiguous handle", related_text)
                self.assertIn("related=1", related_text)

                ambiguities = store.ambiguities(limit=10, candidate_limit=1)
                self.assertEqual(ambiguities["scope"], "project")
                self.assertEqual(ambiguities["handle_count"], 1)
                self.assertEqual(ambiguities["projects"][0]["ambiguous_handle_count"], 1)
                ambiguity = ambiguities["ambiguities"][0]
                self.assertEqual(ambiguity["handle"], "Shared")
                self.assertEqual(ambiguity["candidate_count"], 2)
                self.assertEqual(ambiguity["candidates_returned"], 1)
                self.assertTrue(ambiguity["candidates_truncated"])
                self.assertEqual(ambiguity["ambiguous_link_count"], 1)
                ambiguity_text = format_ambiguities(ambiguities)
                self.assertIn("# Ambiguous Handles", ambiguity_text)
                self.assertIn("handles=1", ambiguity_text)
            finally:
                store.close()

    def test_ambiguities_defaults_to_all_projects(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            store_path = base / "store.sqlite"
            for project in ("one", "two"):
                root = base / project
                root.mkdir()
                (root / "A.md").write_text(
                    "\n".join(["---", "aliases: [Shared]", "---", f"# {project} A"]),
                    encoding="utf-8",
                )
                (root / "B.md").write_text(
                    "\n".join(["---", "aliases: [Shared]", "---", f"# {project} B"]),
                    encoding="utf-8",
                )
                (root / "Source.md").write_text("links to [[Shared]]\n", encoding="utf-8")
                import_markdown_folder_to_sqlite(root, store_path, project_name=project)

            store = SQLiteStore(store_path)
            try:
                report = store.ambiguities(limit=10, candidate_limit=2)
                self.assertEqual(report["scope"], "all-projects")
                self.assertEqual(report["project_count"], 2)
                self.assertEqual(report["handle_count"], 2)
                self.assertEqual({item["project"] for item in report["ambiguities"]}, {"one", "two"})
                self.assertEqual(
                    {project["project"]: project["ambiguous_link_count"] for project in report["projects"]},
                    {"one": 1, "two": 1},
                )
            finally:
                store.close()

    def test_cross_project_spread_reports_weak_normalized_title_signal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            store_path = base / "store.sqlite"

            one = base / "one"
            one.mkdir()
            (one / "A.md").write_text("---\naliases: [Shared]\n---\n# A\n", encoding="utf-8")
            (one / "Overview.md").write_text("# Overview\n", encoding="utf-8")
            (one / "Source.md").write_text("links to [[Shared]] and [[1]]\n", encoding="utf-8")
            import_markdown_folder_to_sqlite(one, store_path, project_name="one")

            two = base / "two"
            two.mkdir()
            (two / "A.md").write_text("---\naliases: [Shared]\n---\n# A\n", encoding="utf-8")
            (two / "B.md").write_text("---\naliases: [Shared]\n---\n# B\n", encoding="utf-8")
            (two / "Overview.md").write_text("# Overview\n", encoding="utf-8")
            (two / "Source.md").write_text("links to [[Shared]] and [[1]]\n", encoding="utf-8")
            import_markdown_folder_to_sqlite(two, store_path, project_name="two")

            three = base / "three"
            three.mkdir()
            (three / "Overview.md").write_text("# Overview\n", encoding="utf-8")
            (three / "Source.md").write_text("links to [[Shared]] and [[1]]\n", encoding="utf-8")
            import_markdown_folder_to_sqlite(three, store_path, project_name="three")

            store = SQLiteStore(store_path)
            try:
                spread = store.cross_project_spread("Shared", limit=10, candidate_limit=1)
                self.assertEqual(spread["scope"], "all-projects")
                self.assertEqual(spread["connection_strength"], "weak-normalized-title")
                self.assertEqual(spread["project_count"], 3)
                self.assertEqual(spread["signal_project_count"], 3)
                self.assertEqual(spread["totals"]["materialized_project_count"], 2)
                self.assertEqual(spread["totals"]["ambiguous_project_count"], 1)
                self.assertEqual(spread["totals"]["unresolved_project_count"], 1)
                self.assertEqual(
                    spread["totals"]["resolution_counts"],
                    {"resolved_unique": 1, "ambiguous": 1, "unresolved": 1},
                )
                projects = {item["project"]: item for item in spread["projects"]}
                self.assertEqual(projects["one"]["materialized"]["candidate_count"], 1)
                self.assertEqual(projects["two"]["materialized"]["candidate_count"], 2)
                self.assertTrue(projects["two"]["materialized"]["candidates_truncated"])
                self.assertEqual(projects["three"]["unresolved"]["link_count"], 1)
                text = format_cross_project_spread(spread)
                self.assertIn("# Cross-project spread: Shared", text)
                self.assertIn("connection_strength: weak-normalized-title", text)
                self.assertIn("ambiguous_projects=1", text)

                spreads = store.cross_project_spreads(limit=10, project_limit=2, candidate_limit=0)
                self.assertEqual(spreads["scope"], "all-projects")
                self.assertEqual(spreads["connection_strength"], "weak-normalized-title")
                self.assertEqual(spreads["spreads"][0]["handle_norm"], "shared")
                self.assertEqual(spreads["spreads"][0]["rank_band"], "concept-like")
                self.assertEqual(spreads["spreads"][0]["project_spread"], 3)
                self.assertEqual(spreads["spreads"][0]["project_samples_returned"], 2)
                numeric = next(item for item in spreads["spreads"] if item["handle_norm"] == "1")
                self.assertEqual(numeric["rank_band"], "numeric-only")
                self.assertEqual(numeric["project_spread"], 3)
                overview = next(item for item in spreads["spreads"] if item["handle_norm"] == "overview")
                self.assertEqual(overview["rank_band"], "structural-name")
                ranked_text = format_cross_project_spreads(spreads)
                self.assertIn("# Cross-project spreads", ranked_text)
                self.assertIn("Shared (shared): spread=3, band=concept-like", ranked_text)
            finally:
                store.close()

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

    def test_reimport_content_only_change_uses_changed_file_fast_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            page_a = root / "A.md"
            page_a.write_text("# A\nlinks to [[B]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")
            page_a.write_text("# A\nlinks to [[B]] and [[Missing]]\n", encoding="utf-8")

            with patch(
                "grasp.sqlite_store.MarkdownMirror.from_folder",
                side_effect=AssertionError("content-only reimport should not build a full MarkdownMirror"),
            ):
                result = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            self.assertEqual(result["markdown_import"]["mode"], "incremental")
            self.assertEqual(result["markdown_import"]["changed_files"], 1)
            self.assertEqual(result["markdown_import"]["fast_path"], "manifest_hash_changed_files")
            self.assertEqual(result["markdown_import"]["scanned_files"], 2)
            self.assertEqual(result["markdown_import"]["parsed_files"], 1)
            self.assertEqual(result["edges"], 2)
            self.assertEqual(result["unresolved_targets"], 1)

            store = SQLiteStore(store_path, project="wiki")
            try:
                read = store.read("A", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertEqual({item["title"] for item in read["unresolved_targets"]}, {"Missing"})
            finally:
                store.close()

    def test_reimport_inherits_line_ids_across_inserted_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            page_a = root / "A.md"
            page_a.write_text("# A\nalpha\nbeta\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")
            store = SQLiteStore(store_path, project="wiki")
            try:
                page = store.resolve_page("A")
                old_lines, _aliases = store.page_lines(page)
            finally:
                store.close()

            page_a.write_text("# A\ninserted\nalpha\nbeta\n", encoding="utf-8")
            result = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            self.assertEqual(result["markdown_import"]["mode"], "incremental")
            self.assertEqual(result["markdown_import"]["fast_path"], "manifest_hash_changed_files")

            store = SQLiteStore(store_path, project="wiki")
            try:
                page = store.resolve_page("A")
                new_lines, _aliases = store.page_lines(page)
            finally:
                store.close()

            self.assertEqual([line.text for line in new_lines], ["# A", "inserted", "alpha", "beta"])
            self.assertEqual(new_lines[0].line_id, old_lines[0].line_id)
            self.assertEqual(new_lines[2].line_id, old_lines[1].line_id)
            self.assertEqual(new_lines[3].line_id, old_lines[2].line_id)
            self.assertNotIn(new_lines[1].line_id, {line.line_id for line in old_lines})
            self.assertEqual(len({line.line_id for line in new_lines}), len(new_lines))

    def test_reimport_full_parse_incremental_path_inherits_line_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            page_a = root / "A.md"
            page_a.write_text("# A\nalpha\nbeta\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")
            store = SQLiteStore(store_path, project="wiki")
            try:
                page = store.resolve_page("A")
                old_lines, _aliases = store.page_lines(page)
            finally:
                store.close()

            page_a.write_text("# A\ninserted\nalpha\nbeta\n", encoding="utf-8")
            with patch("grasp.sqlite_store._try_fast_changed_markdown_import", return_value=None):
                result = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            self.assertEqual(result["markdown_import"]["mode"], "incremental")
            self.assertNotIn("fast_path", result["markdown_import"])

            store = SQLiteStore(store_path, project="wiki")
            try:
                page = store.resolve_page("A")
                new_lines, _aliases = store.page_lines(page)
            finally:
                store.close()

            self.assertEqual(new_lines[0].line_id, old_lines[0].line_id)
            self.assertEqual(new_lines[2].line_id, old_lines[1].line_id)
            self.assertEqual(new_lines[3].line_id, old_lines[2].line_id)
            self.assertEqual(len({line.line_id for line in new_lines}), len(new_lines))

    def test_reimport_remaps_self_anchor_target_line_ids_after_insertion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            page_a = root / "A.md"
            page_a.write_text("# A\n## Target\n[[#Target]]\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")
            store = SQLiteStore(store_path, project="wiki")
            try:
                page = store.resolve_page("A")
                old_lines, _aliases = store.page_lines(page)
                old_heading_id = old_lines[1].line_id
                old_link_id = old_lines[2].line_id
            finally:
                store.close()

            page_a.write_text("# A\ninserted\n## Target\n[[#Target]]\n", encoding="utf-8")
            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            store = SQLiteStore(store_path, project="wiki")
            try:
                page = store.resolve_page("A")
                edge = store.connection.execute(
                    """
                    SELECT e.line_id, l.line_index, e.target_line_id
                    FROM edges e
                    JOIN lines l ON l.project = e.project AND l.line_id = e.line_id
                    WHERE e.project = ? AND e.source_page_id = ? AND e.target_fragment = ?
                    """,
                    ("wiki", page.id, "Target"),
                ).fetchone()
            finally:
                store.close()

            self.assertIsNotNone(edge)
            self.assertEqual(edge[0], old_link_id)
            self.assertEqual(edge[1], 3)
            self.assertEqual(edge[2], old_heading_id)

    def test_write_page_inherits_line_ids_across_inserted_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            page_a = root / "A.md"
            page_a.write_text("# A\n## Target\n[[#Target]]\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")
            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                page = store.resolve_page("A")
                old_lines, _aliases = store.page_lines(page)
                old_heading_id = old_lines[1].line_id
                old_link_id = old_lines[2].line_id

                store.write_markdown_page_with_event(
                    "A",
                    lines=["# A", "inserted", "## Target", "[[#Target]]"],
                    actor="test",
                    session_id="write-page-line-id-test",
                )
                new_page = store.resolve_page("A")
                new_lines, _aliases = store.page_lines(new_page)
                edge = store.connection.execute(
                    """
                    SELECT e.line_id, l.line_index, e.target_line_id
                    FROM edges e
                    JOIN lines l ON l.project = e.project AND l.line_id = e.line_id
                    WHERE e.project = ? AND e.source_page_id = ? AND e.target_fragment = ?
                    """,
                    ("wiki", new_page.id, "Target"),
                ).fetchone()
            finally:
                store.close()

            self.assertEqual([line.text for line in new_lines], ["# A", "inserted", "## Target", "[[#Target]]"])
            self.assertEqual(new_lines[0].line_id, old_lines[0].line_id)
            self.assertEqual(new_lines[2].line_id, old_heading_id)
            self.assertEqual(new_lines[3].line_id, old_link_id)
            self.assertNotIn(new_lines[1].line_id, {line.line_id for line in old_lines})
            self.assertEqual(len({line.line_id for line in new_lines}), len(new_lines))
            self.assertIsNotNone(edge)
            self.assertEqual(edge[0], old_link_id)
            self.assertEqual(edge[1], 3)
            self.assertEqual(edge[2], old_heading_id)

    def test_catalog_only_import_marks_markdown_graph_incomplete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text("# Alpha\nlinks to [[B]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            with patch(
                "grasp.sqlite_store.MarkdownMirror.from_folder",
                side_effect=AssertionError("catalog-only import should not build a MarkdownMirror"),
            ):
                result = import_markdown_folder_to_sqlite(
                    root,
                    store_path,
                    project_name="wiki",
                    catalog_only=True,
                )

            self.assertEqual(result["markdown_import"]["mode"], "catalog")
            self.assertEqual(result["markdown_import"]["graph_complete"], False)
            self.assertEqual(result["markdown_import"]["parsed_files"], 0)
            self.assertEqual(result["markdown_import"]["identity_source"], "path")
            self.assertEqual(result["markdown_graph"]["complete"], False)
            self.assertEqual(result["markdown_graph"]["mode"], "catalog-only")
            self.assertEqual(result["markdown_graph"]["hydrated_files"], 0)
            self.assertEqual(result["markdown_graph"]["total_files"], 2)
            self.assertEqual(result["pages"], 2)
            self.assertEqual(result["lines"], 0)
            self.assertEqual(result["edges"], 0)

            store = SQLiteStore(store_path, project="wiki")
            try:
                stats = store.stats()
                self.assertEqual(stats["markdown_graph"]["complete"], False)
                read = store.read("A", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertEqual(read["page"]["title"], "A")
                self.assertEqual(read["markdown_graph"]["complete"], False)
                self.assertEqual(read["lines"], [])
                self.assertEqual(read["backlink_count_total"], 0)
                self.assertEqual(store.link_stats("B")["link_count"], 0)
            finally:
                store.close()

            hydrated = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")
            self.assertEqual(hydrated["markdown_graph"]["complete"], True)
            self.assertEqual(hydrated["lines"], 3)
            self.assertEqual(hydrated["edges"], 1)
            store = SQLiteStore(store_path, project="wiki")
            try:
                hydrated_read = store.read("A", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertEqual(hydrated_read["page"]["title"], "Alpha")
                self.assertEqual(hydrated_read["markdown_graph"]["complete"], True)
            finally:
                store.close()

    def test_export_markdown_refuses_incomplete_graph_write_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# Alpha\nlinks to [[B]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)

            check = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "export-markdown",
                    "--output",
                    str(root),
                    "--check",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(check.returncode, 1)
            check_result = json.loads(check.stdout)
            self.assertEqual(check_result["markdown_graph"]["complete"], False)
            self.assertEqual(check_result["projection_complete"], False)
            self.assertEqual(check_result["markdown_projection_contract"]["result_scope"], "partial_markdown_graph")
            self.assertEqual(
                check_result["markdown_projection_contract"]["clobber_risk"],
                "unhydrated_markdown_sources_have_no_stored_lines",
            )
            self.assertIn("A.md", check_result["changed_files"])

            refused = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "export-markdown",
                    "--output",
                    str(root),
                    "--allow-projection-overwrite",
                ],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("Markdown graph is incomplete", refused.stderr)
            self.assertEqual((root / "A.md").read_text(encoding="utf-8"), "# Alpha\nlinks to [[B]]\n")

            unsafe_partial = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "export-markdown",
                    "--output",
                    str(root),
                    "--allow-projection-overwrite",
                    "--allow-incomplete-markdown-export",
                ],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(unsafe_partial.returncode, 0)
            self.assertIn("--backup-dir", unsafe_partial.stderr)
            self.assertEqual((root / "A.md").read_text(encoding="utf-8"), "# Alpha\nlinks to [[B]]\n")

            backup_dir = Path(tmpdir) / "projection-backup"
            partial = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "export-markdown",
                    "--output",
                    str(root),
                    "--allow-projection-overwrite",
                    "--allow-incomplete-markdown-export",
                    "--backup-dir",
                    str(backup_dir),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            partial_result = json.loads(partial.stdout)
            self.assertEqual(partial_result["projection_complete"], False)
            self.assertEqual(partial_result["markdown_projection_contract"]["safe_to_write"], True)
            self.assertEqual(partial_result["markdown_projection_contract"]["backup_required"], True)
            self.assertEqual(partial_result["backup_dir"], str(backup_dir))
            self.assertEqual(set(partial_result["backed_up_files"]), {"A.md", "B.md"})
            self.assertEqual(set(partial_result["written_files"]), {"A.md", "B.md"})
            self.assertEqual((backup_dir / "A.md").read_text(encoding="utf-8"), "# Alpha\nlinks to [[B]]\n")
            self.assertEqual((backup_dir / "B.md").read_text(encoding="utf-8"), "# B\n")
            self.assertIn("title: A", (root / "A.md").read_text(encoding="utf-8"))

    def test_read_hydrate_catalog_page_parses_only_selected_markdown_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text("# Alpha\nlinks to [[B]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)
            original_record_from_file = sqlite_store.markdown_page_record_from_file
            parsed_paths: list[str] = []

            def record_from_file(root_arg, path_arg):
                parsed_paths.append(Path(path_arg).relative_to(root_arg).as_posix())
                return original_record_from_file(root_arg, path_arg)

            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                with patch("grasp.sqlite_store.markdown_page_record_from_file", side_effect=record_from_file):
                    read = store.read("A", hydrate=True, backlink_limit=10, related_limit=10, unresolved_limit=10)

                self.assertEqual(parsed_paths, ["A.md"])
                self.assertEqual(read["page"]["title"], "Alpha")
                self.assertEqual([line["text"] for line in read["lines"]], ["# Alpha", "links to [[B]]"])
                self.assertEqual(read["markdown_hydration"]["hydrated"], True)
                self.assertEqual(read["markdown_hydration"]["source_path"], "A.md")
                self.assertEqual(read["markdown_graph"]["complete"], False)
                self.assertEqual(read["markdown_graph"]["mode"], "partial")
                self.assertEqual(read["markdown_graph"]["hydrated_files"], 1)
                self.assertEqual(read["markdown_graph"]["total_files"], 2)
                self.assertEqual(store.stats()["lines"], 2)
                self.assertEqual(store.stats()["edges"], 1)

                b_read = store.read("B", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertEqual(b_read["page"]["title"], "B")
                self.assertEqual(b_read["lines"], [])
                self.assertEqual(b_read["backlink_count_total"], 1)

                with patch("grasp.sqlite_store.markdown_page_record_from_file", side_effect=record_from_file):
                    b_hydrated = store.read("B", hydrate=True, backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertEqual(parsed_paths, ["A.md", "B.md"])
                self.assertEqual([line["text"] for line in b_hydrated["lines"]], ["# B"])
                self.assertEqual(b_hydrated["markdown_graph"]["complete"], True)
                self.assertEqual(b_hydrated["markdown_graph"]["mode"], "on-demand")
                self.assertEqual(b_hydrated["markdown_graph"]["hydrated_files"], 2)
            finally:
                store.close()

    def test_cli_read_reports_partial_fields_on_incomplete_markdown_graph(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# Alpha\nlinks to [[B]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "read",
                    "A",
                    "--backlinks-limit",
                    "10",
                    "--related-limit",
                    "10",
                    "--unresolved-limit",
                    "10",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            result = json.loads(completed.stdout)
            self.assertEqual(result["page"]["title"], "A")
            self.assertEqual(result["lines"], [])
            self.assertIsNone(result["markdown_hydration"])
            self.assertEqual(result["markdown_graph"]["complete"], False)
            contract = result["markdown_query_contract"]
            self.assertEqual(contract["result_scope"], "partial_markdown_graph")
            self.assertEqual(contract["partial_fields"], [
                "page",
                "lines",
                "line_window",
                "link_stats",
                "backlinks",
                "backlink_count_returned",
                "backlink_count_total",
                "related",
                "unresolved_targets",
                "recovery_hints",
            ])
            self.assertEqual(contract["result_field_states"]["lines"]["state"], "partial")
            self.assertEqual(contract["result_field_states"]["backlinks"]["reason"], "unhydrated_markdown_sources")
            self.assertEqual(contract["empty_result_may_be_incomplete"], True)

            hydrated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "read",
                    "A",
                    "--hydrate",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            hydrated_result = json.loads(hydrated.stdout)
            self.assertEqual([line["text"] for line in hydrated_result["lines"]], ["# Alpha", "links to [[B]]"])
            self.assertEqual(hydrated_result["markdown_hydration"]["hydrated"], True)
            self.assertEqual(hydrated_result["markdown_query_contract"]["partial_fields"], contract["partial_fields"])
            self.assertEqual(hydrated_result["markdown_query_contract"]["empty_result_may_be_incomplete"], False)

            text = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "read",
                    "B",
                ],
                check=True,
                text=True,
                capture_output=True,
            ).stdout
            self.assertIn("graph: incomplete", text)
            self.assertIn("partial fields: page, lines, line_window", text)

    def test_hydrate_markdown_chunk_parses_source_order_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text("# Alpha\nlinks to [[B]]\n", encoding="utf-8")
            (root / "B.md").write_text("# Beta\nlinks to [[C]]\n", encoding="utf-8")
            (root / "C.md").write_text("# Gamma\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)
            original_record_from_file = sqlite_store.markdown_page_record_from_file
            parsed_paths: list[str] = []

            def record_from_file(root_arg, path_arg):
                parsed_paths.append(Path(path_arg).relative_to(root_arg).as_posix())
                return original_record_from_file(root_arg, path_arg)

            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                with patch("grasp.sqlite_store.markdown_page_record_from_file", side_effect=record_from_file):
                    first = store.hydrate_markdown_chunk(limit=2)

                self.assertEqual(parsed_paths, ["A.md", "B.md"])
                self.assertEqual(first["hydrated_count"], 2)
                self.assertEqual(first["reason"], "limit_reached")
                self.assertEqual(first["markdown_graph"]["complete"], False)
                self.assertEqual(first["markdown_graph"]["hydrated_files"], 2)
                self.assertEqual(first["remaining_files"], 1)
                self.assertEqual(store.stats()["lines"], 4)
                self.assertEqual(store.stats()["edges"], 2)

                with patch("grasp.sqlite_store.markdown_page_record_from_file", side_effect=record_from_file):
                    second = store.hydrate_markdown_chunk(limit=2)

                self.assertEqual(parsed_paths, ["A.md", "B.md", "C.md"])
                self.assertEqual(second["hydrated_count"], 1)
                self.assertEqual(second["reason"], "graph_complete")
                self.assertEqual(second["markdown_graph"]["complete"], True)
                self.assertEqual(second["markdown_graph"]["hydrated_files"], 3)
                self.assertEqual(second["remaining_files"], 0)
                read = store.read("Gamma", backlink_limit=10, related_limit=10, unresolved_limit=10)
                self.assertEqual(read["backlink_count_total"], 1)
            finally:
                store.close()

    def test_hydrate_markdown_until_complete_is_time_bounded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text("# A\nlinks to [[B]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\nlinks to [[C]]\n", encoding="utf-8")
            (root / "C.md").write_text("# C\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)
            original_record_from_file = sqlite_store.markdown_page_record_from_file
            parsed_paths: list[str] = []

            def record_from_file(root_arg, path_arg):
                parsed_paths.append(Path(path_arg).relative_to(root_arg).as_posix())
                return original_record_from_file(root_arg, path_arg)

            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                with patch("grasp.sqlite_store.markdown_page_record_from_file", side_effect=record_from_file):
                    timed_out = store.hydrate_markdown_chunk(
                        limit=10,
                        until_complete=True,
                        max_seconds=0,
                    )

                self.assertEqual(parsed_paths, [])
                self.assertEqual(timed_out["hydrated_count"], 0)
                self.assertEqual(timed_out["iterations"], 0)
                self.assertEqual(timed_out["reason"], "time_budget_exhausted")
                self.assertEqual(timed_out["stopped_by"], "max_seconds")
                self.assertEqual(timed_out["markdown_graph"]["hydrated_files"], 0)

                with patch("grasp.sqlite_store.markdown_page_record_from_file", side_effect=record_from_file):
                    completed = store.hydrate_markdown_chunk(
                        limit=1,
                        until_complete=True,
                        max_seconds=10,
                    )

                self.assertEqual(parsed_paths, ["A.md", "B.md", "C.md"])
                self.assertEqual(completed["hydrated_count"], 3)
                self.assertEqual(completed["iterations"], 3)
                self.assertEqual(completed["reason"], "graph_complete")
                self.assertEqual(completed["stopped_by"], "graph_complete")
                self.assertEqual(completed["markdown_graph"]["complete"], True)
                self.assertEqual(completed["remaining_files"], 0)
            finally:
                store.close()

    def test_cli_hydrate_markdown_reports_chunk_progress(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text("# A\nlinks to [[B]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)

            first = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "hydrate-markdown",
                    "--limit",
                    "1",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            result = json.loads(first.stdout)
            self.assertEqual(result["hydrated_count"], 1)
            self.assertEqual(result["hydrated"][0]["source_path"], "A.md")
            self.assertEqual(result["markdown_graph"]["complete"], False)
            self.assertEqual(result["markdown_graph"]["hydrated_files"], 1)
            self.assertEqual(result["remaining_files"], 1)

            text = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "hydrate-markdown",
                    "--limit",
                    "10",
                ],
                check=True,
                text=True,
                capture_output=True,
            ).stdout
            self.assertIn("# Hydrate Markdown", text)
            self.assertIn("hydrated: 1", text)
            self.assertIn("reason: graph_complete", text)
            self.assertIn("graph: complete", text)

    def test_cli_hydrate_markdown_until_complete_requires_time_budget(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text("# A\nlinks to [[B]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)

            missing_budget = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "hydrate-markdown",
                    "--until-complete",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(missing_budget.returncode, 2)
            self.assertIn("--until-complete requires --max-seconds", missing_budget.stderr)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "hydrate-markdown",
                    "--limit",
                    "1",
                    "--until-complete",
                    "--max-seconds",
                    "10",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            result = json.loads(completed.stdout)
            self.assertEqual(result["hydrated_count"], 2)
            self.assertEqual(result["iterations"], 2)
            self.assertEqual(result["reason"], "graph_complete")
            self.assertEqual(result["stopped_by"], "graph_complete")
            self.assertEqual(result["markdown_graph"]["complete"], True)

    def test_gather_hydrate_limit_parses_query_matching_sources_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text("# A\nlinks to [[B]] and [[C]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\nbody without incoming links\n", encoding="utf-8")
            (root / "C.md").write_text("# C\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)
            original_record_from_file = sqlite_store.markdown_page_record_from_file
            parsed_paths: list[str] = []

            def record_from_file(root_arg, path_arg):
                parsed_paths.append(Path(path_arg).relative_to(root_arg).as_posix())
                return original_record_from_file(root_arg, path_arg)

            store = SQLiteStore(store_path, project="wiki", for_write=True)
            try:
                with patch("grasp.sqlite_store.markdown_page_record_from_file", side_effect=record_from_file):
                    gather = store.gather(
                        "B",
                        hydrate_limit=1,
                        backlink_limit=10,
                        co_link_limit=10,
                        mention_limit=10,
                    )

                self.assertEqual(parsed_paths, ["A.md"])
                self.assertEqual(gather["markdown_hydration"]["hydrated_count"], 1)
                self.assertEqual(gather["markdown_hydration"]["matched_files"], 1)
                self.assertEqual(gather["markdown_hydration"]["hydrated"][0]["source_path"], "A.md")
                self.assertEqual(gather["markdown_graph"]["complete"], False)
                self.assertEqual(gather["markdown_graph"]["hydrated_files"], 1)
                self.assertEqual(gather["link_stats"]["link_count"], 1)
                self.assertEqual([edge["source_title"] for edge in gather["backlinks"]], ["A"])
                self.assertEqual([item["title"] for item in gather["co_links"]], ["C"])
                self.assertEqual(store.stats()["lines"], 2)
                self.assertEqual(store.stats()["edges"], 2)
            finally:
                store.close()

    def test_cli_hydrate_limit_retrieval_commands_hydrate_matching_sources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nneedle links to [[B]] and [[C]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\nbody without incoming links\n", encoding="utf-8")
            (root / "C.md").write_text("# C\n", encoding="utf-8")

            def make_store(name: str) -> Path:
                store_path = Path(tmpdir) / f"{name}.sqlite"
                import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)
                return store_path

            def run_json(store_path: Path, *args: str) -> dict:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "grasp",
                        "--json",
                        "--store",
                        str(store_path),
                        "--project",
                        "wiki",
                        *args,
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

            search = run_json(make_store("search"), "search", "needle", "--hydrate-limit", "1", "--limit", "10")
            self.assertEqual(search["markdown_hydration"]["hydrated_count"], 1)
            self.assertEqual(search["markdown_graph"]["hydrated_files"], 1)
            self.assertEqual([hit["source_title"] for hit in search["hits"]], ["A"])

            backlinks = run_json(make_store("backlinks"), "backlinks", "B", "--hydrate-limit", "1", "--limit", "10")
            self.assertEqual(backlinks["markdown_hydration"]["hydrated_count"], 1)
            self.assertEqual(backlinks["markdown_graph"]["hydrated_files"], 1)
            self.assertEqual([edge["source_title"] for edge in backlinks["backlinks"]], ["A"])

            related = run_json(make_store("related"), "related", "B", "--hydrate-limit", "1", "--limit", "10")
            self.assertEqual(related["markdown_hydration"]["hydrated_count"], 1)
            self.assertEqual(related["markdown_graph"]["hydrated_files"], 1)
            self.assertEqual([item["title"] for item in related["related"]], ["C"])

    def test_cli_hydrate_limit_contract_reports_partial_nonempty_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nneedle links to [[B]]\n", encoding="utf-8")
            (root / "D.md").write_text("# D\nneedle links to [[C]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            (root / "C.md").write_text("# C\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "search",
                    "needle",
                    "--hydrate-limit",
                    "1",
                    "--limit",
                    "10",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            result = json.loads(completed.stdout)
            self.assertEqual([hit["source_title"] for hit in result["hits"]], ["A"])
            contract = result["markdown_query_contract"]
            self.assertEqual(contract["result_scope"], "partial_markdown_graph")
            self.assertEqual(contract["result_completeness"], "partial")
            self.assertEqual(contract["result_may_be_incomplete"], True)
            self.assertEqual(contract["empty_result_may_be_incomplete"], False)
            self.assertEqual(contract["result_field_states"]["hits"]["state"], "partial")
            progress = contract["hydration_progress"]
            self.assertEqual(progress["scan"], "markdown-source-query")
            self.assertEqual(progress["reason"], "limit_reached")
            self.assertEqual(progress["requested_limit"], 1)
            self.assertEqual(progress["matched_files"], 1)
            self.assertEqual(progress["hydrated_count"], 1)
            self.assertEqual(progress["limit_reached"], True)
            self.assertEqual(progress["scan_exhausted"], False)

    def test_cli_retrieval_reports_incomplete_markdown_graph_without_hydrate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nneedle links to [[B]] and [[C]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\nbody without incoming links\n", encoding="utf-8")
            (root / "C.md").write_text("# C\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)

            def run_json(*args: str) -> dict:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "grasp",
                        "--json",
                        "--store",
                        str(store_path),
                        "--project",
                        "wiki",
                        *args,
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

            cases = [
                (("search", "needle", "--limit", "10"), "hits", ["hits", "count_returned", "recovery_hints"]),
                (("backlinks", "B", "--limit", "10"), "backlinks", ["backlinks", "candidate_backlinks", "count_returned", "count_total"]),
                (("related", "B", "--limit", "10"), "related", ["related", "candidate_related", "recovery_hints"]),
            ]
            for args, result_key, partial_fields in cases:
                with self.subTest(command=args[0]):
                    result = run_json(*args)
                    self.assertEqual(result[result_key], [])
                    self.assertIsNone(result["markdown_hydration"])
                    self.assertEqual(result["markdown_graph"]["complete"], False)
                    self.assertEqual(result["markdown_graph"]["hydrated_files"], 0)
                    contract = result["markdown_query_contract"]
                    self.assertEqual(contract["result_scope"], "partial_markdown_graph")
                    self.assertEqual(contract["graph_complete"], False)
                    self.assertEqual(contract["empty_result_may_be_incomplete"], True)
                    self.assertEqual(contract["partial_fields"], partial_fields)
                    for field in partial_fields:
                        self.assertEqual(contract["result_field_states"][field]["state"], "partial")
                        self.assertEqual(
                            contract["result_field_states"][field]["reason"],
                            "unhydrated_markdown_sources",
                        )
                    self.assertIn("--hydrate-limit N", contract["hydrate_hint"])

            text = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "search",
                    "needle",
                    "--limit",
                    "10",
                ],
                check=True,
                text=True,
                capture_output=True,
            ).stdout
            self.assertIn("graph: incomplete", text)
            self.assertIn("empty results may be caused by unhydrated Markdown source files", text)
            self.assertIn("partial fields: hits, count_returned, recovery_hints", text)

            gather = run_json(
                "gather",
                "needle",
                "--mentions-limit",
                "10",
                "--co-links-limit",
                "10",
                "--backlinks-limit",
                "10",
            )
            gather_contract = gather["markdown_query_contract"]
            self.assertEqual(gather_contract["result_scope"], "partial_markdown_graph")
            self.assertEqual(
                gather_contract["partial_fields"],
                [
                    "link_stats",
                    "mention_summary",
                    "mentions",
                    "co_links",
                    "backlinks",
                    "returned_counts",
                    "total_counts",
                    "omitted_counts",
                    "banner",
                    "recipes",
                ],
            )
            self.assertEqual(gather_contract["result_field_states"]["mentions"]["state"], "partial")

    def test_cli_graph_commands_report_incomplete_markdown_graph_contract(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nneedle links to [[B]] and [[Missing]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)

            def run_json(*args: str) -> dict:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "grasp",
                        "--json",
                        "--store",
                        str(store_path),
                        "--project",
                        "wiki",
                        *args,
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

            cases = [
                (("mentions", "needle", "--limit", "10"), lambda result: result["mentions"], ["summary", "mentions"]),
                (("co-links", "needle", "--limit", "10"), lambda result: result["co_links"], ["co_links", "count_returned"]),
                (("path", "A", "B", "--max-depth", "2"), lambda result: result["paths"], ["paths", "path_count", "truncated", "recovery_hints"]),
                (("unresolved", "--limit", "10"), lambda result: result["unresolved_targets"], ["unresolved_targets"]),
            ]
            for args, result_items, partial_fields in cases:
                with self.subTest(command=args[0]):
                    result = run_json(*args)
                    self.assertEqual(result_items(result), [])
                    self.assertIsNone(result["markdown_hydration"])
                    self.assertEqual(result["markdown_graph"]["complete"], False)
                    self.assertEqual(result["markdown_graph"]["hydrated_files"], 0)
                    contract = result["markdown_query_contract"]
                    self.assertEqual(contract["result_scope"], "partial_markdown_graph")
                    self.assertEqual(contract["graph_complete"], False)
                    self.assertEqual(contract["empty_result_may_be_incomplete"], True)
                    self.assertEqual(contract["partial_fields"], partial_fields)
                    for field in partial_fields:
                        self.assertEqual(contract["result_field_states"][field]["state"], "partial")
                    self.assertIn("hydrate", contract["hydrate_hint"])

            text = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "unresolved",
                    "--limit",
                    "10",
                ],
                check=True,
                text=True,
                capture_output=True,
            ).stdout
            self.assertIn("graph: incomplete", text)
            self.assertIn("empty results may be caused by unhydrated Markdown source files", text)

    def test_cli_misc_catalog_commands_report_incomplete_markdown_graph_contract(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text(
                "---\ntitle: Alpha Title\naliases:\n  - Alias Title\n---\n# Alpha Title\nlinks to [[B]]\n",
                encoding="utf-8",
            )
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            (root / "one").mkdir()
            (root / "two").mkdir()
            (root / "one" / "Dupe.md").write_text("# Dupe one\n", encoding="utf-8")
            (root / "two" / "Dupe.md").write_text("# Dupe two\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)

            def run_json(*args: str) -> dict:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "grasp",
                        "--json",
                        "--store",
                        str(store_path),
                        "--project",
                        "wiki",
                        *args,
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

            cases = [
                (
                    ("link-stats", "B"),
                    ["page", "link_count", "source_page_count", "link_multiplicity", "recovery_hints"],
                    True,
                ),
                (
                    ("peek", "A"),
                    ["page", "lines", "lines_truncated", "lines_truncated_before", "lines_truncated_after"],
                    True,
                ),
                (("suggest", "Alpha"), ["suggestions"], True),
                (
                    ("ambiguities", "--limit", "10"),
                    ["projects", "ambiguities", "handle_count", "handles_returned"],
                    False,
                ),
                (
                    ("cross-project-spread", "B", "--limit", "10"),
                    ["totals", "top_source_projects", "projects", "signal_project_count"],
                    False,
                ),
                (
                    ("cross-project-spreads", "--min-projects", "1", "--limit", "10"),
                    ["spreads", "handle_count", "handles_returned"],
                    False,
                ),
            ]
            for args, partial_fields, empty_result in cases:
                with self.subTest(command=args[0]):
                    result = run_json(*args)
                    self.assertEqual(result["markdown_graph"]["complete"], False)
                    self.assertEqual(result["markdown_graph"]["hydrated_files"], 0)
                    contract = result["markdown_query_contract"]
                    self.assertEqual(contract["result_scope"], "partial_markdown_graph")
                    self.assertEqual(contract["result_completeness"], "partial")
                    self.assertEqual(contract["result_may_be_incomplete"], True)
                    self.assertEqual(contract["empty_result_may_be_incomplete"], empty_result)
                    self.assertEqual(contract["partial_fields"], partial_fields)
                    for field in partial_fields:
                        self.assertEqual(contract["result_field_states"][field]["state"], "partial")

            text = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "peek",
                    "A",
                ],
                check=True,
                text=True,
                capture_output=True,
            ).stdout
            self.assertIn("graph: incomplete", text)
            self.assertIn("partial fields: page, lines", text)

    def test_cli_all_project_commands_report_mixed_incomplete_markdown_graph_contract(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            incomplete_root = base / "incomplete"
            complete_root = base / "complete"
            incomplete_root.mkdir()
            complete_root.mkdir()
            (incomplete_root / "A.md").write_text("# A\nlinks to [[B]]\n", encoding="utf-8")
            (incomplete_root / "B.md").write_text("# B\n", encoding="utf-8")
            (incomplete_root / "one").mkdir()
            (incomplete_root / "two").mkdir()
            (incomplete_root / "one" / "Dupe.md").write_text("# Dupe one\n", encoding="utf-8")
            (incomplete_root / "two" / "Dupe.md").write_text("# Dupe two\n", encoding="utf-8")
            (complete_root / "C.md").write_text("# C\nlinks to [[B]]\n", encoding="utf-8")
            store_path = base / "store.sqlite"
            import_markdown_folder_to_sqlite(
                incomplete_root,
                store_path,
                project_name="incomplete",
                catalog_only=True,
            )
            import_markdown_folder_to_sqlite(complete_root, store_path, project_name="complete")

            def run_json(*args: str) -> dict:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "grasp",
                        "--json",
                        "--store",
                        str(store_path),
                        *args,
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

            cases = [
                (
                    ("link-stats", "B"),
                    ["page", "link_count", "source_page_count", "link_multiplicity", "recovery_hints"],
                    False,
                ),
                (
                    ("peek", "A"),
                    ["page", "lines", "lines_truncated", "lines_truncated_before", "lines_truncated_after"],
                    True,
                ),
                (("suggest", "Dupe"), ["suggestions"], False),
                (
                    ("ambiguities", "--limit", "10"),
                    ["projects", "ambiguities", "handle_count", "handles_returned"],
                    False,
                ),
                (
                    ("cross-project-spread", "B", "--limit", "10"),
                    ["totals", "top_source_projects", "projects", "signal_project_count"],
                    False,
                ),
                (
                    ("cross-project-spreads", "--min-projects", "1", "--limit", "10"),
                    ["spreads", "handle_count", "handles_returned"],
                    False,
                ),
            ]
            for args, partial_fields, empty_result in cases:
                with self.subTest(command=args[0]):
                    result = run_json(*args)
                    graph = result["markdown_graph"]
                    self.assertEqual(graph["complete"], False)
                    self.assertEqual(graph["mode"], "all-projects")
                    self.assertEqual(graph["markdown_project_count"], 2)
                    self.assertEqual(graph["incomplete_project_count"], 1)
                    self.assertEqual(graph["incomplete_projects"][0]["project"], "incomplete")
                    contract = result["markdown_query_contract"]
                    self.assertEqual(contract["result_scope"], "partial_markdown_graph")
                    self.assertEqual(contract["result_completeness"], "partial")
                    self.assertEqual(contract["result_may_be_incomplete"], True)
                    self.assertEqual(contract["empty_result_may_be_incomplete"], empty_result)
                    self.assertEqual(contract["partial_fields"], partial_fields)
                    self.assertEqual(
                        contract["incomplete_markdown_projects"][0]["project"],
                        "incomplete",
                    )

            text = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--store",
                    str(store_path),
                    "link-stats",
                    "B",
                ],
                check=True,
                text=True,
                capture_output=True,
            ).stdout
            self.assertIn("graph: incomplete (all-projects", text)
            self.assertIn("incomplete projects: incomplete", text)

    def test_cli_graph_command_hydrate_limit_parses_matching_sources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nneedle links to [[B]] and [[Missing]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")

            def make_store(name: str) -> Path:
                store_path = Path(tmpdir) / f"{name}.sqlite"
                import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)
                return store_path

            def run_json(store_path: Path, *args: str) -> dict:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "grasp",
                        "--json",
                        "--store",
                        str(store_path),
                        "--project",
                        "wiki",
                        *args,
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                return json.loads(completed.stdout)

            mentions = run_json(make_store("mentions"), "mentions", "needle", "--hydrate-limit", "1", "--limit", "10")
            self.assertEqual(mentions["markdown_hydration"]["hydrated_count"], 1)
            self.assertEqual(mentions["markdown_graph"]["hydrated_files"], 1)
            self.assertEqual([hit["source_title"] for hit in mentions["mentions"]], ["A"])

            co_links = run_json(make_store("co-links"), "co-links", "needle", "--hydrate-limit", "1", "--limit", "10")
            self.assertEqual(co_links["markdown_hydration"]["hydrated_count"], 1)
            self.assertEqual(co_links["markdown_graph"]["hydrated_files"], 1)
            self.assertEqual({item["title"] for item in co_links["co_links"]}, {"B", "Missing"})

            path = run_json(make_store("path"), "path", "A", "B", "--hydrate-limit", "1", "--max-depth", "2")
            self.assertEqual(path["markdown_hydration"]["hydrated_count"], 1)
            self.assertEqual(path["markdown_graph"]["hydrated_files"], 1)
            self.assertEqual(path["path_count"], 1)
            self.assertEqual([node["title"] for node in path["paths"][0]["nodes"]], ["A", "B"])

            unresolved = run_json(make_store("unresolved"), "unresolved", "--hydrate-limit", "1", "--limit", "10")
            self.assertEqual(unresolved["markdown_hydration"]["hydrated_count"], 1)
            self.assertEqual(unresolved["markdown_graph"]["hydrated_files"], 1)
            self.assertEqual([item["title"] for item in unresolved["unresolved_targets"]], ["Missing"])

    def test_cli_idle_hydration_runs_after_result_for_future_commands(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nneedle links to [[B]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"
            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "--idle-hydrate-seconds",
                    "10",
                    "--idle-hydrate-limit",
                    "1",
                    "search",
                    "needle",
                    "--limit",
                    "10",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            result = json.loads(completed.stdout)
            self.assertEqual(result["hits"], [])
            self.assertEqual(result["markdown_graph"]["hydrated_files"], 0)
            idle = result["markdown_idle_hydration"]
            self.assertEqual(idle["applied_after_result"], True)
            self.assertEqual(idle["hydrated_count"], 1)
            self.assertEqual(idle["hydrated"][0]["source_path"], "A.md")
            self.assertEqual(idle["markdown_graph"]["hydrated_files"], 1)

            followup = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grasp",
                    "--json",
                    "--store",
                    str(store_path),
                    "--project",
                    "wiki",
                    "search",
                    "needle",
                    "--limit",
                    "10",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            followup_result = json.loads(followup.stdout)
            self.assertEqual([hit["source_title"] for hit in followup_result["hits"]], ["A"])

    def test_cli_idle_hydration_policy_can_be_set_by_environment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "wiki"
            root.mkdir()
            (root / "A.md").write_text("# A\nneedle links to [[B]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")

            def make_store(name: str) -> Path:
                store_path = Path(tmpdir) / f"{name}.sqlite"
                import_markdown_folder_to_sqlite(root, store_path, project_name="wiki", catalog_only=True)
                return store_path

            base_cmd = [
                sys.executable,
                "-m",
                "grasp",
                "--json",
                "--project",
                "wiki",
            ]
            env = {
                **os.environ,
                "GRASP_IDLE_HYDRATE_SECONDS": "10",
                "GRASP_IDLE_HYDRATE_LIMIT": "1",
            }

            env_store = make_store("env")
            completed = subprocess.run(
                [
                    *base_cmd,
                    "--store",
                    str(env_store),
                    "search",
                    "needle",
                    "--limit",
                    "10",
                ],
                check=True,
                text=True,
                capture_output=True,
                env=env,
            )
            result = json.loads(completed.stdout)
            self.assertEqual(result["hits"], [])
            self.assertEqual(result["markdown_idle_hydration"]["hydrated_count"], 1)

            disabled_store = make_store("disabled")
            disabled = subprocess.run(
                [
                    *base_cmd,
                    "--store",
                    str(disabled_store),
                    "--idle-hydrate-seconds",
                    "0",
                    "search",
                    "needle",
                    "--limit",
                    "10",
                ],
                check=True,
                text=True,
                capture_output=True,
                env=env,
            )
            disabled_result = json.loads(disabled.stdout)
            self.assertNotIn("markdown_idle_hydration", disabled_result)
            self.assertEqual(disabled_result["markdown_graph"]["hydrated_files"], 0)

    def test_noop_reimport_uses_manifest_hash_fast_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "A.md").write_text("# A\nlinks to [[B]]\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            with patch(
                "grasp.sqlite_store.MarkdownMirror.from_folder",
                side_effect=AssertionError("noop reimport should not build a MarkdownMirror"),
            ):
                result = import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            self.assertEqual(result["markdown_import"]["mode"], "incremental")
            self.assertEqual(result["markdown_import"]["changed_files"], 0)
            self.assertEqual(result["markdown_import"]["fast_path"], "manifest_hash_noop")
            self.assertEqual(result["markdown_import"]["scanned_files"], 2)
            self.assertEqual(result["pages"], 2)
            self.assertEqual(result["edges"], 1)

    def test_reimport_aborts_when_writer_event_lands_during_parse(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            page_a = root / "A.md"
            page_a.write_text("# A\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")
            page_a.write_text("# Renamed A\nlocal Markdown edit\n", encoding="utf-8")
            original_from_folder = MarkdownMirror.from_folder

            def from_folder_with_concurrent_write(*args, **kwargs):
                mirror = original_from_folder(*args, **kwargs)
                store = SQLiteStore(store_path, project="wiki", for_write=True)
                try:
                    store.write_markdown_page_with_event(
                        "A",
                        lines=["# A", "- concurrent writer marker"],
                        actor="test",
                        session_id="writer",
                    )
                finally:
                    store.close()
                return mirror

            with patch("grasp.sqlite_store.MarkdownMirror.from_folder", side_effect=from_folder_with_concurrent_write):
                with self.assertRaisesRegex(ValueError, "Markdown import aborted: project events changed"):
                    import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            store = SQLiteStore(store_path, project="wiki")
            try:
                page = store.resolve_page("A")
                lines, _aliases = store.page_lines(page)
                self.assertEqual([line.text for line in lines], ["# A", "- concurrent writer marker"])
                self.assertEqual(store.event_count(), 1)
            finally:
                store.close()

    def test_noop_fast_reimport_aborts_when_writer_event_lands_during_manifest_scan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            page_a = root / "A.md"
            page_a.write_text("# A\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")
            original_fast_summary = sqlite_store._fast_noop_markdown_import_summary

            def fast_summary_with_concurrent_write(*args, **kwargs):
                summary = original_fast_summary(*args, **kwargs)
                store = SQLiteStore(store_path, project="wiki", for_write=True)
                try:
                    store.write_markdown_page_with_event(
                        "A",
                        lines=["# A", "- concurrent writer marker"],
                        actor="test",
                        session_id="writer",
                    )
                finally:
                    store.close()
                return summary

            with patch(
                "grasp.sqlite_store._fast_noop_markdown_import_summary",
                side_effect=fast_summary_with_concurrent_write,
            ):
                with self.assertRaisesRegex(ValueError, "Markdown import aborted: project events changed"):
                    import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            store = SQLiteStore(store_path, project="wiki")
            try:
                page = store.resolve_page("A")
                lines, _aliases = store.page_lines(page)
                self.assertEqual([line.text for line in lines], ["# A", "- concurrent writer marker"])
                self.assertEqual(store.event_count(), 1)
            finally:
                store.close()

    def test_changed_file_fast_reimport_aborts_when_writer_event_lands_during_manifest_scan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            page_a = root / "A.md"
            page_a.write_text("# A\n", encoding="utf-8")
            (root / "B.md").write_text("# B\n", encoding="utf-8")
            store_path = Path(tmpdir) / "store.sqlite"

            import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")
            page_a.write_text("# A\ncontent-only edit\n", encoding="utf-8")
            original_change_scan = sqlite_store._markdown_manifest_change_scan

            def change_scan_with_concurrent_write(*args, **kwargs):
                scan = original_change_scan(*args, **kwargs)
                store = SQLiteStore(store_path, project="wiki", for_write=True)
                try:
                    store.write_markdown_page_with_event(
                        "A",
                        lines=["# A", "- concurrent writer marker"],
                        actor="test",
                        session_id="writer",
                    )
                finally:
                    store.close()
                return scan

            with patch(
                "grasp.sqlite_store._markdown_manifest_change_scan",
                side_effect=change_scan_with_concurrent_write,
            ):
                with self.assertRaisesRegex(ValueError, "Markdown import aborted: project events changed"):
                    import_markdown_folder_to_sqlite(root, store_path, project_name="wiki")

            store = SQLiteStore(store_path, project="wiki")
            try:
                page = store.resolve_page("A")
                lines, _aliases = store.page_lines(page)
                self.assertEqual([line.text for line in lines], ["# A", "- concurrent writer marker"])
                self.assertEqual(store.event_count(), 1)
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
