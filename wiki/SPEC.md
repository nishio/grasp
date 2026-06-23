---
type: spec
summary: grasp が提供する CLI 動詞と data model の source of truth。Codex はこれに実装を合わせる。design が固まるにつれ上書き更新（spec=現状、log=出来事）
sources:
  - llm-wiki 設計対話 2026-06-23
---

# grasp SPEC — CLI surface + data model

> Codex 向け source of truth。**上書き更新**で常に「現状の設計」を表す（履歴は log と decisions に）。

## 一行

単一 AI 所有の local グラフ知識ストア。`[[wikilink]]` で結ばれた **行ベースのページ群**を、自動双方向リンク・2-hop・行リンク・赤リンクつきで CLI から読み書きする。**読む単位は「ファイル」でなく「近傍込みのページ」**。

## 中核原理

1. **read ＝ 近傍同梱** — `read <title>` は本文だけでなく **逆リンク（行文脈つき）・2-hop・赤リンク** を一体で返す。人間がブラウザでページを開くと関連が一望に入るのを、AI が一発で得る。*query はオプトイン、体験はデフォルトで近傍が同梱*。これが「グラフ DB を CLI で叩く」と「Scrapbox の体験を CLI で」の差。

2. **行リンク（line links）** — 逆リンクは「ページ単位」でなく `(page, line-id, 行テキスト)` で返す。"X に言及" でなく "この行で言及"。AI は逆リンクを全文 grep せず **文脈行だけ**受け取る ＝ retrieval が安い。Scrapbox 関連 pane の richness の正体。

3. **赤リンク ＝ 自己宛キュー** — 書かれたが本文のない link target（red link）を `wanted` が一覧。単一所有なので「誰かが書く穴」でなく **「自分が次に書く TODO」**。書く側 ＝ 読む側が同一だから穴が自己宛タスクになる（人間コミュニティの赤リンクとの非対称）。

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
- 後で Markdown adapter も足せる（既存 llm-wiki 森 40+ を読める）。← native を Markdown にしなくても達成。
- 実物の export で確定（スキーマ詳細は [[cosense-json-export]]）: ① **lines に安定 id は無い** → import 時に grasp が line-id を採番（原理4 と整合）。② **link graph は export に保存されない** → line.text を parse してエッジを materialize。③ link 構文 `[...]` は overloaded（内部リンクは 62.7%、残りは外部 URL / icon / 装飾 `[* ]` / cross-project `[/p/x]`）。`[[...]]` は **bold でリンクでない**（grasp の `[[wikilink]]` と逆）。④ リンク解決は normalize（case-insensitive ＋ 空白畳み込み）。

## データモデル（暫定）

- **page**: `id`（安定・不変, 必要時のみ採番）, `title`（表示・変更可, `aliases[]` 可）, `lines[]`
- **line**: `line-id`（機械が自動採番・安定）, `text`（forward links は text から parse）
- **link graph**: **エッジを native に保持**。forward / backward は同一エッジの両読み（backlinks の「維持」は不要、O(1)）。2-hop はグラフ隣接。
- **wanted（red link）**: link target で page が存在しないエッジ。

## MVP（Codex 最初の一歩）

**Cosense JSON export 1ファイルを読み取り専用で CLI から扱う**。書き込み・identity 層・Markdown adapter は後。
- import: Cosense export → 正規化（page/line/edge、line-id 採番）→ in-memory（or 独自 store）
- 動詞: `read`（近傍同梱）/ `backlinks`（行つき）/ `wanted`（赤リンク）の3つ
- これで「AI が CLI だけで Scrapbox グラフを体験する」中核仮説を **実データ（nishio の Cosense project: 25791 pages / 724981 lines / 内部リンク 133022・distinct target 61613・うち red link 45703）** で検証できる（[[cosense-json-export]]）。

## CLI 動詞（surface）

| 動詞 | 返す / する | ブラウザ対応 |
|---|---|---|
| `read <title>` | 本文 ＋ backlinks(行つき) ＋ 2-hop ＋ wanted を一体で | ページを開く |
| `backlinks <title>` | `(page, line-id, 行テキスト)` のリスト | 関連 pane のカード |
| `related <title>` | 2-hop ページ（リンクを共有するページ） | 2-hop 表示 |
| `peek <title>` | 本文だけ（飛ばずプレビュー） | リンク hover |
| `suggest <partial>` | title 補完候補 | `[[` 補完 |
| `wanted` | 未作成 link target 一覧（自己宛キュー） | 赤リンク |
| `write <title> <body>` | ページ作成 / 更新 ＋ グラフ自動更新 | 編集 |
| `transclude <line-id>` | 行の埋め込み / 参照 | 行参照 |
| `rename <id> <new-title>` | identity 保持で改名（リンク追従・文意保存） | name=identity 修正 |

## スコープ外（"before Co-"）

リアルタイム多人数編集 / 行単位 OT・CRDT 同期 / presence / 共有・権限 / Web UI。単一ユーザ ＋ AI には不要。これらを削ぐのが design B の核（[[why-design-B]]）。

## Open Questions

- ~~永続化形式~~ → **解決: 独自フォーマット**（[[persistence-custom-format]]）。読込は import adapter の責務に分離。
- **独自 store の具体**: in-memory のみ（export を毎回読む）か、独自の on-disk 表現を持つか。MVP は前者で可。
- **read の近傍境界**: 2-hop までか、逆リンクは全件か上位 N か、赤リンクの優先順位づけ。← 実データで `wanted` ~45700 件 → **ranking 必須**が確定（[[cosense-json-export]]）。signal 候補: 出現回数 / page.views / recency。
- **page id をいつ振るか**: 「必要時のみ ＝ 意味判断」の運用ルールを誰がどう発火するか。
- **行リンクの文脈窓**: 該当行だけか、前後数行か。
- **Codex からの呼び方**: 純 CLI か MCP server 化か。
- **2-hop のコスト**: グラフが育ったとき related の計算量。

## 関連（親 llm-wiki の設計資産）

- `LLM Wiki 設計のトレードオフ` 軸5（機械 vs 意味、整合性を runtime に逃がす）— grasp はこの deterministic runtime を Scrapbox グラフモデルとして instantiate したもの
- `名前ではなくIDで識別する設計` — identity-without-name 層の出典。実装可能性節に frontmatter id/aliases 案
- `title-as-transclusion-20260522` / `gpt-cosense-transclusion-20260522` — 行 / transclusion 思考
- vil-red-links wiki — 赤リンク現象の研究（人間コミュニティ版）
