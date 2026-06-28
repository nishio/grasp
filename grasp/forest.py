from __future__ import annotations

from pathlib import Path
import re
from time import perf_counter
from typing import Any

from .markdown import MarkdownCollisionError
from .sqlite_store import SQLiteStore, import_markdown_folder_to_sqlite, refresh_store_cross_project_derivatives


YAML_KEY_RE = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*:\s*(.*?)\s*$")
YAML_LIST_KEY_RE = re.compile(r"^\s*-\s*(?:(?P<key>[A-Za-z0-9_-]+)\s*:\s*(?P<value>.*?))?\s*$")


def parse_wiki_registry(registry_path: str | Path) -> list[dict[str, str]]:
    path = Path(registry_path).expanduser()
    if not path.exists():
        raise ValueError(f"wiki registry does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"wiki registry must be a file: {path}")

    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    in_wikis = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = _strip_yaml_comment(raw_line).rstrip()
        if not line.strip():
            continue
        key_match = YAML_KEY_RE.match(line)
        if key_match and not line.lstrip().startswith("-"):
            key = key_match.group(1)
            if key == "wikis":
                in_wikis = True
                current = None
            elif in_wikis and current is not None and line.startswith((" ", "\t")):
                current[key] = _parse_yaml_scalar(key_match.group(2))
            elif in_wikis and not line.startswith((" ", "\t")):
                in_wikis = False
            continue
        if not in_wikis:
            continue

        list_match = YAML_LIST_KEY_RE.match(line)
        if list_match:
            current = {}
            entries.append(current)
            key = list_match.group("key")
            if key is not None:
                current[key] = _parse_yaml_scalar(list_match.group("value") or "")
            continue

        if current is not None:
            child_match = YAML_KEY_RE.match(line)
            if child_match:
                current[child_match.group(1)] = _parse_yaml_scalar(child_match.group(2))

    if not entries:
        raise ValueError(f"wiki registry has no wikis entries: {path}")
    return entries


def import_forest_from_registry(
    registry_path: str | Path,
    store_path: str | Path,
    *,
    wiki_dir: str = "wiki",
    exclude_dirs: tuple[str, ...] = (),
    ambiguity_limit: int = 50,
    ambiguity_candidate_limit: int = 5,
) -> dict[str, Any]:
    registry = Path(registry_path).expanduser()
    store = Path(store_path).expanduser()
    entries = parse_wiki_registry(registry)
    started = perf_counter()
    projects: list[dict[str, Any]] = []
    seen_project_names: set[str] = set()
    aggregate = {
        "projects": 0,
        "pages": 0,
        "lines": 0,
        "edges": 0,
        "unresolved_targets": 0,
    }

    for index, entry in enumerate(entries):
        project_name = entry.get("name") or ""
        duplicate_project = bool(project_name and project_name in seen_project_names)
        if project_name:
            seen_project_names.add(project_name)
        result = _import_forest_entry(
            index=index,
            entry=entry,
            registry_path=registry,
            store_path=store,
            wiki_dir=wiki_dir,
            exclude_dirs=exclude_dirs,
            duplicate_project=duplicate_project,
        )
        projects.append(result)
        if result["status"] == "success":
            aggregate["projects"] += 1
            for key in ("pages", "lines", "edges", "unresolved_targets"):
                aggregate[key] += int(result.get(key) or 0)

    success_count = sum(1 for project in projects if project["status"] == "success")
    failure_count = sum(1 for project in projects if project["status"] == "failure")
    missing_count = sum(1 for project in projects if project["status"] == "missing")
    skipped_count = sum(1 for project in projects if project["status"] == "skipped")
    if success_count:
        refresh_store_cross_project_derivatives(store)
        store_reader = SQLiteStore(store)
        try:
            stats = store_reader.stats()
            aggregate = {
                "projects": int(stats.get("project_count") or 0),
                "pages": int(stats.get("pages") or 0),
                "lines": int(stats.get("lines") or 0),
                "edges": int(stats.get("edges") or 0),
                "unresolved_targets": int(stats.get("unresolved_targets") or 0),
            }
        finally:
            store_reader.close()
    ambiguities = _forest_ambiguities(store, ambiguity_limit, ambiguity_candidate_limit)
    return {
        "registry": str(registry),
        "store": str(store),
        "wiki_dir": wiki_dir,
        "markdown_exclude_dirs": list(exclude_dirs),
        "entry_count": len(entries),
        "success_count": success_count,
        "failure_count": failure_count,
        "missing_count": missing_count,
        "skipped_count": skipped_count,
        "aggregate": aggregate,
        "projects": projects,
        "ambiguities": ambiguities,
        "wall_seconds": round(perf_counter() - started, 3),
    }


def _import_forest_entry(
    *,
    index: int,
    entry: dict[str, str],
    registry_path: Path,
    store_path: Path,
    wiki_dir: str,
    exclude_dirs: tuple[str, ...],
    duplicate_project: bool = False,
) -> dict[str, Any]:
    name = entry.get("name") or ""
    root_raw = entry.get("path") or ""
    base: dict[str, Any] = {
        "index": index,
        "name": name or None,
        "project": name or None,
        "root_path": root_raw or None,
        "wiki_path": None,
    }
    if not name or not root_raw:
        return {
            **base,
            "status": "skipped",
            "diagnostic": {
                "type": "registry_entry_invalid",
                "message": "registry entry requires both name and path",
            },
        }

    root = _registry_relative_path(root_raw, registry_path.parent)
    wiki_path = _wiki_path(root, wiki_dir)
    base.update(
        {
            "root_path": str(root),
            "wiki_path": str(wiki_path),
        }
    )
    if duplicate_project:
        return {
            **base,
            "status": "failure",
            "diagnostic": {
                "type": "registry_project_duplicate",
                "message": f"registry project name is duplicated: {name}",
            },
        }
    if not wiki_path.exists():
        return {
            **base,
            "status": "missing",
            "diagnostic": {
                "type": "wiki_folder_missing",
                "message": f"Markdown wiki folder does not exist: {wiki_path}",
            },
        }
    if not wiki_path.is_dir():
        return {
            **base,
            "status": "failure",
            "diagnostic": {
                "type": "wiki_folder_not_directory",
                "message": f"Markdown wiki path is not a directory: {wiki_path}",
            },
        }

    try:
        stats = import_markdown_folder_to_sqlite(
            wiki_path,
            store_path,
            project_name=name,
            exclude_dirs=exclude_dirs,
            defer_weak_edges=True,
        )
    except MarkdownCollisionError as error:
        return {
            **base,
            "status": "failure",
            "error": str(error),
            "diagnostic": error.to_diagnostic(),
        }
    except Exception as error:
        return {
            **base,
            "status": "failure",
            "error": str(error),
            "diagnostic": {
                "type": type(error).__name__,
                "message": str(error),
            },
        }

    return {
        **base,
        "status": "success",
        "pages": stats["pages"],
        "lines": stats["lines"],
        "edges": stats["edges"],
        "unresolved_targets": stats["unresolved_targets"],
        "markdown_import": stats.get("markdown_import"),
    }


def _forest_ambiguities(
    store_path: Path,
    ambiguity_limit: int,
    ambiguity_candidate_limit: int,
) -> dict[str, Any] | None:
    if not store_path.exists():
        return None
    store = SQLiteStore(store_path)
    try:
        if not store.schema_ok():
            return {
                "diagnostic": {
                    "type": "schema_mismatch",
                    "schema_version": store.schema_version(),
                }
            }
        return store.ambiguities(limit=ambiguity_limit, candidate_limit=ambiguity_candidate_limit)
    finally:
        store.close()


def _registry_relative_path(raw_path: str, registry_dir: Path) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = registry_dir / path
    return path


def _wiki_path(root: Path, wiki_dir: str) -> Path:
    if wiki_dir in ("", "."):
        return root
    return root / wiki_dir


def _parse_yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _strip_yaml_comment(line: str) -> str:
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            if index == 0 or line[index - 1].isspace():
                return line[:index]
    return line
