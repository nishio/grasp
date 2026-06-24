---
type: entity
summary: v1 リリース時点で grasp に実装済みの挙動。旧 SPEC.md / v1-todo.md は一時的な実装指示として分解し、このページは current facts だけを保持する。
sources:
  - 旧 wiki/SPEC.md（v0.5 実装指示, deleted after split）
  - 旧 wiki/v1-todo.md（一時 TODO, deleted after split）
  - grasp/cli.py
  - grasp/cosense.py
  - grasp/markdown.py
  - grasp/sqlite_store.py
  - pyproject.toml
  - README.md
  - skills/grasp/SKILL.md
---

# entity: grasp v1 implemented surface

このページは **v1 リリース時点で実装済みの事実**だけを保持する。旧 `SPEC.md` は定義ではなく v0.5 実装指示、旧 `v1-todo.md` も一時 TODO だったため削除し、未実装項目は [[grasp-backlog]] に分離した。

## v1 scope

v1 = **エクスポート済み Scrapbox / Cosense JSON、または read-only Markdown mirror を、AI が CLI + Agent Skill から高速に読む read-only tool**。

実装済み:

- Cosense JSON export を `grasp import --cosense <json>` で SQLite store に materialize する。
- Markdown folder を `grasp import --markdown <folder>` で read-only mirror として SQLite store に materialize する。
- 1つの SQLite store に複数 project namespace を保持する。project 内の graph は混ぜない。
- `read` が本文だけでなく、行レベル backlinks・related・page-local unresolved targets を一体で返す。
- page が存在しない linked target も graph node として扱い、`backlinks` / `related` / `link-stats` で source context を読める。
- `read` / `link-stats` は missing + 0 incoming の zero-hit 時に recovery hints（`suggest`, `search --limit 3`, 近い unresolved target）を返す。`search` と `related` も空結果時に recovery hints を返す。
- `path <A> <B>` が pages ∪ unresolved targets を node、materialized internal links を無向 edge として bounded shortest path を返す。
- home 配下の global store 1 個を default にする。
- AI 向け delivery は CLI + Agent Skill。詳細引数と JSON key は `grasp <cmd> --help` が mechanics SSoT。

v1 scope 外:

- local write / rename / transclude。
- frontmatter title / aliases / Obsidian block refs などの full Obsidian compatibility。
- vector search。
- Web UI / realtime multi-user collaboration / sharing and permissions。

## delivery

- Python package `grasp`。`python3 -m grasp ...` と console script `grasp` の両方で起動する。
- Python 3.10+、runtime dependencies は無し（stdlib `sqlite3`）。
- `README.md` は「主たるユーザは人間 CLI operator ではなく AI agent」という前提に更新済み。
- `skills/grasp/SKILL.md` が「いつ使うか」を持ち、CLI mechanics は `grasp <cmd> --help` に寄せる。
- `--store` / `--project` は root option として command 前に置く。`--json` / `--full-ids` は agent が末尾へ置くミスを回復するため、command 後にも hidden alias として受ける。
- text 出力の line-id は既定で実行内ローカル別名（`P1:0` など）に短縮し、先頭付近に `line-id aliases: P1=<page-id>` legend を出す。JSON は従来通り完全 `page.id:line-index` を返す。text で完全 ID が必要な時は `--full-ids`。

## store

