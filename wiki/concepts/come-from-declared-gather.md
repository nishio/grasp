---
type: concept
summary: リンクの仕事は4つ（recall / attention / navigation / 読者ケア）あり、Cosense は substrate が他チャネルを持たないため全部を1つの `[X]` に束ねる。これが hub 膨張の根（KJ法 exact 144 pages に対し bare mention 490 pages）。原因は「per-occurrence の局所判断 × 双方向 → hub という大域帰結」のレベルミスマッチ。howm の come-from（用語に1宣言→全出現を gather）は判断も帰結も用語-大域で揃え、「この語は一般に伝わりにくい」の1判断で全出現を読者に親切にする。grasp では come-from は3層に分かれる: read 側は既存 `mentions`（＝nishio 2022 の howm「キーワードページ＝仮想出現一覧」）、declare 側（用語を standing rule として標す）と render 側（Markdown mirror / 公開 view で裸出現を自動リンク化）が未実装。write/identity 層は come-from（用語キー・読者ケア）と felt-sense link（行キー・著者の retrieval 意図）を別物としてモデル化すべき。`mentions` には今後「AI 作ページの default 裸」「come-from 昇格候補」の scoring を足す。
sources:
  - 親 llm-wiki 設計対話 2026-06-24（link overloading → grasp-最適設計）
  - 親 llm-wiki page: `grasp最適設計はlinkからrecallを剥がす-20260624`
  - 親 llm-wiki page: `come-fromリンクは1宣言で全出現を親切にする`
  - 親 llm-wiki page: `KJ法リンクハブはリンク密度でなく用法分解で扱う-20260624`
  - howm (HIRAOKA Kazuyuki) come-from link
  - nishio 2022 howm 考察（kozaneba raw: キーワードページはファイルでなく仮想的出現箇所一覧）
---

# Concept: come-from（宣言された用語単位の gather）

親 llm-wiki の 2026-06-24 設計対話（`grasp最適設計はlinkからrecallを剥がす-20260624` / `come-fromリンクは1宣言で全出現を親切にする`）から grasp に効く部分を抜き出した原理ページ。[[kj-link-hub-audit-2026-06-24]] の数字（exact `[KJ法]` 144 pages vs body bare mention 490 pages）が**なぜ起きるか**と、grasp がそれに何を実装すべきかを与える。

## 1. リンクには4つの仕事がある

Cosense の `[X]` という1行為は、本来別々の仕事を兼ねている:

1. **recall** — 「X のページを探す」検索面
2. **attention / retrieval 意図** — 著者が「後でこの軸で戻りたい」印
3. **navigation** — 今そこへ飛ぶ
4. **読者ケア** — 「この語が分からない読者をここから説明へ辿らせる」hospitality（不安・優しさ駆動）

Cosense はこれら全部を1つの link に束ねる。理由は単純で、**substrate が他のチャネルを持たない**から。全文検索が弱いので recall を link に載せ、説明への到達手段が他にないので読者ケアも link に載せる。

grasp の設計上の意味: grasp は層を分けるので、**4つの仕事を別チャネルに割れる**。

| 仕事 | Cosense | grasp での担い手 |
|---|---|---|
| recall | link（だから過剰リンク） | `search` / `mentions`（link 不要、[[ai-consumer-cost-and-trust]] 軸1の recall） |
| retrieval 意図（著者） | link | sparse な著者 edge（felt-sense link） |
| navigation | link | `read`＝近傍同梱（[[grasp-v1-implemented]]） |
| **読者ケア** | link | **come-from（用語宣言）＋ render 時の自動リンク** |

4番目だけ grasp に機構が無い。本ページはそれを定義する。

## 2. なぜ hub が膨れるか — レベルのミスマッチ

[[kj-link-hub-audit-2026-06-24]] の 144→490 の正体は「リンク漏れ」ではない。**判断レベルと帰結レベルのズレ**:

- Cosense のリンクは **per-occurrence の局所判断**（「この出現を `[X]` にする」）。
- だが双方向なので、その局所判断 N 個が **大域的帰結（X への backlink hub）** を生む。
- 誰も「KJ法 を 490-backlink hub にしよう」と決めていない。各ページで親切に `[KJ法]` を貼った副作用として hub が**創発**する。

これが grasp-backlog の `gather` / projection 方針の *why* の核心言語化: 巨大 hub は「壊れた link graph」ではなく「局所判断が大域に漏れた artifact」。だから対処は「もっとリンクする」でも「リンクを消す」でもなく、**判断を帰結と同じレベル（用語-大域）に上げる**こと。

## 3. come-from = 判断と帰結を用語-大域で揃える

howm（HIRAOKA Kazuyuki の Emacs ノートツール）の **come-from リンク**: ある用語側に1回 `<<< 用語` と宣言すると、ノート全体のその用語の**全出現**が自動でそこへ集まる。各出現を手でリンクしない。

判断単位が **出現 → 用語** に上がる。「この用語は一般には伝わりにくいよな」という**1回の判断で、全出現（過去も未来も）が読者に親切**になる。判断（用語-大域）と帰結（gather=用語-大域）が揃うので、§2 のミスマッチが消える。hub はもはや管理する蓄積物でなく、**1宣言からの projection**。

