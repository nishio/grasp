---
type: plan
summary: 2026-06-28 の開発ゴール。grasp を「並行 agent が同一 canonical store を共有して知識共有しながら並行開発する基盤」として使える状態にする。判定は机上 spec でなく 2-agent 共有 store dogfood が green になること。1.8.72 で deferred projection / activity / SQLite-only log_append history の最小 substrate、1.8.73 で recovery ladder hints、1.8.74 で stale store→Markdown export refusal、1.8.75 で pre-write intent 用の soft page claim surface、1.8.76 で activity の claim-state fold、1.8.77 で recovery ladder の claim-aware hint、1.8.78 で write-page identity target、1.8.79 で claim-page identity target が入った。Git worktree dogfood regression は activity による同ページ rewrite 回避、claim→write→release→明示 batch export、session rollback candidate 分離を確認済み。追加で SQLite write lock 下の同時 `write-page --defer-projection` 2 subprocess と同時 `append-log --defer-projection` 2 subprocess が待って直列化され、両 session の state/event/log-records/revert-plan が残ることも固定済み。次はさらに長い real dogfood で queue / automated reconcile 要否を測る。
sources:
  - [[sqlite-ssot-write-plan]]
  - [[sqlite-write-concurrency]]
  - [[native-authority-markdown-projection]]
  - [[parallel-agent-write-incident-2026-06-26]]
  - [[parallel-session-file-back-contention-2026-06-28]]
  - [[grasp-backlog]]
---

# 並行 agent 知識共有基盤ゴール

## ゴール（today）

grasp を **複数の AI agent が同一 canonical store（`.grasp/authority.sqlite` 系）を共有し、互いの作業状況を読みながら並行に開発を進める知識共有基盤**として使える状態にする。

これは [[native-authority-markdown-projection]] の cutover（grasp=SSoT）の具体目的であり、[[sqlite-write-concurrency]] が「Co- を削いでも multi-process single-owner の並行は残る」と言った並行を、事故でなく **想定用途** として正面から成立させる作業。位置づけは [[parallel-agent-write-incident-2026-06-26]] が示した失敗モードの裏返し（衝突したのは md / JSONL ファイル層で、SQLite の write 直列化は store の lost update を既に防ぐ）。

## Done 条件 = 2-agent 共有 store dogfood が green

抽象な「使える」でなく、観測可能な受け入れテストで判定する。同一 store を共有する2 session（A / B）で:

1. **並行 write が安全**: A と B が並行に `write-page` / `append-log` しても crash も lost-update も起きない。
2. **互いの現在状態が読める**: A の write 後、B が `read` で現在状態を、`history` / `log-records`（event-stream + session_id）で A の直近変化を認識できる。
3. **in-flight 認識で二重作業を避けられる**: B が「A が今このページを触っている / 触った」と分かり、同じページの二重 rewrite を避けられる。`1.8.72` は `activity [title]` で recent page/session work を読む最小 surface を入れた。2026-06-28 の Git worktree dogfood regression は、B が `activity A` で session-a を見て A の再編集を避け、B/log へ進む判断を固定した。`1.8.75` は event がまだ無い pre-write intent のために `claim-page` / `claims` / `release-claim` を追加した。これは soft lease event であり、SQLite lock / mandatory write lock ではない。
4. **projection が race しない**: 並行中は Markdown projection を遅延し、md ファイル層で衝突しない（毎-write 同期 export で [[sqlite-write-concurrency]] reason (c) の clobber 面を再導入しない）。`1.8.72` は `write-page` / `append-log --defer-projection` と batch `export-markdown` の regression を持つ。`1.8.74` 後の Git worktree dogfood regression は、deferred batch export で bare `export-markdown` が拒否され、意図的 batch だけ `--allow-projection-overwrite` で projection を更新することも固定した。
5. **session 単位で独立 revert**: 事故っても `revert-plan --scope session` で A / B の work unit を独立に巻き戻せる。

## 実装済み vs 未充足（2026-06-28 時点）

