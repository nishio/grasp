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

### metadata なし string line の import 対応（PR #2, merged）

2026-06-24: 外部 user（takker, [[takker-opencode-villagepump-test-2026-06-24]]）が `villagepump.json` を import した時、一部 line が `{text, created, updated, userId}` の dict でなく **plain string**（line metadata なし形式）で、importer が落ちた。`grasp/cosense.py` が `line_data.get("text", ...)` と dict 前提で line を読むため。takker 側の agent が local 修正し `https://github.com/nishio/grasp/pull/2`（takker99, branch `fix/string-lines-cosense-import`）として提出した。

- 2026-06-24 23:29 対応済み: PR #2 を review/merge。string line は `{text: <str>, created: None, updated: None, userId: None}` 相当に正規化して import し、リンク抽出対象にもする。回帰テストは `tests/test_cosense.py`。current facts は [[grasp-v1-implemented]]、version は `1.5.24`。
- 一般化: Cosense export の line shape は admin metadata-ON 以外でも来る。非 nishio export で parser 前提が崩れる例なので、他の入力 variant（page metadata 欠落等）も dogfood 候補。

## CLI and agent UX

2026-06-23 21:49: zero-hit recovery hints、`grasp read ... --json` 後置許容、help example drift、store missing diagnostics は実装済み。current facts は [[grasp-v1-implemented]]。

### long page navigation

現状: 長大ログ page の default `read` は CLI 一括出力として多すぎることがある。

2026-06-23 21:52 判断: P0 としては CLI に summarizer を持たせない。Claude Code / OpenCode のような harness は大きい shell output を truncate / 保存し、subagent は中間 tool output を親 conversation へ返さない。したがって長大ページの読解はまず Skill 側で subagent / Explore agent に委譲し、親には要約・根拠 page・line-id だけを返す。詳細は [[delivery-cli-plus-skill]]。

2026-06-24 01:58: `read --around-line <line-id> --line-context N` は実装済み。完全 `line_id` から所属ページを解決し、中心行の前後 N 行だけを返す。JSON は `line_window`、text は `line_window: P1:12 (lines A-B, context N)` を出す。local alias（`P1:12`）は実行内表示用なので入力には使わず、`--json` / `--full-ids` の完全 ID を使う。

2026-06-24 02:30: `search --context N` は実装済み。検索 semantics は変えず、各 hit に前後 N 行の `context_lines[]` と `context_window` を同梱する。text 出力でも hit 直下に bounded context を表示する。

2026-06-24 02:38: `peek --line-offset N` は実装済み。`--line-limit M` と組み合わせて本文行だけをページングし、JSON は `line_offset`, `lines_truncated_before`, `lines_truncated_after` を返す。

この系統は Skill/subagent 運用で不足が見えた時に足す bounded primitive。LLM 要約は CLI ではなく agent 層の責務。

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

2026-06-24 着手判断: write/identity 層に着手する。位置づけ・テスト方法・実装順序は [[write-layer-alpha-and-replay-test]]。要点: **当面 write は alpha testing（自己責任）**／**テストは此のリポジトリの過去 wiki 編集（git history）を grasp で再現できるかで検証**／**実装順序は最高リスク先行**＝下記の順を「楽な順」でなく「危険な順」に読む: ① stable identity + re-import diff（最高リスク）→ ② rename → ③ write → ④ transclude / come-from。作業は `feat/write-identity-alpha` worktree。

v1 は read-only。local store への write / rename / transclude は未実装。

設計要件（2026-06-24, come-from 対話、原理 [[come-from-declared-gather]]）: **リンクは1種類でない**。write/identity 層は2型を**別 first-class object** としてモデル化する（Cosense は両方を単一 `[X]` に束ねていたのが hub 膨張の根）:

- **felt-sense link** — 行キー・sparse・per-occurrence・**著者**の retrieval 意図（edge）。下記 stable line-id 層に乗るのはこちら。
- **come-from link** — 用語キー・1宣言・全出現・**読者**ケア（standing rule）。term が動けば追従する。line-id ではなく term identity に紐づく。

