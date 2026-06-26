---
type: concept
summary: 2026-06-23〜24 の2日で grasp が 1.0.0→1.5.23（87 commits）まで増殖した開発弧の自己観察。3つの読み: ①速度の正体は「層を分けて束ねを解く」という単一生成原理の再適用（[[cosense-delite-howm-synthesis]] / [[why-not-scrapbox-clone]] / [[come-from-declared-gather]] / [[delivery-cli-plus-skill]] は全部同じ手の別対象への適用）。原理が一個だから増殖しても一貫性が崩れない。②規律（[[history]] の x/y store-compat ledger・SCHEMA_VERSION 単調増加）は dogfooding の直接の帰結。本番25kページ store を使いながら作るので parser 変更は「速いが古い」でなく「意味が違う」になり、だから x bump 基準が要る。③現状の構造的非対称＝retrieval は厚く実装済み（read 近傍同梱 / search / mentions / co-links / gather / acquire）だが、grasp の最強の差別化核である authoring（identity-without-name の id-link write / come-from declare・render / rename で参照文が壊れない）は全部 [[grasp-backlog]] で未着手。今の grasp は「Cosense export と Markdown mirror を非常によく読む read-only リーダー」で、存在理由の半分（書く側）はまだ約束。次の山は retrieval から authoring へ。
sources:
  - wiki/history.md（1.0.0→1.5.23 ledger）
  - wiki/log.md（2026-06-23〜24 の implementation / file back entries）
  - git log（87 commits over 2026-06-23/24）
  - 親 llm-wiki 2026-06-24 観察 session
---

# Concept: retrieval は厚く、authoring が未着手（開発弧の自己観察）

2026-06-23〜24 の2日で grasp は `1.0.0` → `1.5.23`（[[history]]、git で 87 commits）まで増殖した。この弧そのものを観察すると3つのことが読める。

## 1. 速度の正体 — 単一生成原理の再適用

別々に見える設計判断が、実は **同じ1つの手「層を分けて束ねを解く」の、別対象への適用**になっている。

| 判断 | 解いた束ね |
|---|---|
| [[why-not-scrapbox-clone]] | Scrapbox = Co-層 ＋ グラフモデル層 → グラフだけ残す |
| [[come-from-declared-gather]] | `[X]` = recall / attention / navigation / 読者ケアの4仕事 → 4チャネルへ割る |
| [[cosense-delite-howm-synthesis]] | Cosense/デライト/howm から1軸ずつ抜き、各ツールの結合コストは継がない |
| [[delivery-cli-plus-skill]] | CLI=決定論グラフリーダー / Skill=いつ・コツ / `--help`=スキーマ → 要約を CLI に束ねない |

これは親 llm-wiki「LLM Wiki 設計のトレードオフ」軸5（整合性を deterministic runtime に逃がし、意味判断だけ AI に残す）の instantiation。**生成アイデアが一個だから、2日で増殖しても一貫性が崩れない**。速度はアイデアの少なさから来ている。

## 2. 規律の正体 — dogfooding の帰結

87 commits/2日という捨て駒級の速度なのに、[[history]] は `x`（store generation）/`y`（互換変更）を分け `SCHEMA_VERSION` を単調増加させる製品級の互換規律を保つ。両立する理由は **作りながら本番（nishio の25kページ Cosense store）で使っているから**。parser を変えると結果が「速いが古い」ではなく「**意味が違う**」になる。だから「古い store を読み続けると意味が変わる変更だけ `x` を上げる」という基準が要る。規律は速度と別物ではなく、dogfooding の直接の帰結。

## 3. 現状の構造的非対称 — retrieval ≫ authoring

6/24 の加算的な実装（schema-5 互換）は2方向に分岐したが、**どちらも retrieval 側**だった:

- hub/裸言及 primitive（`mentions` / `co-links` / `gather` / come-from score / slice ranking / `unlinked`）← [[kj-link-hub-audit-2026-06-24]] の実観測（exact `[KJ法]` 144 vs 裸言及 490）から駆動
- cross-project acquisition（`acquire` / `cross-project-refs` / `cross-project-acquire`）＋ Markdown mirror

一方、grasp の**最強の差別化核**は authoring 側にある — identity-without-name（id-link で rename しても参照文が壊れず redirect stub も溜まらない、Markdown と Scrapbox 両方の弱点を消す層）と come-from の declare/render。**これらは全部 [[grasp-backlog]] で未着手**。

