"""Wiki lint: duplicate IDs, orphan detection, broken links, missing frontmatter.

Reference-count-based broken-link split (Scrapbox 2-hop semantics):
- 1 page でのみ参照 + page なし = 真の壊れた wikilink (typo / 私的 jargon 候補)
- 2+ page で参照 + page なし = aspect handle 候補 (2-hop hub の種、empty page or concept page 化候補)

参照: [[aspect-wikilinkはhubの種-20260601]] / [[empty-pageは静止せずCに近づく-20260601]]

Usage: python3 scripts/lint_wiki.py
"""
import re
from datetime import date
from pathlib import Path
from collections import defaultdict

WIKI = Path(__file__).parent.parent / "wiki"

# Collect all pages by basename (without .md). Wikilinks resolve by basename, so
# duplicate stems make links ambiguous and must not be silently overwritten.
page_paths = []
pages_by_stem = defaultdict(list)
for p in sorted(WIKI.rglob("*.md")):
    if p.name in ("index.md", "log.md"):
        continue
    page_paths.append(p)
    pages_by_stem[p.stem].append(p)

duplicate_stems = {
    stem: paths for stem, paths in pages_by_stem.items() if len(paths) > 1
}
pages = {stem: paths[0] for stem, paths in pages_by_stem.items()}


def page_ref(path):
    """Return a stable display key. Unique stems keep the old output format."""
    if len(pages_by_stem[path.stem]) == 1:
        return path.stem
    return path.relative_to(WIKI).with_suffix("").as_posix()

# Parse each page: extract frontmatter + outgoing wikilinks
WIKILINK = re.compile(r"\[\[([^\]\|#]+?)(?:\|[^\]]*)?\]\]")
FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

outgoing = defaultdict(set)   # page -> set of pages it links to
incoming = defaultdict(set)   # page -> set of pages linking to it
frontmatter = {}              # page -> dict of fm fields (raw text per key)

for path in page_paths:
    name = page_ref(path)
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER.match(text)
    fm_text = m.group(1) if m else ""
    body = text[m.end():] if m else text

    # crude frontmatter parse: only keys we care about
    fm = {}
    for line in fm_text.splitlines():
        line = line.rstrip()
        if line.startswith(("type:", "summary:", "sources:", "date:", "url:", "raw_sources:")):
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
        # detect indented list items as part of last list-key (sources/raw_sources)
    # check whether sources/raw_sources actually has any value (list item or inline)
    has_sources = False
    in_sources_block = False
    for line in fm_text.splitlines():
        stripped = line.rstrip()
        if stripped.startswith(("sources:", "raw_sources:")):
            tail = stripped.split(":", 1)[1].strip()
            if tail:  # inline value like "sources: foo.md"
                has_sources = True
            in_sources_block = True
            continue
        if in_sources_block:
            if line.startswith(("  -", "    -", "\t-")) and line.strip().startswith("-"):
                has_sources = True
            elif stripped and not stripped.startswith(" "):
                in_sources_block = False
    fm["__has_sources__"] = has_sources
    frontmatter[name] = fm

    # strip code blocks and inline code before wikilink extraction
    no_fence = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    no_code = re.sub(r"`[^`\n]*`", "", no_fence)

    # extract outgoing wikilinks
    for link_text in WIKILINK.findall(no_code):
        target = link_text.strip()
        outgoing[name].add(target)
        incoming[target].add(name)

# also parse index.md to count its outgoing links (it's the catalog)
index_text = (WIKI / "index.md").read_text(encoding="utf-8")
INDEX_LINK = re.compile(r"\((?:([^()]*?)/)?([^()/]+)\.md\)")
index_targets = set()
for prefix, stem in INDEX_LINK.findall(index_text):
    index_targets.add(stem)
indexed = set(pages) & index_targets

# ---------- Reports ----------
print("=" * 60)
print("WIKI LINT REPORT")
print("=" * 60)
print(f"Total page files (excluding index/log): {len(page_paths)}")
if duplicate_stems:
    print(f"Unique wikilink IDs: {len(pages)}")
