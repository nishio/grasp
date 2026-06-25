---
type: entity
summary: grasp の release / store compatibility history。version は `<major>.x.y`。major は product line（`1`=read line / `2`=write・authoring line）、x は store format / materialized index semantics が変わる時、y は store format が変わらない時に進める。write の alpha/stable は version でなく write 系 verb の SLA ラベルで表す（version 非依存）。
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

### Major version = product line（`2` = write/authoring line）

メジャー番号は **product line** を標す。これは厳密 semver でなく store-compat 台帳の major（nishio 合意 2026-06-24、根拠は [[write-layer-alpha-and-replay-test]]）。

- `1` = **read line**。AI が CLI + Skill で local graph store を**読む** line（`1.x.y`、v1 系）。
- `2` = **authoring line**。read line に加えて write/identity（id-link write・rename で参照不壊・transclude・come-from declare/render）を持つ line（`2.x.y`）。read-only(`1`) → read+write は本プロジェクト最大の概念変化（[[development-arc-retrieval-ahead-of-authoring]]）なのでメジャーで標す。
- `x` / `y` の意味は major を跨いでも同じ（`x`=store generation、`y`=store-compatible）。

**alpha は version に載せない**: write が alpha かどうかは version 番号でなく **write 系 verb に付く SLA ラベル**で表す（read=stable / write=alpha を別 SLA、[[write-layer-alpha-and-replay-test]] 決定1）。∴ `2.0.0` は write verb が alpha ラベル付きで載った最初の line。`2.0.0-alpha.N` の prerelease に逃げず、alpha→stable はラベルを外す SLA 変更として version bump と独立に扱う。

