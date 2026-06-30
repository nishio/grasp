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
