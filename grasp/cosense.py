from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


WHITESPACE_RE = re.compile(r"\s+")
HASH_TAG_STOP_CHARS = set(" \t\r\n[]{}()<>'\"`#")
HASH_TAG_TRAILING_CHARS = ".,;:!?)]}>" "\u3001\u3002\uff1f\uff01\uff09\u300d\u300f\u3011"
HASH_TAG_PREFIX_BOUNDARY_CHARS = set(" \t\r\n([{<>'\"`")
NUMERIC_PREFIX_RE = re.compile(r"^\s*(\d+)")
ISSUE_NUMBER_HASH_RE = re.compile(
    r"(?i)(?:\b(?:PR|issue|pull request)\s*|open\s+q(?:uestion)?s?\s*)#(?P<number>\d+)"
)


def normalize_title(title: str) -> str:
    """Normalize Cosense title/link matching: case-insensitive, folded spaces."""
    return WHITESPACE_RE.sub(" ", title.strip().casefold())


def is_internal_cosense_link(content: str) -> bool:
    """Return True when a single-bracket Cosense token is an internal page link."""
    token = content.strip()
    if not token:
        return False

    lower = token.casefold()
    if "http://" in lower or "https://" in lower:
        return False
    if token.startswith("/"):
        return False
    if is_decoration_token(token):
        return False
    if len(token) >= 2 and token[0] == "$" and token[1].isspace():
        return False
    if len(token) >= 2 and token[0] == "/" and token[1].isspace():
        return False
    if lower.endswith(".icon") or lower.endswith(".img"):
        return False
    if "[" in token or "]" in token:
        return False

    return True


def parse_cosense_links(text: str) -> list[str]:
    """Extract internal links from Cosense line text.

    Cosense uses single brackets for page links, but the same syntax also
    represents external URLs, icons/images, cross-project links, and decoration.
    Double brackets are bold markup in Cosense, not page links.
    """
    links: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "#":
            tag = parse_cosense_hash_tag(text, index)
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
        if start + 1 < len(text) and text[start + 1] == "[":
            close = text.find("]]", start + 2)
            index = len(text) if close == -1 else close + 2
            continue

        close = text.find("]", start + 1)
        if close == -1:
            break

        if is_inside_inline_code(text, start) or is_ascii_index_syntax(text, start):
            index = close + 1
            continue

        content = text[start + 1 : close].strip()
        if is_internal_cosense_link(content):
            links.append(content)
        index = close + 1

    return links


@dataclass(frozen=True)
class CrossProjectLink:
    raw: str
    project: str
    title: str
    target_class: str

    def to_dict(self) -> dict[str, str]:
        return {
            "raw": self.raw,
            "project": self.project,
            "title": self.title,
            "target_class": self.target_class,
        }


def parse_cosense_cross_project_links(text: str) -> list[CrossProjectLink]:
    """Extract Cosense shorthand links such as [/project/Page].

    These are not internal graph edges for the current project, but they are
    useful as hosted acquisition seeds. Keep this parser separate from
    parse_cosense_links so existing materialized graph semantics do not change.
    """
    links: list[CrossProjectLink] = []
    index = 0
    while index < len(text):
        if text[index] != "[":
            index += 1
            continue

        start = index
        if start + 1 < len(text) and text[start + 1] == "[":
            close = text.find("]]", start + 2)
            index = len(text) if close == -1 else close + 2
            continue

        close = text.find("]", start + 1)
        if close == -1:
            break

        if is_inside_inline_code(text, start) or is_ascii_index_syntax(text, start):
            index = close + 1
            continue

        content = text[start + 1 : close].strip()
        link = parse_cosense_cross_project_link_token(content)
        if link is not None:
            links.append(link)
        index = close + 1

    return links


def parse_cosense_cross_project_link_token(content: str) -> CrossProjectLink | None:
    token = content.strip()
    if len(token) < 2 or not token.startswith("/"):
        return None
    if token[1].isspace():
        return None
    if "[" in token or "]" in token:
        return None

    rest = token[1:]
    project, separator, title = rest.partition("/")
    project = project.strip()
    if not project:
        return None
    title = title.strip() if separator else ""
    return CrossProjectLink(
        raw=token,
        project=project,
        title=title,
        target_class=classify_cross_project_target(title),
    )


