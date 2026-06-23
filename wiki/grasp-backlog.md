---
type: todo
summary: 旧 SPEC.md と旧 v1-todo.md に書かれていたが、v1 時点で未実装の項目。v1 実装済み事実は grasp-v1-implemented に分離した。
sources:
  - 旧 wiki/SPEC.md（v0.5 実装指示, deleted after split）
  - 旧 wiki/v1-todo.md（一時 TODO, deleted after split）
  - wiki/entities/persona1-user-test-2026-06-23.md
  - wiki/entities/persona2-user-test-2026-06-23.md
  - wiki/entities/fts5-trigram-search.md
  - nishio design note 2026-06-23: non-admin project acquisition
  - `cosense searchFullText/listPages/readPage --help` 2026-06-23
---

# grasp backlog

このページは、旧 `SPEC.md` / 旧 `v1-todo.md` に書かれていたが **v1 リリース時点でまだ実装していないもの**を保持する。完了済みの v1 surface は [[grasp-v1-implemented]]。

## Parser fidelity

2026-06-23 21:49: `#tag` link 化と数字のみ `[1]` / `[2024]` link 化は実装済み。current facts は [[grasp-v1-implemented]]。

### parser false-negative 監査

現状の strict parser は unresolved target noise を減らすため保守的。短い英数字 title などを落としていないか未監査。

## CLI and agent UX

2026-06-23 21:49: zero-hit recovery hints、`grasp read ... --json` 後置許容、help example drift、store missing diagnostics は実装済み。current facts は [[grasp-v1-implemented]]。

### long page navigation

現状: 長大ログ page の default `read` は CLI 一括出力として多すぎることがある。

2026-06-23 21:52 判断: P0 としては CLI に summarizer を持たせない。Claude Code / OpenCode のような harness は大きい shell output を truncate / 保存し、subagent は中間 tool output を親 conversation へ返さない。したがって長大ページの読解はまず Skill 側で subagent / Explore agent に委譲し、親には要約・根拠 page・line-id だけを返す。詳細は [[delivery-cli-plus-skill]]。

2026-06-24 01:58: `read --around-line <line-id> --line-context N` は実装済み。完全 `line_id` から所属ページを解決し、中心行の前後 N 行だけを返す。JSON は `line_window`、text は `line_window: P1:12 (lines A-B, context N)` を出す。local alias（`P1:12`）は実行内表示用なので入力には使わず、`--json` / `--full-ids` の完全 ID を使う。

2026-06-24 02:30: `search --context N` は実装済み。検索 semantics は変えず、各 hit に前後 N 行の `context_lines[]` と `context_window` を同梱する。text 出力でも hit 直下に bounded context を表示する。

候補:

- `peek --line-offset`

これらは Skill/subagent 運用で不足が見えた時に足す bounded primitive。LLM 要約は CLI ではなく agent 層の責務。

## Markdown / Obsidian indexed mirror

persona2 向け on-ramp。詳細決定は [[markdown-obsidian-indexed-mirror]]。

2026-06-24 00:58: 最小 read-only Markdown mirror は実装済み。`grasp import --markdown <folder>` が `.md` files を既存 SQLite graph store に materialize し、file stem を title、`[[...]]` / `#tag` を edge として既存 `read` / `backlinks` / `related` surface で読める。2026-06-24 01:12 に frontmatter `title` / `id` / `aliases` / `tags` 対応、2026-06-24 01:45 に content-only 差分 index も追加済み。current facts は [[grasp-v1-implemented]]。

未実装:

- `index-md` / `import-md` / `import --format markdown <folder>` を追加するかどうか。現状の実装 surface は `import --markdown <folder>`。
- first H1 title resolution。
- Obsidian block refs と heading anchors の line-id 対応。
- duplicate title / alias collision の高度な解決（現状は import error）。
- alias / title / id / file set 変更時のより細かい差分 index。現状は安全のため full rebuild に倒す。

### grasp 自身の wiki を最初の dogfood corpus にする

