from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
from typing import Any, Protocol
from urllib.parse import quote, unquote, urlparse

from .cosense import normalize_title, parse_cosense_links
from .sqlite_store import SQLiteStore, parse_cosense_time


class CosenseClient(Protocol):
    def list_pages(
        self,
        project_url: str,
        *,
        sort: str,
        limit: int,
        skip: int,
        filter_name: str | None = None,
    ) -> dict[str, Any]:
        ...

    def read_page(self, page_url: str) -> dict[str, Any]:
        ...

    def search_full_text(self, project_url: str, query: str) -> dict[str, Any]:
        ...


@dataclass
class CosenseCliClient:
    command: str = "cosense"

    def list_pages(
        self,
        project_url: str,
        *,
        sort: str = "updated",
        limit: int = 100,
        skip: int = 0,
        filter_name: str | None = None,
    ) -> dict[str, Any]:
        command = [
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
        if filter_name:
            command.extend(["--filter", filter_name])
        return self._run_json(command)

    def read_page(self, page_url: str) -> dict[str, Any]:
        return self._run_json([self.command, "readPage", page_url])

    def search_full_text(self, project_url: str, query: str) -> dict[str, Any]:
        return self._run_json([self.command, "searchFullText", project_url, query])

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


def acquire_from_cosense(
    store: SQLiteStore,
    project_url: str,
    *,
    client: CosenseClient | None = None,
    project: str | None = None,
    searches: list[str] | None = None,
    from_pages: list[str] | None = None,
    seed_titles: list[str] | None = None,
    filter_name: str | None = None,
    full_list: bool = False,
    depth: int = 1,
    limit: int = 100,
    batch_size: int = 100,
    sort: str = "updated",
) -> dict[str, Any]:
    client = client or CosenseCliClient()
    searches = searches or []
    from_pages = from_pages or []
    seed_titles = seed_titles or []
    if not searches and not from_pages and not seed_titles and not filter_name and not full_list:
        raise ValueError("acquire needs at least one seed: --search, --from-page, --seed-file, --filter, or --full-list")
    if depth < 0:
        raise ValueError("--depth must be >= 0")
    if limit <= 0:
        raise ValueError("--limit must be > 0")
    if batch_size <= 0:
        raise ValueError("--batch-size must be > 0")

    modes: list[str] = []
    project_name = project
    remote_project_name: str | None = None
    remote_count: int | None = None
    candidate_values: list[str] = []
    search_results: list[dict[str, Any]] = []
    list_results: list[dict[str, Any]] = []

    for query in searches:
        modes.append("search")
        result = client.search_full_text(project_url, query)
        remote_project_name = remote_project_name or result.get("projectName")
        search_results.append(
            {
                "query": query,
                "count": result.get("count"),
                "returned": len(result.get("pages") or []),
            }
        )
        for page in result.get("pages") or []:
            title = page.get("title")
            if title:
                candidate_values.append(str(title))

    if full_list:
        modes.append("full-list")
        pages, remote_project_name, remote_count = _list_page_candidates(
            client,
            project_url,
            project_name=remote_project_name,
            sort=sort,
            limit=limit,
            batch_size=batch_size,
            filter_name=None,
        )
        candidate_values.extend(pages)
        list_results.append({"mode": "full-list", "count": remote_count, "returned": len(pages)})

    if filter_name:
        modes.append("filter")
        pages, remote_project_name, filter_count = _list_page_candidates(
            client,
            project_url,
            project_name=remote_project_name,
            sort=sort,
            limit=limit,
            batch_size=batch_size,
            filter_name=filter_name,
        )
        candidate_values.extend(pages)
        list_results.append({"mode": "filter", "filter": filter_name, "count": filter_count, "returned": len(pages)})

    if seed_titles:
        modes.append("seed-file")
        candidate_values.extend(seed_titles)

    fetched_pages: list[dict[str, Any]] = []
    fetched_norms: set[str] = set()
    skipped_nonpersistent: list[dict[str, Any]] = []
    failed_pages: list[dict[str, Any]] = []

    _fetch_candidate_values(
        client,
        project_url,
        candidate_values,
        fetched_pages=fetched_pages,
        fetched_norms=fetched_norms,
        skipped_nonpersistent=skipped_nonpersistent,
        failed_pages=failed_pages,
        limit=limit,
    )

    if from_pages:
        modes.append("from-page")
        _crawl_from_pages(
            client,
            project_url,
            from_pages,
            depth=depth,
            limit=limit,
            fetched_pages=fetched_pages,
            fetched_norms=fetched_norms,
            skipped_nonpersistent=skipped_nonpersistent,
            failed_pages=failed_pages,
        )

    remote_project_name = remote_project_name or project_name_from_url(project_url)
    project_name = project_name or f"{remote_project_name}:acquire"
    display_name = remote_project_name if project is not None else project_name
    source_export = f"cosense:{project_url}"
    coverage = "full-list" if full_list and remote_count is not None and len(fetched_pages) >= remote_count else "partial"
    acquisition_metadata = {
        "mode": "+".join(dict.fromkeys(modes)),
        "coverage": coverage,
        "project_url": project_url,
        "remote_project": remote_project_name,
        "searches": searches,
        "from_pages": from_pages,
        "seed_count": len(seed_titles),
        "filter": filter_name,
        "full_list": full_list,
        "depth": depth,
        "limit": limit,
        "batch_size": batch_size,
        "sort": sort,
        "remote_count": remote_count,
        "fetched": len(fetched_pages),
        "skipped_nonpersistent": len(skipped_nonpersistent),
        "failed": len(failed_pages),
    }
    store.replace_project_with_cosense_pages(
        project_name,
        fetched_pages,
        display_name=display_name,
        source_export=source_export,
        acquisition_metadata=acquisition_metadata,
    )
    stats = store.stats()
    return {
        "project_url": project_url,
        "project": project_name,
        "modes": list(dict.fromkeys(modes)),
        "coverage": coverage,
        "limit": limit,
        "depth": depth,
        "search_results": search_results,
        "list_results": list_results,
        "fetched": len(fetched_pages),
        "updated": len(fetched_pages),
        "skipped_nonpersistent": skipped_nonpersistent,
        "failed_pages": failed_pages,
        "pages": [
            {
                "id": page.get("id"),
                "title": page.get("title"),
                "updated": page.get("updated"),
            }
            for page in fetched_pages
        ],
        "stats": stats,
    }


def _list_page_candidates(
    client: CosenseClient,
    project_url: str,
    *,
    project_name: str | None,
    sort: str,
    limit: int,
    batch_size: int,
    filter_name: str | None,
) -> tuple[list[str], str | None, int | None]:
    titles: list[str] = []
    remote_count: int | None = None
    skip = 0
    while len(titles) < limit:
        current_limit = min(batch_size, limit - len(titles))
        result = client.list_pages(
            project_url,
            sort=sort,
            limit=current_limit,
            skip=skip,
            filter_name=filter_name,
        )
        project_name = project_name or result.get("projectName")
        if remote_count is None and result.get("count") is not None:
            remote_count = int(result["count"])
        pages = result.get("pages") or []
        if not pages:
            break
        for page in pages:
            title = page.get("title")
            if title:
                titles.append(str(title))
                if len(titles) >= limit:
                    break
        skip += len(pages)
    return titles, project_name, remote_count


def _fetch_candidate_values(
    client: CosenseClient,
    project_url: str,
    values: list[str],
    *,
    fetched_pages: list[dict[str, Any]],
    fetched_norms: set[str],
    skipped_nonpersistent: list[dict[str, Any]],
    failed_pages: list[dict[str, Any]],
    limit: int,
) -> None:
    queued: set[str] = set()
    for value in values:
        if len(fetched_pages) >= limit:
            break
        queue_key = normalize_title(value)
        if queue_key in queued:
            continue
        queued.add(queue_key)
        _fetch_one_page(
            client,
            project_url,
            value,
            fetched_pages=fetched_pages,
            fetched_norms=fetched_norms,
            skipped_nonpersistent=skipped_nonpersistent,
            failed_pages=failed_pages,
        )


def _crawl_from_pages(
    client: CosenseClient,
    project_url: str,
    seeds: list[str],
    *,
    depth: int,
    limit: int,
    fetched_pages: list[dict[str, Any]],
    fetched_norms: set[str],
    skipped_nonpersistent: list[dict[str, Any]],
    failed_pages: list[dict[str, Any]],
) -> None:
    queue: list[tuple[str, int]] = [(seed, 0) for seed in seeds]
    queued = {normalize_title(seed) for seed in seeds}
    while queue and len(fetched_pages) < limit:
        value, current_depth = queue.pop(0)
        page = _fetch_one_page(
            client,
            project_url,
            value,
            fetched_pages=fetched_pages,
            fetched_norms=fetched_norms,
            skipped_nonpersistent=skipped_nonpersistent,
            failed_pages=failed_pages,
        )
        if page is None or current_depth >= depth:
            continue
        for link in outgoing_titles_from_page(page):
            norm = normalize_title(link)
            if norm in fetched_norms or norm in queued:
                continue
            queued.add(norm)
            queue.append((link, current_depth + 1))


def _fetch_one_page(
    client: CosenseClient,
    project_url: str,
    value: str,
    *,
    fetched_pages: list[dict[str, Any]],
    fetched_norms: set[str],
    skipped_nonpersistent: list[dict[str, Any]],
    failed_pages: list[dict[str, Any]],
) -> dict[str, Any] | None:
    page_url = page_url_for_value(project_url, value)
    try:
        page = client.read_page(page_url)
    except Exception as error:  # cosense CLI/network failures should not abort the whole slice.
        failed_pages.append({"title_or_url": value, "url": page_url, "error": str(error)})
        return None

    title = page.get("title")
    if not title:
        failed_pages.append({"title_or_url": value, "url": page_url, "error": "readPage result has no title"})
        return None
    if not page.get("persistent", True):
        skipped_nonpersistent.append({"title": title, "url": page_url})
        return None

    norm = normalize_title(str(title))
    if norm in fetched_norms:
        return page
    fetched_norms.add(norm)
    fetched_pages.append(page)
    return page


def outgoing_titles_from_page(page: dict[str, Any]) -> list[str]:
    titles: list[str] = []
    seen: set[str] = set()
    for title in page.get("links") or []:
        norm = normalize_title(str(title))
        if norm and norm not in seen:
            seen.add(norm)
            titles.append(str(title))
    for line in page.get("lines") or []:
        text = str(line.get("text", ""))
        for title in parse_cosense_links(text):
            norm = normalize_title(title)
            if norm and norm not in seen:
                seen.add(norm)
                titles.append(title)
    return titles


def project_name_from_url(project_url: str) -> str:
    parsed = urlparse(project_url)
    parts = [part for part in parsed.path.split("/") if part]
    if parts:
        return unquote(parts[0])
    return "cosense"


def page_url_for_value(project_url: str, value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("http://") or stripped.startswith("https://"):
        return stripped
    return page_url_for_title(project_url, stripped)


def page_url_for_title(project_url: str, title: str) -> str:
    return f"{project_url.rstrip('/')}/{quote(title, safe='')}"
