---
type: entity
summary: nishio Cosense の `KJ法` が 100+ backlink hub になり、リンク化を避けた裸の言及も大量にあることを grasp で実測した記録。exact link だけを読むと 144 pages だが、literal mention は 681 pages、本文の裸言及は 490 pages。対応は「全部リンク化」ではなく、root link・subtopic link・co-link slice・AI cluster handoff に分け、`KJ法` を巨大入口から分岐点に変える。
sources:
  - `~/.grasp/grasp.sqlite` project `nishio`, schema v5, synced 2026-06-24
  - session query 2026-06-24: "KJ法" link hub audit
  - grasp CLI: `stats`, `sync`, `link-stats`, `backlinks`, `related`
  - SQLite scan of `lines` / `edges` with `parse_cosense_links`
---

# KJ法 link hub audit 2026-06-24

## Context

User concern: `KJ法` has too many Cosense backlinks, so some occurrences are intentionally written as bare `KJ法` instead of `[KJ法]`. The question was whether the link is too broad, and whether splitting / co-link filtering / AI clustering can improve the situation.

Store state after `grasp sync https://scrapbox.io/nishio/ --limit 100`: project `nishio`, 25,792 pages / 724,988 lines / 125,409 edges / 42,770 unresolved targets. Recent hosted delta was one page (`タブUI`); it did not change the `KJ法` counts.

## Counts

`grasp link-stats 'KJ法'`:

| metric | value |
|---|---:|
| exact links to `[KJ法]` | 151 |
| exact source pages | 144 |

Literal scan for the string `KJ法`:

| classification | pages | lines | occurrences |
|---|---:|---:|---:|
| any literal `KJ法` | 681 | 2,333 | 2,765 |
| exact link occurrence `[KJ法]` | 144 | 151 | 151 |
| other link target containing `KJ法` | 228 | 361 | 368 |
| bare `KJ法` outside internal-link spans | 519 | 1,866 | 2,246 |
| bare `KJ法` in body lines only | 490 | 1,777 | 2,156 |

Derived page sets:

| set | pages |
|---|---:|
| body has bare `KJ法` but page has no exact `[KJ法]` link | 415 |
| body has bare `KJ法` and page has exact `[KJ法]` somewhere | 75 |
| body has bare `KJ法` but page has no `KJ法`-containing link target at all | 339 |

Interpretation: the graph sees `KJ法` as a 144-page hub, while lexical usage spans 681 pages. If every body bare mention were converted to `[KJ法]`, backlinks could jump from 144 pages toward ~559 pages (exact current source pages plus pages with bare body mentions but no exact link). This is the wrong direction.

## Top bare mention pages

Top pages by body bare `KJ法` occurrences:

| occurrences | lines | exact `[KJ法]` in page | page |
|---:|---:|---|---|
| 266 | 136 | yes | `🌀KJ法` |
| 110 | 85 | yes | `KJ法勉強会@サイボウズ` |
| 78 | 62 | no | `KJ法勉強会@ロフトワーク_講義資料v2` |
| 77 | 59 | no | `KJ法勉強会@ロフトワーク_講義資料v1` |
| 56 | 52 | no | `「渾沌をして語らしめる」勉強会` |
| 53 | 48 | no | `探検ネット(花火)勉強会` |
| 48 | 41 | no | `KJ法勉強会振り返り勉強会` |
| 36 | 26 | no | `🤖Kozaneba` |

Top pages with body bare mentions and no `KJ法`-containing link target at all:

| occurrences | lines | page |
|---:|---:|---|
| 36 | 26 | `🤖Kozaneba` |
| 26 | 19 | `時間軸逆順の整理` |
| 22 | 18 | `ChatGPTと毛玉のときほぐしの議論` |
| 21 | 17 | `LENCHI_Day6` |
| 16 | 16 | `🌀違和感駆動の知的生産` |

## Co-link slices

Same-line co-links on `KJ法` literal lines provide natural slice handles:

| co-link | lines | pages |
|---|---:|---:|
| `考える花火` | 15 | 13 |
| `こざね法` | 11 | 9 |
| `グループ編成` | 9 | 8 |
| `探検ネット` | 8 | 8 |
| `付箋` | 8 | 8 |
| `川喜田 二郎` | 7 | 7 |
| `発想法` | 6 | 6 |
| `表札` / `表札づくり` / `表札作り` | 10 | roughly 10 |

Operationally, `KJ法 + 表札`, `KJ法 + Kozaneba`, `KJ法 + 考える花火`, `KJ法 + 川喜田`, `KJ法 + AI` are better retrieval surfaces than expanding `[KJ法]`.

