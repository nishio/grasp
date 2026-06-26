# grasp

**LLM のための、ローカルなグラフ知識ストア。** フラットな Markdown の束を渡すより、自動双方向リンク＋近傍同梱で読めるグラフのほうが LLM には効く。

`grasp` は、エクスポートした Scrapbox / Cosense プロジェクト、または既存の Markdown フォルダを取り込み、**AI が CLI から「ページ＋その近傍」を 1 コールで読む** ツールです。ブラウザでページを開くと関連ペインが一望に入るあの体験を、Web UI なしに、オフラインで、サブ秒で返します。read surface は stable、Markdown-backed project の append-only authoring は alpha です。

**主たる使い方は、あなたが `grasp` コマンドを叩くことではありません。** AI エージェント（Claude Code 等）に **Agent Skill としてインストール**しておき、あなたは自然言語で AI に問いかけます——「あの概念について自分は何を書いたっけ」「これに関連するページは」「どこで言及した」。AI が裏で `grasp` を呼び、逆リンク・related・未解決ターゲットごとグラフを辿って答えます。CLI は **AI が使う基盤**であって、人間が直接覚える前提ではありません（もちろん直接叩くこともできます）。

---

## なぜ Markdown の束ではないのか

Markdown フォルダでは、リンクは「ファイル内のテキスト」でしかなく、**逆リンクはどこにも保存されません**。「このページは誰から参照されているか」を知るには毎回フォルダ全体を grep するか、相手ファイルに手で書き戻すしかない。

`grasp` はリンクを**グラフのエッジ**として保持します。だから—

- **逆リンクは O(1)** — 同じエッジを逆から読むだけ。「維持」という概念が消える。
- **read = 近傍同梱** — `grasp read <title>` は本文だけでなく、**行レベルの逆リンク**・**related（2-hop）ページ**・**そのページから出ている未解決リンク（赤リンク）** を一体で返す。`--related-snippets` を付けると related/source ページの先頭行、または `--related-snippet-mode edge` で関連根拠のリンク行も同梱できます。これが grasp の中核で、ただの「グラフ DB を CLI で叩く」との差です。
- **本文が無い概念にも意味が宿る** — 参照されているのに本文ページが無いタイトル（例: よく出てくる概念名）も、それを参照する複数ページの文脈ごと読めます。

> 出自: nishio の Scrapbox / Cosense 運用経験と LLM Wiki 設計対話から生まれました。Scrapbox の「自動双方向リンク・2-hop・行リンク・赤リンク」というグラフモデルを、多人数協調の層を削いで、CLI から AI が"体験"できるようにしたものです。

---

## v1 のスコープ

**v1 = エクスポート済み Scrapbox / Cosense JSON と Markdown mirror を AI が CLI から高速に読む stable read line。**

