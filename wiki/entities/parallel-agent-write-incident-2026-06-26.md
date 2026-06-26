---
type: entity
summary: 2026-06-26 に複数 Codex session が grasp repo の main / wiki.grasp/events.jsonl / wiki projection を並行更新した時の観測 incident。設計上の対応は llm-wiki-infra-fast-path-plan と grasp-backlog に反映済み。
sources:
  - [[llm-wiki-infra-fast-path-plan]]
  - [[grasp-backlog]]
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

## Open Questions

- `grasp write` は `wiki.grasp/events.jsonl` と projection export に file lock を取るべきか。
- repo-local `/next` / ship loop は unknown ahead commit を見たら push を拒否すべきか、それとも branch push / PR に自動退避すべきか。
- 並行 agent の commit ownership を機械的に識別する metadata を commit message / journal event に入れるべきか。

## 関連分析
- [[sqlite-write-concurrency]] — 本 incident を実例にした SQLite/store レイヤーの並行書き込み設計の考察（authority は SQLite 外・整合単位は import→export の論理 RMW・対策候補）
