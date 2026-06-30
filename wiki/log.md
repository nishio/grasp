# Log

## [2026-06-28 08:17] implementation+file-back | `history` に current projection target を追加
- code: `history <query>` が `current_state_target` を返し、current page handle 解決を `resolved_unique` / `ambiguous` / `unresolved` / `unavailable` で明示するようにした。unique なら `read --page-id <id>`、ambiguous なら候補ごとの `read_args` / `read_command`、journal-only fallback なら `unavailable` を返す。text 出力にも target status と候補を出す。
- tests: SQLite source の resolved target、alias collision の ambiguous target、missing store journal fallback の unavailable target を CLI regression で固定。schema は v8 のまま、public compatibility version は `1.8.61`。
- file back: [[history]] / [[grasp-v1-implemented]] / [[grasp-backlog]] / [[sqlite-ssot-write-plan]] を更新し、stale-log guard の current projection pointer backlog は実装済みに移した。

## [2026-06-28 08:04] implementation+file-back | `history` / `log-records` を event stream として明示
- code: `log-records` / `history` の JSON result に `result_mode=event-stream`、`current_state=false`、`current_state_hint`、`staleness_signals[]` を追加し、text formatter も同じ header を出すようにした。`history <query>` は current projection の読み先として `read <query>` を hint する。
- tests: SQLite events 優先の `history` / `log-records` test で JSON/text の mode/current-state fields を検査。schema は v8 のまま、public compatibility version は `1.8.60`。
- file back: [[history]] / [[grasp-v1-implemented]] / [[grasp-backlog]] / [[sqlite-ssot-write-plan]] を更新し、log entry import record は過去 transition event であって現在状態ではない、という stale-log guard の実装済み部分を current facts へ移した。

## [2026-06-27 13:37] implementation+file back | `append-section` / `append-log` を SQLite state+event 1 transaction に移行
- code: `SQLiteStore.append_markdown_lines_with_event()` を追加し、append lines update と SQLite `events` row insert を同じ `BEGIN IMMEDIATE` transaction で commit するようにした。CLI `append-section` / `append-log` はこの helper を使う。既存互換のため legacy `events.jsonl` append と Markdown projection export は継続。
- tests: CLI append が SQLite events table に `section_append` / `log_append` を残すこと、duplicate event id で SQLite event insert が失敗した時に appended lines が rollback されることを追加。`python3 -m unittest discover -s tests` は 113 tests OK。
- file back: [[history]] / [[grasp-v1-implemented]] / [[sqlite-ssot-write-plan]] / [[grasp-backlog]] を更新。public compatibility version は `1.8.2`、schema は v8 のまま。次は `rename-page` と SQLite events 由来 recovery。

## [2026-06-27 13:34] file back | [[ai-agent-implementation-experiment]] を新設し、grasp を AI agent 実装実験として説明
- [[ai-agent-implementation-experiment]]: 初見エンジニア向けに、local graph store と AI agent による継続的実装 dogfood の二重性を整理。
- index.md concepts 表へ追加。write-first は current main に対して page_create → index page_update → append-log の順で実行。

## [2026-06-27 13:28] implementation+file back | `write-page` を SQLite state+event 1 transaction に移行
- code: `SQLiteStore.write_markdown_page_with_event()` を追加し、`write-page` / `write-page --create` が Markdown page state update と SQLite `events` row insert を同じ `BEGIN IMMEDIATE` transaction で commit するようにした。既存互換のため legacy `events.jsonl` append と Markdown projection export は継続。
- tests: CLI `write-page --create` が SQLite events table に `page_create` を残すこと、duplicate event id で SQLite event insert が失敗した時に page state が rollback されることを追加。`python3 -m unittest discover -s tests` は 112 tests OK。
- file back: [[history]] / [[grasp-v1-implemented]] / [[sqlite-ssot-write-plan]] / [[grasp-backlog]] を更新。public compatibility version は `1.8.1`、schema は v8 のまま。次は `append-section` / `append-log` / `rename-page` と SQLite events 由来 recovery。

## [2026-06-27 13:18] implementation+file back | SQLite SSoT Phase 2 events table と JSONL migration helper
- code: SQLite schema を v8 に上げ、`events` table（`event_sequence` / `event_id` / `event_type` / `project` / `created_at` / `actor` / `session_id` / `payload_json`）を追加。`SQLiteStore.import_journal_events()` は legacy JSONL path または event dict list を duplicate skip / project filter 付きで SQLite events に移行し、`events()` / `event_count()` は selected project・明示 project・event type で query する。
- tests: schema v8 events table、in-memory event import + duplicate skip + filter、JSONL path import + cross-project query を追加。`python3 -m unittest discover -s tests` は 111 tests OK。
- file back: [[history]] / [[grasp-v1-implemented]] / [[sqlite-ssot-write-plan]] / [[grasp-backlog]] を更新。public compatibility version は `1.8.0`、schema は v8。既存 write command の state+event 1 transaction 化と SQLite events 由来 recovery surface は未実装で、次 slice。

## [2026-06-27 12:44] implementation | SQLite SSoT Phase 0 contract + Phase 1 write transaction substrate
- [[sqlite-ssot-write-plan]] に Phase 0 authority contract を固定: repo-local `.grasp/authority.sqlite`（`$GRASP_CANONICAL_STORE` override）が authoring SSoT default、`wiki/` は git-tracked projection/recovery snapshot、`wiki.grasp/events.jsonl` は legacy audit/migration input、`.grasp/authority.sqlite` 自体は現時点では git tracked にしない。
- code: `canonical_store_path()`、write connection setup（WAL / busy_timeout / `synchronous=NORMAL`）、`sqlite_write_transaction()`（`BEGIN IMMEDIATE` + commit/rollback）を追加。CLI は store 更新系 command を write-configured connection で開く。
- tests: canonical path、WAL/busy_timeout、commit/rollback、2 writer lock contention を追加。events table / JSONL migration / command-level state+event atomic migration は次 slice。public compatibility version は `1.7.39`、schema は v7 のまま。

## [2026-06-27 11:48] implementation | alias-only projection frontmatter を出し、write-page-create→rename→fresh import の旧名 red 化を修正
- `markdown_projection_frontmatter_fields` が `id` / `title` の推論可否だけを見ており、有意味な `aliases` だけが durable 化を必要とする case で frontmatter を出していなかった。これにより `write-page --create` で path stem と title が異なる title==H1 page を作り、`rename-page` で H1 を新 title に更新すると、fresh `import --markdown` 後に旧 title alias が失われ `[[旧名]]` が red 化しうる。
- projection 条件を修正し、title / current file stem から導出できない alias がある場合は `id` / `title` / `aliases` frontmatter を生成するようにした。title と current file stem は fresh import で復元できるため projection 管理 fields から除外する。
- regression test: `write-page --create` → `rename-page` → fresh `import --markdown` 後も旧 title alias が新 page id / title に解決し、backlink が残ることを確認。public compatibility version は `1.7.38`、schema は v7 のまま。

## [2026-06-27 11:08] file back | [[sqlite-ssot-write-plan]] を新設し、旧 fast-path 計画を superseded と明示
- [[llm-wiki-infra-fast-path-plan]] は `1.7.x` alpha / replay harness の履歴として残すが、現行の次実装順ではないと先頭に明記。`events.jsonl` を強化して file-back cutover へ進む前提と、`import --markdown` を通常 reconcile にする前提は使わない。
- 新規 [[sqlite-ssot-write-plan]] を current implementation plan として追加。SQLite を canonical SSoT、events を SQLite table、Markdown を export-only projection にし、canonical store / WAL+busy_timeout / 1 transaction write / native recovery を先に作ってから file-back cutover する phase に整理。
- [[grasp-backlog]] と index を更新し、durable journal policy は SQLite primary + events table 方向決定済み、未実装は store 永続場所・既存 JSONL migration・generated Markdown backup/review policy・actor/session metadata とした。

## [2026-06-27 10:51] file back | sqlite-write-concurrency §Updates — 使い捨て store は store≠authority の症状、SSoT 化が構成上 throwaway を消す（cutover は3点）
- store を捨てて作り直せるのは cache だから。store=authority にすると唯一コピーになり単一 canonical 永続 store にならざるを得ない（read 用 default store は既存）
- cutover 残作業は (1) write path を canonical store 経由化+WAL/busy_timeout (2) events を SQLite テーブル化し write を1 tx に (3) export 一方向化、の3つ

## [2026-06-27 02:31] file back | sqlite-write-concurrency §Updates + native-authority §Updates — SQLite を本体/SSoT に・journal も SQLite 内へ（nishio 方向）
- 方向: SQLite=SSoT、journal も SQLite 内（events テーブル）、Markdown は必要時に吐く projection（= option D）。DB の write serialization が並行を source で防ぐ唯一の形
- git-diff 喪失は受容（event journal は詳細すぎて人間 review 対象でない）。但し incident を救った『素の git ファイルを手 reconcile』脱出口を失うので grasp-native recovery で置換が cutover 条件

## [2026-06-27 02:06] file back | sqlite-write-concurrency — SQLite レイヤーの並行書き込み設計を考察・保存（3層 authority / DB ロックは store 1層のみ / 対策候補）
- write path 3層: journal jsonl=authority / store sqlite=派生キャッシュ（--store ごと別ファイル・非共有）/ projection md=authority。lock/busy_timeout/WAL は package 全体に皆無
- 「SQLite は write でロック取るのでは？」→ DB 全体ロックで直列化はするが store 1層だけ。authority は SQLite 外・整合単位は import→export の論理 RMW・cross-store atomicity 無しで不十分
- Co-（多人数）を削いでも multi-process single-owner の並行は残る。2026-06-26 incident が実例。対策候補=write.lock / compare-and-append journal / staleness check / journal+store を1 SQLite に畳む

## [2026-06-27 11:35] file back+reconcile | parallel agent write branch を merge せず current main へ fresh grasp write
- `codex/fileback-parallel-agent-writes` の SQLite store は `.grasp/` で gitignored なので merge 対象ではなかった。一方、branch の `wiki.grasp/events.jsonl` を Git merge するだけでは journal replay が clean にならないことを temp worktree で確認。
- current `main` も direct patch 由来の page create / update が journal replay authority に未反映だったため、先に current projection を退避し、journal replay store へ current pages を `page_create` / `page_update` として再記録して `replay-journal --check` clean に戻した。
- その後、[[llm-wiki-infra-fast-path-plan]] / [[grasp-backlog]] / `AGENTS.md` に parallel agent write / push guard を追加し、[[parallel-agent-write-incident-2026-06-26]] を新規 entity として作成。Git merge ではなく current main を基準に fresh `grasp write` で入れ直した。

## [2026-06-27 11:20] file back | [[ai-author-feedback-2026-06-26]] §Updates2 — rename-page を sandbox 実走、title==H1 page で alias durability が落ちる dogfood flag
- 差別化核 rename-page を sandbox（throwaway store/journal、共有不触、実行後 rm -rf）で直接検証。**graph では参照保存が効く**: page_id 保持・旧/新 handle とも解決・backlinks 生存・H1 自動更新。回復 toolkit も実在: `revert-event` で単発 undo を in-tool に完結（前 Updates「回復は git に降りた」は単発 undo には不要だった）、`write-diff`=drift 検出、`replay-journal`=journal-authored page のみ再生成。
- **だが alpha の穴を repro 特定**: `write-page --create` が `id/title/aliases` frontmatter を注入するのは **title≠H1 の時だけ**。実 wiki page は規約上 title==H1（grep で id/aliases frontmatter 皆無を確認）。∴ 通常 page を rename→`heading_updated` で title==H1 のまま→旧名が projection に残らず、fresh `import --markdown` で `[[旧名]]` が **red 化**・backlink 喪失。対照で title≠H1 page は `aliases:[旧名]` が残り解決。`export-markdown --check` は ok のまま（**silent**、fresh re-import でのみ顕在化＝read 面 absence-hallucination の write 版）。
- backlog L87 の「1.7.16-17/1.7.36 で direct re-import でも alias 保持」と食い違う → **断定でなく Codex への調査 flag**（境界仮説: harness が test するのは replay-journal path で、本 repro の失敗は import-markdown path / default H1 更新）。自分が前 log で書いた「reconcile は import-markdown」手順が rename 跨ぎで silent に壊す点も訂正、identity authority は journal へ（[[native-authority-markdown-projection]] を強化）。
- 統合: [[ai-author-feedback-2026-06-26]] §Updates2 追記 + [[grasp-backlog]] rename bullet に flag + index 行に Updates 注記。tree clean 確認済み、自分の hunk のみ commit。

## [2026-06-27 00:00] file back | [[ai-author-feedback-2026-06-26]] §Updates — 共有 journal を live 実走した並行下 failure mode（sandbox 実走の対）
- 既存ページ本文は sandbox（隔離 store、共有 journal 不可触）だが、そこが friction 1/5 で引く「並行 session」が私。私は共有 `wiki.grasp/events.jsonl` と本番 `wiki/` に live で write した一次体験を §Updates に追加。
- sandbox が隔離ゆえ原理的に出せない並行下 failure mode 4点: ①**stale store × export 副作用**で他 session の page が untracked 蘇生（22:54 固定 store の `append-log` export が `value-is-problem-solving-not-novelty.md` を再 materialize）②**write-status は divergence を出すが出所を言わない**（`strict_ok:false` が自分由来か他 writer 由来か in-band 不可分＝trust 信号が並行下で劣化）③**append-log placement gotcha**（newest-first log の末尾寄りに entry、成功だが意味的に誤り）④**回復は grasp でなく git 層**（pathspec commit / `checkout HEAD -- events.jsonl` / amend）。
- meta: 本ページ結論「不確実下の AI は共有 write path を避ける」が live で裏付き。追補＝confidence コストは upfront（--help）だけでなく **ongoing**（並行可能性下は各 write op 後に git 検証が固定費化）。最小解候補に **write 前の store-vs-wiki staleness check** を追加。
- write 方式: 本ページ自身の規約どおり direct Markdown patch（race は収束していたが、ページの結論と一貫させ共有 journal を再び触らない）。

## [2026-06-26 23:40] file back | [[ai-author-feedback-2026-06-26]] — AI が write 面（alpha write path）を sandbox 実走した体験
- 前 session の fallback 理由「新規 page+frontmatter+index 表は alpha write が表現できない」を sandbox（throwaway store/journal）実走で検証 → **ほぼ誤り**だった: `write-page --create` は frontmatter を verbatim 保持し `id/title/aliases` を注入（identity-without-name を file に materialize）、body の `[[positioning-two-personas]]` を edge 化（direct Markdown では得られない value）、`append-section`/`append-log` 込み3 write op を通して `export-markdown --check` は ok:true。capability は在った。
- 真の friction（capability でなく ergonomics）: ①構造化 arg ⇄ markdown blob mismatch（append-section=heading+line / append-log=op+summary、`--from-file` 不可。並行 file-back の発見: append-section は既存同名 heading に merge せず EOF 二重作成）②arg 必須 surprise（write-status は `--output`）③title/H1/filename が別物 ④index 行に `write-index` 無く write-page と direct 編集が混在（cutover 未完）⑤共有 journal が lock-free で並行 writer 下は serial-execution を安全に満たせない。
- **meta**: AI が write path を避ける決定因は correctness でなく **confidence 獲得コスト + 並行安全性**。下げる候補=atomic file-back command / dry-run / index を純 projection 化 / journal lock。entity を [[ai-consumer-feedback-2026-06-23]] の write 面の対として新設、[[development-arc-retrieval-ahead-of-authoring]] の「authoring 未着手」を「実装済み・動く・残るは採用」と update。
- **本ページ自体の write 方式**: write-first 規約下だが再び direct Markdown（理由は前回と違い**正しい**＝実走中も並行 session が共有 log/journal を触り lock-free で serial-execution を安全に満たせない＝friction 5）。前回の「frontmatter capability」理由は撤回。sandbox は実行後 `rm -rf` 済み、共有 store/journal は不触。

## [2026-06-26 23:08] file back | [[value-is-problem-solving-not-novelty]] — grasp の設計核は既存研究の再導出、価値は新規性でなく問題解決
- 親 llm-wiki での「grasp と既存知識管理論文」考察を grasp 側 positioning concept として file back。設計核の大半は既存ハイパーテキスト/PKM 研究の再導出（recall を link から剥がす=Halasz "Seven Issues" 争点① search&query / ページ＝投影=Halasz virtual structures / come-from gather=Nelson transclusion を read 時計算で実装し Scrapbox の拒絶理由を回避 / 型 bottom-up 昇格=Trigg TEXTNET 75型失敗の回避 / graph≠triple=Wu et al. PVLDB2026 L2情報完全性）。
- positioning の歯止め3点: (1) 継承部分は prior art で de-risk 済み→速く作ってよい (2) 唯一未踏なのは消費者を token-bounded AI に替えたコスト関数（近傍同梱＝採餌コスト / absence の hallucination）でここだけ prior art が無い→慎重に自前設計 (3) **pitch の lede は「論文的に新規」でなく「目前の問題を解く local graph store」**、論文系譜は補助線で lede にしない。継承は A 型（論文を読んで作ったと誤読させない）。[[positioning-two-personas]] / [[ai-consumer-cost-and-trust]] / [[scrapbubble]] / [[development-arc-retrieval-ahead-of-authoring]] に接続。
- 統合: concepts/ 新規 + index.md concepts 表に1行。**write 方式**: `wiki.grasp/events.jsonl` がある（=grasp write-first 規約）が、新規 concept page + frontmatter(type/summary/sources) + index 表の行編集は alpha write 層が clean に表現できないため CLAUDE.md の direct Markdown patch fallback を採用（次の grasp-write session は `import --markdown wiki` で store を先に reconcile すること）。

## [2026-06-26 23:07] file back | 「grasp を読んで考察」session の net-new 2点を come-from / positioning に file back（親 llm-wiki にも対の file back）＋ append-section 二重 heading gotcha
- [[come-from-declared-gather]] §Updates: 束ねには2理由（substrate-限界 ∧ 人間労力-限界）。AI 著者化は後者を溶かす → unbundling は AI 著者で *より*安く synthesis 原理を強める。溶けない例外＝読者ケア（消費者が人間）。nishio の反論「それは人間前提の判断、こちらは AI が使う」の一段先。
- [[positioning-two-personas]] §Updates: grasp の価値は既存リンク密度に比例 → persona2（低密度 .md）は「逆リンク不在＝動機」と同時に「materialize する graph が薄い＝構造的逆風」。正直な pitch は density 非依存（[[read-vs-grep-benchmark-2026-06-24]] bounded-retrieval）側へ。
- 親 llm-wiki 側の対の file back: `graspは親llm-wikiの理論が数時間でコードになる-20260624` の留保「authoring 未着手＝良いリーダー止まり」を ground truth（1.5.23→1.7.34、write/journal/replay が main に landing 済み）で訂正。AI が 6/24 自己観察ページ本文を current state と誤読した実例（`状態想起はlog残行からするな` の snapshot ページ一般化）。
- 手順 gotcha: append-section は既存同名 `## Updates` に merge せず EOF に新規 heading を作る（come-from=Updates 無し→1、positioning=既存有り→二重）。CLAUDE.md 規約どおり direct patch で merge → 直列 `write-page --from-file` で journal 同期し export-markdown --check / lint clean を確認。

## [2026-06-25 00:08] file back | cross-project 接続に強弱（strong/weak）軸を追加（v6 決定の境界2点を解決）
- nishio が cross-project 統合の残る境界2点を決定: ①別 project に materialized X があれば、他 project の bare 赤 `[X]` はそれに解決する（「自 project だけでは得られない content を他から発見できる」）②赤ベースの接続は**弱い接続=AI 向けヒント**、人間が書いた明示リンクは**強い接続**。
- [[whole-store-graph-and-cross-project-edges]] に **point 8（接続強弱）** を追加。strong=authored（intra `[X]` / explicit `[/P/T]`）、weak=grasp が normalize title の cross-project 一致で推論。赤-materialized 解決も weak。**誤接続（同綴り別概念）は weak 層に閉じる**ので authored グラフを汚さない＝strength が point 7 の誤接続リスクの封じ込め機構。`edges.connection_strength` を schema に追加、retrieval は strength を label し weak を下に rank。`link_kind` や typed/directional 軸とは直交。
- 旧 Open Q の「赤-materialized 境界」「explicit `[/P/T]` 整合」は point 8 で解決。残るは weak の rank/閾値・誤接続頻度 dogfood・表記ゆれ吸収（[[scrapbubble]]）。backlog v6 spec・index 行も更新。
- PR #2 の merge で判明した運用 gotcha を AGENTS.md に追記。`gh` が無く HTTPS push もできない環境では、GitHub connector で PR merge 自体は成功する一方、local main 側に手元の別 merge commit / follow-up commit が残り、`origin/main` と `ahead/behind` に分岐しうる。
- 対応方針: connector merge 後は `git fetch origin main` → `git log --left-right --cherry-pick origin/main...main` で remote merge commit と local commit を照合する。重複 merge commit をそのまま push せず、必要なら remote merge commit を取り込んで follow-up だけを rebase/cherry-pick する。

## [2026-06-24 23:56] file back | 開発弧の非対称を「行動に移した」と概念へ追補 + 並行 main commit の運用 gotcha
- この session の未捕捉知見を file back。
- [[development-arc-retrieval-ahead-of-authoring]] に `## Updates` 追補: §3 の非対称（retrieval≫authoring）は観察で終わらず同じ弧の中で着手判断に変わった（write 層に alpha 着手 [[write-layer-alpha-and-replay-test]]）。nishio の問い「ローカルキャッシュの改良ばかりで書き込みが進まない／今後どうなるか」が持続メカニズムをあぶり出した＝retrieval は tight dogfood loop（hub 観察→同日 ship）を持つが write は各 session に重い open question しか出さないので後回しは構造的（default で retrieval が勝つ）、崩すには意図的決定が要る。決定は §3 Open Q（authoring で dogfood 駆動が効かないリスク）に replay test（authoring 専用 loop）＋cadence A（big-bang 回避）で直接答える。
- AGENTS.md 運用方針に gotcha 追記: 並行 session が同じ main を同時 commit すると `git add` 後に index がクリアされ HEAD が動く（実例: 本 session の versioning commit が一度空振り）。共有 main への commit は確定した自分のファイルだけ単一コマンドで atomic に add+commit し着地を検証、他 session の hunk は staging に混ぜない。


## [2026-06-24 23:46] file back | cross-project を first-class edge に / whole-store retrieval / 赤リンク統合（v6 決定）
- cross-project-refs を「v5 互換・parse-on-read」で足す方針を nishio が却下（「互換性を捨ててどうあるのが理想か。grasp はまだ SSoT が外にある検索 index に過ぎず破壊を恐れる必要はない」）。互換性を捨てた理想形を v6 decision 化。
- 新規 [[whole-store-graph-and-cross-project-edges]]（decisions/）: ①store=再生成可能 projection ゆえ schema 自由→v6 bump ②discover-broad-filter-post-hoc（pre-filter せず label 付きで surface、絞りは post-hoc、性能は bound で対処し hide しない）③`[/P/T]` を import 時に first-class edge へ materialize ④retrieval は whole-store default・`--project` は絞り込み・結果は project ラベル付き（merge せず labeling で誤読回避）⑤node 状態=page 単位の materialized/referenced-only、project=namespace、acquire=materialize ⑥read 多義は全候補返す ⑦**同名 bare 赤リンクを normalize title で project 横断統合**（nishio 判断、自信は低いが Cosense にない概念ハブ value を採る、tentative）。
- [[multi-project-store]] の2 clause（「cross link 作らない」「retrieval は selected project 内だけ」）を supersede。先行 tentative Update（villagepump 由来、赤リンク統合提案）は ⑦で収束、resolved page 分離 vs labeling は v6 が labeling を採用。
- backlog に v6 実装 spec 節、index に decision 行。lint: 孤立0/broken0/未登録0。実装は [[history]] の `x` bump（再 import 要）。残る境界 Q は decision の Open Questions。
- 「takker の経験から何が言えるか」の分析を distill して既存ページに追補（新規ページなし）。
- [[takker-opencode-villagepump-test-2026-06-24]] 含意を強い順に再構成: ①grasp はモデル水準を下げる（構造化出力を CLI が作り agent は薄い recipe→安いモデルで完走、[[delivery-cli-plus-skill]] 境界の正しさ）②意図した retrieval loop が外部 agent で自然発生（AI consumer option が理由を知らない agent に選ばれた）③scale 余裕は read のみ証明・path/gather 未証明 ④takker が向けたのは Co- corpus＝read には問題ないが write/identity の単一所有前提（[[write-layer-alpha-and-replay-test]]）と将来衝突する伏線 ⑤インサイダーは「offline cosense-cli」= Scrapbox/persona1 枠に入れる→persona2 framing 未検証。
- [[positioning-two-personas]] `## Updates` 追記: インサイダーは Scrapbox 枠 / モデル水準を下げる（persona2 GTM 追い風）/ 公開 dogfooding flywheel は高利回りだが persona1 止まり（PR #2 がその実例、別チャネルが要る）。
- [[grasp-backlog]] Parser fidelity の PR #2 一般化を原理化: admin metadata-ON export は in-the-wild の代表でない→外部 export は fuzz test→import 堅牢性は恒常コスト＝persona2 を狙う代償。tolerant import + 実 export variant を fixture 化。
- 並行で Codex が PR #2 merge（1.5.24）・v6 decision [[whole-store-graph-and-cross-project-edges]] を追加済み。takker entity の PR #2 status は merged に揃っている。自分の hunk だけ commit。

## [2026-06-24 23:29] implementation | PR #2 を mergeし Cosense string line import を許容
- GitHub PR #2（takker99 `fix/string-lines-cosense-import`, `f139c516`）を review し、ローカル main に merge。`grasp/cosense.py` は Cosense JSON export の line が plain string の場合、metadata なし本文行（created/updated/user_id = `None`）として import する。string line 内の `[B]` なども通常通り edge 抽出対象。
- 回帰テスト `tests/test_cosense.py::CosenseStoreTests.test_store_imports_plain_string_lines_without_metadata` を追加。`python3` が system 3.9 だと既存 `requires-python >=3.10` / union type 構文で失敗するため、検証は Codex bundled Python 3.12 を使用。
- public compatibility version を `1.5.24` に bump。store schema は v5 のまま。[[grasp-v1-implemented]] / [[history]] / [[cosense-json-export]] / [[grasp-backlog]] / [[takker-opencode-villagepump-test-2026-06-24]] / README に反映。

## [2026-06-24 23:28] decision | write line の versioning を合意 — メジャー 2 = authoring line / alpha は SLA ラベル / cadence A
- nishio の問い「write系完了まで worktree で並行開発 → merge の段階で 2.x.y にする感じ?」を起点に合意形成。3点を file back。
- ①メジャー `2` = 「grasp が write/authoring line を持つ」。read-only(`1`)→read+write は本プロジェクト最大の概念変化（[[development-arc-retrieval-ahead-of-authoring]]）なので store-compat 台帳のメジャーで標す。②alpha/stable は version 番号に載せず、write 系 verb の SLA ラベルで表す（決定1の read=stable/write=alpha 別 SLA をそのまま使う）→ `2.0.0` は alpha ラベル付き write verb が載る最初の line。③cadence A: worktree 並行は最高リスクスライス（① stable identity ② rename）が replay test を通るまで、そこで merge して `2.0.0` 境界、以降 `2.x.y`。big-bang merge を避ける（authoring が tight dogfood loop を失う罠を回避、決定1 で隔離の安全上の必要も消えた）。
- [[write-layer-alpha-and-replay-test]] に Updates 追記＋ Open Q #4 を解決、[[history]] の Versioning policy に「major=product line / alpha=SLA ラベル / 2.0.0 境界」を追記。
- worktree `feat/write-identity-alpha` を main に fast-forward して Codex の context を最新化。


## [2026-06-24 23:21] ingest | Scrapbox `villagepump/grasp` の公開設計対話 + takker 外部試用ログを取り込み
- 出典: https://scrapbox.io/villagepump/grasp （raw/grasp-villagepump-page_2026-06-24.txt に保存, gitignored）。既出と重複しない新規分のみ file back。
- 新ページ [[takker-opencode-villagepump-test-2026-06-24]]（entities/）: **nishio 以外の第三者による初の実走**。takker が OpenCode + Deepseek v4 flash で bare 指示「このリポジトリを設定して」から self-setup → `villagepump.json`（43,742 pages / 1,454,430 lines / 413,605 edges / 171,316 unresolved ≈ nishio store の pages 1.7x・lines 2x）を import → グラフ理論 / リンク構造 / カテゴリ論争の多ターン retrieval を完走。確認3点: persona1 が nishio 固有でなく一般化 / cross-agent（OpenCode）・cross-model（Deepseek）portability / scale headroom。観測の主役は答えでなく `suggest→search(--context/--scope)→read(--related-snippets/--backlinks-limit)→related 辿り` のツール列＝read=近傍同梱 loop の実走証跡（nishio メタ観察「答えより LLM がどう使うかが重要」）。
- [[grasp-backlog]] Parser fidelity に PR #2 を記録: villagepump export の一部 line が dict でなく plain string（metadata なし）で importer が落ちた。takker 側 agent が修正し https://github.com/nishio/grasp/pull/2 （takker99, `fix/string-lines-cosense-import`）として提出 → **2026-06-24 時点 OPEN（未 merge）**。review/merge 後 [[grasp-v1-implemented]] import facts に反映。
- [[multi-project-store]] に `## Updates` 追記（tentative）: nishio 判断「異なる project の赤リンク（unresolved target）は接続する」。resolved page graph の namespace 分離（本 decision の核）は維持し、本文を持たない unresolved target に限って cross-project 接続を許す非対称。明示的に撤回ありの暫定方針。
- [[grasp-v1-implemented]] delivery に license=MIT を追記（LICENSE / pyproject、2026-06-24 追加。inajob の「土台にするので明記してほしい」要望対応、persona2 GTM 前提）。
- index.md entities/ に [[takker-opencode-villagepump-test-2026-06-24]] 1行追加。
- 既出につき再記録しないもの: 複数 project 対応 / Markdown folder import / read=近傍同梱 / gather・mentions・co-links / 25,792 pages count / parser の `#tag`・数字 link edge 化（すべて [[grasp-v1-implemented]] / [[grasp-backlog]] に既載）。

## [2026-06-24 23:09] decision | write/identity 層に着手 — alpha testing 位置づけ・過去 wiki 編集 replay でテスト・最高リスク先行

- nishio 指示2点: ①「当面書き込み機能は alpha testing と位置付ける。信用してここに大事なものを預ける人は自己責任。テスト方法はこのリポジトリの過去の wiki 編集を grasp で同様にやれるかとする」②「実装順序は最もリスクが高いものの検証を先にすべき」。これを言語化して Codex が読む context に固定した。
- 新 decision [[write-layer-alpha-and-replay-test]]（decisions/）: ①位置づけ＝write は alpha、read(v1 stable)/write(alpha) を別 SLA、原典(Cosense export / Markdown mirror)は書き換えず local store に対して write し re-import 安全網を write 対象の外に残す。②テスト方法＝この repo 自身の git history（page 作成/rename/本文編集/リンク変更の実列、既に markdown mirror dogfood corpus）を ground truth に、連続 revision の diff を grasp write/rename で適用し「素朴 import との一致」＋「rename で `[[..]]` 参照不壊・redirect stub なし・参照文保存」を実データで検証（[[use-case-experiment-as-outcome-story]] の authoring 版）。③実装順序＝危険な順: stable identity + re-import diff（最高リスク, stable ID requires memory）→ rename → write → transclude/come-from。
- [[grasp-backlog]]「Local write and identity layer」冒頭に着手判断と decision 参照を追記、未実装リストを「楽な順でなく危険な順に読む」と明示。index に decision 行追加。
- 背景は [[development-arc-retrieval-ahead-of-authoring]]（retrieval≫authoring の非対称）。差別化核 identity-without-name（[[why-not-scrapbox-clone]] / [[positioning-two-personas]]）の write 半分を埋めにいく。
- 次: 本 wiki を main に固定後、`feat/write-identity-alpha` worktree を切り Codex が①から実装。判明した制約は file back。

## [2026-06-24 22:40] file back | 「MD 全読み vs grep vs grasp search」速度比較を実測 → 速度は非論点・token が論点
- nishio の問い「大規模 MD を読むのと grep の速度比較」を本番コーパス（store project `nishio`, 25,798 pages）で実測。全行を flat MD（53.2MB ≈ 14M token, `/tmp/nishio_flat.md`）に dump し、cat / `grep -n` / `python3 -m grasp search` を `/usr/bin/time` で計測。
- 結論が反転: ①ディスク wall-clock は3手法とも sub-second（cat 0.02s / grep 0.3s / grasp 0.25–0.75s）で**論点でない**。効くのは context に入る token 量で、MD 全読みは ~14M token = 1M window の14倍で**そもそも入らない**。②grep vs grasp は速度でなく出力規律の差（grep 無制限: `民主主義` 1 クエリ 498KB≈125K token / grasp bounded 7–14KB）。③∴ grasp の対 grep 優位は「速さ」では立証できず「同等 wall-clock で bounded・ranked・structured」が立つ。
- 新ページ [[read-vs-grep-benchmark-2026-06-24]]（entities/, 日付つき実測 dogfood ジャンル）。[[ai-consumer-cost-and-trust]] に `## Updates` で軸1（round-trip/token 経済）の実測裏付けとして反映。index.md entities/ に1行追加。caveat: token は bytes/4 概算（日本語は実際もっと多く「全読み不可」は強まる向き）/ grasp は cold start 込み（[[language-and-distribution]] warm 値参照）。

## [2026-06-24 22:10] file back | 開発弧の自己観察を concept 化（retrieval 厚く authoring 未着手）
- 親 llm-wiki での「最近の grasp 開発を観察して考察」session の成果を grasp 側へ file back。新ページ [[development-arc-retrieval-ahead-of-authoring]]（concepts/）。
- 主張3点: ①2日 87 commits の速度は「層を分けて束ねを解く」単一原理の再適用ゆえ（[[why-not-scrapbox-clone]]/[[come-from-declared-gather]]/[[cosense-delite-howm-synthesis]]/[[delivery-cli-plus-skill]] が同じ手）。②[[history]] の x/y store-compat 規律は本番 dogfooding の帰結（parser 変更=「意味が違う」になる）。③retrieval は厚いが差別化核の authoring（id-link write / come-from declare・render）は全部 [[grasp-backlog]] 未着手＝次の山。
- index.md concepts/ に1行追加。親側 file back は llm-wiki `analyses/graspは親llm-wikiの理論が数時間でコードになる-20260624`（親子の数時間ループ観点はあちら）。
- 既存ページとの非重複: [[cosense-delite-howm-synthesis]] は製品組成、本ページは開発弧。current facts は [[grasp-v1-implemented]] / [[grasp-backlog]] を参照（重複させない）。

## [2026-06-24 21:58] implementation | acquire の取得条件・日時範囲記録と未更新ページ reuse を追加
- `grasp acquire` が acquisition criteria fingerprint / candidate updated range / page manifest を store metadata に保存するようにした。同じ criteria で再実行した時、hosted metadata の `updated` と前回 manifest / local page が一致するページは `readPage` せず local store から再利用する。
- JSON/text に `remote_fetched` / `reused` / `same_criteria_as_previous` を追加し、`stats` の Acquisition 節でも criteria fingerprint と updated range を確認できるようにした。updated metadata が無い search/seed 由来候補は stale 回避のため従来通り読む。
- 検証: `python3 -m unittest tests/test_cosense_cli.py` OK。

## [2026-06-24 21:58] lint | wiki lint clean
- `python3 scripts/lint_wiki.py` を実行。broken wikilink / 未登録 / frontmatter 不備はいずれも 0。

