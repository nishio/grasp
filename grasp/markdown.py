from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
from pathlib import Path

from .cosense import Edge, Line, Page, normalize_title, parse_cosense_hash_tag


@dataclass(frozen=True)
class MarkdownMirror:
    pages: list[Page]
    edges: list[Edge]
    title_collisions: dict[str, list[str]]
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

        pages: list[Page] = []
        title_buckets: dict[str, list[str]] = defaultdict(list)
        for path in markdown_files:
            relative_path = path.relative_to(root)
            page_id = markdown_page_id(relative_path)
            title = markdown_title(path)
            norm_title = normalize_title(title)
            updated = int(path.stat().st_mtime)
            text_lines = path.read_text(encoding="utf-8").splitlines()
            lines = tuple(
                Line(
                    line_id=f"{page_id}:{line_index}",
                    index=line_index,
                    text=text,
                    updated=updated,
                )
                for line_index, text in enumerate(text_lines)
            )
            pages.append(
                Page(
                    id=page_id,
                    title=title,
                    norm_title=norm_title,
                    created=None,
                    updated=updated,
                    views=0,
                    lines=lines,
                )
            )
            title_buckets[norm_title].append(relative_path.as_posix())

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

        edges: list[Edge] = []
        for page in pages:
            in_code_fence = False
            for line in page.lines:
                links, in_code_fence = parse_markdown_line_links(
                    line.text,
                    in_code_fence=in_code_fence,
                )
                for target_title in links:
                    edges.append(
                        Edge(
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
                    )

        return cls(
            pages=pages,
            edges=edges,
            title_collisions={},
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
