---
type: decision
summary: persona2 向けの Markdown / Obsidian folder 対応は、既存 folder を read-only indexed mirror として SQLite store に materialize し、Skill はその CLI を使わせる薄い層にする。pitch は faster grep ではなく graph reader for LLM agents。LLM Wiki の index/navigation/log は通常の根拠ページでなく current projection / event stream として扱い、graph edge へ無条件に混ぜない
sources:
  - nishio 質問 2026-06-23「既存のMarkdownの束 or Obsidian のfolderをpointし、それにgrepよりも高速な検索とリンクたどりの能力を付与するSkillという方向性はどうか」
  - [[positioning-two-personas]]
  - [[persona2-user-test-2026-06-23]]
  - nishio 質問 2026-06-24「LLM Wikiのindexをgraspの中に入れるのか外に別の仕組みをつけるのか」
  - /Users/nishio/llm-wiki/wiki/analyses/indexの健全性は複製か射影かで決まる-20260622.md
  - /Users/nishio/llm-wiki/wiki/sources/kouchou-ai-index-txt-pattern-20260617.md
  - /Users/nishio/llm-wiki/wiki/concepts/探索の地図と事実の分離.md
  - nishio 質問 2026-06-24「LLM Wiki の log を grasp に入れる場合の運用。並行エージェント衝突より log entry の扱いが本筋か」
  - nishio 質問 2026-06-24「A→B→C と変化した時、B になった log だけ見ると誤答する。どういう仕組みが必要か」
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

- frontmatter `title` があれば page title にし、無ければ first H1、さらに無ければ file stem を title にする（2026-06-25 に first H1 fallback を追加）。
- frontmatter `id` があれば page id にし、無ければ relative path hash を page id にする。
- frontmatter `aliases` と file stem を title resolve 候補にし、`[[alias]]` を canonical title へ解決する。
- frontmatter `tags` を page から tag target への edge にする。
- `[[Page]]`, `[[Page|alias]]`, `[[Page#Heading]]`, `[[folder/Page.md]]`, `![[Embed]]`, `#tag` を edge にする。
- inline backtick / fenced code block 内は edge にしない。
- `--markdown-exclude-dir <name>` で directory basename を除外し、`raw/` など heavy raw/generated directory を mirror から外せる。
- manifest を metadata に保存し、content-only 変更なら changed file の page / lines / outgoing edges だけを差し替える。title / id / aliases / graph role / exclude dirs / file set が変わった時は安全に full rebuild する。
- 既存 Markdown folder へは書き戻さない。

未実装のまま残すもの: block refs、alias-aware なより細かい差分 rebuild、duplicate/alias collision の高度な解決。これらは [[grasp-backlog]] の継続項目。

## Update: LLM Wiki index / navigation boundary

2026-06-24 判断: **LLM Wiki の `index.md` を通常ページとして graph に混ぜるのではなく、grasp は index を生成できる substrate を持つ**。index は content の source-of-truth ではなく、frontmatter summary / path / page graph から作れる projection / navigation layer として扱う。

責務分離:

- grasp store に入れる: 各 wiki の pages / lines / content links / frontmatter `summary` / aliases / tags / unresolved targets / search materialization。
- grasp store から生成する: wiki 内 full catalog（kouchou pattern の `index.txt` 相当）、必要なら人間向け `index.md` のたたき台。
- grasp 外に残す: `wikis.yaml`, `forest-index.md`, `lint_next`, `draft_cycle` など wiki森の運用 orchestration。これは「どの wiki を読むか」の registry / scheduler であり、個別 wiki の graph substrate ではない。

理由:

- LLM Wiki の `index.md` は中央 catalog / navigation であり、多数ページへ意図的にリンクする。これを通常 content edge と同列に入れると、`index.md` が巨大 hub になり、`related` / `path` が「全ページが index 経由で近い」と誤る。
- 親 llm-wiki 側の診断では、健全な index は source-of-truth の**射影**であり、壊れやすい index は知識の**複製**。grasp は native graph store を持つので、index を複製として保存するより projection として再生成する方が設計に合う。
- `探索の地図と事実の分離` 原則に従い、navigation files are not evidence。AI が回答の根拠にすべきなのは target pages / raw / source-backed synthesis であって、index 行ではない。