## [2026-06-24 21:49] implementation | cross-project-acquire の取得後 summary を拡張
- `cross-project-acquire` の successful project row に `reciprocal_refs` と `top_internal_links` を追加。取得した `<project>:semantic` slice 内で source project へ戻る `[/source/...]` refs と、partial corpus 内の上位 internal link targets を bounded に返す。
- `SQLiteStore.cross_project_refs_to()` と `SQLiteStore.top_internal_links()` を追加。どちらも既存 lines/edges を読む summary primitive で、store schema は v5 のまま。
- public compatibility version は `1.5.22`。README / Skill / current facts / backlog / cross-project dogfood entity / outcome-story concept を更新した。

## [2026-06-24 21:26] implementation | cross-project-acquire を追加
- `cross-project-acquire` command を追加。選択中 source project の `cross-project-refs --semantic-only` 相当の seed titles から、複数 target project を `<project>:semantic` namespace に順次 partial acquire する。
- `--dry-run` で plan のみ確認可能。実行結果は target project ごとの status / fetched / failed / skipped_nonpersistent / diagnostic / page_sample / failed_page_sample を bounded summary として返し、full acquire payload は返さない。
- public compatibility version は `1.5.21`。store schema は v5 のまま。README / Skill / current facts / backlog / cross-project dogfood entity / outcome-story concept を更新した。

## [2026-06-24 20:47] implementation | acquire fetch failure diagnostics を追加
- `acquire` の page fetch failure に `failed_pages[].error_class` を追加し、全 candidate fetch 失敗時は `diagnostic.type=all_failed` / `severity=warning` / `next_actions[]` を返すようにした。`cosense` symlink は存在するが shebang の `env node` が失敗する case は `command-env` に分類する。
- text output でも Diagnostic 節を出し、空の partial corpus を成功結果として誤読しにくくした。exit code は partial acquisition report として従来通り 0。
- public compatibility version は `1.5.20`。current facts / history / backlog / cross-project dogfood entity / README / Skill を更新した。

## [2026-06-24 20:26] implementation | cross-project-refs seed preflight を追加
- `cross-project-refs` に seed preflight を追加。各 target project に semantic `seed_titles` / `seed_candidates` / `acquire_recipe` を返し、`--seed-dir <folder>` 指定時は project 別 seed file を書いて runnable `grasp --project <project>:semantic acquire <url> --seed-file <file> --limit N` command を出す。
- `--seed-limit` / `--project-url-base` / `--acquire-limit` を追加。通常の extraction は read-only のまま、seed file 書き込みは明示 option の時だけ。
- public compatibility version は `1.5.19`。current facts / history / backlog / cross-project dogfood entity / README / Skill を更新した。

## [2026-06-24 19:30] implementation | cross-project-refs を追加
- `cross-project-refs` command を追加。保存済み行テキストから Cosense shorthand `[/project/page]` を parsed link target として抽出し、semantic / icon / project-root / self-project に分類して target project ごとに rank する。既定では self-project refs を除外し、`--semantic-only` で `.icon` / project root / self-project を落とした acquisition seed 向け view を返す。
- 通常 internal edge parser / materialized graph は変えず、schema v5 compatible の extraction primitive として実装。`search "[/"` + one-off script の gap は解消し、残るのは seed-file generation / acquire preflight、cosense/node diagnostics、all-failed acquisition warning、direct public API fallback。
- public compatibility version は `1.5.18`。current facts は [[grasp-v1-implemented]]、残課題は [[grasp-backlog]] と [[cross-project-reference-acquire-2026-06-24]] に反映した。

## [2026-06-24 18:47] file back | icon-history report 化の観察
- `villagepump` `[nishio.icon]` raw 抽出を `nishio in villagepump: 公開共同日記から見る grasp 前史 30 scene` へ再構成した過程の学びを [[use-case-experiment-as-outcome-story]] に追記。
- 核: 抽出と report composition は別工程。CLI は raw dump でなく、icon hit kind 分類、年/月 counts、theme counts、代表候補、hosted line id / snippet 付き provenance を返し、agent/report layer がユーザ言語で bounded narrative artifact を書くのがよい。
- [[grasp-backlog]] に `use-case report composition（icon/person history）` を追加。仮 surface は `grasp report icon-history ...` だが、重要なのは command 名ではなく `slice acquisition -> hit classification -> representative candidate bundle -> agent-authored report` の標準 workflow。

## [2026-06-24 18:46] file back | `search` は parsed link classifier ではない
- `[/` cross-project 実験の follow-up として、現行 `grasp search` だけでは `.icon` refs を link target として除外できないことを記録。`search "[/ AND NOT .icon" --mode boolean --scope line` は line-level lexical workaround で、同じ行の semantic link まで落とし、root refs は残り、複数 target の分類もできない。
- [[cross-project-reference-acquire-2026-06-24]] に、target-aware extraction が必要という process observation を追記。[[grasp-backlog]] には `cross-project-refs` / `links --cross-project --classify-targets` 相当の parsed link extraction surface を候補化。
- 教訓: outcome が parsed links に依存する use-case では、text search を本命 surface として扱わず、検索→外部 script の gap を product gap として明示する。

## [2026-06-24 18:19] file back | ユースケース実験は outcome story として記録する
- nishio feedback「ユースケース実験はユーザがこういうことをしたらこうなります、という事例で、いい感じの結果になることが好ましい」を [[use-case-experiment-as-outcome-story]] に concept 化。
- 核: use-case dogfood は gotcha / 未実装発見だけでなく、ユーザの自然な依頼から有用で再利用可能な結果が得られるかを評価する。file back では outcome story、friction/backlog、quality judgement を分けて残す。
- `villagepump` 抽出は到達として成功だが、raw artifact 中心・broad `[nishio.icon]` literal 抽出のため outcome story としてはまだ弱い。author marker / mention / reaction icon list の分類、bounded summary、custom script 非依存の再現 surface が「いい感じ」にする次候補。
- 追記: [[cross-project-reference-acquire-2026-06-24]] は outcome story としては強い。`/nishio` の `[/project/page]` refs を seed bibliography として使い、semantic refs 上位 project を acquire して AI/Cosense/Plurality/熟議/人物辞書の周辺 map を作れる。ただし one-off script / `cosense` PATH wrapper は product gap。

## [2026-06-24 17:36] file back | `villagepump` 日記ページ抽出 dogfood
- public `https://scrapbox.io/villagepump/` の `YYYY/MM/DD` 日記ページ（2020-10-09..2026-06-24）2,079 pages から `[nishio.icon]` を含む block を抽出。結果は raw artifact として 1,481 hit pages / 6,488 paragraphs / 19,134 lines、failed 0。
- `grasp acquire` は `cosense` binary が PATH に無く使えなかった。一方 Scrapbox public API は `pages?sort=title` と page body API で読めた。`search/query?q=[nishio.icon]` は 100 件固定で `skip` が効かなかったため、網羅抽出は title list -> date filter -> page body fetch が必要。
- [[grasp-backlog]] の hosted acquisition 節へ、`cosense-cli` 依存なしの direct public API fallback を候補として追記。

## [2026-06-24 17:31] file back | `/nishio` cross-project refs acquire dogfood
- `/nishio` snapshot の `[/` shorthand を抽出し、other-project refs 4,141 mentions / 183 projects、`.icon` と root refs を除く semantic refs 2,222 mentions / 142 projects と実測した。
- semantic refs 上位 12 project から最大 20 page ずつ seed 取得し、task-local `/tmp/grasp-cross-project.sqlite` に 8 project / 140 pages を partial acquire。主クラスタは AI x Cosense / Plurality・熟議 / Cosense 設計哲学 / public project operation / MITOU 人物辞書。
- gotcha: raw `[/` は `.icon` refs が大きく混ざるため seed 生成前に semantic/icon/root 分類が必要。`cosense` symlink は存在しても PATH に `node` が無いと shebang で exit 127 になる。`grasp acquire` は全 seed failed でも exit 0 で partial result を返すため、agent-facing warning が欲しい。
- 記録: [[cross-project-reference-acquire-2026-06-24]]。残課題は [[grasp-backlog]] の hosted acquisition 節へ追記。

## [2026-06-24 16:27] implementation | co-links に slice/raw rank と target_relation を追加
- `co-links` に `--rank slice|raw` を追加。既定 `slice` は target title 自体が query を含む `query-containing-title` を後ろへ回し、独立した `slice-handle` を先に出す。`raw` は従来の line/page count order。
- 各 co-link item に `target_relation` / `target_relation_rank` を追加し、`gather` は `co_link_rank_mode: slice` を明示する。
- store schema は v5 のまま、public compatibility version は `1.5.17`。current facts は [[grasp-v1-implemented]]、KJ法 dogfood の残課題は [[grasp-backlog]] と [[kj-link-hub-audit-2026-06-24]] に整理した。
- 検証: `python3 -m unittest discover -s tests` OK（43 tests）、`python3 scripts/lint_wiki.py` OK、skill validator OK、`git diff --check` OK。

## [2026-06-24 16:08] file back | Cosense / デライト / howm を grasp と照らした3ツール合成論
- nishio 依頼で Cosense・デライト・howm の UX を列挙し grasp と照合した対話を file back。原理ページ [[cosense-delite-howm-synthesis]] を新規作成。
- 核: grasp は Scrapbox 一本の clone でなく、3ツールから**別々の核を1軸ずつ**抜いた合成。Cosense=グラフモデル / デライト=identity-without-name（知番）/ howm=「ページ＝投影」と come-from。3ツールの弱点は全部「本来別々の仕事を1つの仕掛けに束ねた」に帰着し、grasp の一貫した手は層分離で束ねを解く（Cosense は `[X]` に4仕事、デライトは意味を独自語彙に、howm は retrieval を人間の Emacs 操作に）。捨てたもの: 多人数協調編集 / 独自語彙 / 時間駆動リマインダ。
- backlog 反映（nishio 指摘）: デライトの**引き入れ**（多重所属）は「前景/後景」の向き付き包含が乗った **typed link**（親 llm-wiki `型付きリンク` の構造型）。"Local write and identity layer" に `### typed / directional link` 節を追加。felt-sense / come-from の2型に直交する「型を持たせるか」軸、向き×無向グラフの両立、著者宣言 vs AI 自動推定を論点に。
- 用語方針（nishio feedback）: ページは coding-agent 向け source of truth なので、内部 shorthand（"Co-" / "design A/B"）を裸で使わず、本ページでは「多人数リアルタイム協調編集」「Scrapbox に欠けている層を足したあるべき姿」と明示し、[[why-not-scrapbox-clone]] への pointer に留めた。
- 統合: concepts/ 新ページ + grasp-backlog.md 1節追記 + index.md concepts に1行 + come-from-declared-gather.md 関連に被リンク1本（新ページの孤立回避）。

## [2026-06-24 16:03] implementation | gather omitted rows と come-from 候補 score を追加
- `mentions` summary に `come_from_candidate` を追加。bare occurrence/page spread、unlinked-page、query shape から score / thresholds / signals / rationale を返す初期 heuristic。多義語や AI 作ページ判定は確定しない。
- `gather` に `returned_counts` / `total_counts` / `omitted_counts` / `row_count_basis` を追加。counts は mentions=bare mention lines、co_links=ranked co-link targets、backlinks=incoming link rows の row 単位で、token omitted count ではない。
- store schema は v5 のまま、public compatibility version は `1.5.16`。current facts は [[grasp-v1-implemented]]、残課題は [[grasp-backlog]] に整理した。
- 検証: `python3 -m unittest discover -s tests` OK（43 tests）、`python3 scripts/lint_wiki.py` OK、skill validator OK、`git diff --check` OK。

## [2026-06-24 14:57] file back | gather KJ法 dogfood の co-link ranking caveat
- `grasp gather KJ法 --budget 1500 --json` を `1.5.13` 系実装後の nishio store で dogfood した観測を [[kj-link-hub-audit-2026-06-24]] に追記。huge-hub banner、151 exact links / 144 pages、681 literal pages、519 bare pages、page status counts が出た。
- 重要な caveat: `mentions` summary は all literal lines 基準なので body-only audit の 490 bare pages とは別指標。default summary は 519 bare pages。
- `co-links` の上位は `KJ法 渾沌をして語らしめる` / `KJ法勉強会@ロフトワーク` など query-containing bibliographic / session / title pages が先に出た。raw fidelity としては正しいが、narrower use-slice handle を見たい時には broad query-containing title の分類・filter・weighting が必要。[[grasp-backlog]] に残課題として追記。

## [2026-06-24 12:56] implementation | mentions に unlinked filter を追加
- `mentions --unlinked` を追加。既定 bare-only は維持し、`--unlinked` では page に query-containing link target が無い `unlinked-page` の bare mention 行だけを返す。
- summary は従来通り全 literal hit の total / bare / linked occurrence と page status counts を保持し、`mentions[]` と `returned_lines` だけを filter 後の値にする。
- store schema は v5 のまま、public compatibility version は `1.5.15`。current facts は [[grasp-v1-implemented]]、backlog の `mentions --unlinked` surface gap は実装済みに移した。
- 検証: `python3 -m unittest discover -s tests` OK（43 tests）、`python3 scripts/lint_wiki.py` OK、skill validator OK。

## [2026-06-24 12:52] implementation | related snippet に edge mode を追加
- `read --related-snippets --related-snippet-mode edge` を追加。従来の先頭行 snippet（`lead`）は既定のまま維持し、`edge` では related/source item を導いたリンク行を中心に `snippet_lines[]` を返す。
- JSON では `snippet_mode` と `snippet_window` を返す。text 出力では edge mode の根拠 line-id と target を `snippet: edge ...` として表示する。
- store schema は v5 のまま、public compatibility version は `1.5.14`。current facts は [[grasp-v1-implemented]]、backlog の「該当行モード」は実装済みに移した。
- 検証: `python3 -m unittest discover -s tests` OK（43 tests）、`python3 scripts/lint_wiki.py` OK、skill validator OK。

## [2026-06-24 12:32] implementation | mentions / co-links / gather 初期 surface を追加
- `mentions <query>` を追加。literal query の occurrence を parsed internal-link span 内/外に分け、既定では bare mention 行だけ返す。summary は total / bare / linked occurrence、bare line/page、page status counts を返し、各行を `exact-link-page` / `query-link-page` / `unlinked-page` に分類する。`--include-linked` と `--context N` あり。
- `co-links <query>` を追加。query を含む行で同時に出る internal links を target ごとに rank し、link_count / line_count / source_page_count / examples を返す。exact query target は既定で除外し、`--include-self` で含められる。
- `gather <query>` 初期版を追加。link stats、bare mention summary、representative mentions、co-link slices、backlinks、次に実行する recipe を bounded bundle として返す。`--budget` は厳密 token packing ではなく row limit selector。huge hub では bulk-linking を避ける banner を返す。
- store schema は v5 のまま、public compatibility version は `1.5.13`。current facts は [[grasp-v1-implemented]]、残課題（正規化 index、AI default 裸 / come-from 昇格 scoring、厳密 token packing）は [[grasp-backlog]] に残した。

## [2026-06-24 03:55] file back | come-from（宣言された用語単位の gather）を設計に取り込み
- 親 llm-wiki の 2026-06-24 設計対話（link overloading → grasp-最適）から grasp に効く部分を取り込んだ。背景厚めの原理ページ [[come-from-declared-gather]] を新規作成。
- 核の言語化: リンクには4仕事（recall / attention / navigation / **読者ケア**）があり、Cosense は substrate が他チャネルを持たないため全部を1つの `[X]` に束ねる。これが [[kj-link-hub-audit-2026-06-24]] の exact 144 → bare 490 の根。原因は **per-occurrence 局所判断 × 双方向 → hub という大域帰結のレベルミスマッチ**（誰も hub を作ろうと決めていない、親切な個別 `[KJ法]` の副作用で創発）。
- come-from（howm 由来）は判断単位を出現→用語に上げ、判断と帰結を用語-大域で揃える。「この語は一般に伝わりにくい」の1判断で全出現が読者に親切。read 側は grasp `mentions`（＝nishio 2022 howm 考察「キーワードページ＝仮想出現一覧」）で既に体現、declare 層と render 層（Markdown mirror で裸出現を自動リンク化）が未実装。
- backlog 反映: (1) `gather` 節に hub 膨張の why（レベルミスマッチ）と come-from declare/render 候補、`mentions --unlinked` の3分類化（(a)意図的 / (b)gap / (c)**AI 作 default 裸**＝`🌀KJ法` 266occ は AI 作）＋ come-from 昇格候補（uncommon×頻度×一意）。(2) "Local write and identity layer" に **リンク2型を別 first-class object に**（felt-sense=行キー / come-from=用語キー）要件。安全域＝必要域（uncommon≈一意）。
- decision 反映: [[ai-consumer-cost-and-trust]] に `## Updates` で第3消費者軸（substrate を持たない公開人間読者。読者ケアは AI 2軸モデルの外。公開面を frozen にすると届かない。come-from-at-render が軽量機構。grasp scope 判断点は nishio）。
- 親 llm-wiki 側の対応ページ: `come-fromリンクは1宣言で全出現を親切にする` / `grasp最適設計はlinkからrecallを剥がす-20260624` / `KJ法リンクハブはリンク密度でなく用法分解で扱う-20260624`。
- 統合: concepts/ 新ページ + grasp-backlog.md 2節追記 + ai-consumer-cost-and-trust.md Updates + index.md concepts に1行 + kj-link-hub-audit へ相互リンク（"wrong direction" の why を come-from へ前方参照、監査ページの outgoing 0 を解消）。

## [2026-06-24 02:38] file back | peek に line offset を追加
- `peek --line-offset N` を追加し、`--line-limit M` と組み合わせて本文行だけをページングできるようにした。既定 offset は 0。
- JSON は `line_offset`, `lines_truncated_before`, `lines_truncated_after` を返す。互換用の `lines_truncated` は後方省略（`lines_truncated_after`）と同じ値を維持する。text 出力は前方/後方省略を `...` で表示し、offset 指定時は `line_offset: N` を出す。
- [[grasp-v1-implemented]] / [[history]] / [[grasp-backlog]] / README / skill を更新し、version は schema `5` compatible の `1.5.12` に上げた。
- 検証: `python3 -m unittest discover -s tests` OK（42 tests）、`python3 scripts/lint_wiki.py` OK、skill validator OK。

## [2026-06-24 02:36] file back | KJ法 hub の desired state を明文化
- [[kj-link-hub-audit-2026-06-24]] に、改善後の姿を「`[KJ法]` を増やす」ではなく **root link + 用途別 slice handle** に分岐することとして追記した。
- 具体例: `[KJ法]` は KJ法そのもの・川喜田二郎・原理・全体像に残し、通常言及は `表札づくり` / `グループ編成` / `考える花火` / `Kozaneba` / `探検ネット` / `AIにKJ法を教える` へ逃がす。本文の `KJ法` は bare text のままでよく、link は後で読みたい retrieval handle に付ける。
- [[grasp-backlog]] の `gather` 候補に success contract を追加: huge hub banner、exact / bare mention counts、top co-link slices、unlinked mention candidates、`co-links` / `mentions --unlinked` recipes、AI clustering handoff 用 bounded rows を返す。

## [2026-06-24 02:30] file back | search hit に bounded context を同梱
- `search --context N` を追加し、検索 semantics は literal / boolean / scope とも既存のまま、返却 hit に前後 N 行の `context_lines[]` と `context_window` を同梱する形にした。
- text 出力では hit 直下に `context: lines A-B` と周辺行を表示する。JSON では `context` top-level と per-hit context fields を返す。既定 `context=0` では既存 hit に context fields を付けない。
- [[grasp-v1-implemented]] / [[history]] / [[grasp-backlog]] / README / skill を更新し、version は schema `5` compatible の `1.5.11` に上げた。
- 検証: `python3 -m unittest discover -s tests` OK（41 tests）、`python3 scripts/lint_wiki.py` OK、skill validator OK。

## [2026-06-24 02:22] file back | KJ法 hub audit を記録し、bare mention / co-link slice を backlog 化
- nishio の相談「KJ法 が 100+ backlink で広すぎ、リンクにしないで KJ法 とだけ書くケースもある」を受け、`~/.grasp/grasp.sqlite` project `nishio` を `sync` 後に実測。
- 結果: exact `[KJ法]` は 151 links / 144 pages。一方 literal `KJ法` は 681 pages / 2,333 lines / 2,765 occurrences、internal-link span 外の bare `KJ法` は 519 pages / 1,866 lines / 2,246 occurrences、body bare mention は 490 pages / 1,777 lines / 2,156 occurrences。body bare mention があるが exact `[KJ法]` が無い page は 415、`KJ法` 系 link target が一切無い page は 339。
- 判断: 全部を `[KJ法]` にリンク化すると hub を悪化させる。`[KJ法]` は root / representative link とし、通常言及は `表札づくり` / `グループ編成` / `考える花火` / `Kozaneba` / `探検ネット` / `こざね法` など subtopic link に逃がす方がよい。
- [[kj-link-hub-audit-2026-06-24]] を追加。[[grasp-backlog]] に `mentions` / `search --mentions --link-gap`、`co-links`、`gather` の huge hub handling を未実装候補として追記。`--cluster` 却下は維持しつつ、`KJ法` が「rare だが load-bearing な hub」実例であると補正。

## [2026-06-24 02:21] file back | PR #1 Markdown mirror を main に merge
- GitHub PR #1 `feat/read-only-markdown-mirror`（read-only Markdown mirror import）は draft / conflict 状態だったため、PR worktree で `origin/main` を merge し conflict を解消した。解消 commit は `bf206bf`。
- conflict は version/current facts/log まわりで、package version と [[history]] の current version は `1.5.10` に統合した。`import --markdown` と `read --around-line` の両 surface を保持。
- GitHub 上で PR を ready 化し、head SHA `bf206bf3ef6665bb96132c151fa65892add04886` 固定で merge。merge commit は `2a3972d`。`/Users/nishio/grasp` の `main` worktree は `origin/main` に fast-forward 済み。
- 検証: conflict 解消前に PR worktree で `python3 -m unittest discover -s tests` OK（39 tests; sqlite ResourceWarning 1件）、`python3 scripts/lint_wiki.py` OK、`git diff --check --cached` OK。

## [2026-06-24 02:19] file back | log entry は current fact ではなく transition event
- nishio 指摘「A→B→C と変わった時に `B になった` log だけを見ると誤答する」を受け、[[markdown-obsidian-indexed-mirror]] の log/event stream 節に current-state projection と stale-log guard を追記。
- 判断: log entry は「その時点で起きた transition」であり、現在状態の主張ではない。現在状態は entity / decision / backlog などの current page、または event stream を fold して materialize した current projection から読む。
- query 方針: 既定の「今どうなっているか」は current state を読む。temporal / provenance query は event log を読む。log entry を返す時は同じ subject の later events を `superseded_by` / `later_events` として同梱し、中間状態を current fact と誤読させない。
- [[grasp-backlog]] に未実装項目を追加: log entry subject extraction、stale-log guard、`read` と `history` の surface 分離、current projection と provenance links の分離。

## [2026-06-24 02:18] file back | stable line ID は position と分離する
- nishio 指摘「行を挿入した瞬間に後続行の ID が変わる設計は良くない」を受け、[[why-not-scrapbox-clone]] / [[grasp-v1-implemented]] / [[grasp-backlog]] に反映。
- 判断: v1 の `page.id:line-index` は read-only snapshot 内の positional locator であり、write / transclude / 長期引用を跨ぐ安定 line identity ではない。current surface の「line-id」は歴史的呼称として残るが、identity 層では `line.id` と `line_index` を分ける。
- 方針: stable line id は opaque に mint し、store / identity journal に保持する。外部 source に line id が無い場合も deterministic hash / line index に逃げず、sync / reimport では diff で同一判定できる line だけ id を引き継ぐ。挿入は新 id、削除は tombstone、split / merge / 曖昧一致は自動同一視しない。
- 原則: **stable ID requires memory**。content hash は text=identity、line index は position=identity になり、identity-without-name の目的に反する。

## [2026-06-24 02:12] file back | LLM Wiki log を event stream として扱う判断を記録
- nishio の問い「LLM Wiki の `log.md` は並行エージェント衝突の話なのか」を受け、[[markdown-obsidian-indexed-mirror]] に `log.md` / `wiki/log/*.md` の扱いを追記。
- 判断: 並行 agent が1ファイルへ追記して conflict する問題は運用上の理由だが、grasp 側の本筋は **log entry を巨大 page 内 section でなく first-class event record として materialize すること**。
- 方針: 既存 `log.md` は header ごとに仮想 log-entry record へ split し、将来の record-per-file 形式も読む。log は search / provenance query 対象にはするが、既定の content graph edge / `related` / `path` の根拠ページとは分ける。
- [[grasp-backlog]] に未実装項目を追加: log split importer、record-per-file importer、entry id policy、log artifact の graph 除外、`grasp log` / `grasp history <page>`、人間向け `log.md` 生成 surface。

## [2026-06-24 02:08] file back | LLM Wiki index/navigation の grasp 境界を決定
- nishio の問い「LLM Wiki の index を grasp の中に入れるのか外に別の仕組みをつけるのか」を受け、[[markdown-obsidian-indexed-mirror]] に判断を追記。
- 決定: grasp に入れるのは pages / lines / content links / frontmatter summary などの substrate。`index.md` / `index.txt` / `forest-index.md` は通常の根拠ページでなく、store から生成できる projection / navigation layer として扱う。
- 理由: `index.md` を ordinary graph edge として混ぜると巨大 hub になり、`related` / `path` が「全部 index 経由で近い」と壊れる。親 llm-wiki の「index は複製でなく射影にする」診断、kouchou pattern、`探索の地図と事実の分離` と整合。
- [[grasp-backlog]] に未実装項目を追加: navigation artifact 分類、既定で navigation outgoing edges を content graph から除外、`--include-navigation` escape hatch、frontmatter summary からの catalog generation、wiki森 registry は外側 orchestration として保持。

## [2026-06-24 02:05] integration | Markdown mirror PR を main へ追従
- PR #1 `feat/read-only-markdown-mirror` が main の `1.5.8` / `1.5.9` 変更（line-id alias / `read --around-line`）と version 履歴で conflict したため、Markdown mirror series を final `1.5.10` として統合した。
- conflict は package version、[[history]]、[[grasp-v1-implemented]]、log の時系列だけ。実装 surface は `import --markdown` と `read --around-line` の両方を保持。
- 検証: `python3 -m unittest discover -s tests` OK（39 tests; ResourceWarning 1件は既存の unclosed sqlite warning）、`python3 scripts/lint_wiki.py` OK、`python3 -m py_compile grasp/cli.py grasp/sqlite_store.py` OK。

## [2026-06-24 01:58] implementation | read --around-line を追加
- `grasp read --around-line <line-id> --line-context N` を追加。完全 `line_id` から所属ページを解決し、中心行の前後 N 行だけを `lines[]` として返す。
- JSON は `line_window`（around_line_id / center_index / start_index / end_index / context / truncated_before / truncated_after）を返す。通常 read / missing target read では `line_window: null`。
- text 出力は line-id alias と連動し、`line_window: P1:12 (lines A-B, context N)` を表示する。local alias は入力には使えず、存在しない line-id の場合は `--json` / `--full-ids` の完全 ID を使うよう error で案内する。
- Skill の長大ページ手順を、`search --json` → 完全 `line_id` → `read --around-line` の流れに更新。store schema は v5 のまま、public compatibility version は `1.5.9`。検証: `python3 -m unittest discover -s tests` OK（29 tests）、`python3 scripts/lint_wiki.py` OK、`git diff --check` OK。

## [2026-06-24 01:49] implementation | text 出力の line-id をローカル別名化
- text 出力で `page-id:line-index` を既定で `P1:0` のような実行内ローカル別名に畳み、先頭付近に `line-id aliases: P1=<page-id>` legend を出すようにした。
- JSON は従来通り完全 `line_id` を返す。text で完全 ID が必要な場合は `--full-ids` を使う。`--full-ids` は root option だが、`--json` と同じく verb 後にも置ける hidden alias として受ける。
- 対象は `read` / `backlinks` / `related` / `path` / `link-stats` の recovery hints / `peek` / `search` / `unresolved` の text formatter。`export-ai` は本文 bundle なので対象外。
- store schema は v5 のまま、public compatibility version は `1.5.8`。検証: `python3 -m unittest discover -s tests` OK（28 tests）、`python3 scripts/lint_wiki.py` OK、`git diff --check` OK。

## [2026-06-24 01:45] implementation | Markdown mirror の manifest-based 差分 index
- `grasp import --markdown <folder>` が project metadata に Markdown manifest を保存するようにした。manifest は relative path ごとの content hash / mtime_ns / page id / title / aliases を持つ。
- 再 import 時、title / id / aliases / file set が不変で content hash だけ変わった file は page / lines / outgoing edges を差し替える。unresolved targets と project counts は再計算する。title / id / aliases / file set が変わった時は、他 file の alias 解決済み edges が変わりうるため safe full rebuild に戻す。
- JSON / text import output に `markdown_import.mode`, `changed_files`, `full_rebuild_reason` を追加。Dogfood: `wiki/` は 21 pages / 2086 lines / 249 edges / unresolved 0。旧 manifest 不在の1回目は `mode=full, reason=manifest_missing`、直後の2回目は `mode=incremental, changed_files=0`。
- store schema は v5 のまま。Markdown mirror series は main 追従後に public compatibility version `1.5.10` として release。alias-aware なより細かい差分 rebuild は [[grasp-backlog]] に残す。

## [2026-06-24 01:39] implementation | path no-path recovery hints を追加
- `grasp path <A> <B>` で端点は resolve できるが bounded search 内に経路が無い時、`recovery_hints.path` を返すようにした。
- JSON は `reason`（`no_path_within_max_depth` / `search_truncated`）、`next_max_depth`、両端の `link_stats`、`related`、`backlinks` を小さく同梱。text 出力は次に試す `path --max-depth N` / `related` / `backlinks` と候補データを表示する。
- これで negative-result contract は `read` / `link-stats` / `search` / `related` / `path no-path` まで揃った。`gather` など将来 verb は継続監査。
- store schema は v5 のまま、public compatibility version は `1.5.7`。検証: `python3 -m unittest discover -s tests` OK（27 tests）。

## [2026-06-24 01:12] implementation | Markdown frontmatter title / aliases / tags 対応
- Markdown mirror が frontmatter `title` / `id` / `aliases` / `tags` を読むようにした。`title` は canonical title、`id` は page id、`aliases` と file stem は title resolve 候補、`tags` は page から tag target への outgoing edge として扱う。
- `[[alias]]` は import 時に canonical title へ解決して edge 化し、store metadata の alias map により `read <alias>` / `backlinks <alias>` / `link-stats <alias>` でも canonical page を読める。
- Dogfood: `wiki/` は 21 pages / 2077 lines / 248 edges / unresolved 0。frontmatter の `sources: [[...]]` は従来通り本文行 link として edge 化され、バックティック参照は edge にならない。
- store schema は v5 のまま。Markdown mirror series は main 追従後に public compatibility version `1.5.10` として release。first H1 title resolution / Obsidian block refs は [[grasp-backlog]] に残す。

## [2026-06-24 00:58] implementation | read-only Markdown mirror の最小実装
- `grasp import --markdown <folder>` を追加。Markdown folder を既存 SQLite graph store に read-only mirror として materialize し、file stem を title、relative path hash を page id、`[[wikilink]]` / `#tag` を edge として扱う。
- `[[Page|alias]]`, `[[Page#Heading]]`, `[[folder/Page.md]]`, `![[Embed]]` は target title に畳んで edge 化する。inline backtick / fenced code block 内は edge にしないため、grasp wiki のバックティック親 llm-wiki 参照は graph に混ぜない。
- Dogfood: `python3 -m grasp --store /tmp/grasp-wiki.sqlite import --markdown wiki --project grasp-wiki` で `wiki/` を 21 pages / 2072 lines / 248 edges / unresolved 0 として index。`read markdown-obsidian-indexed-mirror` が backlinks 7 / related を返した。
- store schema は v5 のまま。Markdown mirror series は main 追従後に public compatibility version `1.5.10` として release。frontmatter title / aliases / Obsidian block refs / 差分 index は [[grasp-backlog]] に残す。

## [2026-06-24 00:56] implementation | search を default literal + explicit boolean/scope に変更
- nishio 指摘: 空白で query を刻んで AND 検索する既定は「クエリーを書けない人間向け」の interface で、英文 phrase を検索するなら既定は入力文字列通りの literal search が自然。AND / OR / NOT と行単位 / ページ単位を明示的に組み合わせられる方が良い。
- `grasp search <query>` の既定を、空白も含む literal line substring に戻した。literal 0件時の normalized fallback は維持。
- `--mode boolean` を追加。AND / OR / NOT、括弧、quoted phrase、隣接 term の implicit AND に対応。`--scope line|page` を追加し、式を同一行で評価するか同一ページ全体で評価するかを切り替える。旧「空白区切り page AND」は `--mode boolean --scope page "alpha beta"` で明示的に再現。
- dogfood: `search "KJ法 表札"` は既定 literal なので `(none)`、`search "KJ法 AND 表札" --mode boolean --scope page --limit 3` は `Scrapboxベストプラクティス` / `KJ法` の該当行を返した。
- store schema は v5 のまま、public compatibility version は `1.5.6`。検証: `python3 -m unittest discover -s tests` OK（27 tests）。

## [2026-06-24 00:33] implementation | `/ship-next` と Skill の日本語応答方針を反映
- nishio 指摘「日本語で(skillも更新しといて)」を受け、`.claude/commands/ship-next.md` の最終 summary / "what's next?" を日本語で返す運用に更新。
- `skills/grasp/SKILL.md` の回答形式に「ユーザの言語に合わせ、nishio/grasp の開発 wiki / ship loop は日本語 default」を追記。
- 併せて、Markdown mirror は未実装なので、この repo の `wiki/` を読む時に `grasp import --cosense` で folder を代用しないこと、将来 mirror では `[[...]]` を grasp 内 edge、バックティックのプレーン名を親 wiki 非 edge と扱うことを Skill / [[delivery-cli-plus-skill]] に反映。

## [2026-06-24 00:24] file back | grasp wiki 自身を Markdown mirror 層の最初の dogfood corpus にする動機 ＋ dual-link policy 論点を backlog に追記
- nishio 「いつかのタイミングでこのプロジェクトの wiki 自体をこのシステムで作りたい」を受け、[[grasp-backlog]] の Markdown / Obsidian indexed mirror 節に小節を追加。
- 動機: grasp wiki（`wiki/`, Markdown+frontmatter+`[[...]]`）を mirror 層の最初のテスト corpus にすると「設計判断グラフを近傍同梱で辿りながら次を実装する」ループが閉じる。段階は read-only mirror が write 層より先。
- 設計含意: このwikiは **リンク記法が2系統混在**（`[[...]]`=grasp内→edge、バックティックのプレーン名=親 llm-wiki への cross-wiki link→edge にしない）。∴ Markdown parser TODO に「どの記法を edge とみなすか policy」を明示項目として追加。Cosense JSON だけ見ていると気づけない論点。詳細決定は [[markdown-obsidian-indexed-mirror]]。
- nishio 提案「file back, commit, push, what's next? までを一つのカスタムコマンドにする？」を受け、`.claude/commands/ship-next.md` を追加。
- 目的: grasp の作業ループ（差分理解 → wiki file back → `unittest` / wiki lint / diff check → commit → push → 次実装候補提示）を毎回同じ形で閉じる。空差分なら empty commit せず、current backlog から "what's next?" だけ答える。

