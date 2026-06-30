---
type: todo
summary: v1 リリース後にまだ実装していない作業だけを保持する backlog。実装が済んだ項目は grasp-v1-implemented（current facts の SSoT）へ移し、却下した案は各節末の「却下（再提案しない）」1行ガードに畳む。
sources:
  - wiki/entities/grasp-v1-implemented.md（実装済み事実の SSoT）
  - wiki/entities/ai-consumer-feedback-2026-06-23.md（Tier 1-4 由来）
  - wiki/decisions/whole-store-graph-and-cross-project-edges.md
  - wiki/decisions/write-layer-alpha-and-replay-test.md
  - wiki/decisions/markdown-obsidian-indexed-mirror.md
---

# grasp backlog

このページは **まだ実装していない作業**だけを保持する。実装が済んだ事実は [[grasp-v1-implemented]]（current facts の SSoT）へ移すのでここからは消す（*いつ* 実装したかの時系列は [log](log.md)）。却下した案は経緯を展開せず、各節末の **却下（再提案しない）** に理由つき1行で残す（再提案を防ぐガード）。設計判断の根拠は `decisions/` / `concepts/` にあり、本ページはそこへリンクするだけにする。

> 整理 2026-06-25: 旧 backlog は実装済みの作業ログと却下の経緯を本文に抱えて 412 行に膨らんでいた。実装済み narration を [[grasp-v1-implemented]] と [log](log.md) に寄せ、却下を1行ガードに畳み、未実装項目だけを残した。

## Parser fidelity

- **parser false-negative 監査**: strict parser は unresolved target noise を減らすため保守的。短い英数字 title などを link から落としていないか未監査。
- **外部 export の堅牢性は恒常コスト**: nishio の admin metadata-ON export は in-the-wild の代表ではない（string line・page metadata 欠落・export version 差）。非 nishio export ごとに parser 前提が崩れうる＝実質 fuzz test。方針は tolerant import ＋実 export variant の test fixture 化で、一回の修正では閉じない。これは persona2（[[positioning-two-personas]]）を狙う代償。最初の fixture は takker の villagepump string-line ケース（[[takker-opencode-villagepump-test-2026-06-24]]、PR #2 で対応済み）。

### link-shaped but non-semantic edge annotation

`#1` / `#2` が hashtag link になることは、`log.md` artifact handling とは別問題。Scrapbox 互換では `#1` は link-shaped expression であり、人間側も必要なら `` `#1` `` のように escape してきた。grasp は parser で勝手に捨てるより、edge を保持した上で「表現としてはリンクだが、意味のある概念リンクではない」と annotation できる層を持つべき。初期 system heuristic として、`PR #2` / `Open Question #4` のような issue-number edge に output annotation を付け、`unresolved` で sampled examples がすべて non-semantic な target を後ろへ回す処理は実装済み（[[grasp-v1-implemented]]）。

未実装:

- edge annotation schema（候補: `semantic_role`, `graph_scope`, `confidence`, `annotator=system|llm|human`, `reason`）。`link_kind` / typed link / `connection_strength` とは直交する軸。
- system heuristic annotation の拡張: `../[[..]]` placeholder、version/changelog の ordinal reference、issue number 以外の link-shaped non-semantic 表現を分類する。raw edge は消さない。
- LLM annotation workflow: grasp 自身は候補 edge + source line +近傍を出し、LLM が「意味リンクではない」判断を返して store に annotation する。判断は reversible / provenance 付きにする。
- retrieval policy の拡張: `related` / `path` / backlink ranking でも既定で non-semantic edge を弱く扱い、必要なら `--include-non-semantic` で見る。

## CLI and agent UX

`read --around-line` / `search --context` / `peek --line-offset` の bounded navigation primitive は実装済み。残るのは Skill/subagent 運用で不足が見えた時に bounded primitive を足すこと。**LLM 要約は CLI でなく agent 層の責務**（CLI に summarizer を持たせない、[[delivery-cli-plus-skill]]）。

### AI persona emulation / feedback queue

目的: 複数 persona を AI agent が実際に `grasp` CLI で使い、体験を [[use-case-experiment-as-outcome-story]] の形式で file back する。[[positioning-two-personas]] の persona は corpus owner / GTM の軸なので、この queue では **corpus owner persona** と **AI consumer constraint** を分けて書く。

共通 protocol:

- 各 run は開始前に `persona id` / corpus owner / AI consumer constraint / corpus / user task / success criteria を短く宣言する。想像した persona plan は finding ではなく仮説として扱う。
- AI はできるだけ `grasp` CLI の出力だけで次 action を選び、command trace と「どの出力が次の判断を可能にしたか」を残す。raw dump が最終成果なら outcome story としては未完了。
- file back は entity page（例: `persona-...-user-test-YYYY-MM-DD` または `ai-...-feedback-YYYY-MM-DD`）に、依頼・対象 corpus・実行 surface・結果・coverage/caveat・friction を分けて残す。実装 gap は本 backlog の該当節へ、current fact は [[grasp-v1-implemented]] へ、設計判断は `decisions/` へ routing する。
- 各 run は「いい感じか」を明示判定する。CLI が返した bounded artifact が、読む・判断する・次に使う単位になっているかを見る。

タスク queue:

- **P1: JP Cosense heavy dogfood refresh**。corpus owner = persona1（日本語 Cosense heavy user）。AI consumer = 通常 Codex/Claude。実タスク: nishio store / hosted Cosense から最近の設計問いを1つ調べ、`search` / `read` / `backlinks` / `related` / `path` / `gather` の自然な loop で答える。見るもの: 高密度 graph の強み、表記ゆれ、巨大 hub、bounded output だけで判断できるか。
- **P2a: dense Markdown wiki owner**。corpus owner = persona2a（dense `[[wikilink]]` を持つ Markdown / Obsidian power user、bridge として llm-wiki 森）。AI consumer = 通常 agent。実タスク: `import-forest` または persona2a demo vault を使い、複数 wiki / note を跨ぐ概念探索を完走する。見るもの: Markdown on-ramp、whole-store weak cross-project retrieval、navigation/log artifact handling、demo として人に見せられる concrete value。
- **P2b: sparse Markdown cold skeptic**。corpus owner = persona2b（cold HN/Reddit 的な低リンク密度 .md folder ユーザ）。AI consumer = fresh agent。実タスク: 空 `GRASP_HOME` と小さな sparse notes で始め、`grep` / `cat` / `grasp import --markdown` / `search` / `read` を比較して「何が残る価値か」を判定する。見るもの: density 非依存の bounded retrieval pitch、friendly onboarding、"why not Obsidian/RAG/grep" への実証。
- **P3: AI author / file-back agent**。corpus owner = grasp wiki maintainer。AI consumer = wiki に知見を残す coding agent。実タスク: `activity` / `claim-page` / preflight / `write-page` / `append-log` / postwrite / `revert-plan --scope session` を使って小さな file-back を完走する。見るもの: confidence 獲得コスト、guard message、dirty/stale recovery、direct patch へ逃げたくなる理由が減るか。
- **P4: constrained low-cost model consumer**。corpus owner は P1 or P2a から選ぶ。AI consumer = 小 context・低能力・domain knowledge 薄めの agent。実タスク: custom script なし、`skills/grasp` と `grasp <cmd> --help` だけで同じ retrieval question を解く。見るもの: command discoverability、text/JSON contract、zero-hit recovery、[[takker-opencode-villagepump-test-2026-06-24]] で見えた cross-model portability の再現性。
- **P5: public hosted Cosense partial-acquire researcher**。corpus owner = public project outsider（admin export なし）。AI consumer = 調査 agent。実タスク: public backup release / `acquire` / `cross-project-refs` / `cross-project-acquire` で特定 topic の bounded candidate bundle を作り、agent-authored report へ渡す。見るもの: permission / env diagnostics、partial corpus caveat、report handoff contract、raw dump で終わらないか、`cosense-cli` と grasp が両方ある時に agent が正しく grasp を選ぶか（[[grasp-organic-mentions-2026-06-29]]）。

success shape:

- persona ごとの「感想」ではなく、**grasp の強い用途・弱い導線・次に直すべき面**が実走証跡から決まる状態にする。
- 良かった run は README / docs / demo へ昇格できる concrete outcome story にする。特に P2a は「Markdown 束より grasp が効く」を見せる外向け demo 候補。
- 悪かった run は「persona が不満だった」で止めず、onboarding / zero-hit recovery / raw-dump output / write confidence / report handoff など、CLI・Skill・docs・backlog・decision の修正先へ routing する。
- persona run は将来の回帰基準にする。CLI や docs を変えた時、P2b sparse Markdown の初回体験や P3 file-back agent の write confidence が悪化していないかを確認できる状態がよい。
- 全 persona に同じ売り文句を当てない。P1/P2a は graph density、P2b は bounded retrieval、P3 は write confidence、P4 は low-cost portability、P5 は acquisition/report handoff という別価値として position する。

