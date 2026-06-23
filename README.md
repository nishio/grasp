# grasp

**LLM のための、ローカルなグラフ知識ストア。** フラットな Markdown の束を渡すより、自動双方向リンク＋近傍同梱で読めるグラフのほうが LLM には効く。

`grasp` は、エクスポートした Scrapbox / Cosense プロジェクトを取り込み、**AI が CLI から「ページ＋その近傍」を 1 コールで読む** read-only ツールです。ブラウザでページを開くと関連ペインが一望に入るあの体験を、Web UI なしに、オフラインで、サブ秒で返します。

> 名前 `grasp` = **gra**ph × **s**cra**p**（box）＋「把握する / grasp」。

---

## なぜ Markdown の束ではないのか

Markdown フォルダでは、リンクは「ファイル内のテキスト」でしかなく、**逆リンクはどこにも保存されません**。「このページは誰から参照されているか」を知るには毎回フォルダ全体を grep するか、相手ファイルに手で書き戻すしかない。

`grasp` はリンクを**グラフのエッジ**として保持します。だから—

- **逆リンクは O(1)** — 同じエッジを逆から読むだけ。「維持」という概念が消える。
- **read = 近傍同梱** — `grasp read <title>` は本文だけでなく、**行レベルの逆リンク**・**related（2-hop）ページ**・**そのページから出ている未解決リンク（赤リンク）** を一体で返す。これが grasp の中核で、ただの「グラフ DB を CLI で叩く」との差です。
- **本文が無い概念にも意味が宿る** — 参照されているのに本文ページが無いタイトル（例: よく出てくる概念名）も、それを参照する複数ページの文脈ごと読めます。

