import json
import tempfile
import unittest
from pathlib import Path

from grasp.journal import (
    EVENT_TYPES,
    append_journal_event,
    journal_event_json,
    make_journal_event,
    read_journal_events,
    validate_journal_event,
)


class JournalTests(unittest.TestCase):
    def test_make_validate_and_round_trip_event(self):
        event = make_journal_event(
            "section_append",
            project="grasp-wiki",
            event_id="evt-1",
            created_at="2026-06-26T00:30:00+00:00",
            payload={
                "page_id": "page-1",
                "section_title": "Updates",
                "lines": ["- added note"],
            },
        )

        validate_journal_event(event)
        encoded = journal_event_json(event)
        self.assertTrue(encoded.endswith("\n"))
        self.assertEqual(json.loads(encoded), event)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "wiki.grasp" / "events.jsonl"
            append_journal_event(path, event)
            self.assertEqual(read_journal_events(path), [event])

    def test_event_type_contract_is_frozen_for_fast_path(self):
        self.assertEqual(
            EVENT_TYPES,
            {
                "page_create",
                "page_update",
                "section_append",
                "page_rename",
                "log_append",
                "log_entry_import",
                "page_claim",
                "page_claim_release",
                "projection_export",
                "event_revert",
            },
        )

    def test_rejects_invalid_event_shape(self):
        with self.assertRaisesRegex(ValueError, "unsupported journal event_type"):
            make_journal_event("unknown", project="wiki", payload={})

        event = make_journal_event("page_update", project="wiki", payload={})
        event["payload"] = []
        with self.assertRaisesRegex(ValueError, "object payload"):
            validate_journal_event(event)

    def test_read_reports_invalid_json_line(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.jsonl"
            path.write_text("{not json}\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "invalid journal JSON at line 1"):
                read_journal_events(path)
