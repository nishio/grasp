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

## Markdown / Obsidian indexed mirror

最小 read-only mirror（`import --markdown <folder>`、frontmatter title/id/aliases/tags、first H1 title resolution、content-only 差分 index、`--markdown-exclude-dir` による heavy raw/generated directory 除外）は実装済み。決定は [[markdown-obsidian-indexed-mirror]]。未実装:

- surface 命名: `index-md` / `import-md` / `import --format markdown <folder>` を足すか（現状は `import --markdown <folder>`）。
- Obsidian block refs / heading anchors の line-id 対応。
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

v1 stable surface は read line。Markdown-backed `append-section` / `append-log` / `write-page` / `rename-page` は authoring fast path の alpha として実装済みだが、general write / transclude は未実装。着手の3決定（write は当面 alpha testing / テスト＝この repo の過去 wiki 編集の git history を再現できるかで検証 / 実装順序は「楽な順」でなく「危険な順」）は [[write-layer-alpha-and-replay-test]]。LLM Wiki 移行の目標形は [[native-authority-markdown-projection]]: native store（＋ durable journal）が authority、Markdown は generated projection。作業は `feat/write-identity-alpha` worktree。

**リンクは1種類でない**（Cosense は両方を単一 `[X]` に束ねたのが hub 膨張の根、原理 [[come-from-declared-gather]]）。write/identity 層は2型を別 first-class object としてモデル化する:

- **felt-sense link** — 行キー・sparse・per-occurrence・著者の retrieval 意図（edge）。下記 stable line-id 層に乗る。
- **come-from link** — 用語キー・1宣言・全出現・読者ケア（standing rule）。term identity に紐づき、term が動けば追従する。

未実装:

- `write` authority contract: cutover 後は人間 / Codex が Markdown を直接 patch せず、`grasp write` が native store（＋ durable journal）を更新し、`grasp export-markdown` が `wiki/` projection を再生成する。Phase 0 contract は [[sqlite-ssot-write-plan]] に固定済み（repo-local `.grasp/authority.sqlite` default、`$GRASP_CANONICAL_STORE` override、Markdown は git-tracked projection/recovery snapshot、JSONL は legacy audit/migration input）。旧 [[llm-wiki-infra-fast-path-plan]] の `events.jsonl` replayable authority 方向は prototype / replay harness 履歴として残し、次実装順としては supersede する。
- `SQLite SSoT write substrate`: `1.7.39` で canonical path helper、WAL / busy_timeout write connection、`BEGIN IMMEDIATE` transaction helperは実装済み。`1.8.0` で SQLite `events` table、既存 JSONL import helper、SQLite event query helper も実装済み。`1.8.1` で `write-page` / `write-page --create`、`1.8.2` で `append-section` / `append-log`、`1.8.3` で `rename-page` は state update と SQLite event insert を1 transaction に畳んだ。`1.8.4` で `write-status` は SQLite event count / last event を表示する。`1.8.5` で SQLite-sourced `revert-event` は target lookup を SQLite `events` 優先にし、state revert と SQLite `event_revert` insert を1 transaction に畳んだ。`1.8.6` で `log-records` / `history` は SQLite `log_entry_import` events を優先し、`import-log-records` は new / updated record events を SQLite に書く。`1.8.7` で `adopt-markdown` initial events も SQLite に書く。`write-diff` は目的が曖昧なため `1.8.8` で削除済み。`1.8.9` で projection export failure rollback も state revert と SQLite `event_revert` insert を1 transaction に畳んだ。`1.8.10` で `write-status --strict` は selected-project SQLite events が legacy JSONL journal events 内に順序を保って現れない場合に failure にする。`1.8.11` で `export-markdown` は `projection_policy` を返し、SQLite authority / git-tracked projection role / generated overlays を machine-readable にした。`scripts/check_projection_policy.py` と repo/local file-back 手順でその policy を検査する。`1.8.12` で write commands と `write-status` は `--no-journal` を持ち、SQLite events + Markdown projection だけを active path にできる。`1.8.13` で `scripts/check_file_back_preflight.py` / `scripts/check_file_back_postwrite.py` も `--no-journal` mode を持ち、journal なし path の strict status / projection policy / lint / diff check を実行できる。`1.8.14` で active runbooks は通常 file-back を `--no-journal` default に切り替え、`events.jsonl` を明示 audit 用の compatibility artifact とした。`1.8.15` で `scripts/check_file_back_runbook.py` を追加し、ship loop が no-journal default の runbook drift を検出するようにした。`1.8.16` で pre/postwrite guard scripts 自体も no-journal default になり、compatibility journal guards は `--with-journal` opt-in になった。`1.8.17` で runbooks 側の guard script 呼び出しもフラグなし default に揃えた。2026-06-27 に no-journal default guard + write command `--no-journal --output wiki` + postwrite の file-back dogfood を3連続で通し、direct Markdown patch fallback なしで commit/push まで閉じた。`1.8.18` で tracked `wiki.grasp/events.jsonl` を退役・削除し、checker は repo runbook の `--with-journal` 手順復帰を stale として検出する。`1.8.19` で `export-markdown --regenerate-log` は SQLite events を default source にした。`1.8.20` で postwrite guard は SQLite events 由来の semantic log projection も default で検査する。`1.8.21` で `write-status` は同じ semantic log projection を native status / strict failure として返す。`1.8.22` で projection export failure rollback は journal/no-journal 両方で machine-readable diagnostic を返す。`1.8.23` で `revert-event --dry-run` は rollback される transaction 内で既存 safety guard を評価し、store / journal / projection を変えずに revertibility と `would_*` effects を返す。`1.8.24` で `revert-event --include-dependents` は後続 active same-page reversible events を SQLite `event_sequence` 逆順で先に revert してから requested target を revert する。`1.8.25` で `revert-events` は明示された複数 active SQLite events を reverse `event_sequence` order で同じ transaction 内に戻す。`1.8.26` で `revert-plan --scope log-batch` は anchor event を含む log-batch work unit を前後の `log_append` 境界から read-only に推定し、candidate / excluded / reverse order / suggested `revert-events` args を返す。`1.8.27` で `revert-plan --scope same-page-dependents` は log-batch 境界なしで anchor と後続 active same-page reversible events を read-only に候補化する。`1.8.28` で `revert-plan --scope event-window` は semantic boundary が無い小さな multi-page 連続 `event_sequence` window を明示的に候補化する。`1.8.29` で `revert-plan --scope time-burst --max-gap-seconds` は explicit temporal gap で隣接 multi-page events を read-only に候補化し、非 anchor `log_append` 境界を越えない。`1.8.30` で global `--actor` / `--session-id` は SQLite event metadata に入り、`revert-plan --scope session` は同一 non-empty session の multi-page events を read-only に候補化する。`1.8.31` で `revert-plan --scope subject-log` は広すぎる log-batch を closing log subjects で絞り、matching page events と closing log を read-only に候補化する。`1.8.32` で `revert-plan --scope log-page-subjects` は closing log entry が `log.md` の `page_update` として入った履歴から、新規 log lines の subjects に一致する page events と closing log page update を read-only に候補化する。`1.8.33` で `revert-plan --scope content-subjects` は anchor event の changed lines から subjects を抽出し、changed subjects / event target overlap で page events を read-only に候補化する。`1.8.34` で content-subjects / log-page-subjects の initial adopt baseline は実作業の `write-page --create` を除外しなくなった。`1.8.35` で `content-subjects` は changed-line subject が無い場合に anchor target を fallback subject にできる。`1.8.39` で repo-local postwrite guard は latest event の session marker を検査し、通常 file-back が `revert-plan --scope session` の材料を残すことを要求する。`1.8.40` で repo-local preflight guard は session id の再利用を検査し、同じ session id が複数 file-back を束ねる gap を防ぐ。`1.8.43` で repo-local preflight guard は session/head/base を gitignored preflight stamp に記録し、postwrite guard が同じ stamp の session/head/base 一致を検査するようになった。`1.8.44` で repo-local write-start guard は preflight 後・最初の write command 直前に projection / stamp / store status を import なしで検査するようになった。`1.8.45` で repo-local guard は default store/output pair と temp store + temp output の混在を止めるようになった。未実装は native events からの broader semantic page files projection と、log-batch / subject-log / log-page-subjects / content-subjects / version-bump / same-page / explicit event-window / time-burst / session boundaries を使えない semantic multi-page work-unit inference。将来 projection drift / review command が必要なら `projection-diff` / `check-projection` など目的が読める名前で新設する。
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
- general `write`: 任意更新と edge 自動更新（felt-sense と come-from で別経路）。append-only alpha の `append-section` / `append-log`、full-page replacement alpha の `write-page`、新規 Markdown page 作成 alpha の `write-page --create --path <file.md>` は実装済み。
- `rename`: Markdown-backed `rename-page` alpha は page id を保ち、旧 title を alias にして incoming `[[旧名]]` の surface text を書き換えない（`1.7.15`）。rename identity を `id` / `title` / `aliases` frontmatter として projection し、direct re-import 後も page id と旧名 alias を保つ（`1.7.16`）。実 git history の `why-design-B` → `why-not-scrapbox-clone` rename replay test で、旧 surface link が書き換えなしに解決され direct re-import 後も残ることを確認（`1.7.17`）。実 git history の `0db1449` page create + multi-page update replay test で、新規 plan page 作成と既存3 page 更新が replay/direct re-import clean になることを確認（`1.7.18`）。`1.7.31` で identity frontmatter 更新時に既存の任意 frontmatter metadata を保持する merge も実装済み。`1.7.32` で `3eaab75` source digest policy correction の既存6ページ横断 update も replay/direct re-import clean にした。`1.7.33` で `3eaab75` → `3605e05` の連続 commit page_update replay も同じ journal 上で clean にした。`1.7.34` で連続 replay harness を表駆動にし、`7360053` → `8278069` の handle ambiguity sequence も同じ test で clean にした。`1.7.35` で同 harness を `create_pages` + `update_paths` の mixed operation table にし、`0db1449` → `a07f1af` の fast-path plan create + later update sequence も clean にした。`1.7.36` で同 harness に `rename_pages` を足し、`d4e4c39` の `why-design-B` → `why-not-scrapbox-clone` rename invariant も continuous table で確認した。`1.7.37` で `revert_events` を足し、`0db1449` の fast-path plan page_create を同じ step 内で revert する sequence も clean にした。`1.7.38` で title / current file stem から導出できない旧名 alias がある場合は projection frontmatter を生成するようにし、`write-page --create` → `rename-page` → fresh `import --markdown` でも旧 `[[...]]` backlink が red 化しない regression test を追加した。`1.8.3` で rename state update と SQLite `events` row insert は同じ transaction に畳んだ。`1.8.62` で `3eaab75` の既存6ページ横断 `page_update` を適用後、`grasp-backlog.md` の `page_update` だけを revert する実履歴 regression も追加した。`1.8.63` で rename の projection export failure rollback は旧 projection file を削除する前に新 projection export を試すようにし、export 失敗時に SQLite は戻っているが旧 Markdown file が消える gap を塞いだ。`1.8.64` で export が途中 file まで書いてから後続 file の path/read error で失敗し、SQLite rollback 後も先行 Markdown projection だけ新内容で残る gap を塞いだ。`1.8.65` で page_create / page_rename revert の不要 projection file 削除も export 成功後に移し、revert export failure が既存 projection file を先に消す gap を塞いだ。未実装はさらに広い履歴 corpus から見つかる具体的な recovery gap。
- `transclude`: line-id を使った行参照。
- `export-markdown`: stored lines preserving projection と `--check` no-op gate は実装済み（`1.7.10`）。`append-section` / `append-log` 後の projection export も実装済み（`1.7.11`）。`write-diff` は `1.7.12` で current filesystem -> stored projection の unified diff として追加されたが、SQLite SSoT milestone では目的が曖昧になったため `1.8.8` で削除済み。no-op / drift check は `export-markdown --check` / `write-status --strict` が担う。`--regenerate-index` / `--regenerate-log` の明示 alpha overlay で primary index/log の最小 regeneration は実装済み（`1.7.21`）。`1.8.11` で JSON result に `projection_policy` を追加し、projection authority / base / output role / write mode / generated overlays を検査できるようにした。`1.8.19` で `--regenerate-log` は SQLite events を既定 source にし、partial stream は log page `page_update` / `page_rename` を seed にできる。`1.8.20` で repo-local postwrite はその semantic generated log projection を default guard に含め、`1.8.21` で `write-status` も native status / strict failure として返すようになった。`1.8.64` で write mode の export は全対象を読み取って変更/missing を判定し、書き込み先 path を preflight してから実 file write に入るようになった。未実装は native events 由来 projection の本格 policy、必要が具体化した場合の目的名付き review surface。
- status / rollback or revert event: append/log/page_update/page_rename alpha 用の `write-status` / `revert-event` は実装済み（`1.7.12`-`1.7.15`）。`write-diff` は目的が曖昧なため `1.8.8` で削除済み。page_create revert も実装済み（`1.7.19`）。projection export 失敗時は target event を残した上で自動 `event_revert` を append し、store を戻す（`1.7.20`）。`1.8.5` で SQLite-sourced `revert-event` は SQLite event stream から target を読み、state revert と `event_revert` row を同じ transaction に残す。`1.8.9` で projection export failure rollback も state revert と SQLite `event_revert` insert を同じ transaction に残す。`1.8.22` で projection export failure rollback は `--json` stderr に `projection_export_rollback` diagnostic を返し、no-journal path でも target/rollback event id と元 error を検査できるようにした。`1.8.23` で `revert-event --dry-run` は可逆/不可逆と理由を mutation なしで返すようになった。`1.8.24` で `revert-event --include-dependents` は同一 page の後続 active reversible events を含めて mutation するようになった。`1.8.25` で `revert-events` は複数の明示 target events を1つの SQLite transaction で reverse `event_sequence` order に戻す。`1.8.26` で `revert-plan --scope log-batch` は log-batch 境界から inferred work unit と reverse revert order を mutation なしで返す。`1.8.27` で `revert-plan --scope same-page-dependents` は同一 page の dependency-aware revert plan を mutation なしで返す。`1.8.28` で `revert-plan --scope event-window` は明示された bounded multi-page event_sequence window を mutation なしで返す。`1.8.29` で `revert-plan --scope time-burst` は明示された temporal gap 内の multi-page burst を mutation なしで返す。`1.8.30` で `revert-plan --scope session` は明示された session metadata の multi-page work unit を mutation なしで返す。`1.8.31` で `revert-plan --scope subject-log` は closing log subjects による multi-page work unit を mutation なしで返す。`1.8.32` で `revert-plan --scope log-page-subjects` は direct log page update の追加 log subjects による multi-page work unit を mutation なしで返す。`1.8.33` で `revert-plan --scope content-subjects` は changed content subject overlap による multi-page work unit を mutation なしで返す。`1.8.34` で initial adopt baseline の page_create 誤除外を塞ぎ、`1.8.35` で changed-line subject が無い anchor でも target fallback で content-subjects planning できる。`1.8.65` で actual revert 系 command は projection export 成功後に不要 projection file を削除する順序へ揃えた。`1.8.66` で actual revert 後の projection finalization failure も `--json` diagnostic として返すようにし、`1.8.67` で legacy/ad hoc `--journal` の append 不可能 path は mutation 前に `journal_append_preflight_failed` として拒否するようにし、`1.8.68` で既存 regular journal file の write permission と missing path の parent permission も同 preflight に含め、`1.8.69` で既存 journal JSONL の parse / schema validation も mutation 前 preflight に含めた。未実装は log-batch / subject-log / log-page-subjects / content-subjects / same-page / explicit event-window / time-burst / session boundaries を使えない semantic multi-page SQLite authority revert planning。
- aliases / page-id policy（page id を「いつ・誰が・どの意味判断で」振るか）。
- stable line-id policy（下記 stable line identity 参照）。
- durable journal policy: 方向は [[sqlite-write-concurrency]] / [[sqlite-ssot-write-plan]] で **SQLite primary + events table** に決めた。canonical store helper、events table、JSONL import、actor/session metadata columns、`adopt-markdown` initial events、`write-page` / `append-section` / `append-log` / `rename-page` / SQLite-sourced `revert-event` / projection export failure rollback / projection rollback diagnostics / `revert-event --dry-run` planning / `revert-event --include-dependents` / `revert-events` / `revert-plan --scope log-batch` / `revert-plan --scope same-page-dependents` / `revert-plan --scope event-window` / `revert-plan --scope time-burst` / `revert-plan --scope session` / `revert-plan --scope subject-log` / `revert-plan --scope log-page-subjects` / `revert-plan --scope content-subjects` with baseline hardening, anchor-target fallback, and same-page dependent closure / new-or-updated `import-log-records` の SQLite events 書き込み、`write-status` の SQLite event summary と legacy JSONL mismatch guard、SQLite-sourced `log-records` / `history`、write/status と repo-local pre/postwrite checker の no-journal default、repo file-back の `--no-journal` default cutover、runbook drift checker、no-journal default の3連続 dogfood、tracked `wiki.grasp/events.jsonl` の退役・削除、`export-markdown --regenerate-log` の SQLite events default、postwrite の semantic log projection default guard、preflight の session id uniqueness guard と current-upstream default base、push ownership guard、preflight stamp guard、write-start guard、store/output pair guard、`write-status` の semantic log projection native status / strict failure は実装済み。未実装は log-batch / subject-log / log-page-subjects / content-subjects / same-page / explicit event-window / time-burst / session boundaries を使えない semantic multi-page work-unit inference、必要が具体化した場合の generated Markdown backup/review policy。`write-diff` recovery surface は目的が曖昧なため `1.8.8` で削除済み。`--journal` / `--with-journal` は legacy/ad hoc CLI audit 用としてだけ残る。
- **parallel agent write / push guard**: [[llm-wiki-infra-fast-path-plan]] の初期計画は single writer 前提で、複数 agent が同じ `main` / `wiki.grasp/events.jsonl` / `wiki/` projection に書く場合の規定が薄かった。preflight guard は current upstream（なければ `origin/main`）との差分、unexpected dirty wiki path / retired JSONL path 再作成、未使用 session id、gitignored preflight stamp による write 開始時 session/head/base optimistic check、default store/output pair と temp store + temp output の混在禁止を検査するところまで実装済み。write-start guard は preflight 後・最初の write command 直前に projection / stamp / store status と store/output pair を import なしで再確認する。postwrite guard も同じ pair を確認する。push ownership guard は dirty worktree、behind branch、通常 ship-loop からの protected branch push を止めるところまで実装済み。guard が落ちたら isolated worktree へ誘導する。残る未実装はこの guard 群ではなく、semantic multi-page work-unit inference と generated Markdown backup/review policy 側。
- journal JSONL event type contract は `grasp.journal` で固定済み（`1.7.9`）。`adopt-markdown` は `page_create` events を append する（`1.7.10`）。`append-section` / `append-log` は `section_append` / `log_append` events を append する（`1.7.11`）。`revert-event` は `event_revert` を append する（`1.7.12`）。`replay-journal` は `page_create` / `page_update` / `page_rename` / append / revert events から Markdown projection を strict replay する（`1.7.13`-`1.7.20`）。`revert-event --dry-run` と `revert-plan` は `event_revert` を append しない read-only planning surface として実装済み。`revert-event --include-dependents` と `revert-events` は actual path で複数の SQLite `event_revert` rows を同じ transaction に書き、compatibility journal が有効な時は対応する複数の `event_revert` events を append する。未実装は log-batch / subject-log / log-page-subjects / content-subjects / same-page / explicit event-window / time-burst / session boundaries を使えない semantic multi-page work-unit inference。
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

