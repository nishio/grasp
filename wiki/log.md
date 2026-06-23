# Log

## [2026-06-23 18:27] implementation | wanted examples を materialize、FTS search は見送り
- `wanted_examples` table を追加し、import / sync 後の `rebuild_wanted` で各 wanted target の上位 5 example edge を materialize。`wanted --limit N` が N 回 example query を投げないようにした。schema_version は 2。
- Python 内部計測では `wanted(limit=100)` 約 6ms。CLI wall time は Python 起動 + output 込みで約 1.0 秒。
- SQLite FTS5 trigram を試したが、2文字日本語 query（`盲点`）は `MATCH` で拾えず、FTS table `LIKE` では `盲点カード` の recall が落ちた。本文検索は correctness 優先で `lines.text LIKE` のまま維持。
- 実データ import は約 9.6 秒。`search 盲点 --limit 100` 約 1.16 秒、`wanted --limit 100` 約 1.01 秒、`read 盲点カード` 約 1.03 秒（CLI wall time）。

## [2026-06-23 18:19] implementation | M2-4 cosense-cli 差分 sync を実装
- `grasp sync <project-url>` を追加。`cosense listPages --sort updated` で最近更新ページ metadata を inspect し、store の `pages.updated` と比較して changed page だけ `cosense readPage` → SQLite upsert → `wanted` 再 materialize。`--dry-run`, `--limit`, `--batch-size`, `--cosense-command` 対応。
- humanized `updated` は suffix 前の ISO8601 を epoch seconds に変換。pinned page は停止条件から除外。hosted line id は採用せず `page.id:line-index` を維持。
- 検証: fake client unit test で changed page upsert / old edge 削除 / new wanted を確認。実 `cosense` dry-run/no-op smoke: `sync https://scrapbox.io/nishio/ --limit 5` は changed 0 / updated 0。

## [2026-06-23 18:15] implementation | M2-3 parser false-positive `[** x]` 系を修正
- `is_internal_cosense_link` の decoration 判定を「先頭の連続する `*` / `-` / `_` 群 + 空白」に拡張。`[* x]` だけでなく `[** x]`, `[*** x]`, `[-- x]`, `[__ x]` を link としない。
- 実データ再 import: 120693 edges / 41750 wanted。`backlinks '** 深い思考'` は none になり、wanted 上位から消えた。
- 検証: `python3 -m unittest discover -s tests` OK。

## [2026-06-23 18:14] implementation | M2-2 行レベル本文検索 `search` を追加
- `grasp search <query>` を追加。SQLite `lines.text LIKE` で本文行を検索し、`source_page_id/title/views/updated`, `line_id`, `line_index`, `line_text` を返す。text output は backlinks と同じ行リスト形式、`--json` 対応。
- ranking は SPEC 通り暫定: page.views → updated → title → line_index。`suggest` は title 補完として維持。
- 検証: `python3 -m unittest discover -s tests` OK。実データ `search 盲点 --limit 5` は約 0.7 秒で行レベル hits を返した。

## [2026-06-23 18:12] implementation | M2-1 SQLite on-disk store を実装
- `grasp import --force` と `--store` / `--rebuild-store` を追加。default store は `.grasp/grasp.sqlite`（gitignored）。通常 command は store が存在すれば `raw/nishio.json` を再 parse しない。
- SQLite schema: `metadata`, `pages`, `lines`, `edges`, `wanted`。`wanted` は import 時に materialize（毎回 group-by しない）。`Page.line_count` は SQLite row 由来の `stored_line_count` を持てるようにした。
- 実データ検証: import 約 8 秒、store 利用時 `read 盲点カード` 約 0.7 秒、`wanted --limit 3` 約 0.7 秒、`backlinks 盲点` 約 0.4 秒。`python3 -m unittest discover -s tests` OK。

## [2026-06-23 17:58] decision | 保存=SQLite ＋ 最新化=cosense-cli 差分更新（next SPEC 改訂）
- nishio 判断2点: ① 渡された JSON を JSON のまま保存し続ける必要はない → on-disk store は **SQLite もしくはより良い構造**。② 最新化は export 反復でなく、**初回 export を seed にし以降 cosense-cli で最近更新ページだけ取得して差分 upsert**。
- [[persistence-custom-format]] に Update 追記（on-disk か in-memory かの Open Q を SQLite で解決、store は upsert 可能に）。新 decision [[incremental-sync]] を作成（`cosense listPages --sort updated` を delta cursor にする grounded メカニズム ＋ humanize timestamp / 削除検出 / line-id の Open Q）。
- [[cosense-cli]] の役割を「比較対象・MVP では非依存」から「**post-MVP の freshness 経路**」へ更新。[[SPEC]] を改訂: M2-1 を on-disk store(SQLite, upsert 可能)に、M2-4「cosense-cli 差分更新」を追加、import adapter を bulk seed＋incremental delta の2モードに、スコープ外から「差分 index 更新」を除外。