2026-06-24 00:24: この grasp wiki（`wiki/`, Markdown + frontmatter + `[[...]]`）自体を mirror 層の最初のテスト corpus にする（nishio 動機, いつかのタイミングで）。狙いは「自分の設計判断グラフを近傍同梱で辿りながら次を実装する」ループを閉じること。段階は **read-only mirror が write 層より先**（write より小さく、すぐ価値が出る）。

2026-06-24 00:58: dogfood seed として実装完了。`python3 -m grasp --store /tmp/grasp-wiki.sqlite import --markdown wiki --project grasp-wiki` で `wiki/` を index し、`read markdown-obsidian-indexed-mirror` などで本文＋逆リンク＋related＋未解決 target を読める。

Cosense JSON export だけ見ていると気づけない設計判断が1つあぶり出される: **このwikiはリンク記法が2系統混在**しており、mirror parser は「どれを edge とみなすか」の policy が要る。

- `[[...]]` = grasp 内リンク → **edge にする**。
- バックティックのプレーン名（例: `名前ではなくIDで識別する設計`）= 親 llm-wiki への cross-wiki link → **edge にしない**（別 wiki の node を解決できない。grasp 内 lint が cross-wiki link を broken 扱いする規約とも整合, 出典 `../CLAUDE.md` ページルール）。

∴ 上の Markdown parser TODO（`[[Page]]` / `[[Page|alias]]` 等）に「**どの記法を edge とみなすか**の policy」を明示項目として足す。frontmatter（type / summary / sources）の扱いも併せて決める。詳細決定は [[markdown-obsidian-indexed-mirror]]。

### LLM Wiki index / navigation artifact handling

2026-06-24 判断: LLM Wiki の `index.md` は通常の content page ではなく navigation / generated projection として扱う。詳細は [[markdown-obsidian-indexed-mirror]]。

現状: 最小 Markdown mirror は全 `.md` を同列に import するため、`wiki/index.md` のような全件 catalog が ordinary graph edges を大量に持つ。これは dogfood corpus では小さいが、親 llm-wiki 規模では `index.md` が巨大 hub になり、`related` / `path` を汚す。

未実装:

- navigation artifact の分類。候補: path heuristic（`index.md`, `index.txt`, `log.md`, `forest-index.md`, `maps/`, `views/`）＋ frontmatter `role: navigation` / `layer: navigation`。
- navigation artifact の outgoing edges を既定の content graph から除外する。検索対象には残してよいが、`related` / `path` / backlink ranking では通常 content edge と混ぜない。
- 明示 flag（例: `--include-navigation`）で navigation edges も読む escape hatch。
- frontmatter `summary` / path / type から full catalog を生成する command（`grasp catalog` / `export-index` など）。index 行を手維持するのではなく、store から projection として再生成する。
- wiki森 `wikis.yaml` / `forest-index.md` は grasp store 内の content graph に入れず、複数 project を指す外側 registry / orchestration として扱う。

### LLM Wiki log / event stream handling

2026-06-24 判断: LLM Wiki の `log.md` は通常の content page ではなく append-only event stream / provenance record として扱う。詳細は [[markdown-obsidian-indexed-mirror]]。

本筋: 並行 agent が1つの `log.md` に追記すると conflict しやすい、という問題は運用上重要だが、grasp 側では副次的。設計上の主問題は **log entry を巨大 page 内の section として扱うか、stable identity を持つ first-class record として materialize するか**。grasp では後者が自然。

2026-06-24 追加判断: log entry は現在状態の主張ではなく過去の transition event。A→B→C と変化した対象について `B になった` entry だけを読んで「今は B」と答えるのは誤り。既定 query は current page / current projection を読み、event log は history / provenance query として分離する。

未実装:

- `wiki/log.md` を `## [YYYY-MM-DD HH:MM] op | summary` header ごとに仮想 log-entry record へ split する importer。
- `wiki/log/*.md` record-per-file 形式の importer。frontmatter `type: log-entry`, `date`, `op`, `pages`, `sources` を優先して読む。
- log entry id policy。候補: `source_path + timestamp + content_hash`。record-per-file なら path / frontmatter id を優先。
- log entry subject extraction。frontmatter `subjects` / `pages` があればそれを使い、無い既存 `log.md` では body 中の wikilink / touched file path から推定する。
- stale-log guard。log entry を返す時、同じ subject の later events を検出し、`superseded_by` / `later_events` として同梱する。
- log artifact の outgoing links を既定 content graph から除外しつつ、search / provenance query には残す。
- `read <page>` は current content / current projection、`grasp log` / `grasp history <page>` は event stream、という surface 分離。
- 人間向け `log.md` を record-per-file から生成する projection として扱う export / catalog surface。

## Local write and identity layer

v1 は read-only。local store への write / rename / transclude は未実装。

未実装:

- `write`: page 作成 / 更新と edge 自動更新。
- `rename`: stable id を保った rename。Scrapbox の参照書き換え / redirect stub の二択を避ける。
- `transclude`: line-id を使った行参照。
- aliases / page-id policy。page id を「いつ」「誰が」「どの意味判断で」振るか。
- stable line-id policy。v1 の `page.id:line-index` は positional locator であり、write / transclude / 長期引用用の安定 ID ではない。

補足: hosted Cosense に AI から書く用途は [[cosense-cli]] の `previewEdit` / `submitEdit` が担う。grasp の write 層は local-only store や非 Cosense ユーザ向けの別目的。

AI consumer 観点の要件（出典 [[ai-consumer-feedback-2026-06-23]] Tier 4 / decision [[why-not-scrapbox-clone]]）: AI はユーザに答える時、根拠をページ単位で引用する。将来 write/rename で title が動くと**過去セッションの引用が腐る**ため、`read --json` が **安定 page-id を返す**こと自体が consumer 価値。read 出力 field としては既済（`Page.to_summary()` が `id` を含む、[[grasp-v1-implemented]]）。**未済はこの page-id を rename を跨ぐ stable identity にする層**（上記 `page-id policy`）＝identity-without-name の consumer 側の本体はここ。

### stable line identity

2026-06-24 判断: `page.id:line-index` は **安定 line ID ではなく positional locator**。行を挿入すると後続行の locator が変わるため、write / transclude / 長期引用に使ってはいけない。current v1 surface の「line-id」は read-only snapshot 向けの historical naming として残るが、identity 層では `line.id` と `line_index` を分離する。

設計要件:

- `lines` は opaque stable `id` と current order `line_index` を別列で持つ。
- local write では既存 line を id で編集し、移動しても id を維持する。
- Cosense export / Markdown mirror など外部 source に line id が無い場合、初回 import 時に grasp が line id を mint し、store / identity journal に保持する。
- sync / reimport では旧 lines と新 lines を diff し、同一と判定できる line だけ id を引き継ぐ。挿入行は新 id、削除行は tombstone。
- split / merge / 重複行 / 大幅編集の曖昧一致は自動で同一視しない。新 id にするか、将来の明示操作に回す。
- content hash は本文編集で identity が変わるため不可。line index は挿入で identity が変わるため不可。**stable ID requires memory**。

schema 方向:

```text
lines(
  project,
  id,          -- opaque stable line id
  page_id,
  line_index,  -- current order only
  text,
  created,
  updated,
  user_id
)
line_tombstones(project, id, page_id, deleted_at, last_text?)
```

## Search and retrieval

未実装:

- vector search。
- FTS5 trigram hybrid による `search` 高速化。literal substring semantics を守るには [[fts5-trigram-search]] の通り `LIKE` fallback / post-filter が必要。
- backlink line の前後文脈窓。
- related ranking の重み調整と、大規模化した時の 2-hop cost 対策。

### search recall（AI consumer Tier 1 = 最優先, vector の前）

出典: [[ai-consumer-feedback-2026-06-23]] Tier 1。旧状では `search` は literal substring・単一行マッチで、`search "KJ法 表札"` が両語同一ページでも `(none)` を返す（silent false-negative）。AI は recall に依存し `(none)` の不在/不一致を区別できないため、これは retrieval を AI に食わせる最も危険な失敗モード（原理は [[ai-consumer-cost-and-trust]] 軸2）。

