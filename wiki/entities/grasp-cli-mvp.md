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
python3 -m grasp --json backlinks 盲点 --limit 2
```

- `--export`: Cosense JSON export path。未指定時は `$GRASP_EXPORT` → `raw/nishio.json`。
- `--json`: 機械可読 JSON output。
- console script `grasp = grasp.cli:main` も定義済み（editable install すれば `grasp ...`）。

## 実装済み verbs

- `read <title>`: 本文 lines + line-level backlinks + deterministic 2-hop related + page-local wanted。
- `backlinks <title>`: `(source_page, line-id, line_text)`。red link target にも効く。
- `wanted`: 未作成 target を ranking して返す。
- helper: `related`, `peek`, `suggest`。MVP 必須ではないが read-only なので追加。

## data model 実装

- `Page`: `id`, `title`, normalized title, created/updated/views, `lines`。
- `Line`: `line_id`, line index, text, created/updated/userId。MVP の `line_id` は `page.id:line-index`。
- `Edge`: source page + source line + target title/normalized title。forward/backward は同一 edge の両読み。
- store は in-memory。起動ごとに 118MB JSON を parse するため、実データでは 1 command 約 4-5 秒。

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

この strict parser で `raw/nishio.json`: 25791 pages / 724981 lines / 123170 edges / 58944 distinct targets / 43344 wanted / normalized title collision 1。

### 残る false-positive（2026-06-23 実測）

`wanted` 上位に `** 深い思考`（count 59）が混入する。これは Cosense の見出し装飾 `[** 深い思考]`（複数 `*`）であってリンクではない。`is_internal_cosense_link` は `[* x]`（先頭 1 文字が `*-_` ＋空白）だけ除外し、2 文字目も `*` のケース（`[** x]` / `[*** x]`）を通すため漏れる。→ decoration 判定を「先頭の連続する `*` `-` `_` 群 ＋ 空白」に拡張すべき（[[SPEC]] M2-3）。それ以外のスポットチェックは正しく、例: `ニーチェ` は cosense の 1-hop にも無く真に赤リンク。

## 検証

- `python3 -m unittest discover -s tests` OK。
- `python3 scripts/lint_wiki.py` OK。
- 実データ smoke: `wanted`, `backlinks 盲点`, `read 盲点カード`, `related 盲点カード`, JSON output を確認。

## 次の実装課題

[[cosense-cli]] との実測比較で優先順位が確定（→ [[SPEC]] 次マイルストーン）:

- **on-disk store/cache ★最優先**: 毎回 123MB JSON parse で全コマンド一律 ~3.4s（cosense 0.5–1.2s）。中核体験を最も損なう律速。edge/materialized index を on-disk 永続し sub-second に。
- **本文検索 `search`**: `suggest` はタイトル部分一致のみ。cosense `searchFullText` 比で recall が桁違い（`盲点`: 8 件 vs 100 件）。行レベル（page, line-id, 行テキスト）で返す verb を追加。
- parser false-positive 修正: `[** x]` 系装飾（`** 深い思考` count 59）が `wanted` を汚す。decoration 判定を複数 `*-_` 群対応に拡張。あわせて false-negative（短い英数字 title）監査。
- `#tag` を page link と同等に扱うか。
- line context window: backlink は現状 hit line のみ。前後行を付けるか。
- `wanted` ranking の重み調整: count/views/recency の順で十分かは利用で検証。
