---
type: entity
summary: 2026-06-29 に HN/Reddit の Grasp 隣接 discussion を見たサーベイ。HN は local-first / AI-first knowledge base と「Obsidian + AI では?」への比較圧、Reddit は Karpathy-style LLM Wiki / Obsidian vault / agentic project memory の実践と反論が熱い。persona2a は active に served できるが、cold HN/Reddit persona2b は generic RAG / AI notes app と誤読されやすい
sources:
  - https://news.ycombinator.com/item?id=48675435
  - https://news.ycombinator.com/item?id=47889110
  - https://news.ycombinator.com/item?id=47899844
  - https://news.ycombinator.com/item?id=43667061
  - https://www.reddit.com/r/ObsidianMD/comments/1uai1w2/karpathys_llm_wiki_setup/
  - https://www.reddit.com/r/ObsidianMD/comments/1shntdn/new_plugin_llm_wiki_turn_your_vault_into_a/
  - https://www.reddit.com/r/ObsidianMD/comments/1sx040s/whats_the_deal_with_the_hype_around_karpathys_llm/
  - https://www.reddit.com/r/AI_Agents/comments/1tjtqm5/karpathys_llmwiki_for_agentic_software_development/
id: 7db2eb5f53d6f50e034575a5
title: HN Reddit Grasp-adjacent survey 2026-06-29
---

# entity: HN Reddit Grasp-adjacent survey 2026-06-29

目的: [[positioning-two-personas]] の GTM=HN/Reddit 仮説を、2026-06-29 時点の公開 discussion で軽く当てる。これは launch 実行ではなく、どこに需要・反論・語彙があるかの survey。

## Surveyed clusters

### HN: local-first / AI-first knowledge base

- OpenKnowledge は HN で「AI-first alternative to Obsidian/Notion」として出ており、Markdown editor、Claude/Codex/Cursor integration、LLM-wiki / AI Second Brain 用 MCP/skills/RAG、CRDT+git の同時編集を掲げる。反応は強いが、コメントの主な突っ込みは「Obsidian/VS Code より何が良いのか」「local-first なら local model / local embeddings が必要」「個人 vault を AI や cloud に見せたくない」。
- Atomic は「local-first, AI-augmented personal knowledge base」として出ていたが、HN コメントでは「Obsidian に AI を焼いただけ」に見える疲れと、local-first を名乗るなら主機能が非 local では困る、という警戒が出ている。
- Wuphf 系の HN post は Karpathy-style LLM wiki を「Markdown + git が SSoT、BM25 + SQLite index」と説明しており、grasp の [[adoption-trust-gradient]] mode1 / [[markdown-obsidian-indexed-mirror]] にかなり近い。ただし graph DB なしを明示しているので、grasp は「agent 向け graph read substrate」として差分を出せる。
- memEx / markdown-oxide 周辺では、Obsidian / Roam / org-mode / Markdown LSP / future-proof plain text / no lock-in が語られている。AI に限らず、HN の PKM 読者は plain Markdown と editor integration を強く評価する。

### Reddit: Karpathy-style LLM Wiki / Obsidian vault / agent memory

- r/ObsidianMD では Karpathy-style LLM Wiki の実践・plugin・workflow が連続して話題になっている。Obsidian + Claude Code を使い、整理より収集に寄せ、AI に構造化とリンクを任せる方向が受けている。
- r/ObsidianMD の LLM Wiki plugin thread は「vault を queryable knowledge base にする」「OpenAI/Anthropic/Google に送らない」「local model / regular hardware で動くか」を前面に出す。privacy / local は Reddit でも hook。
- r/AI_Agents では、agentic software development の persistent project memory として LLM Wiki が議論されている。CLAUDE.md、session close protocol、handoff summary、Git commits、Obsidian vault のような実践は grasp の file-back / activity / session_id / event ledger の dogfood と近い。
- 同じ r/AI_Agents thread には強い反論もある。古い/半分間違った過去 docs を agent が自由に読むこと、AI が内容を重複・rephrasing して散らすこと、code/spec drift、user intent が AI freestyled slop に沈むことへの警戒。これは grasp の write-status / semantic log / provenance / direct-patch fallback discipline が答えるべき痛点。