done criteria:

- 少なくとも各 persona 1 run ずつ、entity page または既存 feedback page に command trace と outcome judgement が残る。
- finding は「persona の感想」に留めず、CLI surface / Skill recipe / docs / backlog / decision のどれへ効くかを routing する。
- 良い outcome story になった run は README / docs / demo から参照できる候補にする。

## Markdown / Obsidian indexed mirror

最小 read-only mirror（`import --markdown <folder>`、frontmatter title/id/aliases/tags、first H1 title resolution、content-only 差分 index、`--markdown-exclude-dir` による heavy raw/generated directory 除外）は実装済み。決定は [[markdown-obsidian-indexed-mirror]]。未実装:

- surface 命名: `index-md` / `import-md` / `import --format markdown <folder>` を足すか（現状は `import --markdown <folder>`）。
- **progressive / lazy import**: 2026-06-30 に `refresh_edge_resolutions` の急性性能病は修正し、同日 follow-up で no-op re-import と content-only changed-file re-import の manifest-first fast path も実装した。既存 manifest の source type / exclude dirs / file set / content hash が完全一致する時は `MarkdownMirror.from_folder()` を呼ばず、hash が変わった file も page id / title / aliases / graph_role が保存 manifest と一致する場合は changed file だけを parse する。3000p/54000 edges synthetic は no-op 0.82-1.23s、1-file 1.49s。さらに `import --markdown --catalog-only`、`read --hydrate`、`hydrate-markdown --limit N` / `--until-complete --max-seconds S`、global `--idle-hydrate-seconds S --idle-hydrate-limit N`、env policy `GRASP_IDLE_HYDRATE_SECONDS` / `GRASP_IDLE_HYDRATE_LIMIT`、`gather --hydrate-limit`、basic retrieval `search` / `backlinks` / `related --hydrate-limit`、graph verbs `mentions` / `co-links` / `path` / `unresolved --hydrate-limit` を実装済み。catalog-only は Markdown 本文を読まず path-derived page catalog だけを作り、`parsed_files=0` / lines=0 / edges=0 / `markdown_graph.complete=false` として `stats` / `read` に incomplete warning を出す。`read --hydrate` は選択 page 1件だけを source file から parse し、title/aliases/lines/edges/manifest hash と `markdown_graph.hydrated_files` を更新してから読む。`hydrate-markdown --limit N` は未 hydration source files を source path 順に最大 N 件だけ parse し、`--until-complete --max-seconds S` は graph complete / no progress / time budget exhausted まで bounded loop する。global idle hydration は supported read/retrieval command の結果計算後に最大 N file だけ hydrate し、JSON `markdown_idle_hydration` / text footer で「結果本体は hydration 前、次回以降に効く」と報告する。env policy は毎回 flag を渡さなくても bounded background hydration を有効化し、CLI `--idle-hydrate-seconds 0` で明示的に止められる。`gather` / `search` / `backlinks` / `related` / `mentions` / `co-links` / `path --hydrate-limit N` は未 hydration source files を query/target/endpoint 文字列・link target・catalog handle で軽く scan し、ヒットした source page を最大 N 件だけ parse してから retrieval を計算する。`unresolved --hydrate-limit N` は source-path 順 chunk を先に hydrate して ranking を更新する。3000p/54000 edges synthetic は catalog-only 0.19-0.27s、first page hydrate 0.038s、次10ページ hydrate 平均 0.041s/page、full hydrate import 12.44s。basic retrieval の hydrate なし empty-result contract は `markdown_query_contract` として実装済みで、`search` / `backlinks` / `related` に加えて `mentions` / `co-links` / `path` / `unresolved` も incomplete graph 上の空結果や partial ranking/path absence を complete-corpus absence として返さない。`markdown_query_contract.partial_fields` / `result_field_states` は hydrated subset 由来の派生 field を明示し、`gather` と `read` / `read --around-line` も partial field contract を返す。同 contract は 2026-06-30 Codex follow-up で `result_may_be_incomplete` と `hydration_progress` を持ち、非空 result でも partial であること、command-local hydration が `limit_reached` / `scan_exhausted` のどちらで止まったかを machine-readable にする。`export-markdown` も 2026-06-30 Codex follow-up で `markdown_projection_contract` を持ち、catalog-only / partial graph の non-check export は unhydrated source file を空 projection で上書きしうるため既定で拒否する。`link-stats` / `peek` / `suggest` / `ambiguities` / `cross-project-spread` / `cross-project-spreads` も incomplete graph 上で `markdown_query_contract` と text warning を返すため、catalog-only の 0 incoming / empty lines / empty suggestions / ambiguity or spread counts を complete-corpus fact と誤読しない。2026-06-30 Codex follow-up で all-project mixed scope も aggregate `markdown_graph.mode=all-projects` と `incomplete_projects[]` を返すため、複数 project のうち一部だけ incomplete な store でも aggregate counts を complete と見せない。export/backup policy は 2026-06-30 Codex follow-up で、incomplete graph export が既存 Markdown を上書きする時に `--backup-dir` を必須にし、backup copy を残してから write する形で実装済み。残る本体は real dogfood で必要になった時の finer per-verb completeness refinement。成功条件は初回 usable latency を小さくし、後続 command が incomplete graph を誤って complete と表示せず、使ううちに必要な graph が増えること。
- Obsidian block refs / heading anchors の細部: schema `10` で `target_fragment` / `target_line_id`、schema `11` で GitHub-style heading slug / duplicate suffix match、schema `12` で Markdown write-alpha 由来 edge の fragment 保持は実装済み。`[[Page#Heading]]` / `[[Page#^block-id]]` と相対 Markdown link `[label](Page.md#Heading)` / `[label](Page.md#^block-id)` は target page への edge になり、unique target page 内で target line が見つかれば `target_line_id` も保持する。resolved local-only anchor `[label](#heading)` / `[[#Heading]]` は self-page line edge になる。残件は必要が具体化した時の Obsidian 固有 edge case。
- ambiguous handle retrieval UX。方針は [[markdown-identity-name-collision-policy]]。structured diagnostics / `source` role / `artifact` role / schema v6 `page_handles` / `read` の `handle_ambiguity` / `read --page-id` / `read --path` / schema v7 `edges.resolution_status` / Markdown duplicate title・alias import softening / `backlinks <ambiguous handle>` の handle backlinks + candidate backlinks contract / `related <ambiguous handle>` の handle source pages + candidate related contract / `ambiguities` report / `import-forest` orchestration は実装済み。`source/` は raw を読んで作った source-backed digest なので default exclude しない。
- alias / title / id / file set 変更時の細かい差分 index（現状は安全側で full rebuild）。

### dogfood corpus を wiki森全体へ広げる

grasp 自身の wiki を mirror の最初の dogfood corpus にするのは実装済み（seed: `import --markdown wiki --project grasp-wiki`）。次は corpus を grasp 1 wiki → **親 llm-wiki の wiki森全体（home 配下 40+ の単一所有者 wiki、registry は `wikis.yaml`）**へ拡張する。動機の全文は [log](log.md) 2026-06-25 と [[scrapbubble]] / [[whole-store-graph-and-cross-project-edges]]。要点:

- 森の現状の横断手段は親 llm-wiki `wiki_search.py` の grep 止まり＝節点アクセス。「N wiki を跨いで参照されるが本文がどこにも無い概念」＝俯瞰グラフ層は出せない。grasp の whole-store cross-project ＋ Markdown mirror がこれを供給できる。
- 森は全部 nishio 所有＝マクロな非 Co- 実例なので、多人数協調を削ぐ grasp の cross-project がちょうど嵌まる。
- **森用の特別 edge policy は要らない**: cross-wiki 参照は import 時に裸の referenced-only 赤 node のまま入れ、whole-store の弱い接続（normalize-title の cross-project 一致）が query 時に繋ぐ（下記 cross-project strength 層）。

- `import-forest <wikis.yaml>` orchestration は実装済み。2026-06-25 の command smoke では 42/42 entries を 1 store の 42 project namespace に import し、entry diagnostics / aggregate / `ambiguities` summary まで返せた。未実装:

- 森規模での navigation/log artifact handling の追加 dogfood（path/frontmatter heuristic と outgoing edge 除外の最小実装は [[grasp-v1-implemented]]）。
- weak 接続の **cross-wiki spread ranking** は `cross-project-spread <title>` と seed title なしの `cross-project-spreads` として実装済み。次は spread ranking の継続 dogfood と、whole-store retrieval / first-class cross-project edge への接続。