実装含意:

- Markdown import は `index.md`, `forest-index.md`, `maps/`, `views/` などを navigation artifact、`log.md` / `log/*.md` を log artifact と分類できる必要がある。
- navigation artifact は search には入れてよいが、既定では outgoing edges を `related` / `path` / backlink ranking の content graph から除外する。必要なら明示 flag（例: `--include-navigation`）で見る。
- `grasp catalog` または `grasp export-index` 的な generated view は frontmatter `summary` を source-of-truth にする。index 行の手維持を source-of-truth にしない。
- 複数 wiki は [[multi-project-store]] の通り project namespace を分ける。wiki森横断 registry は外側から複数 project を指す layer であり、別 wiki の同名ページを暗黙 merge しない。

2026-06-25 実装: Markdown mirror は path/frontmatter heuristic で navigation/log artifact を分類し、その outgoing edges を既定 content graph から除外する。本文 lines は store に残すので `search` は hit する。未実装は `--include-navigation` escape hatch、catalog/export-index、log entry split など。

### 2026-06-25 dogfood: Markdown LLM Wiki content is usable as LLM context

grasp 自身の `wiki/` を temp store に import して確認した結果、Markdown LLM Wiki に file back した内容は、再 import 後に Cosense export と同じ retrieval primitives で LLM context として使える。`search` は current facts / backlog / decisions / log を line_id + 周辺文脈つきで拾い、`read` は本文・行レベル backlinks・related・page-local unresolved を同梱する。`backlinks` / `related` / `path` も content pages を辿れる。

重要な境界: `log.md` は検索対象には残るが、navigation/log artifact の outgoing edge 除外により、既定の graph 近傍を支配しない。したがって Markdown mirror の現時点の価値は「既存 Markdown wiki を壊さず、LLM が読むための read-only graph projection を作る」こととして成立している。未解決の差は hosted 最新性や write/rename/identity 層であり、Markdown mirror の read path ではない。

### 2026-06-25 dogfood: wiki森 import scale and collision blocker

`wikis.yaml` registry の全 entries を temp store に `import --markdown <path>/wiki --project <name> --markdown-exclude-dir raw` で投入した。private 内容は読まず、件数と失敗型だけを観測。42 entries 中 37 entries が import 成功し、aggregate は 37 projects / 2458 pages / 213k lines / 22.5k edges / 1412 unresolved。全体の import wall time は約 22 秒。

失敗 5 entries は missing folder や raw directory の重さではなく、すべて duplicate title / alias collision。類型は draft variants の同一 H1、複数 directory の `_overview` / `README` / `index` file stem alias、source digest / session file と canonical page の alias 衝突。したがって森スケールの次 blocker は performance ではなく collision policy。read-only mirror は duplicate を即 import error にするだけでなく、handle ambiguity を表現する必要がある。`source/` は raw 由来の digest / source-backed synthesis なので default exclude ではなく、保持した上で source role / evidence layer として扱う。

2026-06-25 schema v7/1.7.3 追記: `edges.resolution_status` と Markdown import softening により、同じ条件の forest smoke は 42/42 entries 成功になった。duplicate title / alias は import error ではなく `read <handle>` の ambiguity と `edges.resolution_status=ambiguous` で表現する。`backlinks <ambiguous handle>` / `ambiguities` report / `import-forest` は実装済み。残件は `related <ambiguous handle>` と whole-store cross-project surface。

## Update: LLM Wiki log / event stream boundary

2026-06-24 判断: **LLM Wiki の `log.md` は知識ページではなく append-only event stream / provenance record** として扱う。並行エージェントが1ファイルへ追記して衝突する問題は現実の運用上の理由だが、grasp 側の本筋は「巨大な `log.md` を ordinary page として読むか、entry を first-class record として materialize するか」。

運用判断:

- 既存 Markdown LLM Wiki が `log.md` 1ファイルを使っていても、Markdown mirror は `## [YYYY-MM-DD HH:MM] op | summary` のような log header ごとに **仮想 log-entry record** へ split して扱える方がよい。
- 将来の write / file back では `wiki/log/*.md` のような record-per-file 形式も許容する。これは並行 agent の衝突回避に効くが、設計上は「log entry が stable identity を持つ」ことが主目的。
- `log.md` / `wiki/log/*.md` は search 対象にはしてよいが、既定の content graph edge / `related` / `path` の根拠ページとは分ける。log entry は「何が更新されたか」を示す provenance であり、current fact の source-of-truth ではない。
- `log.md` 1本を人間向け時系列 view として残す場合は、record-per-file から生成される projection とみなす。手編集の正本をどちらにするかは wiki 運用の選択だが、grasp store では entry row として正規化する。