## [2026-06-23 17:49] file back | grasp×cosense-cli 実測比較 ＋ Codex 向け次マイルストーン SPEC
- MVP 実装を同一ページ（`君主道徳と奴隷道徳`）で `cosense`（hosted, 認証済み）と同条件比較。一次データを [[cosense-cli]] に「## 実測比較」として固定。
- **速度**: grasp は全コマンド一律 ~3.4s（123MB JSON full parse が律速、cosense は 0.5–1.2s）。**機能**: grasp だけが行レベル逆リンク・赤リンク列挙・1 コール近傍同梱・オフラインを出す。cosense だけが本文/ベクトル検索・生きた状態を出す（`盲点` 検索 grasp 8 vs cosense 100）。中核仮説は成立、弱点は既知の MVP 割り切り。
- parser 残 false-positive を実測: `[** x]` 系装飾（`** 深い思考` count 59）が link 扱い → [[grasp-cli-mvp]] と [[SPEC]] Open Q に記録。
- [[SPEC]] に「## 次のマイルストーン（post-MVP / step 2）」を追加: M2-1 on-disk index（latency 解消・native store seed, 最優先）/ M2-2 `search`（本文検索）/ M2-3 parser 修正。read-only 維持、write/identity はまだ。リリース（README/push）は人間判断待ちで保留。

## [2026-06-23 17:34] rename | decision ページ why-design-B → why-not-scrapbox-clone
- 「design B」は A/B fork を覚えていないと意味が通らない相対ラベルで、リンク identity / H1 として決定の中身を隠していた（nishio 指摘「タイトルが微妙」）。
- `git mv` で `decisions/why-design-B.md` → `decisions/why-not-scrapbox-clone.md`。H1 を「Scrapbox を忠実 clone せず、identity-without-name を足した『あるべき姿』を作る」に。内部呼称としての design B は本文に注記して残す（A vs B fork の論理は維持）。
- 参照を更新: CLAUDE.md / AGENTS.md / index.md / SPEC.md / persistence-custom-format.md の `[[why-design-B]]` リンク、log.md は履歴 prose を残しリンクのみ追従、cosense-json-export.md は prose の「design B」→「grasp」。

## [2026-06-23 17:33] file-back | MVP 実装知見を entity 化し、cosense-cli 可視性を記録
- 新ページ [[grasp-cli-mvp]]: `python3 -m grasp` の read-only verbs、in-memory data model、line-id 方針、wanted ranking、strict parser、実データ scale、検証、次課題を実装現状として固定。
- 新ページ [[cosense-cli]]: local 環境では `@helpfeel/cosense-cli@1.4.4` が `cosense` binary として利用可能。grasp は local export/native store、cosense-cli は hosted Cosense 操作という使い分けを記録。
- [[cosense-json-export]] 更新: broad bracket 分類値と strict parser 実装値（123170 edges / 58944 targets / 43344 wanted）を区別。lines[0] は MVP では本文に残すと確定。

## [2026-06-23 17:28] implementation | read-only Cosense JSON MVP CLI を追加
- Python package `grasp` を追加。`python3 -m grasp` / console script `grasp` で、`--export`（default: `$GRASP_EXPORT` or `raw/nishio.json`）と `--json` を受ける。
- 実装した read-only verbs: `read`（本文 + line-level backlinks + deterministic 2-hop related + page-local wanted）, `backlinks`, `wanted`; helper として `related`, `peek`, `suggest` も追加。line-id は `page.id:line-index`。Cosense title 行 `lines[0]` は本文に残す。
- Cosense parser は broad bracket 分類から厳しめに調整: 外部 URL / icon/img / decoration / math / cross-project / `[[...]]` に加え、inline backtick 内、ASCII index 風 `xs[i]` / `func()[0]`、数字のみ `[1]` を link から除外。理由: 実データで code/list 由来の `0` / `i` / `1` が `wanted` 上位を汚したため。
- strict parser で `raw/nishio.json`: 25791 pages / 724981 lines / 123170 edges / 58944 distinct targets / 43344 wanted / normalized title collision 1。以前の 133022 edges / 61613 targets / 45703 wanted は broad bracket 分類の値として残す。
- 検証: `python3 -m unittest discover -s tests` OK。実データで `wanted`, `backlinks 盲点`, `read 盲点カード`, `related 盲点カード`, JSON output を確認。毎回 118MB JSON を parse するため 1 command 約4-5秒、on-disk store は次段階の性能課題。

