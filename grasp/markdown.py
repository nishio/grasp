from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

from .cosense import Edge, Line, Page, normalize_title, parse_cosense_hash_tag


@dataclass(frozen=True)
class MarkdownMetadata:
    title: str | None
    page_id: str | None
    aliases: list[str]
    tags: list[tuple[str, int]]
    graph_role: str


@dataclass(frozen=True)
class MarkdownPageRecord:
    relative_path: Path
    page: Page
    aliases: list[str]
    tags: list[tuple[str, int]]
    graph_role: str
    source_hash: str
    mtime_ns: int


@dataclass(frozen=True)
class MarkdownCollisionEntry:
    path: str
    title: str
    page_id: str
    handle: str
    source: str
    graph_role: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "title": self.title,
            "page_id": self.page_id,
            "handle": self.handle,
            "source": self.source,
            "graph_role": self.graph_role,
        }


@dataclass(frozen=True)
class MarkdownCollision:
    kind: str
    key: str
    entries: tuple[MarkdownCollisionEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "key": self.key,
            "paths": [entry.path for entry in self.entries],
            "entries": [entry.to_dict() for entry in self.entries],
        }


class MarkdownCollisionError(ValueError):
    def __init__(self, collisions: list[MarkdownCollision] | tuple[MarkdownCollision, ...]):
        self.collisions = tuple(collisions)
        super().__init__(format_markdown_collision_message(self.collisions))

    def to_diagnostic(self) -> dict[str, Any]:
        counts: dict[str, int] = defaultdict(int)
        for collision in self.collisions:
            counts[collision.kind] += 1
        return {
            "type": "markdown_collision",
            "severity": "error",
            "message": str(self),
            "collision_counts": dict(sorted(counts.items())),
            "collisions": [collision.to_dict() for collision in self.collisions],
            "next_actions": [
                "Inspect collisions[].entries[].path to identify the duplicate title, id, or alias source.",
                "If a collision comes from generated or draft artifacts, retry with --markdown-exclude-dir <name>.",
                "If the same visible name intentionally refers to multiple pages, keep page identity separate from display name before softening import.",
            ],
        }


@dataclass(frozen=True)
class MarkdownMirror:
    pages: list[Page]
    edges: list[Edge]
    title_collisions: dict[str, list[str]]
    title_aliases: dict[str, str]
    records: tuple[MarkdownPageRecord, ...]
    file_manifest: dict[str, Any]
    project_name: str
    display_name: str
    source_folder: Path

    @classmethod
    def from_folder(
        cls,
        folder: str | Path,
        *,
        exclude_dirs: tuple[str, ...] = (),
    ) -> "MarkdownMirror":
        root = Path(folder)
        if not root.exists():
            raise ValueError(f"Markdown folder does not exist: {root}")
        if not root.is_dir():
            raise ValueError(f"Markdown source must be a folder: {root}")

        normalized_exclude_dirs = normalize_exclude_dirs(exclude_dirs)
        markdown_files = list(iter_markdown_files(root, exclude_dirs=normalized_exclude_dirs))
        if not markdown_files:
            raise ValueError(f"Markdown folder has no .md files: {root}")

        records = [markdown_page_record_from_file(root, path) for path in markdown_files]

        id_collisions = markdown_id_collisions(records)
        if id_collisions:
            raise MarkdownCollisionError(id_collisions)

        title_collisions = markdown_title_collisions(records)
        title_aliases = build_title_aliases(records)
        pages = [record.page for record in records]
        edges = [edge for record in records for edge in markdown_edges_for_record(record)]

        return cls(
            pages=pages,
            edges=edges,
            title_collisions={collision.key: [entry.path for entry in collision.entries] for collision in title_collisions},
            title_aliases={
                alias_norm: title
                for alias_norm, title in title_aliases.items()
                if normalize_title(title) != alias_norm
            },
            records=tuple(records),
            file_manifest=markdown_file_manifest(records, exclude_dirs=normalized_exclude_dirs),
            project_name=root.name,
            display_name=root.name,
            source_folder=root,
        )


