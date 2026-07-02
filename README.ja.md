# grasp

[English README](README.md)

**AIエージェントのための、ローカルなグラフ読解レイヤー。**

`grasp` は、複数の wiki をひとつのローカルな「wiki森」として読みます。
それぞれの wiki は Markdown フォルダでも、Obsidian vault でも、Scrapbox /
Cosense export でもかまいません。`grasp` はそれらを project-scoped な
ノードとエッジに正規化し、AI エージェントが元形式を意識せずに CLI から
横断読解できるようにします。

まずは SSoT（信頼できる元データ）を移動せずに始められます。Cosense project、
Markdown フォルダ、Obsidian vault を authoring の場として残し、その横に
AI が速く読める検索・読解レイヤーを置きます。必要になったら、grasp を
authoring store にする方向へ段階的に移行できます。

authority の置き方は2つあります。

- **read-only indexed evidence**: 既存の Markdown / Obsidian / Cosense を
  SSoT のまま残し、`grasp` は捨てられるグラフ index として横に置く。
- **SQLite-authority wiki**: 新しく作る知識は `grasp` の write 経路で作り、
  SQLite の current state + event ledger を authority にし、Markdown は
  review / backup / 相互運用の projection として吐く。

A/B の既存 evidence corpus を read-only import し、C の新しい reasoning wiki を
SQLite authority として作る pattern は [docs/authority-modes.md](docs/authority-modes.md)
にまとめています。

まずはこういう道具だと考えてください。

> Cosense や Markdown を引っ越さずに始められ、必要なら段階的に移行できるローカル index。

## wiki森として読む

`grasp` の対象はファイル形式ではなく wiki森です。複数の wiki tree を、project
identity を保ったまま、ひとつの graph store として読めるようにします。

```text
Markdown wiki     Obsidian vault     Cosense export
      \                |                  /
       \               |                 /
             grasp graph store
        project-scoped nodes and edges
        backlinks / related / path / unresolved
                    |
               AI agent reads
```

Markdown / Obsidian の registry がある場合は、`import-forest` でまとめて取り込めます。

```bash
grasp import-forest /path/to/wikis.yaml --markdown-exclude-dir raw
grasp search "探したい語"
grasp backlinks "概念名"
```

Scrapbox / Cosense export も、同じ SQLite store にそれぞれの `--project` 名で取り込めます。
`--project` を省いた検索・読解は store 全体を対象にし、ページ identity は merge せず
project ラベル付きで返します。

## Scrapbox / Cosense を知らない人へ

Scrapbox / Cosense は、ページ本文の中にリンクを書き、リンク元や関連ページを
自然にたどれる wiki 型のノート環境です。知らなくても問題ありません。

`grasp` が使う発想はもっと単純です。

- ノートはファイルの束ではなく、リンクでつながったグラフである
- あるページを読む時は、本文だけでなく「どの行から参照されているか」も重要である
- まだ本文ページがないリンク先も、参照元の行を集めれば意味を持つ

普通の全文検索は、文字列に当たった行を返します。`grasp read` は、ページ本文、
行レベルの逆リンク、近い関連ページ、未解決リンク先をまとめて返します。AI が
毎回 grep して、候補を開いて、リンクをたどり直す手間を減らすための CLI です。

## Cosense ユーザにとっての価値

最初のユーザは、すでに Scrapbox / Cosense に知識をためている人だと想定しています。
重要なのは、**最初から SSoT を Cosense から移さなくてよい**ことです。

Cosense の JSON export を `grasp` に取り込むと、手元にローカル snapshot ができます。
Hosted Cosense はそのまま本体として使い始め、`grasp` は AI 用の高速な検索レイヤーとして
使います。信頼が育ってから、必要な範囲だけ段階的に移行できます。

```bash
grasp import --cosense your-project.json --project my-cosense
grasp --project my-cosense search "探したい語" --context 2
grasp --project my-cosense read "ページタイトル"
```

ブラウザで Cosense を読む時、人間は本文、リンク元、関連ページを自然に見ています。
`grasp read` はそれに近い読書単位を CLI から返します。AI に「この概念について
自分は何を書いた？ 関連ページも見て」と聞けるようにするためです。

## Markdown / Obsidian でも使える

Markdown フォルダも read-only mirror として取り込めます。元ファイルは書き換えません。
`[[wikilink]]`、`#tag`、frontmatter の `title` / `id` / `aliases` / `tags` を読み、
グラフとして索引します。

```bash
grasp import --markdown ~/Notes --project notes
grasp --project notes read "ページタイトル"
grasp --project notes backlinks "概念名"
```

このリポジトリ自身の `wiki/` でも試せます。

```bash
grasp --store /tmp/grasp-demo.sqlite import --markdown wiki --project grasp-wiki
grasp --store /tmp/grasp-demo.sqlite --project grasp-wiki read grasp-v1-implemented --line-limit 20
```

## インストール

Python 3.10 以上が必要です。実行時依存は標準ライブラリだけです。

```bash
git clone https://github.com/nishio/grasp.git
cd grasp
pip install -e .
```

インストールせず試す場合は、リポジトリ直下で `python3 -m grasp ...` と実行できます。

既定の store は `~/.grasp/grasp.sqlite` です。1つの store に複数 project を入れられます。
読む対象は `--project` で選びます。

## AI エージェントに持たせる

`grasp` は人間が毎回コマンドを覚えて叩くためだけの道具ではありません。Claude Code
などのエージェントに Skill として持たせ、自然言語で聞く使い方を主に想定しています。

Claude Code なら、同梱 Skill を symlink できます。

```bash
mkdir -p ~/.claude/skills
ln -s "$PWD/skills/grasp" ~/.claude/skills/grasp
```

あとは AI にこう聞けます。

> 「このノートで `構造化` について何を書いていた？ 関連ページもたどって」

AI は必要に応じて `search`、`read`、`backlinks`、`related` を呼び分けます。
正確な引数と JSON の形は CLI help が正典です。

```bash
grasp <command> --help
grasp read --help
```

## できること / しないこと

安定しているもの:

- Cosense JSON export の import
- Markdown / Obsidian 風フォルダの read-only import
- `wikis.yaml` registry からの Markdown / Obsidian forest import
- 複数 project を1つの SQLite store に保持
- `read` / `search` / `backlinks` / `related` / `path` / `suggest` / `unresolved`
- 本文ページがないリンク先を、逆リンク文脈つきのグラフノードとして読むこと

目的ではないもの:

- Web UI
- Hosted Cosense の置き換え
- リアルタイム多人数編集
- 最初から既存ノートの SSoT 移行を要求すること

Markdown-backed の書き込み系コマンドもありますが、現時点ではプロジェクト自身の
dogfooding 用 alpha surface です。通常の利用では、まず読み取り・検索レイヤーとして
使ってください。新規の SQLite-authority wiki を意図的に prototype する場合は
[docs/authority-modes.md](docs/authority-modes.md) の手順に従ってください。

詳しい入口は [docs/markdown.md](docs/markdown.md) と [docs/cosense.md](docs/cosense.md) にあります。

## License

MIT