## [2026-06-24 00:05] implementation | related recovery hints と path 初期実装
- `related <title>` の空結果に `recovery_hints` を追加し、`read` / `link-stats` / `search` と同じ negative-result contract に揃えた。JSON は `query, related[], recovery_hints|null`、text は空結果時に Recovery Hints を表示する。
- `path <A> <B> --max-depth 4 --limit 3` を追加。pages ∪ unresolved targets を node、materialized internal links を無向 edge として bounded shortest path を返す。edge には source page / line-id / line text を同梱し、bridge の根拠を確認できる。
- Dogfood: `grasp path KJ法 弱い紐帯 --max-depth 4 --limit 1` は 3-hop（KJ法 → Scrapbox情報整理術 → 情報と秩序 → 弱い紐帯）を返した。現状は command ごとに一時 adjacency を構築するため、nishio store では約2-5sで、hot read path ではなく実験的 graph reasoning primitive として扱う。
- store schema は v5 のまま、public compatibility version は `1.5.5`。検証: `python3 -m unittest discover -s tests` OK（26 tests）、`python3 scripts/lint_wiki.py` OK、`git diff --check` OK。

## [2026-06-23 23:58] file back | path の hop 距離を簡易計測
- `path <A> <B>` の go/no-go 基準として、`~/.grasp/grasp.sqlite`（project `nishio`, schema v5）で pages ∪ unresolved targets をノード、materialized edges を無向エッジとして距離分布を標本計測した。グラフは 66092 nodes / 115075 undirected edges、最大連結成分 63490 nodes（96.06%）。
- uniform pages 300 pairs は ≤2-hop 0.3%、≤4-hop 9.0%、≤6-hop 63.3%。top-degree pages 300 pairs でも ≤2-hop 4.3%、≤3-hop 30.0%、≤4-hop 76.7%、≤6-hop 99.3%。「大半が ≤2-hop なら path の純増価値は小さい」という懐疑は少なくともこの標本では成立せず、`path --max-depth 4` の試作価値ありと [[grasp-backlog]] に追記した。

## [2026-06-23 23:42] implementation | read related snippets を追加
- [[grasp-backlog]] / [[ai-consumer-feedback-2026-06-23]] の Tier 2 に対応。`grasp read <title> --related-snippets` を追加し、related 2-hop / missing target の source pages に先頭 N 行（`--related-snippet-lines`, default 5）を同梱できるようにした。
- JSON は related/source item に `snippet_lines` / `snippet_truncated` を opt-in で追加し、text 出力は related item 直下に行を表示する。未指定時の `related[]` shape は維持。
- store schema は v5 のまま、public compatibility version は `1.5.4`。検証: `python3 -m pytest tests/test_sqlite_store.py tests/test_cli_help.py` OK、`python3 -m unittest discover -s tests` OK（24 tests）、`python3 scripts/lint_wiki.py` OK、`git diff --check` OK。

## [2026-06-23 23:10] implementation | search normalized fallback を追加
- `search` の literal 0件時に normalized fallback を追加。NFKC query 正規化＋長音除去は SQLite `REPLACE` で実行し、`ﾕｰｻﾞﾃｽﾄ` が `ユーザテスト` / `ユーザーテスト` 行に hit する。text 出力は `[normalized]`、JSON は `match_mode: "normalized"` / `match_terms` を返す。
- 完全なかな/カナ変換は Python 全行 scan になるため、50k lines 以下の小規模 store のみに制限。nishio 規模での zero-hit kana query は 20s 級だったため、大規模 store では schema/index なしに実行しない。
- store schema は v5 のまま、public compatibility version は `1.5.3`。検証: `python3 -m unittest discover -s tests` OK、実データで `search ﾕｰｻﾞﾃｽﾄ --limit 5` が normalized hits を返すことを確認。

## [2026-06-23 22:39] file back | path の Open Q（グラフモデル）を CLAUDE が解決
- nishio が AI consumer feedback の `path <A> <B>` に「リンクとは？ ページがノード？」と問うた件への回答を [[grasp-backlog]] Graph-native primitives に file back。
- 回答: **ノード = pages ∪ unresolved targets**（page-only にすると page-less の概念ハブ＝最も中心的な connector を落とす）、**エッジ = materialize 済み internal-link edges を無向で**。
- 構造的含意: unresolved target は sink（incoming のみ）なので path の端点か hinge（`A→T←B` = co-cite）。∴ **`path` = `related` を 2-hop 超に一般化したもの**で、related のエッジ集合を再利用できる。
- go/no-go: 密グラフでは大半の対が ≤2-hop（related が繋ぐ）ため path の純増価値は稀。**試作前に hop 距離分布を実測**して falsifiable に判定（>2-hop が稀なら工数を Tier-1 recall へ）。
- 監査: 別 session の ai consumer ingest（22:18-22:31）を raw + 本 session の nishio adjudication と突き合わせて faithful と確認。code claim 2件も実機検証（backlinks は `source.views DESC` ランク済 sqlite_store.py:713 / `Page.to_summary` は `id` 含む cosense.py:186）。

## [2026-06-23 22:36] implementation | search recall の page 単位 AND と空結果 recovery hints を実装

- [[grasp-backlog]] / [[ai-consumer-feedback-2026-06-23]] の Tier 1 に対応。`grasp search "KJ法 表札"` のような空白区切り複数語 query は、同一行の literal substring ではなく **page 単位 AND** として、全語を含む page の該当行を返す。単一語 search は従来通り `lines.text LIKE` の line-level substring。
- `search --json` の空結果に `recovery_hints` を追加し、`read` / `link-stats` と同じ negative-result contract へ寄せた。text output も空結果時に Recovery Hints を表示する。
- SQLite schema / parser semantics は変えないため public compatibility version は `1.5.2`、internal `SCHEMA_VERSION` は `5` のまま。
- 検証: `python3 -m unittest discover -s tests` OK（24 tests）。`python3 scripts/lint_wiki.py` OK（壊れた wikilink 0 / index 未登録 0 / frontmatter 不備 0）。`git diff --check` OK。実データで `grasp search "KJ法 表札"` が `(none)` ではなく `Scrapboxベストプラクティス` / `KJ法` の該当行を返すことを確認。

## [2026-06-23 22:31] file back | AI consumer feedback への nishio 採否を反映

- 22:18 ingest した [[ai-consumer-feedback-2026-06-23]] の候補に nishio が adjudication。live status を [[grasp-backlog]] に、原理の訂正を [[ai-consumer-cost-and-trust]] に、event の採否要約を entity に反映。
- **採用**: `read --related-snippets`（**実 Cosense UI も related 先頭 5 行を表示**するので default snippet=先頭 ~5 行 = Cosense parity）。line-id ローカル別名（agree）。backlinks finer ranking（agree、既に views ランク済み）。
- **却下** `--strip-decoration`: decoration は noise でない。`[nishio.icon]`=block の著者、bare image URL=今の AI に読めずとも人間に画像提示・将来 AI も読む。畳んではいけない。token 削減は line-id 別名側でやる。concept page の cost 軸の例示からも除去し「fidelity を捨てない」を明記。
- **却下** 近傍クラスタリング `--cluster`: クラスタリングは AI がやるべき（AI の方が賢い）。CLI は embeddings 後の雑な embedding クラスタリング程度。そもそも 100+ リンクの hub は rare case。raw＋ranking→AI が畳む方針を確定。
- **experimental** `path <A> <B>`: 研究的には筋が良いが実用性は未知、試作可。要確定 Open Q＝グラフモデル（ノード=page か、エッジ=materialize 済み internal-link edges か）を backlog に記録。
- 検証: `python3 scripts/lint_wiki.py` OK（壊れた wikilink 0 / index 未登録 0 / frontmatter 不備 0）。`python3 -m unittest discover -s tests` OK（22 tests）。`git diff --check` OK。

## [2026-06-23 22:19] lint | AI consumer feedback ingest 後の検証

- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。新設 [[ai-consumer-cost-and-trust]]（concept, sources あり）と [[ai-consumer-feedback-2026-06-23]]（entity）は孤立せず（concept は 4 incoming）。既存の孤立 `multi-project-store` 警告は継続（index 登録済み）。
- `python3 -m unittest discover -s tests` OK（22 tests）。`git diff --check` OK。

## [2026-06-23 22:18] ingest | AI consumer（主たるユーザ視点）の v1 フィードバックを取り込み

- `raw/claude-feedback-2026-06-23.md`（Claude Opus 4.8 が grasp の設計上の主たるユーザ＝CLI 越しにグラフを読む AI として v1 を実走したレビュー、25792 pages の実 store で `stats`/`read`/`related`/`search`/miss を実行）を ingest。仮説（採否 nishio 判断）として routing した。
- **concept 新設** [[ai-consumer-cost-and-trust]]: AI consumer の cost-and-trust model を最初の concept page として切り出し。軸1 round-trip/token の経済（read=近傍同梱の why、gather/snippets/token economy backlog の ranking 原理）、軸2 negative-result contract（沈黙の偽陰性 = absence の hallucination、recall を vector より先に直す理由）。read=近傍同梱（実装済）＋ delivery の Skill orchestration ＋ Tier 1-2 backlog をまたいで育っていたため「育ったら切り出す」trigger 成立と判断。
- **entity 新設** [[ai-consumer-feedback-2026-06-23]]: persona1/persona2 user test と同型の review event 記録。validated（read=近傍同梱・related co-citation rank・miss recovery・scale-first）＋ Tier 1-4 findings ＋ 各 finding の routing 先。
- **backlog 追加** [[grasp-backlog]]: Tier 1 search recall（page 単位 AND / OR / 正規化、vector の前＝最優先）、Tier 2 read --related-snippets / `gather --budget` verb（薄CLI テンション付き）/ output token economy（line-id ローカル別名・--strip-decoration）、Tier 3 Graph-native primitives（path / backlinks finer ranking / --cluster）、横断 Negative-result contract（search/related へ拡張＋実データ hint）、Tier 4 を write/identity の consumer 要件に。
- **decision Update** [[why-not-scrapbox-clone]]: identity-without-name の consumer 側価値（AI 引用が write/rename を跨いで腐らない時間安定性）を著者側 rationale に追記。[[delivery-cli-plus-skill]]: `gather` verb vs 薄CLI の orchestration 置き場を Open Question 化。
- **ingest 時の code 確認で既済2点を訂正記録**（既done な ask を積まないため）: ① backlinks は既に `source.views DESC...` でランク済み（grasp/sqlite_store.py）→ Tier 3 の「挿入順かも」懸念は不成立、未済は finer weighting のみ。② `read --json` は既に安定 page-id を含む（`Page.to_summary()` の `id`、grasp/cosense.py）→ Tier 4 の未済は read field でなく rename を跨ぐ identity 層。

## [2026-06-23 22:07] lint | history / versioning policy 追加後の検証
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。
- `python3 -m unittest discover -s tests` OK（22 tests）。`git diff --check` OK。
- `grasp.__version__` は `1.5.1`。

## [2026-06-23 22:04] implementation | admin export なしの hosted acquisition を実装
- `grasp acquire <project-url>` を追加。`cosense searchFullText` による `--search` seed、`listPages --filter` による `--filter` seed、bounded `--full-list` seed、`readPage` + parsed links による `--from-page --depth` crawl、`--seed-file` に対応。
- `acquire` は対象 project namespace を append せず置き換える。`--project` 省略時は `<remote-project>:acquire` を使い、既存 full export project を誤って partial slice で置き換えない。partial corpus の coverage は store metadata に保存し、`grasp stats` の Acquisition 節で mode / coverage / project_url / fetched を表示する。Skill / README でも backlinks / related / unresolved は取得済み subset 内の結果だと明記。
- 検証: `python3 scripts/lint_wiki.py` OK（真の壊れた wikilink 0、index 未登録 0、frontmatter 不備 0）。`python3 -m unittest discover -s tests` OK（22 tests）。public `https://scrapbox.io/shokai/` に対して `acquire --search codex --limit 2` が `shokai:acquire` に 2 pages / 55 lines / 16 edges / 15 unresolved_targets を作り、`read Codex` が本文 + unresolved targets を返した。`git diff --check` OK。

## [2026-06-23 22:03] file back | history と store 互換 versioning policy を追加
- [[history]] を追加。v1 系の public version は `1.x.y` とし、`x` は SQLite table shape だけでなく parser / materialized index semantics が変わり既存 store を current truth としてそのまま読めない時、`y` は store compatible な CLI / docs / recovery / performance 変更時に進める。
- 2026-06-23 の同日 MVP churn を store compatibility ledger として後付け整理: internal `SCHEMA_VERSION=5` の base は public compatibility version `1.5.0`、current working tree は store-compatible `acquire` 追加を含むため `1.5.1`。`1.4.1` は import cache / auto rebuild の y bump、`1.5.0` は `#tag` / 数字 link の parser/index semantics 変更による x bump。
- `[[grasp-v1-implemented]]` から [[history]] へ current version と source page link を追加。package metadata も `1.5.1` に合わせた。

## [2026-06-23 22:00] file back | install path 検証中に schema auto-rebuild の live 観測
- README/SKILL の install 3 ステップ（`pip install -e`→skill を `~/.claude/skills/grasp` に symlink→`import --cosense`）が nishio primary machine で end-to-end 成立済みと確認（CLI は pyenv 3.10.11 の `grasp`、skill symlink live、store 25791 pages）。install path 自体の dogfooding は persona1/2 test がカバーしていなかった面。
- 検証中に偶発観測: `~/.grasp/grasp.sqlite` が code の `SCHEMA_VERSION` 3→5 に追従して最初の通常 command でサイレント再構築。可視副作用（edges 120693→125409 / unresolved 41750→42770 の drift、`imported_at` 更新、その 1 command だけ import latency）を「期待挙動・corruption でない」gotcha として [[grasp-v1-implemented]] の store 節に追記。rebuild の機構自体は既載なので side-effect の誤読防止だけ足した。

## [2026-06-23 21:54] lint | 長大ページ subagent 委譲 file back 後の検証
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。
- `python3 -m unittest discover -s tests` OK（20 tests）。`git diff --check` OK。
- 既存の孤立ページ警告 `multi-project-store` は継続（index 登録済み）。

## [2026-06-23 21:52] file back | 長大ページ処理の責務を Skill / subagent 側に寄せる判断
- Claude Code / OpenCode 系 harness の shell output は tool result として model に返るが、大きい出力は harness 側で truncate され full output file への導線を返す。subagent は独立 context で探索し、親 conversation には最終結果だけを返す。
- ∴ P0-2 long page navigation は CLI に WebFetch 風 summarizer を入れる話ではなく、Skill が長大ページ探索を subagent / Explore agent に委譲し、親には要約・根拠 page・line-id だけ返す運用を持つのが本筋、と [[delivery-cli-plus-skill]] / [[grasp-backlog]] に file back。

## [2026-06-23 21:52] implementation | Skill に長大ページの subagent 委譲手順を追加
- `skills/grasp/SKILL.md` に「長大ページ・ログページを読む」節を追加。親 conversation に長い `read` 出力を直接持ち込まず、探索用 subagent / Explore agent が `search` / `peek` / limit 付き `read` を使って読み、親には結論・根拠ページ・該当 `line_id`・短い引用/要約だけ返す、と明記。
- CLI は LLM 依存の要約をしない deterministic graph reader として維持し、`search --context N` / `read --around-line <line-id>` は実運用で不足が出た時の bounded primitive 候補に留める。

## [2026-06-23 21:52] lint | persona1 P0 friction file back 後の wiki lint
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。
- 既存の孤立ページ警告 `multi-project-store` は継続（index 登録済み）。

## [2026-06-23 21:49] implementation | persona1 dogfooding P0 friction を解消
- [[persona1-user-test-2026-06-23]] / [[grasp-backlog]] の P0 に対応。parser は `#tag` を `[tag]` と同等の internal link として edge 化し、数字のみ `[1]` / `[2024]` も link として拾う。`xs[0]` / `func()[1]` など ASCII index 風 syntax、inline code、URL fragment は false positive として除外する。
- parser/index semantics 変更のため SQLite schema を v5 に更新。v4 store は通常 command 時に import cache から自動再構築され、新しい edge / unresolved / backlinks / related に反映される。
- `read` / `link-stats` が missing + 0 incoming の時、`recovery_hints` として `suggest`, `search --limit 3`, 近い unresolved target を返す。日本語の `ユーザテスト` / `ユーザーテスト` 型に効くよう、unresolved target 候補では長音記号を落とした loose match も使う。
- `grasp read ... --json` のような command 後 `--json` を hidden alias として受ける。help example の repo-local `.grasp/grasp.sqlite` drift を消し、README / Skill は `--store` / `--project` は root option、`--json` は後置も可に更新。
- store missing 時の `stats` は `diagnostic.type=store_missing` と next actions を返す。通常 command の store missing と folder を `import --cosense` に渡した時は traceback ではなく product language で復旧案 / Markdown import 未実装を返す。
- 検証: `python3 -m unittest discover -s tests` OK（20 tests）。`grasp --store /tmp/grasp-missing-demo.sqlite stats --json` は store missing diagnostic を返し、`grasp --store /tmp/grasp-missing-demo.sqlite read Missing --json` と `grasp import --cosense .` は friendly error を返した。

## [2026-06-23 21:41] file back | 非 admin project の取得候補を backlog 化
- nishio 提案: 自分が管理者でない project の取得方法として、特定文字列を含む page（キーワード、`[nishio.icon]`、`[/nishio/` など）を検索 seed にする、指定 page から link を辿る、など。
- [[grasp-backlog]] に "Hosted Cosense acquisition without admin export" を追加。既存の `import --cosense` は admin export、`sync` は full seed 済み project の freshness path なので、非 admin 取得は別の `acquire` / `crawl` 系 surface として扱う。
- 候補: `listPages` pagination + `readPage` の full list seed、`searchFullText` の search seed、`listPages --filter <name>` の author/icon filter seed、link crawl seed、manual seed list。partial corpus では backlinks / related / unresolved が subset 内の結果であることを metadata / 表示で明示する必要がある。

## [2026-06-23 21:42] lint | 非 admin acquisition file back 後の wiki lint
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。
- 既存の孤立ページ警告 `multi-project-store` は継続（index 登録済み）。

## [2026-06-23 21:38] lint | sync file back 後の wiki lint
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。
- 既存の孤立ページ警告 `multi-project-store` は継続（index 登録済み）。

## [2026-06-23 21:35] implementation | import JSON cache から旧 schema store を自動復旧
- nishio 提案「最後に import した JSON を store のそばに置き、旧 schema store をサイレントに回復」に対応。
- `grasp import --cosense <json>` は import 成功後、store 横の `<store>.imports/` に project ごとの Cosense JSON コピーと `manifest.json` を保存する。`--project` override も manifest に保持する。
- `read` / `peek` など通常 command は schema mismatch を検出したら、まず import cache から current schema store を再構築し、そのまま元の command を続行する。`stats` は診断用なので自動復旧しない。cache が無い旧 store では metadata の `last_source_export` / `source_export` を fallback に使う。import cache は seed snapshot なので、hosted の最新差分は復旧後も `sync` の責務。
- 検証: original export を削除し metadata `schema_version` だけ `3` に戻した store に対して `grasp --json --store <path> peek A` が stderr なしで成功する test を追加。

## [2026-06-23 21:35] verification | sync で hosted/local の page count 一致を確認
- 同期前: `grasp --json stats` は local store `~/.grasp/grasp.sqlite` / project `nishio` が 25791 pages。`cosense listPages https://scrapbox.io/nishio/ --sort updated --limit 1` は hosted count 25792。
- `grasp --json sync https://scrapbox.io/nishio/ --limit 20 --dry-run` は `タブUI` 1 件だけを changed として検出。同期前の `grasp read タブUI` は page なし / backlinks なし。
- 実行: `grasp --json sync https://scrapbox.io/nishio/ --limit 20`。`タブUI` 1 件を upsert し、updated 1。
- 同期後: local stats は 25792 pages / 724986 lines、hosted count 25792。再 dry-run は changed 0 で停止点 `タブUI`。page count mismatch は解消。

## [2026-06-23 21:31] verification | cosense-cli と grasp で同一ページ取得を smoke
- 対象: `盲点カード`。hosted は `cosense readPage https://scrapbox.io/nishio/盲点カード`、local は `grasp --project nishio --json peek 盲点カード`。
- 最初の `grasp peek` は既定 store が schema 3 / current 4 だったため `store schema is 3, current is 4; run \`grasp import --cosense <json>\` to rebuild` で失敗。`grasp import --cosense /Users/nishio/grasp/raw/nishio.json` で `~/.grasp/grasp.sqlite` を schema 4 / project `nishio` として再構築した。
- 再構築後、本文行の full diff は差分なし。両者 124 lines、SHA-256 は `362d6da6a9f2b48693d8b1be7b187cd9d5ee5b082d7c8f3c811918e470fa8357`。`grasp read` も同じページで backlinks / related / unresolved を返すことを確認。
- 付記: `cosense listPages https://scrapbox.io/nishio/ --limit 1` の hosted count は 25792、local store は export snapshot 由来で 25791 pages。freshness は引き続き import/sync の責務。

## [2026-06-23 21:28] release | MIT ライセンスを明示
- `LICENSE` に MIT License を追加し、`pyproject.toml` の package metadata と README に MIT 表記を追加。

## [2026-06-23 21:17] implementation | 複数 project を1 store 内の namespace として保持
- nishio 指摘: 複数 JSON は同じ graph に merge する必要はないが、store file を分けるのでなく1つの store に project 名ごとに保持すべき。
- SQLite schema を v4 に更新。`projects` table を追加し、pages / lines / edges / unresolved_targets / unresolved_target_examples を `project` 列で namespace 化。`grasp import --cosense <json>` は export root `name` を project 名にし、同名 project だけを置き換える。他 project は保持する。`grasp import --project <name> --cosense <json>` で override 可能。
- read/search/backlinks/related/unresolved/sync は selected project 内だけを見る。store に1 project だけなら `--project` 省略可、複数 project なら `--project <name>` / `$GRASP_PROJECT` が必要。`stats` は project list と aggregate/project counts を返す。
- [[multi-project-store]] を追加し、[[grasp-v1-implemented]] / README / Skill を更新。検証: `python3 scripts/lint_wiki.py` OK（壊れた wikilink 0、index 未登録 0、frontmatter 不備 0）、`python3 -m unittest discover -s tests` OK（13 tests）、`git diff --check` OK。

## [2026-06-23 21:11] refactor | 旧 SPEC / v1-todo を実装済み facts と backlog に分解
- nishio 判断: `SPEC.md` は定義ではなく v0.5 を実装するための一時指示、`v1-todo.md` も一時 TODO。v1 リリース後に保つ必要はない。
- `[[grasp-v1-implemented]]` を追加し、v1 時点で実装済みの CLI surface / store / parser / delivery / performance facts を集約。`[[grasp-backlog]]` を追加し、旧 SPEC / 旧 v1-todo にあった未実装項目（`#tag`, 数字 link, zero-hit recovery, root option recovery, Markdown adapter, write/identity, search/vector/sync 残課題など）を集約。
- `wiki/SPEC.md` と `wiki/v1-todo.md` を削除。index / AGENTS.md / CLAUDE.md / current decision/entity ページの参照を新ページへ張り替え。`python3 scripts/lint_wiki.py` OK（壊れた wikilink 0、index 未登録 0、frontmatter 不備 0）。

## [2026-06-23 20:59] file back | write の分担（hosted=cosense-cli / local-only=grasp write）を記録
- nishio の README roadmap 編集を [[cosense-cli]] の「使い分け」に固定。hosted Cosense への write/edit は cosense-cli（`previewEdit` / `submitEdit`）が担い、grasp 自身の write 層（旧 `SPEC.md` roadmap, v1 外）は (a) 非 Cosense ユーザ、(b) オンラインでなくローカルに閉じて書きたいケース のサポートが目的。
- ∴ 書き込み先（hosted ↔ local-only）で棲み分け、grasp write は cosense-cli の重複ではない。Cosense ユーザの hosted 編集は cosense-cli が担うので grasp が hosted write を実装する動機は無い、と明記。

## [2026-06-23 20:59] lint | wiki 全体の意味的矛盾チェック
- `python3 scripts/lint_wiki.py` OK（壊れた wikilink 0、index 未登録 0、フロントマター不備 0）。
- 意味的な矛盾候補: 旧 `v1-todo.md` の F4 判断（write/transclude/rename は v1 に載せない）に対し旧 `SPEC.md` の CLI surface 表がまだ3動詞を載せている。F3 判断（数字のみ `[1]`/`[2024]` はリンクとして拾う）に対し旧 `SPEC.md` / [[grasp-cli-mvp]] / [[cosense-json-export]] は strict parser が数字のみを link としない現状を正典風に保持している。旧 `v1-todo.md` F1 は README 未作成と `--consense` typo を含み、後続 README 作成ログ・実装の `--cosense` と食い違う。

## [2026-06-23 20:53] file back | README を「AI が主たるユーザ」前提で再センタリング
- nishio 指示「主たるユーザは CLI を直接叩かず、AI に Skill として入れて AI が CLI を使う」を [[delivery-cli-plus-skill]] に Update として固定（「AI＝設計上のユーザ」の human-facing copy への operationalize）。README lede が「主たる使い方は `grasp` コマンドを叩くことではない」を明示、install に skill symlink を first-class step 化、quickstart の主経路を `grasp read` 直叩きでなく「AI に聞く」に。
- あわせて user docs hygiene を記録: ジャーゴン（"before Co-" 等）と内部 dev wiki（SPEC / decisions）への導線をユーザ向け README に出さない（F1 README で適用済み, 旧 `v1-todo.md`）。

## [2026-06-23 20:52] lint | `stats` README 説明粒度 file back 後の wiki lint
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。既存の孤立 `v1-todo` は index 登録済みのまま。

## [2026-06-23 20:51] file back | README から `read` 生出力例を削除
- nishio 指摘「こんな生データ、人間が直接みるわけじゃないから書かないでいい」に合わせ、README の `read` 出力サンプル節を削除。
- README は人間向けの価値・install・AI Agent Skill 導線に絞り、出力フォーマット詳細は `grasp read --help` と `grasp --json read ...` に寄せる。これは `grasp <verb> --help` を mechanics SSoT にする [[delivery-cli-plus-skill]] の方針とも一致する。

## [2026-06-23 20:51] verification | README / import UX 変更後の検証
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。既存の孤立 `v1-todo` は index 登録済みのまま。
- `python3 -m unittest discover -s tests` OK（12 tests）。`git diff --check` OK。

## [2026-06-23 20:50] file back | README の `stats` 説明粒度を調整
- nishio 判断: README の command 一覧では `stats` の詳細 schema まで書かず、「ストアの件数・更新日時など」程度の人間向け概要に留める。詳細は `grasp stats --help` と [[grasp-cli-mvp]] 側で保持する。
- README の `stats` 行を「ストアの件数・更新日時などを確認」に変更し、[[grasp-cli-mvp]] に README/detail の役割分担を記録。

## [2026-06-23 20:50] lint | `sync` runtime 前提 file back 後の wiki lint
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。既存の孤立 `v1-todo` は index 登録済みのまま。

## [2026-06-23 20:50] file back | `sync` の cosense-cli install 前提を明示
- `grasp sync <project-url>` は hosted freshness path なので、通常の local read/search と違って `@helpfeel/cosense-cli` の `cosense` binary が install 済みで PATH にあり、対象 project に認証済みであることが動作条件。
- 旧 `SPEC.md` M2-4 / CLI 動詞表、[[incremental-sync]]、[[cosense-cli]]、README、Skill の sync 説明に前提を反映。`--cosense-command` で binary 名 / path を差し替え可能であることも記録。

## [2026-06-23 20:49] lint | import `--force` 削除後の wiki lint
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。既存の孤立 `v1-todo` は index 登録済みのまま。

## [2026-06-23 20:48] implementation | import の `--force` を削除し既存 store をそのまま置換
- nishio 指摘「古い store がある時に拒否して欲しいことはない。`--force` は余計な option」に合わせ、`grasp import --cosense <json>` を初回構築・再構築兼用に変更。CLI は既存 store を拒否せず、import 成功時に置き換える。
- 実装上は既存通り temp store を作成してから `os.replace` するため、再構築の途中失敗で既存 store を消す挙動にはしない。
- SPEC / README / Skill / [[grasp-cli-mvp]] / help test を更新。

## [2026-06-23 20:48] lint | FTS5 trigram 検証ページ切り出し後の wiki lint
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。既存の孤立 `v1-todo` は index 登録済みのまま。

## [2026-06-23 20:46] file back | FTS5 trigram 検証を独立 entity 化
- [[grasp-cli-mvp]] 内の「FTS5 trigram 検証メモ」を新ページ [[fts5-trigram-search]] に移動。`grasp-cli-mvp` には現状判断（correctness 優先で `lines.text LIKE` 維持）とリンクだけを残した。
- [[markdown-obsidian-indexed-mirror]] / [[language-and-distribution]] の FTS5 hybrid 参照を新ページへ差し替え、search index 設計上の注意点を一箇所に集約した。

## [2026-06-23 20:17] file back | 公式 cosense-cli との速度比較を再計測で更新
- [[cosense-cli]] の実測比較を、旧 MVP（毎回 123MB JSON full parse で ~3.4s）から現行 SQLite warm store ベースへ更新。median of 5 で `grasp read` 67ms / `peek` 65ms / `related` 72ms / `search 盲点 --limit 100` 185ms、公式 `cosense` v1.4.4 は `browsePage` 578ms / `browseRelatedPages` 1169ms / `searchFullText` 875ms / `searchVector` 792ms。
- 初回 seed は別枠として temp store import 8.3s。含意: **反復 read/search は grasp、freshness delta は cosense-cli**。`sync --limit 20 --dry-run` 695ms は `listPages --sort updated --limit 20` 636ms と同程度で、sync の律速が hosted network/API であることも明記。

## [2026-06-23 20:15] implementation | explicit import option を `--cosense` に変更
- nishio 指摘「`grasp import --export your.json` は将来サポート対象が増えた時に何の export か混乱する。`--cosense` がよい」に合わせ、明示 import surface を `grasp import --cosense <json> --force` に変更。
- リリース前なので互換性は取らず、global `--export` / `--rebuild-store` / store 不在時の暗黙 seed は削除。store 作成・再構築は `grasp import --cosense <json> --force` に一本化。
- SPEC / Skill / [[grasp-cli-mvp]] に file back。

## [2026-06-23 20:10] decision | Cosense ヘビーユーザ user test の F1–F5 を v1 TODO に確定
- 第3の視点（nishio でない Cosense 熟練者が GitHub から自前 project を入れようとする。persona1/persona2 のどちらとも違う）で CLI を user test し、新ページ 旧 `v1-todo.md` に nishio 判断を固定。
- F1 README=★最優先（landing 無し・自前 project の入れ方が無い・default/例が nishio 固有）。F2 `#hashtag` をデフォルトで Scrapbox 同様リンク化（無視オプションは将来）。F3 数字のみ `[1]`/`[2024]` を捨てるのはバグ→拾う（`xs[0]` 等の false positive 除外は維持）。F4+transclude write/transclude/rename は v1 に**載せない**("planned"でもない)＝v1=Export JSON の AI 高速 read-only、SPEC 表から削除。F5 help 例 `.grasp/grasp.sqlite` を実デフォルト `~/.grasp/grasp.sqlite` に一致。
- 良かった点（中核仮説）: `read`=近傍同梱が「関連ペインのテキスト版」として ~0.1s で成立、search/suggest/peek/unresolved が Scrapbox の手癖に対応、case/space 正規化一致。
- 未了: persona3（Cosense 熟練者 but not nishio）の user test ページ化は offer のまま未実施。本 TODO は SPEC 反映 action を含むが、SPEC.md は別セッション編集中のため本 session では未編集（commit もしていない）。

## [2026-06-23 20:09] implementation | `export-ai` default を depth 1・limit なしに変更
- nishio 指示「デフォルトは `--depth 1` で limit なし」に合わせ、`grasp export-ai` の `--direct-limit` / `--indirect-limit` default を `None`（無制限）に変更。`--depth` は既に 1 が default。
- SPEC と `skills/grasp/SKILL.md` に default semantics を明記。

## [2026-06-23 19:56] file back | global store の設計原理を canonical な store decision へ昇格
- 19:53 の global 化を mechanics として log/delivery decision に書いたが、**「store は global に1個（per-project 複製しない）」という原理**は store の正典 [[persistence-custom-format]] に無かった。そこへ Update を追加: store は単一 AI 所有 knowledge store ＝ どこでも同じ1個（cwd cache でない）、置き場は `$GRASP_STORE → $GRASP_HOME/grasp.sqlite → ~/.grasp/grasp.sqlite`、store path は project state でなく user/agent state、別 knowledge set は `$GRASP_HOME` で home ごと差し替え。delivery の global skill 判断（[[delivery-cli-plus-skill]]）と同根＝「1つの外部脳=1つの store=どこからでも同じ skill」。
- 同ページの stale な Open Q「Cosense export スキーマは Codex が実物で確認」を解決済みに（[[cosense-json-export]] が 25791 pages で確定済み）。

## [2026-06-23 19:53] implementation | store と skill を global 化（per-project 複製しない）
- nishio 判断「同一 Cosense を per-project に別々に持ちたいことはない → global に入れて DB も global」。`grasp/cli.py` の `default_store_path()` を cwd 相対（`./.grasp/grasp.sqlite`）から **`$GRASP_HOME or ~/.grasp` 配下**に変更、`grasp_home()` helper を追加。`default_export_path()` も `$GRASP_EXPORT → ~/.grasp/nishio.json → cwd raw/nishio.json` の順に。
- 既存 store を `~/.grasp/grasp.sqlite` へ移動、seed を `~/.grasp/nishio.json -> repo raw/nishio.json` の symlink に。**`/tmp` から flag 無しの `grasp read/link-stats` が動作**。`python3 -m unittest discover -s tests` 11 OK（tests は default path 非依存）。
- skill を **user-level 化**: `~/.claude/skills/grasp -> /Users/nishio/grasp/skills/grasp`（SSoT 1本を symlink、全 project で発火）。SKILL.md「実行方法」を global default 前提に更新（別 cwd でも flag 不要）。`*.egg-info/` を gitignore。
- file back: [[delivery-cli-plus-skill]] の install Open Q を「user-level skill＋global store 配置済み」に更新。SPEC は別セッションが既に global store 記述に追随済みで一致。

## [2026-06-23 19:52] file back | Markdown / Obsidian folder は indexed mirror として扱う
- nishio の問い（既存 Markdown 束 or Obsidian folder を point し、grep より高速な検索とリンクたどりを付与する Skill 方向はどうか）を新 decision [[markdown-obsidian-indexed-mirror]] に固定。
- 核心: **Skill が速くするのではなく、Markdown / Obsidian folder adapter が read-only indexed mirror を作る**。SQLite store に pages / lines / edges / unresolved targets / search index を materialize し、Skill は `grasp` CLI を使わせる薄い層にする。
- pitch は "faster grep" では弱い。persona2 には **indexed graph reader for Markdown / Obsidian notes, optimized for LLM agents** と言う。価値は `read` が本文 + 逆リンク行 + related + unresolved targets を一体で返すこと。初期は write-back / rename propagation / Obsidian plugin 完全互換を非目標にし、既存 vault を壊さない point-at-folder 体験を優先。

## [2026-06-23 19:50] file back | persona1 user-test の設計含意を SPEC / entity へ伝播
- [[persona1-user-test-2026-06-23]] の発見を旧 `SPEC.md` と [[grasp-cli-mvp]] に反映。`~/.grasp/grasp.sqlite` global store default（`$GRASP_HOME` で差し替え）を current mechanics として明記し、repo-local `.grasp/grasp.sqlite` 前提の記述を更新。[[delivery-cli-plus-skill]] も「別 cwd では --store 必須」から「global store なので flag なしで読む」に更新。
- SPEC に **M2-5 persona1 dogfooding UX fixes** を追加。zero-hit recovery（`ユーザテスト` vs `ユーザーテスト` などの表記ゆれ空振り）、verb 後 `--json` の回復、search hit line から周辺本文へ行く surface を read-only の次課題として固定。