nishio は 2022 年に既にこの核を書いていた（kozaneba raw）: **howm のキーワードページはファイルとして存在せず「キーワード X の出現箇所一覧」という仮想ページ**。これは grasp の `mentions <query>`／`backlinks` が返す仮想リストそのもの。つまり grasp は **come-from の read 側を既に持っている**。親 llm-wiki の `知識は網ページは投影-20260531`（ページ＝投影）とも同型。

## 4. grasp での come-from は3層

| 層 | 状態 | 内容 |
|---|---|---|
| **read** | 既存に近い | `mentions <query>` ＝ 用語の仮想出現一覧。come-from の「集まった姿」を読む側。[[grasp-backlog]] の `mentions` / `co-links` がここ |
| **declare** | 未実装 | 用語を come-from term として標す standing rule（store 内の per-term 宣言）。ad-hoc query を declarative に固定したもの |
| **render** | 未実装 | Markdown mirror / 公開 view を materialize する時、come-from term の**裸出現を自動リンク化**する。authoring 表現（裸＋宣言）と rendered 表現（自動リンク済み）の分離 |

read 側が既にあるので、declare（小さな per-term テーブル/フラグ）と render（mirror 生成時のルール適用）を足せば come-from が閉じる。grasp は store と `.md` を既に分離している（[[markdown-obsidian-indexed-mirror]]）ので render 側は嵌まりがよい。

## 5. リンクの2型を分離する（write/identity 層の要件）

この対話全体の収束点。Cosense の単一 `[X]` は宛先の違う**2種類のリンク**を束ねていた。grasp が write/identity 層（[[grasp-backlog]] の "Local write and identity layer"）を作る時、これを**同じものとしてモデル化してはいけない**:

- **come-from リンク** — 用語キー・1宣言・全出現・**読者**の comprehension に奉仕（standing rule）
- **felt-sense リンク** — 行キー・sparse・per-occurrence・**著者**の future-self retrieval に奉仕（edge）。親 llm-wiki `当たり判定の拡大` / `本文中の語を直接リンクにする` の inline link

identity も lifecycle も別: come-from は term に張る規則（term が動けば追従）、felt-sense は line に張る edge（stable line-id 層に乗る）。

## 6. 裸言及には3系統ある（`mentions` の設計）

[[grasp-backlog]] は現状「link gap か 意図的 non-link か」の2分で `mentions` を設計している。今回の audit で第3が判明した:

| 源 | 意味 | 正しい解決 |
|---|---|---|
| (a) 意図的 non-link | 著者が hub 肥大を避け裸で書いた | そのまま（or come-from 宣言） |
| (b) link gap | 本来リンクしたいが貼り忘れ | felt-sense link を足す |
| (c) **AI default 裸** | AI が書いたページは元々リンク疎（親 llm-wiki `本文中の語を直接リンクにする` の style A） | **come-from で一括 gather**（個別リンクは不要） |

実例: KJ法 audit でトップの bare mention page `🌀KJ法`（266 occurrences）は **AI 作ページ**で (c) だった。**書き手が AI 化するほど (c) が支配的**になり、裸言及は著者の意図と無関係に増える。∴ `mentions` の出力は「埋めるべき gap」だけでなく **「come-from 昇格候補」（高頻度・uncommon・一意の裸語）** を別枠で出すべき。目的は bulk link 化でなく、(a)(b)(c) を見分けて「1宣言で畳めるもの」を surface すること。

## 7. 安全域＝必要域

come-from は文字列マッチで gather するので多義語では過剰収集する（親 llm-wiki `同じ名前でも同じ概念とは限らない` のリスク）。だが**読者ケアが要るのは一般的でない用語**で、uncommon ≈ 一意・希少文字列＝come-from の安全域。危険域（一般的な多義語）はまさに読者ケアが**要らない**域（一般語は通じる）。**必要域＝安全域**。`KJ法` は uncommon かつ frequent かつ一意で理想的な come-from 候補。だから come-from 昇格候補の機械抽出は「uncommon さ × 頻度 × 一意性」で出せる。

## 8. 第3の消費者軸 — substrate を持たない公開読者

[[ai-consumer-cost-and-trust]] は主ユーザを「CLI 越しに読む AI（人間 UI なし）」と明示し、[[positioning-two-personas]] も author / Markdown 束ユーザの2層。読者ケアは**その外**にいる消費者を指す: **公開された PKM を読む人間ストレンジャー**（`/nishio` は個人 PKM でありながら世界公開）。

この消費者は grasp を実行できない（substrate を持たない）。だから reader-care は**公開 projection 側**でしか届かない:

- 公開面が **frozen 静的エクスポート**なら、link が全仕事を再び背負う（come-from も検索も無いので Cosense 以下に退行）。これは grasp-backlog が既に index/log で警戒している「frozen view」問題を、**本文 hub と公開人間読者**にまで拡張したもの。
- 公開面で **come-from を render 時適用**すれば、著者を over-link させずに公開読者が一般的でない用語の説明へ辿れる。AI 作ページの裸言及（§6 (c)）も同じルールで親切になる。

