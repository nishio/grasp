from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
from typing import Any, Protocol
from urllib.parse import quote

from .sqlite_store import SQLiteStore, parse_cosense_time


class CosenseClient(Protocol):
    def list_pages(self, project_url: str, *, sort: str, limit: int, skip: int) -> dict[str, Any]:
        ...

    def read_page(self, page_url: str) -> dict[str, Any]:
        ...


@dataclass
class CosenseCliClient:
    command: str = "cosense"

    def list_pages(self, project_url: str, *, sort: str = "updated", limit: int = 100, skip: int = 0) -> dict[str, Any]:
        return self._run_json(
            [
                self.command,
                "listPages",
                project_url,
                "--sort",
                sort,
                "--limit",
                str(limit),
                "--skip",
                str(skip),
            ]
        )

    def read_page(self, page_url: str) -> dict[str, Any]:
        return self._run_json([self.command, "readPage", page_url])

    def _run_json(self, command: list[str]) -> dict[str, Any]:
        completed = subprocess.run(command, check=True, text=True, capture_output=True)
        return json.loads(completed.stdout)


def sync_from_cosense(
    store: SQLiteStore,
    project_url: str,
    *,
    client: CosenseClient | None = None,
    limit: int = 100,
    batch_size: int = 100,
    dry_run: bool = False,
) -> dict[str, Any]:
    client = client or CosenseCliClient()
    inspected = 0
    skip = 0
    changed_metadata: list[dict[str, Any]] = []
    stopped_at: dict[str, Any] | None = None

    while inspected < limit:
        current_limit = min(batch_size, limit - inspected)
        result = client.list_pages(project_url, sort="updated", limit=current_limit, skip=skip)
        pages = result.get("pages") or []
        if not pages:
            break

        for page in pages:
            inspected += 1
            page_id = page.get("id")
            remote_updated = parse_cosense_time(page.get("updated"))
            local_updated = store.page_updated(page_id) if page_id else None
            pin = int(page.get("pin") or 0)

            if local_updated is not None and remote_updated is not None and local_updated >= remote_updated:
                if pin > 0:
                    continue
                stopped_at = {
                    "id": page_id,
                    "title": page.get("title"),
                    "updated": page.get("updated"),
                }
                break

            changed_metadata.append(page)
            if inspected >= limit:
                break

        if stopped_at is not None or inspected >= limit:
            break
        skip += len(pages)

    fetched_pages: list[dict[str, Any]] = []
    skipped_nonpersistent: list[dict[str, Any]] = []
    if not dry_run:
        for page in changed_metadata:
            page_url = page_url_for_title(project_url, str(page.get("title", "")))
            page_data = client.read_page(page_url)
            if not page_data.get("persistent", True):
                skipped_nonpersistent.append({"title": page.get("title"), "url": page_url})
                continue
            fetched_pages.append(page_data)
        store.upsert_cosense_pages(fetched_pages)
        store.set_metadata(
            {
                "last_sync_project": project_url,
                "last_sync_checked": str(inspected),
                "last_sync_updated": str(max((parse_cosense_time(page.get("updated")) or 0 for page in changed_metadata), default=0)),
            }
        )

    return {
        "project_url": project_url,
        "dry_run": dry_run,
        "inspected": inspected,
        "changed": len(changed_metadata),
        "updated": 0 if dry_run else len(fetched_pages),
        "skipped_nonpersistent": skipped_nonpersistent,
        "stopped_at": stopped_at,
        "changed_pages": [
            {
                "id": page.get("id"),
                "title": page.get("title"),
                "updated": page.get("updated"),
                "pin": page.get("pin", 0),
            }
            for page in changed_metadata
        ],
    }


def page_url_for_title(project_url: str, title: str) -> str:
    return f"{project_url.rstrip('/')}/{quote(title, safe='')}"