| 要素 | 状態 |
|---|---|
| 共有 canonical store への並行 write が crash/lost-update しない | 実装済（canonical store / WAL / busy_timeout / `BEGIN IMMEDIATE` / state+event 1 transaction）。追加 regression で外部 `BEGIN IMMEDIATE` lock 下に2本の CLI `write-page --defer-projection` subprocess と2本の `append-log --defer-projection` subprocess をそれぞれ同時に待たせ、lock 解放後に両方が成功し、A/B の current state / `log-records`・SQLite events・session revert-plan が分離して残ることを確認 |
| write の attribution（どの agent/session が何を触ったか） | 実装済（`--actor` / `--session-id`、events に記録、preflight session uniqueness、postwrite session marker） |
| session 単位の独立 rollback | 実装済（`revert-plan --scope session`） |
| 他 session の write を read（現在状態 / 直近変化） | 現在状態=`read`、変化=`history` / `log-records`（event-stream, current_state=false, session_id）まで実装済 |
| **in-flight 認識（今どの session が何を作業中か / soft claim）** | 最小実装済（`activity [title]` が touched page/path の recent event と active sessions を返す）。`1.8.73` で preflight/write-start failure output から `activity --limit 20` と recovery ladder へ誘導する最初の実行面を追加。2026-06-28 の Git worktree dogfood regression では touched-page 回避に activity だけで足りた。`1.8.75` で pre-write intent 専用に `claim-page` / `claims` / `release-claim` を追加し、`activity` も claim/release event を読むようにした。追加 regression では A が claim 後に write、B が別 page を claim/write、両者が release し、batch export と session rollback candidate 分離まで通した。`1.8.76` で expired/released claim を `activity.active_sessions[]` から外し、`active_claims[]` と claim status を返す。`1.8.77` で recovery ladder も `claims --include-expired` を案内する。`1.8.79` で `claim-page --target page-id|path` と `claims` / `activity` の page_id query match を追加し、観測済み identity で pre-write intent も扱える。未検証: 長い real dogfood で queue / ergonomics が足りるか |
| **遅延 / バッチ projection（write と md export の分離）** | 最小実装済（`write-page` / `append-log --defer-projection`、後段 `export-markdown`）。2026-06-28 の Git worktree dogfood regression で、deferred batch export は `--allow-projection-overwrite` を明示して通す運用に更新済み。未検証: 長い real dogfood での ergonomics |
| 観測した page identity を authoring/coordination に戻す | `1.8.78` で `write-page --target page-id|path` を追加。`1.8.79` で `claim-page --target page-id|path` と `activity` / `claims` の page_id query match を追加。`read --page-id`、`history.current_state_target`、`activity` / `claims` が返す page id / source path を、title/stem に戻さず replacement target / claim target / audit query として使える |

## 2026-06-28 file-back: Markdown を外す時の判断

「知識管理から Markdown を外して Grasp だけにする」は、**Markdown を authority / concurrent edit target から外す**という意味なら、このゴールの方向と一致する。並行 agent が同じ知識基盤を使うには、全 agent が同一 canonical SQLite store を共有し、write は `grasp write` 系に寄せ、並行中の Markdown projection は `--defer-projection` で batch export に回すのが正しい境界。

ただし **Markdown projection 自体を即ゼロにする判断ではない**。現時点の projection は review / backup / publish / fresh-checkout recovery の低頻度 artifact として残す。race するのは projection を per-write の authority 的入力にする時であり、generated snapshot として batch 出力する限り、並行 authoring の critical section には入れない。

`1.8.72` の evidence は「最小 2-agent subprocess regression が green」まで。したがって今の位置は **Grasp-only authority substrate は最小成立、広い実運用は未検証**。`activity` だけでは event が書かれる前の intent が見えないため、`1.8.75` ではその一点だけを目的名付き surface（`claim-page` / `claims` / `release-claim`）として追加した。目的の薄い既存 command を温存しない方針は `append-section` public CLI を削除した `1.8.70` と同じで、今回も汎用 lock manager ではなく page intent event に限定する。

## 2026-06-28 file-back: 三者三様の修正を開発に使う

Claude Code / Codex の並行 file-back では、同じ摩擦に対して3種類の修正が出た。これはバラバラに見えるが、実際は **別レイヤの修正** として全部 substrate goal に使える。

1. **content delivery 優先**: isolated worktree + direct Markdown patch + PR で、知見を止めずに main へ届ける。短期には有効だが、store events に未反映の divergence を残す。
2. **incident entity 化**: [[parallel-session-file-back-contention-2026-06-28]] のように、guard がどこで止めたかを観測データとして残す。次の設計入力になるが、単独では再発を止めない。
3. **concept / code surface 化**: [[sqlite-write-concurrency]] の git working tree / HEAD 層の整理や、`activity` / `--defer-projection` / session_id guard のように、再発防止・観測・rollback surface へ落とす。