### LLM Wiki index / navigation artifact handling

`index.md` 等は通常の content page でなく navigation / generated projection として扱う（[[markdown-obsidian-indexed-mirror]]）。path/frontmatter heuristic による navigation classification と outgoing edge の既定 content graph 除外は実装済み（search 対象には残る）。`export-markdown --regenerate-index` は primary navigation `index.md` を store catalog から再生成する（`1.7.21`）。未実装:

- `--include-navigation` の escape hatch。
- index catalog の folder grouping / source-of-truth ordering / starred pages / section templates など、既存 grasp wiki index と同等の編集意図を表す projection policy。
- `wikis.yaml` / `forest-index.md` は content graph に入れず、複数 project を指す外側 registry として扱う。

### LLM Wiki log / event stream handling

`log.md` は content page でなく append-only event stream / provenance として扱う（[[markdown-obsidian-indexed-mirror]]）。path/frontmatter heuristic による log artifact classification と outgoing edge の既定 content graph 除外は実装済み（search 対象には残る）。`export-markdown --regenerate-log --journal <events.jsonl>` は primary log page を journal の log page events から再生成する（`1.7.21`）。`log.md` を `## [YYYY-MM-DD HH:MM] op | summary` header ごとに `log_entry_import` journal record へ split する importer と、stable `record_id = sha1(source_path + timestamp + op + summary + body_text)[:24]` は実装済み（`1.7.25`）。`read <page>`＝current projection、`log-records` / `history <query>`＝event stream という最小 surface 分離も実装済み（`1.7.26`）。`1.7.27` で `subjects[]` の最小推定（body の `[[wikilink]]` / Markdown path）と subject-aware `history`、same-subject `later_events[]` 同梱も実装済み。`1.7.28` で `type: log-entry` record-per-file importer と frontmatter `subjects` / `pages` 優先も実装済み。`1.7.29` で record-per-file は page identity 由来 `record_id` + `content_fingerprint` にし、frontmatter / body 変更を same-record new version として append、既定 query では superseded version を隠す update policy も実装済み。`1.7.30` で `--regenerate-log` が latest record-per-file records を primary log page へ追記 projection するようになった。`1.8.6` で `import-log-records` は new / updated `log_entry_import` を SQLite events にも書き、`log-records` / `history` は SQLite `log_entry_import` rows を優先し、未移行 record は JSONL fallback で読む。`1.8.7` で `adopt-markdown` initial `log_entry_import` も SQLite events に入る。`1.8.19` で `export-markdown --regenerate-log` は既定で SQLite events を使い、`--journal` は legacy/ad hoc audit input になった。`1.8.20` で repo-local postwrite guard は SQLite events 由来の semantic log projection も default で検査する。`1.8.21` で `write-status` も semantic log projection status を返し、strict failure にできる。`1.8.22` で projection export failure rollback は `--json` stderr に machine-readable diagnostic を返す。`1.8.60` で `log-records` / `history` の JSON result と text formatter は `result_mode=event-stream` / `current_state=false` / `current_state_hint` / `staleness_signals[]` を返す。`1.8.61` で `history <query>` は `current_state_target` として current page handle の `resolved_unique` / `ambiguous` / `unresolved` / `unavailable` を返し、ambiguous current projection 候補も `read_args` 付きで出す。設計上の主問題は log entry を巨大 page 内の section とするか、stable identity を持つ first-class record として materialize するか＝grasp では後者。さらに **log entry は現在状態の主張でなく過去の transition event**（A→B→C で `B になった` entry だけ読んで「今は B」と答えるのは誤り）。この節の current stale-log guard backlog は現時点で実装済み。次に追加するなら、event log を fold した current projection / provenance link が必要になった具体 workflow から目的名付き surface として切る。

## Local write and identity layer

v1 stable surface は read line。Markdown-backed `append-log` / `write-page` / `rename-page` は authoring fast path の alpha として実装済みだが、general write / transclude は未実装。public CLI の `append-section` は `1.8.70` で削除済みで、既存 `section_append` event の replay/revert 互換だけを残す。着手の3決定（write は当面 alpha testing / テスト＝この repo の過去 wiki 編集の git history を再現できるかで検証 / 実装順序は「楽な順」でなく「危険な順」）は [[write-layer-alpha-and-replay-test]]。LLM Wiki 移行の目標形は [[native-authority-markdown-projection]]: native store（＋ durable journal）が authority、Markdown は generated projection。作業は `feat/write-identity-alpha` worktree。

安定マイルストーンの読み替え（2026-06-30）: ここでの stable は read v1 ではなく、mode2 / write-authoring を安心して dogfood stable に近づける gate として扱う。優先順は、(1) `scripts/benchmark_claim_retry_throughput.py` を larger N / 複数 think time / file-back 風 workload に拡張し、`lost=0` / strict green / active claim overlap 0 / completed throughput ratio / surviving marker throughput ratio / p95 claim wait を同じ表で出す、(2) owner が throughput 下限と p95 wait 上限などの cutover 閾値を決める、(3) real dogfood で append / merge surface の要否を判定する、(4) mode2 中の Markdown 直接編集 policy は `scripts/check_mode2_markdown_readonly.py` と runbook で既定 reject / 明示 reconcile に固定済みなので継続 gate として使う、(5) stable line identity（`line.id` と `line_index` の分離、reimport diff の id 引き継ぎ）を詰める。git diff of Markdown に依存しない review/recovery evidence の最小 regression は 2026-07-01 に追加済み: file-back 風の `page_update` + `log_append` を同一 `--session-id` で束ね、別 session の update を混ぜず、`revert-plan --scope session` が projection / SQLite events を変えずに candidate / reverse order / suggested `revert-events` args を返すことを固定した。残る review/recovery backlog は、既存 scope（log-batch / subject-log / log-page-subjects / content-subjects / version-bump / same-page / event-window / time-burst / session）で説明できない実 gap、または generated Markdown backup/review policy が具体化した時に限る。実例なしに汎用 merge / queue を先に作らない。

**リンクは1種類でない**（Cosense は両方を単一 `[X]` に束ねたのが hub 膨張の根、原理 [[come-from-declared-gather]]）。write/identity 層は2型を別 first-class object としてモデル化する:

- **felt-sense link** — 行キー・sparse・per-occurrence・著者の retrieval 意図（edge）。下記 stable line-id 層に乗る。
- **come-from link** — 用語キー・1宣言・全出現・読者ケア（standing rule）。term identity に紐づき、term が動けば追従する。

未実装:

- `write` authority contract: cutover 後は人間 / Codex が Markdown を直接 patch せず、`grasp write` が native store（＋ durable journal）を更新し、`grasp export-markdown` が `wiki/` projection を再生成する。Phase 0 contract は [[sqlite-ssot-write-plan]] に固定済み（repo-local `.grasp/authority.sqlite` default、`$GRASP_CANONICAL_STORE` override、Markdown は git-tracked projection/recovery snapshot、JSONL は legacy audit/migration input）。旧 [[llm-wiki-infra-fast-path-plan]] の `events.jsonl` replayable authority 方向は prototype / replay harness 履歴として残し、次実装順としては supersede する。
- `SQLite SSoT write substrate`: `1.7.39` で canonical path helper、WAL / busy_timeout write connection、`BEGIN IMMEDIATE` transaction helperは実装済み。`1.8.0` で SQLite `events` table、既存 JSONL import helper、SQLite event query helper も実装済み。`1.8.1` で `write-page` / `write-page --create`、`1.8.2` で `append-section` / `append-log`、`1.8.3` で `rename-page` は state update と SQLite event insert を1 transaction に畳んだ。`1.8.4` で `write-status` は SQLite event count / last event を表示する。`1.8.5` で SQLite-sourced `revert-event` は target lookup を SQLite `events` 優先にし、state revert と SQLite `event_revert` insert を1 transaction に畳んだ。`1.8.6` で `log-records` / `history` は SQLite `log_entry_import` events を優先し、`import-log-records` は new / updated record events を SQLite に書く。`1.8.7` で `adopt-markdown` initial events も SQLite に書く。`write-diff` は目的が曖昧なため `1.8.8` で削除済み。`1.8.9` で projection export failure rollback も state revert と SQLite `event_revert` insert を1 transaction に畳んだ。`1.8.10` で `write-status --strict` は selected-project SQLite events が legacy JSONL journal events 内に順序を保って現れない場合に failure にする。`1.8.11` で `export-markdown` は `projection_policy` を返し、SQLite authority / git-tracked projection role / generated overlays を machine-readable にした。`scripts/check_projection_policy.py` と repo/local file-back 手順でその policy を検査する。`1.8.12` で write commands と `write-status` は `--no-journal` を持ち、SQLite events + Markdown projection だけを active path にできる。`1.8.13` で `scripts/check_file_back_preflight.py` / `scripts/check_file_back_postwrite.py` も `--no-journal` mode を持ち、journal なし path の strict status / projection policy / lint / diff check を実行できる。`1.8.14` で active runbooks は通常 file-back を `--no-journal` default に切り替え、`events.jsonl` を明示 audit 用の compatibility artifact とした。`1.8.15` で `scripts/check_file_back_runbook.py` を追加し、ship loop が no-journal default の runbook drift を検出するようにした。`1.8.16` で pre/postwrite guard scripts 自体も no-journal default になり、compatibility journal guards は `--with-journal` opt-in になった。`1.8.17` で runbooks 側の guard script 呼び出しもフラグなし default に揃えた。2026-06-27 に no-journal default guard + write command `--no-journal --output wiki` + postwrite の file-back dogfood を3連続で通し、direct Markdown patch fallback なしで commit/push まで閉じた。`1.8.18` で tracked `wiki.grasp/events.jsonl` を退役・削除し、checker は repo runbook の `--with-journal` 手順復帰を stale として検出する。`1.8.19` で `export-markdown --regenerate-log` は SQLite events を default source にした。`1.8.20` で postwrite guard は SQLite events 由来の semantic log projection も default で検査する。`1.8.21` で `write-status` は同じ semantic log projection を native status / strict failure として返す。`1.8.22` で projection export failure rollback は journal/no-journal 両方で machine-readable diagnostic を返す。`1.8.23` で `revert-event --dry-run` は rollback される transaction 内で既存 safety guard を評価し、store / journal / projection を変えずに revertibility と `would_*` effects を返す。`1.8.24` で `revert-event --include-dependents` は後続 active same-page reversible events を SQLite `event_sequence` 逆順で先に revert してから requested target を revert する。`1.8.25` で `revert-events` は明示された複数 active SQLite events を reverse `event_sequence` order で同じ transaction 内に戻す。`1.8.26` で `revert-plan --scope log-batch` は anchor event を含む log-batch work unit を前後の `log_append` 境界から read-only に推定し、candidate / excluded / reverse order / suggested `revert-events` args を返す。`1.8.27` で `revert-plan --scope same-page-dependents` は log-batch 境界なしで anchor と後続 active same-page reversible events を read-only に候補化する。`1.8.28` で `revert-plan --scope event-window` は semantic boundary が無い小さな multi-page 連続 `event_sequence` window を明示的に候補化する。`1.8.29` で `revert-plan --scope time-burst --max-gap-seconds` は explicit temporal gap で隣接 multi-page events を read-only に候補化し、非 anchor `log_append` 境界を越えない。`1.8.30` で global `--actor` / `--session-id` は SQLite event metadata に入り、`revert-plan --scope session` は同一 non-empty session の multi-page events を read-only に候補化する。`1.8.31` で `revert-plan --scope subject-log` は広すぎる log-batch を closing log subjects で絞り、matching page events と closing log を read-only に候補化する。`1.8.32` で `revert-plan --scope log-page-subjects` は closing log entry が `log.md` の `page_update` として入った履歴から、新規 log lines の subjects に一致する page events と closing log page update を read-only に候補化する。`1.8.33` で `revert-plan --scope content-subjects` は anchor event の changed lines から subjects を抽出し、changed subjects / event target overlap で page events を read-only に候補化する。`1.8.34` で content-subjects / log-page-subjects の initial adopt baseline は実作業の `write-page --create` を除外しなくなった。`1.8.35` で `content-subjects` は changed-line subject が無い場合に anchor target を fallback subject にできる。`1.8.39` で repo-local postwrite guard は latest event の session marker を検査し、通常 file-back が `revert-plan --scope session` の材料を残すことを要求する。`1.8.40` で repo-local preflight guard は session id の再利用を検査し、同じ session id が複数 file-back を束ねる gap を防ぐ。`1.8.43` で repo-local preflight guard は session/head/base を gitignored preflight stamp に記録し、postwrite guard が同じ stamp の session/head/base 一致を検査するようになった。`1.8.44` で repo-local write-start guard は preflight 後・最初の write command 直前に projection / stamp / store status を import なしで検査するようになった。`1.8.45` で repo-local guard は default store/output pair と temp store + temp output の混在を止めるようになった。`1.8.70` で purpose が薄く既存 section merge semantics と衝突した public `append-section` CLI は削除し、既存 `section_append` event は replay/revert 互換としてだけ残した。`1.8.75` で pre-write intent 用の soft page claim surface（`claim-page` / `claims` / `release-claim`、event type `page_claim` / `page_claim_release`）を追加し、`activity` も claim/release event を読む。未実装は native events からの broader semantic page files projection と、log-batch / subject-log / log-page-subjects / content-subjects / version-bump / same-page / explicit event-window / time-burst / session boundaries を使えない semantic multi-page work-unit inference。将来 projection drift / review command が必要なら `projection-diff` / `check-projection` など目的が読める名前で新設する。
- `1.8.36` で `revert-plan --scope content-subjects` は semantic match で選んだ page event を戻すために必要な後続 same-page dependents を `dependent_event_ids` として候補に足し、candidate set が意味的には正しいが実行不能になるケースを塞いだ。
- `1.8.37` で `revert-plan --scope log-batch` / `subject-log` / `log-page-subjects` も同じ後続 same-page dependent closure を使うようになり、推論 plan が選んだ page event を戻すために必要な cleanup update を `dependent_event_ids` として候補に足す。
- `1.8.38` で `revert-plan --scope version-bump` を追加し、release/file-back version update のように semver token は共有するが useful wikilink / Markdown path subjects は共有しない multi-page history を read-only に候補化できるようにした。残る semantic multi-page inference backlog は、log-batch / subject-log / log-page-subjects / content-subjects / version-bump / same-page / explicit event-window / time-burst / session boundaries では説明できない実ギャップに限る。
- `1.8.39` で repo-local postwrite guard は通常 file-back の session marker を必須にした。これは新しい推論 scope ではなく、既存の `revert-plan --scope session` を後から使えるように recovery metadata を確実に残す運用 guard。
- `1.8.40` で repo-local preflight guard は通常 file-back の session id 再利用を禁止した。これは新しい推論 scope ではなく、既存の `revert-plan --scope session` が複数 work unit を過大に束ねないようにする運用 guard。
- `1.8.41` で repo-local preflight guard の default base は current upstream tracking branch 優先になった。これは新しい推論 scope ではなく、PR branch 上で file-back を継続する時に自分の既存 PR commit を `origin/main` divergence として誤検出しないための運用 guard。
- `1.8.42` で repo-local ship loop は commit 後・push 前に `scripts/check_push_ownership.py` を通すようになった。これは dirty worktree、behind branch、通常 ship-loop からの protected branch push を止め、共有 `main` の unknown ahead commit を通常 path で押し込まないための運用 guard。
- `1.8.43` で repo-local preflight/postwrite guard は gitignored preflight stamp を使い、write 開始時の session/head/base を postwrite 時点で optimistic check するようになった。これは新しい推論 scope ではなく、preflight 後に HEAD や fetched base ref が動いた状態で wiki projection を file-back し続ける gap を防ぐ運用 guard。
- `1.8.44` で repo-local write-start guard を追加した。これは新しい推論 scope ではなく、preflight 後に別 writer が projection を変えた時、preflight 再実行で store に取り込んで隠す代わりに、最初の write command 直前の import なし check で止める運用 guard。
- `1.8.45` で repo-local guard は default store/output pair（`.grasp/file-back.sqlite` + `wiki`）と temp store + temp output の混在を止めるようになった。これは新しい推論 scope ではなく、temp dogfood が real store に log events を残して SQLite events 由来 semantic log projection を stale にする gap を防ぐ運用 guard。
- `1.8.74` で direct-patch fallback 蓄積による stale store→Markdown clobber の即時ガードを実装した（[[parallel-session-file-back-contention-2026-06-28]]）。`export-markdown` の non-check write mode は Git worktree 内の projection 差分を `--check` 相当で先読みし、既定では上書きせず re-adopt / reconcile を促す。意図的な deferred projection batch だけ `--allow-projection-overwrite` を明示する。残る恒久対策は同 entity の (a) worktree-aware file-back / projection defer queue (b) working-tree-level in-flight awareness が dogfood で必要になった時に限る。
- general `write`: 任意更新と edge 自動更新（felt-sense と come-from で別経路）。append-only alpha の `append-log`、full-page replacement alpha の `write-page`、新規 Markdown page 作成 alpha の `write-page --create --path <file.md>` は実装済み。`1.8.78` で `write-page --target page-id|path` も入り、read/history/activity/claims が返す page identity / source path を replacement target に使える。`1.8.79` で同じ identity target は `claim-page --target page-id|path` にも広がり、`activity` / `claims` query も page_id に一致する。`append-section` public CLI は `1.8.70` で削除済みで、既存 `section_append` event 互換だけを残す。
- `rename`: Markdown-backed `rename-page` alpha は page id を保ち、旧 title を alias にして incoming `[[旧名]]` の surface text を書き換えない（`1.7.15`）。rename identity を `id` / `title` / `aliases` frontmatter として projection し、direct re-import 後も page id と旧名 alias を保つ（`1.7.16`）。実 git history の `why-design-B` → `why-not-scrapbox-clone` rename replay test で、旧 surface link が書き換えなしに解決され direct re-import 後も残ることを確認（`1.7.17`）。実 git history の `0db1449` page create + multi-page update replay test で、新規 plan page 作成と既存3 page 更新が replay/direct re-import clean になることを確認（`1.7.18`）。`1.7.31` で identity frontmatter 更新時に既存の任意 frontmatter metadata を保持する merge も実装済み。`1.7.32` で `3eaab75` source digest policy correction の既存6ページ横断 update も replay/direct re-import clean にした。`1.7.33` で `3eaab75` → `3605e05` の連続 commit page_update replay も同じ journal 上で clean にした。`1.7.34` で連続 replay harness を表駆動にし、`7360053` → `8278069` の handle ambiguity sequence も同じ test で clean にした。`1.7.35` で同 harness を `create_pages` + `update_paths` の mixed operation table にし、`0db1449` → `a07f1af` の fast-path plan create + later update sequence も clean にした。`1.7.36` で同 harness に `rename_pages` を足し、`d4e4c39` の `why-design-B` → `why-not-scrapbox-clone` rename invariant も continuous table で確認した。`1.7.37` で `revert_events` を足し、`0db1449` の fast-path plan page_create を同じ step 内で revert する sequence も clean にした。`1.7.38` で title / current file stem から導出できない旧名 alias がある場合は projection frontmatter を生成するようにし、`write-page --create` → `rename-page` → fresh `import --markdown` でも旧 `[[...]]` backlink が red 化しない regression test を追加した。`1.8.3` で rename state update と SQLite `events` row insert は同じ transaction に畳んだ。`1.8.62` で `3eaab75` の既存6ページ横断 `page_update` を適用後、`grasp-backlog.md` の `page_update` だけを revert する実履歴 regression も追加した。`1.8.63` で rename の projection export failure rollback は旧 projection file を削除する前に新 projection export を試すようにし、export 失敗時に SQLite は戻っているが旧 Markdown file が消える gap を塞いだ。`1.8.64` で export が途中 file まで書いてから後続 file の path/read error で失敗し、SQLite rollback 後も先行 Markdown projection だけ新内容で残る gap を塞いだ。`1.8.65` で page_create / page_rename revert の不要 projection file 削除も export 成功後に移し、revert export failure が既存 projection file を先に消す gap を塞いだ。未実装はさらに広い履歴 corpus から見つかる具体的な recovery gap。
- `transclude`: line-id を使った行参照。
- `export-markdown`: stored lines preserving projection と `--check` no-op gate は実装済み（`1.7.10`）。`append-section` / `append-log` 後の projection export も実装済み（`1.7.11`）。`write-diff` は `1.7.12` で current filesystem -> stored projection の unified diff として追加されたが、SQLite SSoT milestone では目的が曖昧になったため `1.8.8` で削除済み。no-op / drift check は `export-markdown --check` / `write-status --strict` が担う。`--regenerate-index` / `--regenerate-log` の明示 alpha overlay で primary index/log の最小 regeneration は実装済み（`1.7.21`）。`1.8.11` で JSON result に `projection_policy` を追加し、projection authority / base / output role / write mode / generated overlays を検査できるようにした。`1.8.19` で `--regenerate-log` は SQLite events を既定 source にし、partial stream は log page `page_update` / `page_rename` を seed にできる。`1.8.20` で repo-local postwrite はその semantic generated log projection を default guard に含め、`1.8.21` で `write-status` も native status / strict failure として返すようになった。`1.8.64` で write mode の export は全対象を読み取って変更/missing を判定し、書き込み先 path を preflight してから実 file write に入るようになった。`1.8.74` で Git worktree 内の non-check export は projection 差分を既定で上書きせず、re-adopt/reconcile か `--allow-projection-overwrite` を要求するようになった。未実装は native events 由来 projection の本格 policy、必要が具体化した場合の目的名付き review surface。
- status / rollback or revert event: append/log/page_update/page_rename alpha 用の `write-status` / `revert-event` は実装済み（`1.7.12`-`1.7.15`）。`write-diff` は目的が曖昧なため `1.8.8` で削除済み。page_create revert も実装済み（`1.7.19`）。projection export 失敗時は target event を残した上で自動 `event_revert` を append し、store を戻す（`1.7.20`）。`1.8.5` で SQLite-sourced `revert-event` は SQLite event stream から target を読み、state revert と `event_revert` row を同じ transaction に残す。`1.8.9` で projection export failure rollback も state revert と SQLite `event_revert` insert を同じ transaction に残す。`1.8.22` で projection export failure rollback は `--json` stderr に `projection_export_rollback` diagnostic を返し、no-journal path でも target/rollback event id と元 error を検査できるようにした。`1.8.23` で `revert-event --dry-run` は可逆/不可逆と理由を mutation なしで返すようになった。`1.8.24` で `revert-event --include-dependents` は同一 page の後続 active reversible events を含めて mutation するようになった。`1.8.25` で `revert-events` は複数の明示 target events を1つの SQLite transaction で reverse `event_sequence` order に戻す。`1.8.26` で `revert-plan --scope log-batch` は log-batch 境界から inferred work unit と reverse revert order を mutation なしで返す。`1.8.27` で `revert-plan --scope same-page-dependents` は同一 page の dependency-aware revert plan を mutation なしで返す。`1.8.28` で `revert-plan --scope event-window` は明示された bounded multi-page event_sequence window を mutation なしで返す。`1.8.29` で `revert-plan --scope time-burst` は明示された temporal gap 内の multi-page burst を mutation なしで返す。`1.8.30` で `revert-plan --scope session` は明示された session metadata の multi-page work unit を mutation なしで返す。`1.8.31` で `revert-plan --scope subject-log` は closing log subjects による multi-page work unit を mutation なしで返す。`1.8.32` で `revert-plan --scope log-page-subjects` は direct log page update の追加 log subjects による multi-page work unit を mutation なしで返す。`1.8.33` で `revert-plan --scope content-subjects` は changed content subject overlap による multi-page work unit を mutation なしで返す。`1.8.34` で initial adopt baseline の page_create 誤除外を塞ぎ、`1.8.35` で changed-line subject が無い anchor でも target fallback で content-subjects planning できる。`1.8.65` で actual revert 系 command は projection export 成功後に不要 projection file を削除する順序へ揃えた。`1.8.66` で actual revert 後の projection finalization failure も `--json` diagnostic として返すようにし、`1.8.67` で legacy/ad hoc `--journal` の append 不可能 path は mutation 前に `journal_append_preflight_failed` として拒否するようにし、`1.8.68` で既存 regular journal file の write permission と missing path の parent permission も同 preflight に含め、`1.8.69` で既存 journal JSONL の parse / schema validation も mutation 前 preflight に含めた。未実装は log-batch / subject-log / log-page-subjects / content-subjects / same-page / explicit event-window / time-burst / session boundaries を使えない semantic multi-page SQLite authority revert planning。
- aliases / page-id policy（page id を「いつ・誰が・どの意味判断で」振るか）。
- stable line-id policy（下記 stable line identity 参照）。
- durable journal policy: 方向は [[sqlite-write-concurrency]] / [[sqlite-ssot-write-plan]] で **SQLite primary + events table** に決めた。canonical store helper、events table、JSONL import、actor/session metadata columns、`adopt-markdown` initial events、`write-page` / `append-log` / `rename-page` / legacy `section_append` replay/revert compatibility / SQLite-sourced `revert-event` / projection export failure rollback / projection rollback diagnostics / `revert-event --dry-run` planning / `revert-event --include-dependents` / `revert-events` / `revert-plan --scope log-batch` / `revert-plan --scope same-page-dependents` / `revert-plan --scope event-window` / `revert-plan --scope time-burst` / `revert-plan --scope session` / `revert-plan --scope subject-log` / `revert-plan --scope log-page-subjects` / `revert-plan --scope content-subjects` with baseline hardening, anchor-target fallback, and same-page dependent closure / new-or-updated `import-log-records` の SQLite events 書き込み、`write-status` の SQLite event summary と legacy JSONL mismatch guard、SQLite-sourced `log-records` / `history`、write/status と repo-local pre/postwrite checker の no-journal default、repo file-back の `--no-journal` default cutover、runbook drift checker、no-journal default の3連続 dogfood、tracked `wiki.grasp/events.jsonl` の退役・削除、`export-markdown --regenerate-log` の SQLite events default、postwrite の semantic log projection default guard、preflight の session id uniqueness guard と current-upstream default base、push ownership guard、preflight stamp guard、write-start guard、store/output pair guard、`write-status` の semantic log projection native status / strict failure は実装済み。未実装は log-batch / subject-log / log-page-subjects / content-subjects / same-page / explicit event-window / time-burst / session boundaries を使えない semantic multi-page work-unit inference、必要が具体化した場合の generated Markdown backup/review policy。`write-diff` recovery surface は目的が曖昧なため `1.8.8` で削除済み。`--journal` / `--with-journal` は legacy/ad hoc CLI audit 用としてだけ残る。
- **parallel agent write / push guard**: [[llm-wiki-infra-fast-path-plan]] の初期計画は single writer 前提で、複数 agent が同じ `main` / `wiki.grasp/events.jsonl` / `wiki/` projection に書く場合の規定が薄かった。preflight guard は current upstream（なければ `origin/main`）との差分、unexpected dirty wiki path / retired JSONL path 再作成、未使用 session id、gitignored preflight stamp による write 開始時 session/head/base optimistic check、default store/output pair と temp store + temp output の混在禁止を検査するところまで実装済み。write-start guard は preflight 後・最初の write command 直前に projection / stamp / store status と store/output pair を import なしで再確認する。postwrite guard も同じ pair を確認する。push ownership guard は dirty worktree、behind branch、通常 ship-loop からの protected branch push を止めるところまで実装済み。`1.8.75` で `activity` に event が出る前の intent は `claim-page` soft lease と `claims` で最小実装済み。`1.8.76` で `activity` は expired/released claim を active session から外す claim-state fold も持つ。`1.8.77` で guard failure recovery ladder は `activity --limit 20` に加えて `claims --include-expired` も案内する。`1.8.79` で claim/activity/claims は page_id query と `claim-page --target page-id|path` を持つため、観測済み identity を pre-write intent に戻せる。guard が落ちたら isolated worktree へ誘導する。残る未実装はこの guard 群ではなく、semantic multi-page work-unit inference、generated Markdown backup/review policy、または real dogfood で必要が出た場合の queue / automated reconcile 側。
- **【Codex handoff】mode2 並行編集 dogfood が出した実装タスク**（証跡 [[mode2-parallel-edit-stress-2026-06-30]]）。2026-06-30 に throwaway mode2 store を2プロセスで並行 loop 編集した結果、現状の前提を直す具体作業が出た。(P0) は cutover の前提条件:
  - **(P0a) projection / graph compute の性能病**: 高リンク密度 project（grasp-wiki ~60p / nishio 25,791p）で `export-markdown`（read-only `--check` 単体でも）と `write-page` が 96% CPU で数分〜未完 spin。低密度の llmwiki 743p は高速 → **link 密度に superlinear（O(edges²) 級）疑い**。Homebrew Python 3.14.5 環境。2026-06-30 Codex follow-up 第1段では現 checkout の `.grasp/file-back.sqlite` + `wiki` で `export-markdown --check` 0.20s / `write-status --strict` 0.47s、合成 200p/39,800 edges でも `export-markdown --check` 0.23s で再現せず。第2段の import scaling で `refresh_edge_resolutions` の correlated subquery UPDATE が支配的と判明し、temp handle-count table + indexed `UPDATE FROM` へ変更して修正済み。synthetic 1200p/21600 edges の refresh 単体は 10.65s → 0.26s、3000p/54000 edges full import は 9.7s、1-file re-import は 2.1s。残る性能設計課題は上の progressive / lazy import。
  - **(P0b) content-level lost-update 検出 guard**: 2026-06-30 Codex follow-up で実装済み。`write-status --no-journal --strict` は SQLite events の `page_update` payload を見て、短時間 window 内の cross-session update が直前 update 由来の line_id を消した場合に `concurrent_page_update_overwrites[]` と strict failure `concurrent_page_update_overwrite` を返す。無協調 hot-page stress は 20 write 中 10 lost のままだが、以前の GREEN ではなく strict exit 1 になった。通常の行テキスト変更を false positive にしないため text ではなく line_id ベース。
  - **(P1a) `claim-page` を実効直列化へ格上げ**: 2026-06-30 Codex follow-up で実装済み。`claim-page` / `release-claim` は active state check を `BEGIN IMMEDIATE` transaction 内で再実行し、同時 claim / 同時 release の regression を追加。`write-page` も同じ transaction 内で active claim を確認し、別 session claim 中の target page write は rollback して拒否する。修正前は `claim-page` + retry stress で 50 write 成功中 6 lost / active claim overlap 6、修正後は 50/50 marker 生存 / overlap 0。
  - **(P1b) skip した編集の retry / merge**: 2026-06-30 Codex follow-up で claim retry surface は実装済み。`claim-page --wait-seconds` / `--retry-interval-seconds` が active claim conflict を待って再試行し、JSON result に `claim_attempts` / `claim_waited_seconds` を返す。2プロセス×25 hot-page stress は 50/50 marker 生存 / lost 0 / overlap 0 / strict green。残る未実装は、append 系などで claim を使わない merge surface が具体 workflow で必要になった場合の目的名付き command。
  - 受け入れ条件: 「2プロセス×N iteration の hot-page 奪い合いで lost-update 0」を回帰試験 `tests/` に固定する第一段は P0b/P1a/P1b claim retry で進み、2026-06-30 Codex follow-up で軽量 subprocess regression（2 worker × 4 iteration、同一 page、全 marker 生存、projection export 後 strict green）として固定済み。同 follow-up で `scripts/benchmark_claim_retry_throughput.py` も追加し、同条件（2 worker × 4 iteration、think 0.02s）の測定では無協調が 8 write 中 4 lost / strict failure、claim_retry が 8/8 生存 / strict green、completed write throughput は無協調比 0.322、surviving marker throughput は 0.645 だった。2026-06-30 Codex follow-up 第2段で同 benchmark は larger N / 複数 think time / file-back 風の read→write-page→append-log→projection workload に拡張済みで、第3段では append-log 側の marker survival も `log_lost` として測るようにした。`--iterations 25 --think-seconds 0,0.02,0.05 --workload file-back --format table` では claim_retry が全3条件で 50/50 page marker 生存、page lost 0、log_lost 0、strict green、active claim overlap 0、p95 claim wait 0.462/0.474/0.684s。completed throughput ratio は 0.397/0.390/0.374、surviving throughput ratio は 0.794/0.780/0.747。2026-06-30 Codex follow-up 第4段で同 benchmark は owner threshold を任意指定できる `--min-surviving-throughput-ratio` / `--max-p95-claim-wait-seconds` を持った。未指定なら従来どおり correctness gate のみ、指定時は JSON/table に optional cutover gate を出し、閾値未達で exit 1。残る cutover gate は owner がこの2値を決めること、append 系 merge surface が必要かを real dogfood で見極めること（[[adoption-trust-gradient]] の「信頼を測る指標」）。今回の file-back 風 synthetic では append-log 喪失は観測されず、generic merge / queue を先に足す根拠にはまだならない。mode2 cutover の可否は、owner が閾値を置いてから判断する。
  - **mode2 Markdown 直接編集 policy guard**: 2026-06-30 Codex follow-up で `scripts/check_mode2_markdown_readonly.py` を追加済み。guard は `export-markdown --check` の projection policy と `write-status --no-journal --strict` をまとめて見て、Markdown projection が SQLite authority から drift したら fail するだけで自動採用しない。意図的な direct-patch fallback / remote merge は `reconcile-markdown --dry-run` で blocker が無いことを見てから、fresh `GRASP_SESSION_ID` で明示 reconcile する。unsupported blocker は purpose-named merge surface が必要になるまで未実装のままにし、generic merge / queue は先に足さない。
