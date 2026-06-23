---
type: decision
summary: persona2 向けの Markdown / Obsidian folder 対応は、既存 folder を read-only indexed mirror として SQLite store に materialize し、Skill はその CLI を使わせる薄い層にする。pitch は faster grep ではなく graph reader for LLM agents
sources:
  - nishio 質問 2026-06-23「既存のMarkdownの束 or Obsidian のfolderをpointし、それにgrepよりも高速な検索とリンクたどりの能力を付与するSkillという方向性はどうか」
  - [[positioning-two-personas]]
  - [[persona2-user-test-2026-06-23]]
---

# Decision: Markdown / Obsidian folder は read-only indexed mirror として取り込む

決定: persona2（世界の LLM Wiki / Markdown 束ユーザ）向けの on-ramp は、既存の Markdown / Obsidian folder を **read-only indexed mirror** として `grasp` store に取り込む方向にする。ユーザは folder を point するだけで、`grep` 的な文字列検索に加えて、リンクたどり・逆リンク・related・unresolved target・近傍同梱 read を得る。

重要な責務分離:

- **実体は adapter / indexer**: Markdown / Obsidian folder を parse し、SQLite store に pages / lines / edges / search index を materialize する。
- **Skill は薄い利用層**: Agent Skill は `grasp` CLI の使い方・探索手順・persona2 向け説明を持つだけ。Skill 自体が検索を速くするわけではない。
- **native store は Markdown にならない**: [[persistence-custom-format]] の決定通り、Markdown は import source。grasp の保存層は独自 graph store。

## pitch

persona2 向けの lede は "faster grep" では弱い。小〜中規模の Markdown folder では `rg` が十分速く、速度だけでは差別化しにくい。

強い pitch は:

> grep は文字列 hit を返す。grasp は **ページ本文 + 逆リンク行 + related + unresolved targets** を一回で返す。

つまり persona2 向けの表現は **indexed graph reader for Markdown / Obsidian notes, optimized for LLM agents**。速度は副次的価値であり、本質は v1 の中核挙動（[[grasp-v1-implemented]]）である **read = 近傍同梱** を Markdown / Obsidian assets に付与すること。

## 想定 CLI surface（案）

未実装。最初の surface は read-only でよい。

```text
grasp index-md ~/Notes
grasp read "Some Note"
grasp search "identity"
grasp backlinks "Some Note"
grasp related "Some Note"
```

`index-md` は `import-md` でもよいが、persona2 には「既存 folder を移行せず point して index する」ニュアンスが重要。native store を作るだけで、元 folder へ書き戻さない。

## store に materialize するもの

- files/pages: path, title, frontmatter, aliases, mtime, hash
- lines/blocks: line id, heading context, text
- links: `[[wikilink]]`, `[[note#heading]]`, `[[note|alias]]`, embeds, tags
- backlinks: edges の逆読み
- unresolved targets: link されているが対応 note が無い target
- search index: FTS / trigram / fallback `LIKE` など。日本語・短い query・記号入り query の correctness は [[fts5-trigram-search]] と同じ注意が要る。

## Obsidian compatibility scope

最初から最低限見るべきもの:

- `[[Page]]`
- `[[Page|alias]]`
- `[[Page#Heading]]`
- `![[embed]]`（edge として扱うかは要検討）
- frontmatter `aliases`, `tags`, 可能なら `id`
- `#tag`
- filename と title の衝突
- block refs `^block-id` と grasp `line-id` の対応

非目標（初期）:

- Markdown folder への write-back
- rename propagation
- Obsidian plugin behavior の完全再現
- Canvas / Dataview など plugin-specific syntax

## identity policy

初期は read-only mirror なので、identity は保守的に扱う。

- frontmatter `id` があれば page id 候補。
- `aliases` は title resolve 候補。
- `id` が無い場合は path hash / stable file key / title のどれを使うか未決定。
- persona2 pitch の "rename で links が切れない" は、write/rename 層が入るまでは **将来価値** として扱う。read-only mirror 段階では「folder を壊さず graph retrieval を付与する」が価値。

## なぜ read-only mirror から始めるか

- 既存 Obsidian vault / Markdown notes を壊さない。
- persona2 は移行コストに敏感。最初は "point at folder" が必要。
- `mtime` / file hash で差分 index できる。
- write / rename / identity-without-name は設計の核だが、persona2 の最初の on-ramp では不要。先に retrieval value を実演する。

## 罠

- "grep より速い検索" を主張の中心にすると、`rg` と比較されて価値が縮む。
- "Obsidian clone" に見えると [[why-not-scrapbox-clone]] の線引きが溶ける。grasp の差別化は UI / plugin ecosystem ではなく **LLM agent が CLI で graph neighborhood を読む体験**。
- Markdown を native store にしようとすると、[[persistence-custom-format]] で避けた逆リンク維持のしがらみを再輸入する。

## 帰結

- persona2 active acquisition の前に、この adapter / indexer は release gate。
- README / HN / Reddit では Scrapbox ではなく Markdown / Obsidian folder を入口に置く。
- Agent Skill は adapter 実装後に persona2 用の探索手順を薄く足す。CLI mechanics は `grasp <cmd> --help` を SSoT に保つ。

## Update: minimal mirror implemented

2026-06-24: `grasp import --markdown <folder>` として最小 read-only mirror を実装した。`wiki/` を最初の dogfood corpus とし、既存 SQLite graph store に `.md` files を materialize する。初期 surface はこの decision の案のうち `index-md` ではなく既存 `import` に寄せた `import --markdown`。

実装済み policy:

- frontmatter `title` があれば page title にし、無ければ file stem を title にする。
- frontmatter `id` があれば page id にし、無ければ relative path hash を page id にする。
- frontmatter `aliases` と file stem を title resolve 候補にし、`[[alias]]` を canonical title へ解決する。
- frontmatter `tags` を page から tag target への edge にする。
- `[[Page]]`, `[[Page|alias]]`, `[[Page#Heading]]`, `[[folder/Page.md]]`, `![[Embed]]`, `#tag` を edge にする。
- inline backtick / fenced code block 内は edge にしない。
- manifest を metadata に保存し、content-only 変更なら changed file の page / lines / outgoing edges だけを差し替える。title / id / aliases / file set が変わった時は安全に full rebuild する。
- 既存 Markdown folder へは書き戻さない。

未実装のまま残すもの: first H1 title resolution、block refs、alias-aware なより細かい差分 rebuild、duplicate/alias collision の高度な解決。これらは [[grasp-backlog]] の継続項目。

## Open Questions

- CLI 名: 初期実装は `import --markdown <folder>`。将来 persona2 向けに `index-md` alias を足すか。
- title resolution: 初期実装は frontmatter title → file stem。first H1 を使うか。
- duplicate title / alias collision の扱い。
- heading / block ref を line-id とどう対応させるか。
- `#tag` と wikilink を同一 edge type にするか。
- search index は FTS5 trigram hybrid にするか、まず correctness 優先で `LIKE` にするか（[[fts5-trigram-search]]）。
