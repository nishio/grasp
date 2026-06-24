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

## 関連

- [[history]] — 1.0.0→1.5.23 の store-compat ledger（本ページ §1・§2 の一次データ）
- [[grasp-backlog]] — 未着手の authoring/write/identity（本ページ §3 の「次の山」の中身）
- [[cosense-delite-howm-synthesis]] — 「層分離で束ねを解く」を製品組成として述べた版。本ページは開発弧として述べる
- [[come-from-declared-gather]] — authoring 側の未実装機構（come-from declare/render）
- [[positioning-two-personas]] — persona1 差別化＝id-link authoring がまだ未着手
- [[grasp-v1-implemented]] — retrieval 側の current facts
