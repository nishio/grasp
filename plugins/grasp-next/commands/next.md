---
description: grasp の作業ループを file back, verify, commit, push まで閉じ、次候補を日本語で出す
argument-hint: [focus]
---

# grasp next

この Codex slash command は、Claude Code の `/ship-next` と同等の grasp ship loop を実行する。

## Preflight

1. まず現在の状態を読む。
   - `git status --short --branch`
   - `git diff --stat`
   - `git diff HEAD`
   - `git log --oneline --decorate -5`
2. `$ARGUMENTS` があれば、差分理解と次候補提示の focus として扱う。
3. `python3 --version` を確認する。grasp は Python 3.10+ が必要なので、`python3` が 3.9 以下なら Codex bundled Python（例: `/Users/nishio/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`）などの Python 3.10+ を `PYTHON_BIN` として使う。
4. 既存のユーザ変更や並行 session の変更を勝手に戻さない。commit する時は、意図した自分のファイルだけを明示して stage する。
5. 作業ツリーが clean なら empty commit は作らない。current wiki/backlog を読んで「次にやるなら」だけを日本語で答える。

## Plan

差分がある時は、以下の順で進める。

1. 何が変わったかを把握する。
2. useful facts を development wiki に file back する。
3. 検証を走らせる。
4. 検証が通った時だけ commit し、`$PYTHON_BIN scripts/check_push_ownership.py` を通してから current branch を `origin` へ push する。
5. 日本語で短く結果と次候補を返す。

検証失敗、merge/rebase が必要な remote divergence、push ownership guard 失敗、または stage 対象が曖昧な user hunk がある時は、commit/push せずに止めて、blocking output と判断理由を日本語で出す。

## Commands

### 1. 差分理解

- `git diff HEAD` を読み、実装変更、テスト変更、docs/wiki 更新を分けて理解する。
- `git status --short --branch` で current branch と ahead/behind を確認する。
- `origin/main` との分岐が疑わしい時は `git fetch origin main` と `git log --left-right --cherry-pick origin/main...main` で重複 merge / follow-up を確認する。

### 2. File Back

有用な事実を、必要な場所にだけ反映する。

file back は grasp write first で行う。まず gitignored store を更新する:

```bash
git fetch origin
export GRASP_SESSION_ID="file-back-$(date -u +%Y%m%dT%H%M%SZ)-<topic>"
$PYTHON_BIN scripts/check_file_back_preflight.py
```

この preflight は no-journal default で `.grasp/file-back.sqlite` を import/update し、current upstream（なければ `origin/main`）を基準にして、未使用 session id、fresh store は gitignored `.grasp/file-back-adopt.jsonl` へ bootstrap、remote 分岐なし、wiki dirty なし、退役済み JSONL path の再作成なし、`write-status --no-journal --strict`、projection policy check を確認し、gitignored preflight stamp に session/head/base を記録する。repo default store/output pair は `.grasp/file-back.sqlite` + `wiki` で、temp dogfood は temp store + temp output を使い、default store と temp output を混在させない。tracked `wiki.grasp/events.jsonl` は `1.8.18` で退役・削除済みで、通常編集は repo に JSONL を作らない。最初の write command 直前に `$PYTHON_BIN scripts/check_file_back_write_start.py` を走らせ、preflight 後に projection / stamp / store status が動いていないことを import なしで確認する。その後、表現できる変更は `append-section` / `write-page` / `append-log` を `--output wiki --no-journal` 付きで使う。`GRASP_SESSION_ID` は同じ file-back の全 write command と postwrite で保持する。postwrite は同じ session id を要求し、preflight stamp の session/head/base 一致と SQLite events 由来の semantic log projection も確認する。任意 frontmatter merge、canonical docs、曖昧 handle、混在 hunk など grasp alpha が安全に扱えない場合だけ direct Markdown patch に fallback し、理由を `wiki/log.md` に残す。

`--journal` / `--with-journal` は CLI の legacy/ad hoc audit 用には残るが、repo runbook では `--with-journal` を使わない。JSONL 調査が必要な時は task-local の明示 path を使い、別途 migration decision を切るまで repo artifact として commit しない。

同じ `.grasp/file-back.sqlite` への write 系 command は直列に実行する。並列 write で projection が stale になったら、対象 page を直列で `write-page --from-file --no-journal` し直してから `scripts/check_file_back_postwrite.py` を通す。

複数 wiki page を direct patch fallback してから store に戻す場合も、1 page patch → `write-page --from-file --no-journal` → 次 page の順で行う。`write-page` の projection export は全 page を書くため、未反映の direct patch は上書きされる。

- 実装済み/current behavior: `wiki/entities/grasp-v1-implemented.md` または関連 entity page。
- 残作業: `wiki/grasp-backlog.md`。
- 判断や rationale: `wiki/decisions/`。
- 時系列記録: `wiki/log.md` に `## [YYYY-MM-DD HH:MM] <op> | <desc>`。

file back は factual and scoped にする。未来の over-spec は避ける。

### 3. Verification

必ず実行する。

```bash
$PYTHON_BIN -m unittest discover -s tests
python3 scripts/lint_wiki.py
python3 scripts/check_file_back_runbook.py
git diff --check
```

変更内容に関係する時は、小さな dogfood command を 1 つ走らせる。file-back / projection 周りを触った時は、`scripts/check_file_back_postwrite.py`（no-journal default、SQLite events 由来の semantic log projection check を含む）を必須にし、重要な観測があれば file back する。

### 4. Commit And Push

検証が通った場合だけ実行する。

- `git diff HEAD -- <path>` で stage 対象が自分の意図した変更だけか確認する。
- 共有 `main` では、確定した path だけを単一コマンドで atomic に stage + commit する。
- commit message は concise にする。
- commit 後、push 前に `git fetch origin` と `$PYTHON_BIN scripts/check_push_ownership.py` を実行する。この guard は dirty worktree、behind branch、通常 ship-loop からの protected branch（`main` / `master`）push を止める。
- current branch を `origin` へ push する。
- 直後に `git log --oneline --decorate -1` と `git status --short --branch` で着地を確認する。

## Verification

この command の completion 条件:

- unittest が通っている。
- wiki lint が通っている。
- file-back runbook checker が通っている。
- `git diff --check` が通っている。
- file-back / projection 周りを触った時は `scripts/check_file_back_postwrite.py`（no-journal default、SQLite events 由来の semantic log projection check を含む）が通っている。
- commit 後の `scripts/check_push_ownership.py` が通っている。
- commit と push が成功している、または clean tree のため commit 不要と判断している。
- 失敗時は commit/push していない。

## Summary

最後の返答は日本語で、短く次を含める。

- commit hash と pushed branch、または commit 不要だった理由。
- verification results。
- caveat / known residual risk。
- `次にやるなら`: `wiki/grasp-backlog.md` から leverage の高い候補を 1-3 個。

## Next Steps

次候補は、実装に着手できる粒度で書く。曖昧なテーマ名だけで終えず、最初の concrete action まで落とす。
