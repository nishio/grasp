---
name: grasp
description: >-
  ユーザが指定した Scrapbox/Cosense JSON export、または既に import 済みの grasp local store を
  CLI から調べるスキル。ページ本文だけでなく、行レベル逆リンク、2-hop related、未解決 target を
  近傍同梱で読む。ユーザが「この JSON を読んで」「自分の Cosense export から探して」
  「この概念への言及はどこか」「関連ページは何か」「本文のない概念ハブを見たい」などと依頼した時に使う。
---

# grasp Skill 手順書

`grasp` CLI で、ユーザが指定した Scrapbox/Cosense JSON export から作った local グラフストアを読む。source JSON / hosted project に対しては **read-only**。`import` は SQLite index を作るだけで、元 JSON は変更しない。Markdown-backed project だけは authoring fast path として `append-section` / `append-log` / `write-page` / `rename-page` の alpha write surface があり、明示的な file-back / dogfood 目的で使う。

各 verb の引数・戻り値スキーマ・例は、使う直前に **`grasp <cmd> --help`** を読む（このファイルには列挙しない）。

## 最初にデータソースを確定する

- ユーザが JSON export path を指定している場合は、その JSON を使う。**特定ユーザ名・固定パス・固定 project URL を仮定しない**。
- 既に store がある前提の依頼なら `grasp stats` で store の状態を確認してから読む。
- `grasp stats` の `project_count` が 2 以上なら、ユーザの意図または問いの文脈から対象 project を選び、以後は `--project <name>`（または `$GRASP_PROJECT`）を付ける。project を推測できない時は確認する。
- 一回限りの JSON 調査では、既定 store を上書きしないよう task-local store を使う:

  ```bash
  grasp --store /tmp/grasp-task.sqlite import --cosense "/path/to/export.json"
  grasp --store /tmp/grasp-task.sqlite read "ページタイトル"
  ```

- ユーザが「自分の通常 store に取り込んでよい」と分かる場合だけ、既定 store へ import する:

  ```bash
  grasp import --cosense "/path/to/export.json"
  grasp read "ページタイトル"
  ```

- store が無い、または指定 JSON が見つからない場合は、勝手な別データで代用せず、JSON export path か store path を確認する。
- ユーザが Markdown folder、またはこの repo の `wiki/` を調べたい場合は、必要に応じて task-local store へ read-only mirror として index する:

  ```bash
  grasp --store /tmp/grasp-wiki.sqlite import --markdown wiki --project grasp-wiki
  grasp --store /tmp/grasp-wiki.sqlite --project grasp-wiki read grasp-v1-implemented
  ```

  最小 Markdown mirror は frontmatter `title` / `id` / `aliases` / `tags` を読み、title が無い場合は first H1、さらに無ければ file stem を title にする。`[[...]]` と `#tag` を grasp 内 edge にする。duplicate title / alias は import 全体を止めず、`read <handle>` の ambiguity 候補として返る。`backlinks <ambiguous handle>` は handle 自体への incoming lines を主に返し、候補 page ごとの確定 backlinks も分けて返す。`related <ambiguous handle>` は handle 自体への source pages と候補 page ごとの related を分けて返す。`ambiguities` は store 全体または selected project の曖昧 handle を一覧する。duplicate frontmatter `id` は identity 衝突なので error。バックティックのプレーン名（親 llm-wiki への cross-wiki 参照）は edge にしない。既存 Markdown folder へは書き戻さない。重い raw/generated directory を避けたい時は `--markdown-exclude-dir raw` のように directory basename を指定する。再 import は content-only 変更なら差分更新し、title / id / aliases / graph role / exclude dirs / file set が変わった時は安全に full rebuild する。`index.md` / `log.md` など navigation/log artifact は本文検索対象に残しつつ、既定 content graph では outgoing edges を除外する。Obsidian block refs はまだ未実装。
- ユーザが `wikis.yaml` のような Markdown wiki registry 全体を読みたい場合は、task-local store へ `import-forest` で一括 index する。各 entry は project `<name>` として `<path>/<wiki-dir>` を import し、entry ごとの missing/failure/skipped diagnostics と forest-level `ambiguities` summary を返す:

  ```bash
  grasp --store /tmp/grasp-forest.sqlite import-forest /path/to/wikis.yaml --markdown-exclude-dir raw
  ```

## grasp とはどういう物か

