# Scrapbox / Cosense ユーザ向け

このページは、Scrapbox / Cosense project を持っている人向けの入口です。`grasp` は hosted project そのものではなく、export や取得済み subset から作った local snapshot を読みます。

ブラウザでページを開くと、本文だけでなく関連ページやリンク元の文脈も見ます。`grasp read <title>` はそれを CLI から AI が扱える形にし、本文・行レベル逆リンク・related・未解決ターゲットをまとめて返します。

## JSON export から取り込む

Cosense の **Settings -> Page Data -> Export Pages** から JSON をダウンロードします。ページのメタデータを含める設定は ON 推奨です。

```bash
grasp import --cosense your-project.json
```

project 名は export JSON の `name` を既定で使います。別名で入れたい場合は `--project` を指定します。

```bash
grasp import --project my-cosense --cosense your-project.json
grasp --project my-cosense read "ページタイトル"
```

同じ store には複数 project を入れられます。同名 project を再 import した場合は、その project namespace だけを置き換えます。

## 読む

```bash
grasp --project my-cosense read "ページタイトル"
grasp --project my-cosense backlinks "概念名"
grasp --project my-cosense related "概念名"
grasp --project my-cosense search "探したい語" --context 2
```

`read` は本文が存在するページだけでなく、本文ページが無い linked target にも効きます。本文が無い概念でも、それを参照する source pages と行から文脈を読めます。

related ページの冒頭も一緒に見たい時は `--related-snippets`、関連を生んだリンク行を見たい時は `--related-snippet-mode edge` を使います。

```bash
grasp --project my-cosense read "ページタイトル" --related-snippets
grasp --project my-cosense read "ページタイトル" --related-snippets --related-snippet-mode edge
```

## 管理者 export が無い場合

`@helpfeel/cosense-cli` の `cosense` binary が使える環境なら、hosted project から読める範囲だけを partial corpus として取得できます。

```bash
grasp --project project:slice acquire https://scrapbox.io/project/ --search "[your.icon]" --limit 100
grasp --project project:crawl acquire https://scrapbox.io/project/ --from-page "起点ページ" --depth 1 --limit 100
```

これは full export の代替入口です。結果の backlinks / related / unresolved は、取得済み subset 内の事実として扱ってください。

## hosted の最新差分を取り込みたい場合

既に full export から seed した project を保守する用途では `sync` を使えます。これも `cosense` CLI と認証状態に依存します。

```bash
grasp --project my-cosense sync https://scrapbox.io/project/ --dry-run
grasp --project my-cosense sync https://scrapbox.io/project/
grasp --project my-cosense sync https://scrapbox.io/project/ --full-reconcile --dry-run
```

`sync` は full mirror の保守用 path です。既定では最近更新された hosted pages だけを差分 upsert します。`--full-reconcile` は hosted manifest 全体を比較し、古い missing page、rename、hosted 側 delete tombstone を検出します。

partial corpus は `sync` ではなく、同じ `acquire` criteria の再実行で更新します。`sync` は partial acquisition namespace では mutation せず diagnostic を返します。hosted `lines[].id` は今は local `line_id` に保存せず、grasp 側の `page.id:line-index` locator を維持します。

## cross-project refs を seed にする

既存 store 内の `[/other-project/page]` 参照を外部 project acquisition の seed として使う時は、文字列検索ではなく target-aware な抽出を使います。

```bash
grasp --project my-cosense cross-project-refs --semantic-only --limit 20
grasp --project my-cosense cross-project-refs --semantic-only --limit 20 --seed-dir /tmp/grasp-seeds
grasp --project my-cosense cross-project-acquire --limit 5 --seed-limit 10 --dry-run
```

`.icon` や project root refs を分類して除外できるので、semantic page ref だけを acquisition seed にできます。実取得の前に `--dry-run` で計画を確認してください。

## 注意

- `grasp` の既定 store は `~/.grasp/grasp.sqlite` です。
- `--project` / `$GRASP_PROJECT` で対象 project を指定できます。
- import 済み JSON は store 横の `<store>.imports/` に復旧用コピーとして保持されます。
- 古い export などで行が metadata なしの plain string でも import できますが、その行の作成日時・更新日時・userId は空になります。

詳細な引数と JSON key は `grasp <command> --help` を見てください。
