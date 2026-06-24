---
type: concept
summary: grasp は Scrapbox 一本の clone でなく、Cosense / デライト / howm から別々の核を1つずつ抜き取って CLI で合成したもの。Cosense=グラフモデル（自動双方向・2-hop・赤リンク・行リンク・フラット）、デライト=identity-without-name（知番）、howm=「ページ＝投影」と come-from。3ツールの弱点はどれも「本来別々の仕事を1つの仕掛けに束ねた」ことに帰着し（Cosense は `[X]` に4仕事、デライトは意味を独自語彙に、howm は retrieval を人間の Emacs 操作に）、grasp の一貫した手は層を分離して束ねを解くこと。各ツールから1つずつ捨てる: 多人数リアルタイム協調編集 / 独自語彙＋重い存在論 / 時間駆動リマインダ。デライトの引き入れ（多重所属）はリンクに前景後景型が乗った typed link とみなせ write/identity 層 backlog。
sources:
  - 対話 2026-06-24（nishio: Cosense / デライト / howm の UX を grasp と照らす、引き入れ＝前景後景型の typed link）
  - delite wiki（輪郭・知名・描写・知番・引き入れ・輪符・無番輪符）
  - 親 llm-wiki: `型付きリンク` / `名前ではなくIDで識別する設計` / gpt-delite-cosense-llmwiki-20260514
  - howm (HIRAOKA Kazuyuki): come-from / キーワードページ＝仮想出現一覧（nishio 2022 考察）
---

# Concept: grasp は Cosense / デライト / howm から1軸ずつ抜いた合成

## thesis

grasp は Scrapbox 一本を真似た clone ではなく、nishio が長年突き合わせてきた3つの個人ナレッジツールから、**それぞれ別の核を1つずつ**抜き取って CLI で合成したもの、と読める。3つは「事前分類しない・断片から始める・関係で発見する」を共有する別解で、grasp はその best part だけ取り、各ツールが抱える結合コストは継がない。

## 1軸ずつの抜き取り

| ツール | grasp が抜いた核 | 継がない（捨てた）もの |
|---|---|---|
| **Cosense** | グラフモデル＝自動双方向リンク・2-hop 関連・赤リンク（未解決 target）・行リンク・フラット。**価値の本体** | 多人数リアルタイム協調編集（共同編集・presence・共有/権限）の層。単一ユーザ＋AI には純オーバーヘッド（[[why-not-scrapbox-clone]]） |
| **デライト** | identity-without-name（知番）。名前と実体を分離し、rename しても参照が壊れない。Scrapbox の弱点の**修理パーツ** | 独自語彙体系（輪郭・知名・描写・引き入れ…）と重い存在論。「ツール作者の世界観を先に学ばせる」コスト |
| **howm** | 「ページ＝投影」と come-from。ページは実体でなく「用語 X の出現箇所一覧」という投影。判断単位を出現でなく用語に置ける（[[come-from-declared-gather]]） | 時間駆動リマインダ（todo・優先度減衰）と人間-in-Emacs 前提の grep UX |

要するに **grasp = Cosense のグラフ骨格に、デライトの知番で identity を補強し、howm の「ページ＝投影」で読み方を据えたもの**。各ツールから1つずつ捨てている。

## なぜ「抜き取り」が成立するか — 共通の失敗が「束ね」だから

3ツールの弱点はどれも「**本来別々の仕事を1つの仕掛けに束ねた**」ことに帰着し、grasp の一貫した手は**層を分離して束ねを解く**こと:

| ツール | 何を束ねたか | grasp の分離 |
|---|---|---|
| Cosense | `[X]` という1リンクに recall / retrieval 意図 / navigation / 読者ケアの4仕事（→ hub 膨張 KJ法 144→490） | 4仕事を別チャネルへ。recall=`search`/`mentions`、navigation=`read`近傍同梱、読者ケア=come-from（[[come-from-declared-gather]] §1） |
| デライト | 意味を独自語彙に束ねた（使う前に体系を理解させる） | 語彙はプレーン/借用、機構だけ（知番）を輸入 |
| howm | retrieval を人間の Emacs 操作に束ねた | 消費者を CLI 越しの AI に付け替え、grep を CLI primitive 化（[[ai-consumer-cost-and-trust]]） |

