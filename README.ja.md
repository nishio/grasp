# grasp

[English README](README.md)

**AIエージェントのための、ローカルなグラフ読解レイヤー。**

`grasp` は、既存のノート群をローカルの SQLite グラフに索引します。
SSoT（信頼できる元データ）は移動しません。Cosense project、Markdown
フォルダ、Obsidian vault はそのままにして、その横に AI が速く読める
検索・読解レイヤーを置きます。

まずはこういう道具だと考えてください。

> Cosense や Markdown を引っ越さず、AI が 10 倍速く周辺文脈へ到達するためのローカル index。

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
重要なのは、**SSoT を Cosense から動かさなくてよい**ことです。

Cosense の JSON export を `grasp` に取り込むと、手元にローカル snapshot ができます。
Hosted Cosense はそのまま本体として使い、`grasp` は AI 用の高速な検索レイヤーとして
使います。

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
- 複数 project を1つの SQLite store に保持
- `read` / `search` / `backlinks` / `related` / `path` / `suggest` / `unresolved`
- 本文ページがないリンク先を、逆リンク文脈つきのグラフノードとして読むこと

目的ではないもの:

- Web UI
- Hosted Cosense の置き換え
- リアルタイム多人数編集
- 既存ノートの SSoT 移行

Markdown-backed の書き込み系コマンドもありますが、現時点ではプロジェクト自身の
dogfooding 用 alpha surface です。通常の利用では、まず読み取り・検索レイヤーとして
使ってください。

詳しい入口は [docs/markdown.md](docs/markdown.md) と [docs/cosense.md](docs/cosense.md) にあります。

## License

MIT
