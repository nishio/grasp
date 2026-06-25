---
type: todo
summary: v1 リリース後にまだ実装していない作業だけを保持する backlog。実装が済んだ項目は grasp-v1-implemented（current facts の SSoT）へ移し、却下した案は各節末の「却下（再提案しない）」1行ガードに畳む。
sources:
  - wiki/entities/grasp-v1-implemented.md（実装済み事実の SSoT）
  - wiki/entities/ai-consumer-feedback-2026-06-23.md（Tier 1-4 由来）
  - wiki/decisions/whole-store-graph-and-cross-project-edges.md
  - wiki/decisions/write-layer-alpha-and-replay-test.md
  - wiki/decisions/markdown-obsidian-indexed-mirror.md
---

# grasp backlog

このページは **まだ実装していない作業**だけを保持する。実装が済んだ事実は [[grasp-v1-implemented]]（current facts の SSoT）へ移すのでここからは消す（*いつ* 実装したかの時系列は [log](log.md)）。却下した案は経緯を展開せず、各節末の **却下（再提案しない）** に理由つき1行で残す（再提案を防ぐガード）。設計判断の根拠は `decisions/` / `concepts/` にあり、本ページはそこへリンクするだけにする。

> 整理 2026-06-25: 旧 backlog は実装済みの作業ログと却下の経緯を本文に抱えて 412 行に膨らんでいた。実装済み narration を [[grasp-v1-implemented]] と [log](log.md) に寄せ、却下を1行ガードに畳み、未実装項目だけを残した。

## Parser fidelity

- **parser false-negative 監査**: strict parser は unresolved target noise を減らすため保守的。短い英数字 title などを link から落としていないか未監査。
- **外部 export の堅牢性は恒常コスト**: nishio の admin metadata-ON export は in-the-wild の代表ではない（string line・page metadata 欠落・export version 差）。非 nishio export ごとに parser 前提が崩れうる＝実質 fuzz test。方針は tolerant import ＋実 export variant の test fixture 化で、一回の修正では閉じない。これは persona2（[[positioning-two-personas]]）を狙う代償。最初の fixture は takker の villagepump string-line ケース（[[takker-opencode-villagepump-test-2026-06-24]]、PR #2 で対応済み）。

### link-shaped but non-semantic edge annotation

`#1` / `#2` が hashtag link になることは、`log.md` artifact handling とは別問題。Scrapbox 互換では `#1` は link-shaped expression であり、人間側も必要なら `` `#1` `` のように escape してきた。grasp は parser で勝手に捨てるより、edge を保持した上で「表現としてはリンクだが、意味のある概念リンクではない」と annotation できる層を持つべき。初期 system heuristic として、`PR #2` / `Open Question #4` のような issue-number edge に output annotation を付け、`unresolved` で sampled examples がすべて non-semantic な target を後ろへ回す処理は実装済み（[[grasp-v1-implemented]]）。

未実装:

- edge annotation schema（候補: `semantic_role`, `graph_scope`, `confidence`, `annotator=system|llm|human`, `reason`）。`link_kind` / typed link / `connection_strength` とは直交する軸。
- system heuristic annotation の拡張: `../[[..]]` placeholder、version/changelog の ordinal reference、issue number 以外の link-shaped non-semantic 表現を分類する。raw edge は消さない。
- LLM annotation workflow: grasp 自身は候補 edge + source line +近傍を出し、LLM が「意味リンクではない」判断を返して store に annotation する。判断は reversible / provenance 付きにする。
- retrieval policy の拡張: `related` / `path` / backlink ranking でも既定で non-semantic edge を弱く扱い、必要なら `--include-non-semantic` で見る。

## CLI and agent UX

`read --around-line` / `search --context` / `peek --line-offset` の bounded navigation primitive は実装済み。残るのは Skill/subagent 運用で不足が見えた時に bounded primitive を足すこと。**LLM 要約は CLI でなく agent 層の責務**（CLI に summarizer を持たせない、[[delivery-cli-plus-skill]]）。