def markdown_page_record_from_file(root: str | Path, path: str | Path) -> MarkdownPageRecord:
    root = Path(root)
    path = Path(path)
    relative_path = path.relative_to(root)
    stat = path.stat()
    raw_bytes = path.read_bytes()
    source_hash = hashlib.sha1(raw_bytes).hexdigest()
    text_lines = raw_bytes.decode("utf-8").splitlines()
    metadata = parse_frontmatter(text_lines)
    file_title = markdown_title(path)
    h1_title = first_markdown_h1_title(text_lines)
    page_id = metadata.page_id or markdown_page_id(relative_path)
    title = metadata.title or h1_title or file_title
    norm_title = normalize_title(title)
    updated = int(stat.st_mtime)
    lines = tuple(
        Line(
            line_id=f"{page_id}:{line_index}",
            index=line_index,
            text=text,
            updated=updated,
        )
        for line_index, text in enumerate(text_lines)
    )
    page = Page(
        id=page_id,
        title=title,
        norm_title=norm_title,
        created=None,
        updated=updated,
        views=0,
        lines=lines,
    )
    aliases = list(dict.fromkeys([file_title, *metadata.aliases]))
    return MarkdownPageRecord(
        relative_path=relative_path,
        page=page,
        aliases=[alias for alias in aliases if normalize_title(alias) != norm_title],
        tags=metadata.tags,
        graph_role=markdown_graph_role(relative_path, metadata),
        source_hash=source_hash,
        mtime_ns=stat.st_mtime_ns,
    )


def markdown_catalog_record_from_file(root: str | Path, path: str | Path) -> MarkdownPageRecord:
    root = Path(root)
    path = Path(path)
    relative_path = path.relative_to(root)
    stat = path.stat()
    file_title = markdown_title(path)
    page_id = markdown_page_id(relative_path)
    title = file_title
    norm_title = normalize_title(title)
    updated = int(stat.st_mtime)
    page = Page(
        id=page_id,
        title=title,
        norm_title=norm_title,
        created=None,
        updated=updated,
        views=0,
        lines=(),
    )
    return MarkdownPageRecord(
        relative_path=relative_path,
        page=page,
        aliases=[],
        tags=[],
        graph_role=markdown_graph_role(relative_path, parse_frontmatter([])),
        source_hash="",
        mtime_ns=stat.st_mtime_ns,
    )


def markdown_edges_for_record(record: MarkdownPageRecord) -> list[Edge]:
    if not markdown_graph_role_emits_edges(record.graph_role):
        return []
    page = record.page
    edges: list[Edge] = []
    line_target_norms: dict[str, set[str]] = defaultdict(set)
    in_code_fence = False
    for line in page.lines:
        links, in_code_fence = parse_markdown_line_links(
            line.text,
            in_code_fence=in_code_fence,
        )
        for target_title in links:
            edges.append(markdown_edge(page, line, target_title))
            line_target_norms.setdefault(line.line_id, set()).add(normalize_title(target_title))
    for tag, line_index in record.tags:
        if 0 <= line_index < len(page.lines):
            line = page.lines[line_index]
        else:
            line = page.lines[0] if page.lines else Line(line_id=f"{page.id}:0", index=0, text="")
        if normalize_title(tag) in line_target_norms.get(line.line_id, set()):
            continue
        edges.append(markdown_edge(page, line, tag))
        line_target_norms.setdefault(line.line_id, set()).add(normalize_title(tag))
    return edges


