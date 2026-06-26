---
type: concept
summary: grasp の設計核（recall を link から剥がす / ページ＝投影 / come-from gather / graph≠triple / 型は bottom-up 昇格）は大半が既存ハイパーテキスト・PKM 研究（Memex / Halasz "Seven Issues" / Nelson transclusion / Trigg typed links / Zettelkasten）の再導出。これは positioning の指針になる: (1) 継承部分は prior art で de-risk 済みゆえ速く作ってよい (2) 唯一未踏なのは消費者を token-bounded AI に替えたコスト関数（近傍同梱＝採餌コスト / absence の hallucination）で、ここだけ prior art が無い (3) ∴ pitch の lede は「論文的に新規」でなく「目前の問題を解く local graph store」。論文系譜は補助線で lede にしない。継承は A 型（ツール経由の再導出、論文は出典でない）
sources:
  - 親 llm-wiki: grasp設計核は既存研究の再導出で価値は問題解決-20260626（cross-wiki 考察 2026-06-26）
  - 設計対話 2026-06-26
---

# 価値は問題解決であって新規性ではない

## 一文

grasp の設計核の大半は80年分のハイパーテキスト/PKM 研究の再導出である。だから grasp の価値は「論文的に新規」であることではなく、**目前の問題（LLM が Markdown の束を引くと token と recall が破綻する）を技術で解くこと**にある。文献系譜は de-risk と未踏特定の道具で、pitch の lede ではない。

## なぜこのページ（positioning に効く）

[[positioning-two-personas]] / README pitch が「novel vs papers」へ滑らないための歯止め。grasp は論文を読んで作られていない（Cosense / デライト / howm への felt friction から。[[cosense-delite-howm-synthesis]]）。系譜は **post-hoc な再認であって出典ではない**＝継承は A 型（ツール経由の無自覚な再導出）であって B 型（一次出典の引用）ではない。

## 設計核 ↔ 既存研究（de-risk マップ）

| grasp の設計核 | 対応する研究 |
|---|---|
| 自動双方向リンク・2-hop・連想 traversal | Bush **Memex / 連想トレイル**(1945)、Engelbart NLS |
| **recall を link から剥がす**（mention 検索 L1 を navigation link と分離） | **Halasz "Seven Issues"(1988) 争点①: search & query** が navigation に対し二級だった反省 |
| **ページ＝query 時 live projection**（L3） | Halasz **virtual / computed structures**（同論文） |
| come-from（用語1宣言→全出現 gather）| **Nelson トランスクルージョン** を *read 時計算で実装*＝Scrapbox が拒んだ copy ベース transclusion の難点（範囲指定 / 多重重複）を回避 |
| 型は事前付与せず co-link traffic で **bottom-up 昇格** | **Trigg TEXTNET(1983) の75型＝重すぎ失敗** の回避 |
| **graph化 ≠ triple 還元**（全文保持・リンク構造だけ materialize） | Wu et al. *Memory in the LLM Era*(PVLDB 2026) の L2 情報完全性 / Mem0 > Mem0g / GraphRAG-Bench |

含意: これらは **40年以上の prior art で de-risk 済み**。[[development-arc-retrieval-ahead-of-authoring]] の「速く一貫して作れる」は単一原理（層を分けて束ねを解く）の再適用であると同時に、**既知解の再利用**でもある。安心して速く実装してよい領域。

- recall 剥がしの詳細: `grasp最適設計はlinkからrecallを剥がす`（親 llm-wiki）/ [[come-from-declared-gather]]
- graph≠triple の詳細: `MarkdownのLLM Wikiは手回しのScrapbox`（親 llm-wiki、L2 情報完全性を満たす理由）

## 唯一の未踏 = 消費者を token-bounded AI に替えたコスト関数

prior art は全員「画面を持つ人間ナビゲータ」を消費者と想定（クリック/ホバー、認知負荷と画面面積が制約）。grasp は**同じデータモデルのまま消費者を AI(CLI) に取り替えた**（[[scrapbubble]] = read 模型を consumer-swap した双子）。替えると2点で prior art が無い:

1. **採餌コスト → token 経済。** read=近傍同梱（[[ai-consumer-cost-and-trust]] 軸1）は情報採餌理論（Pirolli & Card 1999）の patch 間移動コスト最小化を、人間の注意でなく **token / round-trip** に置換したもの。近傍同梱＝「採餌者にパッチを持ってくる」。[[read-vs-grep-benchmark-2026-06-24]] が「効くのは速度でなく context token 量」と実測したのは採餌コストの単位が変わった証拠。
2. **absence の hallucination**（[[ai-consumer-cost-and-trust]] 軸2）。人間は「まだ検索していない」を知るが、LLM は空の検索結果を「存在しない」と読んで完全性を hallucinate する。recall を vector より先に最優先する理由。**人間ハイパーテキストに対応物の無い失敗モード**。

ここは prior art が無い＝**自前で慎重に設計すべき frontier**。誇るべき novelty ではなく、注意すべき領域として扱う。

## ∴ pitch ルール

- lede = **「目前の問題を解く local graph store」**。✕「研究的に新規」。
- 論文系譜は説明の補助線に使ってよいが、「grasp = 論文を読んで作った新規モデル」と誤読させない（継承は A 型＝再導出）。
- 価値の証明は use-case outcome（[[use-case-experiment-as-outcome-story]]）で出す。論文への位置づけでは出さない。

## Open Questions

- Halasz "Seven Issues" の7項目と grasp の L0–L3 の正確な対応は一次裏取り未（争点① search & query と virtual structures の2点のみ接地）。pitch に使う前に一次裏取り推奨。
