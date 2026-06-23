---
type: entity
summary: 2026-06-23 時点の read-only Cosense JSON MVP 実装。`python3 -m grasp` で local export を読み、read/backlinks/unresolved を近傍込みで返す。Codex が実装した現状と次の制約を保持する
sources:
  - grasp/cosense.py
  - grasp/cli.py
  - tests/test_cosense.py
  - raw/nishio.json
  - Codex implementation session 2026-06-23
---

# entity: grasp CLI MVP implementation

[[SPEC]] の MVP を Python package `grasp` として実装した現状。目的は「hosted Cosense を操作する CLI」ではなく、Cosense JSON export を local graph store seed として読み、AI が CLI だけで Scrapbox 型近傍を体験すること（区別は [[cosense-cli]]）。

## 実行 surface

```
python3 -m grasp unresolved --limit 10
python3 -m grasp backlinks 盲点 --limit 5
python3 -m grasp read 盲点カード --line-limit 8 --backlinks-limit 3 --related-limit 3 --unresolved-limit 3
python3 -m grasp link-stats 民主主義
python3 -m grasp related 民主主義 --limit 5
python3 -m grasp search 盲点 --limit 5
python3 -m grasp sync https://scrapbox.io/nishio/ --limit 20 --dry-run
python3 -m grasp stats
python3 -m grasp --json backlinks 盲点 --limit 2
```

- `import --cosense <json>`: Cosense JSON export を SQLite store に materialize。既存 store は確認なしで置き換える。
- `--store`: SQLite store path。未指定時は `$GRASP_STORE` → `$GRASP_HOME/grasp.sqlite` → `~/.grasp/grasp.sqlite`（単一 AI が持つ global store）。
- 通常 command は store が存在すれば JSON を再 parse しない。
- `--json`: 機械可読 JSON output。
- `grasp <cmd> --help`: mechanics SSoT。各 command の arguments / `--json` return keys / examples / notes を持つ。Agent Skill 側は具体 schema を重複保持せず、使用直前にここを読む。
- console script `grasp = grasp.cli:main` も定義済み（editable install すれば `grasp ...`）。

## 実装済み verbs

- `read <title>`: 本文 lines + line-level backlinks + deterministic related + page-local unresolved targets。page がない target でも link stats と related source pages を返す。
- `backlinks <title>`: `(source_page, line-id, line_text)`。page がない target にも効く。
- `link-stats <title>`: existing page / unresolved target の incoming `link_count`, `source_page_count`, `link_multiplicity` (`none` / `single` / `multi`) を返す。
- `unresolved`: unresolved target を ranking して返す。
- `search <query>`: 本文行を substring 検索し、`(page, line-id, line_text)` を page.views 優先で返す。
- `sync <project-url>`: `cosense` CLI で最近更新ページだけ取得し、SQLite store に upsert する。`--dry-run` あり。
- `stats`: store path / imported_at / schema version / current schema / counts を返す。古い schema の store を通常 command で開いた時は stderr に rebuild 警告を出す。README では人間向けに「件数・更新日時など」程度の概要に留め、返却キーの詳細は `grasp stats --help` とこの実装ページ側で保持する。
- helper: `related`, `peek`, `suggest`。MVP 必須ではないが read-only なので追加。

## data model 実装

