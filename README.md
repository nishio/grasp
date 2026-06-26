# grasp

**LLM エージェントのための、ローカルなグラフ知識ストア。**

`grasp` は、既存のノート群をローカルな SQLite グラフストアに取り込み、AI が CLI から **ページ本文 + 行レベル逆リンク + related + 未解決リンクターゲット** を一度に読めるようにするツールです。

人間が毎回 `grasp` コマンドを覚えて叩くためのツールというより、Claude Code などの AI エージェントに Skill として持たせておき、あなたは自然言語で「この概念について何を書いたっけ」「関連ページも辿って」と聞く、という使い方を想定しています。

## どちらから始めるか

Markdown / Obsidian の人と Scrapbox / Cosense の人では、最初の疑問が違います。自分に近い入口から読んでください。

| 使っているもの | 入口 |
| --- | --- |
| Obsidian、Markdown notes、LLM Wiki、ただの `.md` フォルダ | [Obsidian / Markdown ユーザ向け](docs/markdown.md) |
| Scrapbox / Cosense project、Cosense JSON export、hosted Cosense | [Scrapbox / Cosense ユーザ向け](docs/cosense.md) |

Scrapbox / Cosense を知らなくても使えます。Markdown フォルダに `[[wikilink]]` や `#tag` があるなら、まずは [Obsidian / Markdown ユーザ向け](docs/markdown.md) から試してください。

## 何がうれしいのか

Markdown の束だけを AI に渡すと、リンクはただの文字列です。「誰がこのページにリンクしているか」「この概念の周辺には何があるか」を知るには、AI が grep して、候補を開いて、また grep する必要があります。

`grasp` はリンクをグラフのエッジとして保存します。だから `grasp read <title>` だけで、次の文脈をまとめて返せます。

- **本文**: 対象ページの行
- **逆リンク**: そのページや未解決ターゲットを参照している行
- **related**: 2-hop で近いページ、または本文が無いターゲットを参照する source pages
- **未解決ターゲット**: 本文ページは無いがリンクされている概念ノード

本文がまだ無い概念でも、多くのページから参照されていれば、参照元の行から意味を読めます。これが「単なる検索 CLI」ではなく、AI がローカルなグラフを読むための基盤である理由です。

## インストール

Python **3.10 以上**。実行時依存はありません。

```bash
git clone https://github.com/nishio/grasp.git
cd grasp
pip install -e .
```

`pip` がシステム Python に弾かれる環境では、仮想環境か `pipx install --editable .` を使ってください。未インストールのまま試す場合は、リポジトリ直下で `python3 -m grasp ...` と実行できます。

手元にまだデータが無い場合は、このリポジトリ自身の `wiki/` を read-only Markdown mirror として試せます。

```bash
grasp --store /tmp/grasp-demo.sqlite import --markdown wiki --project grasp-wiki
grasp --store /tmp/grasp-demo.sqlite --project grasp-wiki read grasp-v1-implemented --line-limit 20
```

## AI エージェントに持たせる

主経路は CLI 直叩きではなく、AI エージェントに Skill として登録する使い方です。Claude Code なら、リポジトリ内の Skill をユーザ skill ディレクトリへ symlink します。

```bash
mkdir -p ~/.claude/skills
ln -s "$PWD/skills/grasp" ~/.claude/skills/grasp
```

これで、AI に次のように聞けます。

> 「グラフ理論について自分は何を書いた？ 関連ページも辿って」

AI は必要に応じて `grasp read` / `search` / `backlinks` / `related` などを呼び分けます。Skill 側の使い方は [skills/grasp/SKILL.md](skills/grasp/SKILL.md)、各コマンドの正確な引数と JSON 形状は `grasp <command> --help` が正典です。

## 最初に覚えるコマンド

| command | 何をするか |
| --- | --- |
| `grasp stats` | store と project の状態を見る |
| `grasp import --markdown <folder>` | Markdown フォルダを read-only mirror として取り込む |
| `grasp import --cosense <json>` | Scrapbox / Cosense JSON export を取り込む |
| `grasp read <title>` | 本文、逆リンク、related、未解決ターゲットをまとめて読む |
| `grasp search <query>` | 本文行を検索する。`--context N` で前後行も返す |
| `grasp backlinks <title>` | 行レベル逆リンクだけを見る |
| `grasp related <title>` | 2-hop related や missing target の source pages を見る |
| `grasp suggest <partial>` | うろ覚えのタイトルを補完する |
| `grasp unresolved` | 本文ページが無いリンクターゲットを ranked view で見る |
| `grasp path <A> <B>` | 2 つのページ / ターゲットの短いリンク経路を見る |

`unresolved` は「埋めるべき TODO リスト」ではありません。本文が無くても、参照元の行の文脈で既に意味を持っている概念ノードとして扱います。

詳しいオプション、返る JSON key、例は使う直前に確認します。

```bash
grasp read --help
grasp search --help
grasp --json read "ページタイトル" --backlinks-limit 5
```

## Store と project

- 既定 store は `~/.grasp/grasp.sqlite` です。
- 1 つの store に複数 project namespace を入れられます。
- project 名を変える場合は import 時に `--project <name>` を付けます。
- 読む対象を選ぶ場合は command の前に `--project <name>` を置きます。

```bash
grasp import --project my-notes --markdown ~/Notes
grasp --project my-notes read "ページタイトル"
```

環境変数でも指定できます。

| option | 環境変数 | 用途 |
| --- | --- | --- |
| `--store PATH` | `GRASP_STORE` | SQLite store の場所 |
| `--project NAME` | `GRASP_PROJECT` | 読み書き対象の project |
| なし | `GRASP_HOME` | 既定 home。未指定なら `~/.grasp` |

text 出力の `line-id` は `P1:0` のような実行内ローカル別名に短縮されます。安定した完全 ID が必要な時は `--json`、text のまま完全 ID を見たい時は `--full-ids` を使います。

## 現在のスコープ

Stable:

- Markdown folder の read-only mirror import
- Scrapbox / Cosense JSON export の import
- 複数 project を 1 store に保持
- `read` / `search` / `backlinks` / `related` / `path` などの read surface
- page が存在しない linked target の backlinks / related / link-stats
- CLI + Agent Skill による AI 向け delivery

Alpha:

- Markdown-backed project 向けの `append-section` / `append-log` / `write-page` / `rename-page`
- `write-status` / `write-diff` / `revert-event` / `replay-journal` による recovery surface

スコープ外:

- Web UI
- リアルタイム多人数編集
- 共有・権限管理
- 汎用の hosted Cosense 編集

## License

MIT
