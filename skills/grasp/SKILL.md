---
name: grasp
description: >-
  nishio の Scrapbox/Cosense（「西尾泰和の外部脳」, 約2.6万ページ）を local・オフラインで調べるスキル。
  「〇〇について自分は何を書いた/考えたか」「この概念に関連するページ」「〇〇への言及（逆リンク）はどこか」
  「まだ本文を書いていない概念ハブ」等、nishio の蓄積知識をグラフごと辿りたい時に使う。
  grasp CLI で、ページを逆リンク・2-hop・未解決 target ごと（近傍同梱）読む。read-only。
---

# grasp Skill 手順書

`grasp` CLI で、nishio の Cosense export を取り込んだ local グラフストアを読む。**read-only**（書き込み verb は無い）。
hosted Cosense を生で操作したい時は `cosense` skill を使う（使い分けは末尾）。

各 verb の引数・戻り値スキーマ・例は、使う直前に **`grasp <cmd> --help`** を読む（このファイルには列挙しない）。

## grasp とはどういう物か

- nishio の Scrapbox（外部脳, 約25,791ページ / 72万行）を JSON export から取り込み、SQLite graph store にしたもの。
- ページは**行ベース**。ページ間リンクは Cosense 記法 `[ページ名]`（単角括弧）。read 出力もこの原文のまま。
- 中核は **read=近傍同梱**: `grasp read <title>` 一発で、本文 ＋ **行レベル逆リンク** ＋ **related（2-hop）** ＋ **そのページから出る未解決 target** が一緒に返る。ブラウザで関連 pane を眺める所作を1コールで得る。
- オフライン・即時（store があれば各コマンド sub-second）。

### グラフの読み解き方（Tips）

- キーワード検索だけに頼らず、**関連リスト・逆リンクを眺めて辿る**。単独ページでは見えない文脈が浮かぶ。
- 被リンク数（read の `links_to_this` / `link-stats`）が大きいページや target は、実質**カテゴリ的ハブ**として機能している。
- **本文の無い（page なし）観念的タイトルでも、意味は他ページの文脈に宿る**。`read`/`backlinks`/`related` は page が無い target でも、それを参照している source pages を返す。「本文なし＝無意味」ではない。
  - 例: `民主主義` は本文ページが無いが 82 links / 78 ページから参照される概念ノード。`grasp read 民主主義` で 78 ページ側の文脈が読める。

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

### hosted の最新を取り込みたい（保守作業）
→ `grasp sync <project-url>`（`cosense` CLI 経由で最近更新ページのみ差分 upsert。`--dry-run` あり）。認証が要る。通常の調査では不要。

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
| `sync <url>` | hosted 差分取り込み（保守） |

## 実行方法

- 形式: **`grasp <verb> ...`**（`pip install -e /Users/nishio/grasp` 済みで PATH にある）。未インストール環境では `/Users/nishio/grasp` から `python3 -m grasp <verb>`。
- store は `/Users/nishio/grasp/.grasp/grasp.sqlite`。無ければ最初のコマンドが `raw/nishio.json` から自動 build（約9秒）。以降は sub-second。
- repo 以外の cwd から使う時は store を絶対指定: `grasp --store /Users/nishio/grasp/.grasp/grasp.sqlite <verb>`（または環境変数 `GRASP_STORE` を同パスに）。
- 機械可読が要る時は `--json`。**root option なので verb の前**に置く: `grasp --json read 民主主義 --backlinks-limit 3`。`--store` / `--export` も同様に verb の前。
- 空白・記号を含む title / query は shell でクォートする（`'...'`）。

## 回答の形式

- 情報源（ページタイトル）を示しながらユーザーの問いに直接答える。
- 本文の無い概念について答える時は「本文なし、関連 N ページの文脈から」と限界を明示する。
- 固定テンプレートは規定しない。

## `cosense` skill との使い分け

| | grasp（このスキル） | cosense skill |
| --- | --- | --- |
| データ | local export の snapshot（オフライン・即時） | hosted の生の最新状態 |
| 強み | 行レベル逆リンク・未解決 target 列挙・近傍同梱を1コール | ベクトル検索・全文検索 recall・編集 |
| 向く時 | nishio の蓄積をグラフで辿る／逆リンク・関連を厚く見る | 最新の状態が要る／本文検索の recall を最大化／書き込む |

最新性が要らず「逆リンク・関連・未解決をグラフごと厚く読む」なら grasp。生の最新や強い本文検索が要るなら cosense。