- **2026-06-23 22:36 実装済み（後に surface 変更）: page 単位の多語 AND**。空白区切り複数語を、同一行でなく同一ページに全語があれば返すようにした。2026-06-24 に暗黙挙動ではなく `--mode boolean --scope page` で明示する surface へ変更。
- **2026-06-24 00:56 実装済み: default literal + 明示 boolean**。空白区切りを暗黙 page AND にするのは「query を書けない人間向け」の interface で、英文 phrase を検索するには既定が入力文字列そのものの literal search である方が自然、という nishio 指摘を反映。`search` 既定は literal line substring に戻し、`--mode boolean` で AND/OR/NOT・括弧・quoted phrase・隣接 term の implicit AND、`--scope line|page` で評価単位を切り替える。旧 page AND は `--mode boolean --scope page "alpha beta"` で明示的に再現する。current facts は [[grasp-v1-implemented]]。
- **2026-06-23 23:10 一部実装済み: normalized fallback**。literal 0件時に NFKC query 正規化＋長音除去を SQLite `REPLACE` で試す。例: `ﾕｰｻﾞﾃｽﾄ` が `ユーザテスト` / `ユーザーテスト` 行に hit し、text では `[normalized]`、JSON では `match_mode: "normalized"` を返す。store schema は変えない。完全なかな/カナ変換の Python scan は 50k lines 以下の小規模 store のみに制限（nishio 規模では 20s 級になるため）。
- **未実装: 大規模 store での完全なかな/カナ・全半角本文正規化 index**。本文側を materialize した normalized column / FTS hybrid / trigram 等で持たない限り、完全な正規化 search は大規模 store で高コスト。
- 順序: **recall（boolean/page scope/正規化）を直してから** FTS5 速度最適化（recall と速度は別軸）。

### read の近傍 snippet 同梱（AI consumer Tier 2）

出典: [[ai-consumer-feedback-2026-06-23]] Tier 2。`read --related-snippets`（各 related ページの先頭 k 行 or 該当行を同梱）で hub 探索が 1 往復で済む。`export-ai --depth` が近いことをやっているので read 経路に snippet option を寄せる。round-trip を畳む原理は [[ai-consumer-cost-and-trust]] 軸1。

2026-06-23 23:42: `read --related-snippets` / `--related-snippet-lines N` は実装済み。default は先頭 5 行＝Cosense parity。existing page の related 2-hop と missing target の source pages の両方で、JSON は related/source item に `snippet_lines` / `snippet_truncated` を足し、text は related item 直下に行を表示する。current facts は [[grasp-v1-implemented]]。

未実装:

- 該当行モード（related/source ページの先頭ではなく、query に関係する backlink/source line 周辺を同梱）。

### high-level retrieval verb `gather`（設計テンションあり）

出典: [[ai-consumer-feedback-2026-06-23]] Tier 2。`gather "<query>" --budget <tokens>` = 問いから「最小ページ集合＋近傍」を token 予算内で返す retrieval orchestration を 1 verb で。ハブ（KJ法=151 backlinks）を読むと context が溢れるので、ランク上位から予算ぶん詰めて「残り N 件省略」と明示する。**テンション**: 太い verb は orchestration を CLI に寄せ、「薄い CLI / Skill がオーケストレーション」境界（[[delivery-cli-plus-skill]]）と緊張する。薄さを保つなら Skill 側に gather レシピを明文化、太くするなら verb。nishio 判断待ち。

2026-06-24 KJ法 hub audit（[[kj-link-hub-audit-2026-06-24]]）で、巨大 hub は単に backlinks が多いだけでなく、**リンク化を避けた bare mention が graph 外に大量にある**ことが分かった。`KJ法` は exact `[KJ法]` 151 links / 144 pages だが、literal `KJ法` は 681 pages / 2,333 lines / 2,765 occurrences、body bare mention は 490 pages / 1,777 lines / 2,156 occurrences。全部リンク化すると hub を悪化させるため、`gather` は「リンク済み backlinks」だけでなく、bare mention / co-link slice / omitted count を扱う必要がある。

未実装候補:

- `mentions <query>` or `search --mentions --link-gap`: literal mentions outside parsed internal-link spansを、page already has exact link / no exact link / no query-containing link target で分けて返す。目的は bulk link 化ではなく、link gap と意図的 non-link を見分けること。
- `co-links <query>` or `backlinks --co-links`: query を含む行で同時に出る internal links を rank し、巨大 hub の slice handle を出す。`KJ法` では `考える花火` / `こざね法` / `グループ編成` / `探検ネット` / `付箋` / `川喜田 二郎` / `発想法` / `表札*` が自然な絞り込み軸だった。
- `gather` は huge hub を token budget 内で扱う時、ranked backlink lines + representative co-link slices + bare mention samples + omitted counts を返す。

## Graph-native reasoning primitives（AI consumer Tier 3）

出典: [[ai-consumer-feedback-2026-06-23]] Tier 3。embeddings 無しでも純グラフ操作で「Markdown 束には出せない」価値が出る所。

- **`path <A> <B>`**（nishio: experimental, 試作可）: 最短リンク経路（＋経路上ページ）。「KJ法 と 弱い紐帯 はどう繋がる？」型の問いに直結。2026-06-23 nishio: 研究的には筋が良いが**実用上有用かは未知**、試しに作ってみる価値はある。
  - **グラフモデル（CLAUDE 回答 — nishio の「リンクとは？ ページがノード？」への返答, 2026-06-23）**: **ノード = pages ∪ unresolved targets**（page-only にしない）。grasp は既に page-less target を first-class node 扱い（read/backlinks/related/link-stats が効く）で、しかも概念ハブは **page-less の方が多い**（unresolved 上位）。page-only にすると最も中心的な connector を落とす。**エッジ = materialize 済み internal-link edges**（page P の行に `[T]` → P→T。storage は line-level、path では page 隣接に畳む。「どう繋がる」用途なので無向で扱う）。
  - **構造的含意**: unresolved target は incoming edge は持つが outgoing は無い（本文＝行が無い→出リンク無し）ので有向では sink。∴ path の**端点**か、無向では **hinge**（`A → T ← B` = A,B が概念 T を co-cite）にしかなれない。これは distance-2 の co-citation そのもので **`related` が既に計算している**。
  - **∴ `path` = `related` を 2-hop 超に一般化したもの**。page-less 概念ノードが自然な bridge（related の "via"）になる。試作は related のエッジ集合をそのまま再利用できる。
  - **go/no-go の実測基準（実用性懐疑への決着法）**: nishio のような密グラフでは大半の概念対が既に ≤2-hop（related が繋ぐ）。path の純増価値は「>2-hop 離れ かつ 共有近傍なし」の対だけ＝おそらく稀。**試作前にランダム概念対の hop 距離分布を測り**、大半が ≤2 なら marginal value は小さい → 工数は Tier-1 recall に回す。これで「作るか否か」を falsifiable に判定できる。
  - **2026-06-23 23:58 簡易実測（`~/.grasp/grasp.sqlite`, project `nishio`, schema v5）**: nodes = pages with edges 23322 + unresolved targets 42770 = 66092、undirected edges = 115075、最大連結成分 = 63490 nodes（96.06%）。ページ間距離の標本では「大半が ≤2-hop」は成立しなかった。uniform pages 300 pairs は ≤2 が 0.3%、≤4 が 9.0%、≤6 が 63.3%。top-degree pages 300 pairs でも ≤2 が 4.3%、≤3 が 30.0%、≤4 が 76.7%、≤6 が 99.3%。**含意: `related`（2-hop）外に意味のある接続は多く、`path --max-depth 4` の試作価値はある**。ただし uniform pages には日記・低次数 leaf が混ざるので、実用評価は user が問う概念ペア（高次数/タイトル明示）でさらに dogfood する。
  - **2026-06-24 00:05 初期実装済み**: `grasp path <A> <B> --max-depth 4 --limit 3` を追加。JSON は source/target node、paths[]、distance、nodes[]、edge example lines、truncated を返す。node は page / unresolved、edge は line-level materialized link を無向に畳む。dogfood: `path KJ法 弱い紐帯 --max-depth 4 --limit 1 --json` が 3-hop（KJ法 → Scrapbox情報整理術 → 情報と秩序 → 弱い紐帯）を返した。**残課題**: dense hub での performance（nishio store で約4-5s）、neighbor ranking、複数 shortest paths の出し方、実用的に意味のある経路かの継続 dogfood。
  - **2026-06-24 01:39 no-path recovery 実装済み**: 端点が resolve できるが bounded search で経路が見つからない時、`recovery_hints.path` に reason / next_max_depth / related / backlinks / link-stats を返す。negative-result contract は path no-path まで揃った。残課題は dense hub performance、neighbor ranking、複数 shortest paths の出し方、実用的に意味のある経路かの継続 dogfood。