- journal JSONL event type contract は `grasp.journal` で固定済み（`1.7.9`）。`adopt-markdown` は `page_create` events を append する（`1.7.10`）。`append-log` は `log_append` events を append する。`section_append` は過去の `append-section` 由来 event type として replay/revert 互換に残すが、`1.8.70` 以降 public CLI では新規生成しない。`1.8.75` で soft claim 用に `page_claim` / `page_claim_release` を追加した。`revert-event` は `event_revert` を append する（`1.7.12`）。`replay-journal` は `page_create` / `page_update` / `page_rename` / append / revert events から Markdown projection を strict replay する（`1.7.13`-`1.7.20`）。`revert-event --dry-run` と `revert-plan` は `event_revert` を append しない read-only planning surface として実装済み。`revert-event --include-dependents` と `revert-events` は actual path で複数の SQLite `event_revert` rows を同じ transaction に書き、compatibility journal が有効な時は対応する複数の `event_revert` events を append する。未実装は log-batch / subject-log / log-page-subjects / content-subjects / same-page / explicit event-window / time-burst / session boundaries を使えない semantic multi-page work-unit inference。
- **rename を跨ぐ stable page-id**（identity-without-name の consumer 側の本体）: AI は根拠をページ単位で引用するので write/rename で title が動くと過去セッションの引用が腐る。`read --json` が安定 page-id を返すこと自体が consumer 価値。read 出力 field は既済、stable identity 化が未済（[[ai-consumer-feedback-2026-06-23]] Tier 4 / [[why-not-scrapbox-clone]]）。

