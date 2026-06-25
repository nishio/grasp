---
type: entity
summary: 2026-06-25 に llm-wiki の `wikis.yaml` 全 entries を対象に Markdown mirror import を temp store で dogfood した結果。37/42 projects は import 成功し、次 blocker は performance ではなく duplicate title / alias collision だと判明した。
sources:
  - /Users/nishio/llm-wiki/wikis.yaml
  - temp store dogfood `/tmp/grasp-forest-import.*`（private 内容は読まず、aggregate / failure type のみ観測）
  - [[markdown-obsidian-indexed-mirror]]
  - [[markdown-identity-name-collision-policy]]
  - [[grasp-backlog]]
---

# wiki森 Markdown import dogfood 2026-06-25

## Result

2026-06-25 に親 llm-wiki の `wikis.yaml` registry 全 entries を対象に、各 `<path>/wiki` を temp SQLite store へ `grasp import --markdown <folder> --project <name> --markdown-exclude-dir raw` で投入した。目的は「wiki森全体を read-only Markdown mirror として 1 store / multi-project namespace に入れられるか」の検証。private wiki 本文は読まず、件数・時間・失敗型だけを観測した。

結果:

- registry entries: 42
- import success: 37
- import failure: 5
- missing folder: 0
- aggregate success store: 37 projects / 2458 pages / 213,309 lines / 22,550 edges / 1,412 unresolved targets
- total import wall time: 約 22.3 秒
- store: schema v5 / schema_ok true

## Analysis

一番重要な発見: **次の blocker は scale / raw size ではなく collision policy**。

`--markdown-exclude-dir raw` は効いた。`llm-wiki-about-nishio` のように raw/source が大きい wiki でも、wiki 本文だけなら import は軽い。37 projects / 213k lines / 22.5k edges を約 22 秒で作れたので、forest dogfood の初期運用は performance では止まっていない。

失敗 5 件はすべて duplicate title / alias collision。類型:

- draft variants が同一 H1 を持つ。
- 複数 directory に `_overview` / `README` / `index` など同一 file stem alias がある。
- source/session file と canonical page が同じ alias を持つ。

現在の Markdown mirror は collision を import error にする。これは単一 wiki の correctness では安全側だが、forest orchestration では 1 project の collision がその project 全体を落とす。全件 import には、collision をまず「観測可能な診断」に変える必要がある。

重要な設計制約: alias collision は単なる import UX ではなく、Scrapbox の name=identity 欠陥を `identity-without-name` で直す問題そのものに近い。path は一意性の根拠として diagnostic / fallback handle には使えるが、path-qualified string をそのまま page name にすると LLM / 人間の期待する `[[Title]]` とずれる。

## Plan

次の実装順:

1. **collision report を structured diagnostic にする。**（2026-06-25 実装）
   `MarkdownMirror.from_folder` の duplicate title / alias / id error を、機械可読な collision kind / normalized handle / paths / candidate title を持つ診断にする。CLI は text では短く、`--json` では full diagnostics を返す。

2. **alias collision policy を identity/name 分離として設計する。**（[[markdown-identity-name-collision-policy]]）
   Page title / alias collision は同一 visible handle が複数 identity に束縛される問題。短期 workaround は path を diagnostic / fallback handle に持つことだが、path-qualified string を page name へ昇格しない。実装は artifact reduction の後、schema v6 の `page_handles` と ambiguous query result へ進める。

3. **draft/source artifact 除外を追加する。**
   `--markdown-exclude-dir raw` と同じ basename 方式で、`drafts/` や `source/` を除外可能にするか、frontmatter / path heuristic で graph_role=`artifact` を導入する。draft variants の同一 H1 は title collision なので、alias 無効化だけでは解けない。

4. **`import-forest` orchestration は急がない。**
   37/42 は手動 loop で成立したので orchestration は価値がある。ただし先に collision policy と artifact 除外を詰めないと、orchestration command は「既知の失敗を集計するだけ」になる。

## Open Questions

- Page title collision の softening をどこまで許すか。同一 title は graph identity 衝突なので、安易に path-qualified title へ自動改名すると `[[Title]]` の期待とずれる。
- alias collision softening を行うなら、どの条件で「意味のあるリンク解決」ではなく「曖昧 handle」として扱うか。path は一意だが、page name に混ぜると retrieval surface が汚れる。
- `drafts/` / `source/` は既定除外にするか、明示 `--markdown-exclude-dir` に留めるか。wiki ごとの意味が違うため、既定除外は過剰かもしれない。
- collision report を store metadata に保存するか、import command の一回限り出力に留めるか。forest dashboard / import-forest を作るなら保存した方がよい。

## Related

- [[markdown-obsidian-indexed-mirror]]
- [[markdown-identity-name-collision-policy]]
- [[grasp-backlog]]
- [[whole-store-graph-and-cross-project-edges]]
