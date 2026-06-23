---
type: entity
summary: 2026-06-23 時点の read-only Cosense JSON MVP 実装。`python3 -m grasp` で local export を読み、read/backlinks/wanted を近傍込みで返す。Codex が実装した現状と次の制約を保持する
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
python3 -m grasp wanted --limit 10
python3 -m grasp backlinks 盲点 --limit 5
python3 -m grasp read 盲点カード --line-limit 8 --backlinks-limit 3 --related-limit 3 --wanted-limit 3
python3 -m grasp search 盲点 --limit 5
python3 -m grasp sync https://scrapbox.io/nishio/ --limit 20 --dry-run
python3 -m grasp --json backlinks 盲点 --limit 2
```

- `--export`: Cosense JSON export path。未指定時は `$GRASP_EXPORT` → `raw/nishio.json`。
- `--store`: SQLite store path。未指定時は `$GRASP_STORE` → `.grasp/grasp.sqlite`。
- `import --force`: export を SQLite store に materialize。通常 command は store が存在すれば JSON を再 parse しない。
- `--rebuild-store`: command 実行前に export から store を再構築。
- `--json`: 機械可読 JSON output。
- console script `grasp = grasp.cli:main` も定義済み（editable install すれば `grasp ...`）。

## 実装済み verbs

- `read <title>`: 本文 lines + line-level backlinks + deterministic 2-hop related + page-local wanted。
- `backlinks <title>`: `(source_page, line-id, line_text)`。red link target にも効く。
- `wanted`: 未作成 target を ranking して返す。
- `search <query>`: 本文行を substring 検索し、`(page, line-id, line_text)` を page.views 優先で返す。
- `sync <project-url>`: `cosense` CLI で最近更新ページだけ取得し、SQLite store に upsert する。`--dry-run` あり。
- helper: `related`, `peek`, `suggest`。MVP 必須ではないが read-only なので追加。

## data model 実装

- `Page`: `id`, `title`, normalized title, created/updated/views, `lines`。
- `Line`: `line_id`, line index, text, created/updated/userId。MVP の `line_id` は `page.id:line-index`。
- `Edge`: source page + source line + target title/normalized title。forward/backward は同一 edge の両読み。
- store は SQLite on-disk。`pages` / `lines` / `edges` / materialized `wanted` を保存する。起動ごとに 118MB JSON を parse しない。
- 実測（2026-06-23）: import 約 8 秒。store 利用時 `read 盲点カード` 約 0.7 秒、`wanted --limit 3` 約 0.7 秒、`backlinks 盲点` 約 0.4 秒。
- Update 2026-06-23: `wanted_examples` を materialize して `wanted --limit N` の example 取得を N 回 query しないようにした。Python 内部計測では `wanted(limit=100)` が約 6ms。CLI wall time は Python 起動 + output 書き出し込みで約 1.0 秒。
- `search` は SQLite FTS5 trigram を試したが、2文字日本語 query（例: `盲点`）は `MATCH` に乗らず、FTS table `LIKE` は一部日本語 substring（例: `盲点カード`）の recall を落とした。現状は correctness 優先で `lines.text LIKE` を維持。

## 実装判断

- lines[0]（Cosense title 行）は本文に残す。理由: 完全性と `page.id:line-index` の安定性を優先。重複表示は formatter の問題。
- title resolve は Cosense に合わせて normalize（casefold + whitespace folding）。
- `wanted` ranking は `count → source_page_count → total_source_views → latest_source_updated → title`。
- `related` は既存 page 間 edge の undirected adjacency から 2-hop score を出す。`via` は deterministic order にした。

## parser 補正

[[cosense-json-export]] の broad bracket 分類では内部リンク 133022 instance だったが、そのまま使うと code/list 由来の `[0]`, `[i]`, `[1]` が `wanted` 上位を汚す。

MVP parser は以下を link としない:
- 外部 URL、icon/img、decoration、math、cross-project
- Cosense の `[[...]]`（bold であって link ではない）
- inline backtick 内
- ASCII index 風 `xs[i]`, `func()[0]`
- 数字のみ `[1]`
- 連続 `*`/`-`/`_` 装飾 `[** x]`, `[*** x]`

この strict parser で `raw/nishio.json`: 25791 pages / 724981 lines / 120693 edges / 41750 wanted / normalized title collision 1。

### 残る false-positive（2026-06-23 実測）

~~`wanted` 上位に `** 深い思考`（count 59）が混入する~~ → M2-3 で修正済み。Cosense の見出し装飾 `[** 深い思考]`（複数 `*`）を decoration として除外する。`backlinks '** 深い思考'` は none。

## 検証

- `python3 -m unittest discover -s tests` OK。
- `python3 scripts/lint_wiki.py` OK。
- 実データ smoke: `wanted`, `backlinks 盲点`, `read 盲点カード`, `related 盲点カード`, JSON output を確認。

## 次の実装課題

[[cosense-cli]] との実測比較で優先順位が確定（→ [[SPEC]] 次マイルストーン）:

- ~~on-disk store/cache ★最優先~~ → SQLite store 実装済み。edge/materialized wanted を on-disk 永続し、通常 read は JSON parse しない。
- ~~本文検索 `search`~~ → 実装済み。SQLite `lines.text LIKE` で行本文を検索し、行レベル hits を返す。
- ~~parser false-positive 修正~~ → `[** x]` 系装飾は除外済み。false-negative（短い英数字 title）監査は残る。
- **cosense-cli 差分更新**: `grasp sync` 実装済み。削除/rename tombstone は未対応。
- `#tag` を page link と同等に扱うか。
- line context window: backlink は現状 hit line のみ。前後行を付けるか。
- `wanted` ranking の重み調整: count/views/recency の順で十分かは利用で検証。