補足: hosted Cosense に AI から書く用途は [[cosense-cli]] の `previewEdit` / `submitEdit` が担う。grasp の write 層は local-only store / 非 Cosense ユーザ向けの別目的。

### typed / directional link（デライトの引き入れ＝前景後景型）

デライトの引き入れ（1輪郭を複数の親に入れる多重所属）は無型の関連リンクでなく「前景（親）/後景（子）」の向き付き包含＝ typed link とみなせる（原理 [[cosense-delite-howm-synthesis]]）。grasp は現状リンクが無型（Cosense 同様、全 predicate が related）。未実装 / 論点:

- リンクに型（向き付き構造型 contains / part_of を最小に）を持たせるか。型は felt-sense / come-from と直交（どちらの型のリンクにも型は乗りうる）。
- 向き（前景/後景）と無向グラフの両立: `related` / `path` は retrieval 用に無向へ畳むので、型付き構造リンクを入れても無向 projection を別に保つ二層が要る。
- 型付けを著者宣言にするか AI ingest 時に自動推定するか（「最初は無印、重要になったら型」「型語彙を増やしすぎない」。整理を runtime/AI に逃がす方針なら型推定は AI 側に寄せる）。
- 多重所属自体は既に持つ。デライトが足すのは遠近＝前景/後景の順序。edge 属性として持つか、`read` 出力でどう見せ分けるか。