- Scrapbox/Cosense の JSON export、または Markdown folder mirror を取り込み、SQLite graph store にしたもの。
- ページは**行ベース**。Cosense では `[ページ名]`（単角括弧）と `#tag`、Markdown mirror では `[[ページ名]]` と `#tag` を edge にする。read 出力は元の行テキストのまま。
- 中核は **read=近傍同梱**: `grasp read <title>` 一発で、本文 ＋ **行レベル逆リンク** ＋ **related（2-hop）** ＋ **そのページから出る未解決 target** が一緒に返る。`--related-snippets` を付けると related/source ページの先頭行を同梱でき、`--related-snippet-mode edge` なら related/source item を導いたリンク行を同梱できる。
- オフライン・即時（store があれば各コマンド sub-second）。

### グラフの読み解き方（Tips）

- キーワード検索だけに頼らず、**関連リスト・逆リンクを眺めて辿る**。単独ページでは見えない文脈が浮かぶ。
- 被リンク数（read の `links_to_this` / `link-stats`）が大きいページや target は、実質**カテゴリ的ハブ**として機能している。
- **本文の無い（page なし）観念的タイトルでも、意味は他ページの文脈に宿る**。`read`/`backlinks`/`related` は page が無い target でも、それを参照している source pages を返す。「本文なし＝無意味」ではない。
  - 例: 本文ページが無い target でも、多数のページから参照されていれば `grasp read <target>` で参照側の文脈を読める。

## こういう時はこうする

### タイトルが分かっている / そのページを軸に調べたい
→ `grasp read <title>`。本文＋逆リンク＋related＋未解決を一括取得。これが基本。related の見出しだけでは足りず冒頭本文も同時に見たい時は `--related-snippets`（既定 5 行、`--related-snippet-lines N` で調整）。related/source item がなぜ出たかを見たい時は `--related-snippet-mode edge` を足して根拠リンク行を同梱する。逆リンクや related が切れていたら `--backlinks-limit` 等で広げる。

### テーマ・問いから探す（タイトル未確定）
→ `grasp search <query>` で**本文行**を検索（行レベル hit）し、良さそうな `source_title` を `grasp read` で開く。タイトルの当たりが付くなら `grasp suggest <partial>`（タイトル補完）。`suggest` の既定は fuzzy で、長文タイトルに対し空白区切り断片や詰めた文字順序でも候補を返す。厳密な部分一致だけにしたい時は `--mode substring`。
- `search` の既定は、空白も含めて入力文字列そのものを探す literal line substring 検索。英文 phrase や空白入り query はまずこの既定でよい。
- 複数語を論理条件として探したい時は `--mode boolean` を付ける。AND / OR / NOT、括弧、quoted phrase、隣接 term の implicit AND が使える。例: `grasp search "KJ法 AND 表札" --mode boolean --scope page`。
- `--scope line` は1行内で式を評価し、`--scope page` は同一ページ内の全行で式を評価してから該当行を返す。旧「空白区切り page AND」は `--mode boolean --scope page "alpha beta"` で明示的に再現する。
- 該当行の前後も必要なら `--context N` を付ける。JSON では各 hit に `context_lines[]` と `context_window` が入り、text では hit 直下に周辺行が出る。
- literal で0件の時は、NFKC と長音ゆれ（例: `ﾕｰｻﾞﾃｽﾄ` / `ユーザーテスト` / `ユーザテスト`）を緩く合わせる normalized fallback が走る。text 出力では該当行に `[normalized]` が付き、JSON では `match_mode: "normalized"` になる。大規模 store では完全なかな/カナ変換 scan は行わない。normalized fallback は literal mode 用。

### 長大ページ・ログページを読む
→ 親 conversation に長い `read` 出力を直接持ち込まない。まず探索用 subagent / Explore agent に任せ、subagent 側で `search` / `peek` / limit 付き `read` を使って読む。
- 親に返すのは、結論・根拠ページ・該当 `line_id`・必要な短い引用/要約だけにする。中間の大量 stdout、長大本文、網羅的検索結果は subagent context に閉じ込める。
- CLI 側は要約しない。grasp は LLM 依存の summarizer ではなく、行 ID 付きの deterministic graph reader。要約と取捨選択は Skill / subagent の責務。
- 長大ページを直接開く必要がある時も、先に `grasp search <query> --context 2 --json` で hit line と短い周辺を読む。さらに広げる必要がある時だけ、完全 `line_id` を使って `grasp read --around-line <line-id> --line-context 5` で追加の周辺行を読む。ページ本文を順に見るだけなら `grasp peek <title> --line-offset N --line-limit M` でページングする。ページ先頭だけで足りる時は `grasp read <title> --line-limit <N>` で範囲を絞る。親へ戻す時は再アクセスできる `source_title` と完全 `line_id` を残す。

