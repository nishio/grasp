---
name: grasp
description: >-
  ユーザが指定した Scrapbox/Cosense JSON export、または既に import 済みの grasp local store を
  CLI から調べるスキル。ページ本文だけでなく、行レベル逆リンク、2-hop related、未解決 target を
  近傍同梱で読む。ユーザが「この JSON を読んで」「自分の Cosense export から探して」
  「この概念への言及はどこか」「関連ページは何か」「本文のない概念ハブを見たい」などと依頼した時に使う。
---

# grasp Skill 手順書

`grasp` CLI で、ユーザが指定した Scrapbox/Cosense JSON export から作った local グラフストアを読む。source JSON / hosted project に対しては **read-only**。`import` は SQLite index を作るだけで、元 JSON は変更しない。

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

## grasp とはどういう物か

- Scrapbox/Cosense の JSON export を取り込み、SQLite graph store にしたもの。
- ページは**行ベース**。ページ間リンクは Cosense 記法 `[ページ名]`（単角括弧）と `#tag`。read 出力もこの原文のまま。
- 中核は **read=近傍同梱**: `grasp read <title>` 一発で、本文 ＋ **行レベル逆リンク** ＋ **related（2-hop）** ＋ **そのページから出る未解決 target** が一緒に返る。`--related-snippets` を付けると related/source ページの先頭行も同梱でき、ブラウザで関連 pane を眺める所作を1コールで得る。
- オフライン・即時（store があれば各コマンド sub-second）。

### グラフの読み解き方（Tips）

- キーワード検索だけに頼らず、**関連リスト・逆リンクを眺めて辿る**。単独ページでは見えない文脈が浮かぶ。
- 被リンク数（read の `links_to_this` / `link-stats`）が大きいページや target は、実質**カテゴリ的ハブ**として機能している。
- **本文の無い（page なし）観念的タイトルでも、意味は他ページの文脈に宿る**。`read`/`backlinks`/`related` は page が無い target でも、それを参照している source pages を返す。「本文なし＝無意味」ではない。
  - 例: 本文ページが無い target でも、多数のページから参照されていれば `grasp read <target>` で参照側の文脈を読める。

## こういう時はこうする

### タイトルが分かっている / そのページを軸に調べたい
→ `grasp read <title>`。本文＋逆リンク＋related＋未解決を一括取得。これが基本。related の見出しだけでは足りず冒頭本文も同時に見たい時は `--related-snippets`（既定 5 行、`--related-snippet-lines N` で調整）。逆リンクや related が切れていたら `--backlinks-limit` 等で広げる。

### テーマ・問いから探す（タイトル未確定）
→ `grasp search <query>` で**本文行**を検索（行レベル hit）し、良さそうな `source_title` を `grasp read` で開く。タイトルの当たりが付くなら `grasp suggest <partial>`（タイトル補完）。
- `search` は単一語ならリテラル substring 検索。空白区切りの複数語は page 単位 AND になり、同じ行でなく同じページに全語があれば該当行を返す。OR 検索はまだ無い。
- literal で0件の時は、NFKC と長音ゆれ（例: `ﾕｰｻﾞﾃｽﾄ` / `ユーザーテスト` / `ユーザテスト`）を緩く合わせる normalized fallback が走る。text 出力では該当行に `[normalized]` が付き、JSON では `match_mode: "normalized"` になる。大規模 store では完全なかな/カナ変換 scan は行わない。

### 長大ページ・ログページを読む
→ 親 conversation に長い `read` 出力を直接持ち込まない。まず探索用 subagent / Explore agent に任せ、subagent 側で `search` / `peek` / limit 付き `read` を使って読む。
- 親に返すのは、結論・根拠ページ・該当 `line_id`・必要な短い引用/要約だけにする。中間の大量 stdout、長大本文、網羅的検索結果は subagent context に閉じ込める。
- CLI 側は要約しない。grasp は LLM 依存の summarizer ではなく、行 ID 付きの deterministic graph reader。要約と取捨選択は Skill / subagent の責務。
- 長大ページを直接開く必要がある時も、先に `grasp search <query>` で hit line を見つけ、`grasp read <title> --line-limit <N>` などで範囲を絞る。親へ戻す時は再アクセスできる `source_title` と `line_id` を残す。

### 「この概念にどこで言及したか」
→ `grasp backlinks <title>`（`(source_title, line-id, 行テキスト)`）。`read` の Backlinks 節と同じものを単体で。page が無い概念にも効く。

### 「この概念と関連するページ」
→ `grasp related <title>`。existing page なら 2-hop ページ、page なし target ならそれを参照する source pages。