## Markdown / Obsidian indexed mirror

最小 read-only mirror（`import --markdown <folder>`、frontmatter title/id/aliases/tags、first H1 title resolution、content-only 差分 index、`--markdown-exclude-dir` による heavy source directory 除外）は実装済み。決定は [[markdown-obsidian-indexed-mirror]]。未実装:

- surface 命名: `index-md` / `import-md` / `import --format markdown <folder>` を足すか（現状は `import --markdown <folder>`）。
- Obsidian block refs / heading anchors の line-id 対応。
- duplicate title / alias collision の高度な解決。方針は [[markdown-identity-name-collision-policy]]。2026-06-25 の wiki森全件 import dogfood（[[wiki-forest-markdown-import-dogfood-2026-06-25]]）では、registry 42 entries 中 37 entries は temp store に import 成功し、失敗 5 entries はすべて duplicate title / alias collision だった。structured diagnostics は実装済み。次は `drafts/` / `source/` artifact 除外で不要 collision を減らし、その後 schema v6 の `page_handles` / ambiguous query result へ進む。
- alias / title / id / file set 変更時の細かい差分 index（現状は安全側で full rebuild）。

### dogfood corpus を wiki森全体へ広げる

grasp 自身の wiki を mirror の最初の dogfood corpus にするのは実装済み（seed: `import --markdown wiki --project grasp-wiki`）。次は corpus を grasp 1 wiki → **親 llm-wiki の wiki森全体（home 配下 40+ の単一所有者 wiki、registry は `wikis.yaml`）**へ拡張する。動機の全文は [log](log.md) 2026-06-25 と [[scrapbubble]] / [[whole-store-graph-and-cross-project-edges]]。要点:

- 森の現状の横断手段は親 llm-wiki `wiki_search.py` の grep 止まり＝節点アクセス。「N wiki を跨いで参照されるが本文がどこにも無い概念」＝俯瞰グラフ層は出せない。grasp の whole-store cross-project ＋ Markdown mirror がこれを供給できる。
- 森は全部 nishio 所有＝マクロな非 Co- 実例なので、多人数協調を削ぐ grasp の cross-project がちょうど嵌まる。
- **森用の特別 edge policy は要らない**: cross-wiki 参照は import 時に裸の referenced-only 赤 node のまま入れ、whole-store の弱い接続（normalize-title の cross-project 一致）が query 時に繋ぐ（下記 cross-project v6 の strength 層）。

未実装:

- 40+ wiki を 1 store の 40+ project namespace へ import するオーケストレーション（`wikis.yaml` を seed に `import --markdown <folder> --project <wiki-name>` を一括実行）。2026-06-25 手動 dogfood（[[wiki-forest-markdown-import-dogfood-2026-06-25]]）では import 可能 project を 1 store に並べること自体は成立した（37 projects / 2458 pages / 213k lines / 22.5k edges / 1412 unresolved）。ただし orchestration は急がず、collision policy / artifact 除外の後に作る。
- 森規模での navigation/log artifact handling の dogfood（path/frontmatter heuristic と outgoing edge 除外の最小実装は [[grasp-v1-implemented]]）。
- weak 接続の **cross-wiki spread ranking**（「何 wiki を跨いで参照されるか」を signal 化）＝森スケール俯瞰グラフの本体出力。

### LLM Wiki index / navigation artifact handling

`index.md` 等は通常の content page でなく navigation / generated projection として扱う（[[markdown-obsidian-indexed-mirror]]）。path/frontmatter heuristic による navigation classification と outgoing edge の既定 content graph 除外は実装済み（search 対象には残る）。未実装:

- `--include-navigation` の escape hatch。
- store から catalog を projection 再生成する command（`catalog` / `export-index`）。手維持の index 行を置換する。
- `wikis.yaml` / `forest-index.md` は content graph に入れず、複数 project を指す外側 registry として扱う。

### LLM Wiki log / event stream handling