## [2026-06-23 19:47] user-test | persona1 dogfooding で CLI 体験を検証
- [[persona1-user-test-2026-06-23]] を追加。persona1 を [[positioning-two-personas]] の定義通り「日本語 Cosense ヘビーユーザ = nishio dogfooding」として、`search` → `read` → missing target `read` → source page traversal を実走。
- 結論: **read=近傍同梱**と **linked target without page を backlinks/source pages で読む体験**は persona1 に刺さる。`民主主義` のような page なし概念でも 82 links / 78 source pages で意味が読める。
- 摩擦: `ユーザテスト` vs `ユーザーテスト` の表記ゆれで missing/0 links に落ちる、`--json` を subcommand 後に置くと回復案なしで argparse error、長大ログ page の default read が 513 lines / 66KB、current help/Skill の default store `~/.grasp/grasp.sqlite` と SPEC/entity の repo-local store 記述が drift。

## [2026-06-23 19:46] user-test | persona2 視点で fresh onboarding を検証
- [[persona2-user-test-2026-06-23]] を追加。persona2（世界の LLM Wiki / Markdown 束ユーザ）として、空 cwd + 空 `GRASP_HOME` + 最小 `notes/Alpha.md` から初回導線を試した。
- 結果: persona2 active release としては fail。`grasp --help` / package description は Scrapbox/Cosense 寄りで persona2 の hook（Markdown 束より local graph store）を出していない。README/docs も無い。`grasp stats` は store/export 無しで onboarding にならず、`grasp import notes` は unrecognized args、`grasp --export notes import --force` は `IsADirectoryError` traceback。
- 判断: MVP の persona1 dogfooding には問題ないが、persona2 を狙うなら Markdown import adapter は release gate。暫定でも directory export の friendly error、store missing の診断、英語 README / demo が必要。

## [2026-06-23 19:43] file back | audience を2層 positioning に決定化、name=identity 欠陥を精密化
- nishio の persona 観（JP Cosense ヘビーユーザは自分の一側面／世界の LLM Wiki・Markdown 束ユーザは upside risk として狙う／HN・Reddit 投稿もあり）を新 decision [[positioning-two-personas]] に distill。核心: **substrate は共有だが value prop と on-ramp が persona ごとに別**。driver=persona1（dogfooding）、persona2 は設計の再センタリングでなく **addition**（Markdown adapter＋英語 docs＋一般化 pitch）で狙う。罠＝dilution（read=近傍同梱が「graph DB を CLI で」との差を溶かさない）。
- 設計含意を2つ固定: ①**Markdown import adapter は persona2 の on-ramp そのもの**（旧 `SPEC.md` 入力節の "後で足せる" は persona1 都合で、persona2 を狙うなら re-rank 候補）。②identity-without-name は両 persona に別の言葉で刺さる。
- **nishio 訂正で name=identity 欠陥を精密化**: 「Markdown と Scrapbox は同じバグ」は誤り。Scrapbox は rename でリンクを**書き換え or redirect** して生存させる（リンクは切れない）。欠陥は**そのリンク生存解が払うコスト**（書き換え＝文意破壊／redirect＝旧名 stub 累積）。3者で失敗モードが別物（Markdown=リンク切れ／Scrapbox=文意破壊 or stub 累積／grasp=どちらも無し）。[[why-not-scrapbox-clone]] の該当箇所も redirect コストを補って一段精密化。
- index に decision 1 行を登録。

## [2026-06-23 19:42] file back | warm-store 再計測を実装現状ページへ伝播
- [[language-and-distribution]] の一次データ（warm page cache・median of 5 の各 verb wall time）を、性能事実の source of truth である [[grasp-cli-mvp]] にも反映。`stats` 70ms / `backlinks` 54ms / `read`（近傍同梱）83ms / `unresolved` 52ms / `search` 178ms、固定オーバーヘッドは bare `python3` 33ms・`import grasp` ~free（依存ゼロ）。
- entity ページに残っていた **stale な「read 約 0.7 秒 / wall 1.0 秒」を訂正**: あれは早い時点の cold/単発計測で、warm steady-state は 50–180ms。中核 read は既に sub-100ms、`search` 178ms だけ SQLite `LIKE` 全行スキャン律速（index が lever、host 言語ではない）。
- 上書きせず `## Updates` 流の inline note 追記（entity の既存 update 慣習に合わせた）。decision の主張に entity 側の一次データが整合した。

## [2026-06-23 19:39] file back | 実装言語 × 配布チャネルの長期比較を decision 化
- nishio の問い（Python/Node/Rust で native build／Claude Code は npm 更新／PyPI は pip）を新 decision [[language-and-distribution]] に distill。核心は**実装言語と配布チャネルは独立な2軸**で、混同（"Node でネイティブビルド"）を解いた。
- **言語論点は session 内実測で溶けた**: warm store（238MB）で bare `python3` 起動 33ms / `import grasp` ~27ms（依存ゼロ）/ `read` 83ms / `backlinks` 52ms / `search` 178ms。重い仕事は全部 SQLite=言語非依存、固定 Python オーバーヘッドは ~30ms のみ。旧 `SPEC.md` 原理1「graph を流れる体験」は既に sub-100ms で達成済み → native 化の latency 便益はほぼ無い。[[grasp-cli-mvp]] の旧「read 0.7s」は cold/最適化前と判明。
- **∴ 長期の実体は配布チャネル**。決定: 当面 Python のまま（surface churning 中・依存ゼロ）、外部 consumer が出たら PyPI 公開 → `pipx install`（素の pip は PEP 668 で弾かれる）。**native(Go/Rust)→npm(optionalDependencies)+Homebrew は trigger 待ち**（Python 不可 agent 環境／warm でも latency 体感／SQLite を超える構造要求）。**SQLite store が言語非依存の契約**ゆえ hot read path だけ先に native 化する段階移行で de-risk。**Node-native は採らない**（SQLite 弱・runtime 依存・起動便益なし）。[[delivery-cli-plus-skill]] の CLI+Skill 境界が言語非依存である点とも整合（言語選択は delivery 決定に直交）。
- index に decision 1 行を登録。

## [2026-06-23 19:30] implementation | Claude Code 用 Agent Skill `skills/grasp/SKILL.md` を実装
- [[delivery-cli-plus-skill]] に従い、cosense-cli パターンで grasp Skill を作成。repo に `skills/grasp/SKILL.md`（SSoT）、`.claude/skills -> ../skills` / `.agents/skills -> ../skills` symlink で project skill 化。`pip install -e .`（依存ゼロ）で `grasp` を PATH に通し、別 cwd から `--store` 絶対指定で動くことを smoke 確認。
- 薄く保った: 「いつ使うか」のケース分岐＋verb 一覧 snapshot のみ。各 verb の引数/戻り値は `grasp <cmd> --help`（mechanics SSoT）に委譲し二重化しない。read=近傍同梱ゆえ cosense の read-page.md 相当の traversal 手順書は不要（[[delivery-cli-plus-skill]] の予言通り SKILL.md 1枚で足りた）。
- 解釈ミス2点を skill content に封じた: `unresolved` は「TODO ではない概念ノード rank view」（実例 `民主主義` 82 links/78 pages/本文なし）、リンクは Cosense 原文 `[single]` 表記で grasp 読みでも `[[...]]` を使わない。`cosense` skill（hosted/最新/ベクトル検索）との使い分け表も付けた。
- decision の install Open Q を解決済みに更新。残: user-level skill（`~/.claude/skills/grasp/`）化は未配置（in-repo のみ）。

## [2026-06-23 19:21] implementation | `grasp <cmd> --help` を mechanics SSoT として拡張
- argparse help を拡張し、root help に global option の位置規則と mechanics SSoT 方針を追加。全 subcommand help に arguments / `--json` return keys / Examples / Notes を持たせた。
- `tests/test_cli_help.py` を追加し、全 command help が `Returns (--json):` と `Examples:` を含むこと、`read` が `--unresolved-limit` / `unresolved_targets` を示し旧 `--wanted-limit` を含まないことを固定。
- [[grasp-cli-mvp]] に、Agent Skill は schema を重複保持せず使用直前に `grasp <cmd> --help` を読む、と file back。

## [2026-06-23 19:20] decision | delivery = CLI + Agent Skill（純CLI/MCP でなく）
- nishio 指摘:「Skills にする選択肢が出てないのはおかしい。cosense-cli の repo はあれは Skills」。実際 cosense-cli の `package.json` は自分を「Agent Skill 用の CLI」と定義し、`docs/guidelines/cli-vs-skill.md` が CLI/Skill 責任境界を SSoT 分割。
- 新 decision [[delivery-cli-plus-skill]]: grasp の利用面 = **CLI + Agent Skill**。SPEC Open Q「純 CLI か MCP か」を CLI+Skill で決着（MCP は当面採らない／将来併設余地）。3 層: `grasp <cmd> --help`=mechanics SSoT / `SKILL.md`=いつ・どう使う＋verb 表 / `<手順>.md`=wisdom・観察指示。grasp 固有: read=近傍同梱（原理1）が cosense skill の traversal wisdom を CLI 出力に吸収 → SKILL.md は薄い。
- 私の skill content 案の解釈ミス2点を nishio が訂正、decision に封じた: ①「`unresolved`(旧wanted)＝自己宛TODO」は誤り（原理3 改訂で構造ノード扱い、TODO と決めつけない）。②「grasp のリンクは `[[...]]`」は誤り（read-only MVP は Cosense 原文 `[single]` 保持、`[[X]]` は未来の write 記法でスコープ外）。
- 旧 `SPEC.md` Open Q「Codex からの呼び方」を解決済みに、index に decision を登録。次: `--help` 充実 → `skills/grasp/SKILL.md` 実装。

## [2026-06-23 19:03] implementation | `wanted` 互換を捨て `unresolved` に破壊的変更
- ユーザ判断: まだ利用者はいないので互換性を考えず、設計語彙に合わせて変える。`wanted` command / JSON field / SQLite table 名を削除し、`unresolved` command / `unresolved_targets` field / `unresolved_targets` table に変更。schema_version は 3。
- `read` option は `--wanted-limit` ではなく `--unresolved-limit`。`read` result から `red_link` field を削除し、page なし target の状態は `page: null` + `link_stats` + `related` で表す。
- `unresolved_targets` entries は `count` ではなく `link_count` を持つ。`stats` も `unresolved_targets` count を返す。旧 schema の通常 command は rebuild 必須で止める。

## [2026-06-23 18:53] implementation | missing link target の link stats と related source pages を追加
- 「link があるが page がない」こと自体は `wanted` ではなく unresolved graph node と整理。旧 `SPEC.md` の中核原理・データモデル・CLI surface を更新し、`wanted` は unresolved targets の ranked view と明記。
- `grasp link-stats <title>` を追加。existing page / unresolved target の incoming `link_count`, `source_page_count`, `link_multiplicity` (`none` / `single` / `multi`) を返す。unresolved target は materialized `wanted` row、existing page は `edges.target_norm` index で数える。
- `related <unresolved-target>` は空でなく、その target に link している source pages を `relation=backlink-source` として返す。実データ smoke: `民主主義` は page なしだが 82 links / 78 source pages、`related 民主主義 --limit 5` が source pages を返した。

## [2026-06-23 18:45] file-back | FTS5 trigram 検証メモを記録
- [[grasp-cli-mvp]] に FTS5 trigram の実測と判断を追記。3文字以上の safe query では hybrid（`MATCH` → `LIKE`）が高速だが、2文字日本語 query は trigram に乗らず、記号入り query は FTS query syntax と衝突する。
- `MATCH` は literal substring search ではない（例 `MATCH 'abc bcd'` が `abcd` / `abcde` / `abcXbcd` も返す）ため、grasp の `search` semantics を保つには hybrid でも最後に `line.text LIKE '%query%'` が必要。現段階では特殊化として見送り、correctness 優先で `lines.text LIKE` を維持。

## [2026-06-23 18:31] implementation | store schema status を可視化
- `grasp stats` を追加。store path, schema_version, current_schema_version, schema_ok, source_export, imported_at, pages/lines/edges/wanted を text/JSON で返す。
- 通常 command で古い schema の store を開いた場合、stderr に `--rebuild-store` / `grasp import --force` を促す警告を出す。v1 store は fallback で動くが、schema v2 の `wanted_examples` 最適化を使うには rebuild が必要。
- 検証: unit tests OK。実データ store で `stats` text/JSON を確認。metadata を一時的に schema 1 に書き換えた copy で warning 出力を確認。

## [2026-06-23 18:27] implementation | wanted examples を materialize、FTS search は見送り
- `wanted_examples` table を追加し、import / sync 後の `rebuild_wanted` で各 wanted target の上位 5 example edge を materialize。`wanted --limit N` が N 回 example query を投げないようにした。schema_version は 2。
- Python 内部計測では `wanted(limit=100)` 約 6ms。CLI wall time は Python 起動 + output 込みで約 1.0 秒。
- SQLite FTS5 trigram を試したが、2文字日本語 query（`盲点`）は `MATCH` で拾えず、FTS table `LIKE` では `盲点カード` の recall が落ちた。本文検索は correctness 優先で `lines.text LIKE` のまま維持。
- 実データ import は約 9.6 秒。`search 盲点 --limit 100` 約 1.16 秒、`wanted --limit 100` 約 1.01 秒、`read 盲点カード` 約 1.03 秒（CLI wall time）。

## [2026-06-23 18:19] implementation | M2-4 cosense-cli 差分 sync を実装
- `grasp sync <project-url>` を追加。`cosense listPages --sort updated` で最近更新ページ metadata を inspect し、store の `pages.updated` と比較して changed page だけ `cosense readPage` → SQLite upsert → `wanted` 再 materialize。`--dry-run`, `--limit`, `--batch-size`, `--cosense-command` 対応。
- humanized `updated` は suffix 前の ISO8601 を epoch seconds に変換。pinned page は停止条件から除外。hosted line id は採用せず `page.id:line-index` を維持。
- 検証: fake client unit test で changed page upsert / old edge 削除 / new wanted を確認。実 `cosense` dry-run/no-op smoke: `sync https://scrapbox.io/nishio/ --limit 5` は changed 0 / updated 0。

## [2026-06-23 18:15] implementation | M2-3 parser false-positive `[** x]` 系を修正
- `is_internal_cosense_link` の decoration 判定を「先頭の連続する `*` / `-` / `_` 群 + 空白」に拡張。`[* x]` だけでなく `[** x]`, `[*** x]`, `[-- x]`, `[__ x]` を link としない。
- 実データ再 import: 120693 edges / 41750 wanted。`backlinks '** 深い思考'` は none になり、wanted 上位から消えた。
- 検証: `python3 -m unittest discover -s tests` OK。

## [2026-06-23 18:14] implementation | M2-2 行レベル本文検索 `search` を追加
- `grasp search <query>` を追加。SQLite `lines.text LIKE` で本文行を検索し、`source_page_id/title/views/updated`, `line_id`, `line_index`, `line_text` を返す。text output は backlinks と同じ行リスト形式、`--json` 対応。
- ranking は SPEC 通り暫定: page.views → updated → title → line_index。`suggest` は title 補完として維持。
- 検証: `python3 -m unittest discover -s tests` OK。実データ `search 盲点 --limit 5` は約 0.7 秒で行レベル hits を返した。

## [2026-06-23 18:12] implementation | M2-1 SQLite on-disk store を実装
- `grasp import --force` と `--store` / `--rebuild-store` を追加。default store は `.grasp/grasp.sqlite`（gitignored）。通常 command は store が存在すれば `raw/nishio.json` を再 parse しない。
- SQLite schema: `metadata`, `pages`, `lines`, `edges`, `wanted`。`wanted` は import 時に materialize（毎回 group-by しない）。`Page.line_count` は SQLite row 由来の `stored_line_count` を持てるようにした。
- 実データ検証: import 約 8 秒、store 利用時 `read 盲点カード` 約 0.7 秒、`wanted --limit 3` 約 0.7 秒、`backlinks 盲点` 約 0.4 秒。`python3 -m unittest discover -s tests` OK。

## [2026-06-23 17:58] decision | 保存=SQLite ＋ 最新化=cosense-cli 差分更新（next SPEC 改訂）
- nishio 判断2点: ① 渡された JSON を JSON のまま保存し続ける必要はない → on-disk store は **SQLite もしくはより良い構造**。② 最新化は export 反復でなく、**初回 export を seed にし以降 cosense-cli で最近更新ページだけ取得して差分 upsert**。
- [[persistence-custom-format]] に Update 追記（on-disk か in-memory かの Open Q を SQLite で解決、store は upsert 可能に）。新 decision [[incremental-sync]] を作成（`cosense listPages --sort updated` を delta cursor にする grounded メカニズム ＋ humanize timestamp / 削除検出 / line-id の Open Q）。
- [[cosense-cli]] の役割を「比較対象・MVP では非依存」から「**post-MVP の freshness 経路**」へ更新。旧 `SPEC.md` を改訂: M2-1 を on-disk store(SQLite, upsert 可能)に、M2-4「cosense-cli 差分更新」を追加、import adapter を bulk seed＋incremental delta の2モードに、スコープ外から「差分 index 更新」を除外。

## [2026-06-23 17:49] file back | grasp×cosense-cli 実測比較 ＋ Codex 向け次マイルストーン SPEC
- MVP 実装を同一ページ（`君主道徳と奴隷道徳`）で `cosense`（hosted, 認証済み）と同条件比較。一次データを [[cosense-cli]] に「## 実測比較」として固定。
- **速度**: grasp は全コマンド一律 ~3.4s（123MB JSON full parse が律速、cosense は 0.5–1.2s）。**機能**: grasp だけが行レベル逆リンク・赤リンク列挙・1 コール近傍同梱・オフラインを出す。cosense だけが本文/ベクトル検索・生きた状態を出す（`盲点` 検索 grasp 8 vs cosense 100）。中核仮説は成立、弱点は既知の MVP 割り切り。
- parser 残 false-positive を実測: `[** x]` 系装飾（`** 深い思考` count 59）が link 扱い → [[grasp-cli-mvp]] と旧 `SPEC.md` Open Q に記録。
- 旧 `SPEC.md` に「## 次のマイルストーン（post-MVP / step 2）」を追加: M2-1 on-disk index（latency 解消・native store seed, 最優先）/ M2-2 `search`（本文検索）/ M2-3 parser 修正。read-only 維持、write/identity はまだ。リリース（README/push）は人間判断待ちで保留。

## [2026-06-23 17:34] rename | decision ページ why-design-B → why-not-scrapbox-clone
- 「design B」は A/B fork を覚えていないと意味が通らない相対ラベルで、リンク identity / H1 として決定の中身を隠していた（nishio 指摘「タイトルが微妙」）。
- `git mv` で `decisions/why-design-B.md` → `decisions/why-not-scrapbox-clone.md`。H1 を「Scrapbox を忠実 clone せず、identity-without-name を足した『あるべき姿』を作る」に。内部呼称としての design B は本文に注記して残す（A vs B fork の論理は維持）。
- 参照を更新: CLAUDE.md / AGENTS.md / index.md / SPEC.md / persistence-custom-format.md の `[[why-design-B]]` リンク、log.md は履歴 prose を残しリンクのみ追従、cosense-json-export.md は prose の「design B」→「grasp」。

## [2026-06-23 17:33] file-back | MVP 実装知見を entity 化し、cosense-cli 可視性を記録
- 新ページ [[grasp-cli-mvp]]: `python3 -m grasp` の read-only verbs、in-memory data model、line-id 方針、wanted ranking、strict parser、実データ scale、検証、次課題を実装現状として固定。
- 新ページ [[cosense-cli]]: local 環境では `@helpfeel/cosense-cli@1.4.4` が `cosense` binary として利用可能。grasp は local export/native store、cosense-cli は hosted Cosense 操作という使い分けを記録。
- [[cosense-json-export]] 更新: broad bracket 分類値と strict parser 実装値（123170 edges / 58944 targets / 43344 wanted）を区別。lines[0] は MVP では本文に残すと確定。

## [2026-06-23 17:28] implementation | read-only Cosense JSON MVP CLI を追加
- Python package `grasp` を追加。`python3 -m grasp` / console script `grasp` で、`--export`（default: `$GRASP_EXPORT` or `raw/nishio.json`）と `--json` を受ける。
- 実装した read-only verbs: `read`（本文 + line-level backlinks + deterministic 2-hop related + page-local wanted）, `backlinks`, `wanted`; helper として `related`, `peek`, `suggest` も追加。line-id は `page.id:line-index`。Cosense title 行 `lines[0]` は本文に残す。
- Cosense parser は broad bracket 分類から厳しめに調整: 外部 URL / icon/img / decoration / math / cross-project / `[[...]]` に加え、inline backtick 内、ASCII index 風 `xs[i]` / `func()[0]`、数字のみ `[1]` を link から除外。理由: 実データで code/list 由来の `0` / `i` / `1` が `wanted` 上位を汚したため。
- strict parser で `raw/nishio.json`: 25791 pages / 724981 lines / 123170 edges / 58944 distinct targets / 43344 wanted / normalized title collision 1。以前の 133022 edges / 61613 targets / 45703 wanted は broad bracket 分類の値として残す。
- 検証: `python3 -m unittest discover -s tests` OK。実データで `wanted`, `backlinks 盲点`, `read 盲点カード`, `related 盲点カード`, JSON output を確認。毎回 118MB JSON を parse するため 1 command 約4-5秒、on-disk store は次段階の性能課題。

## [2026-06-23 16:45] ingest | Cosense JSON export の実物（raw/nishio.json, 25791 pages）を確認、import スキーマを確定
- nishio が管理画面 Export Pages（metadata ON）で出した実物を raw/ に配置 → 実スキーマを実測。SPEC が「Codex が実物で確認」と保留していた項目を確定。
- 新ページ [[cosense-json-export]]（entities/）: root/page/line スキーマ ＋ 6 gotcha。確定事項: ① **line に安定 id 無し**（138220 行で 0）→ grasp が import 時採番（原理4 と整合）。② **link graph は export に未保存**（page キーは title/id/created/updated/views/lines のみ）→ line.text を parse してエッジ materialize。③ `[...]` は overloaded（内部リンク 62.7% / 外部URL 23.4% / icon 6.7% / 装飾 3.6% / cross-project 2.8% / 数式 0.7%）、`[[...]]` は **bold でリンクでない**（grasp の `[[wikilink]]` と逆）。④ リンク解決は normalize（case-insensitive＋空白畳込, 実測 exact→normalize で 208 件だけ解決, title 衝突 1 group）。⑤ title=lines[0].text（≈99.7%）。⑥ users 2人（nishio＋garbot bot, line.userId あり）→ 単一所有前提に注釈。
- scale: 25791 pages / 724981 lines / 118MB。内部リンク instance 133022・distinct target 61613・既存解決 15702・**red link 45703** → `wanted` は ranking 必須（SPEC Open Q 確定。signal: 出現回数/views/recency）。
- 旧 `SPEC.md` 更新: line 40 の保留注記を確定事実＋[[cosense-json-export]] 参照に置換、MVP に実データ scale を追記、Open Q「read の近傍境界」に wanted ranking 必須を追記。

## [2026-06-23 15:56] decision | 保存形式 = 独自フォーマット（Markdown でない）、import は別責務、MVP = Cosense JSON export を読む
- nishio 訂正2点: ①保存形式は独自であるべき — Markdown が逆リンクメンテのしがらみの**発生源**（リンク=テキスト、逆リンクは未保存→全文スキャン or 書き戻し。独自なら逆リンク=エッジの逆読みで「維持」概念が消える）②「読める」は import の話で保存形式と独立。
- 新 decision [[persistence-custom-format]]: native=独自（Cosense の行/グラフモデルを正規化、ゼロ発明でない）。三層分離 native store ← import adapter（Cosense JSON / 後で Markdown）← CLI。「既存森40+を読める」は Markdown adapter で達成（native を Markdown にしない）。
- 旧 `SPEC.md` 更新: 保存形式/入力(import)/MVP 節を追加、データモデルを「エッジを native 保持」に、Open Q の永続化を解決済みに。MVP = Cosense JSON export 1ファイルを `read`/`backlinks`/`wanted` の読み取り専用3動詞で扱い、中核仮説を実データで検証。
- Codex への確認事項: Cosense export の実スキーマ（line-id 有無、リンク `[title]` 構文）。

## [2026-06-23 15:41] 作成 + 設計対話 ingest | grasp dev wiki を新規 scaffold し、llm-wiki での設計対話を founding pages に固定
- **由来**: nishio の llm-wiki 対話。「Cosense は複数人前提だが一人でも Markdown 集合より効く。"Co-" になる前の Scrapbox を CLI で扱える substrate が LLM に良い」→ design B を選択。
- **分業**: 本 wiki ＝ spec / 設計判断 / gotcha（Codex が読む context）、Codex ＝ 実装。
- **固定した founding pages**:
  - 旧 `SPEC.md` — CLI 動詞（read=近傍同梱 / backlinks=行つき / related=2-hop / wanted=赤リンク / write=グラフ自動更新 / transclude / rename=identity保持）＋ data model（page id / line-id / materialized backlinks）＋ 5 中核原理 ＋ Open Q。
  - [[why-not-scrapbox-clone]]（decisions/, 旧 why-design-B）— Scrapbox を Co-層 / グラフモデル層に分解、A（忠実clone, name=identity欠陥相続）vs B（あるべき姿, identity-without-name 追加）の fork で B 採用。用途は（あ）LLM-author 向け・人間UIなし。cosense-cli との区別。
- **次**: 永続化形式（既存 Markdown 互換 or 独自）の決定 → Codex に最小プロトタイプ（read / backlinks / wanted の 3 動詞、読み取り専用）を渡す。
- メタ: 親 llm-wiki の `LLM Wiki 設計のトレードオフ` 軸5（機械 vs 意味）× `名前ではなくIDで識別する設計`（identity-without-name）の収束として本プロジェクトが立った。

## [2026-06-25 00:02] ingest | ScrapBubble (takker99) を entity 化、grasp の read 模型の「双子（別消費者）」として file back
- 出典: github.com/takker99/ScrapBubble（README: "Show n-hop link destination pages beyond projects" / TypeScript+Deno / Preact / ~45 releases, 最新 0.9.15）、scrapbox villagepump/ScrapBubble・takker/takker99%2FScrapBubble、関連 villagepump/複数のprojectを透過的に扱う・takker/ScrapBubbleのcache戦略。全文 raw は raw/scrapbubble--*.json（gitignored）。
- 新ページ [[scrapbubble]]（entities/）: Scrapbox UserScript。リンク hover で**遷移せず**飛び先を吹き出し表示（text-bubble=本文 / card-bubble=関連2-hop）、逆リンクへ再帰潜行、`whiteList` で複数 project 透過、赤リンクは接続検知で blue 切替（全 project 空は全走査要）、cache-first・最大3 fetch・api/projects 更新時刻チェック、`?followRename=true` で改名追従。
- 核となる読み: **ScrapBubble = grasp の read グラフ模型を消費者だけ替えて実装した双子**（ScrapBubble=人間ブラウザ hover GUI / grasp=AI CLI）。bubble=人間版の近傍同梱。grasp の whole-store cross-project（v6）/ read=近傍同梱（[[ai-consumer-cost-and-trust]] 軸1）/ [[incremental-sync]] cache reuse / identity-without-name を**別経路で裏付ける先行例**。
- 3つの sharpening: ① `followRename` = grasp が data model で直す name=identity 欠陥を fetch 時 workaround で当てた downstream 証拠（[[why-not-scrapbox-clone]] に Update）。② `whiteList` 透過は Co-（他者 project 読み）と非 Co-（自分 public+private 統合）を束ね、grasp が継ぐ cross-project は後者だけ → cross-project は Co- 無しでも価値（[[whole-store-graph-and-cross-project-edges]] に Update、本決定が使う `[/takker/ScrapBubble]` の出元）。③ daiiz の「リンク貼って満足／育てる vs preview」deferral は come-from・第3消費者軸に接続。
- index.md に entities/ 1行追加。why-not-scrapbox-clone と whole-store-graph に各1 Update 追記。

## [2026-06-25 00:40] file back | 森全体を grasp の次 dogfood corpus にする設計対話を backlog へ
- 出典: [[scrapbubble]] ingest から派生した nishio との設計対話（2026-06-25）。前提整理は本セッションの ScrapBubble entity と whole-store 決定の Update（cross-project の Co-/非 Co- 2層分解）。
- [[grasp-backlog]] の「grasp 自身の wiki を最初の dogfood corpus にする」に 2026-06-25 subsection を追加: corpus を grasp 1 wiki → **wiki森全体（40+ 単一所有者 wiki）**へ拡張。動機＝森は親 llm-wiki `wiki_search.py` の grep 横断止まり＝節点アクセス (a-1)、「N wiki を跨いで参照されるが本文が無い概念」＝俯瞰グラフ (a-2) は出せない。grasp の whole-store cross-project + Markdown mirror が (a-2) を供給。森は全部 nishio 所有＝Co- を削ぐ grasp の cross-project（非 Co- 横断）の理想 corpus。
- 核心: **森用の特別 edge policy は不要**（nishio「import 時バラバラ→query で徐々に有機結合」）。cross-wiki プレーン名参照は import 時に裸の赤 node のまま、[[whole-store-graph-and-cross-project-edges]] point 8 の弱い接続（normalize-title 一致）が query 時に繋ぐ。「束の束」は query 時結合を待つ正常な初期状態（親 llm-wiki `書いてから整理する` の森スケール版）、誤接続は weak 層に封じ込み。
- 論点: 40+ wiki の namespace import オーケストレーション / navigation・log artifact 森規模除外 / raw/ 除外（llm-wiki-about-nishio md 24,968 件）/ weak 接続の cross-wiki spread ranking。森メタ側は親 llm-wiki `wiki-forest-utilization-design-20260610` に file back。

## [2026-06-25 02:00] 整理 | grasp-backlog を「未実装項目だけ」に再構成（412→251行）
- 動機: 次の開発前に backlog を整理。旧 backlog は実装済みの作業ログ（read --around-line / search --context / mentions / co-links / gather / path / acquire 系など）と却下の経緯を本文に抱えて 412 行に膨らみ、未実装項目が埋もれていた。
- 方針（分業 + ページルールに沿う）: 実装済み narration は [[grasp-v1-implemented]]（current facts の SSoT）と本 [[log]]（*いつ* やったかの時系列）に既に二重記録されているので backlog からは消す。事実は失われない（v1-implemented に全 surface が載っていることを突き合わせ確認）。却下案（`--cluster` / `--strip-decoration`）は経緯を畳んで各節末「却下（再提案しない）」の理由つき1行ガードに。設計根拠は `decisions/` / `concepts/` 側にあり backlog はリンクのみ。
- 残したもの: 未実装項目（parser 監査 / Markdown mirror 残 / 森 dogfood 拡張 / navigation・log artifact handling / write・identity 層 / typed link / stable line identity / search recall 残 / gather・mentions・co-links 残課題 / use-case report / come-from declare・render / path・backlinks ranking / sync freshness / cross-project v6 / acquisition 残 / packaging）と、それらに効く settled な設計制約 + 出典リンク。
- 検証: `python3 scripts/lint_wiki.py`（broken link / orphan 増なし）/ `python3 -m unittest discover -s tests`。コード変更なし、wiki のみ。

## [2026-06-25 02:04] implementation | Markdown import の first H1 title resolution を実装
- `grasp import --markdown <folder>` の title resolution を frontmatter `title` → first H1 → file stem に変更。first H1 extractor は frontmatter と fenced code block 内の `# ...` を title とみなさない。file stem は従来通り alias として残るため、`[[file-stem]]` は canonical H1 title へ解決する。
- H1 title が変わると manifest の title / alias map が変わるので、既存の safe full rebuild path に乗る。SQLite table shape は変えないため schema は `5` のまま、public compatibility version は `1.5.25`。既存 Markdown store はそのまま読めるが、H1 title を反映するには `grasp import --markdown <folder>` の再実行が必要。
- file back: [[grasp-v1-implemented]] の Markdown facts を更新し、[[grasp-backlog]] から first H1 title resolution を削除。[[markdown-obsidian-indexed-mirror]] の Open Question から title resolution 問いを閉じ、[history](history.md) に `1.5.25` を追加。README も title resolution 説明を更新。
- 検証: bundled Python 3.12.13 で `python3 -m unittest tests.test_markdown` / `python3 -m unittest discover -s tests` / `python3 scripts/lint_wiki.py` / `git diff --check` OK。system `/usr/bin/python3` は 3.9.6 で package の `>=3.10` 要件を満たさず、既存 union type で失敗する。

## [2026-06-25 02:17] correction | `#1` noise は log 除外でなく edge annotation 問題
- nishio 指摘: grasp wiki dogfood で見えた `log.md` が graph を汚す問題と、`PR #2` / `Open Q #4` のような `#1` 系が hashtag edge になる問題は別。前者は page/file の artifact handling、後者は link-shaped expression が意味ある概念リンクかの annotation 問題。
- 方針修正: Scrapbox 互換では `#1` は link として成立するので parser で消さない。人間は必要なら `` `#1` `` のように escape してきた。grasp 側は edge を保持したまま、system / LLM / human が「表現としてはリンクだが意味リンクではない」と annotation し、`unresolved` / `related` / `path` ranking で弱く扱う。
- file back: [[grasp-backlog]] に link-shaped but non-semantic edge annotation 節を追加。[[markdown-obsidian-indexed-mirror]] に correction を追記し、log/navigation artifact handling と edge annotation を混同しないよう明記。

## [2026-06-25 02:39] implementation | issue-number hashtag edge の system annotation を追加
- `PR #2` / `Open Question #4` のような numeric hashtag edge に system `semantic_annotation` を付ける初期 heuristic を追加。annotation は `semantic_role=issue-number`, `graph_scope=non-semantic`, `annotator=system`。parser は edge を捨てず、`Edge.to_dict()` / path edge example / unresolved examples に annotation を出す。
- `unresolved` は既定で少し多めに候補を取得し、sampled examples がすべて non-semantic な target を ranking の後ろへ回す。`link_stats("2")` など raw edge count は保持する。永続 annotation table / LLM annotation workflow / `related`・`path` の本格 ranking policy は未実装として [[grasp-backlog]] に残す。
- dogfood: temp store で `wiki/` を import し、`PR #2` / `PR #1` / `Open Q #4` 由来 target に annotation が付くことを確認。`[[..]]` 由来の `..` は別の link-shaped non-semantic 表現として未対応。
- file back: [[grasp-v1-implemented]] に current facts、[history](history.md) に `1.5.26`、[[grasp-backlog]] に残課題を反映。
- 検証: bundled Python 3.12.13 で `python3 -m unittest discover -s tests` / `python3 scripts/lint_wiki.py` / `git diff --check` OK。

## [2026-06-25 02:44] implementation | Markdown navigation/log artifact の outgoing edges を content graph から除外
- `grasp import --markdown` が `index.md` / `forest-index.md` / `maps/` / `views/` / frontmatter `role: navigation` を navigation、`log.md` / `log/*.md` / frontmatter `type: log-entry` を log artifact と分類し、これらの outgoing edges を既定 content graph から除外するようにした。本文 lines は store に残るため `search` は従来通り hit する。
- Markdown manifest version を `2` に更新し、`graph_role` を manifest identity に含めた。既存 Markdown project は次回 re-import で safe full rebuild される。SQLite schema は v5 のまま、public compatibility version は `1.5.27`。
- dogfood: temp store で `wiki/` を import し、32 pages / 3831 lines / 365 edges / unresolved 5。前回の同条件 580 edges から log/index outgoing edges が落ち、`read grasp backlog` の backlinks から `Log` が消えた。一方で `search "first H1"` は `Log` に hit し、検索対象として残ることを確認。
- file back: [[grasp-v1-implemented]] / [history](history.md) / [[grasp-backlog]] / [[markdown-obsidian-indexed-mirror]] を更新。
- 検証: bundled Python 3.12.13 で `python3 -m unittest discover -s tests` / `python3 scripts/lint_wiki.py` / `git diff --check` OK。