- **backlinks の finer ranking**（nishio agree）: 既に `backlinks` は `source.views DESC, updated DESC, title, line_index` でランク済み（related と同じ primary signal、[[grasp-v1-implemented]]）。未済は **link 密度 / multiplicity / recency の重み付け**で「最も中心的な 20 件」精度を上げること。コア（views ランク）は済んでいる。
- ~~**近傍クラスタリング `--cluster`**~~ → **却下（nishio 2026-06-23）**。クラスタリングは **AI がやるべき**（AI の方が賢い）＝grasp は raw＋ranking を返し AI が sub-theme に畳む（feedback 著者自身の「default raw、AI にクラスタさせる」選好とも一致、原理 [[ai-consumer-cost-and-trust]] の fidelity 方針）。CLI 側でやるなら **embeddings 導入後に雑な embedding クラスタリング**を optional で足す程度。
  - 2026-06-24 修正: 「100+ リンクのハブは rare case」自体は希少でも、`KJ法` のように実在すると load-bearing。却下するのは CLI が cluster label を作ること。必要なのは AI が clustering できる raw material（counts / ranked rows / co-link slices / bare mention samples）を出す retrieval primitive。

## Negative-result contract（AI consumer 横断原理）

出典: [[ai-consumer-feedback-2026-06-23]] / 原理 [[ai-consumer-cost-and-trust]] 軸2。AI に retrieval を食わせるツールは、空結果を「情報」として返さねばならない（絶対的不在 vs マッチ失敗の区別）。現状 `read` / `link-stats` の zero-hit、`search` の空結果、`related` の空結果は `recovery_hints` を返す（実装済み, [[grasp-v1-implemented]]）。

2026-06-24 00:05: `related` 空結果への `recovery_hints` は実装済み。ヒントは command 文字列だけでなく **実データ**（近い title 候補・正規化で寄せた候補・部分一致 line）を含む。

未実装:

- empty result contract が今後追加する retrieval verb（例: `gather`）でも揃っているかの継続監査。

## Output token economy（AI consumer Tier 2）

出典: [[ai-consumer-feedback-2026-06-23]] Tier 2。default 出力は AI が読む前提なので token を削るほど AI の context が空き、多くを読める（原理 [[ai-consumer-cost-and-trust]] 軸1）。

実装済み:

- **2026-06-24 実装済み**: line-id のローカル別名。text 出力では `5928725cba093700118fa5b2:0` のような完全 ID を `P1:0` に畳み、先頭付近に `line-id aliases: P1=<page-id>` legend を出す。安定 ID が要る時は `--json`、text で完全 ID が必要な時は `--full-ids`。

却下（nishio 2026-06-23）:

- ~~**`--strip-decoration`**（icon / bare image URL 単独行を畳む）~~ → **却下**。decoration 行は noise ではない。`[nishio.icon]` は **その block の著者が誰か**を示す情報、bare image URL（gyazo 等）は **今の AI には読めないが人間には画像を提示**でき、将来の AI は画像も読む。∴ 畳んではいけない。token を削るのは line-id 別名側でやる。

## Sync freshness

`grasp sync` の basic upsert は実装済みだが、未実装が残る:

- hosted 側で削除された page の tombstone / local delete detection。
- rename detection。
- last-sync cursor の運用精度。

## Hosted Cosense acquisition without admin export