- 2026-06-26 の前処理として、`line_window.around_line_id` / search context window は `page.id:line-index` を再合成せず stored `lines.line_id` を返すようにした（`1.7.8`）。ただし import 時の mint はまだ positional であり、stable line identity / journal replay は未実装。
- local write は既存 line を id で編集し、移動しても id を維持する。
- 外部 source（Cosense export / Markdown mirror）に line id が無ければ初回 import 時に grasp が mint し、identity journal に保持する。
- sync / reimport は旧新 lines を diff し、同一と判定できる line だけ id を引き継ぐ。挿入は新 id、削除は tombstone。split / merge / 重複行 / 大幅編集の曖昧一致は自動同一視しない。

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

`grasp sync` の basic upsert は実装済み（[[incremental-sync]]）。未実装:

- **full manifest reconcile**: `listPages` pagination で remote `id/title/updated/linesCount/linked/views` manifest を取り、local page id set と比較する。recent updated window だけでは拾えない古い missing page / delete / rename を拾う。
- **hosted 側で削除された page の tombstone / local delete detection**: remote manifest から消えた local `id` を tombstone 化し、physical delete とは分ける。認証済み path では `/api/deleted-pages/:project/:pageId` と `/api/stream/:project` の `page.delete` event を補助に使えるか検証する。
- **rename detection**: same page `id` / changed title を rename と見なし、旧 title を alias history に残す。`followRename=true` は fetch 時 workaround であり、rename history 取得ではない。認証済み path では `/api/commits/:project/:pageId` の `TitleChange` で履歴を補えるか検証する。
- **hosted REST metadata enrichment**: `readPage` / `/api/pages/:project/:title` で得られる `commitId`、stable `lines[].id`、`links` / `projectLinks` / `icons`、`linked`、`pageRank`、`accessed`、`relatedPages` をどこまで store に保存するか決める。JSON export seed には無いので optional source-specific columns として扱う。
- **stable hosted line-id policy**: 現行 sync は hosted `lines[].id` を捨て `page.id:line-index` を維持する。hosted edit / line fragment 連携を考えるなら `external_line_id` と local stable `line_id` を別列にする。
- **last-sync cursor の運用精度**: pinned pages / updated ties / clock skew / partial failure の扱い。

