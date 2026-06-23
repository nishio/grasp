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

## 帰結

- import adapter は **2モード**: bulk seed（export）と incremental delta（cosense-cli）。native store（[[persistence-custom-format]]）はどちらの入力も同じ正規化先。
- store は immutable index でなく **upsert 可能**でなければならない → [[SPEC]] M2-1 の store 設計（SQLite 等）に反映。
- これは "Co-"（多人数リアルタイム協調）ではない。単一所有 mirror を最新に保つだけ ＝ [[why-not-scrapbox-clone]] のスコープ内。

## Open Questions

- cosense-cli は `updated` を humanize した文字列（例 `2022-03-01T23:20+09:00 (4 年前)`）で返す → 数値秒での厳密比較がしづらい。page id 単位で updated 文字列の異同を見るか、raw timestamp 取得手段を要確認。
- 削除・rename されたページの検出（listPages は存在ページのみ返す）。tombstone をどう同期するか。
- `pinned page は常に先頭に来る`（sort=updated でも）→ カーソル walk の停止判定で pinned を除外する必要。
- hosted lines は Cosense 由来の安定 line-id を持つ（export には無い）。grasp は自前 line-id（`page.id:line-index`）を維持するか、hosted line-id を採用するか（[[grasp-cli-mvp]] の line-id 方針と整合をとる）。