## [2026-06-25 02:50] dogfood | Markdown LLM Wiki が grasp 経由で LLM context として使えるかを検証
- temp store に `wiki/` を `import --markdown wiki --project grasp-wiki` し、32 pages / 3836 lines / 365 edges / unresolved 5 として materialize できることを確認。
- `search "non-semantic" --context 2` は `Log` だけでなく [[grasp-backlog]] と [[markdown-obsidian-indexed-mirror]] の該当行を line_id + 周辺文脈つきで返した。`search "first H1"` は [[grasp-v1-implemented]] / [[grasp-backlog]] / decision / `Log` の実装履歴を拾い、Markdown に file back した current facts と履歴が CLI から再利用できることを確認。
- `read "grasp backlog" --related-snippets --related-snippet-mode edge` は本文・行レベル backlinks・2-hop related・page-local unresolved を同梱し、`backlinks "grasp backlog"` / `related "grasp backlog"` は `Log` に支配されず content pages を返した。`search` では `Log` が残るが、artifact outgoing edge 除外により graph 近傍の汚染は抑えられている。
- `unresolved` は `#2` / `#4` 系 target に system `semantic_annotation` を出し、`path "grasp backlog" "entity: grasp v1 implemented surface"` は根拠 line つき direct path を返した。現状の答え: **Markdown の LLM Wiki に書き込まれたものは、再 import 後、Cosense export と同じ `search` / `read` / `backlinks` / `related` / `path` primitives で LLM が使える**。未解決の差は hosted 最新性や write layer で、Markdown mirror 自体は read-only indexed graph として成立している。

## [2026-06-25 02:54] file back | Markdown mirror dogfood の結論を current facts / decision へ昇格
- 直前の dogfood 結論を [[markdown-obsidian-indexed-mirror]] と [[grasp-v1-implemented]] へ反映。log だけでなく、Markdown mirror の決定根拠と実装済み facts から「file back された Markdown LLM Wiki は再 import 後に LLM context として使える」と読めるようにした。

## [2026-06-25 02:59] implementation | Markdown import に heavy directory 除外を追加
- `grasp import --markdown <folder>` に `--markdown-exclude-dir <name>` を追加。指定した directory basename 配下の `.md` を再帰 import から除外する。森スケール dogfood で `raw/` の大量 source md を mirror に混ぜないための前提。
- Markdown manifest version を `3` に更新し、exclude dirs を manifest identity に含めた。exclude 条件を変えて同じ project を re-import した時は safe full rebuild する。SQLite schema は v5 のまま、public compatibility version は `1.5.28`。
- file back: [[grasp-v1-implemented]] / [history](history.md) / [[grasp-backlog]] / [[markdown-obsidian-indexed-mirror]] / README / Skill を更新。
- 検証: bundled Python 3.12.13 で `python3 -m unittest discover -s tests`（63 tests）/ `python3 scripts/lint_wiki.py` / `git diff --check` OK。temp store で `grasp --json --store <tmp> import --markdown wiki --project grasp-wiki --markdown-exclude-dir raw` も成功。

## [2026-06-25 03:10] dogfood | wiki森全 entries の Markdown import を temp store で検証
- `/Users/nishio/llm-wiki/wikis.yaml` の 42 entries を対象に、各 `<path>/wiki` を temp store へ `import --markdown --project <name> --markdown-exclude-dir raw` で投入。内容本文は読まず、件数・時間・失敗型だけ観測。
- 結果: 37 entries 成功 / 5 entries 失敗 / missing folder 0。成功分 aggregate は 37 projects / 2458 pages / 213,309 lines / 22,550 edges / 1,412 unresolved。合計 import wall time は約 22.3 秒。`stats` は schema v5 / schema_ok true。
- 失敗はすべて duplicate title / alias collision。典型は draft variants の同一 H1、複数 directory の `_overview` / `README` / `index` file stem alias、source/session file と canonical page の alias 衝突。次 blocker は raw 除外や performance でなく collision policy。
- file back: [[grasp-backlog]] の duplicate title / alias collision と wiki森 import orchestration、[[markdown-obsidian-indexed-mirror]] の dogfood section に反映。

## [2026-06-25 13:04] file back | wiki森 import dogfood を独立 analysis page に昇格し、次計画を整理
- 新ページ [[wiki-forest-markdown-import-dogfood-2026-06-25]] を作成。log/backlog/decision に散っていた dogfood 結果を、Result / Analysis / Plan / Open Questions として coding agent が読める source of truth にした。
- 新計画: collision diagnostics → alias collision softening → draft/source artifact 除外 → forest import orchestration。orchestration は 37/42 成功で価値ありだが、先に collision policy を入れないと失敗集計 command になる。
- repo-local Codex plugin `/next` 用の未コミット差分（AGENTS / `.agents/plugins/marketplace.json` / `plugins/grasp-next/`）もユーザ指示により commit 対象にする。

## [2026-06-25 13:31] implementation+file back | Markdown collision diagnostics と identity/name 計画修正
- Markdown mirror の duplicate title / id / alias collision を `MarkdownCollisionError` と structured diagnostic にした。`grasp --json import --markdown ...` は collision kind / normalized key / paths / entries を stderr JSON に出す。
- ユーザ指摘により、alias collision softening は単なる workaround ではなく `identity-without-name` の本体問題として扱う方針に修正。path は一意性の根拠として diagnostic / fallback handle に使えるが、path-qualified string を page name へ混ぜない。
- 次は alias collision policy（identity=path/id、name=display/link handle の表現）と `drafts/` / `source/` artifact 除外を検討し、`import-forest` orchestration は急がない。

## [2026-06-25 14:03] implementation+file back | ResourceWarning 修正と Markdown identity/name collision decision
- `tests/test_cli_help.py` の raw `sqlite3.connect` を明示 close に修正。Python sqlite3 の connection context manager は commit/rollback 用であり close しないため、ResourceWarning の原因になっていた。
- 新 decision [[markdown-identity-name-collision-policy]] を追加。duplicate title / alias は import UX ではなく、visible handle が複数 page identity に束縛される問題として扱う。path は source address / fallback selection key であり、page name へ混ぜない。
- 次の実装順は artifact reduction（`drafts/` / `source/` 除外または `graph_role=artifact`）→ schema v6 `page_handles` → ambiguous query result。`import-forest` は引き続き急がない。

## [2026-06-25 14:18] correction | `source/` digest は default exclude しない
- nishio 指摘: LLM Wiki の `source/` は `raw/` を読んで作成した digest / source-backed synthesis なので、`raw/` と同列に除外すべきではない。
- 修正方針: `raw/` は heavy original dump として除外候補、`drafts/` / generated temp は artifact reduction 候補。`source/` は保持し、必要なら `graph_role=source` / evidence layer / ranking policy で canonical synthesis と扱いを分ける。
- [[wiki-forest-markdown-import-dogfood-2026-06-25]] / [[grasp-backlog]] / [[markdown-identity-name-collision-policy]] / [[markdown-obsidian-indexed-mirror]] の `draft/source artifact 除外` 表現を修正。

## [2026-06-25 14:30] implementation+file back | Markdown source role と artifact role を実装
- Markdown import が `source/` / `sources/` / frontmatter `role/type: source` を `graph_role=source` と分類するようにした。`source` role は raw digest / source-backed synthesis なので、content と同じく outgoing edges を materialize する。
- `drafts/` / generated temp / frontmatter `role/type: artifact|draft|generated` は `graph_role=artifact` と分類し、search には残すが outgoing edges は除外する。これは duplicate title を許す実装ではなく、handle ambiguity は schema v6 `page_handles` の残件。
- public compatibility version を `1.5.29` に更新。SQLite schema と Markdown manifest version は不変。

## [2026-06-25 16:39] implementation+file back | schema v6 page_handles と read ambiguity を実装
- SQLite schema を v6 に更新し、`page_handles` table を追加。Cosense title と Markdown title / alias / source path / graph_role を page identity `(project,page_id)` とは別に materialize する。
- `read <handle>` は visible handle が複数 page identity に束縛される時、暗黙に片方を選ばず `ambiguity.type=handle_ambiguity` と候補 page_id / path / graph_role を返す。`read --page-id <id>` / `read --path <relative-path>` で identity を明示できる。
- Markdown folder import も import cache manifest に `source_type=markdown` / `exclude_dirs` 付きで保存し、schema mismatch recovery が Cosense JSON copy だけでなく Markdown mirror も再構築できるようにした。
- 残件: Markdown import は duplicate title / alias をまだ hard error にする。`backlinks` / `related` / `link-stats` / outgoing edge resolution も ambiguous handle を first-class に扱う段階は未実装。

## [2026-06-25 16:42] dogfood | schema v6 で wiki森 Markdown import smoke
- `/Users/nishio/llm-wiki/wikis.yaml` の 42 entries を対象に、temp store へ `import --markdown --project <name> --markdown-exclude-dir raw` を再実行。private 本文は出力せず aggregate / failure type のみ観測。
- 結果: 37 success / 5 failure / missing 0。成功 aggregate は schema v6 / schema_ok true / 37 projects / 2460 pages / 213,526 lines / 22,569 edges / 1,412 unresolved、wall time 約 25.8 秒。
- 失敗型は `markdown_collision` のまま（alias collision 4、alias+title collision 1）。v6 `page_handles` は成功 project の import を壊していないが、Markdown import softening は未実装なので 5件の blocker は残る。

## [2026-06-25 19:07] implementation+dogfood | schema v7 edge resolution と Markdown collision softening
- SQLite schema を v7 に更新し、`edges` に `target_handle` / `target_handle_norm` / `target_page_id` / `resolution_status` を追加。`page_handles` から `resolved_unique` / `ambiguous` / `unresolved` を materialize し、ambiguous handle を unresolved target や existing page backlink と誤分類しないようにした。
- Markdown duplicate title / alias は import 全体を止めず、`read <handle>` の ambiguity 候補として surface する。`link-stats <handle>` も ambiguity を返し、recovery hints へ誤分類しない。duplicate frontmatter `id` は identity 衝突なので hard error のまま。
- wiki森 smoke: `/Users/nishio/llm-wiki/wikis.yaml` 42 entries を temp store へ同条件で import し、42 success / 0 failure / missing 0。aggregate は schema v7 / schema_ok true / 42 projects / 3338 pages / 264,963 lines / 23,180 edges / 1,627 unresolved、wall time 約 22.1 秒。
- 検証: `python3 -m unittest discover -s tests`（68 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。
- 残件: `backlinks <ambiguous handle>` の UX と JSON contract、forest import orchestration、whole-store cross-project edge との統合。

## [2026-06-25 19:18] file back | whole-store cross-project の「v6」呼称を current schema 番号から切り離し
- Codex が wiki を読んだ時点で、[[whole-store-graph-and-cross-project-edges]] は「v6 decision / `SCHEMA_VERSION = "6"`」のままだが、実際の schema v6 は `page_handles`、schema v7 は edge `resolution_status` と Markdown collision softening に使われ済みだった。これは今後の実装者に「cross-project は schema 6 で実装する」と誤読させる stale point。
- 修正: 決定の中身は有効な design intent として維持し、当初の「v6」は歴史的ラベルへ降格。今後は **whole-store cross-project decision** と呼び、実装時点の next schema generation で `target_project` / `link_kind` / `connection_strength` / whole-store retrieval を入れる、と明記した。
- [[grasp-backlog]] / [index](index.md) / [[scrapbubble]] / [[multi-project-store]] の current-facing 表現から「v6」を implementation target として読める箇所を外した。過去の [[log]] entry と schema v6/v7 実装済み事実（Markdown identity/name collision）は履歴として保持。

## [2026-06-25 19:36] implementation+file back | ambiguous backlinks の handle/candidate 分離
- `backlinks <ambiguous handle>` は `resolution_status=ambiguous` / `ambiguity` を返し、`backlinks[]` と `handle_backlinks.items[]` には ambiguous handle 自体への incoming lines を返すようにした。これが primary facts。
- 候補 page ごとの確定 backlinks は `candidate_backlinks[]` に分けて返す。`[[Shared]]` のような曖昧リンクは候補 page に自動割当しない。
- schema は v7 のまま。public compatibility version は `1.7.1`。
- 検証: `python3 -m unittest discover -s tests`（68 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-25 19:53] implementation+file back | forest-level ambiguity report を追加
- `ambiguities` command を追加。`page_handles` の 1:N handle を store 全体または selected project で列挙し、project 別 ambiguous handle count / ambiguous incoming link count / source page count と、各 handle の bounded candidates を返す。
- `--project` 未指定時は `read` 系と違い、複数 project store でも全 project を scan する。forest import 後に「どの wiki / handle が曖昧か」をまず把握するための report surface。
- schema は v7 のまま。public compatibility version は `1.7.2`。
- 検証: `python3 -m unittest discover -s tests`（69 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-25 23:02] implementation+file back | `import-forest` orchestration を追加
- `import-forest <wikis.yaml>` command を追加。top-level `wikis:` entries の `name` / `path` を読み、各 `<path>/<wiki-dir>` を project `<name>` として Markdown import する。`--wiki-dir .` なら path 自体を wiki として扱う。
- per-entry failure / missing / skipped は全体を止めず `projects[]` の diagnostics として返す。結果には success/failure/missing/skipped counts、aggregate pages/lines/edges/unresolved、post-import `ambiguities` summary が入る。
- schema は v7 のまま。public compatibility version は `1.7.3`。
- dogfood: `/Users/nishio/llm-wiki/wikis.yaml` を temp store に `--markdown-exclude-dir raw` で実行し、42 success / 0 failure / 0 missing / 0 skipped。aggregate は 42 projects / 3338 pages / 265,012 lines / 23,183 edges / 1,627 unresolved、ambiguous handles 8、wall time 6.025 秒。
- 検証: `python3 -m unittest discover -s tests`（73 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-25 23:08] implementation+file back | `related <ambiguous handle>` の handle/candidate 分離
- `related <ambiguous handle>` は `resolution_status=ambiguous` / `ambiguity` を返し、primary `related[]` には ambiguous handle 自体へ incoming している source pages を返すようにした。
- 候補 page ごとの existing-page related は `candidate_related[]` に分けて返す。`backlinks` と同様、曖昧リンクを候補 page へ自動割当しない。
- schema は v7 のまま。public compatibility version は `1.7.4`。
- smoke: 小さい Markdown fixture で `related Shared --json` が `related=Source:ambiguous-handle-source`、`candidate_related=A:B,B:A` を返すことを確認。
- 検証: `python3 -m unittest discover -s tests`（73 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-25 23:29] implementation+file back | `cross-project-spread` weak spread surface を追加
- `cross-project-spread <title>` command を追加。normalized title が selected/all projects で materialized page handle / ambiguous handle / unresolved target / incoming link としてどれだけ広がるかを project label 付きで返す。
- 出力は `connection_strength=weak-normalized-title` と明示し、page identity は `(project,page_id)` のまま merge しない。これは whole-store cross-project decision の full schema 実装ではなく、schema v7 compatible な観測 surface。
- schema は v7 のまま。public compatibility version は `1.7.5`。
- smoke: 3 project の Markdown fixture で `Shared` が resolved_unique / ambiguous / unresolved の各 signal として集計され、`signal_project_count=3`、`ambiguous_project_count=1`、`unresolved_project_count=1` を返すことを確認。
- 検証: `python3 -m unittest discover -s tests`（74 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 00:03] implementation+dogfood+file back | `cross-project-spreads` ranking を追加
- wiki 森 temp store で `cross-project-spread <title>` を dogfood。42 projects / 3338 pages / 265,031 lines / 23,183 edges / 1,627 unresolved は import 成功したが、query 指定版だけでは seed title が必要で、`index` / `log` / `overview` / numeric-only handles が上位を潰すことが分かった。
- `cross-project-spreads` command を追加。normalized handle を project spread で rank し、seed title なしに weak cross-project signal を発見できる。`structural-name` / `numeric-only` / `artifact-only` は消さずに rank band で下げる。
- dogfood: total normalized handles 6,131、`min_projects=2` で 211 handles。rank band 調整後の上位 concept-like は `nishio` / `ブロードリスニング` / `Plurality` / `Kozaneba` などになった。
- schema は v7 のまま。public compatibility version は `1.7.6`。
- 検証: `python3 -m unittest discover -s tests`（74 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 00:10] file back | LLM Wiki migration target = native authority + Markdown projection
- nishio と合意: LLM Wiki のインフラを Markdown の束から grasp へ移す時、Markdown は出力し続けるが authority ではなく generated projection にする。人間や Codex が直接 Markdown を編集するのではなく、`grasp write` が native store を更新し、そこから Markdown を再生成する。
- 新 decision [[native-authority-markdown-projection]] を追加。native store（＋ durable journal）を source of truth、Markdown を review / backup / publish / interoperability 用 projection とする。direct Markdown edit は cutover 前の source import か emergency path に限定する方向。
- [[write-layer-alpha-and-replay-test]] に cutover 後の原典関係を追記。[[persistence-custom-format]] には「Markdown を保存形式にしない」は「Markdown を捨てる」ではなく projection へ降ろすことだと追記。[[grasp-backlog]] には `export-markdown` / status-diff-revert / durable journal policy を write 層の未実装項目として追加。

## [2026-06-26 00:11] implementation+file back | `suggest` を asearch-style fuzzy title retrieval に拡張
- nishio 指摘: タイトルが長文であり、タイトルを知っている前提だと見つけられない問題は、Cosense では asearch algorithm による曖昧検索と後続の embedding 検索が解いていた。
- `suggest` の既定を fuzzy に拡張。exact / prefix / substring を優先しつつ、長文 title に対する空白区切り断片一致と文字順序近似を返す。JSON suggestion は `match_mode` / `match_score` / `matched_terms` を持つ。`--mode substring` で従来の厳密部分一致に戻せる。
- smoke: wiki 森 temp store の `llm-wiki` project で `suggest '書字 副産物'` と `suggest '再会書字委譲'` が `再会は書字のタダの副産物で、委譲が奪った` を返した。
- schema は v7 のまま。public compatibility version は `1.7.7`。
- 検証: `python3 -m unittest discover -s tests`（75 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 00:17] planning | LLM Wiki infra fast-path plan を backlog と分離して追加
- nishio 指示: 今の backlog とは別に、最速で LLM Wiki のインフラとして grasp を使えるようにするための計画表を作る。
- 新ページ [llm-wiki-infra-fast-path-plan](llm-wiki-infra-fast-path-plan.md) を追加。[[native-authority-markdown-projection]] を実運用へ落とすため、journal contract → adopt one wiki → export projection → minimal write → status/diff/revert → rename → file-back integration → one-wiki cutover → forest rollout の phase 表にした。
- 最初の slice は Phase 0-3: journal schema、`adopt-markdown`、`export-markdown --check` no-op、`append-section` + `append-log`。rename は `2.0.0` 境界には必要だが、日常 file-back dogfood 開始の blocker にはしない。