この学びから、次の開発は単に claim/lease を足す前に **post-guard recovery ladder** を作るべき。preflight が dirty / HEAD moved / semantic log stale で止めた時、agent が毎回その場判断で別解を作るのではなく、標準手順を返す:

- `activity` / session_id で owner と近い work unit を見る。
- 同じ work unit なら owner branch に畳む。
- content-only で急ぐなら isolated worktree + direct patch PR に逃がし、pending reconcile を log / entity に明示する。
- authority/store 変更なら待つか、shared store に `--defer-projection` で書き、projection は後で batch export する。
- merge 後に canonical store reconcile を1回だけ走らせ、semantic log / projection drift を消す。

したがって Done 条件 3 の「in-flight 認識」は、ページ単位の `activity` だけでなく **止まった後に何を選ぶかの recovery path** まで含めて評価する。Done 条件 4 の「projection が race しない」も、write command の `--defer-projection` だけでなく direct-patch fallback 後の store reconcile まで含めて dogfood する。

次の dogfood の SUT は write path 単体ではなく **detection / guardrail / recovery ladder**。現段階では並行 fault がゼロになることより、2026-06-26 の silent clobber / stale resurrection が 2026-06-28 の loud refusal / actionable recovery に変わることを進歩指標にする。

`1.8.73` でこの recovery ladder の最初の実行面を入れた。`scripts/check_file_back_preflight.py` / `scripts/check_file_back_write_start.py` は guard failure 時に `recovery ladder:` を stderr に出し、dirty worktree / HEAD movement / semantic log drift / store advance / pair mismatch / session reuse / active lock を `activity --limit 20` 起点の次アクションへ振り分ける。`1.8.77` では `claims --include-expired` も同じ ladder に足し、recent ownership と soft claim state を停止時に分けて見られるようにした。これは自動 reconcile / queue / mandatory claim ではなく、止まった agent が別解を作る前に標準選択肢を見るための dogfood surface。

2026-06-28 の追加 dogfood regression（`test_parallel_agent_git_worktree_dogfood_uses_activity_and_explicit_batch_export`）で、より実運用に近い Git worktree 上の shared store loop を固定した。A が `write-page A --defer-projection`、B が `activity A` で session-a を見て A の再編集を避け `write-page B --defer-projection` + `append-log` に進む。Markdown は batch export まで旧内容のまま。Git worktree 内では bare `export-markdown` が `--allow-projection-overwrite` 要求で loud refusal し、明示 batch export 後に `write-status --strict` が clean。`revert-plan --scope session` は A と B の work unit を分離する。この結果、少なくとも「触った直後の同ページ二重 rewrite 回避」には claim/lease を足さず activity で足りる。未解決は「まだ event を書く前の intent」を長い real dogfood でどう扱うか。

`1.8.75` で、その未解決だった pre-event intent gap だけを soft page claim として閉じた。`claim-page <title>` は session_id 付きの `page_claim` event を書き、別 session の active claim があれば拒否する。`claims [title]` は active / expired / released claim を fold して見せ、`release-claim` は owning session で `page_claim_release` を書く。`activity` は claim/release event も読むので、B は A の最初の page update より前に「A が A を触るつもり」を見られる。これは optional coordination surface であり、単一 agent 利用では起動しない。

追加 dogfood regression（`test_parallel_agent_claim_write_release_projection_loop`）で、claim を単独の preflight signal ではなく実 write loop に混ぜた。A が `claim-page A`、B が `activity A` で pre-write intent を見て A の claim を拒否され、`claim-page B` へ退避する。A/B はそれぞれ `write-page --defer-projection`、B は `append-log --defer-projection`、両者は `release-claim` し、Markdown は batch export まで旧内容のまま。Git worktree 内の bare export は `--allow-projection-overwrite` 要求で拒否され、明示 batch export 後に `write-status --strict` が clean。`revert-plan --scope session` は page write/log だけを候補化し、claim/release events は rollback work unit から外れる。ここまでは queue / mandatory lock なしで成立した。

`1.8.76` で stale claim の最初の具体 gap も塞いだ。`claims` は TTL/release を fold していたが、`activity` は event age だけで `active` / `active_sessions[]` を作っていたため、期限切れまたは release 済みの `page_claim` が active work signal に見え得た。現在は `activity` も claim state を fold し、expired/released claim は `active=false` / `claim_active=false` / `claim_status=expired|released` になり、`active_sessions[]` から外れる。active soft claim は top-level `active_claims[]` として読む。

