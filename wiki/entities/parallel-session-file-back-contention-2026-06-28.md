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

## Updates

### 2026-06-28: loop が閉じた — gap は実装に昇格、データロスではない

本 entity が flag した divergence / clobber hazard は、cross-agent coordination loop が wiki channel 経由で閉じる形で解消した。

- **私の content は SSoT 両層に到達**: persona 再検討 Update（[[positioning-two-personas]]）/ grasp-backlog の persona2a 優先シグナル / 本 entity は、direct-patch fallback で main に入った後、Codex の ssot-land 系 re-adopt で file-back store にも materialize 済み（store query で確認）。「adopt は main Markdown から build するので、main にある内容は次の re-adopt で自動的に store=SSoT へ流れ込む」＝ cross-agent file-back に明示的な intent 伝達チャネルは不要、を実証。
- **backlog [gap] は clobber でなく実装に昇格**: PR #43 で積んだ「store→md projection 前に re-adopt を強制する check」は、`1.8.74` で実装された（commit `guard projection export against stale markdown`）。`export-markdown` の non-check write mode が Git worktree 内 projection 差分を先読みし、既定では上書きせず re-adopt / reconcile を促す。意図的 deferred batch だけ `--allow-projection-overwrite` を明示。grasp-backlog の該当 [gap] 行はこの実装済み note に置き換わった（[[grasp-v1-implemented]]）。一時 `grep` で gap 行が消えて見えたのは巻き戻しでなくこの昇格。
- **「adopt 済=安全 / 未 adopt の direct-patch=clobber 危険」が確定**: 未 adopt 状態の direct-patch だけが store→md projection で消えうる、という本 entity の Root constraint は正しく、それを `1.8.74` の default-no-overwrite guard が塞いだ。本 Update 自身もこの guard 下にあるので、次の projection で黙って消されない。
- **backlog = 実働する cross-agent handoff チャネル**: gap → 別 agent による実装 → backlog 項目の昇格、が同日中に wiki channel だけで起きた。関連して Codex は dirty-owner reconcile dogfood（PR #59）/ soft page claims など、本 entity の (b) working-tree-level in-flight awareness 方向の協調層も着手している。

∴ Open Questions: 3点目（divergence reconcile を実走して追記）は解消（上記）。1点目（pairing guard worktree-aware 化 / projection defer）は `1.8.74` で即時 clobber guard 部分が実装済み、worktree-aware file-back / projection defer queue は dogfood 必要時まで保留。2点目（direct-patch + remote-merge を正規 fallback として runbook 明文化）は未決のまま。

### 2026-06-28: 診断 gotcha — 消えた wiki 行を「巻き戻し」と即断しない

本セッションで、grasp-backlog の自分の [gap] 行が `grep` で 0 件になったのを見て「stale projection が clobber した（data loss）」と false alarm を出した。実際は **backlog [gap] → 実装済み note への昇格**（`1.8.74 で…実装した` 行へ置換）だった。

並行 SSoT migration 下で wiki 行が消える原因は最低3つあり、見分けないと誤診する:
1. stale store→md projection による clobber（真の data loss。`1.8.74` 以降は default で抑止）。
2. backlog `[gap]` → 実装済みへの昇格（[[grasp-v1-implemented]] / backlog の `X.Y.Z で実装した` 行へ置換）。
3. reword / 別ページへの移動。

判別は **removing commit の diff を見る**: `git log -S '<text>' -- <file>` で最後に触れた commit を特定 → `git show <commit> -- <file>` で `-`/`+` を確認。`grep` の有無だけで「reverted」と結論しない。教訓は本 entity の「adopt 済=安全 / 未 adopt direct-patch=危険」の運用面: 消失を疑ったら store 内在の有無（adopt 済みか）と removing commit の両方を見る。

### 2026-06-28: remote-merge は projection 層で衝突する（Open Q #2 への data point）

direct-patch + remote-merge fallback の「remote-merge」側自体に friction がある。payoff file-back（PR #68）を main へ merge する際、main が並行で進んでおり log.md が conflict した。

- **conflict は log.md の bottom-append 領域に集中する**: append-log placement gotcha で全 session の log entry が同じ末尾行に着地するため、論理的に独立な append 同士が必ず textual conflict になる。append-only の projection は git merge 上の構造的 conflict hotspot。
- **本質は「git は projection を merge し、events を union していない」**: 正しい merge は両 branch の SQLite events を union して projection を再生成することだが、events store（`.grasp/file-back.sqlite`）が gitignored = local scaffolding なので、git には Markdown projection しか無く、projection 層で手 resolve するしかない（[[sqlite-write-concurrency]] の「events ledger は live store 内 authority だが本 repo では gitignored、commit を跨ぐ durable は git-tracked Markdown」の merge 面の帰結）。

∴ Open Q #2（direct-patch + remote-merge を並行下の正規 fallback として明文化するか）への data point: 正規化するなら append-only projection（特に log）の merge conflict をどう自動解消するかが付随課題 ― events-aware merge / merge 時 regenerate / log を git-merge 対象から外す、等。なお本 Update 自体、`semantic log drift` で grasp write-first preflight がまた落ちた（[[sqlite-write-concurrency]] の「direct-patch fallback は伝播する」の再発）ため direct-patch fallback で書かれたが、merge 前に clean owner がこの PR 上で re-adopt して store=SSoT に流し込んだ。
