---
type: entity
summary: 2026-06-25 に llm-wiki の `wikis.yaml` 全 entries を対象に Markdown mirror import を temp store で dogfood した結果。初回は 37/42 projects 成功で blocker は duplicate title / alias collision だった。schema v7 の edge resolution と import softening 後は 42/42 projects が import 成功し、`1.7.3` で `import-forest` command 化した。
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

2026-06-25 16:42 に schema v6 実装後の smoke として同じ registry / `--markdown-exclude-dir raw` 条件を temp store で再実行した。結果は 42 entries 中 37 success / 5 failure / missing 0 で、失敗型はすべて `markdown_collision` のまま。成功 aggregate は schema v6 / schema_ok true / 37 projects / 2460 pages / 213,526 lines / 22,569 edges / 1,412 unresolved、wall time 約 25.8 秒。v6 `page_handles` 追加は成功 project の import を壊していないが、collision 5件は import softening 未実装のため残る。

2026-06-25 19:07 に schema v7 実装後の smoke として同じ条件を再実行した。結果は 42 entries 中 42 success / 0 failure / missing 0。aggregate は schema v7 / schema_ok true / 42 projects / 3338 pages / 264,963 lines / 23,180 edges / 1,627 unresolved、wall time 約 22.1 秒。duplicate title / alias collision は import 全体を止めなくなった。ambiguous handle edge は `resolution_status=ambiguous` として unresolved から分離される。

2026-06-25 に `1.7.3` の `import-forest` command として同じ registry を直接実行した。結果は 42 entries 中 42 success / 0 failure / 0 missing / 0 skipped。aggregate は 42 projects / 3338 pages / 265,012 lines / 23,183 edges / 1,627 unresolved、wall time 6.025 秒、ambiguous handles は 8。command output は per-entry diagnostics と post-import `ambiguities` summary を返すため、手動 shell loop は不要になった。

## Analysis

初回 dogfood の一番重要な発見: **scale / raw size より先に collision policy が blocker になる**。

`--markdown-exclude-dir raw` は効いた。`llm-wiki-about-nishio` のように raw が大きい wiki でも、wiki 本文だけなら import は軽い。37 projects / 213k lines / 22.5k edges を約 22 秒で作れたので、forest dogfood の初期運用は performance では止まっていない。

`source/` は `raw/` と同列に扱わない。LLM Wiki の `source/` は raw を読んで作った digest / source-backed synthesis であり、回答根拠になりうる。したがって default exclude ではなく、必要なら `graph_role=source` / evidence layer / ranking policy で扱いを分ける対象。

失敗 5 件はすべて duplicate title / alias collision。類型:

- draft variants が同一 H1 を持つ。
- 複数 directory に `_overview` / `README` / `index` など同一 file stem alias がある。
- source digest / session file と canonical page が同じ alias を持つ。

schema v7 では duplicate title / alias collision は import error ではなくなった。単一 wiki の correctness は `read <handle>` の ambiguity と `read --page-id` / `read --path` の identity selection に寄せる。2026-06-25 の `1.7.1` で `backlinks <ambiguous handle>` は handle 自体への incoming lines と候補 page ごとの resolved backlinks を分けて返すようになり、`1.7.2` で `ambiguities` が store / project 内の ambiguous handles を一覧できるようになった。`1.7.3` で `wikis.yaml` からの一括 import command 化も済み、`1.7.4` で `related <ambiguous handle>` も handle source pages と候補 page related を分けて返すようになった。`1.7.5` で `cross-project-spread <title>` が normalized title の weak spread report を返すようになった。残る retrieval blocker は first-class cross-project edge と whole-store default retrieval。

重要な設計制約: alias collision は単なる import UX ではなく、Scrapbox の name=identity 欠陥を `identity-without-name` で直す問題そのものに近い。path は一意性の根拠として diagnostic / fallback handle には使えるが、path-qualified string をそのまま page name にすると LLM / 人間の期待する `[[Title]]` とずれる。

## Plan

次の実装順:

1. **collision report を structured diagnostic にする。**（2026-06-25 実装）
   `MarkdownMirror.from_folder` の duplicate title / alias / id error を、機械可読な collision kind / normalized handle / paths / candidate title を持つ診断にする。CLI は text では短く、`--json` では full diagnostics を返す。

2. **alias collision policy を identity/name 分離として設計する。**（[[markdown-identity-name-collision-policy]]）
   Page title / alias collision は同一 visible handle が複数 identity に束縛される問題。path-qualified string を page name へ昇格しない。schema v6 の `page_handles` と `read` の ambiguous query result / `--page-id` / `--path`、schema v7 の edge `resolution_status` と Markdown duplicate title / alias import softening、`backlinks <ambiguous handle>` / `related <ambiguous handle>` の handle/candidate 分離、`ambiguities` report は実装済み。

3. **artifact reduction と source role classification を分ける。**（2026-06-25 最小実装）
   `raw/` は heavy original dump なので `--markdown-exclude-dir raw` で除外可能。`source/` は raw digest / source-backed synthesis なので default exclude せず、`graph_role=source` として保持し content と同じく edge を materialize する。`drafts/` / generated temp は `graph_role=artifact` として search には残すが outgoing edges は除外する。duplicate title / alias は schema v7 の handle ambiguity として別管理する。

4. **`import-forest` orchestration と weak spread report は実装済み。**
   `1.7.3` で registry parse / per-entry diagnostics / aggregate / forest-level ambiguity summary を持つ command になった。`1.7.4` で ambiguous related、`1.7.5` で `cross-project-spread` が入ったため、次は first-class cross-project edge / whole-store retrieval。

## Open Questions

- `import-forest` の結果を store metadata に保存するか、一回限りの command output に留めるか。
- `artifact` role 由来の ambiguity を forest report / ranking でどう弱めるか。
- `source/` digest を content graph にどこまで混ぜるか。保持はするが、canonical synthesis と同列に ranking すると重複根拠が増える可能性がある。

## Related

- [[markdown-obsidian-indexed-mirror]]
- [[markdown-identity-name-collision-policy]]
- [[grasp-backlog]]
- [[whole-store-graph-and-cross-project-edges]]
