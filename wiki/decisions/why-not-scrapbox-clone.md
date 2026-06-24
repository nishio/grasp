---
type: decision
summary: Scrapbox を Co-層とグラフモデル層に分解し、Co- を削いでグラフモデルだけを local・単一AI所有・CLI で再現する（design B）。Scrapbox 忠実 clone（A）でなく、Scrapbox が持たない identity-without-name 層を足す
sources:
  - llm-wiki 設計対話 2026-06-23
  - nishio 指摘 2026-06-24「行を挿入した瞬間に後続行の ID が変わる設計は良くない」
---

# Decision: Scrapbox を忠実 clone せず、identity-without-name を足した「あるべき姿」を作る

決定: **B（あるべき姿を作る）**。Scrapbox 忠実 clone（A）ではない。
（grasp = Scrapbox のグラフモデル − Co- + identity-without-name。以下、この選択を内部で **design B** と呼ぶ。）

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

- **A**: グラフ affordance は得るが、Scrapbox の **name=identity 欠陥** も相続する。Scrapbox は page-title = identity。rename してもリンクは切れない — 参照側の `[旧名]` を**自動で書き換える**か **redirect** を張って生存させる。欠陥は「リンクが切れること」ではなく、**そのリンク生存解が払うコスト**: **書き換え＝参照ページの文意が保存されない**（`[弱い紐帯]が重要` → 改名 → `[偶然の再接続]が重要` になる）／ **redirect＝旧名 stub が累積**（名前が増える）。identity-without-name はこの二択を消す（id link ゆえ rename で書き換えも redirect も要らない）。persona 別の含意は [[positioning-two-personas]]。
- **B（採用）**: グラフ affordance ＋ Scrapbox が **持たない** identity-without-name 層（page `id` / `aliases`, `line-id`）＋ フラット。
- 根拠: 親 llm-wiki が B の仕様を既に部分的に書いている — `名前ではなくIDで識別する設計` の「本wikiでの実装可能性」節（frontmatter id/aliases）、`目的が先、Wiki は後`（フラットの根拠）。

## 用途の確定（あ）: LLM-author 向け、人間 UI なし

materialized グラフは **LLM-author の retrieval / 整合性**のため。人間向け Web UI は作らない。狙いは、**ブラウザで人間がやっている関連リンク・行リンクの所作を、CLI だけで AI が "体験" できる**こと。→ `read ＝ 近傍同梱`（v1 実装は [[grasp-v1-implemented]]）。

## cosense-cli との区別

shokai 製 `@helpfeel/cosense-cli` は *hosted な多人数 Cosense* への CLI アクセス。grasp は **local・単一ユーザ・AI 所有のグラフストア**。「CLI for Cosense」ではなく「Scrapbox のデータモデルを持つ LLM 用 local substrate」。別物。

## 帰結

- v1 実装済みの CLI surface / data model は [[grasp-v1-implemented]] に保持する。
- 未実装の write / identity / Markdown adapter などは [[grasp-backlog]] に保持する。

## Open Questions

- B の identity 層をどこまで最初から入れるか（MVP は line-id 自動のみ、page id は後、でもよい）。
- フラット vs 既存 llm-wiki の concepts/analyses/ 階層との互換（互換を取るとフラット原則と緊張）。

## Updates

### 2026-06-23: identity-without-name の consumer 側価値（AI 引用の時間安定性）

出典: [[ai-consumer-feedback-2026-06-23]] Tier 4。これまで identity-without-name の rationale は**著者側**（rename で参照ページの文意が壊れない・redirect stub が累積しない、上記 fork A の議論）に置いていた。主たるユーザ＝AI consumer 観点で**消費者側の価値**を一つ足す:

AI はユーザに答える時、根拠をページ単位で引用する（「`KJ法` ページより」）。将来 write/rename が入って title が動くと、**過去セッションで AI が出した引用が腐る**（指すページが別物 or 消失）。安定 id で cite できれば、AI の回答は edit を跨いでも検証可能なまま残る。

∴ identity-without-name は「rename で参照ページの文意が壊れない」（著者側）に加えて「**AI の引用が時間を跨いで安定する**」（消費者側）の価値を持つ。write 層設計時の要件: `read --json` が title と別に **安定 page-id を必ず含む**こと。これは read 出力 field としては既済（`Page.to_summary()` が `id` を含む、[[grasp-v1-implemented]]）。未済は id を rename を跨ぐ stable identity にする page-id policy（[[grasp-backlog]] write/identity）。横断原理は [[ai-consumer-cost-and-trust]]。

### 2026-06-24: `page.id:line-index` は安定 line identity ではない

nishio 指摘: 「行を挿入した瞬間に後続行の ID が変わる」設計は良くない。これにより v1 の `page.id:line-index` は **安定IDではなく positional locator** と整理する。read-only snapshot で行を指すには便利だが、write / transclude / 長期引用を跨ぐ identity ではない。

安定 line identity の原則:

- `line.id` は opaque stable id。
- `line_index` は現在の表示順という属性であり、identity ではない。
- 外部 source（Cosense export など）が line id を持たない場合、grasp が初回 import 時に line id を mint し、store / identity journal に保持する必要がある。
- 再 import / sync では旧 lines と新 lines を diff し、同一と判定できる line だけ id を引き継ぐ。挿入行は新 id、削除行は tombstone、split / merge / 曖昧一致は勝手に同一視しない。

要点: **stable ID requires memory**。source に line id が無いなら、content hash / line index / path から deterministic に作るのではなく、grasp 側が一度発行した identity を保存し続ける。content hash は本文編集で変わるため text=identity になり、line index は挿入で変わるため position=identity になる。どちらも identity-without-name の目的に反する。実装要件は [[grasp-backlog]] の Local write and identity layer に保持する。

### 2026-06-24: ScrapBubble の `followRename` ＝ name=identity 欠陥の downstream 証拠

[[scrapbubble]]（takker99 の Scrapbox 閲覧 UserScript）を ingest した際の対比。ScrapBubble は title が動くと飛び先 bubble を見失うため `?followRename=true` で**改名を追いかける**実装を持つ。これは上記 fork A で論じた **name=identity 欠陥**（Scrapbox は page-title=identity）が、著者側だけでなく**閲覧ツール側にも felt な問題**であることの downstream 証拠。直し方が対照的: ScrapBubble は identity 層を足さず fetch 時に改名を追う workaround、grasp は data model（page `id`/`aliases`・stable line-id）で直して参照が改名を跨いで壊れないようにする（identity-without-name）。∴ 「title=identity だと閲覧側も改名追従コストを払う」という消費者外からの補強材料。

さらに ScrapBubble と grasp は **同じ Scrapbox の read グラフ模型を消費者だけ替えて実装した双子**（ScrapBubble=人間ブラウザ hover GUI / grasp=AI CLI）。「ブラウザで人間がやっている関連リンク・行リンクの所作を CLI だけで AI が体験できる」（上記「用途の確定」）という中核仮説を、別消費者で先に実装した先行例。ただし ScrapBubble の `whiteList` 透過は **Co-（多人数：他者 project 読み）と非 Co-（自分の public+private 統合）を束ねている**。grasp が継ぐ cross-project（[[whole-store-graph-and-cross-project-edges]]）は Co- を削いだ後者だけ＝1 AI が複数 store を所有して横断する形。詳細は [[scrapbubble]]。