### stable line identity

`page.id:line-index` は **安定 line ID でなく positional locator**（行挿入で後続 locator が変わる）。content hash は本文編集で、line index は挿入で identity が変わるため不可＝**stable ID requires memory**。identity 層では `line.id`（opaque stable）と `line_index`（current order）を別列にする。要件:

- 2026-06-26 の前処理として、`line_window.around_line_id` / search context window は `page.id:line-index` を再合成せず stored `lines.line_id` を返すようにした（`1.7.8`）。2026-07-01 に Markdown content-only re-import と `write-page` replacement は exact unchanged line の `line_id` を引き継ぐ第一 slice を実装した。初回 mint はまだ source page id + line index 由来で、挿入時に既存 id と衝突する re-import 新規 line だけ opaque suffix を mint する。`write-page` の新規 inserted line は opaque `line-<uuid>` を mint する。
- local write は moved exact-same line の id 維持まで実装済み。残る未実装は、既存 line を `line_id` で指定して編集する command surface と、split / merge / move / 重複行 / 大幅編集の曖昧一致を自動同一視しない policy surface。
- 外部 source（Cosense export / Markdown mirror）に line id が無ければ初回 import 時に grasp が mint し、identity journal に保持する。
- sync / reimport は旧新 lines を diff し、同一と判定できる line だけ id を引き継ぐ。Markdown content-only re-import と `write-page` replacement の exact unchanged line 引き継ぎは実装済み。残る未実装は Cosense / hosted sync 側、line tombstone、line-id 指定 write、split / merge / move / 重複行 / 大幅編集の曖昧一致を自動同一視しない policy surface。

schema 方向:

```text
lines(project, id, page_id, line_index, text, created, updated, user_id)
line_tombstones(project, id, page_id, deleted_at, last_text?)
```

## Search and retrieval

recall（boolean / page scope / 正規化 fallback）は実装済み。順序は **recall を直してから** FTS5 速度最適化（recall と速度は別軸）。未実装:

- **semantic embedding search**。長文 title / うろ覚えパンチライン問題への第一段として `suggest` の asearch-style lexical fuzzy title suggestion は実装済み（`1.7.7`）。ただしこれは表記・断片・文字順序近似であり、同概念別語の semantic retrieval ではない。embedding はその後続層として、`fuzzy propose / human recognize` の候補提示に留め、自動 merge しない。
- **大規模 store での完全なかな/カナ・全半角本文正規化 index**。本文側を materialize した normalized column / FTS hybrid / trigram で持たない限り、完全な正規化 search は大規模 store で高コスト（現状の Python scan は 50k lines 以下に限定）。
- FTS5 trigram hybrid による `search` 高速化。literal substring semantics を守るには `LIKE` fallback / post-filter が要る（[[fts5-trigram-search]]）。
- backlink line の前後文脈窓。
- related ranking の重み調整と、大規模化した時の 2-hop cost 対策。

### gather / mentions / co-links の残課題

`mentions` / `co-links` / `gather`（come-from 昇格候補の初期 heuristic scoring、`returned/total/omitted_counts`、`co-links --rank slice` を含む）は実装済み。出典 [[ai-consumer-feedback-2026-06-23]] Tier 2、KJ法 hub の実測は [[kj-link-hub-audit-2026-06-24]]、原理は [[come-from-declared-gather]]。

**設計テンション（未決）**: 太い verb `gather` は orchestration を CLI に寄せ、「薄い CLI / Skill がオーケストレーション」境界（[[delivery-cli-plus-skill]]）と緊張する。薄さを保つなら Skill 側に gather レシピ、太くするなら verb。nishio 判断待ち。改善の成功条件は「`[KJ法]` backlinks が増える」ことではなく、巨大 hub が **root link + 用途別 slice handle** に分岐し、agent が hub 全体を読まず必要な slice だけ読める状態。

未実装:

- `mentions` の正規化（完全なかな/カナ・全半角）、word boundary、多義語 disambiguation（現状は literal query）。
- come-from 昇格候補の高次分類（AI 作 default 裸 / 意図的 non-link / link gap の3源）、実データでの閾値調整、多義語の一意性判定。
- `co-links` の query-containing でも有用な narrow page（例: `AIにKJ法を教える`）と bibliographic/session title の finer classification、weighting 調整、実データ dogfood。
- `gather --budget` の厳密 token packing / omitted token estimate / 代表サンプル選択の精密化（現状は row 単位 limit）。
- AI clustering handoff: CLI は固定 cluster label を確定せず、AI が仮分類できる bounded rows + sample provenance を返す方針を継続する。

### use-case report composition（icon/person history）

巨大抽出系の「いい感じ」な outcome には report composition 層が要る（原理 [[use-case-experiment-as-outcome-story]]）。raw hits（villagepump `[nishio.icon]` 6,488 paragraphs）は到達としては成功でも、そのままでは読めない。CLI / acquisition 側が返すとよいもの:

- icon/person slice の取得条件（project, diary page rule, date range, icon/user handle, coverage, failures）。
- `icon_hit_kind`（author marker / sentence signed at end / prefix speaker / reaction icon list / mention-of-person / other）。最低限 `[nishio.icon]さん` 型の言及と reaction-only 行を本文発話から分ける。
- representative candidate bundle（year/month counts, top linked targets, keyword/theme counts, longest blocks, source title / line id / snippet つき high-signal examples）。
- report handoff contract: CLI は narrative を確定せず、agent/report 層がユーザ言語で timeline / themes / 代表 scene / caveat / source links を書く。

仮 surface（名前未決）:

```text
grasp acquire https://scrapbox.io/villagepump/ --diary --icon nishio --until 2026-06-24
grasp report icon-history nishio --themes ai,scrapbox,community --top 30
```

重要なのは raw dump でなく **bounded candidate bundle + agent-authored report** を標準 workflow にすること。

### come-from declare / render 層（新規）

巨大 hub が膨れる *why* = per-occurrence の局所判断 × 双方向の大域帰結のミスマッチ（誰も「KJ法 を 490-backlink hub に」と決めていないのに、各ページの親切な `[KJ法]` の副作用で hub ができる）。∴ 対処は「もっとリンク」でも「消す」でもなく、判断を帰結と同じ用語-大域レベルに上げる＝come-from（原理 [[come-from-declared-gather]]）。未実装:

- **come-from declare 層**: 用語を come-from term として標す per-term standing rule（`mentions <query>` の ad-hoc query を declarative に固定）。store 表現は専用テーブル or 宛先ページ frontmatter `come_from: [...]`（後者は Markdown mirror と親和）。
- **come-from render 層**: Markdown mirror / 公開 view を materialize する時、come-from term の裸出現を自動リンク化。store（裸）と view（リンク済み）を分離する（authoring=裸＋宣言 / rendered=自動リンク）。
- 安全域＝必要域: 文字列マッチで多義語は過剰収集するが、読者ケアが要る uncommon 語 ≈ 一意なので安全。昇格候補抽出は「uncommon さ × 頻度 × 一意性」で機械化できる。

## Graph-native reasoning primitives

出典 [[ai-consumer-feedback-2026-06-23]] Tier 3（embeddings 無しの純グラフ操作で「Markdown 束には出せない」価値が出る所）。

- **`path <A> <B>`**: 初期実装済み（pages ∪ unresolved targets を node、materialized internal links を無向 edge、no-path recovery hints まで）。実測でページ間距離は「大半 ≤2-hop」ではなく `path --max-depth 4` の価値あり。残課題: dense hub での performance（nishio store で約4-5s）、neighbor ranking、複数 shortest paths の出し方、実用的に意味のある経路かの継続 dogfood。
- **backlinks の finer ranking**: コア（views ランク）は実装済み。残るのは link 密度 / multiplicity / recency の重み付けで「最も中心的な 20 件」の精度を上げること。

却下（再提案しない）:

- **近傍クラスタリング `--cluster`** — クラスタリングは AI の責務（AI の方が賢い）。grasp は raw + ranking を返し AI が sub-theme に畳む（[[ai-consumer-cost-and-trust]] の fidelity 方針）。CLI でやるなら embeddings 導入後の optional な雑 embedding クラスタリングのみ。却下するのは CLI が cluster label を作ること自体で、AI が clustering できる raw material（counts / ranked rows / co-link slices / bare mention samples）を出す primitive はむしろ必要（上記 gather 系）。

## Negative-result contract

空結果を「情報」として返す（絶対的不在 vs マッチ失敗の区別、[[ai-consumer-cost-and-trust]] 軸2）。`read` / `link-stats` / `search` / `related` の zero-hit recovery hints は実装済み（command 文字列だけでなく近い title 候補・正規化候補・部分一致 line などの実データを含む）。未実装:

- 今後追加する retrieval verb（例: `gather`）でも empty result contract が揃っているかの継続監査。

## Output token economy

line-id のローカル別名（text で `P1:0`、`--json` / `--full-ids` で完全 ID、先頭付近に legend）は実装済み（[[ai-consumer-cost-and-trust]] 軸1）。

却下（再提案しない）:

- **`--strip-decoration`**（icon / bare image URL 単独行を畳む）— decoration 行は noise ではない。`[nishio.icon]` は block の著者情報、bare image URL は今の AI に読めなくても人間に画像を提示でき将来の AI は読む。token 削減は line-id 別名側でやる。

## Sync freshness

`grasp sync` の basic recent upsert と `--full-reconcile` は実装済み（[[incremental-sync]]）。`1.8.82` で full manifest reconcile / hosted delete tombstone / rename detection / partial acquisition boundary / hosted line-id policy は current facts に昇格済み。未実装:

- **hosted REST metadata enrichment**: `readPage` / `/api/pages/:project/:title` で得られる `commitId`、stable `lines[].id`、`links` / `projectLinks` / `icons`、`linked`、`pageRank`、`accessed`、`relatedPages` をどこまで store に保存するか決める。JSON export seed には無いので optional source-specific columns として扱う。
- **authenticated delete / rename history enrichment**: 現行 `--full-reconcile` は manifest 差分から delete tombstone と same-id rename を扱う。認証済み path で `/api/deleted-pages/:project/:pageId`、`/api/stream/:project` の `page.delete` event、`/api/commits/:project/:pageId` の `TitleChange` を取り、tombstone / alias history を補強できるか検証する。
- **external hosted line-id persistence**: 方針は「hosted `lines[].id` は local `lines.line_id` に混ぜず、将来 `external_line_id` として別列にする」で決定済み。実装は schema bump が必要なので未着手。
- **last-sync cursor の運用精度**: pinned pages / updated ties / clock skew / partial failure の扱い。

## Cross-project graph / whole-store retrieval residuals

`1.9.0` で [[whole-store-graph-and-cross-project-edges]] の本体は実装済み: `edges.target_project` / `link_kind` / `connection_strength`、Cosense `[/project/title]` の first-class strong edge、bare unresolved link から他 project materialized page への weak normalized-title edge、`read` / `search` / `backlinks` / `related` / `path` / `unresolved` の whole-store default、read ambiguity disambiguation、whole-store unresolved project spread。

残課題:

- referenced-only namespace の coverage rollup を `stats` / project report にどう surface するか。
- slash-in-title 確定規則（第1 segment=project / 残り=title）の実データ検証と、`raw` を使った将来再解決方針。
- dense graph での whole-store `related` / `path` bound と ranking の継続 dogfood。
- weak 接続の rank / 閾値調整と、同綴り別概念の誤接続頻度の dogfood。
- link 同一判定の表記ゆれ吸収（`yyyy/MM/dd`⇄`yyyy-MM-dd` 等、[[scrapbubble]]）。

## Hosted Cosense acquisition without admin export

`grasp acquire <project-url>`（`--search` / `--filter` / `--full-list` / `--from-page --depth` / `--seed-file`）、`cross-project-refs`（抽出・分類・seed file / acquire command 生成）、`cross-project-acquire`（複数 project を `<project>:semantic` へ一括 partial acquire）、acquire reuse、fetch-stage の env 診断 / all-failed diagnostic は実装済み。current facts は [[grasp-v1-implemented]] の acquire facts、dogfood は [[cross-project-reference-acquire-2026-06-24]]。

未実装 / 残課題:

- **direct public API fallback**: `cosense` binary / Node が無い環境でも public project は Scrapbox API（`curl .../api/pages/<project>` 等）で読める。auth が要る project では従来通り `cosense-cli` に戻す adapter。villagepump dogfood で `cosense` 不在により acquire 不可だったので、入れれば agent 実験の摩擦が下がる。副観測: `search/query?q=...` は 100 件固定で `skip` が効かず、網羅抽出には `pages?sort=title` の列挙が要る。
- env 診断（`cosense` / `node` の shebang `env node` 失敗等）を seed discovery phase（`searchFullText` / `listPages`）へ拡張する。fetch phase は実装済み。
- `cross-project-acquire` の実データ dogfood、project / target ranking の weighting 調整、取得後 summary（reciprocal refs / top internal links / cluster handoff）の richer 化。

設計上の注意（実装時に守る）:

- partial corpus 上の `backlinks` / `related` / `unresolved` は「取得済み subset 内」の結果で、project 全体の事実として表示しない。
- 同じ hosted project の複数 slice を同じ namespace に混ぜると coverage の意味が曖昧になる。`--project project:slice` で分けるか coverage metadata を project 単位で合成する。
- 権限は「その user / token が通常読める page だけ」。admin export の代替であって越権取得経路ではない。
- acquisition mode / seed / depth / limit / acquired_at / failed pages / criteria fingerprint / page manifest を metadata に残す（実装済み、partial の意味を保つため）。

Open Questions:

- `listPages` は非 admin readable project で全ページを pagination できるか。
- `searchFullText` は `[nishio.icon]` / `[/nishio/` を literal に扱うか。検索上限超過時の pagination / continuation はあるか。
- all-candidate 失敗でも exit 0 で partial result を返す方針を維持するか。
- ~~`readPage` の hosted line id を採用するか~~ → hosted id は observed-only。local `lines.line_id` は grasp-managed locator のままにし、将来 `external_line_id` 列で別管理する。
- ~~partial corpus で `sync` する時、seed predicate 外の recently updated page を取り込むか、acquisition mode ごとに sync 動詞を分けるか~~ → partial corpus は `acquire` criteria 再実行、full mirror は `sync`。`sync` は partial acquisition namespace で mutation しない。
- direct public API fallback を入れる場合、Scrapbox API と cosense-cli の metadata / auth / rate limit / search semantics の差をどこまで surface に出すか。

## Packaging and distribution

実装言語と配布チャネルの軸は [[language-and-distribution]]（当面 Python + pipx）。未実装:

- PyPI 公開時の package 名確認。
- `pipx install` 前提の配布導線。
- user-level Skill symlink と package install の統合。
- Python 不可 agent 環境が現実化した場合の native binary 配布。