## [2026-06-23 16:45] ingest | Cosense JSON export の実物（raw/nishio.json, 25791 pages）を確認、import スキーマを確定
- nishio が管理画面 Export Pages（metadata ON）で出した実物を raw/ に配置 → 実スキーマを実測。SPEC が「Codex が実物で確認」と保留していた項目を確定。
- 新ページ [[cosense-json-export]]（entities/）: root/page/line スキーマ ＋ 6 gotcha。確定事項: ① **line に安定 id 無し**（138220 行で 0）→ grasp が import 時採番（原理4 と整合）。② **link graph は export に未保存**（page キーは title/id/created/updated/views/lines のみ）→ line.text を parse してエッジ materialize。③ `[...]` は overloaded（内部リンク 62.7% / 外部URL 23.4% / icon 6.7% / 装飾 3.6% / cross-project 2.8% / 数式 0.7%）、`[[...]]` は **bold でリンクでない**（grasp の `[[wikilink]]` と逆）。④ リンク解決は normalize（case-insensitive＋空白畳込, 実測 exact→normalize で 208 件だけ解決, title 衝突 1 group）。⑤ title=lines[0].text（≈99.7%）。⑥ users 2人（nishio＋garbot bot, line.userId あり）→ 単一所有前提に注釈。
- scale: 25791 pages / 724981 lines / 118MB。内部リンク instance 133022・distinct target 61613・既存解決 15702・**red link 45703** → `wanted` は ranking 必須（SPEC Open Q 確定。signal: 出現回数/views/recency）。
- [[SPEC]] 更新: line 40 の保留注記を確定事実＋[[cosense-json-export]] 参照に置換、MVP に実データ scale を追記、Open Q「read の近傍境界」に wanted ranking 必須を追記。

## [2026-06-23 15:56] decision | 保存形式 = 独自フォーマット（Markdown でない）、import は別責務、MVP = Cosense JSON export を読む
- nishio 訂正2点: ①保存形式は独自であるべき — Markdown が逆リンクメンテのしがらみの**発生源**（リンク=テキスト、逆リンクは未保存→全文スキャン or 書き戻し。独自なら逆リンク=エッジの逆読みで「維持」概念が消える）②「読める」は import の話で保存形式と独立。
- 新 decision [[persistence-custom-format]]: native=独自（Cosense の行/グラフモデルを正規化、ゼロ発明でない）。三層分離 native store ← import adapter（Cosense JSON / 後で Markdown）← CLI。「既存森40+を読める」は Markdown adapter で達成（native を Markdown にしない）。
- [[SPEC]] 更新: 保存形式/入力(import)/MVP 節を追加、データモデルを「エッジを native 保持」に、Open Q の永続化を解決済みに。MVP = Cosense JSON export 1ファイルを `read`/`backlinks`/`wanted` の読み取り専用3動詞で扱い、中核仮説を実データで検証。
- Codex への確認事項: Cosense export の実スキーマ（line-id 有無、リンク `[title]` 構文）。

## [2026-06-23 15:41] 作成 + 設計対話 ingest | grasp dev wiki を新規 scaffold し、llm-wiki での設計対話を founding pages に固定
- **由来**: nishio の llm-wiki 対話。「Cosense は複数人前提だが一人でも Markdown 集合より効く。"Co-" になる前の Scrapbox を CLI で扱える substrate が LLM に良い」→ design B を選択。
- **分業**: 本 wiki ＝ spec / 設計判断 / gotcha（Codex が読む context）、Codex ＝ 実装。
- **固定した founding pages**:
  - [[SPEC]] — CLI 動詞（read=近傍同梱 / backlinks=行つき / related=2-hop / wanted=赤リンク / write=グラフ自動更新 / transclude / rename=identity保持）＋ data model（page id / line-id / materialized backlinks）＋ 5 中核原理 ＋ Open Q。
  - [[why-not-scrapbox-clone]]（decisions/, 旧 why-design-B）— Scrapbox を Co-層 / グラフモデル層に分解、A（忠実clone, name=identity欠陥相続）vs B（あるべき姿, identity-without-name 追加）の fork で B 採用。用途は（あ）LLM-author 向け・人間UIなし。cosense-cli との区別。
- **次**: 永続化形式（既存 Markdown 互換 or 独自）の決定 → Codex に最小プロトタイプ（read / backlinks / wanted の 3 動詞、読み取り専用）を渡す。
- メタ: 親 llm-wiki の `LLM Wiki 設計のトレードオフ` 軸5（機械 vs 意味）× `名前ではなくIDで識別する設計`（identity-without-name）の収束として本プロジェクトが立った。