print()

# 0. Duplicate page IDs
print(f"## 重複ページID（同じbasename）: {len(duplicate_stems)}")
for stem, paths in sorted(duplicate_stems.items()):
    rels = [str(p.relative_to(WIKI)) for p in paths]
    print(f"  - [[{stem}]] が曖昧: {', '.join(rels)}")
print()

# 1. Orphan detection: pages with no incoming wikilinks
orphans = sorted(page_ref(path) for path in page_paths if not incoming.get(path.stem))
print(f"## 孤立ページ（incoming wikilinkなし）: {len(orphans)}")
print("（index.md登録は別カウント）")
for name in orphans:
    stem = name.rsplit("/", 1)[-1]
    in_index = "✓index" if stem in indexed else "✗index"
    typ = frontmatter[name].get("type", "?").strip()
    print(f"  - [{typ}] {name} ({in_index})")
print()

# 2. Wikilinks to non-existent pages — split by reference count (Scrapbox 2-hop semantics)
# 1 回参照 = 真の broken (typo / 私的 jargon 候補)
# 2+ 回参照 = aspect handle 候補 (2-hop hub の種、empty page (B) または concept page (C) 化候補)
# 参照: [[aspect-wikilinkはhubの種-20260601]] / [[empty-pageは静止せずCに近づく-20260601]]
referenced = set()
for src, targets in outgoing.items():
    referenced.update(targets)
missing = sorted(referenced - set(pages))
missing_with_src = defaultdict(list)
for src, targets in outgoing.items():
    for t in targets:
        if t in missing:
            missing_with_src[t].append(src)

true_broken = [t for t in missing if len(missing_with_src[t]) == 1]
print(f"## 真の壊れたwikilink（1 page のみ参照 = typo / 私的 jargon 候補）: {len(true_broken)}")
for target in true_broken:
    srcs = missing_with_src[target]
    print(f"  - [[{target}]] ← from: {', '.join(sorted(srcs))}")
print()

# 3. Missing index entries
missing_in_index = sorted(set(pages) - indexed)
print(f"## index.mdに未登録: {len(missing_in_index)}")
for name in missing_in_index:
    typ = frontmatter[name].get("type", "?").strip()
    print(f"  - [{typ}] {name}")
print()

# 4. Frontmatter health
print("## フロントマター不備")
missing_type = [n for n, fm in frontmatter.items() if "type" not in fm]
missing_summary = [n for n, fm in frontmatter.items() if "summary" not in fm]
missing_sources_required = [
    n for n, fm in frontmatter.items()
    if fm.get("type", "").strip() in ("source", "concept") and not fm["__has_sources__"]
]
print(f"  type欠落: {len(missing_type)}")
for n in missing_type:
    print(f"    - {n}")
print(f"  summary欠落: {len(missing_summary)}")
for n in missing_summary:
    print(f"    - {n}")
print(f"  sources欠落 (source/concept type): {len(missing_sources_required)}")
for n in missing_sources_required:
    typ = frontmatter[n].get("type", "?").strip()
    print(f"    - [{typ}] {n}")
print()

# 5. Aspect handle 候補 (2+ page で参照されるが page なし = 2-hop hub の種)
# 参照: [[aspect-wikilinkはhubの種-20260601]] path B (empty page) または C (concept page) 化候補
aspect_candidates = [(t, missing_with_src[t]) for t in missing if len(missing_with_src[t]) >= 2]
aspect_candidates.sort(key=lambda x: -len(x[1]))
print(f"## aspect handle 候補（2+ page で参照 = 2-hop hub の種、empty page か concept page 化候補）: {len(aspect_candidates)}")
for target, srcs in aspect_candidates:
    print(f"  - {len(srcs)}回参照: [[{target}]] ← from: {', '.join(sorted(srcs))}")
print()