∴ grasp の設計動作は「**Cosense が `[X]` に、デライトが用語に、howm が UI に束ねていたものを解いて、CLI の別 command／別 object に割り直す**」と一言で言える。これは親 llm-wiki `LLM Wiki 設計のトレードオフ` 軸5（整合性を deterministic runtime に逃がし、意味判断だけ AI に残す）の instantiation。

## なぜ忠実 clone でないか — identity-without-name の位置

grasp は Scrapbox を忠実に真似る（clone する）方向を採らなかった。Scrapbox はページタイトル＝identity なので、rename するとリンク生存のために「参照側の文字列を自動書き換え（参照ページの文意が壊れる）」か「redirect stub を残す（名前が増える）」の二択を払う。grasp はデライトの知番に当たる仕組み（page `id` / `aliases`、`line-id`）を足してこの二択を消す＝**Scrapbox に欠けている層を加えた「あるべき姿」を作る**。この選択の記録が [[why-not-scrapbox-clone]]（そこでは内部呼称 design B）。

## UX マッピング（grasp の扱い）

各 UX を grasp がどう扱うか:

- **継承（実装済み）**: 自動双方向リンク=`backlinks`、2-hop=`related`、赤リンク=`unresolved_targets`、行リンク=`line-id`（ただし安定 identity でなく positional locator）、フラット=project namespace、後で grep=`search`、ページ＝投影=`mentions`/`backlinks`（come-from の read 側を既に持つ）、知番=page `id`/`aliases`。
- **読み替え**: 無番輪符（単一→直接 / 複数→候補一覧）= `suggest`/`mentions`/unresolved。デライトの独自語彙コスト ↔ grasp は逆に Cosense 用語＋`--help` mechanics。
- **削ぐ**: 多人数協調編集（Cosense）、時間駆動リマインダ（howm）、立体階層・遠近（デライト引き入れ）。
- **backlog**: come-from の declare/render 層、書く UX 全般（write/identity 層）、引き入れ＝型付きリンク（下記）。

## 引き入れ（デライト）＝ リンクに「前景後景型」が乗ったもの → backlog

nishio 指摘（2026-06-24）: デライトの**引き入れ**（1輪郭を複数の親に入れられる多重所属）は、無型の関連リンクではなく「**前景（親）/後景（子）**」という向き付きの包含関係が乗ったリンク＝ **typed link** とみなせる。親 llm-wiki `型付きリンク` の分類でいう「A. 構造型（contains / part_of の向き付き）」の具体例。

grasp は現状リンクが**無型**（Cosense と同じく全 predicate が related）。write/identity 層でリンクを first-class object 化する時、既出の felt-sense / come-from の2型に加えて「**型（特に向き付き構造型）を持たせるか**」が設計軸として立つ。引き入れがその最初の具体例。詳細要件は [[grasp-backlog]] の write/identity 層に積んだ。

## 留保

- grasp v1 は3ツールの **read/consume 側**しか具現していない。「軽く書く（Cosense）」「引き入れ操作（デライト）」「書き散らす（howm）」という**書く UX**は丸ごと write/identity 層 backlog。
- 消費者が AI 中心なので、substrate を持たない**公開人間読者**には come-from-at-render を出さない限り届かない（[[come-from-declared-gather]] §8）。3ツールにない grasp 固有の宿題。

## Open Questions

- 引き入れ＝構造型リンクを入れるなら、向き（前景/後景）を grasp の無向グラフ（`related`/`path` は無向で畳む）とどう両立させるか。
- 型付きリンクを著者宣言にするか、AI ingest 時に自動推定するか（親 llm-wiki `型付きリンク` の「最初は無印、後から型」運用との整合）。

## 関連

- [[why-not-scrapbox-clone]] — 忠実 clone でなく identity-without-name を足す選択
- [[come-from-declared-gather]] — howm 由来の核（ページ＝投影 / come-from / リンク4仕事の分離）
- [[ai-consumer-cost-and-trust]] — 消費者を AI に付け替える（howm の UI 束ねを解く先）
- [[grasp-backlog]] — 引き入れ＝型付きリンク、come-from declare/render、write/identity
- 親 llm-wiki: `型付きリンク` / `名前ではなくIDで識別する設計` / `書いてから整理する`
