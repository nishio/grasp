---
type: concept
summary: 脆弱性スキャナー結果を current risk として直輸入せず、scanner observation / Claude Code transcript / 人間議論 / 批判 / judgment を disagreement graph として構造化する設計仮説。Grasp は scanner engine ではなく、意見が分かれる理由と判断の前提を次回 triage で再利用する reasoning layer になりうる。
sources:
  - nishio conversation 2026-06-29: vulnerability scanner direction / transcript / human discussion IDs / private-project handoff
  - [[hn-reddit-grasp-adjacent-survey-2026-06-29]]
  - [[use-case-experiment-as-outcome-story]]
  - [[ai-consumer-cost-and-trust]]
  - [[positioning-two-personas]]
---

# concept: security triage disagreement graph

脆弱性スキャナー方向での Grasp の役割は、新しい scanner engine ではない。scanner が出した finding、Claude Code の過去 transcript、人間同士の ID 付き議論、最終判断を、次回以降の triage で再利用できる **reasoning layer / project memory** として扱うこと。

成功形は「47件の検出を要約する」ではなく、同じ finding が再出現した時に **なぜ前回は批判され、どの前提でどう判断し、何が変わると再評価が必要か** を bounded に読める状態。

## Core distinction

scanner と批判の意見が分かれる時、多くは単純な true/false の衝突ではなく、見ている命題が違う。

例:

- scanner position: vulnerable package version is present.
- critique position: this service is not reachable through the vulnerable path in production.

両者は両立しうる。したがって `finding` を中心に current fact 化するより、`dispute` を中心にして disagreement axis を明示する方がよい。

典型的な disagreement axis:

- presence vs reachability
- repository contents vs production behavior
- vulnerable version range vs local mitigation
- dev/test dependency vs runtime dependency
- code path exists vs external input can reach it
- image/package contains component vs deployed service executes it
- advisory severity vs project-specific exploitability
- security fix desirability vs breaking-change / operational cost

## Knowledge layers

raw material は混ぜずに段階化する。

1. **Raw sources**: scanner report、Claude Code transcript / thinking、Slack / issue / PR / meeting notes などの人間議論。source hash、repo、commit、scan target、discussion/message ID を持つ不変一次資料として残す。
2. **Observations**: scanner が観測したこと。scan run、scanner version、input commit / image digest / lockfile hash、matched package/version、advisory ID、raw payload への link。これは current risk ではなく event。
3. **Claims / positions**: transcript や人間発言から抽出した命題。「dev-only らしい」「production で無効」「owner は到達可能性を疑っている」など。thinking 由来は最初 `tentative` とし、confirmed judgment に昇格するには evidence link が必要。
4. **Disputes**: scanner position と critique position を同じ question の下に並べ、どの axis で食い違うかを記録する。
5. **Judgments**: 組織として使う現在の結論。`affected` / `not_affected` / `false_positive` / `accepted_risk` / `mitigated_by_config` / `fixed` / `deferred` など。必ず evidence、assumptions、expiry、invalidation condition を持つ。
6. **Current risk view**: latest observations + non-expired judgments + assumptions + invalidation checks を fold した読み取り面。raw transcript や古い log を current fact として直接読ませない。

## Source handling rules

- scanner finding は **observation**。現在のリスク判断そのものではない。
- Claude Code transcript / thinking は **evidence discovery trail**。そこから有用な仮説や却下経路を抽出できるが、thinking だけを根拠に current fact へ昇格しない。
- 人間同士の議論は **positions / assumptions / organizational decision context**。発言者 ID は authority そのものではなく provenance / role / decision source として使う。
- judgment は **条件付き判断**。期限、前提、無効化条件なしの `false positive` / `accepted risk` は将来の誤読を生む。
- rejected path も残す。同じ疑義が再発した時に「前回なぜ退けたか」を読むため。

## Graph sketch

主要 node:

- `Vulnerability`: CVE / GHSA / OSV advisory。alias を持つ。
- `Component`: package / OS package / container image component。purl や ecosystem/name/version range を持つ。
- `Asset`: repo / service / deploy target / image / environment。
- `CodeSurface`: file / module / endpoint / job / dependency path。
- `ScanRun`: scanner execution event。
- `Observation`: scan finding instance。
- `Discussion` / `Message`: human thread/message with stable ID。
- `Claim` / `Position`: extracted proposition and stance.
- `Dispute`: one security question where scanner and critique diverge.
- `Judgment`: adopted conclusion with evidence and invalidation.
- `Assumption`: production config, exposure, deployment, dependency-path premise.
- `Remediation`: PR / commit / ticket / rollout.

