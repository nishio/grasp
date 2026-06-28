---
type: entity
summary: 2026-06-26 に複数 Codex session が grasp repo の main / wiki.grasp/events.jsonl / wiki projection を並行更新した時の観測 incident。設計上の対応は SQLite events / file-back lock / push ownership / activity surface として実装へ反映済み。
sources:
  - [[llm-wiki-infra-fast-path-plan]]
  - [[grasp-backlog]]
  - [[sqlite-ssot-write-plan]]
  - [[parallel-agent-substrate-goal]]
---

# Parallel agent write incident 2026-06-26

## What Happened

- 2026-06-26、複数の Codex session が同じ `/Users/nishio/grasp` repo で wiki file-back / commit / push 系の作業を並行していた。
- ある file-back request の開始時点で、primary worktree は single-owner clean state ではなかった。`git status --short --branch` は `main...origin/main [ahead 1]` と、未コミットの `wiki.grasp/events.jsonl` / `wiki/concepts/come-from-declared-gather.md` / `wiki/decisions/positioning-two-personas.md` を示していた。
- local `main` の `HEAD` は `013d1ee docs: file back | value-is-problem-solving-not-novelty ...` で、`origin/main` は `5d89d4c test: replay rename revert in wiki history sequence` だった。つまり remote にまだ無い commit が primary branch 上に存在していた。
- 未コミットの `wiki.grasp/events.jsonl` には別 session の log append / page update が含まれていた。これは primary worktree の Markdown projection と journal が、別 agent の作業途中状態を含んでいることを意味する。

## Risk Observed

- `git add <paths>` は commit に混ざる hunk を制限できるが、`git push origin main` は branch 上の ahead commit 全体を送る。したがって「自分の path だけ stage した」ことは、unknown ahead commit を push しない保証にならない。
- grasp の `write-page` は journal append と SQLite update のあと、全 Markdown projection を export する。primary worktree に store / journal へ未反映の別 agent direct patch があると、後から走った `write-page` がその projection を stale store の内容で上書きしうる。
- `write-status --strict` は選択した store / journal / projection の consistency を検査するが、「この ahead commit は誰のものか」「dirty path は別 agent の所有物か」「push してよいか」は判断しない。

## Immediate Handling

- primary `main` では `grasp write` / commit / push を実行しなかった。
- `origin/main` から isolated branch `codex/fileback-parallel-agent-writes` を作り、そちらで file-back を行った。
- commit `6c166af docs: file back parallel agent write guard` で、[[llm-wiki-infra-fast-path-plan]] / [[grasp-backlog]] / `AGENTS.md` に設計上の guard 方針を記録した。ただし primary `main` が別 agent の dirty state を持っていたため、この branch は merge / push せず止めた。

## 2026-06-27 Merge Follow-up

- `.grasp/*.sqlite` は `.gitignore` 配下であり、worktree で触った SQLite store 自体は merge 対象ではなかった。git 管理対象は `wiki.grasp/events.jsonl` と Markdown projection。
- `codex/fileback-parallel-agent-writes` を current `main` に Git merge するシミュレーションは text conflict なしで通ったが、merged `events.jsonl` の `replay-journal --check` は失敗した。Git merge が通ることと grasp journal authority が clean であることは別。
- 原因は、current `main` 側にも direct patch 由来の page create / update があり、それらが journal replay authority に未反映だったこと。branch の journal events を単純に足すと、projection は人間には merge 済みに見えても journal から再構成できない。
- 対応は branch merge ではなく、current `main` の projection を基準に journal を先に reconcile し、その後 guard / incident 記録を fresh `grasp write` で追加することにした。

## Lesson

- 共有 `main` で必要なのは「自分の hunk だけ stage」だけでなく、**push ownership** と **projection ownership** の確認である。
- file-back / ship loop の preflight は、`git fetch origin main`、`git log --left-right --cherry-pick origin/main...main`、`git status --short` を見て、unknown ahead commit と dirty wiki/journal path を検出する必要がある。
- guard が落ちたら、その場で解決しようとせず isolated worktree / branch に逃がす。あとで人間または明示 owner が merge 順を決める。
- grasp-backed wiki の merge 判定は Git conflict だけでは足りない。`export-markdown --check` と `replay-journal --check` が両方 clean であることを merge 完了条件にする。

## Durable Layer After 1.8.72

Markdown projection は耐久 / 回復の本体ではない。`write-page` / `append-log` の per-write full projection export は、並行 writer の stale store から clobber や stale resurrection を起こしうる。`1.8.72` 以降の並行 authoring では、Markdown は `--defer-projection` で遅延し、節目で batch export する generated snapshot として扱う。

真の耐久 / 回復層は **SQLite events ledger + git commit**。SQLite events は `event_sequence` / `event_id` / `session_id` / `actor` で因果順・所有者・rollback unit を保持し、`history` / `activity` / `revert-plan --scope session` の read/recovery surface になる。git commit は人間 review・backup・publish 用の snapshot 境界であって、並行 write の coordination primitive ではない。

2026-06-28 の live dogfood では、別 agent の competing file-back が dirty worktree を検知した `check_file_back_preflight.py` によって止まり、`friction/cross-agent-write` の activity/deferred-projection 作業に合流する判断になった。これは incident 後に追加した guard が、実際の並行 file-back で conflict を拡大せず止めた証拠。

## Open Questions

- `grasp write` は `wiki.grasp/events.jsonl` と projection export に file lock を取るべきか。解決（2026-06-28）: repo-local normal file-back は tracked JSONL を退役し、`.grasp/file-back.lock.json` を preflight で取得、write-start で再検証、postwrite が clean な時だけ解放する。shared-store authoring は `--defer-projection` で projection export を write critical path から外す。
- repo-local `/next` / ship loop は unknown ahead commit を見たら push を拒否すべきか、それとも branch push / PR に自動退避すべきか。解決（2026-06-28）: `scripts/check_push_ownership.py` が dirty worktree、behind branch、通常 ship-loop からの protected branch push を block する。feature branch push / PR に逃がし、protected branch は明示 review 時だけ許す。
- 並行 agent の commit ownership を機械的に識別する metadata を commit message / journal event に入れるべきか。解決（2026-06-28）: ownership は SQLite events の `session_id` / `actor` に置く。postwrite は preflight 後の全 event が同じ `session_id` を持つことを検証し、`activity` command が page/path ごとの actor/session_id/recent active sessions を read surface 化する。

## 関連分析
- [[sqlite-write-concurrency]] — 本 incident を実例にした SQLite/store レイヤーの並行書き込み設計の考察（authority は SQLite 外・整合単位は import→export の論理 RMW・対策候補）