### 被リンクの濃さだけ知りたい / その概念が既出か
→ `grasp link-stats <title>`。incoming `link_count` と 0/1/N（none/single/multi）。

### まだ本文の無い「概念ハブ」を見渡したい
→ `grasp unresolved`。多くのページから参照されるのに本文ページが無い target を rank。
- **これは「書くべき TODO リスト」ではない**。多参照の未解決 target は、本文が無くても**他ページの文脈で既に意味を持つ概念ノード**。「次に書く候補」や調査の起点として眺めるのはよいが、全部を埋めるべき穴と解釈しない。

### 本文だけ見たい（近傍は不要）
→ `grasp peek <title>`。

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

`acquire` は対象 project namespace を置き換える（append しない）。既存 full export を誤って潰さないよう、`--project` 省略時の local namespace は `<remote-project>:acquire` になる。partial corpus の `backlinks` / `related` / `unresolved` は「取得済み subset 内」の結果であり、hosted project 全体の事実として答えない。`grasp stats` の Acquisition 節で coverage を確認する。

## verb 一覧（snapshot — 詳細は各 `grasp <cmd> --help`）

| verb | 用途 |
| --- | --- |
| `read <title>` | 本文＋逆リンク＋related＋未解決を近傍同梱で（`--related-snippets` で related/source ページ冒頭も同梱） |
| `search <query>` | 本文行を検索、単一語は line substring、複数語は page AND、0件時は NFKC/長音ゆれ fallback |
| `suggest <partial>` | タイトル補完 |
| `backlinks <title>` | 行レベル逆リンク（page なし target も） |
| `related <title>` | 2-hop ページ / page なし target の source pages |
| `link-stats <title>` | incoming link count と 0/1/N |
| `unresolved` | 未解決 target の rank view（TODO ではない） |
| `peek <title>` | 本文行のみ |
| `stats` | store の状態・件数 |
| `export-ai <title>` | Export for AI 風の単一テキスト bundle（alias `export-for-ai`） |
| `sync <url>` | hosted 差分取り込み（保守） |
| `acquire <url>` | admin export なしの hosted 部分取得 seed |

## 実行方法

- 形式: **`grasp <verb> ...`**。store は既定では home に1個 `~/.grasp/grasp.sqlite`（global default）。
- 1つの store に複数 project namespace を保持できる。`grasp import --cosense <json>` は export JSON の `name` を project 名として使い、同名 project だけを置き換える。project 名を明示する時は `grasp import --project <name> --cosense <json>`。
- 一回限りのユーザ指定 JSON を読む時は、必要に応じて `--store <task-local.sqlite>` を使い、既定 store に project を増やさない。
- 未インストール環境では grasp repository root から `python3 -m grasp <verb>`（`pip install -e <grasp-repo>` 済みなら `grasp` が PATH）。
- `grasp import --cosense <json>` で Cosense JSON export を import する。以降は sub-second。別パスは `--store` / `$GRASP_STORE`、別 home は `$GRASP_HOME`。
- import 済み JSON は store 横の `<store>.imports/` に復旧用コピーとして保持される。通常 command が古い schema の store を見つけた時は、復旧用コピーからサイレントに current schema へ再構築して続行する。`stats` は診断用なので自動再構築しない。hosted の最新差分は復旧後も `sync` の責務。
- 複数 project がある store で読む時は `grasp --project <name> read "ページタイトル"` のように project を指定する。project が1つだけなら省略可。
- 機械可読が要る時は `--json`。root option だが verb 後にも置ける: `grasp --project <name> read "ページタイトル" --backlinks-limit 3 --json`。`--store` / `--project` は verb の前。
- 空白・記号を含む title / query は shell でクォートする（`'...'`）。

## 回答の形式

- 情報源（ページタイトル）を示しながらユーザーの問いに直接答える。
- 本文の無い概念について答える時は「本文なし、関連 N ページの文脈から」と限界を明示する。
- 固定テンプレートは規定しない。

## hosted Cosense との使い分け

| | grasp（このスキル） | hosted Cosense / cosense CLI |
| --- | --- | --- |
| データ | ユーザ指定 JSON から作った local snapshot / local store（オフライン・即時） | hosted の生の最新状態 |
| 強み | 行レベル逆リンク・未解決 target 列挙・近傍同梱を1コール | hosted project の最新取得・編集 |
| 向く時 | export 済みデータをグラフで辿る／逆リンク・関連を厚く見る | 最新の hosted 状態が要る／hosted project に書き込む |

最新性が要らず「逆リンク・関連・未解決をグラフごと厚く読む」なら grasp。生の最新や hosted への書き込みが要るなら hosted 側の手段を使う。