> 出自: nishio の [Cosense（旧 Scrapbox）](https://scrapbox.io/) 運用と LLM Wiki 設計対話から生まれました。Scrapbox の「自動双方向リンク・2-hop・行リンク・赤リンク」というグラフモデルを、多人数協調（Co-）の層を削いで、CLI から AI が"体験"できるようにしたものです。設計の全体像は [wiki/SPEC.md](wiki/SPEC.md) を参照。

---

## v1 のスコープ

**v1 = エクスポート済み Scrapbox / Cosense JSON を AI が CLI から高速に読む read-only ツール。**

書き込み（`write` / `rename` / `transclude`）や Markdown / Obsidian フォルダの取り込みは v1 には含まれません（[Roadmap](#roadmap) 参照）。

---

## インストール

- Python **3.10 以上**。**依存パッケージはゼロ**（標準ライブラリの `sqlite3` のみ使用）。

```bash
git clone https://github.com/nishio/grasp.git
cd grasp
pip install -e .          # `grasp` コマンドが PATH に入る
```

`pip` がシステム Python に弾かれる環境（PEP 668）では `pipx install` か仮想環境を使ってください。インストールせずに動かすなら、リポジトリ直下から `python3 -m grasp <verb> ...` でも同じです。

---

## クイックスタート

### 1. 自分の Scrapbox / Cosense プロジェクトを JSON エクスポートする

プロジェクトの **Settings → Page Data → Export Pages** から JSON をダウンロードします。**ページのメタデータを含める設定を ON** にしてください（更新日時・閲覧数を使ったランキングに効きます）。`your-project.json` のようなファイルが手に入ります。

### 2. グラフストアに取り込む

```bash
grasp import --cosense your-project.json
```

`~/.grasp/grasp.sqlite` に SQLite のグラフストアが構築されます（数万ページで十数秒程度）。以降のコマンドはこのストアを読むだけなので**サブ秒**で返ります。

### 3. ページを近傍ごと読む

```bash
grasp read "<ページタイトル>"
```

本文に加えて、逆リンク（行つき）・related ページ・未解決ターゲットがまとめて返ります。

---

## `read` が返すもの（近傍同梱）

```
$ grasp read "<ページタイトル>"

# <ページタイトル>
id: 59285cf9ba093700118fa22e
views: 3825
lines: 124
links_to_this: 78 from 73 pages (multi)

## Lines
59285cf9...:0  <ページタイトル>
59285cf9...:1  本文の各行。ページ内リンクは [別のページ] 記法。
...

## Backlinks
- 別のページA 6436ac...:24: … <ページタイトル> について触れた行 …
- 別のページB 5a712d...:17: … ここでも言及している行 …

## Related 2-hop
- 近いページC
- 近いページD

## Unresolved Targets From This Page
- ある概念 (links 3, pages 3, views 3825)
  - <ページタイトル> 59285cf9...:53: … [ある概念] を含む行 …
```

逆リンクは「ページ単位」ではなく **`(ページ, 行ID, 行テキスト)`** で返ります。AI は全文を grep せず、**文脈の行だけ**を安く受け取れます。本文がまだ無いターゲットを `read` した場合は、`## Lines` の代わりにそれを参照している source ページ群が返ります。

---

## コマンド一覧

各コマンドの引数・戻り値・例は、使う直前に **`grasp <verb> --help`** が正典です（ここは概要のみ）。

| verb | 用途 |
| --- | --- |
| `read <title>` | 本文＋逆リンク＋related＋未解決を**近傍同梱**で返す（基本の入口） |
| `search <query>` | 本文行を検索し、行レベルのヒットを返す |
| `suggest <partial>` | タイトルの部分一致補完 |
| `backlinks <title>` | 行レベルの逆リンク（本文の無いターゲットにも効く） |
| `related <title>` | 既存ページなら 2-hop ページ、本文の無いターゲットならそれを参照する source ページ |
| `link-stats <title>` | incoming リンク数と 0 / 1 / N（none / single / multi）区別 |
| `unresolved` | 本文の無いリンクターゲットをランク付けして一覧（後述の注意あり） |
| `peek <title>` | 本文行のみ（近傍は返さない） |
| `export-ai <title>` | main + 1-hop / 2-hop ページ本文を 1 テキストへ展開（alias `export-for-ai`） |
| `stats` | ストアの件数・スキーマ状態 |
| `import --cosense <json>` | Cosense JSON エクスポートからストアを構築（`--force` で置き換え） |
| `sync <project-url>` | hosted Cosense の最近更新ページを差分取り込み（保守用・要認証） |

> `unresolved` は「埋めるべき TODO リスト」ではありません。多くのページから参照される未解決ターゲットは、本文が無くても**他ページの文脈で既に意味を持つ概念ノード**です。次に書く候補や調査の起点として眺めるのはよいですが、全部を埋めるべき穴とは解釈しないでください。

---

## ストアと環境変数

- ストアは home に 1 個（**`~/.grasp/grasp.sqlite`**）。AI が単一で所有する想定なので、**どの作業ディレクトリからもフラグ無しで動きます**。
- パスを変えたいとき:
  - `--store PATH` / `$GRASP_STORE` … SQLite ストアの場所
  - `$GRASP_HOME` … home 自体（既定 `~/.grasp`）を差し替え
  - `--export PATH` / `$GRASP_EXPORT` … 自動リビルド用の JSON エクスポート
- **グローバルオプション（`--json` / `--store` / `--export`）は verb の前**に置きます:

  ```bash
  grasp --json read "<ページタイトル>" --backlinks-limit 5
  ```
- 空白や記号を含むタイトル・クエリはシェルでクォートしてください（`"..."`）。
- 機械可読出力が必要なら `--json`。返るキーは各 `grasp <verb> --help` に記載。

---

## Claude Code / AI エージェントから使う

`grasp` は CLI ＋ [Agent Skill](skills/grasp/SKILL.md) として届けることを想定しています。Skill 側が「いつ・どう使うか」を持ち、`grasp <verb> --help` が各コマンドの仕組みの正典です。PATH に `grasp` があれば Skill は中身の実装言語を知らずに使えます。

---

## Roadmap

v1（read-only ミラー）の先に、設計上は次を見据えています（[wiki/SPEC.md](wiki/SPEC.md) / [wiki/decisions/](wiki/decisions/)）。**まだ v1 には入っていません。**

- **Markdown / Obsidian フォルダの取り込み** — Cosense を持たない人向けの入口。フォルダを read-only の indexed mirror として取り込む。
- **書き込み層（`write` / `rename` / `transclude`）** — `[[X]]` を書けば逆リンクが自動で立つ。`rename` してもリンクが id を指すので**切れず、参照文の文意も汚れない**（name=identity 問題の解消）。
- **全文検索の高速化**（SQLite FTS5）・**vector 検索**。

スコープ外（"before Co-"）: リアルタイム多人数編集・CRDT 同期・presence・共有/権限・Web UI。単一ユーザ＋AI には不要で、これを削ぐのが grasp の核です。

---

## ドキュメント

- [wiki/SPEC.md](wiki/SPEC.md) — CLI サーフェスとデータモデルの source of truth
- [wiki/decisions/](wiki/decisions/) — なぜこの形か（設計判断の記録）
- [skills/grasp/SKILL.md](skills/grasp/SKILL.md) — AI エージェント向けの使い方