両者は identity も lifecycle も別。`write` / `rename` の edge 自動更新も、edge（felt-sense）と term rule（come-from）で別経路になる。

未実装:

- `write`: page 作成 / 更新と edge 自動更新。
- `rename`: stable id を保った rename。Scrapbox の参照書き換え / redirect stub の二択を避ける。
- `transclude`: line-id を使った行参照。
- aliases / page-id policy。page id を「いつ」「誰が」「どの意味判断で」振るか。
- stable line-id policy。v1 の `page.id:line-index` は positional locator であり、write / transclude / 長期引用用の安定 ID ではない。

補足: hosted Cosense に AI から書く用途は [[cosense-cli]] の `previewEdit` / `submitEdit` が担う。grasp の write 層は local-only store や非 Cosense ユーザ向けの別目的。

AI consumer 観点の要件（出典 [[ai-consumer-feedback-2026-06-23]] Tier 4 / decision [[why-not-scrapbox-clone]]）: AI はユーザに答える時、根拠をページ単位で引用する。将来 write/rename で title が動くと**過去セッションの引用が腐る**ため、`read --json` が **安定 page-id を返す**こと自体が consumer 価値。read 出力 field としては既済（`Page.to_summary()` が `id` を含む、[[grasp-v1-implemented]]）。**未済はこの page-id を rename を跨ぐ stable identity にする層**（上記 `page-id policy`）＝identity-without-name の consumer 側の本体はここ。

### typed / directional link（デライトの引き入れ＝前景後景型）

2026-06-24（nishio 指摘、原理は [[cosense-delite-howm-synthesis]]）: デライトの **引き入れ**（1輪郭を複数の親に入れられる多重所属）は、無型の関連リンクでなく「**前景（親）/後景（子）**」という向き付きの包含関係が乗ったリンク＝ **typed link** とみなせる。親 llm-wiki `型付きリンク` の「A. 構造型（contains / part_of の向き付き）」の具体例。

grasp は現状リンクが**無型**（Cosense と同じく全 predicate が related）。write/identity 層でリンクを first-class object 化する時、上記 felt-sense / come-from の2型に加えて「**型（特に向き付き構造型）を持たせるか**」が設計軸として立つ。引き入れがその最初の具体例。

未実装 / 論点:

- リンクに型（向き付き構造型 contains / part_of を最小に）を持たせるか。型は felt-sense / come-from とは直交する属性（どちらの型のリンクにも型は乗りうる）。
- 向き（前景/後景）と grasp の無向グラフの両立。`related` / `path` は「どう繋がる」用途で無向に畳む（[[grasp-v1-implemented]]）。型付き構造リンクを入れても、retrieval 用には無向 projection を別に保つ二層が要る。
- 型付けを著者宣言にするか、AI ingest 時に自動推定するか。親 llm-wiki `型付きリンク` の運用原則「最初は無印、重要になったら型」と、型語彙を増やしすぎない（最小8動詞）戒め。grasp の「整理を runtime / AI に逃がす」方針なら、型推定は AI 側に寄せるのが筋。
- 多重所属（多対多リンク）自体は grasp が既に持つ。デライトが足しているのは所属に**遠近＝前景/後景の順序**を与える点。これを edge 属性として持つか、`read` 出力でどう見せ分けるか。

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

2026-06-24 12:52: 該当行モード `--related-snippet-mode edge` は実装済み。related/source page の先頭ではなく、related/source item を導いたリンク行を中心に `snippet_lines` / `snippet_window` を返す。既定 mode は従来通り `lead`。

### high-level retrieval verb `gather`（設計テンションあり）

出典: [[ai-consumer-feedback-2026-06-23]] Tier 2。`gather "<query>" --budget <tokens>` = 問いから「最小ページ集合＋近傍」を token 予算内で返す retrieval orchestration を 1 verb で。ハブ（KJ法=151 backlinks）を読むと context が溢れるので、ランク上位から予算ぶん詰めて「残り N 件省略」と明示する。**テンション**: 太い verb は orchestration を CLI に寄せ、「薄い CLI / Skill がオーケストレーション」境界（[[delivery-cli-plus-skill]]）と緊張する。薄さを保つなら Skill 側に gather レシピを明文化、太くするなら verb。nishio 判断待ち。