# 6. Most-linked pages (positive signal)
print("## 最もリンクされているページ（top 10）")
top_incoming = sorted(((n, len(incoming[n])) for n in pages), key=lambda x: -x[1])[:10]
for name, cnt in top_incoming:
    print(f"  - {cnt:3d} ← {name}")
print()

# 7. Pages with very few outgoing links (poorly integrated)
print("## outgoing wikilinkが少ないページ（≤1）")
low_outgoing = sorted(
    page_ref(path) for path in page_paths if len(outgoing.get(page_ref(path), set())) <= 1
)
for name in low_outgoing:
    typ = frontmatter[name].get("type", "?").strip()
    cnt = len(outgoing.get(name, set()))
    print(f"  - [{typ}] ({cnt} out) {name}")
print()

# ---------- Log-based operational health ----------
# log.md の entry を parse: `## [YYYY-MM-DD( HH:MM)?] <ops> | <summary>`
# ops に `@<model>` tag があれば実行モデルの記録 (CLAUDE.md 記法参照)
log_entries = []  # (date_str, ops_label, body)
log_path = WIKI / "log.md"
if log_path.exists():
    log_text = log_path.read_text(encoding="utf-8")
    headers = list(re.finditer(
        r"^## \[(\d{4}-\d{2}-\d{2})(?: \d{2}:\d{2})?\] ([^|\n]+)\|", log_text, re.M))
    for i, m in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(log_text)
        log_entries.append((m.group(1), m.group(2).strip(), log_text[m.end():end]))

# 8. 未監査の弱モデル entry (seed 15)
# 弱 tier モデルが実行した ingest/file back は、強モデルが raw と突き合わせて監査するまで
# 「仮説」扱い ([[AI生成物は仮説]])。監査完了は entry 本文の `監査:` 行で記録する。
# 合格条件は rubrics/ingest-audit-rubric.md。
WEAK_MODELS = {"haiku", "sonnet"}
unaudited = []
for d, label, body in log_entries:
    tag = re.search(r"@([\w.-]+)", label)
    if tag and tag.group(1).lower() in WEAK_MODELS:
        if not re.search(r"^監査:", body, re.M):
            unaudited.append((d, label))
print(f"## 未監査の弱モデル entry（@haiku/@sonnet かつ `監査:` 行なし）: {len(unaudited)}")
print("（rubrics/ingest-audit-rubric.md で raw 突き合わせ監査 → entry に `監査:` 行を追記）")
for d, label in unaudited:
    print(f"  - [{d}] {label}")
print()

# 9. seed list の staleness (seed F)
# 「session 末に seed list を更新する」運用が 3 session 連続で破られた実績があるため lint に格上げ。
# seed list 最終更新より新しい ingest/file back entry があれば flag (3 日超で ERROR)。
seed_pages = sorted((WIKI / "analyses").glob("next-overview-session-seeds-*.md"))
if seed_pages:
    seed_page = seed_pages[-1]
    seed_text = seed_page.read_text(encoding="utf-8")
    seed_dates = re.findall(r"(?:\*\*|date: )(\d{4}-\d{2}-\d{2})", seed_text)
    seed_latest = max(seed_dates) if seed_dates else "0000-00-00"
    stale_entries = [
        (d, label) for d, label, _ in log_entries
        if d > seed_latest and ("ingest" in label or "file back" in label)
    ]
    print(f"## seed list staleness（{seed_page.stem} 最終更新 {seed_latest} より後の ingest/file back）: {len(stale_entries)}")
    if stale_entries:
        oldest = min(d for d, _ in stale_entries)
        days = (date.today() - date.fromisoformat(oldest)).days
        sev = "ERROR" if days >= 3 else "WARN"
        print(f"  [{sev}] 未反映 entry が {len(stale_entries)} 件（最古 {oldest}, {days} 日経過）。session 末に seed list を更新すること")
        for d, label in stale_entries:
            print(f"  - [{d}] {label}")
print()

