---
type: spec
summary: grasp が提供する CLI 動詞と data model の source of truth。Codex はこれに実装を合わせる。design が固まるにつれ上書き更新（spec=現状、log=出来事）
sources:
  - llm-wiki 設計対話 2026-06-23
---

# grasp SPEC — CLI surface + data model

> Codex 向け source of truth。**上書き更新**で常に「現状の設計」を表す（履歴は log と decisions に）。

## 一行

単一 AI 所有の local グラフ知識ストア。`[[wikilink]]` で結ばれた **行ベースのページ群**を、自動双方向リンク・2-hop・行リンク・未解決 link target（赤リンク）つきで CLI から読み書きする。**読む単位は「ファイル」でなく「近傍込みのページ」**。

## 中核原理

1. **read ＝ 近傍同梱** — `read <title>` は本文だけでなく **逆リンク（行文脈つき）・related pages・未解決 link target** を一体で返す。人間がブラウザでページを開くと関連が一望に入るのを、AI が一発で得る。*query はオプトイン、体験はデフォルトで近傍が同梱*。これが「グラフ DB を CLI で叩く」と「Scrapbox の体験を CLI で」の差。

2. **行リンク（line links）** — 逆リンクは「ページ単位」でなく `(page, line-id, 行テキスト)` で返す。"X に言及" でなく "この行で言及"。AI は逆リンクを全文 grep せず **文脈行だけ**受け取る ＝ retrieval が安い。Scrapbox 関連 pane の richness の正体。

3. **未解決 link target は構造事実** — 書かれたが本文のない link target は **page 実体のない graph node** として扱う。`link-stats <title>` で incoming link が 0 / 1 / N のどれかを高速に識別し、N 件あるなら page 実体がなくても `related <title>` は source pages を返せる。`unresolved` は未解決 target を link count / source pages / views / recency で rank する view であり、missing target すべてを TODO と決めつけない。

4. **identity ≠ name** — Scrapbox の name=identity 欠陥（rename で文意が変わる）を直す。ページは安定 `id`、行は `line-id`。**粒度分離: line-id は機械が自動採番（意味判断なし）／ page id は意味判断で必要な時だけ振る**（すべてに振る ＝ 早すぎる物化を避ける）。

5. **書く ＝ グラフ自動更新** — `[[X]]` を書けば X 側の逆リンクが自動で立つ。二度目の編集ゼロ。「壊れたリンク / 孤立 / 逆リンク漏れ」は lint が後から検出する欠陥でなく、**ランタイムが構造的に保証する不変条件**。

## 保存形式 = 独自フォーマット（Markdown ではない）

決定: native の保存形式は **独自フォーマット**。Markdown にしない。理由は [[persistence-custom-format]]:
- Markdown ではリンクは「ファイル内のテキスト」で **逆リンクはどこにも保存されない**→ 全文スキャンで導出 or 相手ページに書き戻して「維持」。これが逃げたかった **しがらみの発生源**。
- 独自フォーマットならリンクは **グラフのエッジ**。逆リンクは同じエッジを逆から読むだけで「維持」概念が消える（リンク／逆リンクが *2つの別テキスト事実* でなく *1つの事実*）。
- 「独自」＝ゼロから発明ではなく、**Cosense のグラフ／行モデルを正規化して native にする**（下記 import が seed）。

## 入力 = import adapter（native format とは独立）

「既存資産を読める」は native format でなく **import の責務**。native は独自のまま、複数の adapter で取り込む:
- **初手（MVP の入力）= Cosense JSON export**。pages → lines ＋ リンク構造を既に持つ ＝ native モデルの自然な seed。
- **最新化は export 反復でなく cosense-cli 差分更新**: 初回 export を seed、以降は cosense-cli で最近更新ページだけ取得して upsert（[[incremental-sync]]）。∴ import adapter は bulk seed と incremental delta の2モード（M2-4）。
- 後で Markdown adapter も足せる（既存 llm-wiki 森 40+ を読める）。← native を Markdown にしなくても達成。
- 実物の export で確定（スキーマ詳細は [[cosense-json-export]]）: ① **lines に安定 id は無い** → import 時に grasp が line-id を採番（原理4 と整合）。② **link graph は export に保存されない** → line.text を parse してエッジを materialize。③ link 構文 `[...]` は overloaded（内部リンクは 62.7%、残りは外部 URL / icon / 装飾 `[* ]` / cross-project `[/p/x]`）。`[[...]]` は **bold でリンクでない**（grasp の `[[wikilink]]` と逆）。④ リンク解決は normalize（case-insensitive ＋ 空白畳み込み）。
- MVP parser は上記に加え、実データで code/list/decoration 記法が unresolved target 上位を汚すため **inline backtick 内・ASCII index 風 `xs[i]` / `func()[0]`・数字のみ `[1]`・連続 `*`/`-`/`_` 装飾 `[** x]` を link としない**。この strict parser で `raw/nishio.json` は 120693 edge / unresolved target 41750（先の 133022 / 61613 / 45703 は broad bracket 分類）。

