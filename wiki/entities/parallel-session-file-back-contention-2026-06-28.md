---
type: entity
summary: 2026-06-28、persona 再検討の file-back session（このページを書いた session 自身）が並行 Codex session と同一 working tree / 共有 store を巡って衝突した観測。grasp write-first runbook は3つの guard で順に停止し（dirty-wiki / HEAD-stability / store-output pairing）、worktree + 共有 store の逃げ道も pairing guard に塞がれた。authoritative file-back は単一 repo working tree に bind される single-writer bottleneck だと判明。回避は direct-patch + remote-only merge。これは parallel-agent-substrate-goal の「未充足=in-flight 協調 surface」の実証データ
sources:
  - grasp CLI / file-back runbook 実走 2026-06-28（本 session）
  - [[parallel-agent-substrate-goal]]
  - [[parallel-agent-write-incident-2026-06-26]]
  - [[sqlite-write-concurrency]]
---

# parallel session file-back contention 2026-06-28

## What happened

2026-06-28、[[positioning-two-personas]] の persona 再検討を file back しようとした session（＝本ページを書いた session 自身）が、並行する Codex / parallel session と `/Users/nishio/grasp` の **単一 working tree** および共有 file-back store `.grasp/file-back.sqlite` を巡って衝突した。grasp write-first runbook（CLAUDE.md「操作 / File back」）は完走できず、direct-patch fallback + remote-only merge で main へ届けた。

[[parallel-agent-write-incident-2026-06-26]] が **md / JSONL ファイル層**の衝突なのに対し、本件は **file-back runbook（guard / lock / working tree 所有）層**の衝突。

## 観測した failure mode（具体・guard メッセージ付き）

3つの guard が**設計通り正しく**停止させた。問題は guard でなく、停止後に並行下で進める経路が無かったこと。

1. **preflight の dirty-wiki guard**: 別 session の untracked / dirty wiki ファイル（`wiki/parallel-agent-substrate-goal.md` 等）で `dirty file-back paths before file-back` で停止。共有 working tree に別 session の in-flight 編集があると preflight は通らない。
2. **write-start の HEAD-stability guard**: file-back 準備中に共有 working tree が別 session に branch 切替され HEAD が動いた（`c8c0e02` → `96df1d1`〔PR #37 merge〕→ branch `friction/cross-agent-write`、`grasp/cli.py` dirty）。`current HEAD ... differs from preflight stamp head` で停止。store の event_sequence は 324 のまま動いておらず、**壊れたのは git working tree 側だけ**だった。
3. **store/output pairing guard**: 逃げ道として isolated worktree（temp output）+ 共有 repo store を試すと preflight が `mixed file-back store/output pair ... Use the repo dogfood pair store='.grasp/file-back.sqlite' with output='wiki', or use a temporary store together with a temporary output. Do not run a temporary output against the repo file-back store.` で拒否。

## Root constraint

**authoritative file-back（store write + Markdown projection）は store/output pairing guard により単一 repo working tree に bind される = single-writer bottleneck。** 一方 **git delivery（branch / push / PR / merge）は並行安全**。

∴ 並行 agent 下では非対称が生じる:
- Markdown を main へ届けるのは並行可能（branch を切って remote 操作だけで merge できる）。
- authoritative **store reconcile は並行不可**（単一 working tree の排他所有が要る）。

## Lock gap

file-back lock `.grasp/file-back.lock.json` は **grasp file-back session しか参照しない**。pure code session（`cli.py` 編集）や git の branch 切替・dirty 化は lock を見ずに working tree / HEAD を動かせるため、**lock を保持していても別 session が file-back を壊せる**。store-level の直列化（SQLite `BEGIN IMMEDIATE`、[[sqlite-write-concurrency]]）は効くが、**git working-tree level の協調が存在しない**のが穴。

## 回避策（本ページ自身もこの経路で file back された）

isolated worktree（off `origin/main`）→ **direct-patch**（Markdown を直接編集、grasp write-first runbook を bypass）→ commit → push branch → PR → merge。**remote 操作のみで、占有された working tree に一切触れない。** `origin/main` が branch の base のままなら conflict 0 で clean merge できる（persona PR #40 / #40 merge `23cab08` が実例）。

代償: **authoritative SQLite store は未 reconcile のまま**（event ≤ 324）。store → main の full projection が将来走ると、store に無い Markdown 編集が上書きされうる divergence が残る。reconcile は working tree が clean な main-based 状態になってから `write-page` で行う必要がある。

## Implications for [[parallel-agent-substrate-goal]]（実証データ）

goal が「未充足 = read 側 in-flight 協調 surface と遅延 projection」と置いたものの、**具体形**が本 session で2つ surface した:

- **(a) worktree-aware file-back / 遅延 projection**: authoritative store file-back が単一 working tree の排他所有を要求する（pairing guard）。並行 agent を成立させるには、(i) lock 下で worktree + 共有 store の file-back を許す、または (ii) store write と Markdown projection を分離し projection を defer / queue する store-write mode（goal の「projection 遅延で md race なし」と同根）が要る。
- **(b) working-tree-level の in-flight awareness**: file-back lock を git working-tree 操作（branch 切替・dirty）が無視する。少なくとも他 session の dirty / HEAD-move を検出して **待つ / 別 base へ退避する recovery path**、理想的には working-tree level の lease が要る。

pairing guard と lock は **single-writer 前提**の設計。substrate goal は N 並行 agent を狙うので、guard 自体が worktree-aware に進化する必要がありうる（goal の Done 条件「並行 write 安全」を file-back runbook 層まで広げる）。

## Open Questions

- pairing guard を worktree-aware に緩めるか（lock 下で worktree + 共有 store を許す）、それとも store-write と projection を分離して projection を defer する方向か。
- direct-patch + remote-merge を「並行下の正規 fallback」として runbook に明文化するか。その場合の store reconcile の責任（後追い file-back を誰がいつ走らせるか）をどう決めるか。
- 本件の divergence（main Markdown に有り / store に無し）を解消する reconcile を、本セッション後に実走して結果を本ページへ追記する。