def classify_cross_project_target(title: str) -> str:
    if not title:
        return "project-root"
    lower = title.casefold()
    if lower.endswith(".icon") or lower.endswith(".img"):
        return "icon"
    return "semantic"


def parse_cosense_hash_tag(text: str, start: int) -> tuple[str, int] | None:
    if is_inside_inline_code(text, start):
        return None
    if not is_hash_tag_start_boundary(text, start):
        return None
    if start + 1 >= len(text) or text[start + 1].isspace():
        return None

    end = start + 1
    while end < len(text):
        char = text[end]
        if char in HASH_TAG_STOP_CHARS or char.isspace():
            break
        end += 1

    raw_tag = text[start + 1 : end]
    tag = raw_tag.rstrip(HASH_TAG_TRAILING_CHARS)
    if not tag:
        return None
    if "http://" in tag.casefold() or "https://" in tag.casefold():
        return None
    return tag, end


def is_hash_tag_start_boundary(text: str, start: int) -> bool:
    if start == 0:
        return True

    previous = text[start - 1]
    if not previous.isascii():
        return True
    if previous in HASH_TAG_PREFIX_BOUNDARY_CHARS:
        return True
    return False


def is_inside_inline_code(text: str, position: int) -> bool:
    return text[:position].count("`") % 2 == 1


def is_decoration_token(token: str) -> bool:
    index = 0
    while index < len(token) and token[index] in "*-_":
        index += 1
    return index > 0 and index < len(token) and token[index].isspace()


def is_ascii_index_syntax(text: str, start: int) -> bool:
    if start == 0:
        return False
    previous = text[start - 1]
    return previous.isascii() and not previous.isspace()


@dataclass(frozen=True)
class Line:
    line_id: str
    index: int
    text: str
    created: int | None = None
    updated: int | None = None
    user_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_id": self.line_id,
            "index": self.index,
            "text": self.text,
            "created": self.created,
            "updated": self.updated,
            "user_id": self.user_id,
        }


@dataclass(frozen=True)
class Page:
    id: str
    title: str
    norm_title: str
    created: int | None
    updated: int | None
    views: int
    lines: tuple[Line, ...]
    stored_line_count: int | None = None
    project: str = ""

    @property
    def line_count(self) -> int:
        if self.stored_line_count is not None:
            return self.stored_line_count
        return len(self.lines)

    def to_summary(self) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "created": self.created,
            "updated": self.updated,
            "views": self.views,
            "line_count": self.line_count,
        }
        if self.project:
            summary["project"] = self.project
        return summary


@dataclass(frozen=True)
class Edge:
    source_page_id: str
    source_title: str
    source_views: int
    source_updated: int | None
    line_id: str
    line_index: int
    line_text: str
    target_title: str
    target_norm: str
    target_handle: str | None = None
    target_handle_norm: str | None = None
    target_page_id: str | None = None
    resolution_status: str = "unresolved"
    source_project: str = ""
    target_project: str = ""
    link_kind: str = "internal"
    connection_strength: str = "strong"

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "project": self.source_project,
            "source_project": self.source_project,
            "source_page_id": self.source_page_id,
            "source_title": self.source_title,
            "source_views": self.source_views,
            "source_updated": self.source_updated,
            "line_id": self.line_id,
            "line_index": self.line_index,
            "line_text": self.line_text,
            "target_project": self.target_project,
            "target_title": self.target_title,
            "target_norm": self.target_norm,
            "target_handle": self.target_handle or self.target_title,
            "target_handle_norm": self.target_handle_norm or self.target_norm,
            "target_page_id": self.target_page_id,
            "resolution_status": self.resolution_status,
            "link_kind": self.link_kind,
            "connection_strength": self.connection_strength,
        }
        if not self.source_project:
            result.pop("project")
            result.pop("source_project")
        if not self.target_project:
            result.pop("target_project")
        annotation = edge_semantic_annotation(self)
        if annotation is not None:
            result["semantic_annotation"] = annotation
        return result


def edge_semantic_annotation(edge: Edge) -> dict[str, Any] | None:
    return edge_semantic_annotation_from_fields(edge.target_title, edge.line_text)