## データモデル（暫定）

- **page**: `id`（安定・不変, 必要時のみ採番）, `title`（表示・変更可, `aliases[]` 可）, `lines[]`
- **line**: `line-id`（機械が自動採番・安定。MVP は `page.id:line-index`）, `text`（forward links は text から parse）
- **link graph**: **エッジを native に保持**。forward / backward は同一エッジの両読み（backlinks の「維持」は不要、O(1)）。2-hop はグラフ隣接。
- **unresolved link target**: link target だが page が存在しない node。`link_count` と `source_page_count` を持つ。

## MVP（Codex 最初の一歩）

**Cosense JSON export 1ファイルを読み取り専用で CLI から扱う**。書き込み・identity 層・Markdown adapter は後。
- import: Cosense export → 正規化（page/line/edge、line-id 採番）→ in-memory（or 独自 store）
- 実装: Python package `grasp`。`python3 -m grasp ...`（または console script `grasp`）で起動。`--export` 未指定時は `$GRASP_EXPORT` → `raw/nishio.json` を探す。`--json` で機械可読出力。
- 動詞: MVP 必須の `read`（近傍同梱）/ `backlinks`（行つき）/ `unresolved`（未解決 target ranking）に加え、read-only helper として `related` / `link-stats` / `peek` / `suggest` も持つ。
- read は lines[0]（Cosense title 行）を本文に残す。完全性と line-id 安定性を優先し、重複表示は formatter 側の問題として扱う。
- `link-stats` は existing page / unresolved target の両方に対して incoming `link_count`, `source_page_count`, `link_multiplicity` (`none` / `single` / `multi`) を返す。
- `related <existing-page>` は既存 page 間 edge の 2-hop pages を返す。`related <unresolved-target>` は 2-hop ではなく、その target へ link している source pages を返す。
- `unresolved` ranking: link count → source page count → total source views → latest source updated → title。`read` 内の unresolved targets はその page から出る unresolved link に限定。
- これで「AI が CLI だけで Scrapbox グラフを体験する」中核仮説を **実データ（nishio の Cosense project: 25791 pages / 724981 lines / strict parser で edge 120693・unresolved target 41750）** で検証する（[[cosense-json-export]]）。

## 次のマイルストーン（post-MVP / step 2, なお read-only）

MVP（step 1）は実装・smoke 済み。`cosense` との実測比較（[[cosense-cli]]）で出た **2 つの差** を埋めるのが次。write / identity 層はまだ入れない（"before Co-" 維持）。優先順位はこの順。

### M2-1. on-disk store（SQLite or better）— latency 解消 ★最優先
- Status 2026-06-23: **実装済み**。`.grasp/grasp.sqlite` default、`grasp import --force` と `--rebuild-store` で再構築。通常 command は store があれば JSON を parse しない。
- 問題: 起動毎に 123MB JSON を full parse し、全コマンド一律 ~3.4s（cosense は 0.5–1.2s）。「AI が graph を流れるように体験する」中核体験を最も損なう。
- やること: import（export → page/line/edge/unresolved_targets の materialize）を一度だけ実行し、**SQLite もしくはより良いデータ構造に永続**（pages / lines / edges / unresolved_targets のテーブル）。次回以降は store を読むだけで起動。**渡された JSON は import 入力にのみ使い保存層では捨てる**（JSON のまま持ち続けない）。
- 位置づけ: これは [[persistence-custom-format]] の「独自 on-disk store」の最小実体 ＝ native store の seed。Open Q「in-memory のみ or on-disk」を **on-disk = SQLite** で解決。
- 受け入れ: 2 回目以降の `read` / `backlinks` / `unresolved` が sub-second。store は M2-4 の差分更新を見据え **upsert 可能**に設計する（immutable index にしない）。

### M2-2. `search <query>` — 本文検索（cosense 比較で最大の機能差）
- Status 2026-06-23: **実装済み**。SQLite `lines.text LIKE` で本文行を検索し、行レベル hits を返す。
- 問題: `suggest` は**タイトル部分一致のみ**。cosense `searchFullText` は本文ヒットで recall が桁違い（`盲点`: grasp 8 件 vs cosense 100 件）。
- やること: 行本文を対象にした substring/full-text 検索 verb を追加。返却は backlinks と同じ **行レベル `(page, line-id, 行テキスト)`** に揃える（行リンク機構を再利用）。
- ranking: 暫定で page.views → 出現順。`suggest`（title 補完）は別 verb として残す。
- 非目標: vector 検索（埋め込み生成）は別マイルストーン。