**`2.0.0` 境界（cadence A）**: 最高リスクのスライス（stable identity + re-import diff、次いで rename）が replay test（この repo の過去 wiki 編集の再現、[[write-layer-alpha-and-replay-test]] 決定2）を通った時点で main に merge し、そこを `2.0.0` とする。write系完了を待つ big-bang merge はしない（[[development-arc-retrieval-ahead-of-authoring]] の tight dogfood loop を失わないため）。以降 write / transclude / come-from は `2.x.y`。store generation `x` は `2.0.0` で 1 から再採番せず、`SCHEMA_VERSION`（内部整数）は単調増加を維持する。

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
| `1.7.1` | schema `7` | 2026-06-25 | schema `7` compatible | `backlinks <ambiguous handle>` が `resolution_status=ambiguous` と `ambiguity` を返し、`backlinks[]` / `handle_backlinks.items[]` には ambiguous handle 自体への incoming lines、`candidate_backlinks[]` には候補 page ごとの resolved backlinks を分けて返す。schema は不変 |
| `1.7.0` | schema `7` | 2026-06-25 | `1.6.x` store は rebuild | `edges` に `target_handle`, `target_handle_norm`, `target_page_id`, `resolution_status` を追加。edge resolution は `page_handles` から `resolved_unique` / `ambiguous` / `unresolved` を materialize し、ambiguous handle を unresolved target や既存 page backlink と誤分類しない。Markdown duplicate title / alias は import 全体を止めず、`read <handle>` の ambiguity 候補として surface する。duplicate frontmatter `id` は identity 衝突なので引き続き hard error |
| `1.6.0` | schema `6` | 2026-06-25 | `1.5.x` store は rebuild | SQLite schema に `page_handles` を追加し、visible handle（title / Markdown alias）と page identity `(project,page_id)` を分離する入口を作った。`read <handle>` は handle が複数 page identity に束縛される時、暗黙に片方を選ばず `ambiguity.type=handle_ambiguity` と候補 page_id / path / graph_role を返す。`read --page-id <id>` / `read --path <relative-path>` で明示 identity を選択できる。Markdown import source を import cache manifest に `source_type=markdown` / `exclude_dirs` 付きで保存し、schema mismatch recovery が Markdown folder mirror も再構築できる |
| `1.5.29` | schema `5` | 2026-06-25 | schema `5` compatible | Markdown import が `source/` / `sources/` と frontmatter `role/type: source` を `graph_role=source` と分類する。`source` role は raw 由来 digest / source-backed synthesis として保持し、`content` と同じく outgoing edges を materialize する。`drafts/` / generated temp / frontmatter `role/type: artifact|draft|generated` は `graph_role=artifact` として search には残すが outgoing edges は除外する。collision diagnostics は entry ごとの `graph_role` を返す。SQLite schema と Markdown manifest version は不変 |
| `1.5.28` | schema `5` | 2026-06-25 | schema `5` compatible | Markdown import に `--markdown-exclude-dir <name>` を追加。指定した directory basename 配下の `.md` を read-only mirror から除外し、`raw/` など heavy raw/generated directory を森スケール dogfood で避けられる。Markdown manifest version は `3` になり、exclude dirs も manifest identity に含めるため条件変更時は full rebuild。SQLite schema は不変 |
| `1.5.27` | schema `5` | 2026-06-25 | schema `5` compatible | Markdown import が `index.md` / `forest-index.md` / `maps/` / `views/` / frontmatter `role: navigation` を navigation、`log.md` / `log/*.md` / frontmatter `type: log-entry` を log artifact と分類し、これらの outgoing edges を既定 content graph から除外する。本文 lines は store に残るので `search` は hit する。Markdown manifest version は `2` になり、既存 Markdown project は次回 re-import で full rebuild される。SQLite schema は不変 |
| `1.5.26` | schema `5` | 2026-06-25 | schema `5` compatible | `PR #2` / `Open Question #4` のような issue-number 由来 numeric hashtag edge に system `semantic_annotation` を付ける初期 heuristic を追加。raw edge は保持し、`Edge.to_dict()` / path edge example / unresolved examples に annotation を出す。`unresolved` は sampled examples がすべて non-semantic な target を既定 ranking で後ろへ回す。store schema は不変 |
| `1.5.25` | schema `5` | 2026-06-25 | schema `5` compatible | Markdown import の title resolution に first H1 fallback を追加。frontmatter `title` が無い file は first H1、さらに無ければ file stem を page title にする。file stem は引き続き alias。既存 Markdown store はそのまま読めるが、H1 title を反映するには `grasp import --markdown <folder>` の再実行が必要。store schema は不変 |
| `1.5.24` | schema `5` | 2026-06-24 | schema `5` compatible | Cosense JSON export の line が `{text, created, updated, userId}` dict ではなく plain string の場合も import できるようにした。string line は本文 text として扱い、created / updated / userId は `None`。PR #2（takker99）を merge し、回帰テストを追加。store schema は不変 |
| `1.5.23` | schema `5` | 2026-06-24 | schema `5` compatible | `acquire` が acquisition criteria fingerprint / candidate updated range / page manifest を store metadata に保存し、同じ criteria の再実行時は hosted metadata の `updated` が変わらないページを local store から再利用する。`remote_fetched` / `reused` / `same_criteria_as_previous` を返す。store schema は不変 |
| `1.5.22` | schema `5` | 2026-06-24 | schema `5` compatible | `cross-project-acquire` の取得後 summary に `reciprocal_refs` と `top_internal_links` を追加。取得した `<project>:semantic` slice 内で source project へ戻る `[/source/...]` refs と、partial corpus 内の上位 internal link targets を bounded に返す。store schema は不変 |
| `1.5.21` | schema `5` | 2026-06-24 | schema `5` compatible | `cross-project-acquire` を追加。`cross-project-refs --semantic-only` の seed titles から複数 target project を `<project>:semantic` namespace に一括 partial acquire し、project ごとの fetched / failed / diagnostic / page sample を bounded summary として返す。`--dry-run` で plan のみ確認できる。store schema は不変 |
| `1.5.20` | schema `5` | 2026-06-24 | schema `5` compatible | `acquire` fetch failure diagnostics を追加。`failed_pages[].error_class` と top-level `diagnostic` を返し、全 candidate fetch 失敗時は `diagnostic.type=all_failed` / `next_actions[]` で空 partial corpus の誤読を防ぐ。`cosense` symlink はあるが `env node` が失敗する case は `command-env` に分類する。store schema は不変 |
| `1.5.19` | schema `5` | 2026-06-24 | schema `5` compatible | `cross-project-refs` に seed preflight を追加。各 target project に semantic `seed_titles` / `seed_candidates` / `acquire_recipe` を返し、`--seed-dir` 指定時は project 別 seed file と runnable `acquire --seed-file` command を生成する。store schema は不変 |
| `1.5.18` | schema `5` | 2026-06-24 | schema `5` compatible | `cross-project-refs` を追加。保存済み行テキストから Cosense shorthand `[/project/page]` を parsed link target として抽出し、semantic / icon / project-root / self-project に分類して project 別に rank する。`search "[/"` の line-level workaround ではなく target-aware extraction として、cross-project acquisition seed 生成の前処理に使う。store schema と materialized internal edges は不変 |
| `1.5.17` | schema `5` | 2026-06-24 | schema `5` compatible | `co-links` に `--rank slice|raw` と `target_relation` を追加。既定 `slice` は query-containing target title を後ろへ回して narrower slice handle を先に出し、`raw` は従来の count order を保持する。`gather` は slice ranking を明示する。store schema は不変 |
| `1.5.16` | schema `5` | 2026-06-24 | schema `5` compatible | `mentions` summary に come-from 昇格候補の初期 heuristic scoring を追加し、`gather` に returned / total / omitted row counts と count basis を追加。`gather --budget` は引き続き厳密 token packing ではない。store schema は不変 |
| `1.5.15` | schema `5` | 2026-06-24 | schema `5` compatible | `mentions --unlinked` を追加。bare mention のうち、page に query-containing link target が無い `unlinked-page` だけを返す明示 surface。summary は全 literal hit の監査値を維持し、returned lines のみ絞る。store schema は不変 |
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

- Current public compatibility version: `1.7.1`
- Current internal `SCHEMA_VERSION`: `7`
- Current package metadata should match `1.7.1`; pre-policy `0.1.0` は release compatibility を表す番号として使わない。