def edge_semantic_annotation_from_fields(target_title: str, line_text: str) -> dict[str, Any] | None:
    numeric_match = NUMERIC_PREFIX_RE.match(target_title)
    if numeric_match is None:
        return None

    target_number = numeric_match.group(1)
    for marker_match in ISSUE_NUMBER_HASH_RE.finditer(line_text):
        if marker_match.group("number") == target_number:
            return {
                "semantic_role": "issue-number",
                "graph_scope": "non-semantic",
                "confidence": 0.9,
                "annotator": "system",
                "reason": "numeric hashtag appears with an issue/PR/Open Question marker",
            }
    return None


class CosenseStore:
    def __init__(
        self,
        pages: list[Page],
        edges: list[Edge],
        title_collisions: dict[str, list[str]],
        *,
        project_name: str = "",
        display_name: str = "",
        exported: int | None = None,
    ):
        self.pages = pages
        self.edges = edges
        self.project_name = project_name
        self.display_name = display_name
        self.exported = exported
        self.pages_by_id = {page.id: page for page in pages}
        self.pages_by_norm: dict[str, Page] = {}
        for page in pages:
            self.pages_by_norm.setdefault(page.norm_title, page)

        self.title_collisions = title_collisions
        self.backlinks_by_norm: dict[str, list[Edge]] = defaultdict(list)
        self.outgoing_by_page: dict[str, list[Edge]] = defaultdict(list)
        self.adjacency: dict[str, set[str]] = defaultdict(set)
        self._unresolved_target_stats: list[dict[str, Any]] | None = None

        for edge in edges:
            self.backlinks_by_norm[edge.target_norm].append(edge)
            self.outgoing_by_page[edge.source_page_id].append(edge)

            target_page = self.pages_by_norm.get(edge.target_norm)
            if target_page is not None and target_page.id != edge.source_page_id:
                self.adjacency[edge.source_page_id].add(target_page.id)
                self.adjacency[target_page.id].add(edge.source_page_id)

    @classmethod
    def from_cosense_export(cls, path: str | Path) -> "CosenseStore":
        export_path = Path(path)
        with export_path.open(encoding="utf-8") as file:
            data = json.load(file)

        pages: list[Page] = []
        title_buckets: dict[str, list[str]] = defaultdict(list)

        for page_data in data.get("pages", []):
            page_id = str(page_data["id"])
            title = str(page_data["title"])
            norm_title = normalize_title(title)
            def _parse_line(line_data: dict | str, line_index: int) -> Line:
                if isinstance(line_data, str):
                    return Line(
                        line_id=f"{page_id}:{line_index}",
                        index=line_index,
                        text=line_data,
                        created=None,
                        updated=None,
                        user_id=None,
                    )
                return Line(
                    line_id=f"{page_id}:{line_index}",
                    index=line_index,
                    text=str(line_data.get("text", "")),
                    created=line_data.get("created"),
                    updated=line_data.get("updated"),
                    user_id=line_data.get("userId"),
                )
            lines = tuple(
                _parse_line(line_data, line_index)
                for line_index, line_data in enumerate(page_data.get("lines", []))
            )
            pages.append(
                Page(
                    id=page_id,
                    title=title,
                    norm_title=norm_title,
                    created=page_data.get("created"),
                    updated=page_data.get("updated"),
                    views=int(page_data.get("views") or 0),
                    lines=lines,
                )
            )
            title_buckets[norm_title].append(title)

        first_title_by_norm = {page.norm_title: page.title for page in pages}
        edges: list[Edge] = []
        for page in pages:
            for line in page.lines:
                for target_title in parse_cosense_links(line.text):
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
                for cross_link in parse_cosense_cross_project_links(line.text):
                    target_title = cross_link.title or cross_link.project
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
                            target_handle=cross_link.raw,
                            target_handle_norm=normalize_title(target_title),
                            target_project=cross_link.project,
                            link_kind=f"cross-{cross_link.target_class}",
                            connection_strength="strong",
                        )
                    )

        title_collisions = {
            norm: titles
            for norm, titles in title_buckets.items()
            if len(set(titles)) > 1 and first_title_by_norm.get(norm) is not None
        }
        return cls(
            pages=pages,
            edges=edges,
            title_collisions=title_collisions,
            project_name=str(data.get("name") or ""),
            display_name=str(data.get("displayName") or data.get("name") or ""),
            exported=data.get("exported"),
        )

    def resolve_page(self, title: str) -> Page | None:
        return self.pages_by_norm.get(normalize_title(title))

    def page_lines(self, page: Page, limit: int | None = None, offset: int = 0) -> tuple[list[Line], bool]:
        offset = max(0, offset)
        if limit is None or limit < 0:
            return list(page.lines[offset:]), False
        lines = list(page.lines[offset : offset + limit])
        return lines, offset + len(lines) < len(page.lines)

    def backlinks(self, title: str, limit: int | None = None, offset: int = 0) -> list[Edge]:
        edges = sorted(self.backlinks_by_norm.get(normalize_title(title), []), key=edge_rank_key)
        if offset:
            edges = edges[offset:]
        if limit is not None and limit >= 0:
            return edges[:limit]
        return edges

    def link_stats(self, title: str) -> dict[str, Any]:
        norm = normalize_title(title)
        page = self.resolve_page(title)
        backlinks = self.backlinks_by_norm.get(norm, [])
        if page is None:
            title_counts = Counter(edge.target_title for edge in backlinks)
            canonical_title = title_counts.most_common(1)[0][0] if title_counts else title
        else:
            canonical_title = page.title

        return {
            "query": title,
            "title": canonical_title,
            "normalized_title": norm,
            "page_exists": page is not None,
            "page": page.to_summary() if page is not None else None,
            "link_count": len(backlinks),
            "source_page_count": len({edge.source_page_id for edge in backlinks}),
            "link_multiplicity": link_multiplicity(len(backlinks)),
        }

    def unresolved_targets(self, limit: int | None = None) -> list[dict[str, Any]]:
        stats = self._unresolved_target_stats
        if stats is None:
            by_norm: dict[str, list[Edge]] = defaultdict(list)
            for edge in self.edges:
                if edge.target_norm not in self.pages_by_norm:
                    by_norm[edge.target_norm].append(edge)
            stats = [self._unresolved_target_entry(norm, edges) for norm, edges in by_norm.items()]
            stats.sort(
                key=lambda item: (
                    -item["link_count"],
                    -item["source_page_count"],
                    -item["total_source_views"],
                    -(item["latest_source_updated"] or 0),
                    item["title"].casefold(),
                )
            )
            self._unresolved_target_stats = stats
        if limit is not None and limit >= 0:
            return stats[:limit]
        return stats

    def unresolved_targets_from_page(self, page: Page, limit: int | None = None) -> list[dict[str, Any]]:
        by_norm: dict[str, list[Edge]] = defaultdict(list)
        for edge in self.outgoing_by_page.get(page.id, []):
            if edge.target_norm not in self.pages_by_norm:
                by_norm[edge.target_norm].append(edge)

        unresolved_targets = [self._unresolved_target_entry(norm, edges) for norm, edges in by_norm.items()]
        unresolved_targets.sort(
            key=lambda item: (
                -item["link_count"],
                -item["source_page_count"],
                -item["total_source_views"],
                item["title"].casefold(),
            )
        )
        if limit is not None and limit >= 0:
            return unresolved_targets[:limit]
        return unresolved_targets

    def related(self, title: str, limit: int | None = None) -> list[dict[str, Any]]:
        page = self.resolve_page(title)
        if page is None:
            return self._related_missing_target(title, limit)

        direct = self.adjacency.get(page.id, set())
        scores: Counter[str] = Counter()
        via: dict[str, list[str]] = defaultdict(list)
        for neighbor_id in sorted(direct, key=self._page_sort_key):
            for related_id in sorted(self.adjacency.get(neighbor_id, set()), key=self._page_sort_key):
                if related_id == page.id or related_id in direct:
                    continue
                scores[related_id] += 1
                if len(via[related_id]) < 3:
                    via[related_id].append(self.pages_by_id[neighbor_id].title)

        related_pages = []
        for related_id, score in scores.items():
            related_page = self.pages_by_id[related_id]
            related_pages.append(
                {
                    **related_page.to_summary(),
                    "score": score,
                    "via": via[related_id],
                }
            )

        related_pages.sort(key=lambda item: (-item["score"], -item["views"], item["title"].casefold()))
        if limit is not None and limit >= 0:
            return related_pages[:limit]
        return related_pages

    def _related_missing_target(self, title: str, limit: int | None = None) -> list[dict[str, Any]]:
        source_edges: dict[str, list[Edge]] = defaultdict(list)
        for edge in self.backlinks_by_norm.get(normalize_title(title), []):
            source_edges[edge.source_page_id].append(edge)

        related_pages = []
        for source_page_id, edges in source_edges.items():
            source_page = self.pages_by_id[source_page_id]
            title_counts = Counter(edge.target_title for edge in edges)
            related_pages.append(
                {
                    **source_page.to_summary(),
                    "score": len(edges),
                    "relation": "backlink-source",
                    "via": [title_counts.most_common(1)[0][0]],
                }
            )
        related_pages.sort(key=lambda item: (-item["score"], -item["views"], item["title"].casefold()))
        if limit is not None and limit >= 0:
            return related_pages[:limit]
        return related_pages

    def suggest(self, partial: str, limit: int = 20) -> list[dict[str, Any]]:
        norm_partial = normalize_title(partial)
        candidates = [
            page
            for page in self.pages
            if norm_partial in page.norm_title
        ]
        candidates.sort(
            key=lambda page: (
                not page.norm_title.startswith(norm_partial),
                -page.views,
                page.title.casefold(),
            )
        )
        return [page.to_summary() for page in candidates[:limit]]

    def read(
        self,
        title: str,
        *,
        line_limit: int | None = None,
        backlink_limit: int = 20,
        related_limit: int = 20,
        unresolved_limit: int = 20,
    ) -> dict[str, Any]:
        page = self.resolve_page(title)
        backlinks = self.backlinks(title, backlink_limit)
        link_stats = self.link_stats(title)

        if page is None:
            return {
                "query": title,
                "page": None,
                "link_stats": link_stats,
                "lines": [],
                "lines_truncated": False,
                "backlinks": [edge.to_dict() for edge in backlinks],
                "backlink_count_returned": len(backlinks),
                "backlink_count_total": link_stats["link_count"],
                "related": self.related(title, related_limit),
                "unresolved_targets": [],
            }

        lines, lines_truncated = self.page_lines(page, line_limit)
        return {
            "query": title,
            "page": page.to_summary(),
            "link_stats": link_stats,
            "lines": [line.to_dict() for line in lines],
            "lines_truncated": lines_truncated,
            "backlinks": [edge.to_dict() for edge in backlinks],
            "backlink_count_returned": len(backlinks),
            "backlink_count_total": link_stats["link_count"],
            "related": self.related(page.title, related_limit),
            "unresolved_targets": self.unresolved_targets_from_page(page, unresolved_limit),
        }

    def _unresolved_target_entry(self, norm: str, edges: list[Edge]) -> dict[str, Any]:
        title_counts = Counter(edge.target_title for edge in edges)
        source_page_ids = {edge.source_page_id for edge in edges}
        total_source_views = sum(self.pages_by_id[page_id].views for page_id in source_page_ids)
        latest_source_updated = max((edge.source_updated or 0 for edge in edges), default=0)
        examples = sorted(edges, key=edge_rank_key)[:5]
        return {
            "title": title_counts.most_common(1)[0][0] if title_counts else norm,
            "normalized_title": norm,
            "link_count": len(edges),
            "source_page_count": len(source_page_ids),
            "total_source_views": total_source_views,
            "latest_source_updated": latest_source_updated,
            "examples": [edge.to_dict() for edge in examples],
        }

    def _page_sort_key(self, page_id: str) -> tuple[str, int]:
        page = self.pages_by_id[page_id]
        return (page.title.casefold(), -page.views)


def edge_rank_key(edge: Edge) -> tuple[int, int, str, int]:
    return (
        -edge.source_views,
        -(edge.source_updated or 0),
        edge.source_title.casefold(),
        edge.line_index,
    )


def link_multiplicity(link_count: int) -> str:
    if link_count <= 0:
        return "none"
    if link_count == 1:
        return "single"
    return "multi"
