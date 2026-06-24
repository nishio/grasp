---
type: entity
summary: `/nishio` で `[/` を探すと、他 Cosense project への参照を bibliography として発見し、読める semantic slice を acquire して周辺知識圏の map を作れる、という use-case 実験。other-project 参照は 4,141 mentions / 183 projects、semantic refs は 2,222 mentions / 142 projects。semantic 上位 12 project から最大 20 page ずつ seed 取得し、8 project / 140 pages を local store に取り込めた。主要クラスタは AI/Cosense/Plurality/熟議/未踏人物/共同知的生産。
sources:
  - `/Users/nishio/grasp/raw/nishio.json`
  - `/tmp/grasp-cross-project.sqlite` task-local store, 2026-06-24
  - `grasp acquire` via `@helpfeel/cosense-cli` v1.4.4, 2026-06-24
  - session query 2026-06-24: `/nishio` から `[/` で他 Cosense project 参照を取得して分析
---

# cross-project reference acquire 2026-06-24

## Outcome Story

User action:

> `/nishio` から `[/` で検索して、他の Cosense project への参照を発見し、それらを取得して分析する。

Nice outcome:

- `/nishio` 内に散らばった `[/project/page]` links が、他 project を読むための seed bibliography として使える。
- `.icon` や project-root refs を除いた semantic refs を ranking すると、どの project が知識圏として近いか分かる。
- 読める referenced pages を partial acquire すると、AI/Cosense/Plurality/熟議/未踏人物/共同知的生産という周辺 map が得られる。
- 取得した外部 page には `/nishio` への reciprocal refs もあり、単なる outbound link 集ではなく、共同知識圏の輪郭として読める。

Actual outcome: 183 referenced projects were discovered; 142 had semantic refs; semantic top projects were acquired as bounded slices; 8 projects / 140 pages were usable enough for theme analysis.

Quality judgement: this is close to a good [[use-case-experiment-as-outcome-story]]. The outcome is useful and explainable, but the path still required one-off extraction scripts and a `cosense` PATH wrapper. The product gap is to turn this into a first-class cross-project discovery/acquire/report workflow.

## Context

User experiment: start from `/nishio`, search `[/`, discover references to other Cosense projects, acquire those projects, and analyze the resulting slice.

This was run as a task-local experiment, not as a durable default store mutation:

- source: `/Users/nishio/grasp/raw/nishio.json`
- store: `/tmp/grasp-cross-project.sqlite`
- initial import: `grasp --store /tmp/grasp-cross-project.sqlite import --cosense raw/nishio.json`
- acquisition namespace pattern: `<remote-project>:semantic`

Partial corpus caveat from [[grasp-v1-implemented]] applies: `backlinks` / `related` / `unresolved` inside acquired namespaces describe only the acquired subset, not the hosted project as a whole.

## Discovery Counts

Extraction target was Cosense cross-project shorthand in bracket links, e.g. `[/project/page]`.

| metric | count |
|---|---:|
| all slash refs, including `/nishio` self refs | 5,983 |
| `/nishio` self refs | 1,842 |
| other-project refs | 4,141 |
| other projects | 183 |
| semantic refs (`.icon` and project-root refs excluded) | 2,222 |
| icon refs | 1,713 |
| project-root refs | 206 |
| projects with semantic refs | 142 |

Important dogfood finding: raw `[/` is dominated by `.icon` author/community decoration in some projects, especially `villagepump`. For analysis or seed acquisition, split refs into at least:

- semantic page refs: `[/project/page]` where page is not `.icon`
- icon refs: `[/project/name.icon]`
- project root refs: `[/project]`

Treating all three as the same signal makes `villagepump` look even more dominant than it already is and selects low-value seed pages.

2026-06-24 follow-up from process observation: at dogfood time, `grasp search` could not do this classification by itself. `search "[/"` is line text retrieval, and `search "[/ AND NOT .icon" --mode boolean --scope line` only excludes lines that contain the literal string `.icon`. That loses lines that contain both a semantic cross-project link and an icon mention, keeps root refs, and never classifies each parsed link target. The right primitive is target-aware extraction over parsed links, not more boolean text search.