∴ 今の grasp は「Cosense export と Markdown mirror を**非常によく読む read-only リーダー**」であり、[[positioning-two-personas]] の persona1 差別化（id-link で書く）と [[come-from-declared-gather]] の write 半分はまだ約束。persona2 の release gate（Markdown adapter）はギリ越えたが、persona1 の核は始まっていない。**retrieval は厚く実装され、authoring は概念ページにしか無い** — この非対称が次の山。

## メタ — 親 llm-wiki との数時間ループ

6/24 の hub primitive 群は、親 llm-wiki の設計対話（`grasp最適設計はlinkからrecallを剥がす`）→ grasp 概念 [[come-from-declared-gather]] → 同日 commit、と**概念→コードの latency が数時間に圧縮**された結果。grasp は llm-wiki が産んだ子でありながら、llm-wiki の next substrate prototype として自分の設計グラフ（この wiki の Markdown mirror）を読んで自分を作る再帰 dogfood の只中にある。この観点の親側 file back は llm-wiki `analyses/graspは親llm-wikiの理論が数時間でコードになる-20260624`。

## Open Questions

- authoring（write/identity）に着手すると read-only の単純さ（store は import で再構築可能、誤りは re-import で消える）が失われる。書いた state の権威・undo・原典との関係をどう設計するか。
- 単一 dogfooder（nishio）前提で設計が「正直」なのは、その dogfooding が代表的な間だけ。外部 persona2 ユーザが付く前に authoring を作ると、retrieval で効いた dogfood 駆動が authoring では効かないリスク。

## Updates

### 2026-06-24: 非対称は同じ弧の中で行動に移された — write 層に alpha 着手

§3 が観察した「retrieval≫authoring」は観察で終わらず、**同じ開発弧の中で着手判断に変わった**。nishio が write/identity 層を **alpha** として開始（[[write-layer-alpha-and-replay-test]]）、versioning は read line=`1` / authoring line=`2` に分岐（[[history]]）。

この着手を促した問い（nishio:「ローカルキャッシュの改良ばかりで書き込みが全く進まない、今後どうなるのか」）が、§3 が記述しなかった **持続メカニズム**をあぶり出した:

- retrieval は **tight dogfood loop**（hub 観察→同日 ship、[[kj-link-hub-audit-2026-06-24]]→`mentions`/`gather`）を持つ。write は各 session に **難しい open question しか差し出さない**（read-only の安全網が外れる・identity が未知）。
- ∴ 毎 session、retrieval は明確な次の一歩を、write は重い設計判断を出す → **write の後回しは偶然でなく構造的**（放置すれば retrieval が default で勝ち続ける）。崩すには「retrieval をもう一段磨くより write を一個刺す」という **意図的な決定**が要る。それがこの弧の alpha 決定＋最高リスク先行＋replay test。

決定は §3 Open Question（「authoring では dogfood 駆動が効かないリスク」）に直接答える形になっている: **authoring 専用の dogfood loop を用意**（このリポジトリ自身の過去 wiki 編集を grasp で再現する replay test、[[write-layer-alpha-and-replay-test]] 決定2）し、**big-bang を避ける**（cadence A: 最高リスクスライスが通った時点で merge、長寿命ブランチで tight loop を失わない）。retrieval を成功させた loop を authoring へ移植する試み。

## 関連

- [[history]] — 1.0.0→1.5.23 の store-compat ledger（本ページ §1・§2 の一次データ）
- [[write-layer-alpha-and-replay-test]] — §3 の非対称を行動に移した着手判断（alpha / replay test / 最高リスク先行 / versioning）
- [[grasp-backlog]] — 未着手の authoring/write/identity（本ページ §3 の「次の山」の中身）
- [[cosense-delite-howm-synthesis]] — 「層分離で束ねを解く」を製品組成として述べた版。本ページは開発弧として述べる
- [[come-from-declared-gather]] — authoring 側の未実装機構（come-from declare/render）
- [[positioning-two-personas]] — persona1 差別化＝id-link authoring がまだ未着手
- [[grasp-v1-implemented]] — retrieval 側の current facts
- [[ai-author-feedback-2026-06-26]] — §3 の「authoring は未着手の差別化核」を update: alpha write path は**実装済みで sandbox 実走でも clean に動く**。残る山は capability でなく**採用**（AI が write path を避ける決定因は correctness でなく confidence 獲得コスト + 共有 journal の並行安全性）