# 10. 撤回スローガンの下流伝播 (一人歩き検出)
# 撤回・縮小修正した主張は出典ページ Updates に残る (ローカル) が、キャッチーなスローガンは
# 既に下流へコピー済み (グローバル) で訂正が伝播しない。撤回スローガン登録テーブルを読み、
# 各 slogan を全ページで grep して「出典以外の引用箇所」を surface する (auto-judge せず人間/LLM が確認)。
# 登録テーブルの所在: [[撤回はローカルにスローガンはグローバルに伝播する]] の「撤回スローガン登録」節。
# caveat token を含む引用は ✓ (縮小後の言い換え / 撤回に言及済みの可能性)、含まない引用は ⚠ で示す。
CAVEAT_TOKENS = ("撤回", "縮小修正", "縮小", "artifact", "一人歩き",
                 "leading indicator", "交絡", "未検証", "仮説")
registry_page = WIKI / "concepts" / "撤回はローカルにスローガンはグローバルに伝播する.md"
retracted_rows = []  # (slogan, source_stem)
if registry_page.exists():
    reg_text = registry_page.read_text(encoding="utf-8")
    # 「撤回スローガン登録」節のテーブル行をパース: | slogan | 出典 | ... |
    m = re.search(r"## 撤回スローガン登録.*?\n(.*?)(?:\n## |\Z)", reg_text, re.DOTALL)
    if m:
        for row in re.findall(r"^\|(.+)\|\s*$", m.group(1), re.M):
            cells = [c.strip() for c in row.split("|")]
            if len(cells) < 2:
                continue
            slogan, source = cells[0], cells[1]
            # ヘッダ行・区切り行をスキップ
            if slogan in ("slogan(grep)", "") or set(slogan) <= set("-: "):
                continue
            retracted_rows.append((slogan, source))

# status 分け (seed 19: 撤回後サーベイランスの周期操作化):
#   ⚠>0 = active worklist (未張替 downstream、lint session が縮小後言い換えへ張替で消化)
#   ⚠=0 かつ citer>0 = remediated (張替完了、regression 監視のため登録は残す = surveillance のみ)
#   citer=0 = archive 可 (本文から slogan 文字列が完全消滅、監視不要)
slogan_status = []  # (slogan, source, citers, warn_count)
for slogan, source in retracted_rows:
    citers = []  # (page_ref, has_caveat)
    for path in page_paths:
        if path.stem == source or path.stem == registry_page.stem:
            continue  # 出典ページと登録ページ自身は除外
        text = path.read_text(encoding="utf-8")
        if slogan in text:
            has_caveat = any(tok in text for tok in CAVEAT_TOKENS)
            citers.append((page_ref(path), has_caveat))
    slogan_status.append((slogan, source, citers, sum(1 for _, ok in citers if not ok)))
active = sum(1 for _, _, _, w in slogan_status if w > 0)
surveil = sum(1 for _, _, c, w in slogan_status if w == 0 and c)
archivable = sum(1 for _, _, c, _ in slogan_status if not c)
print(f"## 撤回スローガンの下流伝播（出典で撤回済みだが下流が引き続けている）: {len(retracted_rows)} slogan 登録"
      f"（active worklist {active} / surveillance {surveil} / archive 可 {archivable}）")
print("（登録: [[撤回はローカルにスローガンはグローバルに伝播する]] / ⚠=未張替=lint session で縮小後の言い換えへ張替）")
for slogan, source, citers, warn_count in slogan_status:
    if not citers:
        status = "🗑 archive 可（本文から消滅、登録から除去してよい）"
    elif warn_count > 0:
        status = f"⚠ active worklist（{warn_count} 件を lint session で張替）"
    else:
        status = "✅ remediated（張替完了、regression 監視のため登録維持）"
    print(f"  「{slogan}」(出典 {source}): 下流 {len(citers)} 件, うち未張替(⚠) {warn_count} 件 → {status}")
    for ref, ok in sorted(citers):
        print(f"    {'✓' if ok else '⚠'} {ref}")
