---
type: plan
summary: 既存 backlog とは別に、最速で LLM Wiki の日常インフラとして grasp を dogfood するための計画表。目標は native authority + Markdown projection へ一気に完成移行することではなく、file-back の普段使いを grasp write 経由にする最短 slice を切ること。
sources:
  - [[native-authority-markdown-projection]]
  - [[write-layer-alpha-and-replay-test]]
  - [[persistence-custom-format]]
  - [[grasp-backlog]]
---

# LLM Wiki infra fast-path plan

このページは [[grasp-backlog]] とは別の **実行計画表**。全 backlog を正規化しない。目的は「LLM Wiki の日常 file-back / draft / index 更新が、最短で grasp 経由で回る」状態を作り、authoring dogfood loop を太くすること。

## Goal

最短の usable state:

- Codex / file-back skill が Markdown を直接 patch せず、`grasp write` 相当の authoring surface を呼ぶ。
- grasp native store（＋ durable journal）が authority になり、`wiki/` Markdown は generated projection として commit / review できる。
- no-op export は安定し、git diff が人間に読める。
- 壊れた時は journal / status / diff / revert で戻せる。

Non-goals for this fast path:

- full editor UI。
- come-from render / transclude / typed links。
- whole-store cross-project first-class edge の完成。
- perfect external Markdown edit merge。
- semantic embedding search。

## Plan table

| Phase | Outcome | Implement | Dogfood check | Done when | Explicitly defer |
|---|---|---|---|---|---|
| 0. Freeze contract | 迷わない最小契約 | event journal の最小 schema を決める。`page_create`, `page_update`, `section_append`, `page_rename`, `log_append`, `projection_export` 程度。SQLite primary か journal primary かを仮決めする | grasp wiki の既存 page 1枚を手で event に変換し、projection で同じ Markdown が出るかを見る | journal / projection / rollback の責務が1ページに書ける | undo 完全設計、multi-user conflict |
| 1. Adopt one wiki | 既存 Markdown を native authority 候補に取り込める | `grasp adopt-markdown wiki --project grasp-wiki --journal wiki.grasp/events.jsonl`。frontmatter id を採用し、無ければ page id / line id を mint。adoption manifest を出す | この repo の `wiki/` を adopt し、`export-markdown` no-op diff を確認 | no-op projection が clean、minted id が再実行で揺れない | 森全体 cutover、外部編集 merge |
| 2. Export projection | Markdown を generated view として再生成できる | `grasp export-markdown --project grasp-wiki --output wiki --check`。frontmatter / page file / index/log projection の stable formatting | `export-markdown --check` が clean。1行変更時の diff が局所的 | generated Markdown が既存 lint と git review に耐える | 見た目の完全互換、全 index 自動生成 |
| 3. Minimal write | file-back の普通の追記が grasp 経由になる | `write page`, `append-section`, `append-log`。write は journal append + SQLite update + projection export の順にする | この wiki の軽い file-back を `grasp write` だけで行う | page update + log append + projection diff + commit が一往復で通る | rename, transclude, come-from |
| 4. Status / diff / revert | alpha でも怖くなく使える | `grasp write-status`, `write-diff`, `revert-event <id>`。journal event id と projection diff を結び付ける | 意図的に小さな誤 write を入れ、revert して no-op diff へ戻す | 失敗時に Markdown を手で戻さず回復できる | branching / collaborative merge |
| 5. Rename slice | identity-without-name の差別化を実データで示す | `rename <page-id|handle> <new-title>`。edge は page id を指し、surface `[[旧名]]` は保持。aliases / handles を更新 | 過去の grasp wiki rename 1件を replay し、redirect stub なし・参照文破壊なしを確認 | rename replay が projection diff と graph diff の両方で説明できる | global title rewrite, external Cosense rename |
| 6. File-back integration | Codex の通常運用が切り替わる | file-back skill / repo command を `grasp write` first にする。alpha 中は direct Markdown patch fallback を明示 | この repo の file-back を3回連続で grasp write 経由にする | 手作業 patch より面倒でなく、lint / commit まで閉じる | 全 wiki forest への一括強制 |
| 7. One-wiki cutover | 1つの LLM Wiki が native authority で動く | `wiki.grasp/` を git-tracked authority set とし、`wiki/` は projection 扱いにする運用 docs | 低リスクな wiki 1つで1週間使う | direct Markdown edit が不要になり、問題は backlog ではなく実運用 bug として出る | 全 forest cutover |
| 8. Forest rollout | LLM Wiki 森の infrastructure になる | `adopt-forest`, per-wiki projection, cross-wiki status report | `wikis.yaml` の数 wiki から段階展開 | 毎日の探索・file-back・commit が grasp surface で始まる | native-only publish pipeline |

