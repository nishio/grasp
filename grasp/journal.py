from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


JOURNAL_SCHEMA_VERSION = 1

EVENT_TYPES = {
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
}


def make_journal_event(
    event_type: str,
    *,
    project: str,
    payload: dict[str, Any],
    event_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    event = {
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "event_id": event_id or uuid4().hex,
        "event_type": event_type,
        "project": project,
        "created_at": created_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "payload": payload,
    }
    validate_journal_event(event)
    return event


def validate_journal_event(event: dict[str, Any]) -> None:
    if event.get("schema_version") != JOURNAL_SCHEMA_VERSION:
        raise ValueError(f"unsupported journal schema_version: {event.get('schema_version')!r}")
    event_type = event.get("event_type")
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unsupported journal event_type: {event_type!r}")
    for field in ("event_id", "project", "created_at"):
        if not isinstance(event.get(field), str) or not event[field]:
            raise ValueError(f"journal event requires non-empty string field: {field}")
    if not isinstance(event.get("payload"), dict):
        raise ValueError("journal event requires object payload")


def journal_event_json(event: dict[str, Any]) -> str:
    validate_journal_event(event)
    return json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def append_journal_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(journal_event_json(event))


def read_journal_events(path: Path) -> list[dict[str, Any]]:
    events = []
    if not path.exists():
        return events
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid journal JSON at line {line_number}: {exc}") from exc
            if not isinstance(event, dict):
                raise ValueError(f"journal line {line_number} must be a JSON object")
            validate_journal_event(event)
            events.append(event)
    return events