def normalize_exclude_dirs(exclude_dirs: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized: set[str] = set()
    for raw_part in exclude_dirs:
        part = raw_part.strip()
        if not part:
            continue
        if part in {".", ".."} or "/" in part or "\\" in part:
            raise ValueError(f"Markdown exclude dir must be a directory basename, not a path: {raw_part}")
        normalized.add(part)
    return tuple(sorted(normalized))


def iter_markdown_files(root: Path, *, exclude_dirs: tuple[str, ...] = ()) -> list[Path]:
    excluded = set(exclude_dirs)
    return [
        path
        for path in sorted(root.rglob("*.md"))
        if not any(part.startswith(".") for part in path.relative_to(root).parts)
        and not any(part in excluded for part in path.relative_to(root).parts[:-1])
    ]


def markdown_page_id(relative_path: Path) -> str:
    key = relative_path.as_posix().encode("utf-8")
    return hashlib.sha1(key).hexdigest()[:24]


def markdown_title(path: Path) -> str:
    return path.stem


def first_markdown_h1_title(lines: list[str]) -> str | None:
    in_frontmatter = bool(lines and lines[0].strip() == "---")
    in_code_fence = False
    for line in lines[1:] if in_frontmatter else lines:
        stripped = line.strip()
        if in_frontmatter:
            if stripped in {"---", "..."}:
                in_frontmatter = False
            continue
        if is_code_fence(line.lstrip()):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        if title := parse_markdown_h1_title(line):
            return title
    return None


def parse_markdown_h1_title(line: str) -> str | None:
    stripped = line.lstrip()
    leading_spaces = len(line) - len(stripped)
    if leading_spaces > 3 or not stripped.startswith("#"):
        return None
    if stripped.startswith("##"):
        return None
    if len(stripped) == 1 or not stripped[1].isspace():
        return None
    title = stripped[1:].strip()
    if title.endswith("#"):
        without_closing = title.rstrip("#")
        if not without_closing or without_closing[-1].isspace():
            title = without_closing.rstrip()
    return title or None


def markdown_file_manifest(records: list[MarkdownPageRecord], *, exclude_dirs: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "version": 3,
        "exclude_dirs": list(exclude_dirs),
        "files": {
            record.relative_path.as_posix(): {
                "page_id": record.page.id,
                "title": record.page.title,
                "norm_title": record.page.norm_title,
                "aliases": record.aliases,
                "graph_role": record.graph_role,
                "hash": record.source_hash,
                "mtime_ns": record.mtime_ns,
            }
            for record in records
        },
    }


def markdown_projection_text(
    relative_path: str | Path,
    *,
    page_id: str,
    title: str,
    aliases: list[str],
    lines: list[str],
) -> str:
    fields = markdown_projection_frontmatter_fields(
        relative_path,
        page_id=page_id,
        title=title,
        aliases=aliases,
        lines=lines,
    )
    if not fields:
        return markdown_lines_to_text(lines)
    if markdown_frontmatter_matches(lines, fields):
        return markdown_lines_to_text(lines)
    return markdown_lines_to_text(merge_markdown_projection_frontmatter(lines, fields))


def markdown_projection_frontmatter_fields(
    relative_path: str | Path,
    *,
    page_id: str,
    title: str,
    aliases: list[str],
    lines: list[str],
) -> dict[str, Any]:
    aliases = list(dict.fromkeys(str(alias) for alias in aliases if str(alias).strip()))
    _, body_lines = split_markdown_frontmatter(lines)
    h1_title = first_markdown_h1_title(body_lines)
    page_id = str(page_id)
    title = str(title)
    derived_alias_norms = {
        normalize_title(title),
        normalize_title(markdown_title(Path(relative_path))),
    }
    meaningful_aliases = [
        alias for alias in aliases if normalize_title(alias) not in derived_alias_norms
    ]
    identity_needs_frontmatter = page_id != markdown_page_id(Path(relative_path))
    title_needs_frontmatter = bool(title) and normalize_title(title) != normalize_title(h1_title or "")
    alias_needs_frontmatter = bool(meaningful_aliases)
    if (
        not identity_needs_frontmatter
        and not title_needs_frontmatter
        and not alias_needs_frontmatter
    ):
        return {}
    return {
        "id": page_id,
        "title": title,
        "aliases": meaningful_aliases,
    }


def markdown_frontmatter_matches(lines: list[str], fields: dict[str, Any]) -> bool:
    frontmatter, _ = split_markdown_frontmatter(lines)
    if not frontmatter:
        return False
    metadata = parse_frontmatter(lines)
    return (
        metadata.page_id == fields.get("id")
        and metadata.title == fields.get("title")
        and metadata.aliases == (fields.get("aliases") or [])
    )


def merge_markdown_projection_frontmatter(lines: list[str], fields: dict[str, Any]) -> list[str]:
    frontmatter, body_lines = split_markdown_frontmatter(lines)
    if not frontmatter:
        return [*render_markdown_frontmatter(fields), *body_lines]
    replaced_keys = set(fields)
    if "aliases" in fields:
        replaced_keys.add("alias")
    inner = frontmatter_without_keys(frontmatter[1:-1], replaced_keys)
    return [frontmatter[0], *inner, *render_markdown_frontmatter(fields)[1:-1], frontmatter[-1], *body_lines]


def frontmatter_without_keys(lines: list[str], keys: set[str]) -> list[str]:
    filtered: list[str] = []
    skipping_key = False
    for line in lines:
        stripped = line.strip()
        is_continuation = bool(line[:1].isspace())
        if is_continuation:
            if not skipping_key:
                filtered.append(line)
            continue
        if not stripped:
            skipping_key = False
            filtered.append(line)
            continue
        if stripped.startswith("#"):
            skipping_key = False
            filtered.append(line)
            continue
        if ":" not in line:
            skipping_key = False
            filtered.append(line)
            continue
        key, _ = line.split(":", 1)
        skipping_key = normalize_frontmatter_key(key) in keys
        if not skipping_key:
            filtered.append(line)
    return filtered


def split_markdown_frontmatter(lines: list[str]) -> tuple[list[str], list[str]]:
    if not lines or lines[0].strip() != "---":
        return [], list(lines)
    for index in range(1, len(lines)):
        if lines[index].strip() in {"---", "..."}:
            return list(lines[: index + 1]), list(lines[index + 1 :])
    return [], list(lines)


def render_markdown_frontmatter(fields: dict[str, Any]) -> list[str]:
    rendered = [
        "---",
        f"id: {frontmatter_scalar(fields['id'])}",
        f"title: {frontmatter_scalar(fields['title'])}",
    ]
    aliases = fields.get("aliases") or []
    if aliases:
        rendered.append("aliases:")
        rendered.extend(f"  - {frontmatter_scalar(alias)}" for alias in aliases)
    rendered.append("---")
    return rendered


def frontmatter_scalar(value: Any) -> str:
    return str(value).replace("\n", " ").strip()


def markdown_lines_to_text(lines: list[str]) -> str:
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def parse_frontmatter(lines: list[str]) -> MarkdownMetadata:
    values = parse_frontmatter_values(lines)
    if not values:
        return MarkdownMetadata(title=None, page_id=None, aliases=[], tags=[], graph_role="content")

    title = first_frontmatter_value(values, "title")
    page_id = first_frontmatter_value(values, "id")
    graph_role = frontmatter_graph_role(values)
    aliases = [value for value, _ in values.get("aliases", [])]
    aliases.extend(value for value, _ in values.get("alias", []))
    tags = [
        (normalize_frontmatter_tag(value), line_index)
        for key in ("tags", "tag")
        for value, line_index in values.get(key, [])
    ]
    return MarkdownMetadata(
        title=title,
        page_id=page_id,
        aliases=list(dict.fromkeys(alias for alias in aliases if alias)),
        tags=list(dict.fromkeys((tag, line_index) for tag, line_index in tags if tag)),
        graph_role=graph_role,
    )


def parse_frontmatter_values(lines: list[str]) -> dict[str, list[tuple[str, int]]]:
    if not lines or lines[0].strip() != "---":
        return {}

    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() in {"---", "..."}:
            end = index
            break
    if end is None:
        return {}

    values: dict[str, list[tuple[str, int]]] = defaultdict(list)
    current_key: str | None = None
    for offset, raw_line in enumerate(lines[1:end], start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw_line[:1].isspace():
            if current_key and stripped.startswith("- "):
                value = clean_frontmatter_scalar(stripped[2:].strip())
                if value:
                    values[current_key].append((value, offset))
            continue
        if ":" not in raw_line:
            current_key = None
            continue
        key, raw_value = raw_line.split(":", 1)
        current_key = normalize_frontmatter_key(key)
        raw_value = raw_value.strip()
        if raw_value:
            for value in parse_frontmatter_value(raw_value):
                values[current_key].append((value, offset))
    return dict(values)


def parse_frontmatter_value(raw_value: str) -> list[str]:
    value = raw_value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [
            parsed
            for item in inner.split(",")
            if (parsed := clean_frontmatter_scalar(item.strip()))
        ]
    cleaned = clean_frontmatter_scalar(value)
    return [cleaned] if cleaned else []


def clean_frontmatter_scalar(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    return value.strip()


def normalize_frontmatter_key(key: str) -> str:
    return key.strip().casefold().replace("-", "_")


def first_frontmatter_value(values: dict[str, list[tuple[str, int]]], key: str) -> str | None:
    key_values = values.get(key) or []
    return key_values[0][0] if key_values else None


def frontmatter_graph_role(values: dict[str, list[tuple[str, int]]]) -> str:
    candidates = []
    for key in ("graph_role", "role", "layer"):
        candidates.extend(value for value, _ in values.get(key, []))
    candidates.extend(value for value, _ in values.get("type", []))
    for value in candidates:
        normalized = normalize_frontmatter_key(value)
        if normalized in {"navigation", "index", "catalog", "map", "view"}:
            return "navigation"
        if normalized in {"log", "event_stream", "event-stream", "log_entry", "log-entry"}:
            return "log"
        if normalized in {"source", "source_digest", "source_backed", "evidence"}:
            return "source"
        if normalized in {"artifact", "draft", "generated", "temp", "temporary"}:
            return "artifact"
    return "content"


def markdown_graph_role(relative_path: Path, metadata: MarkdownMetadata) -> str:
    if metadata.graph_role != "content":
        return metadata.graph_role

    parts = tuple(part.casefold() for part in relative_path.parts)
    name = parts[-1] if parts else ""
    if name in {"index.md", "forest-index.md"}:
        return "navigation"
    if name == "log.md" or "log" in parts[:-1]:
        return "log"
    if any(part in {"source", "sources"} for part in parts[:-1]):
        return "source"
    if any(part in {"draft", "drafts", "generated", "tmp", "temp"} for part in parts[:-1]):
        return "artifact"
    if any(part in {"maps", "views"} for part in parts[:-1]):
        return "navigation"
    return "content"


def markdown_graph_role_emits_edges(graph_role: str) -> bool:
    return graph_role in {"content", "source"}


def markdown_title_collisions(records: list[MarkdownPageRecord]) -> list[MarkdownCollision]:
    buckets: dict[str, list[MarkdownCollisionEntry]] = defaultdict(list)
    for record in records:
        page = record.page
        buckets[page.norm_title].append(markdown_collision_entry(record, handle=page.title, source="title"))
    return [
        MarkdownCollision(kind="title", key=norm_title, entries=tuple(entries))
        for norm_title, entries in sorted(buckets.items())
        if len(entries) > 1
    ]


def markdown_id_collisions(records: list[MarkdownPageRecord]) -> list[MarkdownCollision]:
    buckets: dict[str, list[MarkdownCollisionEntry]] = defaultdict(list)
    for record in records:
        page = record.page
        buckets[page.id].append(markdown_collision_entry(record, handle=page.id, source="id"))
    return [
        MarkdownCollision(kind="id", key=page_id, entries=tuple(entries))
        for page_id, entries in sorted(buckets.items())
        if len(entries) > 1
    ]


def markdown_alias_collisions(records: list[MarkdownPageRecord]) -> list[MarkdownCollision]:
    buckets: dict[str, list[MarkdownCollisionEntry]] = defaultdict(list)
    for record in records:
        page = record.page
        handles = [("title", page.title)]
        handles.extend(("alias", alias) for alias in record.aliases)
        for source, handle in handles:
            norm = normalize_title(handle)
            if not norm:
                continue
            buckets[norm].append(markdown_collision_entry(record, handle=handle, source=source))
    collisions: list[MarkdownCollision] = []
    for norm, entries in sorted(buckets.items()):
        page_ids = {entry.page_id for entry in entries}
        sources = {entry.source for entry in entries}
        if len(page_ids) > 1 and "alias" in sources:
            collisions.append(MarkdownCollision(kind="alias", key=norm, entries=tuple(entries)))
    return collisions


def markdown_collision_entry(record: MarkdownPageRecord, *, handle: str, source: str) -> MarkdownCollisionEntry:
    page = record.page
    return MarkdownCollisionEntry(
        path=record.relative_path.as_posix(),
        title=page.title,
        page_id=page.id,
        handle=handle,
        source=source,
        graph_role=record.graph_role,
    )


def format_markdown_collision_message(collisions: tuple[MarkdownCollision, ...]) -> str:
    kinds = {collision.kind for collision in collisions}
    if kinds == {"title"}:
        prefix = "duplicate Markdown page titles"
    elif kinds == {"id"}:
        prefix = "duplicate Markdown page ids"
    elif kinds == {"alias"}:
        prefix = "duplicate Markdown page aliases"
    else:
        prefix = "duplicate Markdown page metadata"
    details = "; ".join(
        f"{collision.kind} {collision.key}: {', '.join(entry.path for entry in collision.entries)}"
        for collision in collisions
    )
    return f"{prefix}: {details}"


def normalize_frontmatter_tag(value: str) -> str:
    tag = clean_frontmatter_scalar(value).strip()
    while tag.startswith("#"):
        tag = tag[1:]
    return tag.strip()


def build_title_aliases(records: list[MarkdownPageRecord]) -> dict[str, str]:
    owners: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for record in records:
        page = record.page
        for title in [page.title, *record.aliases]:
            norm = normalize_title(title)
            if not norm:
                continue
            owners[norm].append((page.id, page.title, record.relative_path.as_posix()))
    aliases: dict[str, str] = {}
    for norm, entries in owners.items():
        page_ids = {page_id for page_id, _title, _path in entries}
        if len(page_ids) == 1:
            aliases[norm] = entries[0][1]
    return aliases


def resolve_markdown_target(target_title: str, title_aliases: dict[str, str]) -> str:
    return title_aliases.get(normalize_title(target_title), target_title)


def markdown_edge(page: Page, line: Line, target_title: str) -> Edge:
    return Edge(
        source_page_id=page.id,
        source_title=page.title,
        source_views=page.views,
        source_updated=page.updated,
        line_id=line.line_id,
        line_index=line.index,
        line_text=line.text,
        target_title=target_title,
        target_norm=normalize_title(target_title),
    )


def parse_markdown_links(text: str) -> list[str]:
    links, _ = parse_markdown_line_links(text, in_code_fence=False)
    return links


def parse_markdown_line_links(text: str, *, in_code_fence: bool) -> tuple[list[str], bool]:
    stripped = text.lstrip()
    if is_code_fence(stripped):
        return [], not in_code_fence
    if in_code_fence:
        return [], in_code_fence

    links: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "#":
            tag = parse_markdown_hash_tag(text, index)
            if tag is not None:
                links.append(tag[0])
                index = tag[1]
                continue
            index += 1
            continue

        if char != "[":
            index += 1
            continue

        start = index
        if start + 1 >= len(text) or text[start + 1] != "[":
            index += 1
            continue
        if is_inside_inline_code(text, start):
            close = text.find("]]", start + 2)
            index = len(text) if close == -1 else close + 2
            continue

        close = text.find("]]", start + 2)
        if close == -1:
            break
        target = markdown_wikilink_target(text[start + 2 : close])
        if target:
            links.append(target)
        index = close + 2

    return links, in_code_fence


def parse_markdown_hash_tag(text: str, start: int) -> tuple[str, int] | None:
    if start >= 2 and text[start - 1] == "(" and text[start - 2] == "]":
        return None
    return parse_cosense_hash_tag(text, start)


def markdown_wikilink_target(content: str) -> str | None:
    target = content.split("|", 1)[0].split("#", 1)[0].strip()
    if not target:
        return None
    if target.endswith(".md"):
        target = target[:-3]
    if "/" in target:
        target = target.rsplit("/", 1)[-1]
    return target.strip() or None


def is_code_fence(stripped_line: str) -> bool:
    return stripped_line.startswith("```") or stripped_line.startswith("~~~")


def is_inside_inline_code(text: str, position: int) -> bool:
    return text[:position].count("`") % 2 == 1