- `Page`: `id`, `title`, normalized title, created/updated/views, `lines`。
- `Line`: `line_id`, line index, text, created/updated/userId。MVP の `line_id` は `page.id:line-index`。
- `Edge`: source page + source line + target title/normalized title。forward/backward は同一 edge の両読み。
- store は SQLite on-disk。schema v3 は `pages` / `lines` / `edges` / materialized `unresolved_targets` / `unresolved_target_examples` を保存する。起動ごとに 118MB JSON を parse しない。
- 実測（2026-06-23）: import 約 8 秒。store 利用時 `read 盲点カード` 約 0.7 秒、`unresolved --limit 3` 約 0.7 秒、`backlinks 盲点` 約 0.4 秒。
- Update 2026-06-23: `unresolved_target_examples` を materialize して `unresolved --limit N` の example 取得を N 回 query しないようにした。Python 内部計測では unresolved target list 100 件が約 6ms。CLI wall time は Python 起動 + output 書き出し込みで約 1.0 秒。
- Update 2026-06-23（warm-store 再計測）: warm page cache・median of 5 で各 verb の CLI wall time を測り直すと、`stats` 70ms / `backlinks 盲点 --limit 5` 54ms / `read 盲点カード`（近傍同梱）83ms / `unresolved --limit 10` 52ms / `search 民主主義 --limit 5` 178ms。**上の「0.7–1.0 秒」は早い時点の cold/単発計測で、warm steady-state は 50–180ms**。固定オーバーヘッドは bare `python3 -c pass` 33ms・`import grasp` は依存ゼロゆえ ~free（差は noise 内）。∴ 中核 read 体験は既に sub-100ms で、`search` の 178ms だけが SQLite `lines.text LIKE` 全行スキャン律速（言語非依存 → index が lever、host 言語ではない）。この再計測が [[language-and-distribution]]（実装言語論点は実測で溶ける／native 化の latency 便益はほぼ無い）の一次データ。
- `search` は SQLite FTS5 trigram を試したが、2文字日本語 query・記号入り query・literal substring semantics に注意が必要。現状は correctness 優先で `lines.text LIKE` を維持。詳細は [[fts5-trigram-search]]。
- Update 2026-06-23: 「link があるが page がない」こと自体は unresolved graph node と整理。互換性を考えず `wanted` command / JSON field / schema 名は削除し、`unresolved` / `unresolved_targets` に破壊的変更した。`link-stats` は missing target の 0/1/N を materialized `unresolved_targets` row から高速に返し、existing page は `edges.target_norm` index で count する。`related <missing-target>` は source pages を `relation=backlink-source` として返す。
- Update 2026-06-23: argparse help を mechanics SSoT として拡張。root help は global options と SSoT 方針、各 subcommand help は arguments / Returns (`--json`) / Examples / Notes を持つ。`tests/test_cli_help.py` で全 command に Returns/Examples があることを固定。
- Update 2026-06-23: store default を cwd-local `.grasp/grasp.sqlite` から `~/.grasp/grasp.sqlite` に寄せた。`$GRASP_HOME` で home を差し替え可能。理由は「単一 AI が所有する local graph store」というモデルに合わせ、どの cwd からも flag なしで同じ store を読むため。暗黙 seed は持たず、store 作成は `grasp import --cosense <json>` に一本化。
- Update 2026-06-23: `import` の `--force` を削除。既存 store がある時に拒否する UX は不要なので、同じ `grasp import --cosense <json>` が初回構築と再構築の両方を担う。実装は一時 DB 作成後に `os.replace` する既存の原子的置換を維持。
- Update 2026-06-23: [[persona1-user-test-2026-06-23]] で dogfooding UX の摩擦を記録。価値の核（`read=近傍同梱`, page なし target を source pages で読む）は成立。残課題は (1) missing + 0 incoming 時の recovery hints（例: `ユーザテスト` vs `ユーザーテスト`）、(2) verb 後 `--json` の回復、(3) search hit line から周辺本文へ行く surface。

## 実装判断

- lines[0]（Cosense title 行）は本文に残す。理由: 完全性と `page.id:line-index` の安定性を優先。重複表示は formatter の問題。
- title resolve は Cosense に合わせて normalize（casefold + whitespace folding）。
- `unresolved` ranking は `link_count → source_page_count → total_source_views → latest_source_updated → title`。
- `related` は existing page なら page 間 edge の undirected adjacency から 2-hop score を出す。page がない target なら、その target に link している source pages を返す。`via` は deterministic order にした。

## parser 補正

[[cosense-json-export]] の broad bracket 分類では内部リンク 133022 instance だったが、そのまま使うと code/list 由来の `[0]`, `[i]`, `[1]` が unresolved target 上位を汚す。

MVP parser は以下を link としない:
- 外部 URL、icon/img、decoration、math、cross-project
- Cosense の `[[...]]`（bold であって link ではない）
- inline backtick 内
- ASCII index 風 `xs[i]`, `func()[0]`
- 数字のみ `[1]`
- 連続 `*`/`-`/`_` 装飾 `[** x]`, `[*** x]`

この strict parser で `raw/nishio.json`: 25791 pages / 724981 lines / 120693 edges / 41750 unresolved targets / normalized title collision 1。

### 残る false-positive（2026-06-23 実測）

~~unresolved target 上位に `** 深い思考`（link count 59）が混入する~~ → M2-3 で修正済み。Cosense の見出し装飾 `[** 深い思考]`（複数 `*`）を decoration として除外する。`backlinks '** 深い思考'` は none。

## 検証

- `python3 -m unittest discover -s tests` OK。
- `python3 scripts/lint_wiki.py` OK。
- 実データ smoke: `unresolved`, `backlinks 盲点`, `read 盲点カード`, `related 盲点カード`, `link-stats 民主主義`, `related 民主主義`, JSON output を確認。

## 次の実装課題

[[cosense-cli]] との実測比較で優先順位が確定（→ [[SPEC]] 次マイルストーン）:

- ~~on-disk store/cache ★最優先~~ → SQLite store 実装済み。edge/materialized unresolved targets を on-disk 永続し、通常 read は JSON parse しない。
- ~~本文検索 `search`~~ → 実装済み。SQLite `lines.text LIKE` で行本文を検索し、行レベル hits を返す。
- ~~parser false-positive 修正~~ → `[** x]` 系装飾は除外済み。false-negative（短い英数字 title）監査は残る。
- **cosense-cli 差分更新**: `grasp sync` 実装済み。削除/rename tombstone は未対応。
- missing + 0 incoming の時の recovery hints（`suggest` / `search` / 近い unresolved target）。
- verb 後に置かれた root option（特に `--json`）の受理 or friendly error。
- search hit line から周辺本文へ移動する surface（`read --around-line`, `peek --line-offset`, `search --context` など）。
- `#tag` を page link と同等に扱うか。
- line context window: backlink は現状 hit line のみ。前後行を付けるか。
- `unresolved` ranking の重み調整: link count/views/recency の順で十分かは利用で検証。
