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
- ページは**行ベース**。ページ間リンクは Cosense 記法 `[ページ名]`（単角括弧）。read 出力もこの原文のまま。
- 中核は **read=近傍同梱**: `grasp read <title>` 一発で、本文 ＋ **行レベル逆リンク** ＋ **related（2-hop）** ＋ **そのページから出る未解決 target** が一緒に返る。ブラウザで関連 pane を眺める所作を1コールで得る。
- オフライン・即時（store があれば各コマンド sub-second）。

### グラフの読み解き方（Tips）

- キーワード検索だけに頼らず、**関連リスト・逆リンクを眺めて辿る**。単独ページでは見えない文脈が浮かぶ。
- 被リンク数（read の `links_to_this` / `link-stats`）が大きいページや target は、実質**カテゴリ的ハブ**として機能している。
- **本文の無い（page なし）観念的タイトルでも、意味は他ページの文脈に宿る**。`read`/`backlinks`/`related` は page が無い target でも、それを参照している source pages を返す。「本文なし＝無意味」ではない。
  - 例: 本文ページが無い target でも、多数のページから参照されていれば `grasp read <target>` で参照側の文脈を読める。

## こういう時はこうする

### タイトルが分かっている / そのページを軸に調べたい
→ `grasp read <title>`。本文＋逆リンク＋related＋未解決を一括取得。これが基本。逆リンクや related が切れていたら `--backlinks-limit` 等で広げる。

### テーマ・問いから探す（タイトル未確定）
→ `grasp search <query>` で**本文行**を検索（行レベル hit）し、良さそうな `source_title` を `grasp read` で開く。タイトルの当たりが付くなら `grasp suggest <partial>`（タイトル補完）。
- `search` はリテラル substring 検索。OR 検索は無いので、語を分けて複数回叩く。

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

## verb 一覧（snapshot — 詳細は各 `grasp <cmd> --help`）

| verb | 用途 |
| --- | --- |
| `read <title>` | 本文＋逆リンク＋related＋未解決を近傍同梱で（基本の入口） |
| `search <query>` | 本文行を検索、行レベル hit |
| `suggest <partial>` | タイトル補完 |
| `backlinks <title>` | 行レベル逆リンク（page なし target も） |
| `related <title>` | 2-hop ページ / page なし target の source pages |
| `link-stats <title>` | incoming link count と 0/1/N |
| `unresolved` | 未解決 target の rank view（TODO ではない） |
| `peek <title>` | 本文行のみ |
| `stats` | store の状態・件数 |
| `export-ai <title>` | Export for AI 風の単一テキスト bundle（alias `export-for-ai`） |
| `sync <url>` | hosted 差分取り込み（保守） |

## 実行方法

- 形式: **`grasp <verb> ...`**。store は既定では home に1個 `~/.grasp/grasp.sqlite`（global default）。
- 一回限りのユーザ指定 JSON を読む時は、必要に応じて `--store <task-local.sqlite>` を使い、既定 store を上書きしない。
- 未インストール環境では grasp repository root から `python3 -m grasp <verb>`（`pip install -e <grasp-repo>` 済みなら `grasp` が PATH）。
- `grasp import --cosense <json>` で Cosense JSON export を import する。既存 store があってもそのまま置き換える。以降は sub-second。別パスは `--store` / `$GRASP_STORE`、別 home は `$GRASP_HOME`。
- 機械可読が要る時は `--json`。**root option なので verb の前**に置く: `grasp --json read "ページタイトル" --backlinks-limit 3`。`--store` も同様に verb の前。
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