### 「この概念にどこで言及したか」
→ `grasp backlinks <title>`（`(source_title, line-id, 行テキスト)`）。`read` の Backlinks 節と同じものを単体で。page が無い概念にも効く。

### 「この概念と関連するページ」
→ `grasp related <title>`。existing page なら 2-hop ページ、page なし target ならそれを参照する source pages。

### 「この概念とこの概念はどう繋がるか」
→ `grasp path <A> <B> --max-depth 4`。pages と page なし target をどちらも node として扱い、materialized internal links を無向 edge として短い経路を返す。経路の edge には根拠 line が付くので、bridge が意味的に妥当かを確認する。密な hub では展開が大きくなるため、まず `--max-depth 4 --limit 1` で見る。端点は見つかったが経路が無い時も `recovery_hints.path` に次に試す depth、related、backlinks、link-stats が入るので、単なる不在として扱わない。

### 巨大 hub / 裸言及を扱う
→ `grasp gather <query>` を最初に見る。link stats、裸言及 summary、co-link slice、representative mentions、backlinks、次に実行する recipe が bounded に返る。`returned_counts` / `total_counts` / `omitted_counts` は row 単位（mentions=bare mention lines、co_links=targets、backlinks=link rows）なので、足りなければ個別 verb で広げる。`--budget` は厳密 token packing ではなく row limit selector。

- 裸言及の監査: `grasp mentions <query>`。既定は parsed internal-link span 外の bare occurrence がある行だけ返す。各行は `exact-link-page` / `query-link-page` / `unlinked-page` に分類され、summary に `come_from_candidate`（初期 heuristic score / signals / rationale）が入る。page に query 系 link handle が無い行だけ見たい時は `--unlinked`、全 occurrence が link 内の行も見たい時は `--include-linked`。
- slice handle 探索: `grasp co-links <query>`。query を含む行で同時に出る internal links を rank する。既定 `--rank slice` は target title 自体が query を含むものを `query-containing-title` として後ろへ回し、narrower handle を先に出す。raw count order が必要なら `--rank raw`。
- 重要: `mentions` の裸言及は「全部リンク化すべき漏れ」ではない。bulk link 化は hub を悪化させることがある。come-from 昇格候補や、用途別 handle への分岐を考えるための観測値として扱う。

### 被リンクの濃さだけ知りたい / その概念が既出か
→ `grasp link-stats <title>`。incoming `link_count` と 0/1/N（none/single/multi）。

### まだ本文の無い「概念ハブ」を見渡したい
→ `grasp unresolved`。多くのページから参照されるのに本文ページが無い target を rank。
- **これは「書くべき TODO リスト」ではない**。多参照の未解決 target は、本文が無くても**他ページの文脈で既に意味を持つ概念ノード**。「次に書く候補」や調査の起点として眺めるのはよいが、全部を埋めるべき穴と解釈しない。

### 本文だけ見たい（近傍は不要）
→ `grasp peek <title>`。長大ページでは `--line-offset N --line-limit M` で本文行だけをページングする。

### AI に渡す 1 ファイルの近傍 bundle が欲しい
→ `grasp export-ai <title>`。Cosense の "Export for AI" 風に main page + 1-hop pages を 1 テキストへ展開する。default は `--depth 1` かつ limit なし。2-hop まで欲しい時は `--depth 2`、ファイルへ保存する時は `--output <path>`。

### hosted の最新を取り込みたい（保守作業）
→ ユーザが指定した project URL で `grasp sync <project-url>`（`cosense` CLI 経由で最近更新ページのみ差分 upsert。`--dry-run` あり）。`@helpfeel/cosense-cli` の `cosense` binary が PATH にあり、対象 project に認証済みであることが必要。通常の JSON 調査では不要。

### 管理者 export が無い hosted project を部分取得したい
→ `grasp acquire <project-url>`。これは full seed 済み project の freshness path である `sync` とは別で、読めるページだけを local store の project namespace に取り込む初回 seed。