実装含意:

- Markdown import は navigation artifact とは別に log artifact / event stream を分類できる必要がある。
- `log.md` split parser は header pattern, timestamp, op, summary, body, touched pages を抽出し、entry id を `source_path + timestamp + content_hash` などで安定化する。
- record-per-file 形式では frontmatter `type: log-entry`, `date`, `op`, `pages`, `sources` を優先して materialize する。
- `grasp log` / `grasp history <page>` のような surface は、content graph search ではなく event stream query として設計する。

### Current-state projection and stale-log guard

2026-06-24 追加判断: **log entry は現在状態の主張ではなく、過去の遷移イベント**として扱う。対象が A→B→C と変化した時、`B になった` という log entry は「その時点で A→B になった」という正しい event だが、現在状態の答えではない。LLM がその entry だけを読んで「今は B」と答える設計は壊れている。

必要な分離:

- current state: entity / decision / backlog などの current page、または event stream を fold して materialize した current projection。
- event log: `at T1, A→B`, `at T2, B→C` のような transition history。
- provenance: current state がなぜそうなったかを説明するために参照する log entries。

query 方針:

- 既定の「X は今どうなっているか」は current page / current projection を読む。log search hit 単独で答えない。
- 「いつ B になったか」「T1 時点ではどうだったか」のような temporal / provenance query は event log を読む。
- log entry を返す時、同じ subject にその entry より後の event があるなら `superseded_by` / `later_events` を同梱し、stale な中間状態を現在状態として読ませない。
- record-per-file log では frontmatter `subjects` / `pages` / `supersedes` を優先する。`supersedes` を完全に手維持できなくても、最低限 `subjects` と `date` から後続 event を検出する。

grasp における実装含意:

- `read <page>` は current content を返し、`history <page>` は event stream を返す、という surface 分離が必要。
- `search` が log artifact に hit した場合、text / JSON ともに「log entry は current fact ではない」ことと後続 event の有無を示す。
- current projection を生成する場合、event log をそのまま根拠にせず、fold 後の state と provenance links を別々に保持する。

### 2026-06-25 correction: `#1` noise is edge annotation, not log handling

grasp wiki dogfood で `log.md` が graph を汚すことと、`PR #2` / `Open Q #4` のような `#1` 系が hashtag edge になることを同一視しかけたが、これは別問題。log / navigation artifact handling は **page/file の役割**の問題で、`#1` は **link-shaped expression が意味のある概念リンクか**の問題。

Scrapbox 互換では `#1` は link として成立する。したがって parser が捨てるのではなく、edge を保持した上で system / LLM / human が「意味リンクではない」「issue number / ordinal reference」などの annotation を付け、retrieval ranking や unresolved concept hub から弱める方針が正しい。これは [[grasp-backlog]] の link-shaped but non-semantic edge annotation に積む。

## Open Questions

- CLI 名: 初期実装は `import --markdown <folder>`。将来 persona2 向けに `index-md` alias を足すか。
- duplicate title / alias collision の扱いは [[markdown-identity-name-collision-policy]] に分離。schema v6/v7 と `1.7.3` で handle ambiguity / edge resolution / backlinks / ambiguity report / import-forest の最小実装は入った。残件は `related <ambiguous handle>`。
- heading / block ref を line-id とどう対応させるか。
- `#tag` と wikilink を同一 edge type にするか。
- search index は FTS5 trigram hybrid にするか、まず correctness 優先で `LIKE` にするか（[[fts5-trigram-search]]）。
- log artifact の entry split は wiki ごとの header convention にどこまで対応するか。最低限は LLM Wiki / grasp wiki の `## [timestamp] op | summary`。
- log entry の `subjects` 抽出をどこまで自動化するか。明示 frontmatter / touched page list が無い既存 `log.md` では body 中の wikilink と file path から推定するしかない。