- current public compatibility version は `1.5.17`。release / store compatibility の履歴と bump rule は [[history]]。
- store default: `$GRASP_STORE` → `$GRASP_HOME/grasp.sqlite` → `~/.grasp/grasp.sqlite`。
- project default: `$GRASP_PROJECT` → store 内に1 project だけならそれ → 複数 project なら明示必須。
- `grasp import --cosense <json>` は export JSON の `name` を project namespace として使い、同名 project だけを置き換える。`grasp import --project <name> --cosense <json>` で明示 override できる。
- `grasp import --markdown <folder>` は folder 名を project namespace として使い、同名 project だけを置き換える。`grasp import --project <name> --markdown <folder>` で明示 override できる。既存 Markdown file へは書き戻さない。
- current schema は v5。schema version は table shape だけでなく parser/index semantics の変更にも使う。v5 は `#tag` と数字 link を edge 化するため、v4 store は import cache から再構築される。
- current schema store への import は他 project を保持する。古い schema の store に import する時は current schema として作り直す。
- legacy `--export` / `--rebuild-store` / `--force` / 暗黙 seed は v1 surface には無い。
- SQLite schema は projects / pages / lines / edges / unresolved_targets / unresolved_target_examples を持つ。pages/lines/edges/unresolved は project 列で namespace 化し、page id / line id は project と組にした複合 key で扱う。
- `stats` は store path, selected project, project list, schema version, source export, imported_at, counts, acquisition metadata などを返す。project 未指定かつ複数 project がある時は aggregate counts と `projects[]` を返す。store が存在しない場合も traceback/error ではなく `diagnostic.type=store_missing` と次アクションを返す。
- import 済み JSON は store 横の `<store>.imports/` に project ごとの復旧用コピーとして保持する。manifest は project override と cached path を持つ。
- 古い schema の store でも `stats` は診断用に読める。`read` / `peek` など通常 command は schema mismatch を検出すると、復旧用コピーからサイレントに current schema へ再構築してから続行する。復旧用コピーが無い古い store では、metadata の `last_source_export` / `source_export` が存在すればそれを fallback に使う。どちらも無ければ従来通り手動 `grasp import --cosense <json>` を促す。import cache は seed snapshot なので、hosted の最新差分は復旧後も `sync` の責務。
- **2026-06-23 観測（nishio primary machine, install path 検証中に偶発）**: code の `SCHEMA_VERSION` が 3→5 に上がった後、`~/.grasp/grasp.sqlite`（schema 3 のまま）に対する最初の通常 command で import cache からサイレント再構築が実際に発火した。**可視な副作用**として stats の count が変わり（parser semantics 変更で edges 120693→125409, unresolved_targets 41750→42770）、`imported_at` も更新され、その **1 command だけは sub-second でなく import 相当の latency** を払う（[[grasp-cli-mvp]] の "初回 import は数秒〜十数秒" がここでも当てはまる）。これは corruption でも `sync` でもなく期待挙動。upgrade（`git pull` で schema bump）前後で `stats` を比べた AI / 人間が count drift や `imported_at` 更新を「壊れた / 同期された」と誤読しないこと。drift は parser が `#tag` / 数字 link を edge 化した結果で、本文・page 数（25791）は不変。

## commands

| command | v1 implemented behavior |
|---|---|
| `import --cosense <json>` | Cosense JSON export を project namespace に構築・置換。他 project は保持 |
| `import --markdown <folder>` | Markdown folder を read-only mirror として project namespace に構築・置換。他 project は保持。frontmatter `title` / `id` / `aliases` / `tags` を読み、`[[wikilink]]` / `#tag` を edge にする |
| `stats` | store の schema / project list / metadata / count を表示。store missing 時は diagnostic と next actions を返す |
| `read <title>` | existing page は本文 + backlinks + related + unresolved。missing linked target は link stats + backlinks + source pages。zero-hit 時は `recovery_hints` も返す。`--related-snippets` で related/source pages の snippet を同梱する。既定 `--related-snippet-mode lead` は先頭 N 行（default 5）、`edge` は related/source item を導いたリンク行を中心に `snippet_lines` / `snippet_window` を返す。`--around-line <line-id> --line-context N` で完全 line_id からページを解決し、中心行の前後 N 行だけを `lines[]` と `line_window` で返す |
| `backlinks <title>` | `(source page, line-id, line text)` の行レベル backlinks。missing target にも効く |
| `related <title>` | existing page は page 間 edge の 2-hop pages。missing target は source pages。空結果時は `recovery_hints` を返す |
| `path <A> <B>` | pages ∪ unresolved targets を node、materialized internal links を無向 edge として shortest path を返す。`--max-depth` default 4、`--limit` default 3。edge には根拠 line を同梱する。端点が resolve できるが経路が無い時は `recovery_hints.path` に reason / next_max_depth / related / backlinks / link-stats を返す |
| `link-stats <title>` | incoming link count / source page count / none-single-multi を返す。zero-hit 時は `recovery_hints` も返す |
| `peek <title>` | page lines のみ。`--line-offset N --line-limit M` で本文行だけをページングし、JSON は `line_offset`, `lines_truncated_before`, `lines_truncated_after` を返す |
| `suggest <partial>` | title 部分一致候補 |
| `search <query>` | 既定は空白も含む literal line substring search。`--mode boolean` で AND/OR/NOT、括弧、quoted phrase、隣接 term の implicit AND を扱う。`--scope line` は行単位、`--scope page` はページ単位で式を評価する。`--context N` で各 hit に前後 N 行の `context_lines[]` と `context_window` を同梱し、text 出力でも hit 直下に bounded context を表示する。literal 0件時は NFKC query 正規化＋長音除去の normalized fallback を試し、text は `[normalized]`、JSON は `match_mode: "normalized"` を返す。空結果時は `recovery_hints` も返す |
| `mentions <query>` | literal query の出現を行単位で探し、parsed internal-link span 外の **bare mention** を既定で返す。summary は全 literal hit の total/bare/linked occurrence 数、bare line/page 数、page status counts、come-from 昇格候補の初期 heuristic scoring を返す。各行は `exact-link-page` / `query-link-page` / `unlinked-page` に分類し、`--unlinked` で page に query-containing link target が無い行だけ返す。`--include-linked` で全 occurrence が link span 内の行も返す。`--context N` で周辺行同梱 |
| `co-links <query>` | literal query を含む行で同時に出る internal links を target ごとに rank する。exact query target は既定で除外し、`--include-self` で含める。既定 `--rank slice` は `target_relation=query-containing-title` を後ろへ回し、narrower `slice-handle` を先に出す。`--rank raw` は従来の count order。各 item は target_relation / link_count / line_count / source_page_count / total_source_views / examples を返す |
| `gather <query>` | link stats、bare mention summary、representative bare mentions、co-link slices、backlinks、次に実行する recipe を bounded bundle として返す。co-link slice は既定 `slice` ranking。`returned_counts` / `total_counts` / `omitted_counts` は row 単位（mentions=bare mention lines、co_links=ranked co-link targets、backlinks=incoming link rows）で返す。`--budget` は row limit を選ぶ近似であり厳密 token packing ではない。huge hub では bulk-linking を避ける banner を返す |
| `export-ai <title>` / `export-for-ai` | main + 1-hop/2-hop page 本文を Cosense Export for AI 風に単一テキスト化 |
| `sync <project-url>` | optional freshness path。`cosense` CLI で最近更新ページを取得し、SQLite store に upsert |
| `acquire <project-url>` | admin export なしの hosted Cosense 初回 seed / partial corpus acquisition。`--search` / `--filter` / `--full-list` / `--from-page` / `--seed-file` |
| `unresolved` | page 実体のない linked target を ranking して返す。TODO list ではない |

