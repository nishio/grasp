# grasp

**LLM のための、ローカルなグラフ知識ストア。** フラットな Markdown の束を渡すより、自動双方向リンク＋近傍同梱で読めるグラフのほうが LLM には効く。

`grasp` は、エクスポートした Scrapbox / Cosense プロジェクト、または既存の Markdown フォルダを取り込み、**AI が CLI から「ページ＋その近傍」を 1 コールで読む** read-only ツールです。ブラウザでページを開くと関連ペインが一望に入るあの体験を、Web UI なしに、オフラインで、サブ秒で返します。

**主たる使い方は、あなたが `grasp` コマンドを叩くことではありません。** AI エージェント（Claude Code 等）に **Agent Skill としてインストール**しておき、あなたは自然言語で AI に問いかけます——「あの概念について自分は何を書いたっけ」「これに関連するページは」「どこで言及した」。AI が裏で `grasp` を呼び、逆リンク・related・未解決ターゲットごとグラフを辿って答えます。CLI は **AI が使う基盤**であって、人間が直接覚える前提ではありません（もちろん直接叩くこともできます）。

---

## なぜ Markdown の束ではないのか

Markdown フォルダでは、リンクは「ファイル内のテキスト」でしかなく、**逆リンクはどこにも保存されません**。「このページは誰から参照されているか」を知るには毎回フォルダ全体を grep するか、相手ファイルに手で書き戻すしかない。

`grasp` はリンクを**グラフのエッジ**として保持します。だから—

- **逆リンクは O(1)** — 同じエッジを逆から読むだけ。「維持」という概念が消える。
- **read = 近傍同梱** — `grasp read <title>` は本文だけでなく、**行レベルの逆リンク**・**related（2-hop）ページ**・**そのページから出ている未解決リンク（赤リンク）** を一体で返す。`--related-snippets` を付けると related/source ページの先頭行も同梱できます。これが grasp の中核で、ただの「グラフ DB を CLI で叩く」との差です。
- **本文が無い概念にも意味が宿る** — 参照されているのに本文ページが無いタイトル（例: よく出てくる概念名）も、それを参照する複数ページの文脈ごと読めます。

> 出自: nishio の Scrapbox / Cosense 運用経験と LLM Wiki 設計対話から生まれました。Scrapbox の「自動双方向リンク・2-hop・行リンク・赤リンク」というグラフモデルを、多人数協調の層を削いで、CLI から AI が"体験"できるようにしたものです。

---

## v1 のスコープ

**v1 = エクスポート済み Scrapbox / Cosense JSON と read-only Markdown mirror を AI が CLI から高速に読む read-only ツール。**