## [2026-06-26 00:26] implementation+file back | line window が stored line_id を返すように修正
- `page_lines_around` が `around_line_id` を `page.id:line-index` で合成していたため、stable line identity の前段として stored `lines.line_id` を返すようにした。`read --around-line` と `search --context` の context window が opaque line id を保持できる。
- これは stable line identity の完全実装ではない。Cosense / Markdown import はまだ line id を positional に mint する。journal replay / re-import diff で stable id を維持する作業は [[llm-wiki-infra-fast-path-plan]] Phase 1 以降。
- fast-path plan には、Phase 0-3 は append-only authoring alpha であり identity-without-name の差別化 claim は rename slice 以降、という注記を足した。
- schema は v7 のまま。public compatibility version は `1.7.8`。
- 検証: `python3 -m unittest discover -s tests`（76 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 00:31] implementation+file back | journal event JSONL contract を固定
- `grasp.journal` module を追加。journal schema v1、event types `page_create` / `page_update` / `section_append` / `page_rename` / `log_append` / `projection_export`、canonical JSONL encode、append、read validation を固定した。
- これは [[llm-wiki-infra-fast-path-plan]] Phase 0 の前処理。まだ `adopt-markdown` / replay / write CLI / projection export は未実装。
- schema は v7 のまま。public compatibility version は `1.7.9`。
- 検証: `python3 -m unittest discover -s tests`（80 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 00:44] implementation+dogfood+file back | `adopt-markdown` と `export-markdown --check` を追加
- `adopt-markdown <folder>` command を追加。Markdown folder を既存 import path で SQLite materialized index に入れ、各 page を `page_create` event として JSONL journal に append する。既存 journal は `--replace-journal` なしでは上書きしない。
- `export-markdown --output <folder> --check` command を追加。Markdown-backed project の stored lines を source path へ projection し、既存 files と比較する。差分があれば `ok=false` で exit 1。通常実行では changed / missing files を書くが、extra files は削除しない。
- dogfood: temp store で repo `wiki/` を `adopt-markdown wiki --project grasp-wiki` し、`export-markdown --output wiki --check` が 36 files / changed 0 / missing 0 / extra 0 で clean。
- これは [[llm-wiki-infra-fast-path-plan]] Phase 1-2 の最小 no-op gate。まだ replay / write CLI / semantic index-log regeneration は未実装。
- schema は v7 のまま。public compatibility version は `1.7.10`。
- 検証: `python3 -m unittest discover -s tests`（81 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 08:35] docs+lint | history を箇条書きへ変更し commit 時刻を分まで表示
- [[history]] の Version history を表から箇条書きへ変更。各 entry は version / 更新 commit 時刻（JST, 分まで）/ store / compat / changes を一行で持つ。
- version / schema / compatibility の内容は変えず、`Date` だけを `git blame --line-porcelain wiki/history.md` 由来の committer time に置き換えた。
- 検証: `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 10:00] implementation+dogfood+file back | `append-section` / `append-log` alpha write を追加
- `append-section <title>` と `append-log` command を追加。Markdown-backed project の unique handle page に lines を追記し、SQLite `lines` / `edges` / unresolved / counts を更新し、`section_append` / `log_append` journal event を append し、Markdown projection を export する。
- dogfood: temp copy の repo `wiki/` を `adopt-markdown` し、`append-section llm-wiki-infra-fast-path-plan` と `append-log` を実行した後、`export-markdown --check` が 36 files / changed 0 / missing 0 / extra 0 で clean。
- これは [[llm-wiki-infra-fast-path-plan]] Phase 3 の append-only slice。まだ `write page` / replay / status / diff / revert / rename は未実装で、ambiguous handle には書かない。
- schema は v7 のまま。public compatibility version は `1.7.11`。
- 検証: `python3 -m unittest discover -s tests`（82 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 10:24] implementation+dogfood+file back | append alpha の status / diff / revert を追加
- `write-status`, `write-diff`, `revert-event <event-id>` command を追加。`write-status` は journal 件数・last event・projection check、`write-diff` は current filesystem -> stored projection の unified diff、`revert-event` は `section_append` / `log_append` の inserted lines が現在も page tail にある時だけ削除する。
- journal event type に `event_revert` を追加。revert は対象 event を消さず、取り消し event を append する。non-tail event は拒否し、後続編集を silently damage しない。
- dogfood: temp copy の repo `wiki/` で adopt→append-section→write-status→write-diff→revert-event→export-markdown --check を実行。status は projection ok / journal events 37、diff_count 0、revert removed_lines 3、last_event `event_revert`、最終 check clean。
- これは [[llm-wiki-infra-fast-path-plan]] Phase 4 の最小 recovery slice。まだ `write page` / replay / rename / general revert / projection export 失敗時 rollback は未実装。
- schema は v7 のまま。public compatibility version は `1.7.12`。
- 検証: `python3 -m unittest discover -s tests`（82 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 10:31] implementation+dogfood+file back | `replay-journal` で append/revert journal を再生
- `replay-journal --journal <events.jsonl> --output <folder> [--check]` command を追加。SQLite store を読まず、JSONL journal の `page_create` / `section_append` / `log_append` / `event_revert` を strict replay して Markdown projection を reconstruct / compare / write する。
- replay は multiple project journal では `--project` を要求する。`event_revert` は replay 上でも removed lines が page tail に一致する場合だけ適用する。`page_update` / `page_rename` replay はまだ未実装。
- dogfood: temp copy の repo `wiki/` で adopt→append-section→revert-event 後、`replay-journal --check` が existing projection と clean。空 folder へ replay write すると 36 files written、その folder への replay check も clean。
- これは [[llm-wiki-infra-fast-path-plan]] Phase 4 の recovery を journal authority 側へ寄せる前処理。
- schema は v7 のまま。public compatibility version は `1.7.13`。
- 検証: `python3 -m unittest discover -s tests`（82 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 11:03] implementation+dogfood+file back | `write-page` と `page_update` replay/revert を追加
- `write-page <title>` command を追加。Markdown-backed project の unique handle page の本文行を `--from-file` または repeat `--line` で全置換し、SQLite `lines` / outgoing `edges` / unresolved / counts を更新し、`page_update` event に before/after lines を記録し、Markdown projection を export する。title / aliases / source path / page id は変えない。
- `revert-event` が `page_update` に対応。current lines が target event の after lines と一致する場合だけ before lines へ戻す。`replay-journal` も `page_update` とその `event_revert` を strict replay する。
- dogfood: temp copy の repo `wiki/` で `write-page llm-wiki-infra-fast-path-plan --from-file /tmp/page.md` → `revert-event` → `replay-journal --check` → `export-markdown --check` を実行。write_lines 4 / write_edges 1、revert restored_lines 75、最終 replay/check とも clean。
- これは [[llm-wiki-infra-fast-path-plan]] Phase 3 の `write page` 最小実装。まだ rename / source-path 変更 / semantic index-log regeneration / general revert は未実装。
- schema は v7 のまま。public compatibility version は `1.7.14`。
- 検証: `python3 -m unittest discover -s tests`（82 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 11:17] implementation+dogfood+file back | `rename-page` と `page_rename` replay/revert を追加
- `rename-page <target> <new-title>` command（alias `rename`）を追加。Markdown-backed project の page id を保ったまま title と optional source path を変更し、旧 title / old file stem を alias handle に残す。incoming `[[旧名]]` の surface text は書き換えず、edge resolution を新 handle table で再計算する。
- first H1 が旧 title と一致する場合だけ、同じ line_id のまま `# <new-title>` に更新する。frontmatter `title:` 追従はまだ未実装。
- `page_rename` journal event を append し、`replay-journal` と `revert-event` が `page_rename` に対応。revert は current lines / title / source path が target event の after state と一致する時だけ previous state へ戻す。
- dogfood: temp wiki で `Old.md`（`# Old`）と `A.md`（`[[Old]]`）を adopt し、`rename-page Old New --new-path New.md` → `read Old` → `replay-journal --check` → `revert-event` → `replay-journal --check` を実行。`read Old` は title `New` に解決し backlink count 1、rename/revert 後の projection と replay は clean。
- これは [[llm-wiki-infra-fast-path-plan]] Phase 5 の最小 rename slice。まだ semantic index-log regeneration / direct re-import 後の alias 永続化 / general revert / projection export 失敗時 rollback は未実装。
- schema は v7 のまま。public compatibility version は `1.7.15`。
- 検証: `python3 -m unittest discover -s tests`（83 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 12:40] implementation+dogfood+file back | rename identity を projection frontmatter に保持
- `export-markdown` と `replay-journal` の Markdown projection が、path-derived id / first H1 / aliases だけでは identity が失われる page に限って `id` / `title` / `aliases` frontmatter を生成するようにした。既存 frontmatter が同じ identity metadata を持つ場合は触らない。
- rename 後の `New.md` には旧 page id と旧名 alias が projection されるため、generated Markdown を direct `import --markdown` しても page id と `Old` alias が残る。
- dogfood: temp wiki で `Old.md` + `A.md`（`[[Old]]`）を `rename-page Old New --new-path New.md` した後、generated `New.md` を別 store に direct import。`read Old` は同じ page id / title `New` / backlink count 1 を返し、`export-markdown --check` も clean。
- これは [[llm-wiki-infra-fast-path-plan]] Phase 5 の rename slice の穴埋め。まだ semantic index-log regeneration / 任意 frontmatter merge / general revert / projection export 失敗時 rollback は未実装。
- schema は v7 のまま。public compatibility version は `1.7.16`。
- 検証: `python3 -m unittest discover -s tests`（84 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 13:07] implementation+dogfood+file back | 実 git history の rename replay test を追加
- `tests/test_git_history_replay.py` を追加。`d4e4c39^` の `wiki/decisions/why-design-B.md` と旧参照 pages を fixture にし、`rename-page --target path decisions/why-design-B.md ... --new-path decisions/why-not-scrapbox-clone.md` で実履歴 rename を再現する。
- test は redirect stub が残らないこと、旧 `[[why-design-B]]` surface text が書き換えられないこと、旧 handle `why-design-B` で read/backlinks が新 page title に解決すること、`replay-journal --check` と generated Markdown の direct re-import 後 read/backlinks が通ることを確認する。
- projection frontmatter は aliases だけでは生成しないよう条件を絞った。通常 page の file-stem alias だけで no-op projection が崩れないよう、repo `wiki/` temp import → `export-markdown --check` 36 files clean を確認。
- これは [[llm-wiki-infra-fast-path-plan]] Phase 5 の done check を実データに寄せる test。まだ semantic index-log regeneration / 任意 frontmatter merge / general revert / projection export 失敗時 rollback は未実装。
- schema は v7 のまま。public compatibility version は `1.7.17`。
- 検証: `python3 -m unittest discover -s tests`（85 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check`, repo `wiki/` temp import → `export-markdown --check` は通過。

## [2026-06-26 13:20] research+file back | ScrapBubble / hosted REST を import 改善目線で再読
- `takker99/ScrapBubble` current code と `@cosense/std@0.31` / `@cosense/types@0.11` / `@helpfeel/cosense-cli` 1.4.4 を読み、JSON export に無い hosted REST metadata を整理した。
- REST page は stable `lines[].id` / `commitId` / resolved `links` / `projectLinks` / `relatedPages` / `linked` / `pageRank` を返す。JSON export は bulk seed として有用だが、sync / acquire でこの metadata を補助列として取り込む余地がある。
- rename/delete については、recent updated window だけでは不足。`listPages` full manifest reconcile（remote page id set と local id set の比較）を主軸にし、認証済み path では `/api/commits/:project/:pageId` の `TitleChange`、`/api/deleted-pages/:project/:pageId`、`/api/stream/:project` の `page.delete` を補助に使う案を [[incremental-sync]] と [[grasp-backlog]] に追記した。
- 公開 API 実測では commits / snapshots / deleted-pages は未ログイン 401、stream は 200。direct public API fallback は可能だが、認証要 API と分ける必要がある。

## [2026-06-26 13:43] implementation+dogfood+file back | `page_create` の revert/replay を追加
- `revert-event` が `page_create` event を扱えるようにした。current lines / title / source path / aliases が created state と一致する場合だけ page を削除し、projection file も削除し、`event_revert` を append する。
- `replay-journal` は `event_revert(target_event_type=page_create)` で replay state から page を削除する。後続編集で lines/title/path/aliases が変わっていれば revert は拒否する。
- dogfood: temp wiki で `A.md`（`[[New]]`）を adopt し、`write-page New --create --path New.md` → `read New` → `replay-journal --check` → `revert-event` → `replay-journal --check` を実行。create 後は backlink count 1、revert 後は `New.md` が projection から消え、replay は clean。
- これは `write-page --create` (`1.7.18`) の recovery 穴埋め。まだ semantic index-log regeneration / 任意 frontmatter merge / general revert / projection export 失敗時 rollback は未実装。
- schema は v7 のまま。public compatibility version は `1.7.19`。
- 検証: `python3 -m unittest discover -s tests`（87 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 14:20] implementation+dogfood+file back | projection export failure の自動 rollback を追加
- `append-section` / `append-log` / `write-page` / `rename-page` が、target event を journal append した後に Markdown projection export へ失敗した場合、自動的に同じ safety check で store を戻し、`event_revert` を journal に追記するようにした。
- 失敗した target event は消さない。journal は `target event` → `event_revert(reason="projection export failed: ...")` の形で、何を試して何が原因で戻したかを残す。command は exit 2 で失敗を返す。
- dogfood: temp wiki で `A.md` を directory に置き換えて `append-section A` の projection export を失敗させた。journal は `page_create` / `section_append` / `event_revert`、store の `peek A` は元の1行、`replay-journal` は original `A.md` を再生成した。
- これは [[llm-wiki-infra-fast-path-plan]] Phase 4 の recovery boundary。まだ semantic index-log regeneration / 任意 frontmatter merge / general revert は未実装。
- schema は v7 のまま。public compatibility version は `1.7.20`。
- 検証: `python3 -m unittest discover -s tests`（88 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 14:58] implementation+dogfood+file back | `export-markdown` に index/log regeneration overlay を追加
- `export-markdown` に明示 alpha overlay として `--regenerate-index` / `--regenerate-log --journal <events.jsonl>` を追加した。既定 projection は stored lines preserving のまま。
- `--regenerate-index` は primary navigation `index.md` を store catalog から生成する。対象は content/source pages、summary は frontmatter `summary` を使う。
- `--regenerate-log` は primary log page を journal の log page events から再生成する。adoption 時の `page_create` を seed にし、`log_append` / log page update / supported `event_revert` を反映する。
- dogfood: temp wiki で hand-written `index.md` / `Log.md` / `concepts/A.md` / `source/Digest.md` を adopt し、`append-log` 後に `export-markdown --regenerate-index --regenerate-log --check` が `index.md` 差分を検出。write 後の同 check は clean になった。
- これは [[llm-wiki-infra-fast-path-plan]] Phase 2 の semantic projection 最小 slice。まだ record 化 log importer / stale-log guard / 本格 index policy / 任意 frontmatter merge / general revert は未実装。
- schema は v7 のまま。public compatibility version は `1.7.21`。
- 検証: `python3 -m unittest discover -s tests`（89 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。

## [2026-06-26 16:01] implementation+dogfood+file-back | file-back を grasp write first に切替
- user-level file-back skill / repo-local /next / AGENTS / CLAUDE に grasp write first を明記した。
- wiki.grasp/events.jsonl を initial adoption journal として追加し、以後の file-back は .grasp/file-back.sqlite + project grasp-wiki + output wiki で journal に追記できる。
- direct Markdown patch は任意 frontmatter merge / canonical docs / ambiguous handle / recovery failure など grasp alpha が安全に扱えない時だけ fallback とした。

## [2026-06-26 16:14] implementation+dogfood+file-back | write-status に stale-log guard を追加
- write-status が通常 projection check に加え、journal 由来の primary log projection を比較し journal_log_stale / journal_log_projection を返すようにした。
- direct Markdown edit を import して通常 projection が clean になっても、journal に無い log 変更は journal_log_stale=true と changed_files で検出できる。
- 同じ SQLite store / journal への並列 write は projection を一時的に stale にするため、repo 手順と file-back skill に直列実行の注意を追加した。
- schema は v7 のまま。public compatibility version は 1.7.23。

## [2026-06-26 16:38] implementation+dogfood+file-back | write-status strict gate を追加
- write-status に --strict を追加し、projection dirty / journal missing / journal log stale / log regeneration error で exit 1 にするようにした。
- status output に strict_ok / strict_failures[] を追加し、ship loop と file-back skill は write-status --strict を gate として使うようにした。
- clean / stale log / non-log projection dirty / missing journal の strict behavior を tests で固定した。
- schema は v7 のまま。public compatibility version は 1.7.24。

## [2026-06-26 16:42] dogfood+gotcha+file-back | write-page projection は未反映 direct patch を上書きする
- write-page は target page だけでなく全 Markdown projection を export するため、複数 wiki page を direct patch してから順に write-page すると、まだ store に入っていない別 page の patch が上書きされる。
- direct patch fallback を journal に戻す時は、1 page patch → write-page --from-file → 次 page の順にする。
- AGENTS / CLAUDE / repo-local /next / user-level file-back skill にこの直列手順を追加した。

## [2026-06-26 16:58] implementation+dogfood+file-back | log entries as journal records
- Added `log_entry_import` journal events and `import-log-records`, so Markdown `log.md` sections can become stable record events without changing projection.
- `adopt-markdown` now emits log entry records during adoption; `write-status` reports `journal_log_record_count`; `replay-journal` treats record imports as non-projection events.
- Dogfooded on this wiki by importing existing `wiki/log.md` entries into `wiki.grasp/events.jsonl`.

## [2026-06-26 17:07] fix+dogfood+file-back | replay tolerates line-id drift
- `replay-journal` now compares page guard lines by `line_index` + `text`, so projection replay does not fail only because direct Markdown re-import reset line IDs.
- This surfaced while dogfooding `log_entry_import` on `wiki.grasp/events.jsonl`; full journal replay now stays clean.

## [2026-06-26 17:25] implementation+dogfood+file-back | query log records from journal
- Added `log-records` to list/filter `log_entry_import` journal records without opening SQLite; filters include query, op, source path, record id, since/until, limit, and offset.
- Added `history <query>` as the event-stream counterpart to `read <page>`; until subject extraction exists it is text search over heading/body/source fields.
- Dogfooded against `wiki.grasp/events.jsonl` with `log-records --query line-id drift`.

## [2026-06-26 18:15] implementation+dogfood+file-back | subject-aware log history
- Added `subjects[]` to new `log_entry_import` records using body `[[wikilink]]` and Markdown path extraction; old records without subjects are inferred at read time.
- `history <query>` and `log-records --subject` now match extracted subjects instead of free-text search, while `log-records --query` remains whitespace term AND text search.
- Returned log records now include bounded same-subject `later_events[]`, `later_event_count`, and `later_events_omitted` so stale transition records are visible.
- Dogfooded with `history grasp-v1-implemented --journal wiki.grasp/events.jsonl`; existing journal records produced subjects and later events without SQLite.

## [2026-06-26 19:25] implementation+test+file-back | record-per-file log entries
- Added record-per-file import for frontmatter `type: log-entry`; `adopt-markdown` and `import-log-records` now create one `log_entry_import` record per such file.
- Frontmatter `date` / `timestamp`, `op`, `summary`, `subjects` / `pages`, and `sources` are read into the record. Explicit subjects win over body heuristics and are exposed separately from `heuristic_subjects[]`.
- Updated [[grasp-v1-implemented]], [[history]], [[grasp-backlog]], and [[llm-wiki-infra-fast-path-plan]]; added regression coverage for explicit subjects overriding body `[[Gamma]]` mentions.

## [2026-06-26 19:44] implementation+test+file-back | log record versioning
- Added content_fingerprint to log_entry_import payloads and made record-per-file entries use page identity as record_id.
- import-log-records now appends a new version when the same record_id has changed frontmatter/body content, and skips unchanged fingerprints.
- log-records/history hide superseded versions by default and expose record_version, record_version_count, superseded_by/supersedes, plus --include-superseded for audits.
- Updated [[grasp-v1-implemented]], [[history]], [[grasp-backlog]], and [[llm-wiki-infra-fast-path-plan]].

## [2026-06-26 20:55] implementation+test+file-back | project record-file logs into Log
- export-markdown --regenerate-log now appends latest record_format=file log_entry_import records to the primary log page projection.
- write-status --strict treats a clean journal-regenerated log projection as satisfying the log-page guard, even when stored log lines differ from generated log output.
- Added regression coverage for record-file projection using the latest version only.
- Updated [[grasp-v1-implemented]], [[history]], [[grasp-backlog]], and [[llm-wiki-infra-fast-path-plan]].

## [2026-06-26 21:26] implementation+test+file-back | projection frontmatter merge
- `export-markdown` projection now merges generated `id` / `title` / `aliases` into existing frontmatter instead of dropping arbitrary metadata such as `type`, `summary`, or `sources`.
- Added regression coverage for stale identity fields being replaced while arbitrary frontmatter survives; bumped package version to `1.7.31`.
- Updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[llm-wiki-infra-fast-path-plan]] through grasp write-first.

## [2026-06-26 21:36] implementation+test+file-back | expand git history replay corpus
- Added an actual git history replay test for `3eaab75`, reproducing the source digest policy correction as six existing-page `write-page` updates and checking replay/direct re-import/projection exact match.
- Fixed existing `write-page` update JSON to include `source_path`, matching the documented return contract and allowing replay tests to assert target files directly.
- Updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[llm-wiki-infra-fast-path-plan]] through grasp write-first.

## [2026-06-26 21:44] implementation+test+file-back | add consecutive git history replay
- Added a consecutive git history replay test for `3eaab75` -> `3605e05`, applying both commits as page_update events in one temp store/journal.
- The test checks replay after each step, final projection exact match, and direct re-import of the final projected wiki.
- Updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[llm-wiki-infra-fast-path-plan]] through grasp write-first.

## [2026-06-26 21:52] implementation+test+file-back | table-drive continuous replay sequences
- Converted the consecutive git history replay test to a `CONTINUOUS_REPLAY_SEQUENCES` table with per-sequence commit/path lists and final assertions.
- Added the `7360053` -> `8278069` handle ambiguity sequence alongside the existing source role sequence, both replayed in the same harness with final projection exact match and direct re-import.
- Updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[llm-wiki-infra-fast-path-plan]] through grasp write-first.

## [2026-06-26 22:10] implementation+test+file-back | mixed operation continuous replay
Extended the continuous git history replay table to support create_pages plus update_paths per step.
Added 0db1449 -> a07f1af as a create-then-update sequence for llm-wiki-infra-fast-path-plan.
Updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[llm-wiki-infra-fast-path-plan]] through grasp write-first.

## [2026-06-26 22:30] implementation+test+file-back | rename operation continuous replay
Added rename_pages support to the continuous git history replay table.
Moved the d4e4c39 why-design-B -> why-not-scrapbox-clone rename invariant into the table-driven continuous replay harness.
Made rename-page JSON results include event_type=page_rename, matching write-page result shape.
Updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[llm-wiki-infra-fast-path-plan]] through grasp write-first.

## [2026-06-26 22:54] implementation+test+file-back | event revert continuous replay
Added revert_events support to the continuous git history replay table.
Added a 0db1449 sequence that creates llm-wiki-infra-fast-path-plan, updates the existing pages, then reverts the page_create event while keeping the updates.
Updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[llm-wiki-infra-fast-path-plan]] through grasp write-first.

## [2026-06-27 14:12] implementation | migrate rename-page to SQLite events transaction
- `rename-page` / `rename` now use `SQLiteStore.rename_markdown_page_with_event()`, committing rename state and SQLite `events` insert in one `BEGIN IMMEDIATE` transaction while keeping legacy JSONL journal append and Markdown projection export.
- Added regression coverage for SQLite `page_rename` rows and rollback when event insert fails.

## [2026-06-27 14:29] implementation | show SQLite events in write-status
- `write-status` now reports selected-project SQLite `events` count and last event in JSON and text output, alongside legacy JSONL journal count and last event.
- Strict mode remains projection / JSONL / regenerated-log based; SQLite-vs-JSONL mismatch is visible but not yet a failure.

## [2026-06-27 14:56] implementation | migrate revert-event to SQLite events
- `revert-event` now resolves target events from SQLite `events` first and falls back to legacy JSONL.
- SQLite-sourced reverts commit state rollback and SQLite `event_revert` insert in one transaction, then append legacy JSONL and export Markdown.

## [2026-06-27 15:20] implementation | query log history from SQLite events
- `import-log-records` now inserts new/updated `log_entry_import` records into SQLite `events` before appending legacy JSONL.
- `log-records` and `history` prefer SQLite `log_entry_import` rows and fall back to JSONL when the selected store has no migrated log records.

## [2026-06-27 16:22] implementation | write adopt-markdown initial events to SQLite
- `adopt-markdown` now inserts initial `page_create` / `log_entry_import` events into SQLite `events` before appending legacy JSONL.
- Fresh adoption now gives `log-records` / `history` a SQLite event stream immediately; tests update expected initial SQLite event sequences.

## [2026-06-27 16:40] implementation | remove unclear write-diff command
- Removed the `write-diff` command and its store helper instead of redefining it under SQLite SSoT.
- Projection drift checks remain through `export-markdown --check` / `write-status --strict`; a future diff command should use a purpose-specific name.

## [2026-06-27 16:50] implementation | write projection failure rollback to SQLite events
- Projection export failure rollback now reverts store state and inserts SQLite `event_revert` in the same write transaction.
- The existing failed export regression now asserts the SQLite event stream matches the legacy journal sequence.

## [2026-06-27 17:01] implementation | strict-check SQLite and journal event stream mismatch
- `write-status` now checks whether selected-project SQLite events appear in the legacy JSONL journal in order.
- `write-status --strict` fails with `event_stream_mismatch` when that compatibility audit fails.
- README recovery surface was updated to remove the deleted `write-diff` command.

## [2026-06-27 17:38] implementation | expose Markdown projection policy
- `export-markdown` now returns `projection_policy` with SQLite authority, stored-lines base, git-tracked projection role, write mode, and generated overlays.
- CLI help/text output now labels `export-markdown --check` as the projection freshness gate for ship loops and file-back cutover.
- The repo skill instructions were updated to remove stale `write-diff` usage and reflect the current `write-status` strict guard.

## [2026-06-27 18:03] implementation | guard file-back projection authority
- Added `scripts/check_projection_policy.py` to validate clean `export-markdown --json --check` output and reject non-SQLite projection authority.
- Updated `/next`, `/ship-next`, AGENTS/CLAUDE, repo `grasp` skill, and local `file-back` skill so file-back / ship loops assert the projection policy before treating Markdown as clean.
- Targeted test and dogfood pipe confirmed `projection_policy authority=sqlite base=stored_markdown_lines output_role=git_tracked_projection`.

## [2026-06-27 17:51] implementation+file-back | file-back preflight guard
- Added `scripts/check_file_back_preflight.py` to fail file-back before writes when `origin/main...HEAD` is non-empty, wiki/journal paths are dirty, `write-status --strict` is not clean, or projection policy is not SQLite-authority clean.
- Updated `/next`, `/ship-next`, AGENTS/CLAUDE, repo `grasp` skill, and local `file-back` skill to use the preflight when available.
- Dogfood: the preflight passed on the clean wiki/journal state before this grasp write-first file-back; targeted tests cover dirty path, divergence, and write-status guard failures.

## [2026-06-27 18:01] implementation+file-back | file-back postwrite guard
- Added `scripts/check_file_back_postwrite.py` to verify `write-status --strict`, SQLite-authority projection policy, wiki lint, and `git diff --check` after grasp write-first file-backs.
- Updated `/next`, `/ship-next`, AGENTS/CLAUDE, repo `grasp` skill, and local `file-back` skill to use the postwrite checker when available.
- Dogfood: preflight passed before this file-back, and the new postwrite checker passed on the clean projection before the wiki write.

## [2026-06-27 18:08] file-back | compatibility journal boundary in active runbooks
- Updated AGENTS/CLAUDE, `/next`, repo `grasp` skill, and local `file-back` skill so `wiki.grasp/events.jsonl` is described as a transition compatibility/audit journal, not normal edit authority.
- Recovery wording now routes through `scripts/check_file_back_postwrite.py` where available instead of spelling raw projection checks in the active path.
- Dogfood: this file-back started with `scripts/check_file_back_preflight.py` and used grasp `write-page` / `append-log` only for wiki changes.

## [2026-06-27 18:25] implementation+file back | write commands に --no-journal を追加
- code: Markdown-backed `append-section` / `append-log` / `write-page` / `rename-page` / `revert-event` に `--no-journal` を追加し、SQLite events + Markdown projection を更新しつつ compatibility JSONL append を省略できるようにした。`write-status --no-journal --strict` は JSONL guards を外し、SQLite-authority projection だけを strict check する。
- tests: no-journal write が `journal=null` / `journal_written=false` を返し、compatibility journal を変更せず SQLite events と projection を更新する統合テストを追加。既存 journal strict failure と journal あり write path の targeted tests も確認。
- file back: [[history]] / [[grasp-v1-implemented]] / [[sqlite-ssot-write-plan]] / [[grasp-backlog]] を更新。public compatibility version は `1.8.12`、schema は v8 のまま。repo file-back は当面 compatibility journal あり guard を継続し、次は guarded dogfood streak と `--no-journal` cutover 判断。

## [2026-06-27 18:36] implementation+file back | file-back guard scripts に --no-journal mode を追加
- code: `scripts/check_file_back_preflight.py` / `scripts/check_file_back_postwrite.py` に `--no-journal` mode を追加。preflight は `write-status --no-journal --strict` を使い、dirty path default を `wiki` のみにする。postwrite は no-journal status を使いつつ projection policy / wiki lint / `git diff --check` を継続する。既定の compatibility journal あり mode は維持。
- tests: preflight / postwrite script tests に no-journal guard skip と subprocess argument selection を追加。実 repo に対して journal あり/なし両 mode の preflight/postwrite smoke も通した。
- file back: [[history]] / [[grasp-v1-implemented]] / [[sqlite-ssot-write-plan]] / [[grasp-backlog]] を更新。public compatibility version は `1.8.13`、schema は v8 のまま。次は guarded dogfood streak と repo file-back の `--no-journal` cutover 判断。

## [2026-06-27 18:49] implementation+file back | repo file-back runbooks を --no-journal default に切替
- docs: AGENTS/CLAUDE、Codex `/next`、Claude `/ship-next`、repo `grasp` skill、README を通常 `--no-journal` path に更新。`wiki.grasp/events.jsonl` は明示 audit 用 artifact として残す。
- file back: [[history]] / [[grasp-v1-implemented]] / [[sqlite-ssot-write-plan]] / [[grasp-backlog]] を更新。public compatibility version は `1.8.14`、schema は v8 のまま。
- dogfood: `scripts/check_file_back_preflight.py --no-journal` から開始し、wiki 更新は `write-page --no-journal` / `append-log --no-journal` で store に反映した。

## [2026-06-27 18:58] implementation+file back | file-back runbook drift checker を追加
- code: `scripts/check_file_back_runbook.py` を追加し、AGENTS/CLAUDE、Codex `/next`、Claude `/ship-next`、repo `grasp` skill、README が `--no-journal` default を保持しているか検査できるようにした。
- tests: `tests/test_file_back_runbook_script.py` を追加し、required / forbidden fragment と current repo docs の一致を確認する。`/next` と `/ship-next` の verification に runbook checker を追加。
- file back: [[history]] / [[grasp-v1-implemented]] / [[sqlite-ssot-write-plan]] / [[grasp-backlog]] を更新。public compatibility version は `1.8.15`、schema は v8 のまま。

## [2026-06-27 19:09] implementation+file back | file-back guard scripts を no-journal default に切替
- code: `scripts/check_file_back_preflight.py` / `scripts/check_file_back_postwrite.py` の default を no-journal mode に切替。compatibility JSONL journal checks は `--with-journal` の明示 opt-in にした。`--no-journal` は既存 runbook 用の明示互換フラグとして残した。
- tests: `resolve_require_journal()` の default / conflict tests を追加し、preflight / postwrite の no-flag smoke で `journal_mode=none` を確認。
- file back: [[history]] / [[grasp-v1-implemented]] / [[sqlite-ssot-write-plan]] / [[grasp-backlog]] を更新。public compatibility version は `1.8.16`、schema は v8 のまま。

## [2026-06-27 19:15] implementation+file back | file-back runbook drift guard を no-journal default 表記に追従
- docs: AGENTS/CLAUDE、Codex `/next`、Claude `/ship-next` から guard script の旧 `--no-journal` 明示を外し、通常 pre/postwrite はフラグなし no-journal default とした。write commands の `--no-journal --output wiki` は通常 path として維持。
- docs: compatibility JSONL audit は `scripts/check_file_back_preflight.py --with-journal` / `scripts/check_file_back_postwrite.py --with-journal` と `--journal wiki.grasp/events.jsonl --output wiki` の明示手順にした。
- code: `scripts/check_file_back_runbook.py` が旧 `check_file_back_* --no-journal` guard 表記と `--with-journal` audit 手順漏れを検出するようにし、regression test を追加。
- file back: [[history]] / [[grasp-v1-implemented]] / [[sqlite-ssot-write-plan]] / [[grasp-backlog]] を更新。public compatibility version は `1.8.17`、schema は v8 のまま。

## [2026-06-27 19:21] dogfood | no-journal default file-back streak 1
- preflight: `git fetch origin main` + `python3 scripts/check_file_back_preflight.py` が `journal_mode=none` で通った。
- write: `append-log --output wiki --no-journal` で本 log entry を追加し、`wiki.grasp/events.jsonl` は触らない。direct Markdown patch fallback は使っていない。
- next: 同じ path をあと2回、実作業の file-back で通し、generated Markdown backup/review policy の必要性を実観測で判断する。

## [2026-06-27 19:24] dogfood | no-journal default file-back streak 2
- preflight: `python3 scripts/check_file_back_preflight.py` が `journal_mode=none` で通った。
- write: `append-log --output wiki --no-journal` で本 log entry を追加した。`wiki.grasp/events.jsonl` は無変更、direct Markdown patch fallback なし。
- observation: streak 2 でも generated Markdown backup/review policy の追加を要する concrete gap は出ていない。次は同じ path の streak 3 を通して Phase 6 の dogfood proof を閉じる。

## [2026-06-27 19:27] dogfood | no-journal default file-back streak 3
- preflight: `python3 scripts/check_file_back_preflight.py` が `journal_mode=none` で通った。
- write: `append-log --output wiki --no-journal` で本 log entry を追加した。`wiki.grasp/events.jsonl` は無変更、direct Markdown patch fallback なし。
- observation: streak 1-3 で generated Markdown backup/review policy の追加を要する concrete gap は出ていない。次は [[sqlite-ssot-write-plan]] / [[grasp-backlog]] を更新し、Phase 6 dogfood proof を完了扱いにする。

## [2026-06-27 19:27] file back | Phase 6 dogfood proof を完了扱いに更新
- file back: [[sqlite-ssot-write-plan]] の Phase 6 を repo-local dogfood done にし、Immediate Next Slice を `wiki.grasp/events.jsonl` artifact policy へ進めた。
- file back: [[grasp-backlog]] から no-journal default dogfood streak を未実装項目として外し、残課題を native events semantic projection / JSONL artifact policy / concrete gap が出た場合の generated Markdown backup-review policy に更新。
- proof: streak 1-3 は preflight/postwrite をフラグなし no-journal default で通し、write は `--no-journal --output wiki`、`wiki.grasp/events.jsonl` 無変更、direct Markdown patch fallback なし。

## [2026-06-27 19:41] implementation | retire tracked events jsonl artifact
- implemented: tracked wiki.grasp/events.jsonl を削除し、repo-local file-back runbook / checker / skill / README を no-journal default + retired journal policy に更新。
- guard: scripts/check_file_back_preflight.py は no-journal default でも wiki/ と退役済み JSONL path の dirty を止める。runbook checker は repo runbook の --with-journal 復帰を stale として検出する。
- file back: history / grasp-v1-implemented / sqlite-ssot-write-plan / grasp-backlog / log を --no-journal --output wiki で更新し、wiki.grasp/events.jsonl は再作成していない。

## [2026-06-27 19:50] implementation | regenerate log from SQLite events
- implemented: export-markdown --regenerate-log は --journal なしなら SQLite events を source にし、projection_policy generated_overlays に sqlite-events-log、result に log_event_source=sqlite / log_event_count を返す。
- compatibility: --journal <path> を明示した時だけ legacy JSONL event stream を読み、legacy-journal-log overlay を返す ad hoc audit path として残した。
- test: record-per-file log_entry_import を SQLite events から Log.md へ生成する no-journal regression を追加した。

## [2026-06-27 19:50] dogfood | sqlite regenerate-log check passes on repo store
- command: python3 -m grasp --store .grasp/file-back.sqlite --project grasp-wiki --json export-markdown --output wiki --regenerate-log --check
- result: ok=true, regenerated_files=[log.md], log_event_source=sqlite, log_event_count=135, generated_overlays=[sqlite-events-log], changed_files=[]。partial event stream は log page page_update を seed にして replay できる。

## [2026-06-27 20:06] implementation | guard semantic log projection in postwrite
- implemented: check_file_back_postwrite.py runs export-markdown --regenerate-log --check by default and verifies sqlite source / sqlite-events-log overlay.
- escape hatch: --skip-semantic-log-check skips only this additional semantic log projection check.
- file back: [[history]], [[grasp-v1-implemented]], [[sqlite-ssot-write-plan]], and [[grasp-backlog]] now treat the repo postwrite guard as implemented.

## [2026-06-27 20:17] implementation | surface semantic log projection in write-status
- implemented: write-status now returns semantic_log_projection / semantic_log_stale / semantic_log_changed_files for SQLite events-derived log projection.
- strict: write-status --strict fails with semantic_log_stale when the generated SQLite log projection drifts; projects without a log page skip the semantic check.
- tests: added no-journal strict drift coverage and preflight diagnostics for semantic_log_* status fields.

## [2026-06-27 20:34] implementation | surface projection rollback diagnostics
- implemented: write command projection export failures now raise a structured rollback diagnostic on --json stderr after automatic event_revert rollback.
- covered: both compatibility journal and --no-journal paths report target_event_id / rollback_event_id / journal_written / original_error.
- scope: this starts the SQLite authority rollback policy slice; remaining general revert policy still needs a concrete multi-event or planning definition.

## [2026-06-27 21:05] implementation | add revert-event dry-run planning surface
implemented: revert-event --dry-run now runs existing revert safety guards inside a rollback-only SQLite write transaction and reports dry_run / revertible / reason / would_* fields without writing event_revert, journal, or projection.
tests: covered reversible page_create dry-run and non-revertible section_append dependency/tail guard dry-run.
file back: [[history]], [[grasp-v1-implemented]], [[sqlite-ssot-write-plan]], and [[grasp-backlog]] now treat dry-run diagnostics as implemented; remaining work is mutating multi-event / dependency-aware general revert policy.

## [2026-06-27 21:22] implementation | add dependent revert execution
- implemented: revert-event --include-dependents now reverts later active same-page SQLite events in reverse event_sequence before the requested target.
- dry-run: --dry-run --include-dependents returns the same sequence as included_dependent_event_ids / would_event_count / reverted_events without writing event_revert, journal, or projection.
- tests: covered two append events where the earlier append is normally blocked by tail guard but succeeds when the later append is included as a dependent.

## [2026-06-27 21:42] verification | cover dependent create-rename revert
- tests: added regression coverage for reverting a page_create after a later page_rename with --include-dependents; the dependent rename is reverted first and only the final New.md projection is removed.
- docs: updated skills/grasp/SKILL.md so agents see page_create revert, --dry-run, and --include-dependents as part of the recovery surface.
- scope: no CLI behavior change; this fixes agent-facing documentation and locks the rename-dependent projection case into tests.

## [2026-06-27 22:23] implementation | add explicit multi-event rollback
- implemented: revert-events <event-id...> rolls back explicitly selected active SQLite events in reverse event_sequence inside one transaction.
- dry-run: revert-events --dry-run returns requested_event_ids / revert_order_event_ids / would_event_count without mutating store, journal, or projection.
- tests: covered two page_update events across different pages to verify multi-page rollback order and event_revert payloads.

## [2026-06-27 22:41] implementation | add log-batch revert planning
- implemented: revert-plan <event-id> --scope log-batch infers a file-back style rollback candidate set from SQLite log_append boundaries without mutation.
- dogfood: the planner identifies the previous 1.8.25 file-back as four page_update events plus its closing log_append and reports reverse event_sequence rollback order.
- tests: covered a two-page update plus closing log_append and verified revert-plan leaves files and SQLite events unchanged.

## [2026-06-27 22:55] implementation | add same-page revert planning
- implemented: revert-plan <event-id> --scope same-page-dependents infers anchor + later active same-page reversible rollback candidates without requiring log-batch boundaries.
- tests: covered a later append blocking a plain revert-event dry-run while same-page-dependents returns a two-event read-only plan.
- docs: bumped compatibility version to 1.8.27 and narrowed the remaining revert-planning backlog to multi-page histories without log-batch or same-page boundaries.

## [2026-06-27 23:05] implementation | add event-window revert planning
- implemented: revert-plan <event-id> --scope event-window --before/--after returns a bounded multi-page event_sequence rollback candidate set without log-batch boundaries.
- tests: covered two page_update events across different pages with no log entry and verified plan output without store/projection mutation.
- docs: bumped compatibility version to 1.8.28 and narrowed remaining revert planning to semantic multi-page work-unit inference beyond log-batch, same-page, or explicit event-window boundaries.

## [2026-06-27 23:17] implementation | add time-burst revert planning
- implemented: revert-plan <event-id> --scope time-burst --max-gap-seconds returns a bounded multi-page rollback candidate set from adjacent event created_at gaps without crossing log_append boundaries.
- tests: covered three page_update events across different pages with a large gap after the second update, verifying the burst excludes the later event and does not mutate store/projection.
- docs: bumped compatibility version to 1.8.29 and narrowed remaining revert planning to semantic multi-page work-unit inference beyond log-batch, same-page, explicit event-window, or time-burst boundaries.

## [2026-06-27 23:38] implementation | add session-scoped revert planning
- implemented: global --actor / --session-id metadata now reaches SQLite write, revert, import-log, and adopt events, defaulting from GRASP_ACTOR / GRASP_SESSION_ID.
- implemented: revert-plan <event-id> --scope session returns read-only rollback candidates for selected-project events sharing the anchor session_id.
- tests: covered interleaved page_update events from two sessions, env-default event metadata, and empty-session anchors rejected by session planning.
- docs: bumped compatibility version to 1.8.30 and narrowed remaining work-unit inference to cases beyond log-batch, same-page, explicit event-window, time-burst, or session boundaries.

## [2026-06-27 23:52] implementation | add subject-log revert planning
- implemented: revert-plan <event-id> --scope subject-log now filters a too-broad log-batch by subjects extracted from the closing log_append summary/body.
- implemented: subject-log candidates include matching page events plus the closing log_append, then reuse the existing rollback-only safety check and suggested revert-events args.
- tests: covered a mixed A/B/C page_update log-batch where the closing log mentions [[A]] and concepts/C.md, proving B is excluded and the plan stays read-only.
- docs: bumped compatibility version to 1.8.31 and narrowed remaining work-unit inference to cases beyond log-batch, subject-log, same-page, explicit event-window, time-burst, or session boundaries.

## [2026-06-28 00:09] implementation | add log page subject revert planning
- implemented: revert-plan <event-id> --scope log-page-subjects now handles legacy/direct Markdown history where a closing log entry appears as a log.md page_update rather than log_append.
- implemented: the plan diffs previous_lines and lines to read only newly added log lines, extracts wikilink/Markdown path subjects, and keeps matching page events plus the closing log page update.
- implemented: page_update SQLite event payloads now include source_path and graph_role; older page_update events are matched through page_id-derived current handles/source paths.
- tests: covered real git history replay commit 3eaab75, proving subject-log is incomplete without log_append while log-page-subjects selects the four subject pages plus log.md and excludes index.md without mutating projection.
- docs: bumped compatibility version to 1.8.32 and narrowed remaining work-unit inference to cases beyond log-batch, subject-log, log-page-subjects, same-page, explicit event-window, time-burst, or session boundaries.

## [2026-06-28 00:38] implementation | add content subject revert planning
- implemented: revert-plan <event-id> --scope content-subjects now extracts wikilink/Markdown path subjects from the anchor event changed lines and matches page events by changed-subject or event-target overlap.
- implemented: content-subjects skips the initial adopt baseline, uses the next log boundary as a scan cap when present, and reuses the rollback-only safety check without mutating store, journal, or projection.
- tests: covered real git history replay commit b644237, where log-page-subjects misses index.md but content-subjects selects grasp-backlog.md, sqlite-ssot-write-plan.md, index.md, llm-wiki-infra-fast-path-plan.md, and log.md.
- docs: bumped compatibility version to 1.8.33 and narrowed remaining work-unit inference to cases beyond log-batch, subject-log, log-page-subjects, content-subjects, same-page, explicit event-window, time-burst, or session boundaries.

## [2026-06-28 00:49] implementation+file-back | harden revert-plan baseline detection
- implemented: `revert-plan` initial adopt baseline detection no longer treats real `write-page --create` events before a `content-subjects` anchor as baseline; regression uses git history fixture `b644237`.

## [2026-06-28 01:05] implementation+file-back | add content-subjects anchor-target fallback
`1.8.35` lets `revert-plan --scope content-subjects` use the anchor event target when changed lines have no wikilink or Markdown path subjects; regression covers a plain created page linked by another page and the closing log.

## [2026-06-28 01:15] implementation+file-back | make content-subjects dependency-complete
`1.8.36` adds same-page dependency closure to `revert-plan --scope content-subjects`, so semantic candidate sets include required later page events before rollback-only safety checking.

## [2026-06-28 01:37] file-back | record test cadence policy
- Recorded [[sqlite-ssot-write-plan]] test cadence: use targeted tests during tight rollback/write slices, reserve full suite plus lint/runbook/diff checks for ship boundaries, and run heavy replay/help tests only when their contracts change.

## [2026-06-28 02:09] implementation+file-back | make inferred revert plans dependency-complete
`1.8.37` extends same-page dependency closure from content-subjects to log-batch, subject-log, and log-page-subjects, so inferred plans include required later cleanup events before rollback-only safety checking.

## [2026-06-28 02:03] implementation+file-back | add version-bump revert plan
`1.8.38` adds `revert-plan --scope version-bump`, using shared semver tokens in a log-bounded slice to recover release/file-back version update work units that subject-based scopes cannot infer.
Regression replays git history commit `5f1b821` and confirms the `1.8.37` five-page file-back is selected by the shared version token while `content-subjects` and `log-page-subjects` remain insufficient.

## [2026-06-28 02:27] implementation+file-back | require file-back session marker in postwrite
- code: `scripts/check_file_back_postwrite.py` now requires a non-empty expected session id by default and checks latest `sqlite_last_event.session_id` against `$GRASP_SESSION_ID` / `--session-id`. Legacy/ad hoc checks must opt out with `--skip-session-check`.
- docs/tests: runbook checker, AGENTS/CLAUDE, `/next`, `/ship-next`, repo skill, README, history, current facts, backlog, and write plan now require normal file-backs to keep one `GRASP_SESSION_ID` through postwrite.
- dogfood: postwrite passed with `GRASP_SESSION_ID=file-back-20260627T172244Z-session-postwrite`; `revert-plan --scope session` on the latest log update returned 8 same-session candidate events with `revertible=true`.
- rationale: this does not add another fuzzy inference scope; it ensures new repo file-backs preserve metadata for existing `revert-plan --scope session`.

## [2026-06-28 02:50] implementation+file back | preflight で file-back session id 再利用を検出
- code: `scripts/check_file_back_preflight.py` が `$GRASP_SESSION_ID` / `--session-id` を読み、selected project の既存 SQLite events に同じ `session_id` がある場合は通常 preflight を failure にする。legacy/ad hoc verification だけ `--skip-session-uniqueness-check` で省略できる。
- tests/docs: preflight unit tests と runbook checker を更新し、AGENTS/CLAUDE、`/next`、`/ship-next`、repo skill、README は export `GRASP_SESSION_ID` → preflight 未使用性確認 → write → postwrite 同一性確認の順序を要求する。
- dogfood: 新 session `file-back-20260627T174500Z-session-uniqueness` の preflight は通り、旧 `file-back-20260627T172244Z-session-postwrite` を指定した preflight は既存10 eventsを検出して失敗した。public compatibility version は `1.8.40`、schema は v8 のまま。

## [2026-06-28 03:00] implementation+file back | preflight default base を current upstream にする
- code: `scripts/check_file_back_preflight.py` の default `--base` を `auto` にし、current upstream tracking branch を優先、upstream が無い時だけ `origin/main` に fallback するようにした。明示 `--base <ref>` は維持。
- docs/tests: preflight unit tests、runbook checker、AGENTS/CLAUDE、`/next`、`/ship-next`、repo skill、README、history、current facts、backlog、write plan を current-upstream base policy に更新した。
- dogfood: `GRASP_SESSION_ID=file-back-20260627T180001Z-preflight-auto-base` で default preflight が `base=origin/codex/recovery-gap-scan` を報告し、PR branch 上の継続 file-back で manual `--base` override が不要なことを確認した。public compatibility version は `1.8.41`、schema は v8 のまま。

## [2026-06-28 03:19] implementation+file back | push ownership guard を ship loop に追加
- code: `scripts/check_push_ownership.py` を追加し、dirty worktree、behind branch、通常 ship-loop からの protected branch（`main` / `master`）push を failure にするようにした。feature branch の ahead push と新規 branch push は許容する。
- docs/tests: unit tests、runbook checker、AGENTS/CLAUDE、`/next`、`/ship-next`、repo skill、README、history、current facts、backlog、write plan を push ownership guard に更新した。
- dogfood: 未コミット差分がある状態で `python3 scripts/check_push_ownership.py` が dirty worktree を検出して失敗することを確認した。commit 後に同 guard を再実行して push 前 gate として確認する。public compatibility version は `1.8.42`、schema は v8 のまま。

## [2026-06-28 03:40] implementation+file back | preflight stamp で write 開始 base を検査
- code: `scripts/check_file_back_preflight.py` が clean preflight 後に gitignored `.grasp/file-back-preflight.json` へ session/head/base/store/project/output を記録し、`scripts/check_file_back_postwrite.py` が通常 mode で同 stamp の session/head/base 一致を検査するようにした。
- docs/tests: unit tests、runbook checker、AGENTS/CLAUDE、`/next`、`/ship-next`、repo skill、README、history、current facts、backlog、write plan を preflight stamp guard に更新した。
- fallback/dogfood: 今回は preflight/postwrite guard 自体と runbook を同じ差分で更新しており、wiki dirty 前提の直接 patch で file-back した。別途 `HEAD` 由来の一時 projection で preflight → `append-log --no-journal` → postwrite を実行し、stamp の session/head/base 検査が通ることを確認した。public compatibility version は `1.8.43`、schema は v8 のまま。

## [2026-06-28 04:01] implementation+file back | write-start guard を追加
- code: `scripts/check_file_back_write_start.py` を追加し、preflight 後・最初の write command 直前に preflight stamp / git dirty paths / `write-status --no-journal --strict` / SQLite authority projection / semantic log projection を import なしで検査するようにした。
- docs/tests: unit tests、runbook checker、AGENTS/CLAUDE、`/next`、`/ship-next`、repo skill、README、history、current facts、backlog、write plan を write-start guard に更新した。
- rationale: preflight 再実行は Markdown を store に取り込むため、preflight 後の projection 変化を隠しうる。write-start は stale store export/clobber gap を write 直前に止める運用 guard。public compatibility version は `1.8.44`、schema は v8 のまま。

## [2026-06-28 04:25] implementation+file back | file-back store/output pair guard を追加
- code: `scripts/check_file_back_preflight.py` / `scripts/check_file_back_write_start.py` / `scripts/check_file_back_postwrite.py` が repo default store/output pair（`.grasp/file-back.sqlite` + `wiki`）と temp store + temp output の混在を failure にするようにした。
- docs/tests: preflight/write-start/postwrite unit tests、runbook checker、AGENTS/CLAUDE、`/next`、`/ship-next`、repo skill、README、history、current facts、backlog、write plan を store/output pair guard に更新した。
- rationale: temp dogfood を real store + temp output で走らせると、temp log event が real SQLite events に残り、SQLite events 由来 semantic log projection を stale にする。public compatibility version は `1.8.45`、schema は v8 のまま。

## [2026-06-28 04:41] implementation+file back | package version metadata drift guard を追加
- code: `grasp.__version__` と `pyproject.toml` の `[project] version` を `1.8.46` に揃え、`tests/test_version_metadata.py` が一致を検査するようにした。
- finding: `1.8.45` 時点で package metadata は進んでいたが `grasp.__version__` は `1.8.42` のままで、runtime から見る version と release ledger がずれていた。
- docs: [[history]] の current state と [[grasp-v1-implemented]] の current facts を更新した。public compatibility version は `1.8.46`、schema は v8 のまま。

## [2026-06-28 04:49] implementation+file back | `grasp --version` を追加
- code: root CLI に `--version` を追加し、`grasp.__version__` を `grasp 1.8.47` の形式で表示できるようにした。
- tests: `tests/test_version_metadata.py` は package metadata と `grasp.__version__` の一致に加え、`python3 -m grasp --version` の出力も package version と一致することを検査する。
- docs: [[history]] と [[grasp-v1-implemented]] を更新した。public compatibility version は `1.8.47`、schema は v8 のまま。

## [2026-06-28 05:03] implementation+file back | fresh file-back store を preflight で bootstrap
- code: `scripts/check_file_back_preflight.py` が no-journal mode で selected-project SQLite events の無い file-back store を検出した場合、`adopt-markdown` で gitignored `.grasp/file-back-adopt.jsonl` に bootstrap audit を作ってから通常の `import --markdown` / `write-status --no-journal --strict` / projection check に進むようにした。
- tests/docs: preflight unit tests、runbook checker、AGENTS/CLAUDE、`/next`、`/ship-next`、repo skill、README、history、current facts、write plan を fresh store bootstrap guard に更新した。
- dogfood: fresh isolated worktree の `.grasp/file-back.sqlite` が未初期化でも、`GRASP_SESSION_ID=file-back-20260627T200500Z-bootstrap-repro python3 scripts/check_file_back_preflight.py` が通った。public compatibility version は `1.8.48`、schema は v8 のまま。

## [2026-06-28 05:13] implementation+file back | preflight bootstrap の SQLite error 境界を狭める
- code: `scripts/check_file_back_preflight.py` は repo 基準で解決した store path がまだ無い場合と `events` table が無い場合だけ bootstrap 可能な empty state と扱い、locked / malformed / unopenable existing store などその他 SQLite error では adoption せず preflight failure にする。
- tests: preflight unit tests は missing store file、missing `events` table、malformed DB、unopenable existing store、repo-relative store resolution、locked DB で bootstrap しないことを固定した。
- dogfood: fresh worktree で最初の preflight が `unable to open database file` を返したため、missing store file を bootstrappable として扱う判定を追加し、その後 `GRASP_SESSION_ID=file-back-20260627T203300Z-bootstrap-error-boundary python3 scripts/check_file_back_preflight.py` と write-start が通った。public compatibility version は `1.8.49`、schema は v8 のまま。

## [2026-06-28 05:20] implementation+file back | direct patch projection clobber guard
- code: Markdown-backed write commands now refuse Git dirty projection paths outside the current target unless those paths already match the current store projection; append-section/log also expose source_path in result and event payload.
- dogfood: initial guard blocked the next wiki page because the previous page was already stored but still git-dirty, so 1.8.50 compares dirty files against store projection before blocking.
- tests: added regression coverage for blocking unrelated dirty B.md, allowing target dirty direct patch fallback, and allowing prior stored dirty pages during multi-page file-back. public compatibility version is 1.8.50; schema remains v8.

## [2026-06-28 06:10] implementation+file-back | guard revert projection exports before mutation
- code: revert-event, revert-events, and revert-event --include-dependents now run dirty projection guard before mutating store/event rows.
- guard: reverted target paths are allowed; unrelated dirty paths must already match the current store projection, with older payloads resolving source_path from page_id via the Markdown manifest.
- tests: added regression coverage that dirty unrelated B.md blocks each revert surface without inserting event_revert or changing target files. public compatibility version is 1.8.51; schema remains v8.

## [2026-06-28 06:30] implementation+file-back | guard dirty revert target files
- code: revert-event, revert-events, and revert-event --include-dependents now reject dirty target projection paths unless they match the current store projection before mutation.
- risk: 1.8.51 blocked unrelated dirty projection files, but a local draft in the recovered target path could still be overwritten or removed during recovery export.
- tests: added regression coverage that dirty target A.md blocks revert before event_revert insertion while preserving both store state and the local draft. public compatibility version is 1.8.52; schema remains v8.

## [2026-06-28 06:45] implementation+file-back | guard dirty write target files
- code: append-section, append-log, write-page, and rename-page now reject dirty target projection paths before mutation unless they already match the current store projection.
- exception: write-page --from-file may still use the target projection file itself as the replacement input, preserving the direct patch fallback.
- tests: added regression coverage for dirty target drafts in write-page --line, append-section, append-log, and rename-page. public compatibility version is 1.8.53; schema remains v8.

## [2026-06-28 07:15] implementation+file-back | guard full file-back session window
- code: preflight stamp schema v2 records the latest SQLite event_sequence before file-back writes.
- guard: postwrite now checks every SQLite event written after that baseline for the expected GRASP_SESSION_ID, not only the latest event.
- reason: dogfood showed an intermediate write-page can accidentally omit session metadata while the final append-log still makes the latest-event guard pass. public compatibility version is 1.8.54; schema remains v8.

## [2026-06-28 07:35] implementation+file-back | guard write-start SQLite event window
- code: scripts/check_file_back_write_start.py now compares the preflight stamp latest SQLite event_sequence with the current latest event_sequence before the first write command, and fails before mutation if the store advanced.
- tests/docs: added write-start regression coverage, runbook checker fragments, AGENTS/CLAUDE, /next, /ship-next, repo skill, README, history, current facts, and write plan updates. Public compatibility version is 1.8.55; schema remains v8.
- dogfood: preflight and the new write-start event_sequence=unchanged guard passed before this no-journal wiki file-back used grasp writes.

## [2026-06-28 07:55] implementation+file-back | guard overlapping file-back sessions
- code: repo-local preflight now acquires gitignored .grasp/file-back.lock.json after clean checks; write-start and postwrite require the same session/store/project/output lock, and postwrite releases it only after all checks pass.
- reason: the previous guard stopped store changes before the first write, but a multi-command file-back could still overlap another normal runbook writer between write commands and only be detected at postwrite.
- tests/docs: added lock acquire/check/release regression coverage, runbook checker fragments, AGENTS/CLAUDE, /next, /ship-next, repo skill, README, history, current facts, and write plan updates. Public compatibility version is 1.8.56; schema remains v8.
- dogfood: preflight acquired the lock, write-start checked it, and this no-journal file-back used grasp writes under the same GRASP_SESSION_ID.
## [2026-06-28 07:26] implementation+file-back | guard version ledger drift

- code: `tests/test_version_metadata.py` now checks package version against `grasp.__version__`, `pyproject.toml`, [[history]] latest/current release ledger lines, and [[grasp-v1-implemented]] current public compatibility version.
- reason: dogfood found a stale current fact: after `1.8.56`, [[grasp-v1-implemented]] still said current public compatibility version was `1.8.54` while package/history were `1.8.56`.
- docs: bumped public/package version to `1.8.57`, updated [[history]], [[grasp-v1-implemented]], and [[sqlite-ssot-write-plan]]. schema remains v8.
## [2026-06-28 07:36] implementation+file-back | promote version ledger drift guard to lint

- code: added `scripts/check_wiki_version_ledger.py` and wired `scripts/lint_wiki.py` to report release ledger / current facts version drift and exit 1 on drift.
- tests: added `tests/test_wiki_version_ledger_script.py` for clean ledger, current-facts drift, duplicate history entry, and semver ordering drift. `tests/test_version_metadata.py` still checks package/history/current facts consistency.
- docs: bumped public/package version to `1.8.58` and updated [[history]], [[grasp-v1-implemented]], and [[sqlite-ssot-write-plan]]. schema remains v8.
## [2026-06-28 07:49] implementation+file-back | make explicit rollback scopes dependency-complete

- code: `revert-plan --scope event-window`, `time-burst`, and `session` now run the same required later same-page dependent closure as the semantic scopes and report additions in `dependent_event_ids`.
- tests: added a CLI regression where the explicit base selection includes `A` and `B`, but a later same-page `A` cleanup outside the window / time gap / session must be included for rollback-only safety to pass.
- docs: bumped public/package version to `1.8.59` and updated [[history]], [[grasp-v1-implemented]], and [[sqlite-ssot-write-plan]]. schema remains v8.

## [2026-06-28 08:29] implementation+file-back | cover page_update revert in real history replay

- tests: added a continuous git history replay sequence for commit `3eaab75` that applies six existing-page `page_update` events, then reverts only the `grasp-backlog.md` update.
- coverage: expected projection is mixed state: the reverted page matches the parent revision while the other five pages remain at the updated commit; `replay-journal --check` and direct re-import stay clean.
- docs: bumped public/package version to `1.8.62` and updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[sqlite-ssot-write-plan]]. schema remains v8.

## [2026-06-28 08:44] implementation+file-back | preserve old rename projection on export rollback

- code: `rename-page` now exports the new projection before deleting the previous projection file, so a failed new-path export rolls SQLite back without also deleting the old Markdown file.
- tests: added a regression with `New.md` as a directory; the command returns `projection_export_rollback`, inserts SQLite `event_revert`, restores current store state to `Old`, and leaves `Old.md` intact.
- docs: bumped public/package version to `1.8.63` and updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[sqlite-ssot-write-plan]]. schema remains v8.

## [2026-06-28 08:57] implementation+file-back | preflight projection writes before export
- code: `export-markdown` now reads all projection targets and preflights write target paths before writing any file, preventing partial Markdown projection updates when a later target fails.
- tests: added a non-git `write-page A` regression where `B.md` is a directory; automatic rollback leaves SQLite reverted and `A.md` unchanged.
- docs: bumped public/package version to `1.8.64` and updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[sqlite-ssot-write-plan]]. schema remains v8.

## [2026-06-28 09:11] implementation+file-back | export before removing revert projection files
- code: `revert-event`, `revert-events`, and `revert-event --include-dependents` now export the reverted store state before deleting projection files made obsolete by page_create/page_rename revert.
- tests: added a page_rename revert regression where `Old.md` is a directory; the SQLite `event_revert` lands and `New.md` remains instead of being deleted before the failing export.
- docs: bumped public/package version to `1.8.65` and updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[sqlite-ssot-write-plan]]. schema remains v8.

## [2026-06-28 09:23] implementation+file-back | diagnose revert projection export failures
- code: actual revert projection finalization now raises a `revert_projection_export_failed` diagnostic under `--json` after revert events have been written.
- tests: strengthened the page_rename revert export-failure regression to assert phase, target/revert event ids, pending removed files, journal status, and original error while preserving the old projection file.
- docs: bumped public/package version to `1.8.66` and updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[sqlite-ssot-write-plan]]. schema remains v8.

## [2026-06-28 09:39] implementation+file-back | preflight legacy journal append paths
- code: write / recovery / adopt / import-log paths that still request legacy `--journal` now preflight appendability before SQLite mutation.
- tests: added append-section and revert-event regressions where `--journal` points at a directory; both return `journal_append_preflight_failed` and leave SQLite events plus Markdown projection unchanged.
- docs: bumped public/package version to `1.8.67` and updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[sqlite-ssot-write-plan]]. schema remains v8.

## [2026-06-28 09:52] implementation+file-back | preflight unwritable journal files
- code: legacy/ad hoc `--journal` preflight now rejects read-only existing journal files and unwritable existing parent directories for missing journal paths before mutation.
- tests: added an append-section regression with a read-only JSONL file; the command returns `journal_append_preflight_failed` and leaves SQLite events, Markdown projection, and journal content unchanged.
- docs: bumped public/package version to `1.8.68` and updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[sqlite-ssot-write-plan]]. schema remains v8.

## [2026-06-28 10:02] implementation+file-back | preflight invalid existing journals
- code: legacy/ad hoc `--journal` write paths now parse and validate existing JSONL before appending, failing before mutation when the audit stream is corrupt.
- tests: added an append-section regression with invalid JSONL; the command returns `journal_append_preflight_failed` and leaves SQLite events, Markdown projection, and journal content unchanged.
- docs: bumped public/package version to `1.8.69` and updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[sqlite-ssot-write-plan]]. schema remains v8.

## [2026-06-28 10:27] implementation+file-back | remove append-section public CLI
- public CLI から append-section を削除し、通常 authoring/file-back は write-page / append-log に寄せた。既存 section_append event は replay/revert compatibility として残す。

## [2026-06-28 10:46] implementation+file-back | fix stale append-log help note
- append-log --help が rename-page 済みの current surface と矛盾する stale note を出していたため、page identity changes は rename-page が扱うという説明へ更新し、regression test を追加した。

## [2026-06-28 11:41] file-back | 今日の開発ゴール [[parallel-agent-substrate-goal]] を新設（Codex 向け）
並行 agent が同一 canonical store を共有して知識共有しながら並行開発する基盤、を今日のゴールに固定。判定は 2-agent 共有 store dogfood が green（並行 write 安全 / 互いの現在状態・直近変化が read 可 / in-flight 認識で二重作業回避 / projection 遅延で md race なし / session 単位 revert）。
write 側基盤（canonical store / WAL / BEGIN IMMEDIATE / session 帰属 / revert-plan --scope session）は実装済、未充足は in-flight 協調 surface と遅延 projection。dogfood-first で落ちた所だけ実装する。新規ユーザは Markdown=SSoT の mode 1 から入る信頼勾配の高信頼端向けで、協調レイヤは単一 agent では不要な形に degrade。

## [2026-06-28 12:03] file back | 初期 persona 設計を再検討（positioning-two-personas に3軸分解 / bridge persona / persona2a-2b / consumer 軸）
[[positioning-two-personas]] に `## Updates` 追記。初期の persona1↔persona2 単一スペクトラムが独立3軸（A on-ramp=実装済で解決 / B リンク密度=価値駆動・逆風 / C corpus 所有者・GTM）を畳んでいたと整理。二項が名前を付け忘れたセル=(Markdown×高密度×nishio 所有)=llm-wiki 森を bridge persona と位置づけ（[[wiki-forest-markdown-import-dogfood-2026-06-25]]）。persona2 を persona2a（高密度 Markdown、served・次 driver 候補）/ persona2b（まばら .md・冷たい HN/Reddit、density 非依存 pitch・dilution 本体）に分割。persona は corpus 所有者軸と AI consumer 軸（[[delivery-cli-plus-skill]]）を分離。
- fallback 理由: grasp write-first runbook が通らなかったため direct Markdown patch で file back。並行 session が共有 main working tree を占有（branch 切替・wiki/code dirty）し git-side guard を満たせず、worktree + shared store は store/output pairing guard（repo store↔repo output のみ）で禁止。SQLite store(.grasp/file-back.sqlite, event<=324) への authoritative 反映は main working tree が空いてから write-page で reconcile 予定。branch: file-back/persona-reconsider-wt（off origin/main 96df1d1）。