**scope 判断点（nishio）**: 「substrate-backed な公開 view を出す」は grasp scope か publish に委譲か。少なくとも come-from-at-render は、この第3消費者を著者の負担なしに served にする唯一の軽量機構。grasp が render 層（Markdown mirror）を既に持つ以上、ここに自然に乗る。

## 9. grasp 実装への含意（Codex 向け要約）

- `mentions <query>`: 既定 bare-only の現行 surface に、(a)(b)(c) 分類と come-from 昇格候補（uncommon×頻度×一意）の別枠 scoring を足す（[[grasp-backlog]] の既存 `mentions` 残課題を拡張）。
- come-from **declare 層**: per-term standing rule の store 表現（小さなテーブル or page frontmatter `come_from: [...]`）。
- come-from **render 層**: Markdown mirror / 公開 view 生成時に come-from term の裸出現を自動リンク化。store（裸）と view（リンク済み）の分離を保つ。
- write/identity 層: come-from（term キー）と felt-sense link（line キー）を別 first-class object に。stable line-id 層（[[grasp-backlog]]）は後者にのみ必要。
- `gather` の rationale 行に §2 のレベルミスマッチ言語化を入れ、「リンクを増やす方向が誤り」を原理で言えるようにする。

## Open Questions

- come-from declare の store 表現: 専用テーブルか、宛先ページの frontmatter `come_from:` か。後者なら Markdown mirror と親和的。
- come-from 昇格候補の閾値（uncommon さ・頻度・一意性）をどう機械化するか。`mentions` の出力に scoring を載せるか。
- render 層の自動リンクは mirror（read-only）だけか、将来の公開 view export まで担うか（§8 の scope 判断と連動）。
- come-from term の多義境界例（uncommon だが多義）でのスコープ指定（文脈・近傍語での絞り込み）。
- felt-sense link（行・著者）と come-from（用語・読者）を同一 store でどう型区別し、`read` 出力でどう見せ分けるか。

## 関連

- [[kj-link-hub-audit-2026-06-24]] — 144→490 の実測。本ページはその「なぜ」と「何を実装するか」
- [[grasp-backlog]] — `gather` / `mentions` / write-identity / markdown-mirror の各節に本ページが要件を足す
- [[ai-consumer-cost-and-trust]] — 第3消費者軸（§8）はこの2軸モデルの外側にいる人間公開読者
- [[markdown-obsidian-indexed-mirror]] — render 層（自動リンク・projection）の置き場
- [[cosense-delite-howm-synthesis]] — 本ページの howm 由来の核（ページ＝投影 / come-from）を、Cosense / デライトと並べた3ツール合成論に一般化したもの
- [[positioning-two-personas]] — persona の外にいる「公開読者」消費者
- 親 llm-wiki: `come-fromリンクは1宣言で全出現を親切にする` / `grasp最適設計はlinkからrecallを剥がす-20260624` / `知識は網ページは投影-20260531`

## Updates
### 2026-06-26: 束ねには2理由（substrate-限界 ＋ 人間労力-限界）。AI 著者化は後者を溶かす

§1 は Cosense が4仕事を `[X]` に束ねる理由を「substrate が他チャネルを持たない」に置いた。2026-06-26 対話で束ねには **2つ目の理由**があったと判明: たとえ substrate が別チャネルを持っても、**人間著者は出現ごとに4チャネルを撃ち分けるコストを払えない**。`[X]` 一個が recall+attention+navigation+読者ケアを限界費用ゼロで兼ねるのは **人間のエルゴノミクス上の affordance** でもあった。束ね = substrate-限界 ∧ 人間労力-限界 の2本撚り。

grasp は両方を外す: substrate-限界は層分離（別 command・別 object）で、人間労力-限界は **著者を AI に付け替える**ことで。AI 著者は declare / 4チャネル撃ち分けを実質ゼロコストで払う。∴「束ねを解くと write friction が戻る」懸念は **人間前提**でのみ成立し grasp では消える —— unbundling は AI 著者では *より*安い。[[cosense-delite-howm-synthesis]] の synthesis 原理は弱まるどころか強まる。

ただし **溶けない例外が1つ**: 4仕事のうち **読者ケアだけは消費者が人間**（substrate を持たない公開人間読者、§8）。著者労力が AI 化で溶けても reader-care の binding constraint は著者労力でも substrate でもなく「**消費者が人間**」なので溶けない。∴ AI 著者化で無料になるのは AI に向く3仕事（recall / attention / navigation）に限り、読者ケアは come-from-at-render（§4 render 層）という別機構を依然要する。§8 の第3消費者軸が他3仕事と非対称な *構造的理由* がこれ。

§6 (c)「書き手が AI 化するほど裸言及が支配的」と同根: AI 著者は束ねる動機（労力）を持たず裸で書く。だが読者ケアが要る uncommon 語（§7 安全域=必要域）では裸のままでは人間読者に届かず、come-from declare / render が橋になる。