`log.md` は content page でなく append-only event stream / provenance として扱う（[[markdown-obsidian-indexed-mirror]]）。path/frontmatter heuristic による log artifact classification と outgoing edge の既定 content graph 除外は実装済み（search 対象には残る）。設計上の主問題は log entry を巨大 page 内の section とするか、stable identity を持つ first-class record として materialize するか＝grasp では後者。さらに **log entry は現在状態の主張でなく過去の transition event**（A→B→C で `B になった` entry だけ読んで「今は B」と答えるのは誤り）。未実装:

- `log.md` を `## [YYYY-MM-DD HH:MM] op | summary` header ごとに仮想 log-entry record へ split する importer。
- `log/*.md` record-per-file 形式の importer（frontmatter `type: log-entry` / `date` / `op` / `pages` / `sources` 優先）。
- log entry id policy（候補: `source_path + timestamp + content_hash`、record-per-file なら path / frontmatter id 優先）。
- log entry subject extraction（frontmatter `subjects` / `pages`、無ければ body の wikilink / touched path から推定）。
- stale-log guard（log entry を返す時、同 subject の later events を `superseded_by` / `later_events` で同梱）。
- surface 分離: `read <page>`＝current projection、`log` / `history <page>`＝event stream。
- 人間向け `log.md` を record-per-file から生成する projection export。

## Local write and identity layer

v1 は read-only。local store への write / rename / transclude は未実装。着手の3決定（write は当面 alpha testing / テスト＝この repo の過去 wiki 編集の git history を再現できるかで検証 / 実装順序は「楽な順」でなく「危険な順」）は [[write-layer-alpha-and-replay-test]]。作業は `feat/write-identity-alpha` worktree。

**リンクは1種類でない**（Cosense は両方を単一 `[X]` に束ねたのが hub 膨張の根、原理 [[come-from-declared-gather]]）。write/identity 層は2型を別 first-class object としてモデル化する:

- **felt-sense link** — 行キー・sparse・per-occurrence・著者の retrieval 意図（edge）。下記 stable line-id 層に乗る。
- **come-from link** — 用語キー・1宣言・全出現・読者ケア（standing rule）。term identity に紐づき、term が動けば追従する。

未実装:

- `write`: page 作成 / 更新と edge 自動更新（felt-sense と come-from で別経路）。
- `rename`: stable id を保った rename（Scrapbox の参照書き換え / redirect stub の二択を避ける）。
- `transclude`: line-id を使った行参照。
- aliases / page-id policy（page id を「いつ・誰が・どの意味判断で」振るか）。
- stable line-id policy（下記 stable line identity 参照）。
- **rename を跨ぐ stable page-id**（identity-without-name の consumer 側の本体）: AI は根拠をページ単位で引用するので write/rename で title が動くと過去セッションの引用が腐る。`read --json` が安定 page-id を返すこと自体が consumer 価値。read 出力 field は既済、stable identity 化が未済（[[ai-consumer-feedback-2026-06-23]] Tier 4 / [[why-not-scrapbox-clone]]）。

補足: hosted Cosense に AI から書く用途は [[cosense-cli]] の `previewEdit` / `submitEdit` が担う。grasp の write 層は local-only store / 非 Cosense ユーザ向けの別目的。

### typed / directional link（デライトの引き入れ＝前景後景型）

デライトの引き入れ（1輪郭を複数の親に入れる多重所属）は無型の関連リンクでなく「前景（親）/後景（子）」の向き付き包含＝ typed link とみなせる（原理 [[cosense-delite-howm-synthesis]]）。grasp は現状リンクが無型（Cosense 同様、全 predicate が related）。未実装 / 論点:

- リンクに型（向き付き構造型 contains / part_of を最小に）を持たせるか。型は felt-sense / come-from と直交（どちらの型のリンクにも型は乗りうる）。
- 向き（前景/後景）と無向グラフの両立: `related` / `path` は retrieval 用に無向へ畳むので、型付き構造リンクを入れても無向 projection を別に保つ二層が要る。
- 型付けを著者宣言にするか AI ingest 時に自動推定するか（「最初は無印、重要になったら型」「型語彙を増やしすぎない」。整理を runtime/AI に逃がす方針なら型推定は AI 側に寄せる）。
- 多重所属自体は既に持つ。デライトが足すのは遠近＝前景/後景の順序。edge 属性として持つか、`read` 出力でどう見せ分けるか。

### stable line identity

`page.id:line-index` は **安定 line ID でなく positional locator**（行挿入で後続 locator が変わる）。content hash は本文編集で、line index は挿入で identity が変わるため不可＝**stable ID requires memory**。identity 層では `line.id`（opaque stable）と `line_index`（current order）を別列にする。要件:

- local write は既存 line を id で編集し、移動しても id を維持する。
- 外部 source（Cosense export / Markdown mirror）に line id が無ければ初回 import 時に grasp が mint し、identity journal に保持する。
- sync / reimport は旧新 lines を diff し、同一と判定できる line だけ id を引き継ぐ。挿入は新 id、削除は tombstone。split / merge / 重複行 / 大幅編集の曖昧一致は自動同一視しない。

schema 方向:

```text
lines(project, id, page_id, line_index, text, created, updated, user_id)
line_tombstones(project, id, page_id, deleted_at, last_text?)
```

## Search and retrieval

recall（boolean / page scope / 正規化 fallback）は実装済み。順序は **recall を直してから** FTS5 速度最適化（recall と速度は別軸）。未実装:

- **大規模 store での完全なかな/カナ・全半角本文正規化 index**。本文側を materialize した normalized column / FTS hybrid / trigram で持たない限り、完全な正規化 search は大規模 store で高コスト（現状の Python scan は 50k lines 以下に限定）。
- vector search。
- FTS5 trigram hybrid による `search` 高速化。literal substring semantics を守るには `LIKE` fallback / post-filter が要る（[[fts5-trigram-search]]）。
- backlink line の前後文脈窓。
- related ranking の重み調整と、大規模化した時の 2-hop cost 対策。

### gather / mentions / co-links の残課題

`mentions` / `co-links` / `gather`（come-from 昇格候補の初期 heuristic scoring、`returned/total/omitted_counts`、`co-links --rank slice` を含む）は実装済み。出典 [[ai-consumer-feedback-2026-06-23]] Tier 2、KJ法 hub の実測は [[kj-link-hub-audit-2026-06-24]]、原理は [[come-from-declared-gather]]。

**設計テンション（未決）**: 太い verb `gather` は orchestration を CLI に寄せ、「薄い CLI / Skill がオーケストレーション」境界（[[delivery-cli-plus-skill]]）と緊張する。薄さを保つなら Skill 側に gather レシピ、太くするなら verb。nishio 判断待ち。改善の成功条件は「`[KJ法]` backlinks が増える」ことではなく、巨大 hub が **root link + 用途別 slice handle** に分岐し、agent が hub 全体を読まず必要な slice だけ読める状態。

未実装:

- `mentions` の正規化（完全なかな/カナ・全半角）、word boundary、多義語 disambiguation（現状は literal query）。
- come-from 昇格候補の高次分類（AI 作 default 裸 / 意図的 non-link / link gap の3源）、実データでの閾値調整、多義語の一意性判定。
- `co-links` の query-containing でも有用な narrow page（例: `AIにKJ法を教える`）と bibliographic/session title の finer classification、weighting 調整、実データ dogfood。
- `gather --budget` の厳密 token packing / omitted token estimate / 代表サンプル選択の精密化（現状は row 単位 limit）。
- AI clustering handoff: CLI は固定 cluster label を確定せず、AI が仮分類できる bounded rows + sample provenance を返す方針を継続する。

### use-case report composition（icon/person history）

巨大抽出系の「いい感じ」な outcome には report composition 層が要る（原理 [[use-case-experiment-as-outcome-story]]）。raw hits（villagepump `[nishio.icon]` 6,488 paragraphs）は到達としては成功でも、そのままでは読めない。CLI / acquisition 側が返すとよいもの:

- icon/person slice の取得条件（project, diary page rule, date range, icon/user handle, coverage, failures）。
- `icon_hit_kind`（author marker / sentence signed at end / prefix speaker / reaction icon list / mention-of-person / other）。最低限 `[nishio.icon]さん` 型の言及と reaction-only 行を本文発話から分ける。
- representative candidate bundle（year/month counts, top linked targets, keyword/theme counts, longest blocks, source title / line id / snippet つき high-signal examples）。
- report handoff contract: CLI は narrative を確定せず、agent/report 層がユーザ言語で timeline / themes / 代表 scene / caveat / source links を書く。

仮 surface（名前未決）:

```text
grasp acquire https://scrapbox.io/villagepump/ --diary --icon nishio --until 2026-06-24
grasp report icon-history nishio --themes ai,scrapbox,community --top 30
```

重要なのは raw dump でなく **bounded candidate bundle + agent-authored report** を標準 workflow にすること。

### come-from declare / render 層（新規）

巨大 hub が膨れる *why* = per-occurrence の局所判断 × 双方向の大域帰結のミスマッチ（誰も「KJ法 を 490-backlink hub に」と決めていないのに、各ページの親切な `[KJ法]` の副作用で hub ができる）。∴ 対処は「もっとリンク」でも「消す」でもなく、判断を帰結と同じ用語-大域レベルに上げる＝come-from（原理 [[come-from-declared-gather]]）。未実装:

- **come-from declare 層**: 用語を come-from term として標す per-term standing rule（`mentions <query>` の ad-hoc query を declarative に固定）。store 表現は専用テーブル or 宛先ページ frontmatter `come_from: [...]`（後者は Markdown mirror と親和）。
- **come-from render 層**: Markdown mirror / 公開 view を materialize する時、come-from term の裸出現を自動リンク化。store（裸）と view（リンク済み）を分離する（authoring=裸＋宣言 / rendered=自動リンク）。
- 安全域＝必要域: 文字列マッチで多義語は過剰収集するが、読者ケアが要る uncommon 語 ≈ 一意なので安全。昇格候補抽出は「uncommon さ × 頻度 × 一意性」で機械化できる。

## Graph-native reasoning primitives

出典 [[ai-consumer-feedback-2026-06-23]] Tier 3（embeddings 無しの純グラフ操作で「Markdown 束には出せない」価値が出る所）。

- **`path <A> <B>`**: 初期実装済み（pages ∪ unresolved targets を node、materialized internal links を無向 edge、no-path recovery hints まで）。実測でページ間距離は「大半 ≤2-hop」ではなく `path --max-depth 4` の価値あり。残課題: dense hub での performance（nishio store で約4-5s）、neighbor ranking、複数 shortest paths の出し方、実用的に意味のある経路かの継続 dogfood。
- **backlinks の finer ranking**: コア（views ランク）は実装済み。残るのは link 密度 / multiplicity / recency の重み付けで「最も中心的な 20 件」の精度を上げること。

却下（再提案しない）:

- **近傍クラスタリング `--cluster`** — クラスタリングは AI の責務（AI の方が賢い）。grasp は raw + ranking を返し AI が sub-theme に畳む（[[ai-consumer-cost-and-trust]] の fidelity 方針）。CLI でやるなら embeddings 導入後の optional な雑 embedding クラスタリングのみ。却下するのは CLI が cluster label を作ること自体で、AI が clustering できる raw material（counts / ranked rows / co-link slices / bare mention samples）を出す primitive はむしろ必要（上記 gather 系）。

## Negative-result contract

空結果を「情報」として返す（絶対的不在 vs マッチ失敗の区別、[[ai-consumer-cost-and-trust]] 軸2）。`read` / `link-stats` / `search` / `related` の zero-hit recovery hints は実装済み（command 文字列だけでなく近い title 候補・正規化候補・部分一致 line などの実データを含む）。未実装:

- 今後追加する retrieval verb（例: `gather`）でも empty result contract が揃っているかの継続監査。

## Output token economy

line-id のローカル別名（text で `P1:0`、`--json` / `--full-ids` で完全 ID、先頭付近に legend）は実装済み（[[ai-consumer-cost-and-trust]] 軸1）。

却下（再提案しない）:

- **`--strip-decoration`**（icon / bare image URL 単独行を畳む）— decoration 行は noise ではない。`[nishio.icon]` は block の著者情報、bare image URL は今の AI に読めなくても人間に画像を提示でき将来の AI は読む。token 削減は line-id 別名側でやる。

## Sync freshness

`grasp sync` の basic upsert は実装済み（[[incremental-sync]]）。未実装:

- hosted 側で削除された page の tombstone / local delete detection。
- rename detection。
- last-sync cursor の運用精度。

## Cross-project graph を first-class edge に + whole-store retrieval（v6）

決定は [[whole-store-graph-and-cross-project-edges]]。store = 外部 source から再生成可能な projection なので schema を v6 に bump して理想形に作り直す（`recover_store_from_import_cache` 機構で再 import は安全）。現状の parse-on-read `cross_project_refs`（`LIKE '%[/%'` 全スキャン + 毎回 re-parse、edge にならない）を置換する。実装項目:

- **cross-project link を materialize**: `edges` に `target_project` / `link_kind`（internal / cross-semantic / cross-icon / cross-root）を追加、`source_project` へ rename。`CrossProjectLink`（`raw/project/title/target_class`）を流し、`raw` 保存で slash-in-title を再解決可能に。
- **解決と unresolved 再構築**: `[/P/T]` を (P, norm(T)) に解決し、存在チェックを target_project の pages に対して行う。`unresolved_targets` を `(target_project, target_norm)` で集計。materialized page 0 の namespace も unresolved の値に取れる。
- **whole-store default retrieval**: `_require_project` の「複数 project で error」を削除。`search` / `read` / `backlinks` / `related` / `path` / `unresolved` / `mentions` / `co-links` / `gather` は default 全 project、`--project` で絞り、結果は project ラベル付き。`import` / `sync` / `acquire` は project-targeted のまま。
- **read 多義の disambiguation**: 同名 page が複数 namespace にある時 error せず、全候補を project ラベル + summary で返し `--project` / page-id で絞らせる。
- **node 状態 = page 単位の materialized / referenced-only**: project は namespace、「未取得 project」は categorical でなく coverage（materialized page 数）の派生量。acquire = referenced-only node の materialize。`unresolved`(whole-store) が「参照済みだが未取得の知識圏」を link_count 順で出し acquire の seed bibliography になる（[[cross-project-reference-acquire-2026-06-24]] の手作業を primitive 化）。
- **同名 bare 赤リンクの cross-project 統合**: 別 project の同名 bare 赤リンク `[X]`（どの namespace でも未 materialize）を normalize title の project 非依存 key で1ノードに束ねる。materialized page は (project, id) のまま、統合は赤 node だけ。「全 project を通じて誰も本文を書いていないが皆が指す概念ハブ」= project ごとに別 Scrapbox の Cosense が出せない value。誤接続（同綴り別概念）は受容し provenance で後判別（decision point 7）。
- **接続の強弱**: `edges` に `connection_strength`（strong = 人間が書いた明示リンク intra `[X]` / explicit `[/P/T]` / weak = grasp が normalize title の cross-project 一致で推論した接続＝著者が書いていない AI 向けヒント）。bare 赤 `[X]` が他 project の materialized X に解決するのも weak。誤接続は weak 層に閉じ authored グラフを汚さない＝strength が point 7 の誤接続リスクの封じ込め機構。retrieval は strength を label し weak を strong より下に rank。`link_kind` や typed/directional 軸とは直交（decision point 8）。
- **出力契約**: discover-broad-filter-post-hoc。relevance で pre-filter せず target_project / link_kind / connection_strength / scope ラベル付きで surface、絞りは post-hoc flag、出力量は rank + omitted-count で bound、性能は bound で対処し hide しない。現 `cross_project_refs` の `--semantic-only` / `--exclude-icons` / `--include-self` は pre-filter から post-hoc filter に位置づけ直す。
- **history**: store format / materialized index semantics が変わるため [[history]] の `x` を進める（再 import 要）。

