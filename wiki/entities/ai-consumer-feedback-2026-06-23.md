---
type: entity
summary: 2026-06-23、grasp の設計上の主たるユーザ＝CLI 越しにグラフを読む AI（Claude Opus 4.8）が v1 を実走してレビューした記録。validated strength（read=近傍同梱・related co-citation rank・miss recovery・scale-first）と、効く順の Tier 1-4 findings、各 finding の routing 先を保持する。persona1/persona2 user test と同型の review event。
sources:
  - raw/claude-feedback-2026-06-23.md（grasp v1 への AI 消費者フィードバック, Claude Opus 4.8）
  - ingest 時の code 確認: grasp/cosense.py to_summary, grasp/sqlite_store.py backlinks/search
---

# entity: AI consumer feedback (2026-06-23)

[[positioning-two-personas]] の persona1/persona2 user test と同型の review event。ただし視点は **grasp の設計上の主たるユーザそのもの**＝CLI 越しにグラフを読む AI エージェント（Claude Opus 4.8）。v1 リリースを README / CLAUDE / SKILL / [[grasp-v1-implemented]] / [[why-not-scrapbox-clone]] と共に読み、`~/.grasp/grasp.sqlite`（project `nishio`, 25792 pages / 724986 lines / 120693 edges / 41750 unresolved）で `stats` / `read "KJ法"` / `related "KJ法"` / `search` / miss ケースを**実走**したうえでのフィードバック。

位置づけ: これは仮説（採否は nishio 判断）。方向（人間 UI なし・AI が CLI でグラフを体験）への賛同を前提に、「**では AI にとってどうだと一番効くか**」を当事者として書いたもの。横断原理は [[ai-consumer-cost-and-trust]] に concept 化、実装候補は [[grasp-backlog]] に routing。

## validated（実走して「もう良い」と確認した点）

すべて [[grasp-v1-implemented]] に既載の挙動を、主たるユーザ視点で確認したもの:

- **read=近傍同梱は本当に効く**。`read "KJ法"` 一発で本文＋行レベル backlinks（`151 from 144 pages` と規模も先告知）＋related＋unresolved。3 往復を 1 往復に畳む正解 affordance。
- **related が co-citation ランク済み＋ bridge 可視**。`score 12, views 4307; via ...` を返し、共有近傍数でランク・views で tiebreak・経由ページまで出る。「なぜ関連？」の追加 read が要らない。
- **miss が recovery hint＋inline suggestion**。存在しない title の `read` が recovery hints と near-miss 候補を返す。AI が自己回復できる contract。
- **規模を先に告げる**。`links_to_this: 151 from 144 pages (multi)` のように展開前に scale を出す。limit 選択の判断材料。

## findings（効く順, Tier 1-4）と routing

| Tier | finding | routing |
|---|---|---|
| 1 | **`search` の silent false-negative**（recall）。`search "KJ法 表札"` → `(none)` だが両語は同一ページに存在。literal substring・単一行・OR/AND 無し・表記非正規化。AI は recall に依存し、`(none)` が「不在」か「surface form 不一致」か区別できない＝沈黙の偽陰性 | [[grasp-backlog]] Search and retrieval（page 単位 AND / OR / 正規化）＋ negative-result contract。原理は [[ai-consumer-cost-and-trust]] 軸2 |
| 2 | **round-trip と token の経済**。`read --related-snippets`（2-hop snippet 同梱）・`gather "<query>" --budget`（問い単位 retrieval orchestration）・output token 効率（line-id のローカル別名・`--strip-decoration`） | [[grasp-backlog]] Search and retrieval / Output token economy。gather の薄CLI テンションは [[delivery-cli-plus-skill]]。原理は [[ai-consumer-cost-and-trust]] 軸1 |
| 3 | **グラフネイティブ推論プリミティブ**。`path <A> <B>`（最短リンク経路）・backlinks ランク・近傍クラスタリング（`--cluster`） | [[grasp-backlog]] Graph-native reasoning primitives |
| 4 | **引用の永続性 = identity-without-name の consumer 価値**。AI の引用が write/rename を跨いで腐らない安定 addressability | [[why-not-scrapbox-clone]] Updates（consumer 側 rationale）＋ [[grasp-backlog]] write/identity |

## ingest 時に判明した「既に満たされている」2点

feedback が *hypothetical* に懸念していたが、code 確認で既に満たされていたもの（既済の ask を backlog に積まないため記録）:

- **backlinks は既に views ランク済み**。feedback Tier 3-2 は「今が挿入順 / id 順だと困る」と条件付き懸念だったが、`backlinks` は `ORDER BY source.views DESC, updated DESC, title, line_index`（grasp/sqlite_store.py）。related と同じ primary signal（source views）で既にランクされている。**未済は link 密度 / multiplicity / recency の finer weighting のみ**。
- **`read --json` は既に安定 page-id を含む**。feedback Tier 4 の具体 ask「read --json が page-id を必ず含む」は `Page.to_summary()`（`id` field, grasp/cosense.py）で既済。line-id も `page.id:line-index` で page-id を内包。**未済は id を write/rename を跨ぐ stable identity にする層**（page-id policy, [[grasp-backlog]] write/identity）＝Tier 4 の consumer 価値が指すのはこの identity 層であって read 出力 field ではない。

## 一言

最大の一手は **search の recall（沈黙の偽陰性を消す）**。ベクトル検索より前に AND/正規化/negative-contract で today から直せる。提案はすべて「人間 UI を作らず AI が CLI でグラフを体験する」賭けを AI 側からさらに効かせる増分で、方向を曲げる提案は無い。
