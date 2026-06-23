---
type: entity
summary: SQLite FTS5 trigram を `grasp search` の高速化に使えるか検証したメモ。結論は「safe query の候補 prefilter としては有効だが、literal substring semantics を守るには `LIKE` fallback / post-filter が必要」
sources:
  - raw/nishio.json
  - grasp/sqlite_store.py
  - [[grasp-cli-mvp]]
  - Codex verification session 2026-06-23
---

# entity: FTS5 trigram search verification

`grasp search` は現在、SQLite `lines.text LIKE` による literal substring search で実装されている。FTS5 trigram はこの search の高速化候補だが、`grasp search` の semantics（`line.text` に query が literal substring として含まれる行を返す）をそのまま満たすわけではない。

## 検証結果（2026-06-23）

FTS5 trigram は **候補 prefilter としては有効**。

実測（`raw/nishio.json` → SQLite store）:

| query | 現行 `lines LIKE` best | hybrid (`MATCH` → `LIKE`) best |
|---|---:|---:|
| `盲点カード` | 0.121s | 0.001s |
| `民主主義` | 0.128s | 0.013s |
| `Scrapbox` | 0.127s | 0.029s |
| `cosense` | 0.118s | 0.002s |
| `関係性` | 0.125s | 0.003s |
| `トップダウン` | 0.126s | 0.002s |

ただし:

- 2文字 query（`盲点`, `知識`, `AI` など）は trigram `MATCH` に乗らない。
- 記号入り query（`[盲点カード]`, `C++`, `foo-bar`, `AI/LLM`）は FTS query syntax と衝突して error または別解釈になる。
- `MATCH 'abc bcd'` は literal substring `abc bcd` だけでなく `abcd`, `abcde`, `abcXbcd` も返した。つまり `MATCH` は literal substring search ではない。

## 実装判断

現段階では `grasp search` は correctness 優先で `lines.text LIKE` を維持する（[[grasp-cli-mvp]]）。

将来 hybrid を入れるなら:

- `len(query) >= 3` かつ safe query（空白・記号・FTS syntax なし）の時だけ `MATCH` で候補 line_id を絞る。
- その後に必ず `line.text LIKE '%query%'` をかけ、literal substring semantics を保証する。
- 2文字 query / 記号入り query は現行 `lines.text LIKE` に fallback。

この `LIKE` は全 lines ではなく FTS 候補集合にだけかかるため、速度メリットは残る。これは「本文検索の未実装」ではなく、**search 高速化の未実装候補**。

## 影響範囲

- `grasp search`: 現状は `lines.text LIKE`。FTS5 hybrid は未実装。
- Markdown / Obsidian indexed mirror: search index を設計する時も、短い日本語 query・記号入り query・literal substring semantics で同じ注意が要る（[[markdown-obsidian-indexed-mirror]]）。
- 配布/言語選択: `search` latency は host 言語でなく SQLite index 設計の問題。native 化より search index の方が効く可能性が高い（[[language-and-distribution]]）。
