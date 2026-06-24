import json
import tempfile
import unittest
from pathlib import Path

from grasp.cosense import CosenseStore, normalize_title, parse_cosense_cross_project_links, parse_cosense_links


class CosenseParsingTests(unittest.TestCase):
    def test_normalize_title_folds_case_and_whitespace(self):
        self.assertEqual(normalize_title("  Foo   BAR  "), "foo bar")

    def test_parse_cosense_links_filters_overloaded_brackets(self):
        text = (
            "[Page] [[bold only]] [https://example.com label] [label https://example.com] "
            "[person.icon] [photo.img] [* bold] [/ italic] [- strike] [_ underline] "
            "[** heading] [*** deeper] [-- strike] [__ underline] "
            "[$ x+y] [/other/project] [Other Page] xs[i] paper.projects[1] func()[0] [2] `[Code]` "
            "#tag #2024 # https://example.com/#fragment"
        )

        self.assertEqual(parse_cosense_links(text), ["Page", "Other Page", "2", "tag", "2024"])

    def test_parse_cosense_links_allows_links_embedded_in_japanese_text(self):
        self.assertEqual(parse_cosense_links("人間が[盲点]に気づく"), ["盲点"])

    def test_parse_cosense_links_allows_hash_tags_embedded_in_japanese_text(self):
        self.assertEqual(parse_cosense_links("人間が#盲点 に気づく"), ["盲点"])

    def test_parse_cosense_cross_project_links_classifies_targets(self):
        text = (
            "[/villagepump/Page A] [/villagepump/nishio.icon] [/plurality-japanese] "
            "[/takker/takker99/ScrapBubble] [/ italic] xs[/bad] `[/code/Page]` [[/bold/Page]]"
        )

        links = parse_cosense_cross_project_links(text)

        self.assertEqual(
            [link.to_dict() for link in links],
            [
                {
                    "raw": "/villagepump/Page A",
                    "project": "villagepump",
                    "title": "Page A",
                    "target_class": "semantic",
                },
                {
                    "raw": "/villagepump/nishio.icon",
                    "project": "villagepump",
                    "title": "nishio.icon",
                    "target_class": "icon",
                },
                {
                    "raw": "/plurality-japanese",
                    "project": "plurality-japanese",
                    "title": "",
                    "target_class": "project-root",
                },
                {
                    "raw": "/takker/takker99/ScrapBubble",
                    "project": "takker",
                    "title": "takker99/ScrapBubble",
                    "target_class": "semantic",
                },
            ],
        )


class CosenseStoreTests(unittest.TestCase):
    def test_store_materializes_backlinks_unresolved_targets_and_related(self):
        data = {
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
                        {"text": "also links to [B]", "created": 1, "updated": 2, "userId": "u"},
                    ],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "export.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            store = CosenseStore.from_cosense_export(path)

        backlinks = store.backlinks("b")
        self.assertEqual([edge.source_title for edge in backlinks], ["A", "C"])
        self.assertEqual(backlinks[0].line_id, "aaaaaaaaaaaaaaaaaaaaaaaa:1")

        unresolved_targets = store.unresolved_targets()
        self.assertEqual(unresolved_targets[0]["title"], "Missing")
        self.assertEqual(unresolved_targets[0]["link_count"], 1)

        related = store.related("A")
        self.assertEqual(related[0]["title"], "C")
        self.assertEqual(related[0]["via"], ["B"])

        read = store.read("A", backlink_limit=10, related_limit=10, unresolved_limit=10)
        self.assertEqual(read["page"]["title"], "A")
        self.assertEqual(read["unresolved_targets"][0]["title"], "Missing")


if __name__ == "__main__":
    unittest.main()
