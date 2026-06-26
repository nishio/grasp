---
type: decision
summary: データ最新化は export の繰り返しでなく、初回 export を seed にし以降は cosense-cli で「最近更新されたページだけ」取得して差分 upsert する。cosense-cli は比較対象から grasp の freshness 経路へ昇格（post-MVP）
sources:
  - llm-wiki 設計対話 2026-06-23（nishio）
  - cosense listPages --help / 実測 2026-06-23
---

# Decision: 最新化は export 反復でなく cosense-cli 差分更新

決定: grasp の local store の最新化は、**初回 = Cosense JSON export（bulk seed）／以降 = cosense-cli で最近更新ページのみ取得して upsert（incremental delta）**。123MB の export を都度作り直す運用にはしない。

## 文脈

[[cosense-cli]] は当初「grasp と責務が違う比較対象、MVP では runtime dependency にしない」と位置づけた。nishio 判断で **post-MVP の freshness 経路として cosense-cli を使う**ことが確定。export は重く（管理画面で手動生成・123MB）頻繁な再取得に向かない。

## メカニズム（cosense listPages に grounded, 2026-06-23 実測）

- `cosense listPages <projectUrl> --sort updated --limit N [--skip M]` が **更新日時降順**でページ metadata（`id` / `title` / `updated` / `linesCount` …）を返す。**本文 lines は含まない**（`descriptions` の先頭数行のみ）。`--limit` 最大 1000。
- grasp は last-sync カーソル（前回同期時点の最大 updated）を保持。listPages を新しい順に walk し、stored と updated が一致する run に達したら停止 ＝ **変更ページ集合**を得る。
- 各変更ページは `cosense readPage <pageUrl>`（`lines` を含む）で本文取得 → store に upsert ＋ そのページの edge を再 materialize（[[persistence-custom-format]] のエッジ層）。

## Update (2026-06-23): 実装

`grasp sync <project-url>` を追加。`--limit` 件まで `cosense listPages --sort updated` を inspect し、store の `pages.updated` と remote `updated` を比較する。変更ページだけ `cosense readPage` で取得して SQLite store に upsert、最後に `unresolved_targets` を再 materialize する。

- runtime 前提: `grasp sync` は optional freshness path なので、通常の read-only path と違って `@helpfeel/cosense-cli` の `cosense` binary が install 済みで PATH にあることが必要。対象 project への login / 認証も必要。binary 名や path は `--cosense-command` で差し替える。
- `updated` は humanized suffix の前の ISO8601 部分を `datetime.fromisoformat` で epoch seconds に変換して比較する。
- pinned page は updated が古くても停止条件にしない（`pin > 0` なら skip して次を見る）。
- hosted line id は採用せず、grasp の既存方針 `page.id:line-index` を維持する。
- `--dry-run` は changed page の列挙のみで `readPage` / upsert しない。

## Update (2026-06-23): page count mismatch 解消を実測

export seed 直後の local store は `nishio` 25791 pages、hosted `cosense listPages https://scrapbox.io/nishio/ --sort updated --limit 1` の `count` は 25792 pages だった。`grasp sync --dry-run --limit 20` は新規ページ `タブUI` 1 件だけを changed として検出し、実 sync はこれを upsert した。

同期後の local `grasp stats` は 25792 pages / 724986 lines になり、hosted count 25792 と一致。再 dry-run は changed 0。少なくとも「export 後に追加された最近更新ページ」については、現行 sync path で page count mismatch を解消できる。

制約: 停止条件は「recent updated walk で既知ページに到達」なので、古い更新日時のまま local に存在しないページ、削除、rename の検出はこの実測では解決していない。削除・rename は引き続き Open Questions。

## Update (2026-06-26): ScrapBubble / hosted REST からの補正案

ScrapBubble は `@cosense/std@0.31/rest` の `getPage(..., {followRename: true, projects: [...]})` を使い、JSON export には無い hosted REST metadata（stable `lines[].id`, `commitId`, `links`, `projectLinks`, `relatedPages`）を bubble graph に使っている。`@helpfeel/cosense-cli` 1.4.4 の `readPage` も `/api/pages/v2/:project/:title` から stable `lines[].id` と `commitId` を返すが、現行 `grasp sync` はそれを採用せず `page.id:line-index` を維持する。

sync 改善の候補:

- **recent delta は維持**: updated 降順で新しい順に walk し、変更ページだけ `readPage` / REST page fetch して upsert する現行 hot path は残す。
- **periodic full manifest reconcile を追加**: `listPages` pagination（または `@cosense/std` の `listPagesStream` 相当）で project 全体の `id/title/updated/linesCount/linked/views` manifest を取り、local page id set と比較する。これで updated window では拾えない delete / rename / 古い missing page を検出する。
- **rename は page id を主キーにする**: same `id` / changed `title` を rename として alias history に入れる。`followRename=true` は「旧 title で読める」ための fetch workaround であって、旧 title → 新 title の履歴そのものを返すわけではない。
- **delete は tombstone**: remote manifest から消えた local `id` は即物理削除せず tombstone 化し、edges / unresolved rebuild からは外す。認証済みなら `/api/deleted-pages/:project/:pageId` や `/api/stream/:project` の `page.delete` event で補強する。
- **stable hosted line id を保存するか決める**: REST `lines[].id` は JSON export に無い。sync で取得した page だけでも `external_line_id` として保持すれば、line fragment URL や hosted edit (`previewEdit` / `submitEdit`) と対応できる。ただし export seed 由来 page には line id が無いので、grasp の local stable line-id とは別列にする方が安全。
- **direct public API fallback**: `cosense` binary が無い環境でも public project は `/api/pages/:project` と `/api/pages/:project/:title` で読める。private / auth-required project は従来通り cosense-cli or cookie/token path に戻す。

## 帰結

- import adapter は **2モード**: bulk seed（export）と incremental delta（cosense-cli）。native store（[[persistence-custom-format]]）はどちらの入力も同じ正規化先。
- store は immutable index でなく **upsert 可能**でなければならない → v1 SQLite store（[[grasp-v1-implemented]]）に反映。
- これは "Co-"（多人数リアルタイム協調）ではない。単一所有 mirror を最新に保つだけ ＝ [[why-not-scrapbox-clone]] のスコープ内。

## Open Questions

- ~~cosense-cli は `updated` を humanize した文字列で返す~~ → suffix 前の ISO8601 を epoch seconds に parse して比較。
- 削除・rename されたページの検出（listPages は存在ページのみ返す）。tombstone をどう同期するか。
- ~~`pinned page は常に先頭に来る`~~ → sync の停止判定から pinned を除外。
- ~~hosted lines は Cosense 由来の安定 line-id を持つ~~ → grasp は自前 line-id（`page.id:line-index`）を維持。