2026-06-24 KJ法 hub audit（[[kj-link-hub-audit-2026-06-24]]）で、巨大 hub は単に backlinks が多いだけでなく、**リンク化を避けた bare mention が graph 外に大量にある**ことが分かった。`KJ法` は exact `[KJ法]` 151 links / 144 pages だが、literal `KJ法` は 681 pages / 2,333 lines / 2,765 occurrences、body bare mention は 490 pages / 1,777 lines / 2,156 occurrences。全部リンク化すると hub を悪化させるため、`gather` は「リンク済み backlinks」だけでなく、bare mention / co-link slice / omitted count を扱う必要がある。

2026-06-24 追加判断: 改善の成功条件は「`[KJ法]` backlinks が増える」ことではなく、`KJ法` が **root link + 用途別 slice handle** に分岐すること。`[KJ法]` は KJ法そのもの・原理・全体像に残し、通常言及は `表札づくり` / `グループ編成` / `考える花火` / `Kozaneba` / `探検ネット` / `AIにKJ法を教える` などの narrower handle へ逃がす。agent が `[KJ法]` hub 全体を読まず、最初に 5-10 個の use cluster / slice を見て必要な slice だけ読める状態を success とする。

2026-06-24 12:32 初期実装済み:

- `mentions <query>`: literal query の出現を探し、parsed internal-link span 外の bare mention を既定で返す。summary は total / bare / linked occurrence、bare line/page、`exact-link-page` / `query-link-page` / `unlinked-page` count を返す。`--unlinked` で page に query-containing link target が無い `unlinked-page` だけを返す。目的は bulk link 化ではなく link gap / intentional non-link / come-from 候補の監査。
- `co-links <query>`: query を含む行で同時に出る internal links を target ごとに rank し、line_count / source_page_count / examples を返す。巨大 hub の slice handle を AI が読む材料にする。
- `gather <query>`: link stats + bare mention summary + representative mentions + co-link slices + backlinks + next recipes を bounded bundle として返す。`--budget` は row limit selector であり厳密 token packing ではない。huge hub では bulk-linking を避ける banner を返す。

2026-06-24 16:03 追加実装済み:

- `mentions` summary に `come_from_candidate` を追加。bare occurrence/page spread、unlinked-page、query shape の uncommon signal から初期 heuristic score / threshold / signals / rationale を返す。これは候補 surface であり、多義語や AI 作ページ判定を確定しない。
- `gather` に `returned_counts` / `total_counts` / `omitted_counts` と `row_count_basis` を追加。counts は mentions=bare mention lines、co_links=ranked co-link targets、backlinks=incoming link rows の row 単位で、token omitted count ではない。
- `co-links` に `target_relation` と `--rank slice|raw` を追加。既定 `slice` は query-containing target title を後ろへ回し、narrower `slice-handle` を先に出す。`raw` は従来の count order。

残課題:

- `mentions` は現状 literal query。完全なかな/カナ・全半角正規化 index、word boundary、多義語 disambiguation は未実装。
- 2026-06-24 12:56: `mentions --unlinked` は実装済み。既定 bare-only は維持し、`--unlinked` では page に query-containing link target が無い bare mention 行だけを返す。
- page-level 3分類は `exact-link-page` / `query-link-page` / `unlinked-page` まで。come-from 昇格候補の初期 heuristic scoring は実装済みだが、AI 作 default 裸 / 意図的 non-link / link gap の高次分類、実データでの閾値調整、多義語の一意性判定は未実装。
- `co-links` の broad query-containing title と use-slice handle の初期分類 / rank surface は実装済み。残るのは query-containing でも有用な narrow page（例: `AIにKJ法を教える`）と bibliographic/session title の finer classification、weighting 調整、実データ dogfood。
- `gather --budget` は厳密 token packing / omitted token count ではない。row 単位 omitted counts は実装済みだが、token budget 内への packing、omitted token estimate、代表サンプル選択の精密化は未実装。
- AI clustering handoff: CLI は固定 cluster label を確定しないが、AI が `表札` / `ツール` / `AI応用` / `講義資料` などへ仮分類できるだけの bounded rows と sample provenance を返す、という方針は継続。

