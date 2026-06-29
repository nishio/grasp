# Obsidian / Markdown ユーザ向け

このページは、Obsidian vault、LLM Wiki、Zettelkasten、ただの Markdown フォルダを使っている人向けの入口です。Scrapbox / Cosense を知らなくても大丈夫です。

`grasp` は既存の `.md` ファイルを書き換えず、read-only mirror として index します。`[[wikilink]]` や `#tag` をグラフのエッジとして読み、AI が `read` 一発で本文・逆リンク・related・未解決ターゲットをまとめて読めるようにします。

## なぜ Markdown フォルダだけでは足りないのか

Markdown では、forward link はファイル内にありますが、逆リンクや 2-hop related は保存されていません。AI は毎回 grep で探して、候補ファイルを開いて、関連をつなぎ直す必要があります。

`grasp import --markdown` は、その探索に必要な graph index を事前に作ります。元の Markdown はそのままで、AI には「ページ + 近傍」が返ります。

## 取り込む

```bash
grasp import --markdown ~/Notes --project notes
```

重い raw/generated directory を避けたい場合は directory basename を指定します。

```bash
grasp import --markdown ~/Notes --project notes --markdown-exclude-dir raw
```

取り込み後は、project を指定して読みます。

```bash
grasp --project notes read "ページタイトル"
grasp --project notes search "探したい語" --context 2
grasp --project notes backlinks "概念名"
```

project が 1 つだけなら `--project` は省略できます。

小さな高密度 Markdown vault で試す demo は [persona2a-demo.md](persona2a-demo.md) にあります。`examples/persona2a-vault` を取り込み、`read` が本文・逆リンク・related・未解決ターゲットを一度に返すことと、temp copy 上の `append-log` / `write-status --strict` までを確認できます。

## タイトルとリンクの扱い

page title は次の順で決まります。

1. frontmatter `title`
2. first H1
3. file stem

frontmatter `id` / `aliases` / `tags` も読みます。`aliases` と file stem は link handle になります。本文中の `[[wikilink]]` と `#tag` は internal edge として index されます。

duplicate title / alias は import を止めません。`grasp read <handle>` の結果に候補が返るので、必要なら `--page-id` や `--path` で identity を選びます。duplicate `id` は同じ identity が複数ある状態なので error です。

```bash
grasp --project notes read --path source/Digest.md
grasp --project notes ambiguities
```

## 複数 wiki をまとめて読む

`wikis.yaml` のような registry がある場合は、複数 Markdown wiki を 1 store の複数 project namespace としてまとめて import できます。

```bash
grasp import-forest /path/to/wikis.yaml --markdown-exclude-dir raw
```

各 wiki の失敗は全体を止めず diagnostics に集約されます。import 後は `grasp stats` で project 一覧を確認し、読む時に `--project <name>` を指定します。

## まず AI に聞く

Skill を登録していれば、AI に自然言語で聞けます。

> 「この vault で `構造化` について何を書いていた？ 関連ページも辿って」

AI は必要に応じて `search` で当たりを付け、`read` で本文 + 逆リンク + related を読みます。長いページでは `search --context` や `read --around-line` を使って、必要な周辺だけを読むのが基本です。

## まだできないこと

- Obsidian block refs / heading anchors の line-id 対応は未実装です。
- Markdown import は read-only mirror です。既存ファイルには書き戻しません。
- Markdown-backed project 向けの `append-section` / `append-log` / `write-page` / `rename-page` は alpha です。

詳細な引数と JSON key は `grasp <command> --help` を見てください。