2026-06-24 implementation follow-up: `grasp cross-project-refs` now provides that target-aware extraction. It scans stored line text for Cosense shorthand `[/project/page]`, classifies targets as `semantic` / `icon` / `project-root` / `self-project`, ranks target projects, and supports `--semantic-only` for seed bibliography review. `--seed-dir` writes per-project seed files and returns runnable `acquire --seed-file` commands. `grasp cross-project-acquire` is the executing counterpart: it takes those semantic seed titles, acquires multiple target projects into `<project>:semantic` namespaces, and returns bounded per-project summaries including reciprocal refs to the source project and top internal links inside the acquired slice.

2026-06-24 diagnostics follow-up: `acquire` fetch failures now include compact `failed_pages[].error_class`, and all-candidate fetch failure returns `diagnostic.type=all_failed` with `next_actions`. The observed `cosense` symlink / missing `node` case is classified as `command-env`. This reduces the risk that an agent treats an empty partial corpus as a useful acquisition result.

## Top Semantic Projects

Top projects after excluding `.icon` and root-only refs:

| project | semantic mentions | unique targets | source pages |
|---|---:|---:|---:|
| `villagepump` | 833 | 643 | 578 |
| `plurality-japanese` | 185 | 97 | 117 |
| `omoikane` | 135 | 89 | 78 |
| `tkgshn` | 128 | 107 | 86 |
| `shokai` | 111 | 69 | 58 |
| `blu3mo-public` | 77 | 70 | 65 |
| `mitou-meikan` | 54 | 43 | 41 |
| `unnamedcamp` | 54 | 34 | 35 |
| `rashitamemo` | 45 | 35 | 25 |
| `shiology` | 38 | 31 | 23 |
| `intellitech-en` | 33 | 31 | 21 |
| `takker` | 30 | 21 | 23 |

## Acquisition Result

Acquisition used the top 12 semantic projects and up to 20 referenced pages per project. Pages were selected by reference count, then max source page views.

| project | fetched / seeds | notes |
|---|---:|---|
| `villagepump` | 18 / 20 | AI x Scrapbox / ChatGPT connector / context-oriented communication |
| `plurality-japanese` | 17 / 20 | Plurality translation/community docs |
| `omoikane` | 18 / 20 | Omoikane Embed, AI/SF/community workshop |
| `tkgshn` | 20 / 20 | Plurality, Talk to the City, QV, governance/economics |
| `shokai` | 19 / 20 | Cosense/Scrapbox design philosophy and product mechanics |
| `blu3mo-public` | 19 / 20 | AI-mediated communication, Keicho, Scrapbox operation |
| `mitou-meikan` | 20 / 20 | people/entity directory around MITOU |
| `unnamedcamp` | 9 / 20 | atomic notes, discussion process, knowledge work |
| `rashitamemo` | 0 / 20 | `readPage` exit 1 for selected seeds |
| `shiology` | 0 / 20 | `readPage` exit 1 for selected seeds |
| `intellitech-en` | 0 / 20 | likely inaccessible or moved; all selected seeds failed |
| `takker` | 0 / 20 | all selected seeds failed; note selected targets include slash-like titles such as `takker99/ScrapBubble` |

Total acquired pages in semantic namespaces: 140.

## Theme Clusters

Observed clusters from acquired page titles, source context in `/nishio`, and top internal link targets:

| cluster | projects | reading |
|---|---|---|
| AI connected to personal wiki | `villagepump`, `omoikane`, `blu3mo-public` | `/nishio` points outward to experiments where Scrapbox/Cosense becomes an LLM substrate: ChatGPT connector, Omoikane Embed, Keicho, vector search, and AI-mediated conversation. |
| Plurality / digital democracy / deliberation | `plurality-japanese`, `tkgshn`, `blu3mo-public`, `omoikane` | Cross-project refs bind Plurality translation, Talk to the City, Polis/QV, Social Hack Day, and AI-mediated deliberation. |
| Cosense design philosophy | `shokai`, `villagepump`, `rashitamemo` source refs | These refs are not just tool docs; they provide design principles: telomere, 2-hop link, "do not make dead text warehouse", context-oriented communication. |
| Community memory / public project operation | `villagepump`, `unnamedcamp`, `blu3mo-public` | The refs are often about how shared projects behave: cutting pages out of conversation, atomicity, private/limited public operation, and how comments migrate across projects. |
| People/entity lookup | `mitou-meikan` | This project acts differently from conceptual projects: it is mainly an entity dictionary for people and projects cited from `/nishio`. |