### use-case report composition（icon/person history）

2026-06-24 `villagepump` `[nishio.icon]` 抽出から、巨大抽出系の「いい感じ」な outcome には report composition 層が必要だと分かった（原理は [[use-case-experiment-as-outcome-story]]）。raw hits 6,488 paragraphs は到達としては成功だが、そのままでは読めない。agent が `公開共同日記から見る grasp 前史 30 scene` のような bounded narrative artifact へ組むには、CLI / acquisition 側が次を返すとよい:

- icon/person slice の取得条件: project, diary page rule, date range, icon/user handle, coverage, failures。
- `icon_hit_kind`: author marker / sentence signed at end / prefix speaker / reaction icon list / mention-of-person / other。最低限、`[nishio.icon]さん` 型の言及と reaction-only rows を本文発話から分ける。
- representative candidate bundle: year/month counts, top linked targets, keyword/theme counts, longest blocks, high-signal examples with source page title, hosted line id, line index, snippet。
- report handoff contract: CLI は narrative を確定しない。agent/report layer がユーザ言語で timeline・themes・代表 scene・caveat・source links を書く。

仮 surface:

```text
grasp acquire https://scrapbox.io/villagepump/ --diary --icon nishio --until 2026-06-24
grasp report icon-history nishio --themes ai,scrapbox,community --top 30
```

surface 名は未決。重要なのは、raw dump ではなく **bounded candidate bundle + agent-authored report** を標準 workflow にすること。

2026-06-24（come-from / link overloading、親 llm-wiki 設計対話、原理は [[come-from-declared-gather]]）:

巨大 hub が膨れる *why* を言語化できた。[[kj-link-hub-audit-2026-06-24]] の exact 144 → bare 490 は「リンク漏れ」ではなく**判断レベルと帰結レベルのミスマッチ**: Cosense のリンクは per-occurrence の局所判断だが双方向で大域帰結（hub）を創発する。誰も「KJ法 を 490-backlink hub にしよう」と決めていないのに、各ページの親切な `[KJ法]` の副作用として hub が出来る。∴ 対処は「もっとリンク」でも「リンクを消す」でもなく、**判断を帰結と同じ用語-大域レベルに上げる**こと（= come-from）。`gather` の banner / rationale にこの一文を入れると「リンク化を増やす方向が誤り」を原理で言える。

- `mentions` の3分類化: 現状の「link gap か 意図的 non-link か」に第3の源 **(c) AI 作ページの default 裸**を足す。KJ法 audit トップの bare page `🌀KJ法`（266 occ）は AI 作で (c)。書き手が AI 化するほど (c) が支配的になり、裸言及は著者意図と無関係に増える。出力は「埋めるべき gap」だけでなく **come-from 昇格候補（uncommon × 頻度 × 一意）** を別枠で scoring 付きで返す。目的は bulk link 化でなく「1宣言で畳めるもの」の surface。
- **come-from declare 層**（新規）: 用語を come-from term として標す per-term standing rule。`mentions <query>` の ad-hoc query を declarative に固定したもの。store 表現は専用テーブル or 宛先ページ frontmatter `come_from: [...]`（後者は Markdown mirror と親和）。
- **come-from render 層**（新規）: Markdown mirror / 公開 view を materialize する時、come-from term の裸出現を自動リンク化。store（裸）と view（リンク済み）の分離を保つ（[[markdown-obsidian-indexed-mirror]] の projection 方針に乗る）。authoring（裸＋宣言）と rendered（自動リンク）の分離が、著者を over-link させずに読者ケアを届ける機構。
- 安全域＝必要域: come-from は文字列マッチで gather するので多義語は過剰収集するが、読者ケアが要る uncommon 語 ≈ 一意なので安全。昇格候補抽出は「uncommon さ × 頻度 × 一意性」で機械化できる。read 側（仮想出現一覧）は nishio 2022 の howm 考察そのもので grasp `mentions` が既に体現している。

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

## Cross-project graph を first-class edge に + whole-store retrieval（v6）

