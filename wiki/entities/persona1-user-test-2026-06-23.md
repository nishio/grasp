---
type: entity
summary: persona1（日本語Cosenseヘビーユーザ=nishio dogfooding）の視点で grasp CLI を実走したユーザテスト結果。read=近傍同梱と linked target without page の価値は成立。摩擦は表記ゆれ空振り、global option 位置、長大ページの出力量、テスト時点の store default docs drift
sources:
  - [[positioning-two-personas]]
  - [[SPEC]]
  - skills/grasp/SKILL.md
  - grasp CLI 実行 2026-06-23
---

# entity: persona1 user test 2026-06-23

目的: [[positioning-two-personas]] の **persona1 = 日本語話者で Cosense ヘビーユーザ（nishio 自身の一側面）**として、既存 Cosense 資産を `grasp` CLI だけで調査する。評価軸は新規 onboarding ではなく、dogfooding で「Co- 以前の Scrapbox を CLI で AI が体験」できるか。

## テスト前提

- persona1 は Cosense のページ・リンク・関連 pane・赤リンクの感覚を持つ。
- persona1 は既に `raw/nishio.json` 由来の store を持つ。
- 問いは「ユーザテスト」周辺を nishio の外部脳から拾うこと。
- 併せて、本文ページのない target（例: `民主主義`, `ユーザーテスト`）が意味ある概念ノードとして読めるかを試す。

## 結果サマリ

**persona1 dogfooding としては成功。** 特に `read <title>` が本文・行レベル backlinks・related・page-local unresolved targets を一括で返す点と、page なし target を backlinks/source pages として開ける点は、Cosense heavy user の感覚に合う。

主な摩擦は core graph model ではなく、空振り時の回復と docs consistency:

- `ユーザテスト` vs `ユーザーテスト` のような日本語表記ゆれで missing/0 links になる。
- `--json` を subcommand 後に置く自然なミスが、回復案なしの argparse error になる。
- 長大ログページの default `read` は CLI 一括出力としては多い。
- テスト時点で root help と `skills/grasp/SKILL.md` は `~/.grasp/grasp.sqlite` default だが、[[SPEC]] / [[grasp-cli-mvp]] には repo-local store 前提の記述が残っていた（19:50 file back で同期済み）。

## 観察

### 1. search -> read -> related は成立

`grasp search ユーザテスト --limit 8` は line-level hits を返し、`Devin.aiを試す2025-01` の「人間が裏にいるMVP」の人間部分を Devin にしてユーザテストする、という行に到達できた。

`grasp suggest ユーザテスト --limit 8` は title hit として `5人でユーザテストすればユーザビリティ上の問題の85%が見つかる` などを返した。`search` は本文、`suggest` は title 補完という分担は理解しやすい。

`grasp read '5人でユーザテストすればユーザビリティ上の問題の85%が見つかる' --line-limit 12 --backlinks-limit 5 --related-limit 5 --unresolved-limit 5` は、本文・逆リンク・2-hop related・page-local unresolved を一画面で返した。Cosense の page + related pane に近い。

### 2. page なし target が読めるのは強い

`grasp read 民主主義 --backlinks-limit 4 --related-limit 4` は `page: linked target without page` として、82 links / 78 source pages を返した。本文はなくても、リンク元の行文脈と source pages で意味が読める。

`grasp read '自由と民主主義は両立しない' --line-limit 20 --backlinks-limit 3 --related-limit 5 --unresolved-limit 5` では、ページ本文から `[民主主義]` unresolved target と 2-hop related が同時に見えた。[[SPEC]] 原理の `read=近傍同梱` はここで明確に効く。

### 3. 表記ゆれで体験が切れる

`grasp read ユーザテスト` / `grasp link-stats ユーザテスト` は missing/0 links だった。一方で `grasp search ユーザテスト` は多数ヒットし、実際の graph target は長音ありの `ユーザーテスト` だった。

`grasp read ユーザーテスト --backlinks-limit 5 --related-limit 5` は page なし target として 4 backlinks / 4 source pages を返した。つまり情報はあるが、空振り時の導線がない。

persona1 は日本語表記ゆれを普通に踏む。完全な日本語正規化を急ぐより、missing + 0 links のときに `suggest` / `search` / 近い linked target を hints として出す方が先に効く。

### 4. global option 位置のミスが回復しにくい

`grasp read 民主主義 --json --backlinks-limit 2` は `grasp: error: unrecognized arguments: --json` で終了した。

正しい形は `grasp --json read 民主主義 --backlinks-limit 2 --related-limit 2`。root help と Skill には root option と書かれているが、エラー本文からは回復できない。AI agent も人間も自然に末尾へ置きがちなので、command 側 alias として受けるか、少なくとも error に具体例を出したい。

### 5. 長大ページの default read は多い

`grasp read 'Devin.aiを試す2025-01'` は 513 lines / 66394 bytes。`--line-limit 40` でも近傍込みで 120 lines / 12372 bytes。

Cosense browser ならスクロールできるが、CLI は一括出力なので persona1 の長いログページでは流量が大きい。`peek` / `--line-limit` はあるが、search hit line から周辺本文へ移動する導線はまだ弱い。

### 6. store default の source of truth が割れている

観察時点の `grasp stats` は `/Users/nishio/.grasp/grasp.sqlite` を見た。root help と `skills/grasp/SKILL.md` も default store を `~/.grasp/grasp.sqlite` としていた。一方で [[SPEC]]・[[grasp-cli-mvp]] には `.grasp/grasp.sqlite` 前提の記述が残っていた。

one global store は「単一 AI が一つの local store を持つ」設計に合う。採用済みなら wiki と skill を更新するべき。未決なら decision が必要。

Update 2026-06-23 19:50: [[SPEC]] / [[grasp-cli-mvp]] / [[delivery-cli-plus-skill]] に `~/.grasp/grasp.sqlite` global default を file back 済み。

## 推奨

P0:

- missing + zero incoming の `read` / `link-stats` に recovery hints を足す。候補は `suggest <query>` と `search <query> --limit 3` の summary。
- `--json` を subcommand 後でも受ける、または argparse error に `use: grasp --json read ...` を出す。
- store default の docs drift は 2026-06-23 19:50 に [[SPEC]] / [[grasp-cli-mvp]] / [[delivery-cli-plus-skill]] へ file back 済み。

P1:

- `search` hit から周辺本文へ移動する surface を足す。候補: `read --around-line <line-id>`, `peek --line-offset`, または `search --context N`。
- 長大ページ向けに Skill 側へ「まず `search` hit を読み、必要なら `read --line-limit` / `peek`」という手順を追記する。

## 判定

- persona1 dogfooding: 現状で継続可能。価値の核は成立。
- 次に直すべきもの: graph model ではなく、miss recovery と docs consistency。
