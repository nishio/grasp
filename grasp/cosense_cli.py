from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import subprocess
import time
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
class CosenseCliError(RuntimeError):
    command: list[str]
    error_class: str
    message: str
    returncode: int | None = None
    stderr: str = ""
    stdout: str = ""

    def __str__(self) -> str:
        details = self.message
        stderr_line = first_nonempty_line(self.stderr)
        if stderr_line and stderr_line not in details:
            details = f"{details}: {stderr_line}"
        if self.returncode is not None:
            return f"{self.error_class} (exit {self.returncode}): {details}"
        return f"{self.error_class}: {details}"


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
        try:
            completed = subprocess.run(command, check=True, text=True, capture_output=True)
        except FileNotFoundError as error:
            raise CosenseCliError(
                command=command,
                error_class="command-not-found",
                message=f"command not found: {command[0]}",
            ) from error
        except subprocess.CalledProcessError as error:
            error_class = classify_cosense_cli_failure(
                returncode=error.returncode,
                stderr=error.stderr or "",
                stdout=error.stdout or "",
            )
            raise CosenseCliError(
                command=command,
                error_class=error_class,
                message=f"cosense CLI command failed: {' '.join(command)}",
                returncode=error.returncode,
                stderr=error.stderr or "",
                stdout=error.stdout or "",
            ) from error
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise CosenseCliError(
                command=command,
                error_class="invalid-json",
                message="cosense CLI returned non-JSON output",
                stdout=completed.stdout,
                stderr=completed.stderr,
            ) from error


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

    criteria = acquisition_criteria(
        project_url=project_url,
        searches=searches,
        from_pages=from_pages,
        seed_titles=seed_titles,
        filter_name=filter_name,
        full_list=full_list,
        depth=depth,
        limit=limit,
        batch_size=batch_size,
        sort=sort,
    )
    criteria_fingerprint = acquisition_criteria_fingerprint(criteria)
    modes: list[str] = []
    project_name = project
    remote_project_name: str | None = None
    remote_count: int | None = None
    candidate_entries: list[dict[str, Any]] = []
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
                candidate_entries.append(candidate_entry(str(title), source="search", metadata=page))

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
        candidate_entries.extend(pages)
        list_results.append(
            {
                "mode": "full-list",
                "count": remote_count,
                "returned": len(pages),
                "window": candidate_window(pages, sort=sort),
            }
        )

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
        candidate_entries.extend(pages)
        list_results.append(
            {
                "mode": "filter",
                "filter": filter_name,
                "count": filter_count,
                "returned": len(pages),
                "window": candidate_window(pages, sort=sort),
            }
        )

    if seed_titles:
        modes.append("seed-file")
        candidate_entries.extend(candidate_entry(title, source="seed-file") for title in seed_titles)

    fetched_pages: list[dict[str, Any]] = []
    fetched_norms: set[str] = set()
    skipped_nonpersistent: list[dict[str, Any]] = []
    failed_pages: list[dict[str, Any]] = []
    reused_pages: list[dict[str, Any]] = []

    remote_project_name = remote_project_name or project_name_from_url(project_url)
    project_name = project_name or f"{remote_project_name}:acquire"
    previous_acquisition = store.project_acquisition_metadata_by_name(project_name)
    same_criteria = previous_acquisition is not None and previous_acquisition.get("criteria_fingerprint") == criteria_fingerprint

    _fetch_candidate_entries(
        client,
        store,
        project_url,
        candidate_entries,
        project_name=project_name,
        previous_acquisition=previous_acquisition,
        same_criteria=same_criteria,
        fetched_pages=fetched_pages,
        fetched_norms=fetched_norms,
        skipped_nonpersistent=skipped_nonpersistent,
        failed_pages=failed_pages,
        reused_pages=reused_pages,
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

    display_name = remote_project_name if project is not None else project_name
    source_export = f"cosense:{project_url}"
    coverage = "full-list" if full_list and remote_count is not None and len(fetched_pages) >= remote_count else "partial"
    candidate_count = len(
        dict.fromkeys(
            normalize_title(str(value))
            for value in [
                *(entry.get("title") or entry.get("value") for entry in candidate_entries),
                *from_pages,
            ]
        )
    )
    remote_fetched = max(0, len(fetched_pages) - len(reused_pages))
    window = candidate_window(candidate_entries, sort=sort)
    diagnostic = acquire_diagnostic(
        candidate_count=candidate_count,
        fetched_count=len(fetched_pages),
        failed_pages=failed_pages,
        skipped_nonpersistent=skipped_nonpersistent,
    )
    acquisition_metadata = {
        "mode": "+".join(dict.fromkeys(modes)),
        "coverage": coverage,
        "acquired_at": int(time.time()),
        "project_url": project_url,
        "remote_project": remote_project_name,
        "criteria": criteria,
        "criteria_fingerprint": criteria_fingerprint,
        "same_criteria_as_previous": same_criteria,
        "searches": searches,
        "from_pages": from_pages,
        "seed_count": len(seed_titles),
        "seed_fingerprint": sequence_fingerprint(seed_titles),
        "filter": filter_name,
        "full_list": full_list,
        "depth": depth,
        "limit": limit,
        "batch_size": batch_size,
        "sort": sort,
        "remote_count": remote_count,
        "candidate_count": candidate_count,
        "candidate_window": window,
        "fetched": len(fetched_pages),
        "remote_fetched": remote_fetched,
        "reused": len(reused_pages),
        "skipped_nonpersistent": len(skipped_nonpersistent),
        "failed": len(failed_pages),
        "diagnostic_type": diagnostic.get("type") if diagnostic else None,
        "error_classes": diagnostic.get("error_classes") if diagnostic else {},
        "page_manifest": acquisition_page_manifest(fetched_pages),
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
        "criteria_fingerprint": criteria_fingerprint,
        "candidate_window": window,
        "fetched": len(fetched_pages),
        "updated": remote_fetched,
        "remote_fetched": remote_fetched,
        "reused": len(reused_pages),
        "same_criteria_as_previous": same_criteria,
        "skipped_nonpersistent": skipped_nonpersistent,
        "failed_pages": failed_pages,
        "diagnostic": diagnostic,
        "pages": [
            {
                "id": page.get("id"),
                "title": page.get("title"),
                "updated": page.get("updated"),
                "reused": normalize_title(str(page.get("title", ""))) in {
                    str(item.get("normalized_title"))
                    for item in reused_pages
                },
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
) -> tuple[list[dict[str, Any]], str | None, int | None]:
    candidates: list[dict[str, Any]] = []
    remote_count: int | None = None
    skip = 0
    while len(candidates) < limit:
        current_limit = min(batch_size, limit - len(candidates))
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
                candidates.append(candidate_entry(str(title), source="listPages", metadata=page))
                if len(candidates) >= limit:
                    break
        skip += len(pages)
    return candidates, project_name, remote_count


def _fetch_candidate_entries(
    client: CosenseClient,
    store: SQLiteStore,
    project_url: str,
    entries: list[dict[str, Any]],
    *,
    project_name: str,
    previous_acquisition: dict[str, Any] | None,
    same_criteria: bool,
    fetched_pages: list[dict[str, Any]],
    fetched_norms: set[str],
    skipped_nonpersistent: list[dict[str, Any]],
    failed_pages: list[dict[str, Any]],
    reused_pages: list[dict[str, Any]],
    limit: int,
) -> None:
    queued: set[str] = set()
    for entry in entries:
        if len(fetched_pages) >= limit:
            break
        value = str(entry.get("value") or entry.get("title") or "")
        queue_key = normalize_title(value)
        if queue_key in queued:
            continue
        queued.add(queue_key)
        reusable_page = reusable_candidate_page(
            store,
            project_name,
            entry,
            previous_acquisition=previous_acquisition,
            same_criteria=same_criteria,
        )
        if reusable_page is not None:
            norm = normalize_title(str(reusable_page.get("title", "")))
            if norm in fetched_norms:
                continue
            fetched_norms.add(norm)
            fetched_pages.append(reusable_page)
            reused_pages.append(
                {
                    "id": reusable_page.get("id"),
                    "title": reusable_page.get("title"),
                    "normalized_title": norm,
                    "updated": reusable_page.get("updated"),
                }
            )
            continue
        _fetch_one_page(
            client,
            project_url,
            value,
            fetched_pages=fetched_pages,
            fetched_norms=fetched_norms,
            skipped_nonpersistent=skipped_nonpersistent,
            failed_pages=failed_pages,
        )


def acquisition_criteria(
    *,
    project_url: str,
    searches: list[str],
    from_pages: list[str],
    seed_titles: list[str],
    filter_name: str | None,
    full_list: bool,
    depth: int,
    limit: int,
    batch_size: int,
    sort: str,
) -> dict[str, Any]:
    return {
        "project_url": canonical_project_url(project_url),
        "searches": list(searches),
        "from_pages": list(from_pages),
        "seed_titles": list(seed_titles),
        "filter": filter_name,
        "full_list": full_list,
        "depth": depth,
        "limit": limit,
        "batch_size": batch_size,
        "sort": sort,
    }


def acquisition_criteria_fingerprint(criteria: dict[str, Any]) -> str:
    return stable_json_fingerprint(criteria)


def sequence_fingerprint(values: list[str]) -> str:
    return stable_json_fingerprint(list(values))


def stable_json_fingerprint(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_project_url(project_url: str) -> str:
    return project_url.rstrip("/") + "/"


def candidate_entry(value: str, *, source: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = metadata or {}
    title = str(metadata.get("title") or value)
    updated = metadata.get("updated")
    return {
        "value": str(value),
        "source": source,
        "id": metadata.get("id"),
        "title": title,
        "normalized_title": normalize_title(title),
        "updated": updated,
        "updated_epoch": parse_cosense_time(updated),
        "pin": metadata.get("pin"),
    }


def candidate_window(entries: list[dict[str, Any]], *, sort: str) -> dict[str, Any]:
    source_counts: dict[str, int] = {}
    updated_entries = []
    for entry in entries:
        source = str(entry.get("source") or "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
        updated_epoch = entry.get("updated_epoch")
        if updated_epoch is not None:
            updated_entries.append(entry)

    updated_range: dict[str, Any] | None = None
    if updated_entries:
        newest = max(updated_entries, key=lambda entry: int(entry["updated_epoch"]))
        oldest = min(updated_entries, key=lambda entry: int(entry["updated_epoch"]))
        updated_range = {
            "newest_epoch": newest.get("updated_epoch"),
            "newest": newest.get("updated"),
            "newest_title": newest.get("title"),
            "oldest_epoch": oldest.get("updated_epoch"),
            "oldest": oldest.get("updated"),
            "oldest_title": oldest.get("title"),
        }

    return {
        "sort": sort,
        "candidate_count": len(entries),
        "candidates_with_updated": len(updated_entries),
        "source_counts": source_counts,
        "updated_range": updated_range,
    }


def reusable_candidate_page(
    store: SQLiteStore,
    project_name: str,
    entry: dict[str, Any],
    *,
    previous_acquisition: dict[str, Any] | None,
    same_criteria: bool,
) -> dict[str, Any] | None:
    if not same_criteria or previous_acquisition is None:
        return None
    updated_epoch = entry.get("updated_epoch")
    if updated_epoch is None:
        return None
    norm_title = str(entry.get("normalized_title") or normalize_title(str(entry.get("title") or entry.get("value") or "")))
    page_manifest = previous_acquisition.get("page_manifest")
    if not isinstance(page_manifest, dict):
        return None
    previous_page = page_manifest.get(norm_title)
    if not isinstance(previous_page, dict):
        return None
    if _int_or_none(previous_page.get("updated")) != int(updated_epoch):
        return None
    stored_page = store.cosense_page_dict_by_norm(project_name, norm_title)
    if stored_page is None:
        return None
    if parse_cosense_time(stored_page.get("updated")) != int(updated_epoch):
        return None
    return stored_page


def acquisition_page_manifest(pages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for page in pages:
        title = page.get("title")
        if not title:
            continue
        norm_title = normalize_title(str(title))
        manifest[norm_title] = {
            "id": page.get("id"),
            "title": title,
            "updated": parse_cosense_time(page.get("updated")),
        }
    return manifest


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def failed_page_entry(value: str, page_url: str, error: Exception) -> dict[str, Any]:
    if isinstance(error, CosenseCliError):
        entry: dict[str, Any] = {
            "title_or_url": value,
            "url": page_url,
            "error": str(error),
            "error_class": error.error_class,
        }
        if error.returncode is not None:
            entry["returncode"] = error.returncode
        stderr_line = first_nonempty_line(error.stderr)
        if stderr_line:
            entry["stderr"] = stderr_line
        return entry
    return {
        "title_or_url": value,
        "url": page_url,
        "error": str(error),
        "error_class": classify_exception(error),
    }


def acquire_diagnostic(
    *,
    candidate_count: int,
    fetched_count: int,
    failed_pages: list[dict[str, Any]],
    skipped_nonpersistent: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not failed_pages and not skipped_nonpersistent:
        return None

    error_classes = count_error_classes(failed_pages)
    if candidate_count > 0 and fetched_count == 0 and failed_pages:
        diagnostic_type = "all_failed"
        severity = "warning"
        message = "all candidate pages failed to fetch; acquired corpus is empty"
    elif candidate_count > 0 and fetched_count == 0 and skipped_nonpersistent:
        diagnostic_type = "no_persistent_pages"
        severity = "warning"
        message = "all fetched candidates were nonpersistent; acquired corpus is empty"
    elif skipped_nonpersistent and not failed_pages:
        diagnostic_type = "partial_nonpersistent"
        severity = "warning"
        message = "some candidate pages were nonpersistent and skipped"
    else:
        diagnostic_type = "partial_failures"
        severity = "warning"
        message = "some candidate pages failed to fetch"

    return {
        "type": diagnostic_type,
        "severity": severity,
        "message": message,
        "candidate_count": candidate_count,
        "fetched": fetched_count,
        "failed": len(failed_pages),
        "skipped_nonpersistent": len(skipped_nonpersistent),
        "error_classes": error_classes,
        "next_actions": acquire_next_actions(error_classes),
    }


def count_error_classes(failed_pages: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for page in failed_pages:
        error_class = str(page.get("error_class") or "unknown")
        counts[error_class] = counts.get(error_class, 0) + 1
    return counts


def acquire_next_actions(error_classes: dict[str, int]) -> list[str]:
    actions: list[str] = []
    if "command-not-found" in error_classes:
        actions.append("Install @helpfeel/cosense-cli or pass --cosense-command pointing to a working cosense wrapper.")
    if "command-env" in error_classes:
        actions.append("Ensure node is on PATH for the cosense CLI; a symlinked cosense binary can still fail if env cannot find node.")
    if "permission" in error_classes:
        actions.append("Check that the cosense CLI is logged in and that the hosted project/pages are readable.")
    if "page-not-found" in error_classes:
        actions.append("Check seed titles/URLs; some referenced pages may be moved, deleted, or inaccessible.")
    if not actions and error_classes:
        actions.append("Inspect failed_pages[].error and retry with a smaller seed file or known readable page.")
    return actions


def classify_exception(error: Exception) -> str:
    if isinstance(error, FileNotFoundError):
        return "command-not-found"
    return "unknown"


def classify_cosense_cli_failure(*, returncode: int, stderr: str, stdout: str) -> str:
    text = f"{stderr}\n{stdout}".casefold()
    if returncode == 127 or "env: node" in text or "node: no such file" in text or "node: command not found" in text:
        return "command-env"
    if "forbidden" in text or "unauthorized" in text or "permission" in text or "login" in text or "not logged in" in text:
        return "permission"
    if "not found" in text or "404" in text:
        return "page-not-found"
    return "command-failed"


def first_nonempty_line(value: str) -> str:
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


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
        failed_pages.append(failed_page_entry(value, page_url, error))
        return None

    title = page.get("title")
    if not title:
        failed_pages.append(
            {
                "title_or_url": value,
                "url": page_url,
                "error": "readPage result has no title",
                "error_class": "invalid-page",
            }
        )
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
