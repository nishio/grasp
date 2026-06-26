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

`write-page` / `append-section` / `append-log` は1コマンドで次を**別々の操作として直列実行**する（help 逐語: "appends a … journal event, updates the SQLite materialized index, and exports the Markdown projection"）:

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
- **(b) store はそもそも普通共有されない**。`--store` ごとに別ファイル・慣習は `/tmp` 使い捨て。共有 db ファイルが無ければ SQLite ロックは発火しない（競合は無いが**協調も無い**→ stale snapshot を掴む）。
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