- 特定文字列を含む slice: `grasp --project <project:slice> acquire <url> --search <query> --limit N`
- 自分の icon / 編集 page slice: `grasp --project <project:mine> acquire <url> --filter <name> --limit N`
- 起点 page から link crawl: `grasp --project <project:crawl> acquire <url> --from-page <title-or-url> --depth N --limit N`
- URL/title リスト: `grasp --project <project:seed> acquire <url> --seed-file pages.txt`

`acquire` は対象 project namespace を置き換える（append しない）。既存 full export を誤って潰さないよう、`--project` 省略時の local namespace は `<remote-project>:acquire` になる。partial corpus の `backlinks` / `related` / `unresolved` は「取得済み subset 内」の結果であり、hosted project 全体の事実として答えない。`grasp stats` の Acquisition 節で coverage と前回 acquisition criteria / candidate updated range / `remote_fetched` / `reused` を確認する。
同じ acquisition criteria で再実行すると、前回 page manifest と hosted metadata の `updated` が一致するページは local store から再利用し、不要な `readPage` を避ける。`searchFullText` や `seed-file` など hosted updated metadata が無い候補は stale を避けるため従来通り読む。
取得候補が全て失敗しても partial acquisition report として exit 0 で返ることがある。`diagnostic.type=all_failed`、`failed_pages[].error_class`、`diagnostic.next_actions` を見て、`cosense` binary / `node` PATH / login / seed title を切り分ける。

既存 store 内の `[/project/page]` refs を外部 project acquisition の seed bibliography として使う時は `grasp cross-project-refs` を先に見る。これは `search "[/"` ではなく parsed link target extraction なので、`.icon` / project root / self-project / semantic page ref を target 単位で分けられる。

```bash
grasp --project <source-project> cross-project-refs --semantic-only --limit 20
grasp --project <source-project> cross-project-refs --semantic-only --limit 20 --seed-dir /tmp/grasp-seeds
grasp --project <source-project> cross-project-acquire --limit 5 --seed-limit 10 --dry-run
```

`--semantic-only` は `.icon`、project root、自 projectへの refs を除き、外部 project の page refs だけを rank する。`--seed-dir` を付けると target project ごとに seed file を書き、対応する `grasp --project <project>:semantic acquire ... --seed-file ...` command も返す。raw な混在を見たい時は `--exclude-icons` や `--include-self` を使い分ける。
実取得まで行う時は `cross-project-acquire` を使う。これは `cross-project-refs --semantic-only` の seed titles を使って target project を `<project>:semantic` namespace に順に partial acquire し、各 project の fetched / failed / diagnostic / reciprocal refs / top internal links を bounded summary として返す。store を更新するので、まず `--dry-run` で計画を確認する。

## verb 一覧（snapshot — 詳細は各 `grasp <cmd> --help`）