## Reciprocal References

Acquired pages often point back to `/nishio`, so the cross-project graph is not just outbound citation:

- `villagepump:semantic`: `Scrapbox ChatGPT Connector` links back to `/nishio`, `/nishio/AIパネルディスカッション`, `/nishio/Scrapboxのtoken/page`, and `/nishio/自分のScrapboxをChatGPTにつないだ`.
- `plurality-japanese:semantic`: `日本におけるPluralityの歴史` links back to `/nishio/真鶴2023-05-13`, `/nishio/Plurality Tokyo Salon 2023-07-08`, `/nishio/なめ敵会`, etc.
- `omoikane:semantic`: `雑談ページ5` links back to `/nishio/AIとの共同化`, `/nishio/主観か客観かではなく、一人の主観から大勢の主観へ`, `/nishio/AIと人間の知的な共同作業`.
- `blu3mo-public:semantic`: `Keicho` links back to `/nishio/聞き出しチャットシステム`; `Scrapbox限定公開運用` links back to `/nishio/Scrapboxで他人のプロジェクトに参加する`.

This supports the [[multi-project-store]] decision: merging project graphs into one namespace would blur authorship and coverage, but keeping namespaces separate still allows an agent to observe cross-project neighborhoods by explicit acquisition.

## Operational Gotchas

- `cosense` existed at `/Users/nishio/.nvm/versions/node/v24.16.0/bin/cosense`, but the shell PATH used by this task did not include the matching `node`. Direct `--cosense-command` to the symlink failed with exit 127 because the shebang is `#!/usr/bin/env node`. A temporary wrapper that prepended `/Users/nishio/.nvm/versions/node/v24.16.0/bin` to PATH fixed acquisition. Follow-up: fetch failures now classify this as `command-env`.
- `grasp acquire` can complete with exit code 0 while fetching 0 pages and putting all candidates into `failed_pages`. That is technically a successful partial-acquisition report, so fetch-stage failures now return `diagnostic.type=all_failed` / `failed_pages[].error_class` instead of relying on exit status alone.
- A raw seed list sorted only by target frequency selected many `.icon` pages. For cross-project analysis, seed generation should have a semantic filter or at least report target classes before fetching.
- A lexical workaround such as boolean `NOT .icon` is only a stopgap. It filters whole lines, not link targets. It cannot answer "which `[/project/page]` links on this line are semantic?".
- Failed `readPage` stderr is now reduced to a compact `failed_pages[].error_class` plus first stderr line where available. Remaining diagnostic gap is seed discovery (`searchFullText` / `listPages`) failures before page fetch starts.
- Friction should not be the headline of this use-case. It becomes implementation input: the desirable user-facing surface is "discover a cross-project map from `[/`", with diagnostics only when the happy path cannot be completed.

## Implications

- The `[/` use case is a strong dogfood case for `acquire --seed-file`: `/nishio` already contains a curated outbound bibliography into other Cosense projects.
- The useful unit is not "fetch all referenced projects"; it is "fetch semantic slices per referenced project". Full acquisition of 183 projects would be expensive and would mix private/inaccessible/noisy refs.
- Current first-class cross-project workflow:
  1. Extract parsed cross-project links from the source project.
  2. classify link targets into semantic/icon/root.
  3. rank projects by semantic refs and source-page spread.
  4. generate per-project seed files.
  5. `cross-project-acquire` or `acquire --seed-file` each project into `<project>:<slice>` namespaces.
  6. read the bounded per-project acquisition summary.

Future richer report layer: cluster / narrate the reciprocal refs and top internal links into an agent-authored map rather than just listing ranked rows.

## Open Questions

- `cross-project-acquire` now runs semantic seed acquisition as a multi-project workflow and returns reciprocal refs plus top internal links. Should the next layer cluster / narrate those signals, or should that remain an agent/report-layer step?
- Now that `acquire` returns `diagnostic.type=all_failed` while keeping exit 0, is that enough for agent workflows, or should a separate strict mode turn all-failed acquisition into non-zero exit?
- How should cross-project links with slash in the target title, such as `[/takker/takker99/ScrapBubble]`, be interpreted: project `takker` + page `takker99/ScrapBubble`, or nested project-like path?