未決（decision の Open Questions）: referenced-only namespace の coverage rollup surface 形 / slash-in-title 確定規則の実データ検証 / dense graph での whole-store related/path bound / weak 接続の rank・閾値調整と同綴り別概念の誤接続頻度の dogfood / link 同一判定の表記ゆれ吸収（`yyyy/MM/dd`⇄`yyyy-MM-dd` 等、[[scrapbubble]]）。

## Hosted Cosense acquisition without admin export

`grasp acquire <project-url>`（`--search` / `--filter` / `--full-list` / `--from-page --depth` / `--seed-file`）、`cross-project-refs`（抽出・分類・seed file / acquire command 生成）、`cross-project-acquire`（複数 project を `<project>:semantic` へ一括 partial acquire）、acquire reuse、fetch-stage の env 診断 / all-failed diagnostic は実装済み。current facts は [[grasp-v1-implemented]] の acquire facts、dogfood は [[cross-project-reference-acquire-2026-06-24]]。

未実装 / 残課題:

- **direct public API fallback**: `cosense` binary / Node が無い環境でも public project は Scrapbox API（`curl .../api/pages/<project>` 等）で読める。auth が要る project では従来通り `cosense-cli` に戻す adapter。villagepump dogfood で `cosense` 不在により acquire 不可だったので、入れれば agent 実験の摩擦が下がる。副観測: `search/query?q=...` は 100 件固定で `skip` が効かず、網羅抽出には `pages?sort=title` の列挙が要る。
- env 診断（`cosense` / `node` の shebang `env node` 失敗等）を seed discovery phase（`searchFullText` / `listPages`）へ拡張する。fetch phase は実装済み。
- `cross-project-acquire` の実データ dogfood、project / target ranking の weighting 調整、取得後 summary（reciprocal refs / top internal links / cluster handoff）の richer 化。

設計上の注意（実装時に守る）:

- partial corpus 上の `backlinks` / `related` / `unresolved` は「取得済み subset 内」の結果で、project 全体の事実として表示しない。
- 同じ hosted project の複数 slice を同じ namespace に混ぜると coverage の意味が曖昧になる。`--project project:slice` で分けるか coverage metadata を project 単位で合成する。
- 権限は「その user / token が通常読める page だけ」。admin export の代替であって越権取得経路ではない。
- acquisition mode / seed / depth / limit / acquired_at / failed pages / criteria fingerprint / page manifest を metadata に残す（実装済み、partial の意味を保つため）。

Open Questions:

- `listPages` は非 admin readable project で全ページを pagination できるか。
- `searchFullText` は `[nishio.icon]` / `[/nishio/` を literal に扱うか。検索上限超過時の pagination / continuation はあるか。
- all-candidate 失敗でも exit 0 で partial result を返す方針を維持するか。
- `readPage` の hosted line id を採用するか（現行は export/sync と同じく grasp 側で `page.id:line-index` を維持）。
- partial corpus で `sync` する時、seed predicate 外の recently updated page を取り込むか、acquisition mode ごとに sync 動詞を分けるか。
- direct public API fallback を入れる場合、Scrapbox API と cosense-cli の metadata / auth / rate limit / search semantics の差をどこまで surface に出すか。

## Packaging and distribution

実装言語と配布チャネルの軸は [[language-and-distribution]]（当面 Python + pipx）。未実装:

- PyPI 公開時の package 名確認。
- `pipx install` 前提の配布導線。
- user-level Skill symlink と package install の統合。
- Python 不可 agent 環境が現実化した場合の native binary 配布。