| verb | 用途 |
| --- | --- |
| `read <title>` | 本文＋逆リンク＋related＋未解決を近傍同梱で（`--related-snippets` で related/source ページ冒頭、`--related-snippet-mode edge` で根拠リンク行も同梱） |
| `search <query>` | 本文行を検索。既定は literal line substring、`--mode boolean` で AND/OR/NOT、`--scope line|page` で評価単位を切替、`--context N` で hit 周辺行を同梱 |
| `suggest <partial>` | タイトル補完。既定 fuzzy は長文タイトルの断片語・文字順序近似を拾う。`--mode substring` で厳密部分一致 |
| `backlinks <title>` | 行レベル逆リンク（page なし target も） |
| `related <title>` | 2-hop ページ / page なし target の source pages / ambiguous handle の source pages + candidate related |
| `path <A> <B>` | pages / page なし target 間の短いリンク経路（no-path 時も recovery hints） |
| `mentions <query>` | literal query の裸言及を link span 外 occurrence として数え、page-level link status と come-from 昇格候補 score を返す。`--unlinked` で no-link-handle page に絞る |
| `co-links <query>` | query を含む行で同時に出る internal links を rank し、hub の slice handle を返す。`target_relation` と `--rank slice|raw` あり |
| `cross-project-spread <title>` | normalized title が project 群にどれだけ広がるかを見る weak signal。materialized / ambiguous / unresolved / incoming counts を project label 付きで返し、page identity は merge しない |
| `cross-project-spreads` | seed title なしに normalized handle の project spread を rank する。structural-name / numeric-only / artifact-only は label して下位 band に回す |
| `cross-project-refs` | Cosense shorthand `[/project/page]` を target-aware に抽出し、semantic / `.icon` / project root / self-project に分類して project 別に rank。`--seed-dir` で acquire seed files / commands を生成 |
| `cross-project-acquire` | `cross-project-refs --semantic-only` の seed titles から複数 hosted project を `<project>:semantic` に一括 partial acquire。`--dry-run` あり。実行後は reciprocal refs / top internal links も返す |
| `gather <query>` | link stats・裸言及 summary・co-link slices・backlinks・next recipes の bounded bundle。row 単位の returned / total / omitted counts 付き |
| `adopt-markdown <folder>` | 既存 Markdown wiki を store + JSONL journal に採用する authoring fast-path 入口 |
| `export-markdown --output <folder> --check` | Markdown projection の no-op gate。差分があれば exit 1。明示 alpha overlay として `--regenerate-index` / `--regenerate-log --journal <events.jsonl>` も持つ |
| `append-section <title>` | Markdown-backed page に section を追記し、SQLite index / JSONL journal / Markdown projection を更新する alpha write surface |
| `append-log` | Markdown-backed log page に dated entry を追記し、SQLite index / JSONL journal / Markdown projection を更新する alpha write surface |
| `write-page <title>` | Markdown-backed page の本文行を全置換し、`page_update` event と projection を更新する alpha write surface |
| `rename-page <target> <new-title>` | Markdown-backed page の page id を保ったまま title / optional source path を変更し、旧 title を alias として残す alpha write surface。必要時は projection に `id` / `title` / `aliases` frontmatter を出す |
| `write-status` | alpha write 用に journal 件数・last event・Markdown projection check を返す。journal がある場合は primary log page を journal 由来 projection と比較し、`journal_log_stale` / `journal_log_changed_files` も返す。`--strict` は projection dirty / journal missing / stale log / log regeneration error で exit 1 |
| `write-diff` | filesystem 上の Markdown と stored projection の unified diff を返す |
| `revert-event <event-id>` | `section_append` / `log_append` / `page_update` / `page_rename` を current state 一致時だけ取り消し、`event_revert` を journal に記録する |
| `replay-journal` | JSONL journal だけから Markdown projection を再構築・check する alpha recovery surface |
| `link-stats <title>` | incoming link count と 0/1/N |
| `unresolved` | 未解決 target の rank view（TODO ではない） |
| `peek <title>` | 本文行のみ。`--line-offset N --line-limit M` でページング |
| `stats` | store の状態・件数 |
| `import --cosense <json>` / `import --markdown <folder>` | Cosense JSON / Markdown folder mirror の取り込み・再構築 |
| `import-forest <wikis.yaml>` | Markdown wiki registry の複数 entries を 1 store の複数 project namespace に一括 import。entry diagnostics と ambiguity summary 付き |
| `export-ai <title>` | Export for AI 風の単一テキスト bundle（alias `export-for-ai`） |
| `sync <url>` | hosted 差分取り込み（保守） |
| `acquire <url>` | admin export なしの hosted 部分取得 seed |

## 実行方法