汎用の `write` / `rename` / replayable native authority は v1 の stable surface には含まれません（[Roadmap](#roadmap) 参照）。ただし Markdown-backed project の fast-path dogfood 用に、`append-section` / `append-log` の append-only authoring alpha があります。Markdown mirror の最小版は `grasp import --markdown <folder>` で使えます。frontmatter `title` / `id` / `aliases` / `tags` を読み、title が無い場合は first H1、さらに無ければ file stem を title とし、`[[wikilink]]` と `#tag` を edge として index します。

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

プロジェクトの **Settings → Page Data → Export Pages** から JSON をダウンロードします。**ページのメタデータを含める設定は ON 推奨**です（更新日時・閲覧数を使ったランキングに効きます）。古い export などで行が metadata なしの plain string になっていても import できますが、その行の作成日時・更新日時・userId は空になります。`your-project.json` のようなファイルが手に入ります。

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
同じ acquisition criteria（project URL、seed 条件、sort、limit など）で再実行した場合、前回の `criteria_fingerprint` / candidate updated range / page manifest を store metadata に残しているため、hosted metadata の `updated` が変わっていないページは local store から再利用し、不要な `readPage` を避けます。`grasp stats` の Acquisition 節で前回条件と `remote_fetched` / `reused` を確認できます。
取得候補が全て失敗しても partial acquisition の結果として exit 0 で返ることがあります。その場合は JSON/text の `diagnostic.type=all_failed` と `failed_pages[].error_class`（例: `command-env`, `command-not-found`, `permission`, `page-not-found`）を確認してください。

既存 store 内の `[/other-project/page]` 参照を seed bibliography として使う時は、`search "[/"` ではなく target-aware な抽出を使います。

```bash
grasp --project your-project cross-project-refs --semantic-only --limit 20
grasp --project your-project cross-project-refs --semantic-only --limit 20 --seed-dir /tmp/grasp-seeds
grasp --project your-project cross-project-acquire --limit 5 --seed-limit 10 --dry-run
```

`.icon` や project root refs を分類して除外できるので、cross-project acquisition の seed 候補を line text workaround なしで見られます。`--seed-dir` を付けると target project ごとに seed file を書き、対応する `grasp --project <project>:semantic acquire ... --seed-file ...` command も出力します。
実際に複数 project を取得する時は、`cross-project-acquire` を使うと semantic seed titles から `<project>:semantic` namespace へ順に取得し、project ごとの fetched / failed / diagnostic / reciprocal refs / top internal links を bounded summary として返します。まず `--dry-run` で計画を確認してください。

Markdown フォルダを read-only mirror として index する場合:

```bash
grasp import --markdown ~/Notes --project notes
grasp import --markdown ~/Notes --project notes --markdown-exclude-dir raw
grasp --project notes read "<ファイル名から .md を除いた title>"
```

frontmatter `title` があれば page title に使い、無ければ first H1、さらに無ければ file stem を使います。`aliases` と file stem は link handle になります。duplicate title / alias は import 全体を止めず、`read <handle>` の候補として返ります。duplicate frontmatter `id` だけは identity 衝突なので error です。既存ファイルへは書き戻しません。
`--markdown-exclude-dir raw` のように directory basename を指定すると、重い raw/generated directory を再帰 import から外せます。`source/` は raw 由来の digest として保持され、通常の content と同じく link graph に入ります。再 import 時は manifest を見て、本文だけ変わったファイルを page 単位で差分更新します。frontmatter `title` / first H1 / `id` / `aliases` / graph role / exclude dirs や file set が変わった時は、安全のため project 全体を再構築します。
同じ visible handle が複数 page identity に対応する場合、`grasp read <handle>` は片方を勝手に選ばず候補を返します。`grasp backlinks <handle>` は曖昧な handle 自体への incoming lines を主に返し、候補 page ごとの確定 backlinks も分けて返します。`grasp related <handle>` も曖昧 handle への source pages と候補 page ごとの related を分けて返します。`grasp ambiguities` は store 全体または selected project の曖昧 handle を一覧します。候補から選ぶ時は `grasp read --page-id <id>`、Markdown mirror の source path で選ぶ時は `grasp read --path source/Digest.md` を使います。

`wikis.yaml` のような registry で複数 Markdown wiki を管理している場合は、各 entry を別 project namespace としてまとめて import できます。各 wiki の失敗は全体を止めず diagnostics に集約され、import 後の ambiguity summary も同じ結果で確認できます。

```bash
grasp import-forest /Users/nishio/llm-wiki/wikis.yaml --markdown-exclude-dir raw
```

### 3. AI に聞く

Skill を登録してあれば、あとは AI エージェントに自然言語で話しかけるだけです。

> 「グラフ理論について自分は何を書いた？ 関連ページも辿って」

AI が `grasp read` / `search` / `backlinks` などを必要に応じて呼び分け、本文・逆リンク（行つき）・related ページ・未解決ターゲットを辿って答えます。あなたはタイトルやコマンドを覚える必要はありません。

自分で直接叩くなら:

```bash
grasp read "<ページタイトル>"
```

本文に加えて、逆リンク（行つき）・related ページ・未解決ターゲットがまとめて返ります。related ページの冒頭も同じ出力で見たい時は `grasp read "<ページタイトル>" --related-snippets`、関連を生んだリンク行を見たい時は `--related-snippet-mode edge` を使います。検索 hit の周辺だけ読みたい時は、完全 `line_id` を使って `grasp read --around-line <line-id> --line-context 5` とします。名前が曖昧な場合は候補が返るので、必要なら `--page-id` / `--path` で identity を選びます。人間が出力フォーマットを覚える前提ではないので、詳細は使う直前の `grasp read --help` と、機械可読に見るための `grasp read "<ページタイトル>" --json` に寄せます。

---

## コマンド一覧

ふだんは AI が裏で呼び分けるものですが、直接叩くこともできます。各コマンドの引数・戻り値・例は、使う直前に **`grasp <verb> --help`** が正典です（ここは概要のみ）。

| verb | 用途 |
| --- | --- |
| `read <title>` | 本文＋逆リンク＋related＋未解決を**近傍同梱**で返す。曖昧な handle は候補を返し、`--page-id` / `--path` で identity を選べる（`--related-snippets` で related/source ページ冒頭や `--related-snippet-mode edge` の根拠行を同梱、`--around-line <line-id>` で行周辺だけ読む） |
| `search <query>` | 本文行を検索。既定は空白も含めて入力文字列そのものの line substring。`--mode boolean` で AND/OR/NOT、`--scope line|page` で行単位/ページ単位を切替。`--context N` で各 hit の前後 N 行を同梱。0件時は NFKC/長音ゆれの normalized fallback を試す |
| `mentions <query>` | literal query の裸言及を、link span 外の occurrence として数える。page already has exact link / query-containing link / no link handle で分類し、come-from 昇格候補 score を返す。`--unlinked` で no link handle の page だけに絞る |
| `co-links <query>` | query を含む行で同時に出る internal links を rank し、巨大 hub の slice handle を見つける。既定 `--rank slice` は query-containing target title を後ろへ回し、`--rank raw` で count order を見る |
| `cross-project-spread <title>` | normalized title が各 project で materialized page / ambiguous handle / unresolved target / incoming link としてどれだけ広がるかを weak signal として返す。page identity は merge しない |
| `cross-project-spreads` | normalized handle を project spread で rank し、森を跨ぐ weak signal を seed title なしに発見する。structural-name / numeric-only / artifact-only は label して下位 band に回す |
| `cross-project-refs` | Cosense shorthand `[/project/page]` を parsed link target として抽出し、semantic / `.icon` / project root / self-project に分類して project 別に rank。`--semantic-only` で acquisition seed 向けに絞り、`--seed-dir` で project 別 seed file と acquire command を生成 |
| `cross-project-acquire` | `cross-project-refs --semantic-only` の seed titles を使い、複数 target project を `<project>:semantic` namespace に一括 partial acquire。`--dry-run` で計画だけ返せ、実行後は reciprocal refs / top internal links も返す |
| `gather <query>` | link stats・裸言及 summary・co-link slices・backlinks・次の recipe を bounded bundle として返す。returned / total / omitted は row 単位で明示。`--budget` は近似 row limit |
| `suggest <partial>` | タイトル候補を fuzzy / 部分一致で補完。既定 fuzzy は長文タイトルに対し、空白区切り断片や詰めた文字順序でも候補を返す。厳密部分一致は `--mode substring` |
| `backlinks <title>` | 行レベルの逆リンク（本文の無いターゲットにも効く） |
| `related <title>` | 既存ページなら 2-hop ページ、本文の無いターゲットならそれを参照する source ページ。曖昧 handle は handle source pages と候補 page ごとの related を分けて返す |
| `path <A> <B>` | 2つのページ / 未解決ターゲットがリンクグラフ上でどう繋がるかを短い経路で見る。経路なしでも related / backlinks などの recovery hints を返す |
| `link-stats <title>` | incoming リンク数と 0 / 1 / N（none / single / multi）区別 |
| `unresolved` | 本文の無いリンクターゲットをランク付けして一覧（後述の注意あり） |
| `peek <title>` | 本文行のみ（`--line-offset N --line-limit M` で長大ページをページング） |
| `export-ai <title>` | main + 1-hop / 2-hop ページ本文を 1 テキストへ展開（alias `export-for-ai`） |
| `stats` | ストアの件数・更新日時などを確認 |
| `import --cosense <json>` / `import --markdown <folder>` | Cosense JSON エクスポート、または read-only Markdown folder mirror を project namespace に取り込み・再構築 |
| `adopt-markdown <folder>` | 既存 Markdown wiki を store に import し、page_create event を JSONL journal に記録する |
| `export-markdown --output <folder> --check` | Markdown-backed project の stored lines を Markdown projection として比較する no-op gate。差分があれば exit 1 |
| `append-section <title>` | Markdown-backed page に section を追記し、SQLite index / JSONL journal / Markdown projection を更新する alpha write surface |
| `append-log` | Markdown-backed log page に dated entry を追記し、SQLite index / JSONL journal / Markdown projection を更新する alpha write surface |
| `write-status` | alpha write 用に journal 件数・last event・Markdown projection check を返す |
| `write-diff` | filesystem 上の Markdown と stored projection の unified diff を返す |
| `revert-event <event-id>` | tail に残っている `section_append` / `log_append` event だけを取り消し、`event_revert` を journal に記録する |
| `replay-journal` | JSONL journal だけから Markdown projection を再構築・check する alpha recovery surface |
| `import-forest <wikis.yaml>` | registry の複数 Markdown wiki を 1 store の複数 project namespace に一括 import。entry ごとの diagnostics と forest-level ambiguity summary を返す |
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

- **Markdown / Obsidian 互換性の拡張** — 最小の read-only mirror と content-only 差分 index、first H1 title resolution は実装済み。Obsidian block refs / より細かい alias-aware incremental rebuild などは今後の拡張。
- **書き込み層（`write` / `rename`）** — append-only alpha（`append-section` / `append-log`）と、その recovery surface（`write-status` / `write-diff` / tail-only `revert-event` / `replay-journal`）は入りましたが、stable identity / rename / 汎用 page update replay / 汎用 revert は未実装です。Scrapbox / Cosenseを使っている人がAIから hosted に書くときはcosense-cliで書くことを想定しています。grasp の write 層は将来的にCosenseユーザでない人 or オンラインのCosenseに書くのではなくローカルに閉じて欲しいケース をサポートする目的です。
- **ベクトル検索** — 文字列一致だけでなく、意味の近さで関連を辿る。

スコープ外: リアルタイム多人数編集・同期・共有/権限・Web UI。単一ユーザ＋AI には不要で、これらを削ぎ落とすのが grasp の核です。

## License

MIT
