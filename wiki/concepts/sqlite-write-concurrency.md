---
type: concept
summary: grasp の write path は journal(jsonl)+store(sqlite)+projection(md) の3層で、authority は SQLite 外の plain file にある。「単一人間が使うから並行性は無関係」は AI 著者/複数 agent プロセスが本来の用途なので甘かった。SQLite の write は DB 全体ロックで直列化するが store 1層しか守らず、import→export の論理 RMW と cross-store atomicity は守らない。2026-06-26 incident が実例。
sources:
  - [[parallel-agent-write-incident-2026-06-26]]
  - [[grasp-v1-implemented]]
  - [[grasp-backlog]]
---

# SQLite レイヤーの並行書き込み

## 前提の訂正：消したのは Co- だが、噛んだのは multi-process

grasp は設計時に Scrapbox の **Co-（多人数協調）層を意図的に削いだ**（single-owner = AI 自身が所有する local store）。そこから「単一所有者だから並行性はあまり関係ない」という前提が出た。これは甘かった。

削いだのは「複数の**人間**が同じ wiki を編集する」軸。だが 2026-06-26 に噛んだのは別軸 ―「**1人の所有者のために複数の agent プロセスが同時に書く**」(multi-process single-owner) だ。nishio が3体（Codex1 / Claude2 / Claude3）に同じ repo へ並行 file-back させ、混乱が起きた（[[parallel-agent-write-incident-2026-06-26]]）。grasp の対象ユーザが AI 著者である以上、**並行は事故でなく想定用途**。Co- を削いでも並行性は消えていなかった。

Git レイヤーで複数 writer が衝突するのは既知問題。本ページは **SQLite/store レイヤー**に絞る。

## write path の3層永続化（実装事実）

2026-06-26 incident 当時の `write-page` / `append-section` / `append-log` は1コマンドで次を**別々の操作として直列実行**していた（help 逐語: "appends a … journal event, updates the SQLite materialized index, and exports the Markdown projection"）:

1. **journal append** — `wiki.grasp/events.jsonl` に1行追記。`path.open("a")` の素のファイル追記（[journal.py:62-65](grasp/journal.py#L62-L65)）。git-tracked、**authority**。
2. **store update** — `.grasp/*.sqlite` の materialized index を更新。`sqlite3.connect(store_path)` + `PRAGMA synchronous=NORMAL` + `with connection:`（[sqlite_store.py](grasp/sqlite_store.py)）。gitignored、**派生キャッシュ**。`--store` ごとに別ファイル（既定 `grasp_home()/grasp.sqlite`、慣習は `/tmp` 使い捨て。incident 時は `file-back` / `fresh-parallel-merge` / `post-commit` / `reconcile-from-replay` が `.grasp/` に併存）。
3. **projection export** — `wiki/*.md` を書き出す。git-tracked、**authority/出力**。

∴ **authority は journal(jsonl) と projection(md)、どちらも SQLite の外の plain file**。SQLite は中間キャッシュにすぎない。

## 「SQLite は write でロックを取るのでは？」への答え

半分正しいが、守る層を間違えている。

- 正確には SQLite は**テーブルでなく DB ファイル全体**をロックする。default の rollback-journal mode では writer が commit 時に EXCLUSIVE へ昇格し直列化される。だから**同一 .sqlite ファイル**への並行 write は破損しない。
- ただし grasp は `busy_timeout` も `journal_mode=WAL` も**設定していない**（パッケージ全体に lock / busy_timeout / WAL / flock / threading.Lock は皆無）。∴ 同一 store への2nd writer は待たず即 `database is locked` で**落ちる**（queue されない）。

しかしこのロックは grasp の並行問題を**ほぼ守らない**。4つの理由:

- **(a) authority が SQLite の外**。journal 追記(jsonl)も projection 書き出し(md)もロックを取らない。実際に衝突したのはこの2つ。
- **(b) store は cache であって authority でない（共有/非共有は二次的）**。一般 read は単一の global default `~/.grasp/grasp.sqlite` を共有する（SKILL「store は既定では home に1個…global default」）。`--store` 別ファイル・`/tmp` 使い捨ては *write/file-back dogfood と一回限り read で既定 store を汚さないため* の特殊慣習で、incident で共有 store が無かったのはこの産物（一般用法ではない）。だが**仮に全 agent が同一 store を共有しても** SQLite ロックが守るのは再構築可能な派生キャッシュであって authority ではない。∴ (b) は (a)/(c)/(d) ほど本質的でない — 直せる慣習の問題で、本丸は (a) authority が SQLite 外 / (c) 論理 RMW / (d) cross-store atomicity 無し。
- **(c) 整合の単位が単一 SQL 文でなく論理的 multi-file read-modify-write**: `import(wiki/ を読む) → journal append → store update → 全 md export`。SQLite のロックは store 1ステップ・その文の間だけ。仮に保持しても import→export 区間の isolation は無く、2 agent が同じ pre-state を import → 両方 export で **last-writer-wins / lost update**。incident で Claude2 の stale store からの `append-log` export が別 agent の page を untracked で蘇生/clobber したのがこれ。
- **(d) cross-store atomicity が無い**。journal event だけ着地し projection が伴わない（逆も）状態が起きる。`auto-revert failed markdown projection writes` は**単一プロセスの export 失敗**しか戻さず、プロセス間 race は戻さない。reconcile で Codex1 が見たのがこれ: `replay-journal --check` が落ち、projection に在るが journal に無い page（direct patch 着地）が `extra` 扱い。→ **「git merge が無衝突で通る」と「merged events.jsonl を replay して projection に戻る」は別**。

## 帰結：前提は「ロックし忘れた」より深い所で崩れた

崩れたのは「SQLite をロックし忘れた」ではなく、**整合の単位がアーキテクチャ的に SQLite の外にある**こと。必要な critical section は「自分の import と export の間に他 writer がいない、かつ journal と projection が一緒に commit される」で、これは SQLite の DB ロックでは与えられない。

さらに incident は**全 agent が grasp write path から逃げて git/direct-patch に移った**ことを示した（Claude2 は `git checkout HEAD -- events.jsonl` で自分の journal events を撤回、Claude3 は journal を最初から不触）。結果 journal が静かに authority を失い、Codex1 が reconcile で journal を projection に追いつかせた。**並行下で最初に壊れるのが、まさに journal-as-authority という grasp の中核不変条件**だった。

## 設計オプション（未決・要検討）

- **(A) 論理 write lock**: `wiki.grasp/write.lock` を flock で取り、1コマンド(import→export)全体を直列化。最も安く file-journal 設計を保つ。busy_timeout 相当を application 層で持つ形。
- **(B) compare-and-append journal（楽観）**: write 開始時に読んだ base journal event id / count を記録し、journal が伸びていなければ append・伸びていれば reject して再実行。ロック無しで並行を許す event-sourcing 正解（Codex1 の "base journal event id optimistic check"）。
- **(C) pre-write staleness check**: export 前に「自分の store == 現在の wiki/」を検査し、ずれていたら中断（Claude3 の要望）。防止でなく検知。
- **(D) journal+store を1つの SQLite に畳む**: events テーブル + projection テーブルを同一 db に置き、md export を純粋な read-only 副産物にする。**この時だけ**「SQLite が write を直列化する」が authority を実際に守る（=「ロック取るのでは？」の直感が成立する）。代償は git-diff 可能な jsonl journal を失うこと。WAL + busy_timeout + `BEGIN IMMEDIATE` を1論理 op 全体に保持して初めて意味を持つ。

(A)(B)(C) は file-journal を保つ。(D) は「SQLite のロックを使う」を本当に成立させるが設計の根を変える。現状の最小は **(A) write.lock + (B) 楽観 check + direct md patch の抑止**（journal authority を守る）に見える。

## Open Questions

- write.lock（悲観）か compare-and-append（楽観）か。AI agent は失敗 retry が安いので楽観が合うか。
- default store `grasp_home()/grasp.sqlite` を複数 agent が同時使用したら（busy_timeout 無しで即 fail）。store は常に per-task `/tmp` を強制すべきか。
- direct Markdown patch を**禁止**すべきか（incident では全 agent が逃げ込み、journal authority を壊した張本人）。
- 並行下の per-write 検証コスト（Claude2「confidence コストは upfront でなく ongoing」）を (A)/(B) はどこまで下げるか。

## 関連

- [[parallel-agent-write-incident-2026-06-26]] — 実例 incident（3 agent 視点）
- [[grasp-backlog]] — guard 実装候補
- [[grasp-v1-implemented]] — 現 write path の実装事実

## Updates 2026-06-27
- **方向（nishio）: SQLite を本体/SSoT にし journal も SQLite 内（events テーブル）へ、Markdown は必要時に吐く projection** = 上の option (D)。write が単一 SQLite tx になり、DB の write serialization（=「SQLite はロック取るのでは」の直感）が authority を実際に守る唯一の形。
- **git-diff 喪失の代償は受容**: detailed な event journal は詳細すぎて人間が目視しない＝git-review 価値が低い。人間可読の Markdown projection は publish/review 用に残せるので失うのは「journal の git-diff」だけ。Open Q「journal に lock か / lock か optimistic か」は『authority を SQLite に入れれば DB の write serialization が担う』で大半解決。
- **honest tradeoff（cutover 条件）**: 今回 incident を手で救えたのは journal/Markdown が素の git ファイルで人間が reconcile できたから（[[parallel-agent-write-incident-2026-06-26]]）。SQLite-SSoT + git-diff 喪失はこの脱出口を失う。∴ 並行を source で serialize すると同時に、git-diff/checkout を置換する grasp-native review/recovery（history / write-diff / revert-event）を整えるのが条件。防げれば手 recovery は不要、に賭ける。
- Markdown が export-only 化すると wiki の git 履歴（＝現在の人間 review trail）の意味が変わる: 生成物 snapshot として残すか git-track をやめるか、review trail は grasp `history` 側へ移る。[[native-authority-markdown-projection]] の cutover に concurrency という決定理由が加わった。
- **使い捨て store は store≠authority の症状**（nishio 指摘から）: store を捨てて作り直せるのは cache だからで、これは特殊設定でなく現状の write/一回限り read 慣習。SSoT 化（store=authority）は store を events の唯一コピーにするので **throwaway を構成上消す** → 単一 canonical 永続 store にならざるを得ない（read 用の単一 default store インフラは既に在る）。∴ cutover で足りないのは (1) write/file-back path を canonical store 経由化＋WAL/busy_timeout (2) events を SQLite テーブル化し write を1 tx に (3) export 一方向化、の3つだけ。

## Updates 2026-06-28
- `1.8.70` で public CLI から `append-section` を削除した。既存 `section_append` event は replay/revert 互換として読み続けるが、新規 authoring surface は `write-page` と `append-log` に寄せる。repo-local file-back runbook は SQLite events + Markdown projection の `--no-journal` path を通常経路にしており、上の journal/projection 競合分析は 2026-06-26 incident と JSONL-active 時代の教訓として読む。
- **git working-tree / HEAD は store の上にある lock 管轄外の層**（2026-06-28 live 観測、詳細 [[ai-author-feedback-2026-06-26]] §Updates 2026-06-28 / [[parallel-agent-substrate-goal]]）。post-incident の file-back lock は store / projection write を直列化するが、2 agent が **同一 working tree + 同一 HEAD** を共有すると git レイヤで絡む: 第二 agent（Claude Code）の未コミット変更が第一 agent のブランチ HEAD に乗り、さらに一方の `git switch` が他方の HEAD を動かした。lock は reason (a)(c)(d) を緩和したが、**git の working tree / HEAD は store と別レイヤ**で lock の管轄外。2026-06-26 incident（lock 以前）の git 絡みが lock 導入後も git 層だけ残った形。
- **worktree は tree / HEAD を隔離するが store を割る。** 別 worktree は各自 working tree + HEAD + **各自 `.grasp/` store** を持つので、tree 衝突は消えるが store も非共有になり reason (b)（store は --store ごと別ファイルで非共有）に逆戻り＝共有 substrate が grasp store でなく git / Markdown projection に縮退する（[[native-authority-markdown-projection]] mode2 の逆）。∴ **tree 分離（worktree）と store 共有は独立軸**。両取りは worktree + 明示 `$GRASP_CANONICAL_STORE` 1個共有 + 遅延 / single-owner projection（store 1 : projection 複数の stale を避ける＝ store を別 worktree の `--output` で多重 export しない）。これが [[parallel-agent-substrate-goal]] の三点要件。
- **worktree-per-agent は既に部分運用、衝突は運用の不徹底。** repo に codex 用 worktree が併存（`grasp-fileback-*`）。2026-06-28 の絡みは並行 agent が **共有 main checkout** にいたために起きた＝ infra でなく運用の問題。actionable 候補（[[grasp-backlog]]）: code / wiki を書く並行 agent は worktree 必須化。私（Claude Code）は本 file-back を隔離 worktree（fresh bootstrap した各自 store、Markdown projection だけ commit）で完走し worktree-isolation が機能することを確認したが、その store は共有でなく、**共有 substrate が git / Markdown に縮退する**ことも同時に確認した。

### 並行 write の test 論・耐久層・fallback 伝播（2026-06-28 live dogfood の考察）
- **正しい SUT は write path でなく detection 層**: write path はまだ source level の並行安全を持たない（上の option D cutover 途上）ので、「わざと並行 write して衝突させる」を write path の chaos test と呼ぶのは誤りで、結果既知（壊れる）の negative test にすぎない。意味ある steady-state 仮説は guardrail 層に置く ―「並行 write が起きても preflight / file-back lock / postwrite が検出して拒否 or 復旧する」。これを fault（並行 write）で叩くなら正しい chaos test で、SUT は書き込みパスでなく安全機構。
- **進歩の指標 = silent clobber → loud refusal**: 2026-06-26 は並行 write が黙って clobber / stale 蘇生し、回復は事後の git 手作業だった（[[parallel-agent-write-incident-2026-06-26]]）。2026-06-28 は同型の competing file-back を `check_file_back_preflight.py` の single-owner clean guard が事前に exit 1 で拒否した（log 参照）。同じ fault が「黙って壊す」→「うるさく断る」に変わった差分が guardrail の効きの測定値。上の Open Q「並行下は per-write 検証が ongoing コスト」も、検証が手作業 git review から preflight script に移った分だけ下がった。
- **耐久層の所在（層の取り違え注意）**: working-tree Markdown は clobberable projection ― `write-page` / `append-log` は毎回全 projection を再 export するので store 未反映の他 session page を上書きも stale 蘇生もする。∴「grasp が壊れても Markdown に残る」は層の取り違え。実際の cross-agent 耐久 / 回復層は **git commit 履歴**（commit 済み Markdown projection の snapshot。06-26 の手復旧も `checkout HEAD -- …`）。SQLite events ledger（`session_id` / `event_sequence`）は live store 内では authority だが、本 repo では `.grasp/file-back.sqlite` が gitignored = local scaffolding なので、commit を跨ぐ durable record は git-tracked Markdown 側にある。cf. [[native-authority-markdown-projection]]。
- **direct-patch fallback は伝播する**: agent A が dirty tree で grasp write-first を使えず direct Markdown patch に逃げると、その committed 状態（例: log の semantic projection drift）が次の agent B の `check_file_back_preflight.py` を `semantic_log_stale` で落とし、B も fallback を強いられる。grasp write-first path は agent を跨いで self-heal しない。**この Updates 自体がその実例**: Codex の 12:xx direct-patch fallback 後、後続 file-back の preflight が `semantic_log_stale` で停止し、これも direct patch で書いた。
- **SSoT 自身も陳腐化する**: 本 incident の Open Questions（lock を取るべきか 等）は対応実装 land 後も「未解決」のまま残り、SSoT を読む agent に「まだ検討中」と誤読させていた（2026-06-28 に解決追記）。「過去を current と混同するな」は agent memory だけでなく **SSoT page 自身**に適用する ― 解決は別所への append でなく該当 OQ への解決追記で反映しないと SSoT が嘘をつく。
- **耐久層 thesis は同 session で自己実証された**: 上記「耐久層の所在」の考察を file back する作業中に、前述の git-layer interleave（line 81）が実際に起き、考察を書いた当の Claude Code session の uncommitted hunk が別 agent の commit `9dd1607` に吸われた。だが hunk は失われず、その commit は **PR #44 経由で origin/main に merge** された。私自身は一度も成功 commit していないのに、git commit という耐久層が hunk を main まで運んだ ―「working-tree は clobberable / git commit が耐久層」を、その主張を書いた session 自身が身をもって裏づけた。lock 管轄外の git 層で clobber されかけても、commit された時点で耐久層に入る、が実地で確認できた。
- **高頻度並行 file-back では `log.md` が merge bottleneck ＝ content と log を分離して着地させる技法。** 2026-06-28 のこのセッションで複数 Codex agent が分単位で PR を merge する中、私の file-back PR は **`log.md` の append が競合源**になり繰り返し stale 化した（content ページ自体は無競合）。さらに `gh pr merge` がコマンド上は流れても実際は未 merge のまま（silent failure）になり、read-back で初めて検知した。技法: (1) **content ページ変更だけの PR にし `append-log` を切り離す**と、非重複ファイルは main が動いてもクリーンに merge できる。log entry は contention が落ち着いてから batch する。(2) merge 後は必ず read-back で着地確認（[[ai-author-feedback-2026-06-26]] §Updates の verification discipline）。構造的には [[parallel-agent-substrate-goal]] の遅延 projection と同型＝**append-only な共有ファイル（`log.md`）への per-write 着地が並行の衝突面**で、per-write を batch にずらすと衝突が消える。本 bullet 自体も content-only で着地させた（技法の実演）。
- **Grasp-only concurrency の判断**: 「知識管理から Markdown を外す」が Markdown を authority / edit input から外し、全 agent が同じ canonical SQLite store に同じ transaction write path で書く、という意味なら、旧事故の主因（JSONL append、Markdown patch/import、store/projection の cross-store split）は消える。SQLite の single-writer serialization が authority に届くので、複数 agent write は破壊的 interleave ではなく wait / deterministic failure になる。ただしこれは storage consistency の話で、2 agent が同じ古い state を読んで別々に妥当な更新を出す **semantic conflict / lost intent** は残る。長い作業単位には base event_sequence、session/lock、または optimistic precondition が必要。`sync` / `acquire` など別 write path が同じ canonical transaction/event model に乗るまでは「Grasp-only」と呼ばない。