- 形式: **`grasp <verb> ...`**。store は既定では home に1個 `~/.grasp/grasp.sqlite`（global default）。
- 1つの store に複数 project namespace を保持できる。`grasp import --cosense <json>` は export JSON の `name` を、`grasp import --markdown <folder>` は folder 名を project 名として使い、同名 project だけを置き換える。project 名を明示する時は `grasp import --project <name> --cosense <json>` / `grasp import --project <name> --markdown <folder>`。
- 一回限りのユーザ指定 JSON を読む時は、必要に応じて `--store <task-local.sqlite>` を使い、既定 store に project を増やさない。
- 未インストール環境では grasp repository root から `python3 -m grasp <verb>`（`pip install -e <grasp-repo>` 済みなら `grasp` が PATH）。
- `grasp import --cosense <json>` で Cosense JSON export、`grasp import --markdown <folder>` で read-only Markdown mirror、`grasp import-forest <wikis.yaml>` で registry 配下の複数 Markdown wiki を import する。authoring fast path では `grasp adopt-markdown <folder> --journal <events.jsonl>`、`grasp export-markdown --output <folder> --check`、`grasp append-section ... --output <folder>`、`grasp append-log ... --output <folder>`、`grasp write-page ... --from-file <file> --output <folder>`、`grasp rename-page <target> <new-title> --new-path <path.md> --output <folder>`、`grasp write-status --output <folder>`、`grasp write-diff --output <folder>`、`grasp revert-event <event-id> --output <folder>`、`grasp replay-journal --journal <events.jsonl> --output <folder> --check` を使う。write 系は Markdown-backed project の unique handle / page-id / path に限る alpha surface。`write-page` は title / aliases / source path を変えず本文行だけ全置換する。`rename-page` は page id を保ち、旧 title を alias にして incoming `[[旧名]]` の surface text を書き換えない。rename 後に path-derived id / first H1 / aliases だけでは identity が失われる場合、projection は `id` / `title` / `aliases` frontmatter を生成するため、direct re-import でも page id と旧名 alias が残る。`export-markdown --regenerate-index` は primary `index.md` を catalog projection に、`--regenerate-log --journal <events.jsonl>` は primary log page を journal 由来 projection にする。`write-status` は通常 projection check に加え、journal がある場合は primary log page と journal 由来 projection を比較し `journal_log_stale` / `journal_log_changed_files` を返す。ship loop では `write-status --strict` を使い、projection dirty / journal missing / stale log / log regeneration error を exit 1 にする。`revert-event` は append event の inserted lines が現在も page tail にある時、page_update の current lines が一致する時、または page_rename の current lines / title / path が一致する時だけ動く。`replay-journal` は `page_create` / `page_update` / `page_rename` / `section_append` / `log_append` / `event_revert` の strict replay に対応。任意 frontmatter の merge / 汎用 revert はまだ無い。以降は sub-second。別パスは `--store` / `$GRASP_STORE`、別 home は `$GRASP_HOME`。
- この repo の file-back dogfood では、gitignored store `.grasp/file-back.sqlite`、project `grasp-wiki`、journal `wiki.grasp/events.jsonl`、output `wiki` を既定の組として使う。`wiki.grasp/events.jsonl` がある時は direct Markdown patch でなく grasp write first。grasp alpha が安全に表現できない変更だけ fallback する。
- import 済み JSON は store 横の `<store>.imports/` に復旧用コピーとして保持される。通常 command が古い schema の store を見つけた時は、復旧用コピーからサイレントに current schema へ再構築して続行する。`stats` は診断用なので自動再構築しない。hosted の最新差分は復旧後も `sync` の責務。
- 複数 project がある store で読む時は `grasp --project <name> read "ページタイトル"` のように project を指定する。project が1つだけなら省略可。
- text 出力の `line_id` は既定で `P1:0` のような実行内ローカル別名に短縮され、先頭付近に `P1=<page-id>` の legend が出る。親へ根拠として返す時は、必要なら `source_title` とこの alias ではなく `--json` の完全 `line_id` を使う。
- 機械可読が要る時は `--json`。root option だが verb 後にも置ける: `grasp --project <name> read "ページタイトル" --backlinks-limit 3 --json`。text のまま完全 line id を見たい時は `--full-ids`（これも verb 後可）。`--store` / `--project` は verb の前。
- 空白・記号を含む title / query は shell でクォートする（`'...'`）。

## 回答の形式

- 情報源（ページタイトル）を示しながらユーザーの問いに直接答える。
- 本文の無い概念について答える時は「本文なし、関連 N ページの文脈から」と限界を明示する。
- 回答言語はユーザの言語に合わせる。nishio/grasp の開発 wiki や `/ship-next` 運用について答える時は、特に指定がなければ日本語で簡潔に返す。
- 固定テンプレートは規定しない。

## hosted Cosense との使い分け

| | grasp（このスキル） | hosted Cosense / cosense CLI |
| --- | --- | --- |
| データ | ユーザ指定 JSON / Markdown folder から作った local snapshot / local store（オフライン・即時） | hosted の生の最新状態 |
| 強み | 行レベル逆リンク・未解決 target 列挙・近傍同梱を1コール | hosted project の最新取得・編集 |
| 向く時 | export 済みデータをグラフで辿る／逆リンク・関連を厚く見る | 最新の hosted 状態が要る／hosted project に書き込む |

最新性が要らず「逆リンク・関連・未解決をグラフごと厚く読む」なら grasp。生の最新や hosted への書き込みが要るなら hosted 側の手段を使う。