## [2026-06-28 12:05] file-back | Grasp-only authority と並行 agent 判断
- judgment: 知識管理から Markdown を外す、は Markdown を authority / concurrent edit target から外す意味なら妥当。Markdown projection は review / backup / publish / fresh-checkout recovery の低頻度 artifact として残す。
- implementation position: `1.8.72` で `write-page` / `append-log --defer-projection`、SQLite-only `history` / `log-records` の `log_append` records、`activity [title]` が入り、2-agent subprocess regression は shared store / deferred projection / cross-session read / session rollback plan まで green。
- next: Grasp-only authority substrate は最小成立、広い real dogfood は未検証。まず `activity` で soft coordination し、二重作業や stale intent が残る時だけ claim/lease を目的名で足す。明確な目的のない既存 command は温存せず削除し、必要になったら分かりやすい名前で作り直す。
- fallback note: 既に `1.8.72` 実装と wiki 更新の未コミット差分があり、通常の grasp write-first preflight が前提にする clean `wiki/` ではないため、この file-back は direct Markdown patch fallback として実施した。

## [2026-06-28 12:13] file-back | competing file-back preflight blocked dirty worktree
別 agent の incident file-back は、この `friction/cross-agent-write` worktree が activity / deferred projection / version bump / file-back で dirty だったため、`scripts/check_file_back_preflight.py` の single-owner clean guard で正しく停止した。衝突をその場で解こうとせず、この pass に畳む判断になったため、[[parallel-agent-write-incident-2026-06-26]] の Open Questions を file-back lock / push ownership / SQLite event session_id / `activity` surface の解決済みとして追記した。これは incident 後 guardrail の live dogfood 成功。

## [2026-06-28 12:15] file back | grasp-backlog に persona2a 優先の実装シグナルを追記
[[positioning-two-personas]] 2026-06-28 再検討の実装含意を [[grasp-backlog]] の「Cross-project graph を first-class edge に + whole-store retrieval」節へ1行: 次に served すべきは persona2a（高密度 Markdown 森）= whole-store cross-project + retrieval が最優先、persona2b 向け come-from 自動昇格は後置。backlog = Codex の作業候補リストなので、再検討を Codex に伝える経路はここ。direct-patch fallback 継続（authoritative store 反映は main tree が静まってから）。

## [2026-06-28 12:23] file back | 並行 session 下の file-back 衝突体験を entity 化
新 entity [[parallel-session-file-back-contention-2026-06-28]]（entities/）。本 session 自身の体験: persona 再検討の file-back が並行 Codex session と単一 working tree / 共有 store を巡って衝突し、grasp write-first runbook が3 guard（dirty-wiki / HEAD-stability / store-output pairing）で順に停止、worktree+共有 store の逃げ道も pairing guard に塞がれた。判明=authoritative file-back は単一 repo working tree に bind される single-writer bottleneck（git delivery は並行安全）、file-back lock は git working-tree level の操作に無視される。回避=isolated worktree の direct-patch + remote-only merge（占有 tree 非接触）。[[parallel-agent-substrate-goal]] の「未充足=in-flight 協調 surface」の実証データとして (a) worktree-aware file-back / 遅延 projection (b) working-tree-level in-flight awareness を含意。[[parallel-agent-write-incident-2026-06-26]]（md/JSONL 層）の sibling（runbook 層）。本 entity 自身も direct-patch fallback で file back。

## [2026-06-28 12:30] file back | 三者三様の修正を [[parallel-agent-substrate-goal]] の開発条件へ反映
Claude Code / Codex の並行 file-back で出た3種類の修正（content delivery 優先の isolated worktree+direct patch、incident entity 化、concept/code surface 化）を、[[parallel-agent-substrate-goal]] の次開発へ反映。結論: これらは競合案ではなく別レイヤの修正なので、次に作るべきは claim/lease 単体ではなく post-guard recovery ladder。preflight が dirty / HEAD moved / semantic log stale で止めた時に、`activity` で owner を見て、owner branch に畳む / isolated direct-patch PR に逃がして pending reconcile を明示する / authority store write は `--defer-projection` へ寄せる / merge 後に canonical reconcile を1回走らせる、という標準手順を Done 条件 3・4 に含める。fallback 理由: repo store が event 324 で止まり、`write-status --no-journal --strict` が `semantic_log_stale` を返したため Grasp write-first preflight が停止。direct Markdown patch で file back。

## [2026-06-28 12:30] file-back | 並行 write 考察 — SUT は detection 層 / fallback 伝播
- [[sqlite-write-concurrency]] の Updates 2026-06-28 に5点を追記: ①並行 write 実験の正しい SUT は write path でなく detection/guardrail 層 ②進歩指標 = silent clobber(06-26) → loud refusal(06-28 preflight が competing file-back を exit 1 拒否) ③耐久層は git commit 履歴(本 repo は file-back store gitignored ゆえ commit を跨ぐ durable は git-tracked Markdown) ④direct-patch fallback は伝播する(Codex の direct patch 後 semantic_log_stale で後続 preflight が停止) ⑤SSoT page 自身も陳腐化する。
- fallback note: 本 file-back は grasp write-first を試みたが `check_file_back_preflight.py` が `semantic_log_stale`(committed log projection が SQLite-events 由来 semantic log と不一致)で exit 1。runbook の escape 条件に従い direct Markdown patch fallback で実施。これは追記④の実例そのもの。

## [2026-06-28 12:33] file-back | 別 harness (Claude Code) の書き込み体験を SSoT(現 main) に着地: [[ai-author-feedback-2026-06-26]] §Updates + [[sqlite-write-concurrency]] §Updates 2026-06-28
前 file-back は使い捨て worktree の fresh store で実行し store ごと消えたため、content は未マージ枝の Markdown にしか無く SSoT 未着地だった（自己実演: worktree 隔離→store が git/Markdown に縮退）。現 main に対しクリーンに再適用。摩擦=cross-machine store 非共有 / write-page handle が read と非対称(bug候補) / content 軽量追記欠如 / env portability、および lock の上の git working-tree/HEAD 層（worktree は tree/HEAD を隔離するが store を割る＝独立軸）。goal ページの運用観察は並行 agent の 1.8.72 実装で重複化したため落とした。

## [2026-06-28 12:38] implementation+file-back | guard failure recovery ladder hints
- code: `scripts/check_file_back_preflight.py` / `scripts/check_file_back_write_start.py` now print `recovery ladder:` hints when guard failure stops a file-back.
- behavior: hints start from `activity --limit 20` ownership inspection and route dirty worktree, HEAD movement, semantic log drift, store event advance, store/output pair mismatch, session reuse, and active lock toward owner-branch fold-in, isolated direct-patch PR with pending reconcile, clean reconcile, preflight rerun, or waiting.
- docs: bumped public/package version to `1.8.73` and updated [[history]], [[grasp-v1-implemented]], [[parallel-agent-substrate-goal]], and [[sqlite-ssot-write-plan]]. schema remains v8.

## [2026-06-28 12:46] file back | 前回 file-back 内容が SSoT store に届いたことを確認 + projection 前 re-adopt ガードを backlog 追加
検証: persona 再検討（positioning Update / grasp-backlog persona2a シグナル / 新 entity [[parallel-session-file-back-contention-2026-06-28]] / index / log）が direct-patch fallback 経由で main に入った後、Codex の ssot-land 系 re-adopt で **file-back store（.grasp/file-back.sqlite, 44 pages）にも全て materialize** されていることを確認（store 内 page "parallel session file-back contention 2026-06-28" 実在、各内容行 present）。∴ 「並行下で store に直接書けず direct-patch fallback しても、adopt は main Markdown から build するので内容は次の re-adopt で自動的に store=SSoT へ流れ込む」。ただし暗黙依存なので、逆向き（store→md full projection）を未取り込み diff のまま走らせると未 reconcile の direct-patch（他 session 分含む）が巻き戻る。この projection 前 re-adopt 強制 check を [[grasp-backlog]] の write-substrate guard 群に [gap] として追加した。

## [2026-06-28 13:22] file-back | [[grasp-backlog]] に write-page handle bug 候補を tracked 化（read と非対称）
ai-author-feedback §Updates 散文にしか無かった bug 候補を backlog の Local write and identity layer に上げ、Codex が拾えるようにした。read <short page_id> 可・write-page <同 id> 不可・stem handle 可。

## [2026-06-28 13:38] implementation+file-back | guard store-to-Markdown projection overwrite before re-adopt
- code: `export-markdown` non-check write mode now previews changed/missing projection files and refuses to overwrite Git-worktree Markdown diffs unless `--allow-projection-overwrite` is explicit.
- rationale: direct-patch fallback or merge can advance Markdown while SQLite is stale; full store-to-Markdown projection must stop and require re-adopt/reconcile instead of resurrecting stale content.
- docs: bumped public/package version to `1.8.74` and updated [[history]], [[grasp-v1-implemented]], [[grasp-backlog]], and [[sqlite-ssot-write-plan]]. schema remains v8.

## [2026-06-28 13:53] implementation+file-back | Git-worktree shared-store dogfood for activity + explicit batch export
- tests: added `test_parallel_agent_git_worktree_dogfood_uses_activity_and_explicit_batch_export`, a Git-worktree shared `.grasp/authority.sqlite` loop where A writes `A` with `--defer-projection`, B checks `activity A`, avoids rewriting A, writes `B` plus a log entry, then batch exports.
- result: Markdown remains unchanged during deferred writes; bare `export-markdown --regenerate-log` refuses with `--allow-projection-overwrite` guidance; explicit batch export writes A/B/Log and `write-status --strict` is clean.
- judgment: for touched-page duplicate rewrite avoidance, `activity` is sufficient in this dogfood and no claim/lease was added. Pre-event intent awareness remains a longer real-dogfood question.

## [2026-06-28 14:05] implementation+file-back | soft page claims for pre-write agent intent
- code: added `claim-page`, `claims`, and `release-claim` as optional soft lease commands backed by SQLite `page_claim` / `page_claim_release` events. `activity` now includes those events as well as write events.
- tests/docs: added a parallel-agent regression where session A claims page A before writing, session B sees the intent, is refused for A, can claim B, and can claim A only after A releases. Public/package version is `1.8.75`; schema remains v8.
- judgment: this closes the specific pre-event intent gap without adding a mandatory write lock, queue, or automated reconcile. Longer real dogfood should decide whether stale claim cleanup or queueing is needed.

## [2026-06-28 14:16] dogfood+file-back | claim/write/release loop in Git worktree shared store
- tests: added `test_parallel_agent_claim_write_release_projection_loop`, combining `claim-page`, `activity`, refused duplicate claim, deferred `write-page`, deferred `append-log`, `release-claim`, explicit batch export, strict status, and session rollback planning in one Git-worktree shared-store loop.
- result: Markdown projection stays old until batch export; bare export refuses without `--allow-projection-overwrite`; claim/release events stay coordination metadata and are excluded from `revert-plan --scope session` candidates.
- judgment: happy-path soft claims do not yet require queueing or mandatory locks. Stale claim cleanup remains a longer real-dogfood question.

## [2026-06-28 14:27] implementation+file-back | fold stale claim state into activity
- code: `activity` now folds `page_claim` / `page_claim_release` state before summarizing events. Claim events expose `claim_status`, `claim_active`, expiry/release metadata, and top-level `active_claims[]`.
- tests: added coverage that expired and released claims remain visible as event-stream history but no longer set `active=true` or appear in `active_sessions[]`.
- judgment: this removes the concrete stale-claim ergonomics gap where TTL-expired or released soft leases could still look like active work through `activity`.

## [2026-06-28 14:37] implementation+file-back | make recovery ladder claim-aware
- code: guard failure recovery hints now include `claims --include-expired` alongside `activity --limit 20`, so stopped agents can inspect soft claim state before choosing a recovery path.
- tests: extended preflight recovery ladder coverage to require the claim-inspection command.
- judgment: this keeps the current direction as observation-first coordination; no queue, mandatory lock, or automated reconcile is added without a stronger dogfood gap.

## [2026-06-28 14:48] implementation+file-back | let write-page target page identity
- code: `write-page` now accepts `--target page-id` and `--target path` for existing-page replacement, while `--create` remains title + `--path`.
- tests: added a regression that reads page identity, writes the same page by page id, then writes another page by source path and verifies store/projection updates.
- judgment: this removes an observation-to-authoring friction point for parallel agents; page identity returned by read/history/activity/claims can now be reused directly instead of converted back to title or file stem.

## [2026-06-28 15:07] implementation+file-back | let claim-page target page identity
- code: `claim-page` now accepts `--target page-id` and `--target path`, sharing the Markdown page resolver used by write targets. `claims <query>` and `activity <query>` also match page_id.
- tests: added a regression that claims a page by page id, inspects it by page_id through `claims` and `activity`, rejects another session claiming the same page by source path, and claims a different page by path.
- judgment: this closes the pre-write intent half of the identity loop introduced by `write-page --target`; observed page identity can now flow into claim, write, and audit without falling back to title/stem conversion. No mandatory lock or queue is added.

## [2026-06-28 15:17] dogfood+file-back | concurrent CLI write-page subprocesses serialize through SQLite
- tests: added a regression that holds an external SQLite `BEGIN IMMEDIATE` writer lock, starts two `write-page --defer-projection` CLI subprocesses against one store, verifies both are waiting, releases the lock, and confirms both writes succeed.
- result: Markdown projection stays old until batch export; store current state has A/B updates; SQLite events contain separate session-a/session-b `page_update` rows; `activity` sees both active sessions; `revert-plan --scope session` keeps the work units independent.
- judgment: this directly backs Done condition 1 of [[parallel-agent-substrate-goal]] at CLI level. WAL / busy_timeout / `BEGIN IMMEDIATE` already provide the needed serialization here; no queue or mandatory lock is justified by this dogfood.

## [2026-06-28 15:31] dogfood+file-back | concurrent CLI append-log subprocesses serialize through SQLite
- tests: added the matching regression for `append-log --defer-projection`: an external SQLite `BEGIN IMMEDIATE` writer lock holds two CLI subprocesses, both wait, and both succeed after release.
- result: `Log.md` projection stays old until batch export; SQLite events contain separate session-a/session-b `log_append` rows; `log-records` / `history A` / `history B` expose the subject+session split; `revert-plan --scope session` keeps each log append as an independent work unit.
- judgment: Done condition 1 explicitly names `write-page` and `append-log`; both write verbs now have CLI-level lock-wait / serialization dogfood without adding a queue or mandatory lock.

## [2026-06-28 15:42] implementation+file-back | activity matches log subjects
- code: `activity <query>` now matches `log_append` subjects as well as touched page title/path/page_id, and `active_sessions[]` now carries `subjects[]`. Text output prints active session subjects too.
- tests: updated shared-store dogfood and claim/write/release regressions so `activity A` includes a recent `log_append` about `[[A]]`; concurrent append-log dogfood now asserts `activity A` / `activity B` expose each log-only session.
- judgment: log-only parallel work no longer requires agents to switch from `activity` to `history` just to notice a session discussing the page. This improves the recovery-ladder in-flight surface without adding a queue or mandatory lock. Public compatibility version is `1.8.80`; schema remains v8.

## [2026-06-28 15:51] dogfood+file-back | log-only activity avoids duplicate work
- tests: added a Git-worktree shared-store regression where session-a appends a deferred log entry about `[[A]]` without touching A, session-b reads `activity A`, sees session-a's log-only active subject, and writes B plus a B log instead of rewriting A.
- result: Markdown projection stays old until explicit batch export; bare export refuses without `--allow-projection-overwrite`; batch export updates only B/Log; `history A` shows both log records; `revert-plan --scope session` separates A's log-only work unit from B's write+log work unit.
- judgment: this is a longer in-flight dogfood for Done condition 3. The existing soft activity surface is sufficient for this log-only duplicate-avoidance path, so no queue or mandatory lock is justified by this evidence.

## [2026-06-28 16:10] dogfood+file-back | dirty guard ladder avoids duplicate work
- tests: added a Git-worktree shared-store regression where session-a owns `[[A]]` through an active claim, a deferred A store update, and a dirty uncommitted `wiki/A.md` projection; session-b hits the dirty guard path, follows the recovery ladder to `activity` / `claims --include-expired`, and writes `[[B]]` instead of claiming or rewriting A.
- result: dirty-path detection reports `wiki/A.md`; recovery hints include `activity --limit 20` and `claims --include-expired`; B's attempted A claim is rejected; B's deferred B page/log work is visible in the shared store; bare export still refuses without `--allow-projection-overwrite` instead of clobbering dirty A.
- judgment: this extends the dogfood from normal duplicate avoidance into guard-failure recovery. The current soft claim + activity + loud projection refusal path is still sufficient for this case, so no queue, mandatory lock, or automated reconcile is justified by this evidence.

## [2026-06-28 16:20] dogfood+file-back | dirty owner reconcile returns clean
- tests: extended the dirty guard ladder regression so the A owner reconciles the dirty `wiki/A.md` draft back into SQLite with `write-page A.md --target path --from-file wiki/A.md --defer-projection`.
- result: after owner reconcile, `export-markdown --check` no longer reports `A.md`; only B/Log remain pending. Bare export still refuses without `--allow-projection-overwrite`, explicit batch export writes B/Log, and `write-status --strict` is clean.
- judgment: the observed recovery path is targeted owner reconcile plus explicit batch projection, not automated reconcile or queueing. This covers a full dirty guard failure -> avoid duplicate work -> clean return loop with existing surfaces.

## [2026-06-28 16:24] dogfood+file-back | dirty guard cleanup keeps rollback boundaries
- tests: extended the dirty owner reconcile regression again so `revert-plan --scope session` on the owner reconcile event selects both A page updates and excludes the A claim event, then A/B release their claims.
- result: after release, `claims --include-expired` has no active claims and contains both released claim ids; `write-status --strict` remains clean because release events do not touch Markdown projection.
- judgment: the dirty guard recovery loop now covers duplicate avoidance, targeted owner reconcile, explicit batch export, session rollback grouping, and claim cleanup without adding a queue, mandatory lock, or automated reconcile.

## [2026-06-28 16:41] dogfood+file-back | multi-turn agent lifecycle works without queue
- tests: added `test_parallel_agent_multi_turn_lifecycle_uses_activity_without_queue`, where session-a claims [[A]], session-b is refused for A, claims [[B]] by path, writes B, and leaves a [[Shared]] log subject.
- result: session-a reads `history Shared` / `activity Shared`, writes/logs A using B context, both claims are released, session rollback plans split A write+log from B write+log, and explicit batch export returns strict clean.
- judgment: this longer temp shared-store lifecycle still fits soft claims + activity + deferred projection; queue / automated reconcile should wait for a live multi-agent runbook gap.

## [2026-06-28 16:52] dogfood+file-back | live runbook lock blocks competing preflight
- live trial: on clean main, session-a ran `check_file_back_preflight.py` against the real repo pair and acquired `.grasp/file-back.lock.json`; session-b then ran the same preflight with a different session id.
- result: session-b failed loudly with active lock owner session, and stderr included the recovery ladder: inspect `activity --limit 20`, inspect `claims --include-expired`, then wait or remove only a confirmed stale lock.
- judgment: normal file-back runbook writers now serialize at the real repo guard layer instead of silently interleaving. This supports wait/owner handoff, not queue or automated reconcile yet; contentful external-agent file-back remains the next live test.

## [2026-06-28 17:03] dogfood+file-back | external sub-agent contentful file-back drill
- `multi_agent_v1` external sub-agent used the same checkout and `.grasp/file-back.sqlite`, and held the normal preflight lock as session `subagent-contentful-live-fileback-20260628T1703JST`.
- While that lock was active, parent competing preflight `parent-competing-live-fileback-20260628T1703JST` was rejected with active lock owner plus recovery ladder; the sub-agent then passed write-start and wrote this goal/log update.
- Judgment: external-agent contentful file-back serialized through the same runbook path; no queue or automated reconcile need was observed here.

## [2026-06-28 17:38] dogfood+file-back | external agent postwrite handoff gap
- follow-up: the external sub-agent completed the contentful goal/log write, but its postwrite was interrupted inside write-status and did not release the runtime files.
- recovery: parent reran check_file_back_postwrite.py with the same GRASP_SESSION_ID; semantic log, lint, and diff check passed, and the lock was released.
- judgment: this validates same-session owner handoff/rescue for a half-closed runbook; it is an ergonomics gap, not evidence for queue or automated reconcile.

## [2026-06-28 18:10] implementation+file-back | active lock hint includes postwrite rescue
- implemented: active-lock recovery ladder now says to rerun postwrite with the lock owner GRASP_SESSION_ID when the owner is unreachable but its writes are already in the store.
- test: preflight recovery-ladder unit test now asserts the postwrite rescue hint and lock-owner session wording.
- judgment: this turns the external-agent half-closed runbook gap into an actionable same-session rescue path, without adding queueing or automated reconcile.

## [2026-06-28 18:25] file-back | parallel substrate goal completion audit
- audit: Done 条件1-5（並行 write safety / read-history-log surface / in-flight duplicate avoidance / deferred projection / session rollback）は current regressions と live dogfood で green。
- result: current main は write-status strict / wiki lint / targeted parallel-agent regression suite が clean。
- judgment: today goal complete。長い real dogfood は concrete future gap を拾う monitoring であり、queue / automated reconcile を今足す理由ではない。