## Cross-project graph を first-class edge に + whole-store retrieval

決定は [[whole-store-graph-and-cross-project-edges]]。store = 外部 source から再生成可能な projection なので、実装時点の next schema generation に bump して理想形に作り直す（`recover_store_from_import_cache` 機構で再 import は安全）。当初は「v6 decision」と呼んだが、実際の schema v6/v7 は Markdown identity/name collision work で消費済みなので、今後は schema 番号でなく **whole-store cross-project** として扱う。現状の parse-on-read `cross_project_refs`（`LIKE '%[/%'` 全スキャン + 毎回 re-parse、edge にならない）を置換する。実装項目:

- **cross-project link を materialize**: `cross-project-spread` / `cross-project-spreads` は schema-compatible な観測 pre-step として実装済みだが、edge ではない。次は `edges` に `target_project` / `link_kind`（internal / cross-semantic / cross-icon / cross-root）を追加、`source_project` へ rename。`CrossProjectLink`（`raw/project/title/target_class`）を流し、`raw` 保存で slash-in-title を再解決可能に。
- **解決と unresolved 再構築**: `[/P/T]` を (P, norm(T)) に解決し、存在チェックを target_project の pages に対して行う。`unresolved_targets` を `(target_project, target_norm)` で集計。materialized page 0 の namespace も unresolved の値に取れる。
- **whole-store default retrieval**: `_require_project` の「複数 project で error」を削除。`search` / `read` / `backlinks` / `related` / `path` / `unresolved` / `mentions` / `co-links` / `gather` は default 全 project、`--project` で絞り、結果は project ラベル付き。`import` / `sync` / `acquire` は project-targeted のまま。
- **read 多義の disambiguation**: 同名 page が複数 namespace にある時 error せず、全候補を project ラベル + summary で返し `--project` / page-id で絞らせる。
- **node 状態 = page 単位の materialized / referenced-only**: project は namespace、「未取得 project」は categorical でなく coverage（materialized page 数）の派生量。acquire = referenced-only node の materialize。`unresolved`(whole-store) が「参照済みだが未取得の知識圏」を link_count 順で出し acquire の seed bibliography になる（[[cross-project-reference-acquire-2026-06-24]] の手作業を primitive 化）。
- **同名 bare 赤リンクの cross-project 統合**: 別 project の同名 bare 赤リンク `[X]`（どの namespace でも未 materialize）を normalize title の project 非依存 key で1ノードに束ねる。materialized page は (project, id) のまま、統合は赤 node だけ。「全 project を通じて誰も本文を書いていないが皆が指す概念ハブ」= project ごとに別 Scrapbox の Cosense が出せない value。誤接続（同綴り別概念）は受容し provenance で後判別（decision point 7）。
- **接続の強弱**: `edges` に `connection_strength`（strong = 人間が書いた明示リンク intra `[X]` / explicit `[/P/T]` / weak = grasp が normalize title の cross-project 一致で推論した接続＝著者が書いていない AI 向けヒント）。bare 赤 `[X]` が他 project の materialized X に解決するのも weak。誤接続は weak 層に閉じ authored グラフを汚さない＝strength が point 7 の誤接続リスクの封じ込め機構。retrieval は strength を label し weak を strong より下に rank。`link_kind` や typed/directional 軸とは直交（decision point 8）。
- **出力契約**: discover-broad-filter-post-hoc。relevance で pre-filter せず target_project / link_kind / connection_strength / scope ラベル付きで surface、絞りは post-hoc flag、出力量は rank + omitted-count で bound、性能は bound で対処し hide しない。現 `cross_project_refs` の `--semantic-only` / `--exclude-icons` / `--include-self` は pre-filter から post-hoc filter に位置づけ直す。
- **history**: store format / materialized index semantics が変わるため [[history]] の `x` を進める（再 import 要）。

未決（decision の Open Questions）: referenced-only namespace の coverage rollup surface 形 / slash-in-title 確定規則の実データ検証 / dense graph での whole-store related/path bound / weak 接続の rank・閾値調整と同綴り別概念の誤接続頻度の dogfood / link 同一判定の表記ゆれ吸収（`yyyy/MM/dd`⇄`yyyy-MM-dd` 等、[[scrapbubble]]）。

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
- `readPage` の hosted line id を採用するか（現行は export/sync と同じく grasp 側で `page.id:line-index` を維持）。
- partial corpus で `sync` する時、seed predicate 外の recently updated page を取り込むか、acquisition mode ごとに sync 動詞を分けるか。
- direct public API fallback を入れる場合、Scrapbox API と cosense-cli の metadata / auth / rate limit / search semantics の差をどこまで surface に出すか。

## Packaging and distribution

実装言語と配布チャネルの軸は [[language-and-distribution]]（当面 Python + pipx）。未実装:

- PyPI 公開時の package 名確認。
- `pipx install` 前提の配布導線。
- user-level Skill symlink と package install の統合。
- Python 不可 agent 環境が現実化した場合の native binary 配布。