## sync facts

- `sync` は `cosense listPages --sort updated` の metadata を store の `pages.updated` と比較し、changed page だけ `cosense readPage` で本文取得して upsert する。upsert 後に unresolved target を再 materialize し、project counts を更新する。
- `--dry-run` は changed page の検出だけを行い、`readPage` / upsert はしない。
- 2026-06-23 実測: export seed 由来の local `nishio` store は 25791 pages、hosted count は 25792 pages。`sync --limit 20` が新規ページ `タブUI` を upsert し、local stats は 25792 pages / 724986 lines になった。再 dry-run は changed 0。
- この検証は「最近更新された missing/new page」の解消を確認したもの。削除・rename・古い更新日時のまま local に無いページの検出は [[incremental-sync]] の Open Questions のまま。

## acquire facts

- `grasp acquire <project-url>` は `@helpfeel/cosense-cli` の `cosense` binary を使い、管理者 JSON export なしに hosted project の読めるページを local project namespace に seed する。
- acquisition modes: `--search <query>` は `cosense searchFullText` の page results、`--filter <name>` / `--full-list` は `cosense listPages` pagination、`--from-page <title-or-url> --depth N` は `cosense readPage` と本文 links の bounded crawl、`--seed-file` は title/URL list を読む。
- `acquire` は対象 project namespace を append せず置き換える。`--project` 省略時は既存 full export project を誤って潰さないよう `<remote-project>:acquire` を default local namespace にする。同じ hosted project の複数 slice は `--project project:slice` のように別 namespace へ分ける。
- `stats.acquisition` と text `## Acquisition` は mode / coverage / project_url / seed / depth / limit / fetched / failed を返す。partial corpus の `backlinks` / `related` / `unresolved` は取得済み subset 内の結果であり、hosted project 全体の事実ではない。
- 2026-06-23 smoke: public `https://scrapbox.io/shokai/` に対して `acquire --search codex --limit 2` が 2 pages / 55 lines / 16 edges / 15 unresolved_targets を作成し、`read Codex` が本文 + unresolved targets を返した。

## import and parser facts

