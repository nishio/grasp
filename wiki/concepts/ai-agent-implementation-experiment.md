---
type: concept
summary: grasp を、AI エージェントが durable な wiki context を読み、実装し、判明した制約を wiki に戻すソフトウェア実装実験として説明する初見エンジニア向け orientation。プロダクトは local graph store だが、同時に「AI が自分の実装文脈を持つとソフトウェア開発はどこまで継続できるか」の dogfood でもある。
sources:
  - AGENTS.md
  - wiki/index.md
  - wiki/entities/grasp-v1-implemented.md
  - wiki/concepts/ai-consumer-cost-and-trust.md
  - wiki/concepts/development-arc-retrieval-ahead-of-authoring.md
  - wiki/concepts/value-is-problem-solving-not-novelty.md
  - wiki/decisions/positioning-two-personas.md
  - wiki/entities/parallel-agent-write-incident-2026-06-26.md
  - wiki/sqlite-ssot-write-plan.md
  - wiki/history.md
  - wiki/log.md
id: b1abb0a514e27d4b1b776f06
title: ai-agent-implementation-experiment
---

# AIエージェントによる実装実験としての grasp

このページは、初めてこのリポジトリを見るエンジニア向けの入口。grasp は「Scrapbox/Cosense 型の local graph knowledge store」だが、このリポジトリ自体はそれだけではない。**自走する AI エージェントが、継続的にソフトウェアを実装できるようにするための実験場**でもある。

## 一文

grasp のプロダクト仮説は「LLM に Markdown の束を丸投げするより、本文・逆リンク・2-hop・未解決リンクを materialize した local graph store を CLI で読ませる方がよい」。開発実験としての仮説は「その graph store と wiki を、AI エージェント自身の実装文脈として使わせると、設計判断・実装事実・失敗知見を失わずに開発を継続できる」。

つまり grasp は **AI agent が使う道具**であると同時に、**AI agent によって作られる道具**であり、さらに **その作る過程の知見を grasp-backed wiki に戻す dogfood**になっている。

## 実験の構図

| 層 | 役割 |
|---|---|
| `grasp/` code | 通常の Python CLI プロダクト。SQLite store、parser、retrieval command、alpha write path、tests を持つ |
| `wiki/` | 設計判断・current facts・backlog・gotcha の source of truth。chat の記憶ではなく、次の agent が読む durable context |
| `wiki.grasp/events.jsonl` / `.grasp/` | wiki 書き戻しを grasp の write path で dogfood するための journal / local store |
| AI agent | wiki を読んで実装し、テストし、判明した制約を wiki に file back する実装者 |
| tests / lint / git | AI の自走を bounded にする外部規律。意図と実装のズレを検出する hard gate |

ここでの「自走」は、AI が無制限に勝手な設計をするという意味ではない。実際の loop はかなり狭い:

1. `wiki/index.md` から current facts / backlog / decisions を読む。
2. 小さな実装 slice を選び、既存コードの pattern に沿って変更する。
3. `python3 -m unittest discover -s tests`、`python3 scripts/lint_wiki.py`、`git diff --check` などで検証する。
4. 実装で分かった制約・落とし穴・設計変更を `wiki/` に戻す。
5. 次の AI agent は chat 履歴ではなく wiki から再開する。

この loop が成立するかどうかが、このリポジトリの開発実験の本体。

## なぜ graph store が必要か

AI agent は人間と違い、読める文脈に hard limit がある。大規模 Markdown を全部読むと token budget を壊し、grep は速くても出力が unbounded で、空振りした時に「存在しない」と誤読しやすい。[[ai-consumer-cost-and-trust]] はこれを、round-trip/token cost と negative-result contract の問題として整理している。

grasp の read surface はこの制約に合わせている。`read` は本文だけでなく backlinks / related / unresolved targets を同梱し、`search` や zero-hit には recovery hints を返す。これは便利機能ではなく、AI が「少ない tool call で、断定しすぎずに、次に読む場所を決める」ための実装基盤。

## この実験で見ているもの

- **文脈継続性**: 別 session / 別 agent が、過去の設計判断を wiki から拾って実装を続けられるか。
- **実装と記憶の往復**: 実装で判明した事実が backlog / decision / current facts に戻り、次の実装判断を変えるか。
- **AI 向け retrieval の有効性**: `read` / `search` / `gather` / `history` が、人間向け wiki より AI 実装者に効く形で context を返せるか。
- **規律の維持**: 速い実装でも schema version、store compatibility、unit test、wiki lint を落とさずに進められるか。
- **並行 agent の失敗モード**: 複数 session が同じ branch / journal / projection に触った時の衝突を検出し、運用や storage design に戻せるか。実例は [[parallel-agent-write-incident-2026-06-26]] と [[sqlite-ssot-write-plan]]。