## [2026-06-28 18:32] file-back | post-completion sub-agent write smoke
- note: separate sub-agent performed a post-completion Grasp write-first smoke on clean main after [[parallel-agent-substrate-goal]] was green; long real dogfood remains monitoring.

## [2026-06-28 21:11] file-back | 耐久層 thesis を同 session で自己実証 — interleave されても PR #44 で main 着地
[[sqlite-write-concurrency]] の並行 write 考察 section に payoff bullet を追記: 考察を書いた session の hunk が git-layer interleave で別 agent commit 9dd1607 に吸われたが、PR #44 経由で origin/main に merge され、git commit=耐久層 を自己実証した。
今回は preflight が通った(semantic_log_stale が store-reconcile guardrail #42/#43 で解消)ので grasp write-first で記録。session 通して preflight refusal / fallback 伝播 / commit interleave の3 contention を live で踏んだ締め。

## [2026-06-28 21:15] file-back | 決定 [[adoption-trust-gradient]] を新設（採用は信頼勾配: mode1 オンランプ → mode2 dogfood）
今セッションの設計対話を decision 化。mode1(Markdown=SSoT・grasp=捨てられる派生index) と mode2(grasp=SSoT・Markdown=projection) は authority の矢印が逆で同一コンテンツに同時 on 不可。新規ユーザは mode1(リスク0)から入り信頼が育って mode2 へ＝mode1 は永続オンランプ。mode1→2 の信頼を稼ぐ recovery/review surface は cutover 条件と同一物(二重役割で優先度up)。北極星は [[parallel-agent-substrate-goal]]。協調レイヤは単一 agent では degrade。[[positioning-two-personas]] を authority-direction 連続軸へ一般化。

## [2026-06-28 21:45] file back | 並行 file-back contention の loop が閉じたことを entity に追記
[[parallel-session-file-back-contention-2026-06-28]] に `## Updates`。私の persona file-back 群（positioning Update / persona2a シグナル / 本 entity）は direct-patch fallback 後に Codex の re-adopt で file-back store=SSoT にも到達済みと確認。PR #43 で積んだ backlog [gap]「store→md projection 前 re-adopt 強制」は clobber されたのでなく `1.8.74`（guard projection export against stale markdown、export-markdown 既定で stale 上書き拒否 / `--allow-projection-overwrite` opt-in）として実装に昇格していた（[[grasp-v1-implemented]]）。∴「adopt 済=安全 / 未 adopt direct-patch=clobber 危険」確定、backlog=実働する cross-agent handoff チャネルを実証。entity Open Q 3点目解消・1点目は即時 guard 部分実装済み。

## [2026-06-28 22:18] file back | 「消えた wiki 行を巻き戻しと即断しない」診断 gotcha を entity に追記
[[parallel-session-file-back-contention-2026-06-28]] に診断 gotcha。並行 migration 下で wiki 行が grep から消える原因は (1) stale projection clobber (2) backlog [gap]→実装済み昇格 (3) reword/移動 の3種。本セッションで (2) を (1) と誤診し false alarm を出した。判別は removing commit の diff（`git log -S` → `git show`）を見ること、grep 有無だけで reverted と結論しないこと。

## [2026-06-28 23:10] file-back | remote-merge は projection 層で衝突する — entity Open Q #2 へ data point
- [[parallel-session-file-back-contention-2026-06-28]] に `## Updates` 追記。PR #68 を main へ merge した際 log.md が conflict した経験から: ①append-log placement gotcha で全 session の entry が同じ末尾に着地し append-only projection が構造的 conflict hotspot になる ②本質は git が projection を merge し SQLite events を union していないこと(events store が gitignored = git には projection しか無い)。Open Q #2(direct-patch+remote-merge を正規 fallback 化)への付随課題 = append-only projection の自動 merge。
- reconcile note: 当初は grasp write-first preflight が `semantic log drift` で停止したため direct-patch fallback で記録されたが、merge 前に clean owner がこの PR 上で re-adopt して store=SSoT に流し込んだ。

## [2026-06-29 00:00] implementation | `reconcile-markdown` re-adopts Markdown-only diffs into SQLite SSoT
- code: `reconcile-markdown --output <wiki>` reads current projection files, adopts non-log page diffs as path-targeted `page_update`, adopts missing log sections as `log_append`, and normalizes `log.md` when stored lines and SQLite semantic log diverge.
- regression: added a mixed fixture where `A.md` is Markdown-only dirty while `Log.md` was direct-patched then `import --markdown` made stored lines clean but semantic log stale; reconcile leaves no duplicate log entry and `write-status --no-journal --strict` clean.
- constraint: missing/delete/extra files and record-file log overlays remain blockers; this is a manual recovery surface, not queueing or automatic reconcile.

## [2026-06-29 00:43] implementation | Sync Freshness: full manifest reconcile / tombstone / rename boundary
- implemented: `sync --full-reconcile` walks hosted `listPages` manifest pagination, compares remote id/title/updated/linesCount against local pages, fetches missing/renamed/stale candidates, and reports dry-run candidates without mutation.
- implemented: hosted deletes become active-graph removals plus `project.<project>.sync_tombstones` metadata; same-id title changes keep old hosted title as `hosted-rename-alias` handle.
- decision: partial acquisition namespaces are refreshed by rerunning `acquire` with the same criteria; `sync` refuses them with `partial_acquisition_not_syncable`. hosted `lines[].id` remains observed-only and is not mixed into local `lines.line_id` until a future `external_line_id` schema exists.

## [2026-06-29 00:52] docs | READMEを英語版と日本語版に分離
- README.md は英語の初見読者向け introduction にし、Scrapbox / Cosense を知らない読者にも local graph reader として読める構成にした。
- README.ja.md を追加し、Cosense / Markdown の SSoT を最初から移行せず AI 向けの高速な検索・読解レイヤーとして始められる価値を前面に出した。
- scripts/check_file_back_runbook.py は public README を内部 runbook target から外し、AGENTS/CLAUDE/commands/repo skill 側の guard 検査に集中させた。

## [2026-06-29 01:02] file-back | dirty main fast-forward autostash recovery を記録
- filed: [[parallel-session-file-back-contention-2026-06-28]] に、isolated worktree `codex/sync-freshness` を dirty primary `main` へ `git merge --ff-only --autostash` した時の復旧手順を追記。
- lesson: autostash replay は append-only hotspot の `wiki/log.md` で conflict しうる。append union として両 entry を残し、unmerged state だけを解消して、ユーザ dirty 差分を staged に混ぜない。
- fallback: grasp write-first preflight は `branch differs from origin/main` と既存 dirty wiki paths で停止したため、今回は direct Markdown patch で file back。protected dirty main を push する理由にはしない。

## [2026-06-29 01:04] file-back | SSoT wording belongs to trust-gradient decision
- [[adoption-trust-gradient]] に Updates を追加。README の『SSoT は移動しません』は mode1 だけを不変の約束にするので強すぎ、正しくは『最初から SSoT 移行を要求しない / 信頼が育ったら grasp authoring store へ段階移行できる』。
- 外向き pitch は 'start without moving your source of truth' / 'no up-front migration' / 'gradual migration' を使い、mode1 の安全性と mode2 の目標を同時に出す。

## [2026-06-29 01:08] docs | README の SSoT 表現を「非移行」断定から段階移行へ修正
- correction: 「SSoT は移動しません」は言いすぎ。正しくは、既存 SSoT を移さず検索・読解レイヤーとして始められ、信頼が育ったら grasp authoring store へ段階的に移行できる。
- docs: README.md / README.ja.md / current facts の表現を同じ方向に修正した。

## [2026-06-29 01:18] implementation+dogfood | whole-store cross-project retrieval 1.9.0
- implemented: schema v9 adds `edges.target_project` / `link_kind` / `connection_strength`; `read` / `search` / `backlinks` / `related` / `path` / `unresolved` now default to whole-store when `--project` is omitted and return project/edge metadata.
- dogfood: imported `/Users/nishio/llm-wiki/wikis.yaml` into `/tmp/grasp-whole-store-forest.sqlite` (42 project / 3,404 page / 270,371 line / 24,279 edge). Whole-store `unresolved` surfaced multi-wiki missing concept hubs such as `一つの概念だと思っていたものが入れ子の二つの概念`, `狭義と広義`, `アナロジー`, `利用と探索のトレードオフ`, and `倍速会議` with `projects` / `project_count`.
- performance note: rebuilding inferred weak cross-project edges after every project import was too slow for forest dogfood, so `import-forest` now defers weak edge rebuilds and runs one whole-store derivative refresh at the end.

## [2026-06-29 02:10] file-back | whole-store forest import timing
- filed: [[wiki-forest-markdown-import-dogfood-2026-06-25]] に `1.9.0` whole-store cross-project retrieval dogfood の import timing を追記。final store は 42 projects / 3,404 pages / 270,371 lines / 24,279 edges / 1,639 unresolved targets、約 98 MiB、weak inferred edge 553。
- timing: SQLite `projects.imported_at` と import cache manifest mtime から、project import span 約 223 秒、final derivative/cache 完了まで約 233 秒（3分53秒）と推定。command output の `wall_seconds` は保存していなかったため推定値として記録。
- fallback: grasp write-first preflight は local main が `origin/main` より `4e9b036` だけ ahead で `branch differs from origin/main` 停止。今回は direct Markdown patch fallback で記録した。

## [2026-06-29 03:14] file-back | HN/Reddit Grasp-adjacent survey
[[hn-reddit-grasp-adjacent-survey-2026-06-29]] を追加。HN は OpenKnowledge / Atomic / Karpathy-style LLM wiki など local-first AI knowledge-base の場だが、generic Obsidian + AI との比較・local/privacy・concrete value の突っ込みが強い。
Reddit は r/ObsidianMD / r/AI_Agents で Karpathy-style LLM Wiki、Obsidian vault、agentic project memory が実践・反論込みで動いている。
判断: persona2a は active served 候補、cold HN/Reddit persona2b は skeptical channel。Grasp は CLI substrate / bounded graph read / no up-front SSoT migration を concrete demo で出す。

## [2026-06-28 11:06] file-back | 就寝中自動実行の観察を記録
[[ai-agent-implementation-experiment]] に 2026-06-28 の就寝中自動実行観察を追記。goal「LLM Wikiのインフラとして信頼できるものになる」/ 実行時間 17h 47m 45s / PR #7-#36 / 1.8.36→1.8.71 の進捗は大機能追加より reliability hardening に寄り、無人 run は明確な recovery gap と guard task を積む用途に向くと整理した。

## [2026-06-28 11:10] file-back | record Grasp-only concurrency conditions
- [[sqlite-write-concurrency]] に、Markdown を authority / edit input から外し同一 canonical SQLite transaction path に寄せれば storage-level の並行 safety は得られるが、semantic conflict / stale intent は base event_sequence 等で別途検出する必要がある、と記録。
- [[native-authority-markdown-projection]] に、Grasp-only mode は現行 Markdown projection 方針の stronger profile であり、fresh checkout / review / recovery を grasp-native surface で置換してから guard 付きで cutover すべき、と記録。

## [2026-06-29 11:51] implementation+fallback | persona2a concrete demo artifact
- implemented: `examples/persona2a-vault/` small dense Markdown vault, `docs/persona2a-demo.md` walkthrough, README/docs links, and `tests/test_persona2a_demo.py`.
- demo path: import temp vault, compare grep with `search` / `read` / `backlinks` / `related` / `gather`, then append a session-close log entry and verify `write-status --no-journal --strict`.
- verification: `python3 -m unittest tests.test_persona2a_demo`, `python3 -m unittest tests.test_markdown`, `python3 -m unittest discover -s tests`, `python3 scripts/lint_wiki.py`, `python3 scripts/check_file_back_runbook.py`, and `git diff --check` all passed.
- fallback: grasp write-first preflight stopped because local `main` is already ahead of `origin/main` by `366fd62 docs: file back hn reddit survey`; this wiki update used direct Markdown patch fallback and recorded the reason here.
- 13:01 follow-up: explicit user `file back` request confirmed this existing record. A fresh write-first preflight still refused because local `main` differs from `origin/main` and the wiki file-back paths are already dirty, so this remains a direct Markdown fallback pending later reconcile.

## [2026-06-29 12:19] file-back | AI persona emulation feedback queue
[[grasp-backlog]] に AI persona emulation / feedback queue を追加。複数 persona は corpus owner と AI consumer constraint を分けて扱う。
タスク queue: P1 JP Cosense heavy dogfood refresh / P2a dense Markdown wiki owner / P2b sparse Markdown cold skeptic / P3 AI author file-back agent / P4 constrained low-cost model consumer / P5 public hosted Cosense partial-acquire researcher。
各 run は command trace と outcome judgement を entity page に残し、finding を CLI surface / Skill recipe / docs / backlog / decision の該当先へ routing する。

## [2026-06-29 12:23] file-back | persona emulation success shape
[[grasp-backlog]] の AI persona emulation / feedback queue に success shape を追記。目的は persona ごとの感想集めではなく、grasp の強い用途・弱い導線・次に直すべき面を実走証跡から決めること。
良い run は README / docs / demo に昇格できる concrete outcome story、悪い run は onboarding / zero-hit recovery / raw-dump output / write confidence / report handoff などの修正先へ routing する。
persona run は将来の回帰基準にし、P1/P2a=graph density、P2b=bounded retrieval、P3=write confidence、P4=low-cost portability、P5=acquisition/report handoff と価値を分けて position する。

## [2026-06-29 12:37] file-back | SQLite SSoT does not prevent projection merge conflicts
[[sqlite-write-concurrency]] に 2026-06-29 Updates を追記。SQLite SSoT は live write authority だが、Git merge は gitignored SQLite events を見ず tracked Markdown projection を text merge するため、`wiki/log.md` は conflict しうる。
今回の `codex/persona-emulation-plan` fast-forward + autostash conflict は P3 AI author/file-back agent の bad experience として routing。correctness は保てるが、merge 済み / dirty 継続 / autostash 残存 / append union が人間に重い。
改善方向: events-aware merge、git-tracked durable event bundle、または `log.md` projection の merge 対象外化 / 遅延 batch。現状 recovery は append union と conflict marker / lint / whitespace check。

## [2026-06-29 14:22] file-back | vulnerability triage disagreement graph
[[security-triage-disagreement-graph]] を追加。脆弱性スキャナー方向での Grasp は scanner engine ではなく、scanner finding / Claude Code transcript / 人間議論 / 批判 / judgment を次回 triage に再利用する reasoning layer と位置づける。
核心: scanner finding は observation、Claude thinking は evidence discovery trail、人間議論は position / assumption / decision provenance、judgment は evidence・前提・期限・無効化条件つきの current conclusion。scanner と批判は `vulnerable version present` vs `not reachable in production` のように別命題を見ていることが多いので、中心は finding ではなく disagreement axis / dispute。
非公開プロジェクトへの handoff 方針: 公開 wiki 側は構造仮説だけを渡し、実際の ontology / ingest policy は非公開 scanner report・Claude transcript・ID付き人間議論で壊して決めてもらう。
fallback: grasp write-first preflight は local `main` が `origin/main` より4 commits ahead で `branch differs from origin/main` 停止。今回は direct Markdown patch fallback で記録した。

## [2026-06-29 23:15] file-back | authority modes docs clarify A/B evidence + C reasoning wiki
[[security-triage-disagreement-graph]] に authority modes / A/B+C pattern の Updates を追記。Claude / private-project handoff で Grasp が "Markdown-only indexer" と読まれうる public-doc ambiguity が出たため、`docs/authority-modes.md`・README/README.ja・`docs/markdown.md` 側で read-only indexed evidence と SQLite-authority wiki を分けた。
設計結論: 既存 Wiki A/B は read-only evidence corpus として import し、新規 Wiki C は SQLite-authority reasoning wiki として作る。C はまず page type / frontmatter conventions で `scan-observation` / `security-dispute` / `security-judgment` / `assumption` / `invalidation` / per-file attention ledger を持ち、実データで残った型だけ native command / event type に昇格する。
用語補正: Grasp は event-backed materialized SQLite store であり pure replay-only event sourcing ではない。`claim-page` は soft coordination signal で mandatory lock ではない。Mode 2 の Markdown は review / backup / export projection であって authority ではない。
実装 gotcha: docs recipe の smoke で、空ディレクトリへの `adopt-markdown` は `Markdown folder has no .md files` で失敗すると分かったため、fresh SQLite-authority wiki には seed `Home.md` が必要と記録した。
fallback: `GRASP_SESSION_ID=file-back-20260629T2315-authority-modes python3 scripts/check_file_back_preflight.py` は local `main` が `origin/main` より9 commits ahead で `branch differs from origin/main` 停止。今回は direct Markdown patch fallback で記録した。

## [2026-06-29 23:25] file-back | Grasp organic mention survey
[[grasp-organic-mentions-2026-06-29]] を追加。grasp 直接 mention は HN/Reddit では見つからず、井戸端・motoso・stao など Scrapbox/Cosense 圏に集中していた。
最重要 data point は inajob の非 admin public backup + OpenCode + grasp skill 試用。persona1 周辺の organic adoption と public project outsider persona を示す。
[[hn-reddit-grasp-adjacent-survey-2026-06-29]] と [[grasp-backlog]] P5 に反映。tool routing（cosense-cli ではなく grasp を選ばせる）が次の friction。

## [2026-06-30 04:46] file-back | Open Q #1/#2 は cutover decision の下流（合成を entity に追記）
[[parallel-session-file-back-contention-2026-06-28]] に Update。未決 Open Q #1(pairing guard / projection defer)と #2(direct-patch+remote-merge 正規化 / append-only merge)は独立でなく [[adoption-trust-gradient]] の mode1↔mode2 cutover の下流。mode2 に倒せば Q#1=defer-projection(半実装済) / Q#2=store から regenerate で解ける。leverage は Q#1(ii) を先に。decision でなく分析(cutover 判断は owner)。

## [2026-06-30 11:30] experiment+file-back | mode2 並行編集 stress run → Codex handoff
owner 判断「dogfood を mode2 に倒すか」の go/no-go 材料として、throwaway mode2 store（~/llm-wiki 743p adopt）を2プロセスで並行 loop 編集する stress を実走。新規 entity [[mode2-parallel-edit-stress-2026-06-30]] を追加し index 行を追記。
結果: (A) 無協調は 50 write 中 24 を silent lost（last-writer-wins、エラー0、なお `write-status --strict` は GREEN＝整合≠正しさ）。(B) `claim-page` soft lease + `--defer-projection` で lost 0、staleness は strict が exit 1 で検出、ただし ~50% skip（throughput 半減＋dropped-work）。
実装ブロッカー finding: grasp-wiki 等の高密度グラフで projection/graph compute が病的に遅く（read-only `export-markdown --check` も 25s timeout、link 密度に superlinear 疑い、Python 3.14.5 環境）、grasp-write file-back 自体が踏んだ。
次の実験/修正は owner 指示により**自分で回さず Codex に handoff**: [[grasp-backlog]] の Local write 層に P0a(projection 性能 profile+bisect) / P0b(content-level lost-update guard) / P1a(claim 実効直列化) / P1b(skip retry/merge) と受け入れ条件（lost-update 0 回帰を cutover gate に）を起票。[[adoption-trust-gradient]] の「信頼を測る指標」にも gate 案を追記。
fallback: 上記 projection 性能病で `write-page` が未完 spin したため、本 file-back は grasp write-first を断念し direct Markdown patch で着地。store/projection は divergent（projection ahead）のまま — Codex 側で P0a 修正後に store へ再取り込みが必要。

## [2026-06-30 12:10] codex-fix | mode2 concurrency guard follow-up
Codex が [[mode2-parallel-edit-stress-2026-06-30]] の handoff を受け、P0a/P0b/P1a を実装・再実験。P0a は現 checkout では再現せず（`.grasp/file-back.sqlite` + `wiki` の `export-markdown --check` 0.20s、合成 200p/39,800 edges 0.23s）。
P1a: `claim-page` / `release-claim` の active state check を `BEGIN IMMEDIATE` transaction 内へ移し、同時 claim / 同時 release regression を追加。`write-page` も別 session の active claim 中 target を transaction 内で拒否するようにした。修正前 `claim-page` + retry stress は 50 write 中 6 lost / active claim overlap 6、修正後は 50/50 marker 生存 / overlap 0。
P0b: `write-status --strict` に line_id ベースの `concurrent_page_update_overwrite` guard を追加。無協調 hot-page stress は content lost 自体は残るが、20 write 中 10 lost を strict exit 1 として検出するようになった。
P1b: `claim-page --wait-seconds` / `--retry-interval-seconds` を追加し、claim conflict を skip で捨てず一定時間 retry できるようにした。2プロセス×25 hot-page stress は 50/50 marker 生存、lost 0、overlap 0、strict green。
verification: `python3 -m unittest discover -s tests`、`python3 scripts/lint_wiki.py`、`python3 scripts/check_file_back_runbook.py`、`git diff --check` が green。
fallback: repo store は PR #80 の direct Markdown fallback で projection ahead のままなので、通常 grasp write-first file-back は使わず direct Markdown patch で最小記録した。store への再取り込みは別途 reconcile が必要。

## [2026-06-30 13:03] codex-fix | import performance and import/write race follow-up
User 指示で並行性/性能実験を追加。synthetic Markdown corpus（6 content lines/page、3 links/line）で、修正前は 800p/14400 edges full import 5.75s / 1-file re-import 5.51s、1500p/27000 edges full import 18.06s / 1-file re-import 17.52s、3000p 初回 import は3分超で未完。profile では 1200p/21600 edges の `refresh_edge_resolutions` が 10.54s/11.78s を占め、1-file re-import でも同じ全 edge refresh が走っていた。
fix: `refresh_edge_resolutions` を correlated subquery UPDATE から temp handle-count table + indexed `UPDATE FROM` に変更。store copy 実験で refresh 単体 10.65s → 0.26s。修正後は 1500p/27000 edges full import 5.42s / 1-file re-import 1.21s、3000p/54000 edges full import 9.70s / no-op 1.48s / 1-file 2.12s。
concurrency: full re-import parse 中に `write-page --defer-projection --no-journal` が成功すると、修正前は writer marker が current page から消え、writer `page_update` event だけ残り、`write-status --strict` は projection_dirty 以外に lost import overwrite を検出しなかった。fix: Markdown import は parse 前の selected-project latest `event_sequence` を snapshot し、parse 後の `BEGIN IMMEDIATE` transaction 内で event_sequence が進んでいたら abort する。再実験では import が exit 2 で loud failure、writer marker は store に残った。
design note: 急性性能病は解消したが、現行 import はまだ全 file read / 全 edge build を先に払う。初回 onboarding は manifest-first catalog、page-on-demand parse、background graph hydration、incomplete/stale derivative flag で「使ううちに徐々に良くなる」設計を backlog に残した。
verification: `python3 -m unittest tests.test_markdown.MarkdownImportTests`、`python3 -m unittest tests.test_sqlite_store`、`python3 -m unittest tests.test_cosense tests.test_forest`、`python3 -m unittest discover -s tests` が green。fallback: repo store は projection ahead のままなので、この file-back は direct Markdown patch。

## [2026-06-30 13:42] implementation+file-back | manifest-first no-op Markdown import fast path
- code: `import --markdown` now checks stored Markdown manifest source type / exclude dirs / file set / content hashes before building `MarkdownMirror`; exact no-op re-import returns `markdown_import.fast_path=manifest_hash_noop`.
- concurrency: fast path still rechecks selected-project latest `event_sequence` inside the write transaction, so writer events landing during manifest scan abort instead of being silently overwritten.
- benchmark: 3000p/54000 edges synthetic corpus measured full 14.2s, no-op 0.82s, 1-file 1.85s on this checkout. [[grasp-v1-implemented]] and [[grasp-backlog]] updated; remaining progressive/lazy import work is initial catalog / page-on-demand hydration / incomplete graph status.

## [2026-06-30 13:57] implementation+file-back | manifest-first changed-file Markdown import fast path
- code: `MarkdownMirror.from_folder` now shares single-file record/edge helpers; `import --markdown` uses stored manifest hashes to parse only changed Markdown files when page id / title / aliases / graph_role are unchanged.
- safety: identity-affecting changes still fall back to the existing full parse/rebuild path, and the fast path rechecks selected-project `event_sequence` inside the write transaction.
- benchmark: 3000p/54000 edges synthetic corpus measured full 13.1s, no-op 1.23s, 1-file 1.49s with `manifest_hash_changed_files` and parsed_files=1. Remaining progressive/lazy work is initial catalog / on-demand hydration / incomplete graph status.

## [2026-06-30 14:20] implementation+file-back | catalog-only Markdown import first slice
- code: `import --markdown --catalog-only` now writes a path-derived page catalog without parsing Markdown content, returning `markdown_import.mode=catalog`, `parsed_files=0`, and `markdown_graph.complete=false`.
- UX: `stats` and `read` surface incomplete graph status so lines/backlinks/related/unresolved are not mistaken for complete until normal `import --markdown` hydrates the graph.
- benchmark: 3000p/54000 edges synthetic corpus measured catalog-only 0.27s, later hydrate import 12.44s with 6000 lines / 54000 edges and complete graph.
- docs: [[grasp-v1-implemented]] updated with current facts; [[grasp-backlog]] now leaves page-on-demand / background hydration and finer incomplete/stale query contracts as the remaining progressive import work.

## [2026-06-30 14:38] implementation+file-back | read-hydrate Markdown page-on-demand slice
- code: `read --hydrate` now parses only the selected source file for catalog/partial Markdown graphs, updates title/aliases/lines/edges/manifest hash, and returns `markdown_hydration` plus updated `markdown_graph`.
- UX: normal `read` remains read-only; `--hydrate` is explicit opt-in and refuses `--around-line`.
- benchmark: 3000p/54000 edges synthetic corpus measured catalog-only 0.19s, first page hydrate 0.038s, next 10 page hydrates 0.412s total (~0.041s/page), leaving graph partial at 11/3000 hydrated files.
- docs: [[grasp-v1-implemented]] updated with current facts; [[grasp-backlog]] now leaves auto/background hydration policy and finer stale/incomplete query contracts as remaining work.

## [2026-06-30 14:55] implementation+file-back | gather hydrate-limit query-source slice
- code: `gather --hydrate-limit N` scans incomplete Markdown source files for the query and hydrates up to N matching source pages before calculating link stats, mentions, co-links, and backlinks.
- test: catalog-only 3-page corpus proves only the query-matching source file is parsed and the returned bundle gains backlink/co-link evidence while `markdown_graph` stays partial.

## [2026-06-30 15:20] implementation+file-back | basic retrieval hydrate-limit slice
- code: `search` / `backlinks` / `related --hydrate-limit N` now hydrate up to N query/target-matching Markdown source pages before returning results; `search --hydrate-limit` is literal-mode only.
- test: catalog-only 3-page CLI regression verifies `search needle`, `backlinks B`, and `related B` each hydrate one source page and return the expected hit/backlink/2-hop related result.

## [2026-06-30 15:29] implementation+file-back | incomplete Markdown query contract
- code: `search` / `backlinks` / `related` now report `markdown_graph` and `markdown_query_contract` on incomplete Markdown graphs even without `--hydrate-limit`, so empty results are not treated as complete-corpus absence.
- test: catalog-only 3-page CLI regression verifies no-hydrate empty results include `empty_result_may_be_incomplete=true`; text output includes an incomplete graph warning and hydrate hint.

## [2026-06-30 15:46] implementation+file-back | manual chunked Markdown hydration
- code: added `hydrate-markdown --limit N` as a manual chunk worker for incomplete Markdown graphs; it hydrates unhydrated source files in source-path order and reports before/after graph progress, remaining files, skipped sources, and reason.
- test: catalog-only 3-page regression verifies `limit=2` hydrates exactly A/B, leaves one remaining, and the next chunk completes the graph; CLI regression verifies JSON/text progress output.

## [2026-06-30 16:02] implementation+file-back | bounded Markdown hydration loop
- code: `hydrate-markdown` now supports `--until-complete --max-seconds S`, repeating source-order chunks until graph complete, no progress, or time budget exhaustion; output includes iterations, elapsed_seconds, stopped_by, and the before/after graph.
- test: regression covers `max_seconds=0` no-start behavior, `--until-complete --max-seconds 10 --limit 1` completing a 3-page catalog in 3 iterations, and CLI rejection of unbounded `--until-complete` without `--max-seconds`.

## [2026-06-30 16:15] implementation | opt-in idle Markdown hydration
- Added global --idle-hydrate-seconds S / --idle-hydrate-limit N for supported read/retrieval commands; results keep their pre-idle partial graph contract and report markdown_idle_hydration for future-command progress.
- Updated progressive/lazy import backlog: explicit opt-in idle hydration is implemented; remaining work is default policy/env policy, derivative stale flags, and finer contracts for mentions/co-links/path/unresolved.

## [2026-06-30 16:29] implementation | partial Markdown graph contracts for graph verbs
- Added markdown_query_contract / markdown_graph reporting to mentions, co-links, path, and unresolved on incomplete Markdown graphs so empty results, no-path answers, and rankings are not mistaken for complete-corpus facts.
- Text formatters reuse the existing incomplete graph warning; regression covers catalog-only mentions/co-links/path/unresolved JSON and unresolved text warning.

## [2026-06-30 16:40] implementation | idle Markdown hydration environment policy
- Added GRASP_IDLE_HYDRATE_SECONDS and GRASP_IDLE_HYDRATE_LIMIT as persistent defaults for global idle hydration, so supported retrieval loops can grow incomplete Markdown graphs without repeating CLI flags.
- CLI --idle-hydrate-seconds 0 explicitly disables the env policy for a command; regression covers env-enabled idle hydration and CLI override-to-zero.

## [2026-06-30 16:53] implementation | graph verb hydrate-limit for partial Markdown graphs
- Added command-local --hydrate-limit to mentions, co-links, path, and unresolved so catalog/partial Markdown graphs can hydrate the relevant source page(s) before computing graph-verb results.
- mentions/co-links use query-source scan, path scans both endpoints with a shared limit, and unresolved uses source-order chunk hydration before ranking unresolved targets.

## [2026-06-30 17:03] implementation | field-level partial contracts for incomplete Markdown graphs
- Added markdown_query_contract.partial_fields and result_field_states so retrieval/gather results identify which derived fields are partial on incomplete Markdown graphs.
- gather now attaches the same partial Markdown contract as search/backlinks/related/mentions/co-links/path/unresolved; text output prints the partial field list.

## [2026-06-30 17:14] implementation | read partial field contract for incomplete Markdown graphs
- Added markdown_query_contract.partial_fields/result_field_states to read/read --around-line on incomplete Markdown graphs, marking page lines and graph-neighborhood fields as partial.
- Text read output now prints partial fields alongside the incomplete graph warning; regression covers catalog-only read and read --hydrate.

## [2026-06-30 17:25] implementation | hot-page claim retry regression for cutover gate
- Added a subprocess hot-page regression where two workers claim/read/write/release the same page with claim retry and deferred projection; all markers must survive.
- The regression exports the projection and requires write-status --no-journal --strict to stay green, fixing the first lost-update cutover gate in tests.

## [2026-06-30 17:36] implementation | claim retry throughput benchmark harness
- Added scripts/benchmark_claim_retry_throughput.py to rerun uncoordinated vs claim_retry hot-page contention with real grasp CLI subprocesses.
- Small run (2 workers x 4, think 0.02s): uncoordinated lost 4/8 and strict failed; claim_retry kept 8/8, strict green, completed throughput 0.322x and surviving-marker throughput 0.645x of uncoordinated.

## [2026-06-30 17:50] implementation | incomplete Markdown export guard
- Added an export-markdown contract for incomplete Markdown graphs: JSON now reports markdown_graph, projection_complete=false, and markdown_projection_contract.
- Non-check export from catalog-only/partial Markdown graphs now refuses by default because unhydrated files have no stored lines and can be clobbered; explicit --allow-incomplete-markdown-export is required.

## [2026-06-30 18:01] implementation | partial Markdown query contract progress
- Added result_completeness=partial and result_may_be_incomplete=true to markdown_query_contract so non-empty results on incomplete Markdown graphs are not mistaken for complete result sets.
- Added hydration_progress to the same contract, exposing command-local hydrate-limit progress such as scan, reason, matched_files, hydrated_count, and limit_reached.

## [2026-06-30 18:17] implementation | incomplete graph contract coverage
- Added markdown_query_contract coverage for selected-project link-stats, peek, suggest, ambiguities, cross-project-spread, and cross-project-spreads so catalog-only results are not read as complete corpus facts.
- Text output for those commands now prints the same incomplete graph warning and partial fields note used by retrieval commands.

## [2026-06-30 18:29] implementation | all-project incomplete graph contract
- Added an all-project aggregate markdown_graph for mixed complete/incomplete Markdown stores, including incomplete_projects and contract incomplete_markdown_projects.
- Commands that can run without --project now keep incomplete Markdown projects visible instead of presenting aggregate counts as complete.

## [2026-06-30 18:42] implementation+file-back | incomplete export backup policy
- `export-markdown --allow-incomplete-markdown-export` now requires `--backup-dir` before overwriting existing Markdown files from an incomplete graph, backs up changed existing files, and reports `backup_dir` / `backed_up_files` / `backed_up_count` plus contract `backup_required`.
- Regression: `tests.test_markdown.MarkdownImportTests.test_export_markdown_refuses_incomplete_graph_write_by_default` covers refusal without backup and successful backup+partial projection.

## [2026-06-30 18:53] implementation+file-back | relative Markdown heading/block links
- `import --markdown` now treats relative standard Markdown links to `.md` files, including `[label](Page.md#Heading)` and `[label](Page.md#^block-id)`, as page-level edges while still ignoring HTTP URLs, pure local anchors, and image links.
- Regression: `tests.test_markdown.MarkdownParsingTests` covers parser output and mirror edge materialization for relative heading/block links.

## [2026-06-30 19:17] implementation+file-back | Markdown anchor target line ids
`import --markdown` now stores `edges.target_fragment` and resolves Markdown heading/block fragments to `edges.target_line_id` when the unique target page contains the heading or block id; resolved local-only anchors become self-page line edges.
Schema bumped to `10`; `refresh_edge_resolutions` recomputes `target_line_id` from `target_fragment` so incoming edges survive target-only incremental re-imports.
Regression: `tests.test_markdown.MarkdownParsingTests` covers mirror edge line targets, persisted backlinks output, local anchors, and target-only incremental refresh.

## [2026-06-30 19:29] implementation+file-back | Markdown heading slug anchors
`import --markdown` now resolves heading fragments through GitHub-style slugs, so links such as `[x](Page.md#api-overview)` can target `## API: Overview!`.
Duplicate headings use the same `-1`, `-2` suffix convention during `target_line_id` resolution; schema bumped to `11` because materialized line-target semantics changed.
Regression: `tests.test_markdown.MarkdownParsingTests.test_markdown_heading_anchors_match_github_style_slugs` covers punctuation stripping and duplicate heading suffixes.

## [2026-06-30 19:46] implementation+file-back | materialize Markdown write-alpha anchor fragments
code: Markdown write-alpha edge rows now keep target_fragment for write-page replacement, write-page --create, and append path; refresh resolves target_line_id after page handles are materialized.
tests: added regressions for external Markdown heading fragments, GitHub-style duplicate slug fragments, resolved local-only anchors, and missing local anchors on write/create/append paths.
compat: bumped public version to 1.12.0 and internal schema to 12 because materialized edge semantics changed while table shape stayed the same.

## [2026-06-30 23:07] file-back | make cutover throughput gate explicit
[[grasp-backlog]] and [[adoption-trust-gradient]] now distinguish the already-fixed lost-update correctness gate from the still-open mode2 cutover policy gate.
Next measurement should broaden scripts/benchmark_claim_retry_throughput.py to larger N, multiple think times, and file-back-like read/write/log/projection workload, then report lost=0, strict green, active claim overlap 0, throughput ratios, and p95 claim wait.
Mode2 cutover remains a policy decision until owner chooses acceptable overhead thresholds from that measurement.