## Channel map

| 場所 | 期待できる反応 | Grasp 側の出し方 |
|---|---|---|
| HN Show HN | local-first / OSS / Markdown / agent tooling への強い反応と、競合比較の厳しい突っ込み | 「Obsidian replacement」ではなく、CLI で agent が読む local graph substrate。短い demo と diffable repo を出す |
| HN comments under AI knowledge-base posts | 近接 competitor との比較、local model / privacy / concrete value の質問 | 直接宣伝ではなく、bounded graph read / no up-front SSoT migration / git+SQLite durability を具体例で説明 |
| r/ObsidianMD | persona2a 本命。Karpathy LLM Wiki / vault query / local privacy が既に言語化されている | Obsidian plugin 競争ではなく、既存 vault を AI agent が CLI で読む indexed mirror として提示 |
| r/AI_Agents | agentic project memory / long-running project context の実務者 | file-back runbook、session handoff、activity/history、stale/rot guard を前面に出せる |
| r/PKMS | graph / knowledge management / LLM Wiki の概念寄り | 具体ツール比較より、why graph read and provenance matter を整理して出す |
| r/LocalLLaMA | local model / embedding / privacy 期待値の検証場所 | local embeddings / local reranker の story ができるまでは主戦場にしない |

## Implications for Grasp

1. **persona2a は実在し active**。dense Obsidian / Markdown wiki を持ち、Karpathy-style LLM Wiki / agent memory を試している人がいる。[[whole-store-graph-and-cross-project-edges]]、[[markdown-obsidian-indexed-mirror]]、[[parallel-agent-substrate-goal]] はこの層にそのまま刺さる。
2. **cold HN/Reddit persona2b は skeptical channel**。HN は「また Obsidian + AI か」「local-first なのに cloud か」「自分の vault を見せたくない」「VS Code/Obsidian/grep でよくないか」を即座に聞く。launch するなら generic RAG app でなく、bounded graph read の実演が必要。
3. **語彙は Scrapbox ではなく LLM Wiki / Obsidian vault / agent memory / local-first Markdown**。Scrapbox は lineage に後置する、という [[positioning-two-personas]] の判断は正しい。
4. **privacy/local は hook だが、Grasp の primary differentiation ではない**。privacy を掲げる competitors は多い。grasp の差分は `read` が source page + backlinks + related + unresolved を bounded に返し、file-back / reconcile で agent write の drift を制御すること。
5. **LLM Wiki skepticism は設計 input**。古い docs、slop propagation、code/spec drift、duplicated memory への反論は正当。Grasp は「agent が勝手に全部読む/書く」ではなく、source-backed retrieval、semantic log、event ledger、strict status、session ownership を売りにする。

## Candidate external demo

HN/Reddit に出す前に必要な最小 demo:

- seed: small but dense Markdown / Obsidian-like vault。公開可能な llm-wiki subset か synthetic project memory。
- task: agent が「この設計判断の背景と未解決を答えて」と聞く。
- comparison: raw grep / editor search では token が散る一方、`grasp read` / `search` は source page + backlinks + related + unresolved を bounded に返す。
- write loop: session close で file-back し、`write-status --strict` が clean であることを見せる。stale Markdown / direct-patch fallback は `reconcile-markdown` で SSoT に戻す。

## Open Questions

- HN 投稿の最小タイトルは何か。候補: `Show HN: Grasp - a local graph reader for agent-maintained Markdown wikis`。ただし `reader` だけでは write/file-back dogfood が弱いかもしれない。
- r/ObsidianMD に出す場合、plugin ではないことは弱点か、それとも CLI agent substrate として差別化になるか。
- local embeddings / local LLM をいつまでに語れるようにするか。privacy hook は強いが、今の grasp は graph/SQLite/token-bounded read が主役であり、local model story を先に盛ると軸がぶれる。
