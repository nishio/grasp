---
type: plan
summary: 2026-06-28 の開発ゴール。grasp を「並行 agent が同一 canonical store を共有して知識共有しながら並行開発する基盤」として使える状態にする。判定は机上 spec でなく 2-agent 共有 store dogfood が green になること。1.8.72 で deferred projection / activity / SQLite-only log_append history の最小 substrate は入った。次は real dogfood で activity だけで足りるかを測り、不足した時だけ claim/lease 等を足す。
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
3. **in-flight 認識で二重作業を避けられる**: B が「A が今このページを触っている / 触った」と分かり、同じページの二重 rewrite を避けられる。`1.8.72` は `activity [title]` で recent page/session work を読む最小 surface を入れた。claim/lease は real dogfood で activity が足りない時だけ足す。
4. **projection が race しない**: 並行中は Markdown projection を遅延し、md ファイル層で衝突しない（毎-write 同期 export で [[sqlite-write-concurrency]] reason (c) の clobber 面を再導入しない）。`1.8.72` は `write-page` / `append-log --defer-projection` と batch `export-markdown` の regression を持つ。
5. **session 単位で独立 revert**: 事故っても `revert-plan --scope session` で A / B の work unit を独立に巻き戻せる。

## 実装済み vs 未充足（2026-06-28 時点）

| 要素 | 状態 |
|---|---|
| 共有 canonical store への並行 write が crash/lost-update しない | ほぼ実装済（canonical store / WAL / busy_timeout / `BEGIN IMMEDIATE` / state+event 1 transaction） |
| write の attribution（どの agent/session が何を触ったか） | 実装済（`--actor` / `--session-id`、events に記録、preflight session uniqueness、postwrite session marker） |
| session 単位の独立 rollback | 実装済（`revert-plan --scope session`） |
| 他 session の write を read（現在状態 / 直近変化） | 現在状態=`read`、変化=`history` / `log-records`（event-stream, current_state=false, session_id）まで実装済 |
| **in-flight 認識（今どの session が何を作業中か / soft claim）** | 最小実装済（`activity [title]` が touched page/path の recent event と active sessions を返す）。未検証: real dogfood で claim/lease が不要か |
| **遅延 / バッチ projection（write と md export の分離）** | 最小実装済（`write-page` / `append-log --defer-projection`、後段 `export-markdown`）。未検証: 長い real dogfood での運用 ergonomics |

## 2026-06-28 file-back: Markdown を外す時の判断

「知識管理から Markdown を外して Grasp だけにする」は、**Markdown を authority / concurrent edit target から外す**という意味なら、このゴールの方向と一致する。並行 agent が同じ知識基盤を使うには、全 agent が同一 canonical SQLite store を共有し、write は `grasp write` 系に寄せ、並行中の Markdown projection は `--defer-projection` で batch export に回すのが正しい境界。

ただし **Markdown projection 自体を即ゼロにする判断ではない**。現時点の projection は review / backup / publish / fresh-checkout recovery の低頻度 artifact として残す。race するのは projection を per-write の authority 的入力にする時であり、generated snapshot として batch 出力する限り、並行 authoring の critical section には入れない。

`1.8.72` の evidence は「最小 2-agent subprocess regression が green」まで。したがって今の位置は **Grasp-only authority substrate は最小成立、広い実運用は未検証**。次は real multi-agent dogfood を走らせ、`activity` だけで二重作業回避が足りるなら claim/lease は作らない。不足が観測された場合だけ、目的が名前に出る command として追加する。目的の薄い既存 command を温存しない方針は `append-section` public CLI を削除した `1.8.70` と同じ。

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

## 進め方: dogfood-first

机上で spec を確定させず、**まず 2-agent 共有 dogfood を組んで走らせ、実際に落ちた所だけを実装する**（実装事実 first、判明した制約は file back）。

1. 同一 store（temp 可）を共有する2 session を回す最小ハーネスを作る。
2. 上の Done 条件 1–5 を assert する。1・2・5 は通る想定、**3・4 が落ちるはず**。
3. 落ちた所に最小実装を入れる。3 が「`history` を session で引く運用ルール + 軽い surface」で足りるか claim/lease が要るかは、走らせて決める。
4. 判明した制約・設計変更を file back（[[sqlite-write-concurrency]] / [[sqlite-ssot-write-plan]] / [[grasp-backlog]]）。

## スコープの歯止め（mode 1 へ degrade）

この基盤は **信頼勾配の高信頼端**（grasp=SSoT を信じて預ける dogfood）向け。新規ユーザは Markdown=SSoT + grasp=捨てられる派生 index（[[markdown-obsidian-indexed-mirror]]）から入り、信頼が育って初めてこちらへ来る。∴ in-flight / claim 等の協調レイヤは、**単一 agent の利用では一切要らない形に degrade** すること。協調コストを低信頼端に漏らさない。

## Non-goals（today）

- 複数 **人間** の協調編集（Co- 層）。削いだ軸であり対象外。
- 分散 / リモート共有 store。今日は単一マシン上の同一 local store 共有まで。
- Markdown projection の publish/review 体裁の最適化。