Useful edges:

```text
Vulnerability --affects--> Component
Observation --observed_in--> ScanRun
Observation --matched--> Component
Component --included_in--> Asset
CodeSurface --uses--> Component
Asset --owned_by--> Owner
Asset --exposes--> Endpoint
Claim --stated_in--> Message
Position --supports|critiques--> Dispute
Judgment --judges--> Dispute
Judgment --supported_by--> Observation / Message / CodeSurface / ScanRun
Judgment --depends_on--> Assumption
Judgment --supersedes--> older Judgment
Remediation --fixes--> Vulnerability on Asset
Remediation --landed_in--> PR / commit
```

## Why Grasp instead of plain Markdown LLM Wiki

Markdown LLM Wiki だけでも、CVE page、scan-run page、judgment page は書ける。ただし、それは運用規約として「そう書く」だけになりやすい。

Grasp 側の差分候補:

- ID の安定化: CVE / GHSA / OSV / package URL / discussion message ID / service identity を alias ではなく同一対象として扱える。
- event/current 分離: scanner observation、transcript claim、human discussion、current judgment を同じ prose に混ぜず、読む時に fold できる。
- bounded graph read: `read CVE-X` や `related service-api` で、scanner側・批判側・過去判断・期限切れ・未解決論点を限られた出力で拾える。
- stale 判定: commit、image digest、dependency path、production config、exposure、advisory range、owner judgment が変わった時に、過去の judgment を current fact として再利用しない。
- disagreement reuse: 「前回 false positive」ではなく、「presence vs reachability で分かれ、production import disabled という前提で not exploitable と判断した」を再取得できる。

したがって pitch は "better scanner" でも "better grep" でもない。

> Not another vulnerability scanner. A local context layer that helps agents triage scanner findings without forgetting prior security decisions.

## Handoff to private project

この grasp wiki 側の知識は公開前提なので、非公開の scanner report / Claude Code transcript / human discussion ID をここへ持ち込まない。公開側が渡せるのは **構造の仮説** まで。

非公開側に最初に伝えるべきこと:

- これは scanner 本体ではなく、scanner finding・Claude Code transcript・人間議論・最終判断を再利用する triage reasoning layer の設計相談。
- 公開側の仮説は、observation / evidence discovery trail / position / dispute / judgment / invalidation condition を分けること。
- 実際の ontology、page structure、ingest policy は、非公開の実データで壊して決めるべき。

非公開側で見るべき実データ:

- 過去 scanner report と、同じ CVE / package が繰り返し出た例。
- false positive / accepted risk / deferred / fixed の実例。
- Claude Code の scan/triage transcript と、途中仮説が最終判断へ昇格した例・却下された例。
- Slack / issue / PR comment / meeting note の thread ID / message ID。
- waiver が期限切れ・前提変更・再議論になった例。
- service / repo / package / owner / deploy environment の対応表。

非公開側への設計問い:

- どの単位を stable identity にするか。
- finding と judgment をどう分けるか。
- disagreement axis は実データ上で何種類あるか。
- Claude thinking を tentative claim として残すか、discovery trail に留めるか。
- 人間の発言者 ID / role / owner status を judgment provenance にどう反映するか。
- current risk view を何から fold するか。
- 何が変わったら再評価を必須にするか。

## Related

- [[use-case-experiment-as-outcome-story]]: raw dump で終わらず、ユーザが判断に使える outcome story にする基準。
- [[ai-consumer-cost-and-trust]]: token-bounded AI が読む時の bounded retrieval / absence handling の設計軸。
- [[positioning-two-personas]]: 外向き persona と on-ramp を曲げずに、use-case / demo を選ぶ判断。
- [[hn-reddit-grasp-adjacent-survey-2026-06-29]]: generic "Obsidian + AI" 誤読を避け、concrete value demo が必要という外部 survey。

## Open Questions

- Grasp 本体に scanner-report importer を持つべきか、まずは Markdown/frontmatter convention + `import --markdown` で実験するべきか。
- `dispute` / `judgment` / `assumption` は typed link として持つべきか、page type + frontmatter + wikilink で足りるか。
- Claude Code transcript の thinking をどの粒度で保存し、どの権限境界で読ませるか。
- current risk view は CLI command として fold するか、agent layer の report composition に任せるか。
- 非公開 corpus で得た ontology 改善を、秘密を漏らさず公開側 grasp wiki へどう file back するか。