## Updates 2026-06-28: 就寝中の自動実行観察

2026-06-28 の就寝中に、Codex PR 連鎖を自動で走らせる実験をした。設定した goal は「LLM Wikiのインフラとして信頼できるものになる」、実行時間は 17h 47m 45s。観測された `origin/main` の進捗は PR #7 から #36 までで、public compatibility version は `1.8.36` 付近から `1.8.71` まで進んだ。主な成果は新しい大機能ではなく、SQLite SSoT file-back / rollback / projection export / legacy journal / CLI help の reliability hardening だった。

観察:

- **小さい recovery gap が明確なら、AI agent は長時間にわたって micro-slice を積み上げられる**。実装は `revert-plan` の dependency closure、session/preflight/write-start/postwrite guard、dirty projection guard、journal preflight、version ledger lint、CLI help drift fix のように、既存設計を広げるより既知の失敗面を潰す方向へ進んだ。
- **自動実行は branch/projection/session の外枠がないと、後から何が起きたかを人間が復元しにくい**。今回の post-hoc 説明でも、手元 `main` は remote に大きく behind かつ local ahead commit を持っていたため、`origin/main` と wiki log/history を基準に読む必要があった。無人 run の評価では、commit 数よりも「どの base から、どの session id で、どの guard を通して、どの PR に分かれたか」を残すことが重要。
- **夜間自動化の価値は探索より回収に出やすい**。backlog に抽象課題を置くだけだと設計を勝手に広げるリスクがあるが、実履歴 regression や既知 incident から切った guard/recovery task は、無人でも tests と lint が成果を固定しやすい。次に無人実行へ渡す候補は、抽象的な「whole-store を作る」より、実データで再現できる recovery gap / drift / diagnostic の小片が向く。

含意: 「AI が寝ている間に実装する」実験は、企画を丸投げする場ではなく、wiki に十分分解された failure surface を、tests / lint / runbook checker で閉じるバッチ処理として扱うとよい。観察結果も chat ではなく wiki に戻さないと、翌朝の人間や次 agent は local branch の分岐と remote PR 群を再解釈するところから始めることになる。

## 初見エンジニアの読み順

まず `wiki/index.md` を読む。そこから次の順に辿ると、この repo の「今」が見える。

1. [[grasp-v1-implemented]]: 実装済みの CLI surface / data model / parser / delivery。current facts はここ。
2. [[grasp-backlog]]: 未実装項目。次に実装する候補。
3. [[why-not-scrapbox-clone]] と [[positioning-two-personas]]: なぜこの形か、誰のためか。
4. [[development-arc-retrieval-ahead-of-authoring]]: 実装速度、dogfooding、retrieval と authoring の非対称。
5. [[history]] と `wiki/log.md`: いつ何が変わったか。ただし log は current facts ではなく時系列。

コードを触るなら、実装後に wiki も見る。実装済み事実が増えたら `entities/`、未実装が残ったら [[grasp-backlog]]、設計判断を変えたら `decisions/`、横断原理なら `concepts/` に戻す。これが「AI が実装したことを、次の AI が読める context にする」ための最小単位。

## 誤解しないこと

- これは「AI が設計者なしで何でも作れる」という主張ではない。nishio の設計判断、wiki の source of truth、tests、git discipline が強い外枠になっている。
- これは単なるドキュメント駆動開発でもない。wiki は人間向け説明だけでなく、AI agent の retrieval substrate として設計されている。
- これは「論文的に新規な PKM モデル」を主張するページではない。[[value-is-problem-solving-not-novelty]] の通り、価値は novelty ではなく、LLM が大きな知識束を扱う時の token / recall / continuity 問題を解くこと。
- write path はまだ移行中。Markdown projection / JSONL journal / SQLite SSoT の境界は [[sqlite-ssot-write-plan]] の通り整理中で、ここはこの実験の主要なリスク領域。

## 関連

- [[ai-consumer-cost-and-trust]]: AI が読む consumer model。
- [[development-arc-retrieval-ahead-of-authoring]]: この repo の開発弧の自己観察。
- [[use-case-experiment-as-outcome-story]]: dogfood を outcome story として評価する考え方。
- [[parallel-agent-write-incident-2026-06-26]]: 並行 agent が共有 write path に触れた時の実例。
- [[sqlite-ssot-write-plan]]: write authority を SQLite SSoT へ寄せる現行計画。