2026-06-24 決定（[[whole-store-graph-and-cross-project-edges]]）: 互換性を捨て、store を v6 に bump して理想形に作り直す。store = 外部 source から再生成可能な projection なので schema bump + 再 import は安全（`recover_store_from_import_cache` 機構が既存）。現状の parse-on-read `cross_project_refs`（`LIKE '%[/%'` 全スキャン + 毎回 re-parse/re-classify、edge にならない）を置換する。

実装項目:

- **cross-project link を materialize**: `edges` に `target_project` / `link_kind`（internal / cross-semantic / cross-icon / cross-root）を追加。`source_project` へ rename。`CrossProjectLink`（`raw/project/title/target_class`）をそのまま流す。`raw` 保存で slash-in-title 再解決可能に。
- **解決と unresolved 再構築**: `[/P/T]` を (P, norm(T)) に解決。存在チェックを target_project の pages に対して行い、`unresolved_targets` を `(target_project, target_norm)` で集計。materialized page 0 の namespace も unresolved の値に取れる。
- **whole-store default retrieval**: `_require_project` の「複数 project で error」を削除。`search` / `read` / `backlinks` / `related` / `path` / `unresolved` / `mentions` / `co-links` / `gather` は default で全 project から、`--project` で絞る。結果は project ラベル付き。`import` / `sync` / `acquire` は project-targeted のまま。
- **read 多義の disambiguation**: 同名 page が複数 namespace にある時、error せず全候補を project ラベル + summary で返し `--project` / page-id で絞らせる。
- **node 状態 = page 単位の materialized / referenced-only**: project は namespace。「未取得 project」は categorical でなく coverage（materialized page 数）の派生量。acquire = referenced-only node の materialize。`unresolved`(whole-store) が「参照済みだが未取得の知識圏」を link_count 順で出し、acquire の seed bibliography になる（[[cross-project-reference-acquire-2026-06-24]] dogfood の手作業を primitive 化）。
- **出力契約**: discover-broad-filter-post-hoc。relevance で pre-filter せず target_project / link_kind / scope ラベル付きで surface、絞りは post-hoc flag、出力量は rank + omitted-count で bound、性能は bound で対処し hide しない。現 `cross_project_refs` の `--semantic-only` / `--exclude-icons` / `--include-self` は「pre-filter」から「surface 済み集合への post-hoc filter」に位置づけ直す。
- **history**: store format / materialized index semantics が変わるため [[history]] の `x` を進める（再 import 要）。

未決（decision の Open Questions）: referenced-only namespace の coverage rollup surface 形 / slash-in-title 確定規則の実データ検証 / dense graph での whole-store related/path bound / **同名 bare 赤リンクの cross-project 統合**（[[multi-project-store]] tentative Update との diverge、nishio 判断待ち）。

## Hosted Cosense acquisition without admin export

背景: `import --cosense <json>` は管理画面の JSON export を初回 seed にするため、user が管理者でない project では使えなかった。`sync` は full seed 済み project の freshness path なので、seed なしの project 取得とは意味を分ける。

2026-06-23 22:04: 初期 `grasp acquire <project-url>` を実装済み。`cosense searchFullText` による `--search` seed、`listPages --filter` による `--filter` seed、bounded `--full-list` seed、`readPage` + parsed links による `--from-page --depth` crawl、`--seed-file` に対応。対象 project namespace は append せず置き換える。`--project` 省略時は既存 full export project を誤って潰さないよう `<remote-project>:acquire` を default local namespace にする。store metadata に acquisition mode / coverage / seed / depth / limit / fetched / failed を保存し、`stats` に Acquisition 節を出す。partial corpus では backlinks / related / unresolved が取得済み subset 内の結果であることを CLI / Skill / README に明記済み。current facts は [[grasp-v1-implemented]]。

2026-06-24 dogfood: `/nishio` の `[/` cross-project refs から semantic refs 上位 project を `--seed-file` acquire した（[[cross-project-reference-acquire-2026-06-24]]）。観測:

- raw `[/` refs は `.icon` と project-root refs が多く、semantic seed 生成前に target class 分類が必要。
- dogfood 時点の `grasp search` は line text retrieval なので、`--mode boolean` の `NOT .icon` は line-level workaround に過ぎなかった。同じ行の semantic link まで落とし、root refs は残り、複数 link target の個別分類はできない。この gap は `cross-project-refs` の target-aware extraction として実装した。
- `cosense` binary への絶対パスを `--cosense-command` に渡しても、shebang が `#!/usr/bin/env node` なので PATH に対応する `node` が無いと exit 127 になる。この fetch-stage case は `acquire` diagnostics の `command-env` として実装済み。残るのは search/list seed discovery phase で同じ環境診断を返すこと。
- `acquire` は全 candidate が `failed_pages` に落ちても exit 0 で partial acquisition result を返す。機械処理には一貫しているため、fetch-stage は `diagnostic.type=all_failed` / `failed_pages[].error_class` で警告する実装にした。残る問いは、この exit 0 方針を維持するか。

2026-06-24 dogfood: public `https://scrapbox.io/villagepump/` の日記ページから `[nishio.icon]` 付き段落を抽出する use case で、実行環境に `cosense` binary がなく `grasp acquire` を使えなかった。Scrapbox public API 自体は `curl https://scrapbox.io/api/pages/villagepump?...` と `curl https://scrapbox.io/api/pages/villagepump/<title>` で読めたため、read-only public project には `cosense-cli` 依存なしの direct API fallback があると agent 実験の摩擦が下がる。副観測: `search/query?q=[nishio.icon]` は 100 件固定で `skip` が効かず、網羅抽出には `pages?sort=title` で date title を列挙して各 page を読む必要があった。

2026-06-24 追加実装済み:

- `cross-project-refs`: 保存済み行テキストから Cosense shorthand `[/project/page]` を parsed link target として抽出し、semantic / icon / project-root / self-project に分類して project 別に rank する。`--semantic-only` は `.icon` / project-root / self-project を除いて external semantic page refs だけを返す。これは `search "[/"` の line-level workaround ではなく、seed bibliography の前処理 surface。
- `cross-project-refs --seed-dir <folder>`: returned project ごとに semantic target title の seed file を書き、`grasp --project <project>:semantic acquire <url> --seed-file <file> --limit N` の runnable command を `acquire_recipe` として返す。`--seed-limit` で project ごとの seed title 数を制御する。
- `acquire` diagnostics: fetch failures に `failed_pages[].error_class` を付け、全 candidate fetch 失敗時は `diagnostic.type=all_failed` / `severity=warning` / `next_actions[]` を返す。`cosense` は見つかるが shebang の `env node` が失敗するケースは `command-env` に分類する。
- `cross-project-acquire`: `cross-project-refs --semantic-only` の seed titles から複数 target project を `<project>:semantic` namespace に順次 partial acquire し、project ごとの bounded summary を返す。`--dry-run` で plan のみ確認できる。取得後 summary には `reciprocal_refs` と `top_internal_links` を同梱する。
- `acquire` reuse: acquisition criteria fingerprint / candidate updated range / page manifest を metadata に保存し、同じ criteria の再実行時に hosted metadata の `updated` が一致するページは local store から再利用する。JSON/text は `remote_fetched` / `reused` / `same_criteria_as_previous` を返す。updated metadata が無い seed は stale 回避のため従来通り読む。

残課題:

- `cross-project-acquire` の実データ dogfood、project ranking / target ranking の weighting 調整、取得後 summary の signal 改善（reciprocal refs / top internal links の ranking、cluster handoff など）。
- `cosense` / `node` 環境診断の seed discovery phase（`searchFullText` / `listPages`）への拡張。fetch phase は実装済み。
- direct public API fallback。

候補:

- **full list seed**: `cosense listPages <projectUrl> --sort ... --skip ...` で readable page metadata を pagination し、各 page を `readPage` で取得する。export に近いが、非 admin project で全ページ列挙できるか、rate limit / private page / permission error を要実測。
- **search seed**: `cosense searchFullText <projectUrl> <query>` で特定文字列を含む page を集める。例: キーワード、`[nishio.icon]`、`[/nishio/`。project 全体でなく「自分に関係する slice」を作る用途に向く。検索 query の literal 性、bracket / slash を含む検索挙動、hit 上限と pagination は要確認。
- **author/icon filter seed**: `cosense listPages --filter <name>` は本文中の `[name.icon]` と、その user が編集した page を返す。自分が管理者でない project の「自分が関わった page」取得に使える可能性がある。
- **link crawl seed**: 指定 page / title / URL から `readPage` し、本文の internal links / `projectLinks` を parse して BFS で辿る。`--depth`, `--limit`, `--include-cross-project`, `--same-project-only` のような境界が必要。孤立 page や seed から到達不能な page は拾えない。
- **manual seed list**: URL/title のリストを渡して `readPage` する。Slack や会話ログから抽出した page list、または user が明示した重要 page 群の取り込みに向く。
- **direct public API fallback**: `cosense` binary / Node が無い環境でも、public project は Scrapbox API で page list / page body を読める。公式 CLI の挙動差を吸収する adapter として実装するなら、auth が必要な project では従来通り `cosense-cli` に戻す。
- **parsed cross-project refs seed**: `cross-project-refs` の抽出・分類、seed-file generation、acquire command bundle、複数 project の一括 acquire orchestration は実装済み。残るのは実データ dogfood と取得後 summary の richer report 化。

設計上の注意:

- これは full mirror とは限らないため、store metadata に acquisition mode / seed query / start pages / depth / limit / acquired_at / failed pages を残す。実装済み: criteria fingerprint / candidate updated range / page manifest も保存する。
- 部分取得 corpus 上の `backlinks` / `related` / `unresolved` は「取得済み subset 内」の結果であり、project 全体の事実として表示してはいけない。
- 同じ hosted project の複数 slice を同じ project namespace に混ぜると coverage の意味が曖昧になる。`--project` override で `project:slice` 相当の namespace に分けるか、coverage metadata を project 単位で合成する方針が必要。
- 権限は「その user / token が通常読める page だけ」。admin export の代替であって、非公開データを越権取得する経路ではない。

surface 候補:

- `grasp acquire <project-url> --full-list [--limit N]`（初期実装済み）
- `grasp acquire <project-url> --search <query> [--search <query> ...]`（初期実装済み）
- `grasp acquire <project-url> --filter <name> [--limit N]`（初期実装済み）
- `grasp acquire <project-url> --from-page <title-or-url> --depth N --limit N`（初期実装済み）
- `grasp acquire <project-url> --seed-file pages.txt`（初期実装済み）
- `grasp cross-project-refs [--semantic-only] [--exclude-icons] [--seed-dir <folder>] [--json]`（抽出・分類・seed file / acquire command 生成は実装済み）
- `grasp cross-project-acquire [--limit N] [--seed-limit N] [--dry-run] [--json]`（semantic refs から複数 project を `<project>:semantic` へ取得する orchestration は実装済み）

Open Questions:

- `listPages` は非 admin readable project で全ページを pageinate できるか。
- `searchFullText` は `[nishio.icon]` や `[/nishio/` を literal に扱うか。検索上限を超えた場合の pagination / continuation はあるか。
- parsed link extraction を `search` ではなく `cross-project-refs` の別 verb とした。seed-file / acquire command 生成と実 acquire orchestration、reciprocal refs / top internal links summary は接続済み。残る問いは、取得後の richer summary（cluster handoff / representative theme bundle）を CLI がどこまで担うか。
- direct public API fallback を入れる場合、Scrapbox API と cosense-cli の metadata / auth / rate limit / search semantics の差をどこまで surface に出すか。
- `readPage` の hosted line id を採用するか。現行方針は export/sync と同じく grasp 側で `page.id:line-index` を維持。
- partial corpus で `sync` する時、seed predicate 外の recently updated page を取り込むべきか、acquisition mode ごとの sync 動詞に分けるべきか。

## Packaging and distribution

未実装:

- PyPI 公開時の package 名確認。
- `pipx install` 前提の配布導線。
- user-level Skill symlink と package install の統合。
- Python 不可 agent 環境が現実化した場合の native binary 配布。