背景: `import --cosense <json>` は管理画面の JSON export を初回 seed にするため、user が管理者でない project では使えなかった。`sync` は full seed 済み project の freshness path なので、seed なしの project 取得とは意味を分ける。

2026-06-23 22:04: 初期 `grasp acquire <project-url>` を実装済み。`cosense searchFullText` による `--search` seed、`listPages --filter` による `--filter` seed、bounded `--full-list` seed、`readPage` + parsed links による `--from-page --depth` crawl、`--seed-file` に対応。対象 project namespace は append せず置き換える。`--project` 省略時は既存 full export project を誤って潰さないよう `<remote-project>:acquire` を default local namespace にする。store metadata に acquisition mode / coverage / seed / depth / limit / fetched / failed を保存し、`stats` に Acquisition 節を出す。partial corpus では backlinks / related / unresolved が取得済み subset 内の結果であることを CLI / Skill / README に明記済み。current facts は [[grasp-v1-implemented]]。

候補:

- **full list seed**: `cosense listPages <projectUrl> --sort ... --skip ...` で readable page metadata を pagination し、各 page を `readPage` で取得する。export に近いが、非 admin project で全ページ列挙できるか、rate limit / private page / permission error を要実測。
- **search seed**: `cosense searchFullText <projectUrl> <query>` で特定文字列を含む page を集める。例: キーワード、`[nishio.icon]`、`[/nishio/`。project 全体でなく「自分に関係する slice」を作る用途に向く。検索 query の literal 性、bracket / slash を含む検索挙動、hit 上限と pagination は要確認。
- **author/icon filter seed**: `cosense listPages --filter <name>` は本文中の `[name.icon]` と、その user が編集した page を返す。自分が管理者でない project の「自分が関わった page」取得に使える可能性がある。
- **link crawl seed**: 指定 page / title / URL から `readPage` し、本文の internal links / `projectLinks` を parse して BFS で辿る。`--depth`, `--limit`, `--include-cross-project`, `--same-project-only` のような境界が必要。孤立 page や seed から到達不能な page は拾えない。
- **manual seed list**: URL/title のリストを渡して `readPage` する。Slack や会話ログから抽出した page list、または user が明示した重要 page 群の取り込みに向く。

設計上の注意:

- これは full mirror とは限らないため、store metadata に acquisition mode / seed query / start pages / depth / limit / acquired_at / failed pages を残す。
- 部分取得 corpus 上の `backlinks` / `related` / `unresolved` は「取得済み subset 内」の結果であり、project 全体の事実として表示してはいけない。
- 同じ hosted project の複数 slice を同じ project namespace に混ぜると coverage の意味が曖昧になる。`--project` override で `project:slice` 相当の namespace に分けるか、coverage metadata を project 単位で合成する方針が必要。
- 権限は「その user / token が通常読める page だけ」。admin export の代替であって、非公開データを越権取得する経路ではない。

surface 候補:

- `grasp acquire <project-url> --full-list [--limit N]`（初期実装済み）
- `grasp acquire <project-url> --search <query> [--search <query> ...]`（初期実装済み）
- `grasp acquire <project-url> --filter <name> [--limit N]`（初期実装済み）
- `grasp acquire <project-url> --from-page <title-or-url> --depth N --limit N`（初期実装済み）
- `grasp acquire <project-url> --seed-file pages.txt`（初期実装済み）

Open Questions:

- `listPages` は非 admin readable project で全ページを pageinate できるか。
- `searchFullText` は `[nishio.icon]` や `[/nishio/` を literal に扱うか。検索上限を超えた場合の pagination / continuation はあるか。
- `readPage` の hosted line id を採用するか。現行方針は export/sync と同じく grasp 側で `page.id:line-index` を維持。
- partial corpus で `sync` する時、seed predicate 外の recently updated page を取り込むべきか、acquisition mode ごとの sync 動詞に分けるべきか。

## Packaging and distribution

未実装:

- PyPI 公開時の package 名確認。
- `pipx install` 前提の配布導線。
- user-level Skill symlink と package install の統合。
- Python 不可 agent 環境が現実化した場合の native binary 配布。
