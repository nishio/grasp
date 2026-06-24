---
type: entity
summary: grasp の release / store compatibility history。v1 系の version は 1.x.y とし、x は store format / materialized index semantics が変わる時、y は store format が変わらない時に進める。
sources:
  - wiki/log.md
  - wiki/entities/grasp-v1-implemented.md
  - wiki/entities/grasp-cli-mvp.md
  - wiki/decisions/multi-project-store.md
  - grasp/sqlite_store.py
  - pyproject.toml
---

# history

このページは `grasp` の release 番号と store 互換性の履歴を保持する。`[[log]]` は細かい時系列、ここは **どの version がどの store / index semantics を読むか** の source of truth。

## Versioning policy

v1 系では public version を `1.x.y` とする。

- `1`: v1 product line。Cosense JSON / hosted sync / future Markdown adapter などの入力差はあっても、AI が CLI + Skill で local graph store を読む line。
- `x`: store format generation。SQLite table shape だけでなく、parser / materialized edge / unresolved target の semantics が変わり、既存 store を current truth としてそのまま読めない時に上げる。
- `y`: store compatible change。CLI UX、command 追加、formatter、recovery hints、docs、Skill、performance、sync logic など、既存 current store を再構築しなくてもよい変更で上げる。

`grasp.sqlite_store.SCHEMA_VERSION` は内部の store compatibility key として単調増加する整数文字列を維持する。`x` が上がる時は原則 `SCHEMA_VERSION` も上がる。`y` だけの変更では `SCHEMA_VERSION` は変えない。

## Store bump criteria

`x` を上げる変更:

- SQLite の table / column / index / key structure が変わる。
- page id / line id / project namespace の解釈が変わる。
- link parser の結果が変わり、`edges` / `unresolved_targets` / backlinks / related の答えが変わる。
- 古い store を読み続けると「速いが古い」ではなく「意味が違う」結果になる。

`y` に留める変更:

- 既存 store から返す表示や JSON field の補助情報を増やす。
- zero-hit recovery、friendly error、help / README / Skill の改善。
- `sync` の取得戦略や import cache からの復旧など、current store format 自体を変えない upgrade path。
- query performance 改善。ただし index 追加で SQLite schema を変えるなら `x`。

`x` bump 後の期待挙動: 通常 command は import cache があれば旧 store から current schema へサイレント再構築してから続行する。`stats` は診断用なので、古い schema をそのまま観測できる。再構築後に edges / unresolved counts や `imported_at` が変わるのは schema / parser 変更の結果であり、hosted sync や corruption ではない。current facts は [[grasp-v1-implemented]]。

## Version history

2026-06-23 の同日 MVP churn を、v1 互換性履歴として後付けで整理したもの。git tag / PyPI release の履歴ではなく、store compatibility ledger。