`1.8.78` で観測面から write 面へ戻る identity gap も塞いだ。`read --page-id` / `history.current_state_target` / `activity` / `claims` は page id や source path を返すが、`write-page` は title/handle 前提だったため、agent は観測した identity を人間可読 title/stem へ戻してから replacement する必要があった。現在は `write-page --target page-id <id>` と `write-page --target path <source.md>` が使え、並行時に見た同じ page identity をそのまま update target にできる。

`1.8.79` で同じ identity symmetry を pre-write intent 側にも広げた。`claim-page --target page-id <id>` と `claim-page --target path <source.md>` が使えるため、agent は `read` / `activity` / `claims` で見た page identity を title へ戻さず claim できる。`claims <page-id>` と `activity <page-id>` も同じ claim/work event を絞り込めるので、観測→claim→write→監査の途中で title ambiguity や file stem 依存に戻らない。

2026-06-28 15:17 の追加 regression で、Done 条件 1 の「並行 write が安全」を CLI レベルでも固定した。test は import 済み store に外部 `BEGIN IMMEDIATE` を張り、A/B 2本の `write-page --defer-projection` subprocess を同時起動して lock 待ちにする。lock 解放後、両 command は crash せず成功し、Markdown projection は batch export まで旧内容、store current state は A/B それぞれ更新済み、SQLite events には session-a/session-b の `page_update` が残り、`activity` は両 session を active として返し、`revert-plan --scope session` は各 event を独立候補化する。この evidence は queue を足す理由ではなく、SQLite authority 層の直列化が CLI authoring surface まで届いている確認。

2026-06-28 15:31 の追加 regression で、同じ contention proof を `append-log --defer-projection` 側にも広げた。test は外部 `BEGIN IMMEDIATE` lock 下で A/B 2本の `append-log` subprocess を同時に待たせ、解放後に両方が成功することを確認する。Markdown `Log.md` は batch export まで旧内容のまま、SQLite events には session-a/session-b の `log_append` が分離して残り、`log-records` / `history A` / `history B` がそれぞれの subject と session を返し、`revert-plan --scope session` は各 log event を独立候補化する。これで Done 条件 1 の名指し対象だった `write-page` と `append-log` の両方が CLI-level lock-wait / serialization regression を持つ。

## 進め方: dogfood-first

机上で spec を確定させず、**まず 2-agent 共有 dogfood を組んで走らせ、実際に落ちた所だけを実装する**（実装事実 first、判明した制約は file back）。

1. 同一 store（temp 可）を共有する2 session を回す最小ハーネスを作る。
2. 上の Done 条件 1–5 を assert する。最小 subprocess regression に加え、Git worktree regression で activity-based duplicate avoidance と explicit batch export は通った。`1.8.75` で pre-write claim surface と claim→write→release→batch export loop、`1.8.76` で activity の stale-claim fold、`1.8.78` で observation identity → write target、`1.8.79` で observation identity → claim target / audit query、2026-06-28 15:17 で SQLite write lock 下の同時 CLI `write-page` 直列化、2026-06-28 15:31 で同時 CLI `append-log` 直列化 regression も入った。次は長い real dogfood で落ちる箇所を見る。
3. 落ちた所に最小実装を入れる。claim/lease は `claim-page` の soft event surface までに留め、queue / automated reconcile は実際の運用 gap が出た時だけ足す。
4. 判明した制約・設計変更を file back（[[sqlite-write-concurrency]] / [[sqlite-ssot-write-plan]] / [[grasp-backlog]]）。

## スコープの歯止め（mode 1 へ degrade）

この基盤は **信頼勾配の高信頼端**（grasp=SSoT を信じて預ける dogfood）向け。新規ユーザは Markdown=SSoT + grasp=捨てられる派生 index（[[markdown-obsidian-indexed-mirror]]）から入り、信頼が育って初めてこちらへ来る。∴ in-flight / claim 等の協調レイヤは、**単一 agent の利用では一切要らない形に degrade** すること。協調コストを低信頼端に漏らさない。

## Non-goals（today）

- 複数 **人間** の協調編集（Co- 層）。削いだ軸であり対象外。
- 分散 / リモート共有 store。今日は単一マシン上の同一 local store 共有まで。
- Markdown projection の publish/review 体裁の最適化。