### M2-3. parser false-positive 修正（小）
- Status 2026-06-23: **実装済み**。連続 `*`/`-`/`_` 群 + 空白を decoration として除外。
- `[** x]` / `[*** x]`（複数 `*` の見出し装飾）が link 扱いされ unresolved target 上位を汚す（実測 `** 深い思考` link count 59）。
- 修正: decoration 判定を「先頭の連続する `*` `-` `_` 群 ＋ 空白」に拡張（現状は先頭 1 文字のみ判定）。あわせて false-negative（短い英数字 title）の監査。

### M2-4. cosense-cli 差分更新（freshness）
- Status 2026-06-23: **実装済み**。`grasp sync <project-url>` が `cosense listPages` → changed page `readPage` → SQLite upsert を行う。`--dry-run` 対応。
- 問題: export は重く（手動生成・123MB）頻繁な再取得に向かない。最新化を export 反復でやらない。
- やること: 初回 export を seed にし、以降は `cosense listPages <project> --sort updated` で最近更新ページのみ取得 → `readPage` で本文 → store に upsert ＋ edge 再 materialize。決定と grounded メカニズム（last-sync カーソル / humanize 済み updated の扱い）は [[incremental-sync]]。
- 位置づけ: "Co-" でなく単一所有 mirror の最新化（[[why-not-scrapbox-clone]] スコープ内）。import adapter が bulk seed と incremental delta の2モードになる。
- 前提: M2-1 の store が upsert 可能であること。

### この step でもまだスコープ外
write / transclude / rename（identity 層）・Markdown import adapter・vector 検索。

## CLI 動詞（surface）

| 動詞 | 返す / する | ブラウザ対応 |
|---|---|---|
| `read <title>` | 本文 ＋ backlinks(行つき) ＋ related ＋ page-local unresolved targets を一体で。page がなくても incoming link count と related source pages を返す | ページを開く |
| `backlinks <title>` | `(page, line-id, 行テキスト)` のリスト。page がない target にも効く | 関連 pane のカード |
| `related <title>` | existing page は 2-hop pages、unresolved target は source pages | 2-hop / related 表示 |
| `link-stats <title>` | existing page / unresolved target の incoming link count と 0/1/N 区別 | 赤リンク濃度 / link badge |
| `peek <title>` | 本文だけ（飛ばずプレビュー） | リンク hover |
| `suggest <partial>` | title 補完候補 | `[[` 補完 |
| `search <query>` | 本文行検索。`(page, line-id, 行テキスト)` のリスト | 全文検索 |
| `unresolved` | unresolved link target の ranked view | 赤リンク / unresolved target list |
| `sync <project-url>` | cosense-cli で最近更新ページを差分 upsert | hosted freshness |
| `write <title> <body>` | ページ作成 / 更新 ＋ グラフ自動更新 | 編集 |
| `transclude <line-id>` | 行の埋め込み / 参照 | 行参照 |
| `rename <id> <new-title>` | identity 保持で改名（リンク追従・文意保存） | name=identity 修正 |

## スコープ外（"before Co-"）

リアルタイム多人数編集 / 行単位 OT・CRDT 同期 / presence / 共有・権限 / Web UI。単一ユーザ ＋ AI には不要。これらを削ぐのが grasp の核（[[why-not-scrapbox-clone]]）。

## Open Questions

- ~~永続化形式~~ → **解決: 独自フォーマット**（[[persistence-custom-format]]）。読込は import adapter の責務に分離。
- ~~独自 store の具体~~ → **SQLite store 実装済み**。MVP は in-memory から `.grasp/grasp.sqlite` へ移行。
- **read の近傍境界**: MVP は `--backlinks-limit` / `--related-limit` / `--unresolved-limit` の上位 N。ranking の妥当性（link count/views/recency の重み）は実利用で調整。
- **Cosense link parser の厳しさ**: code/list/decoration 由来の false positive を避けるため strict にしたが、短い英数字タイトルなどの false negative は未監査。
- **page id をいつ振るか**: 「必要時のみ ＝ 意味判断」の運用ルールを誰がどう発火するか。
- **行リンクの文脈窓**: 該当行だけか、前後数行か。
- **Codex からの呼び方**: 純 CLI か MCP server 化か。
- **2-hop のコスト**: グラフが育ったとき related の計算量。

## 関連（親 llm-wiki の設計資産）

- `LLM Wiki 設計のトレードオフ` 軸5（機械 vs 意味、整合性を runtime に逃がす）— grasp はこの deterministic runtime を Scrapbox グラフモデルとして instantiate したもの
- `名前ではなくIDで識別する設計` — identity-without-name 層の出典。実装可能性節に frontmatter id/aliases 案
- `title-as-transclusion-20260522` / `gpt-cosense-transclusion-20260522` — 行 / transclusion 思考
- vil-red-links wiki — 赤リンク現象の研究（人間コミュニティ版）
