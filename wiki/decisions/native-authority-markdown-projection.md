---
type: decision
summary: LLM Wiki を Markdown の束から grasp infrastructure へ移行する目標形。grasp native store（＋ durable journal）を authority にし、Markdown は review / backup / publish / interoperability 用の generated projection として出し続ける。cutover 後、人間や Codex は Markdown を直接編集せず `grasp write` が native store を更新し、`grasp export-markdown` が Markdown projection を再生成する。
sources:
  - nishio 合意 2026-06-26「当面は Markdown を出力し続ける。ただし人間や Codex が直接 Markdown を編集するのではなく、grasp write が native store を更新し、そこから Markdown を再生成する」に同感
  - [[persistence-custom-format]]
  - [[write-layer-alpha-and-replay-test]]
  - [[markdown-obsidian-indexed-mirror]]
---

# Decision: native authority + Markdown projection で LLM Wiki を移行する

決定: LLM Wiki を grasp infrastructure へ移行する時の目標形は、**grasp native store（＋ durable journal）を authority にし、Markdown は generated projection として出し続ける**こと。

これは「Markdown import を便利にする」ではない。authority を Markdown files から grasp native layer へ反転する話。cutover 後、人間や Codex は Markdown を直接 patch しない。`grasp write` が native store を更新し、そこから Markdown projection を再生成する。

## 決定内容

- **native store / journal が source of truth**。page / line / edge / handle / identity / event は native layer にある。
- **Markdown は projection**。git review、backup、publish、人間のざっとした閲覧、既存 LLM Wiki workflow との互換のために出力し続けるが、authoritative edit target ではない。
- **write path は `grasp write` 経由**。page create/update、append section、rename、log event append などは native store を更新し、edge / backlinks / aliases / log projection を派生させる。
- **direct Markdown edit は cutover 前の source import か emergency path**。通常 workflow では「Markdown を直接直す → import」ではなく「native を直す → Markdown を export」へ寄せる。
- **journal は reviewable であるべき**。SQLite だけを authority にすると git diff / review / rollback の LLM Wiki らしさが落ちる。正確な形は Open Question だが、append-only event journal（例: `wiki.grasp/events.jsonl`）を git-tracked にし、`wiki/` は generated projection にする案が有力。

## なぜ

[[persistence-custom-format]] は「native 保存形式は Markdown ではない」と決めた。Markdown はリンクをテキストに埋め込み、逆リンク維持や rename 追従を手作業にする発生源だから。

一方、LLM Wiki の運用価値には Markdown の効用もある: git diff で見える、commit できる、publish / review しやすい、既存 toolchain が読める。したがって Markdown を捨てるのではなく、**authority から projection へ降ろす**。

これにより、grasp の差別化核である identity-without-name が authoring 側でも成立する。surface text の `[[旧名]]` は残せるが、edge は stable page id を指せる。rename は参照文を書き換えず、redirect stub も溜めない。

## 移行フェーズ

1. **adopt phase**: 既存 Markdown wiki を import し、frontmatter `id` があれば採用、無ければ page id / line id を mint する。この段階では Markdown がまだ authority。
2. **identity journal phase**: re-import diff で page id / line id を維持できるかを replay test で測る。外部 Markdown edit からの adoption policy もここで決める。
3. **native write alpha phase**: `grasp write` / `rename` が native store を更新し、event journal に記録する。ここから authority を native 側へ移し始める。
4. **projection phase**: `grasp export-markdown` が `wiki/` を生成する。`index.md` は catalog projection、`log.md` は event stream projection、人間向け Markdown は派生 view。
5. **dogfood phase**: file-back / Codex workflow が Markdown patch ではなく `grasp write` → export Markdown → lint → commit を使う。

## 最初の write slice

LLM Wiki の file-back dogfood に必要な面から始める:

- page create / update
- append section
- append log event
- rename page
- export Markdown projection
- status / diff / rollback or revert event

巨大な editor は不要。まず「普段の wiki 作業」が grasp 経由で閉じることを優先する。

実行順の詳細は [[llm-wiki-infra-fast-path-plan]]。この decision は目標形、本 plan は最速 dogfood の phase table と done 条件を持つ。

## Open Questions

- durable journal の正確な authority は何か。SQLite が primary で journal が audit log なのか、journal が replayable source of truth で SQLite が materialized index なのか。
- `wiki.grasp/events.jsonl` のような git-tracked journal を採る場合、SQLite store と projection をどこまで commit 対象にするか。
- cutover 後に人間が Markdown projection を直接編集した場合、reject / adopt / merge のどれにするか。
- generated Markdown の header / formatting / line wrapping をどこまで stable にし、git diff を読みやすく保つか。
- file-back skill をいつ `grasp write` first に切り替えるか。alpha 中は Markdown direct patch fallback を残すか。