書き込み（`write` / `rename`）は v1 には含まれません（[Roadmap](#roadmap) 参照）。Markdown mirror の最小版は `grasp import --markdown <folder>` で使えます。frontmatter `title` / `id` / `aliases` / `tags` を読み、無い場合は file stem を title とし、`[[wikilink]]` と `#tag` を edge として index します。

---

## インストール

Python **3.10 以上**。**依存パッケージはゼロ**（標準ライブラリの `sqlite3` のみ使用）。

**1. CLI を入れる**（AI が呼ぶ基盤を PATH に通す）

```bash
git clone https://github.com/nishio/grasp.git
cd grasp
pip install -e .          # `grasp` コマンドが PATH に入る
```

`pip` がシステム Python に弾かれる環境（PEP 668）では `pipx install` か仮想環境を使ってください。

**2. AI エージェントに Skill を登録する**（主たる使い方）

Claude Code なら、リポジトリ内の Skill をユーザ skill ディレクトリに symlink するだけで全プロジェクトで自動発火します。

```bash
ln -s "$PWD/skills/grasp" ~/.claude/skills/grasp
```

これで「あの概念について何を書いたっけ」等と話しかけたとき、AI が `grasp` を使うべき場面を自分で判断し、CLI を叩いてグラフを辿ります。Skill が「いつ・どう使うか」を持ち、`grasp <verb> --help` が各コマンドの仕組みの正典です（[skills/grasp/SKILL.md](skills/grasp/SKILL.md)）。

> 直接 CLI を試したいだけなら、Skill 登録は省略可。未インストールでも、リポジトリ直下から `python3 -m grasp <verb> ...` で同じことができます。

---

## クイックスタート

### 1. 自分の Scrapbox / Cosense プロジェクトを JSON エクスポートする

プロジェクトの **Settings → Page Data → Export Pages** から JSON をダウンロードします。**ページのメタデータを含める設定を ON** にしてください（更新日時・閲覧数を使ったランキングに効きます）。`your-project.json` のようなファイルが手に入ります。

### 2. グラフストアに取り込む

```bash
grasp import --cosense your-project.json
```

`~/.grasp/grasp.sqlite` に SQLite のグラフストアが構築されます（数万ページで十数秒程度）。以降のコマンドはこのストアを読むだけなので**サブ秒**で返ります。import した JSON はストア横の `grasp.sqlite.imports/` に復旧用コピーとして保持され、古い schema の store を通常コマンドで開いた時はそこから自動再構築します。hosted の最新差分は引き続き `sync` の責務です。

同じ SQLite store には複数の Cosense project を入れられます。project 名は export JSON の `name` を既定で使い、同名 project を再 import した場合はその project namespace だけを置き換えます。複数 project が入っている store を読む時は `--project` を指定します。

```bash
grasp --project your-project read "<ページタイトル>"
```

管理者 export を取れない hosted project では、`cosense` CLI 経由で読める範囲だけを partial corpus として seed できます。これは full export の代替入口で、結果の逆リンク・related・未解決ターゲットは**取得済み subset 内**の事実です。

```bash
grasp --project project:slice acquire https://scrapbox.io/project/ --search "[your.icon]" --limit 100
grasp --project project:crawl acquire https://scrapbox.io/project/ --from-page "<起点ページ>" --depth 1 --limit 100
```

`--project` を省略した場合、既存の full export project を誤って潰さないよう local namespace は `<remote-project>:acquire` になります。

Markdown フォルダを read-only mirror として index する場合:

```bash
grasp import --markdown ~/Notes --project notes
grasp --project notes read "<ファイル名から .md を除いた title>"
```

frontmatter `title` があれば page title に使い、`aliases` と file stem は link 解決候補になります。既存ファイルへは書き戻しません。
再 import 時は manifest を見て、本文だけ変わったファイルを page 単位で差分更新します。frontmatter `title` / `id` / `aliases` や file set が変わった時は、安全のため project 全体を再構築します。

### 3. AI に聞く

Skill を登録してあれば、あとは AI エージェントに自然言語で話しかけるだけです。

> 「グラフ理論について自分は何を書いた？ 関連ページも辿って」

AI が `grasp read` / `search` / `backlinks` などを必要に応じて呼び分け、本文・逆リンク（行つき）・related ページ・未解決ターゲットを辿って答えます。あなたはタイトルやコマンドを覚える必要はありません。

自分で直接叩くなら:

```bash
grasp read "<ページタイトル>"
```

本文に加えて、逆リンク（行つき）・related ページ・未解決ターゲットがまとめて返ります。related ページの冒頭も同じ出力で見たい時は `grasp read "<ページタイトル>" --related-snippets` を使います。検索 hit の周辺だけ読みたい時は、完全 `line_id` を使って `grasp read --around-line <line-id> --line-context 5` とします。人間が出力フォーマットを覚える前提ではないので、詳細は使う直前の `grasp read --help` と、機械可読に見るための `grasp read "<ページタイトル>" --json` に寄せます。

---

## コマンド一覧

ふだんは AI が裏で呼び分けるものですが、直接叩くこともできます。各コマンドの引数・戻り値・例は、使う直前に **`grasp <verb> --help`** が正典です（ここは概要のみ）。

| verb | 用途 |
| --- | --- |
| `read <title>` | 本文＋逆リンク＋related＋未解決を**近傍同梱**で返す（`--related-snippets` で related/source ページ冒頭も同梱、`--around-line <line-id>` で行周辺だけ読む） |
| `search <query>` | 本文行を検索。既定は空白も含めて入力文字列そのものの line substring。`--mode boolean` で AND/OR/NOT、`--scope line|page` で行単位/ページ単位を切替。0件時は NFKC/長音ゆれの normalized fallback を試す |
| `suggest <partial>` | タイトルの部分一致補完 |
| `backlinks <title>` | 行レベルの逆リンク（本文の無いターゲットにも効く） |
| `related <title>` | 既存ページなら 2-hop ページ、本文の無いターゲットならそれを参照する source ページ |
| `path <A> <B>` | 2つのページ / 未解決ターゲットがリンクグラフ上でどう繋がるかを短い経路で見る。経路なしでも related / backlinks などの recovery hints を返す |
| `link-stats <title>` | incoming リンク数と 0 / 1 / N（none / single / multi）区別 |
| `unresolved` | 本文の無いリンクターゲットをランク付けして一覧（後述の注意あり） |
| `peek <title>` | 本文行のみ（近傍は返さない） |
| `export-ai <title>` | main + 1-hop / 2-hop ページ本文を 1 テキストへ展開（alias `export-for-ai`） |
| `stats` | ストアの件数・更新日時などを確認 |
| `import --cosense <json>` / `import --markdown <folder>` | Cosense JSON エクスポート、または read-only Markdown folder mirror を project namespace に取り込み・再構築 |
| `acquire <project-url>` | 管理者 export なしで hosted Cosense から読めるページを partial corpus として取得（要 `cosense` CLI） |
| `sync <project-url>` | hosted Cosense の最近更新ページを差分取り込み（保守用・要 `cosense` CLI install + 認証） |

> `unresolved` は「埋めるべき TODO リスト」ではありません。多くのページから参照される未解決ターゲットは、本文が無くても**他ページの文脈で既に意味を持つ概念ノード**です。次に書く候補や調査の起点として眺めるのはよいですが、全部を埋めるべき穴とは解釈しないでください。

---

## ストアと環境変数

- ストアは home に 1 個（**`~/.grasp/grasp.sqlite`**）。AI が単一で所有する想定なので、**どの作業ディレクトリからも動きます**。
- 1つの store に複数 project を保持できます。`grasp import --cosense <json>` は export の `name` を project namespace として使い、同名 project だけを置き換えます。project 名を変える場合は `grasp import --project <name> --cosense <json>`。
- 複数 project がある store で読む時は `--project <name>` / `$GRASP_PROJECT` を指定してください。project が1つだけなら省略できます。
- パスを変えたいとき:
  - `--store PATH` / `$GRASP_STORE` … SQLite ストアの場所
  - `--project NAME` / `$GRASP_PROJECT` … 読み書き対象の project namespace
  - `$GRASP_HOME` … home 自体（既定 `~/.grasp`）を差し替え
- text 出力の `line-id` は既定で `P1:0` のような実行内ローカル別名に短縮され、先頭付近に `P1=<page-id>` の legend が出ます。安定した完全 ID が必要なら `--json`、人間向け text のまま完全 ID を見たい時は `--full-ids`。
- `--store` / `--project` は verb の前に置きます。`--json` と `--full-ids` は root option ですが、agent が自然に末尾へ置くことが多いため verb 後にも置けます:

  ```bash
  grasp --project your-project read "<ページタイトル>" --backlinks-limit 5 --json
  grasp read "<ページタイトル>" --full-ids
  ```
- 空白や記号を含むタイトル・クエリはシェルでクォートしてください（`"..."`）。
- 機械可読出力が必要なら `--json`。返るキーは各 `grasp <verb> --help` に記載。

---

## Roadmap

- **Markdown / Obsidian 互換性の拡張** — 最小の read-only mirror と content-only 差分 index は実装済み。first H1 title resolution / Obsidian block refs / より細かい alias-aware incremental rebuild などは今後の拡張。
- **書き込み層（`write` / `rename`）** — Scrapbox / Cosenseを使っている人がAIから書くときはcosense-cliで書くことを想定しています。これは将来的にCosenseユーザでない人 or オンラインのCosenseに書くのではなくローカルに閉じて欲しいケース をサポートする目的です。
- **ベクトル検索** — 文字列一致だけでなく、意味の近さで関連を辿る。

スコープ外: リアルタイム多人数編集・同期・共有/権限・Web UI。単一ユーザ＋AI には不要で、これらを削ぎ落とすのが grasp の核です。

## License

MIT