- Cosense export の line には安定 id が無いので、v1 は `page.id:line-index` を `line-id` として採番する。これは read-only snapshot 内の **positional locator** であり、行挿入や write / transclude を跨ぐ安定 line identity ではない。text 出力では token 節約のため local alias に畳むが、JSON と `--full-ids` は完全 ID を出す。stable line identity の設計要件は [[grasp-backlog]]。
- link graph は export に保存されないため、line text から edge を materialize する。
- title / link resolve は case-insensitive + whitespace folding。
- Cosense title 行 `lines[0]` は本文に残す。完全性と line-id 安定性を優先する。
- Cosense `[[...]]` は bold markup であり link ではない。v1 importer は link として扱わない。
- `[2024]` のような数字のみ bracket token は valid internal link として扱う。`xs[0]` / `func()[1]` のように `[` の直前が ASCII 非空白の index 風 syntax は false positive として除外する。
- `#tag` は `[tag]` と同等の internal link として edge 化する。`# ` は空 token なので除外し、`https://example.com/#fragment` のような URL fragment は hashtag boundary で除外する。

Markdown mirror facts:

- `grasp import --markdown <folder>` は再帰的に `.md` を読み、hidden path component 配下の file は除外する。
- page title は frontmatter `title` があればそれ、なければ file stem（`foo.md` → `foo`）。同一 normalized title は import 時に error にする。
- page id は frontmatter `id` があればそれ、なければ relative path の SHA-1 先頭 24 hex から作る。line id は Cosense import と同じく `<page-id>:<line-index>`。
- frontmatter `aliases` と file stem は title resolve 候補になる。import 時に `[[alias]]` は canonical page title へ解決して edge 化し、store metadata の alias map により `read <alias>` / `backlinks <alias>` / `link-stats <alias>` も canonical page を読む。
- frontmatter `tags` は page から tag target への outgoing edge として materialize する。`#tag` 付きの同じ frontmatter line で重複する場合は line 単位で重複 edge を避ける。
- Markdown mirror の再 import は manifest を metadata に保存して差分判定する。manifest は relative path ごとの content hash / mtime_ns / page id / title / aliases を持つ。content-only 変更では changed file の page / lines / outgoing edges だけを差し替え、unresolved targets と project counts を再計算する。title / id / aliases / file set が変わった時は alias 解決が他 file の edges に影響するため full rebuild に戻す。
- Markdown line text は原文のまま保存する。frontmatter も本文行として残す。
- `[[Page]]`, `[[Page|alias]]`, `[[Page#Heading]]`, `[[folder/Page.md]]`, `![[Embed]]`, `#tag` を internal edge として materialize する。heading / alias は target resolution からは落とし、path suffix は file stem に畳む。
- inline backtick 内と fenced code block 内の `[[...]]` は edge にしない。この repo の `wiki/` ではバックティックのプレーン名を親 llm-wiki 参照として扱い、grasp 内 edge にしない方針と整合する。

parser が link から除外するもの:

- external URL / icon or image / decoration / math / cross-project link。
- inline backtick 内。
- ASCII index 風 `xs[i]` / `func()[0]`。
- 連続 `*` / `-` / `_` decoration の `[** x]` など。

## performance

実データ（nishio project: 25791 pages / 724981 lines）で、SQLite warm store の主要 command はおおむね 50-200ms:

- `read` は sub-100ms。
- `backlinks` / `unresolved` は約 50-80ms。
- 既定 `search` は `LIKE` 全行 scan 律速で約 180ms。boolean page scope は SQL の `EXISTS` でページ単位に条件判定し、該当 positive term を含む行を返す。literal 0件時の normalized fallback は NFKC query 正規化＋長音除去を SQLite `REPLACE` で行う。完全なかな/カナ変換 Python scan は 50k lines 以下の小規模 store に限る。FTS5 trigram hybrid は [[fts5-trigram-search]] の通り未実装候補。
- `mentions` / `co-links` / `gather` は既存 `lines` / `edges` / `pages` から都度計算する schema-compatible retrieval primitive。query literal の `LIKE` hit 行を起点にするため、巨大・一般語 query では `search` 同様に scan cost を払う。`gather --budget` は厳密 token budget ではなく bounded row limit selector。omitted counts も token ではなく row 単位。
- `path` は実験的 command で、現状は command ごとに pages ∪ unresolved targets の一時 adjacency を構築する。nishio store の dogfood（66092 nodes / 115075 undirected edges）では `path KJ法 弱い紐帯 --max-depth 4 --limit 1` が約2-5s。hot read path ではなく graph reasoning primitive として扱う。
- 初回 import は 1 回だけ数秒から十数秒程度。

## source pages

- Cosense JSON export の実スキーマ: [[cosense-json-export]]
- v1 実装の詳細履歴: [[grasp-cli-mvp]]
- release / store compatibility history: [[history]]
- CLI + Skill delivery: [[delivery-cli-plus-skill]]
- store 決定: [[persistence-custom-format]]
- freshness path: [[incremental-sync]]
- hosted Cosense との使い分け: [[cosense-cli]]
