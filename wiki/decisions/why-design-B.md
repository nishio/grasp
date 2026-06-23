---
type: decision
summary: Scrapbox を Co-層とグラフモデル層に分解し、Co- を削いでグラフモデルだけを local・単一AI所有・CLI で再現する（design B）。Scrapbox 忠実 clone（A）でなく、Scrapbox が持たない identity-without-name 層を足す
sources:
  - llm-wiki 設計対話 2026-06-23
---

# Decision: design B — 単一 AI 所有の Scrapbox 型グラフストア

決定: **B（あるべき姿を作る）**。Scrapbox 忠実 clone（A）ではない。

## 文脈

nishio の観察: Cosense は複数人前提（"Co-"）で今の設計になっているが、**一人で使っても Markdown 集合（今の LLM Wiki）より効く**。→ "Co-" になる前の Scrapbox を CLI で扱える substrate が LLM に良い knowledge system になるのでは。

## 分解: Scrapbox = Co- 層 + グラフモデル層

- **Co- 層（捨てる）**: リアルタイム多人数編集・行単位 OT/CRDT 同期・presence・共有/権限。単一ユーザ ＋ AI には純オーバーヘッド。
  - 注: "Cosense" 改名（2023）は branding で、行ベース data model 自体は元から。よって "before Co-" が指すのは技術的差分でなく **単一ユーザ設計思想への回帰**。
- **グラフモデル層（価値）**: ①自動双方向リンク ②2-hop・関連 ③行リンク ④フラット title-addressed（フォルダ階層なし、構造はリンクから創発）。**Markdown 集合に欠けているのは丸ごとこの層**。

## なぜ「今の Markdown 集合」では足りないか

今の llm-wiki は wikilink ＋ lint ＋ file-back skill で **このグラフモデルを手作業エミュレート** している。逆リンクは write-once-forward-only で、手で足すか lint で検出して直す（file-back skill は「関連ページからの被リンクも足す」と明記）。

→ felt friction ＝ **逆リンク維持の手回しコスト**。grasp はグラフを materialize してこの手回しを消す。これは親 llm-wiki `LLM Wiki 設計のトレードオフ` の **軸5「機械的処理 vs 意味判断」**（整合性を deterministic runtime に逃がし、LLM は意味的 read/write だけ）の instantiation。

## fork: A（Scrapbox 忠実 clone）vs B（あるべき姿）

- **A**: グラフ affordance は得るが、Scrapbox の **name=identity 欠陥** も相続する。Scrapbox は page-title = identity で、リンクは切れないが **タイトルを変えると文意が保存されない**（`[弱い紐帯]が重要` → 改名 → `[偶然の再接続]が重要` になる）。
- **B（採用）**: グラフ affordance ＋ Scrapbox が **持たない** identity-without-name 層（page `id` / `aliases`, `line-id`）＋ フラット。
- 根拠: 親 llm-wiki が B の仕様を既に部分的に書いている — `名前ではなくIDで識別する設計` の「本wikiでの実装可能性」節（frontmatter id/aliases）、`目的が先、Wiki は後`（フラットの根拠）。

## 用途の確定（あ）: LLM-author 向け、人間 UI なし

materialized グラフは **LLM-author の retrieval / 整合性**のため。人間向け Web UI は作らない。狙いは、**ブラウザで人間がやっている関連リンク・行リンクの所作を、CLI だけで AI が "体験" できる**こと。→ `read ＝ 近傍同梱`（[[SPEC]] 原理1）。

## cosense-cli との区別

shokai 製 `@helpfeel/cosense-cli` は *hosted な多人数 Cosense* への CLI アクセス。grasp は **local・単一ユーザ・AI 所有のグラフストア**。「CLI for Cosense」ではなく「Scrapbox のデータモデルを持つ LLM 用 local substrate」。別物。

## 帰結

- 実装は [[SPEC]] の CLI 動詞 ＋ data model に従う。
- 永続化を既存 Markdown 互換にすれば、既存の wiki森を即 grasp で読める（[[SPEC]] Open Q）。

## Open Questions

- B の identity 層をどこまで最初から入れるか（MVP は line-id 自動のみ、page id は後、でもよい）。
- フラット vs 既存 llm-wiki の concepts/analyses/ 階層との互換（互換を取るとフラット原則と緊張）。
