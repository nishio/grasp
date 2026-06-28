---
type: plan
summary: 2026-06-28 の開発ゴール。grasp を「並行 agent が同一 canonical store を共有して知識共有しながら並行開発する基盤」として使える状態にする。判定は机上 spec でなく 2-agent 共有 store dogfood が green になること。write 側基盤（canonical store / WAL / BEGIN IMMEDIATE / session 帰属 / revert-plan --scope session）はほぼ実装済みで、未充足は read 側の in-flight 協調 surface と遅延 projection。dogfood-first で落ちた所だけ実装する。
sources:
  - [[sqlite-ssot-write-plan]]
  - [[sqlite-write-concurrency]]
  - [[native-authority-markdown-projection]]
  - [[parallel-agent-write-incident-2026-06-26]]
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
3. **in-flight 認識で二重作業を避けられる**: B が「A が今このページを触っている / 触った」と分かり、同じページの二重 rewrite を避けられる。← **現状 surface が無い。今日の主対象。**
4. **projection が race しない**: 並行中は Markdown projection を遅延し、md ファイル層で衝突しない（毎-write 同期 export で [[sqlite-write-concurrency]] reason (c) の clobber 面を再導入しない）。← **現状 write 毎に同期 export。今日の対象。**
5. **session 単位で独立 revert**: 事故っても `revert-plan --scope session` で A / B の work unit を独立に巻き戻せる。

## 実装済み vs 未充足（2026-06-28 時点）

| 要素 | 状態 |
|---|---|
| 共有 canonical store への並行 write が crash/lost-update しない | ほぼ実装済（canonical store / WAL / busy_timeout / `BEGIN IMMEDIATE` / state+event 1 transaction） |
| write の attribution（どの agent/session が何を触ったか） | 実装済（`--actor` / `--session-id`、events に記録、preflight session uniqueness、postwrite session marker） |
| session 単位の独立 rollback | 実装済（`revert-plan --scope session`） |
| 他 session の write を read（現在状態 / 直近変化） | 現在状態=`read`、変化=`history` / `log-records`（event-stream, current_state=false, session_id）まで実装済 |
| **in-flight 認識（今どの session が何を作業中か / soft claim）** | **未着手。Done 条件 3 の本丸** |
| **遅延 / バッチ projection（write と md export の分離）** | **未着手。現状 write 毎に同期 export。Done 条件 4** |

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