## Shortest first slice

最初に実装するなら、Phase 0-3 だけでよい。

1. journal schema を固定する。
2. `adopt-markdown` でこの repo の `wiki/` を native store + journal へ取り込む。
3. `export-markdown --check` の no-op projection を通す。
4. `append-section` + `append-log` でこの plan page か別小ページを更新する。

この slice は rename をまだ実装しなくても、日常 file-back dogfood を始められる。ただしこれは **append-only authoring alpha** の fast path であり、identity-without-name の差別化を claim する段階ではない。`2.0.0` 境界は [[write-layer-alpha-and-replay-test]] の通り stable identity + rename replay が通った時点にする。

2026-06-26 status: Phase 0 の前処理として `grasp.journal` に event JSONL schema v1 と event type contract を固定した。続いて `adopt-markdown` と `export-markdown --check` を実装し、repo `wiki/` dogfood で 36 files clean を確認した。Phase 3 の最小 append-only slice として `append-section` / `append-log` を追加し、temp copy の repo `wiki/` で append 後の `export-markdown --check` が 36 files clean になることを確認した。Phase 4 の最小 recovery slice として `write-status` / `write-diff` / `revert-event` / `replay-journal` を追加し、append→status/diff→revert→replay→check clean を確認した。`write-page` full-page replacement と `page_update` replay/revert も追加済み。Phase 5 の最小 rename slice として `rename-page` / `page_rename` replay/revert を追加し、旧 title alias で incoming `[[旧名]]` を書き換えずに解決できることを temp wiki で確認した。rename identity は必要時に `id` / `title` / `aliases` frontmatter として projection し、direct re-import 後も page id と旧名 alias が残ることを確認済み。実 git history の `why-design-B` → `why-not-scrapbox-clone` rename replay test で、redirect stub なし・旧 surface link 書き換えなし・replay/direct re-import clean を確認した。まだ semantic index-log regeneration / 任意 frontmatter merge / general revert は無い。

## Risk register

| Risk | Why it matters | Fast-path mitigation |
|---|---|---|
| journal と SQLite の authority が曖昧 | 壊れた時にどちらを信じるか分からない | Phase 0 で仮決め。alpha では journal replayable を優先し、SQLite は materialized index に寄せる案を検証 |
| generated Markdown diff が大きすぎる | git review 不能になる | 既存 formatting をなるべく保存。no-op export を hard gate |
| direct Markdown edit が混ざる | projection と authority が diverge する | cutover 前は adopt で吸収、cutover 後は `export-markdown --check` で検出し emergency adopt only |
| line identity が揺れる | transclude /引用 / replay test が腐る | Phase 1 で minted id manifest を固定し、content-only re-run で揺れないことを先に確認 |
| write alpha が怖くて使われない | dogfood loop が生えない | status / diff / revert を Phase 4 までに入れる。完璧な write より回復可能性を優先 |

## Success metric

最初の成功条件は機能数ではなく運用の切替:

- 1週間で3回以上、この repo の wiki file-back を `grasp write` 経由で行う。
- その全てで `export-markdown --check` / `scripts/lint_wiki.py` / git commit が通る。
- 失敗や不便が出たら [[grasp-backlog]] ではなく、この plan の phase に紐づけて修正する。
