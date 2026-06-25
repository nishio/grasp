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
4. 検証が通った時だけ commit し、current branch を `origin` へ push する。
5. 日本語で短く結果と次候補を返す。

検証失敗、merge/rebase が必要な remote divergence、または stage 対象が曖昧な user hunk がある時は、commit/push せずに止めて、blocking output と判断理由を日本語で出す。

## Commands

### 1. 差分理解

- `git diff HEAD` を読み、実装変更、テスト変更、docs/wiki 更新を分けて理解する。
- `git status --short --branch` で current branch と ahead/behind を確認する。
- `origin/main` との分岐が疑わしい時は `git fetch origin main` と `git log --left-right --cherry-pick origin/main...main` で重複 merge / follow-up を確認する。

### 2. File Back

有用な事実を、必要な場所にだけ反映する。

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
git diff --check
```

変更内容に関係する時は、小さな dogfood command を 1 つ走らせ、重要な観測があれば file back する。

### 4. Commit And Push

検証が通った場合だけ実行する。

- `git diff HEAD -- <path>` で stage 対象が自分の意図した変更だけか確認する。
- 共有 `main` では、確定した path だけを単一コマンドで atomic に stage + commit する。
- commit message は concise にする。
- current branch を `origin` へ push する。
- 直後に `git log --oneline --decorate -1` と `git status --short --branch` で着地を確認する。

## Verification

この command の completion 条件:

- unittest が通っている。
- wiki lint が通っている。
- `git diff --check` が通っている。
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