| Version | Internal store | Date | Store compatibility | Main changes |
|---|---:|---|---|---|
| `1.5.14` | schema `5` | 2026-06-24 | schema `5` compatible | `read --related-snippets --related-snippet-mode edge` を追加。related/source item の冒頭ではなく、その item を導いたリンク行を `snippet_lines[]` と `snippet_window` に同梱できる。既定 mode は従来通り `lead`。store schema は不変 |
| `1.5.13` | schema `5` | 2026-06-24 | schema `5` compatible | `mentions <query>` / `co-links <query>` / `gather <query>` を追加。裸言及を parsed internal-link span 外で数え、page-level link status で分類し、query 行の co-link slice と bounded gather bundle を返す。store schema は不変 |
| `1.5.12` | schema `5` | 2026-06-24 | schema `5` compatible | `peek --line-offset N` を追加。`--line-limit M` と組み合わせて本文行だけをページングし、JSON は `line_offset`, `lines_truncated_before`, `lines_truncated_after` を返す。store schema は不変 |
| `1.5.11` | schema `5` | 2026-06-24 | schema `5` compatible | `search --context N` を追加。各 hit に前後 N 行の `context_lines[]` と `context_window` を同梱し、text 出力でも hit 直下に bounded context を表示する。検索 semantics / store schema は不変 |
| `1.5.10` | schema `5` | 2026-06-24 | schema `5` compatible | `grasp import --markdown <folder>` を追加。Markdown folder を read-only mirror として既存 SQLite graph store に materialize する。frontmatter `title` / `id` / `aliases` / `tags`、wikilinks / hashtags、alias canonicalization、manifest-based incremental re-import に対応 |
| `1.5.9` | schema `5` | 2026-06-24 | schema `5` compatible | `read --around-line <line-id> --line-context N` を追加。完全 `line_id` から同一ページを解決し、中心行の前後 N 行だけを返す。JSON は `line_window` を返し、通常 read では `line_window: null` |
| `1.5.8` | schema `5` | 2026-06-24 | schema `5` compatible | text 出力の line-id を既定で実行内ローカル別名（`P1:0` など）に短縮し、先頭付近に `P1=<page-id>` legend を出す。`--json` は従来通り完全 ID、text で完全 ID が必要な時は `--full-ids` |
| `1.5.7` | schema `5` | 2026-06-24 | schema `5` compatible | `path` の no-path negative-result contract を追加。端点が resolve できるが bounded search で経路が見つからない時、`recovery_hints.path` に reason / next_max_depth / related / backlinks / link-stats を返す |
| `1.5.6` | schema `5` | 2026-06-24 | schema `5` compatible | `search` の既定を空白も含む literal line substring に戻し、`--mode boolean` と `--scope line|page` を追加。boolean は AND/OR/NOT、括弧、quoted phrase、隣接 term の implicit AND を扱う。旧 page 単位 AND は `--mode boolean --scope page` で明示 |
| `1.5.5` | schema `5` | 2026-06-24 | schema `5` compatible | `related` 空結果に `recovery_hints` を追加。`path <A> <B>` を追加し、pages ∪ unresolved targets を node、materialized internal links を無向 edge として `--max-depth` bounded な shortest path と根拠 line を返す |
| `1.5.4` | schema `5` | 2026-06-23 | schema `5` compatible | `read --related-snippets` / `--related-snippet-lines N` を追加。related 2-hop / missing target の source pages に先頭 N 行（default 5）を `snippet_lines` として同梱し、Cosense related pane 風の近傍読解を 1 call で行えるようにした |
| `1.5.3` | schema `5` | 2026-06-23 | schema `5` compatible | `search` の zero-hit 時に normalized fallback を追加。NFKC query 正規化＋長音除去は SQLite `REPLACE` で大規模 store でも使い、text 出力は `[normalized]`、JSON は `match_mode: "normalized"` を返す。完全な kana 変換の Python scan は 50k lines 以下の小規模 store のみに制限 |
| `1.5.2` | schema `5` | 2026-06-23 | schema `5` compatible | `search` の recall 改善。単一語は従来通り line substring、空白区切り複数語は page 単位 AND で全語を含む page の該当行を返す。`search` 空結果にも `recovery_hints` を追加。SQLite schema / parser semantics は変えない |
| `1.5.1` | schema `5` | 2026-06-23 | schema `5` compatible | `grasp acquire <project-url>` を追加。admin export なしに hosted Cosense から読める page を partial corpus として seed する。acquisition metadata は既存 metadata table に key/value として保存し、SQLite schema / parser semantics は変えない |
| `1.5.0` | schema `5` | 2026-06-23 | `1.4.x` store は rebuild | `#tag` と数字のみ `[1]` / `[2024]` を internal link として edge 化。parser / index semantics が変わるため store generation を更新。zero-hit recovery hints、verb 後 `--json` 受理、store missing diagnostics もこの build に含む |
| `1.4.1` | schema `4` | 2026-06-23 | schema `4` compatible | import 済み JSON を `<store>.imports/` に保存し、schema mismatch 時に import cache から自動再構築する upgrade path を追加。SQLite store format 自体は変えない |
| `1.4.0` | schema `4` | 2026-06-23 | `1.3.x` store は rebuild | 1つの SQLite store に複数 project を namespace として保持。`projects` table を追加し、pages / lines / edges / unresolved tables に `project` 列を持たせる |
| `1.3.0` | schema `3` | 2026-06-23 | `1.2.x` store は rebuild | `wanted` 語彙を捨て、`unresolved` / `unresolved_targets` に破壊的変更。command / JSON field / SQLite table 名が変わる |
| `1.2.0` | schema `2` | 2026-06-23 | `1.1.x` store は rebuild recommended | `unresolved_target_examples` の前身 `wanted_examples` を materialize。ranking example 取得を N 回 query しないための store format 変更 |
| `1.1.0` | schema `1` | 2026-06-23 | first persistent store | SQLite on-disk store を導入。metadata / pages / lines / edges / wanted を materialize し、通常 command で JSON full parse しない |
| `1.0.0` | none | 2026-06-23 | no persistent store | read-only Cosense JSON MVP。`read` / `backlinks` / `wanted` / `related` / `peek` / `suggest` は毎回 JSON export を parse |

## Current state

- Current public compatibility version: `1.5.14`
- Current internal `SCHEMA_VERSION`: `5`
- Current package metadata should match `1.5.14`; pre-policy `0.1.0` は release compatibility を表す番号として使わない。