## AI cluster handoff

Manual clustering from title/text/co-link evidence:

| cluster | examples |
|---|---|
| KJ法本体・原理 | `狭義のKJ法`, `表札づくり`, `グループ編成`, `分類してはいけない`, `川喜田二郎`, `W型問題解決モデル` |
| 勉強会・講義資料 | `KJ法勉強会@ロフトワーク`, `KJ法勉強会@サイボウズ`, `講義資料v1/v2`, `質疑`, `Zoomコメント` |
| 派生実践 | `考える花火`, `探検ネット`, `こざね法`, `花火日報` |
| ツール化 | `Kozaneba`, `電子的KJ法ツール`, `Miro`, `Notability`, `Excel型KJ法` |
| AI・LLM応用 | `AIにKJ法を教える`, `AIでKJ法2024-12-19`, `ブロードリスニング`, `Talk to the City` |
| 比較・隣接手法 | `マインドマップ`, `GTD`, `NM法`, `U理論`, `ブレインストーミング` |
| 執筆・知的生産 | `エンジニアの知的生産術`, `知的生産術`, `執筆`, `反響まとめ` |

This supports the existing decision that CLI-side `--cluster` is not the first move. The durable primitive should be: expose counts, ranked backlink lines, co-link slices, and enough source rows for AI to cluster per question.

## Desired state

The better state is not "more `[KJ法]` links". It is a graph where `KJ法` acts as a root / representative link and routine mentions route through narrower handles.

Target link semantics:

| link | role |
|---|---|
| `[KJ法]` | KJ法そのもの、川喜田二郎、原理、全体像 |
| `[表札づくり]` | labels / name-making in KJ practice |
| `[グループ編成]` | grouping cards / notes |
| `[考える花火]` | divergent thinking / workshop practice |
| `[Kozaneba]` | tool / implementation context |
| `[探検ネット]` / `[こざね法]` | adjacent practice / derived method |
| `[AIにKJ法を教える]` | LLM / AI application context |

Preferred writing pattern:

| avoid | prefer |
|---|---|
| `[KJ法]` で整理する | KJ法で `[表札づくり]` をする |
| `[KJ法]` を使ったツール | KJ法を使った `[Kozaneba]` |
| `[KJ法]` 的にグルーピングする | KJ法的に `[グループ編成]` する |

Here `KJ法` may remain as bare text in the sentence. The link should mark the retrieval handle the reader will want later, not every occurrence of the word.

Tool-level success criterion:

- `gather KJ法` detects a huge hub and reports both graph and lexical surfaces: exact links, body bare mentions, pages with bare mention but no exact link, pages with no `KJ法`-related link, top co-link slices, representative samples, and omitted counts.
- `co-links KJ法` ranks same-line slice handles (`考える花火`, `こざね法`, `グループ編成`, `探検ネット`, `表札*`, etc.).
- `mentions KJ法 --unlinked` returns bare mention lines with enough page/link context to decide whether to add a narrower link.
- AI clustering consumes this raw material and proposes 5-10 use clusters, but the durable page/link names remain human-reviewed.

The practical success condition is: opening `[KJ法]` backlinks should no longer require reading the whole hub. The first view should expose a handful of use clusters and let the agent read only the relevant slice.

## Implications

- `KJ法` is a counterexample to the earlier "100+ link hubs are rare case" dismissal. It is rare but load-bearing enough to deserve first-class retrieval handling.
- Do not bulk-convert bare `KJ法` to `[KJ法]`. That would amplify the hub and dilute attention.
- Keep `[KJ法]` as root concept / representative link. Use more specific links for routine mentions: `表札づくり`, `グループ編成`, `考える花火`, `Kozaneba`, `探検ネット`, `こざね法`, etc.
- Add tool support for **link gap / bare mention audit**: "literal mentions of X outside parsed link spans, grouped by page and whether the page already has an exact link".
- Add tool support for **co-link slices**: top links co-occurring on lines containing a query / target, and search recipes for those slices.
- `gather "<query>" --budget` should treat huge hubs as a budgeted sampling problem: top ranked lines, representative co-link slices, omitted counts, and explicit "remaining N pages omitted".

## Open Questions

- Should `grasp` expose `mentions <query>` as a separate verb, or fold this into `search --mentions --link-gap`?
- Should co-link slice counts be computed from same-line only, same-page, or windowed context?
- What is the right output contract for AI clustering: raw rows only, or a compact "candidate clusters" section explicitly labeled as heuristic?
