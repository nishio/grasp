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
    def from_folder(cls, folder: str | Path) -> "MarkdownMirror":
        root = Path(folder)
        if not root.exists():
            raise ValueError(f"Markdown folder does not exist: {root}")
        if not root.is_dir():
            raise ValueError(f"Markdown source must be a folder: {root}")

        markdown_files = list(iter_markdown_files(root))
        if not markdown_files:
            raise ValueError(f"Markdown folder has no .md files: {root}")

        records: list[MarkdownPageRecord] = []
        title_buckets: dict[str, list[str]] = defaultdict(list)
        id_buckets: dict[str, list[str]] = defaultdict(list)
        for path in markdown_files:
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
            records.append(
                MarkdownPageRecord(
                    relative_path=relative_path,
                    page=page,
                    aliases=[alias for alias in aliases if normalize_title(alias) != norm_title],
                    tags=metadata.tags,
                    graph_role=markdown_graph_role(relative_path, metadata),
                    source_hash=source_hash,
                    mtime_ns=stat.st_mtime_ns,
                )
            )
            title_buckets[norm_title].append(relative_path.as_posix())
            id_buckets[page_id].append(relative_path.as_posix())

        title_collisions = {
            norm: paths
            for norm, paths in title_buckets.items()
            if len(paths) > 1
        }
        if title_collisions:
            details = "; ".join(
                f"{norm}: {', '.join(paths)}"
                for norm, paths in sorted(title_collisions.items())
            )
            raise ValueError(f"duplicate Markdown page titles: {details}")

        id_collisions = {
            page_id: paths
            for page_id, paths in id_buckets.items()
            if len(paths) > 1
        }
        if id_collisions:
            details = "; ".join(
                f"{page_id}: {', '.join(paths)}"
                for page_id, paths in sorted(id_collisions.items())
            )
            raise ValueError(f"duplicate Markdown page ids: {details}")

        title_aliases = build_title_aliases(records)
        pages = [record.page for record in records]
        edges: list[Edge] = []
        line_target_norms: dict[str, set[str]] = defaultdict(set)
        for record in records:
            if record.graph_role != "content":
                continue
            page = record.page
            in_code_fence = False
            for line in page.lines:
                links, in_code_fence = parse_markdown_line_links(
                    line.text,
                    in_code_fence=in_code_fence,
                )
                for target_title in links:
                    resolved_title = resolve_markdown_target(target_title, title_aliases)
                    edges.append(markdown_edge(page, line, resolved_title))
                    line_target_norms.setdefault(line.line_id, set()).add(normalize_title(resolved_title))
            for tag, line_index in record.tags:
                if 0 <= line_index < len(page.lines):
                    line = page.lines[line_index]
                else:
                    line = page.lines[0] if page.lines else Line(line_id=f"{page.id}:0", index=0, text="")
                if normalize_title(tag) in line_target_norms.get(line.line_id, set()):
                    continue
                edges.append(markdown_edge(page, line, tag))
                line_target_norms.setdefault(line.line_id, set()).add(normalize_title(tag))

        return cls(
            pages=pages,
            edges=edges,
            title_collisions={},
            title_aliases={
                alias_norm: title
                for alias_norm, title in title_aliases.items()
                if normalize_title(title) != alias_norm
            },
            records=tuple(records),
            file_manifest=markdown_file_manifest(records),
            project_name=root.name,
            display_name=root.name,
            source_folder=root,
        )


def iter_markdown_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*.md"))
        if not any(part.startswith(".") for part in path.relative_to(root).parts)
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


def markdown_file_manifest(records: list[MarkdownPageRecord]) -> dict[str, Any]:
    return {
        "version": 2,
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


def parse_frontmatter(lines: list[str]) -> MarkdownMetadata:
    if not lines or lines[0].strip() != "---":
        return MarkdownMetadata(title=None, page_id=None, aliases=[], tags=[], graph_role="content")

    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() in {"---", "..."}:
            end = index
            break
    if end is None:
        return MarkdownMetadata(title=None, page_id=None, aliases=[], tags=[], graph_role="content")

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
    candidates.extend(value for value, _ in values.get("type", []) if value == "log-entry")
    for value in candidates:
        normalized = normalize_frontmatter_key(value)
        if normalized in {"navigation", "index", "catalog", "map", "view"}:
            return "navigation"
        if normalized in {"log", "event_stream", "event-stream", "log_entry", "log-entry"}:
            return "log"
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
    if any(part in {"maps", "views"} for part in parts[:-1]):
        return "navigation"
    return "content"


def normalize_frontmatter_tag(value: str) -> str:
    tag = clean_frontmatter_scalar(value).strip()
    while tag.startswith("#"):
        tag = tag[1:]
    return tag.strip()


def build_title_aliases(records: list[MarkdownPageRecord]) -> dict[str, str]:
    owners: dict[str, tuple[str, str]] = {}
    for record in records:
        page = record.page
        for title in [page.title, *record.aliases]:
            norm = normalize_title(title)
            if not norm:
                continue
            owner = owners.get(norm)
            if owner is not None and owner[0] != page.title:
                raise ValueError(
                    "duplicate Markdown page aliases: "
                    f"{title!r} is used by {owner[1]} and {record.relative_path.as_posix()}"
                )
            owners[norm] = (page.title, record.relative_path.as_posix())
    return {norm: title for norm, (title, _) in owners.items()}


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
