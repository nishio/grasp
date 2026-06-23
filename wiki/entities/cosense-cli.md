---
type: entity
summary: `@helpfeel/cosense-cli` は hosted Cosense を読む・調べる・編集する既存 CLI。grasp とは用途が違うが比較対象として重要。local 環境では `cosense` binary として利用可能
sources:
  - `cosense --help` in local environment 2026-06-23
  - npm global package list 2026-06-23
  - [[why-not-scrapbox-clone]]
---

# entity: cosense-cli

`@helpfeel/cosense-cli` は hosted Cosense への CLI access。grasp は local export/native store を読む LLM 用 graph substrate なので、同じ「Cosense/Scrapbox を CLI で扱う」でも責務が違う（[[why-not-scrapbox-clone]]）。

## local availability

2026-06-23 の Codex 環境では見える:

```
package: @helpfeel/cosense-cli@1.4.4
binary: cosense
path: /Users/nishio/.nvm/versions/node/v24.16.0/bin/cosense
node: /Users/nishio/.nvm/versions/node/v24.16.0
```

`cosense-cli` という binary 名ではなく `cosense`。

## commands visible in `cosense --help`

- `login`, `whoami`, `listProjects`
- `browsePage`, `browseRelatedPages`
- `readPage`, `readProjectMembers`, `listPages`
- `list1hopLinks`, `list2hopLinks`
- `searchVector`, `searchFullText`, `search1hopLinks`, `search2hopLinks`
- `previewEdit`, `submitEdit`

## grasp との使い分け

- `cosense`: hosted Cosense project を読む・検索する・編集する。認証やネットワーク、共同編集された現在状態が関係する。
- `grasp`: local export/native store を読む。AI 所有の graph memory substrate。逆リンク・2-hop・unresolved link target を local graph として materialize する。

grasp の **MVP** では `cosense` を runtime dependency にしない（export が import 入力、hosted API は別系統）。**ただし post-MVP では cosense-cli が grasp の freshness 経路に昇格する**: 初回 export を seed にし、以降は `grasp sync <project-url>` が `cosense listPages` / `cosense readPage` を呼び、最近更新ページのみ差分取得して local store を最新化する（決定とメカニズムは [[incremental-sync]]）。比較対象から grasp の構成要素へ。

## 実測比較（2026-06-23, 同一ページ `君主道徳と奴隷道徳` 38 lines / 2113 views）

`grasp`（local export, read-only）と `cosense`（hosted, 認証済み `whoami` OK）を同条件で走らせた一次データ。MVP の中核仮説検証の材料。

### 速度

| 操作 | grasp | cosense |
|---|---|---|
| ページ ＋ 近傍 | **3.4s / 1 コール** | `browsePage` 0.47s ＋ `browseRelatedPages` 1.25s ≈ **1.7s / 2 コール** |
| 本文のみ | 3.4s | `readPage` 0.6s |
| backlinks / unresolved | 3.4–3.9s | 同等コマンド無し |
| 検索 | `suggest` 3.7s | `searchFullText` 0.9s |

- grasp の latency はコマンド種別に依らずほぼ一定 ~3.4s で、内訳は **起動毎の 123MB JSON full parse**（user time ≈ wall time）。アルゴリズムでなく「毎回 export を読み直す」MVP 割り切りが律速 → on-disk index で解消見込み（[[grasp-cli-mvp]] / [[SPEC]] 次マイルストーン）。
- cosense が速いのは hosted 事前インデックスだから。代償は **認証 ＋ ネットワーク ＋ 生きた project** が前提。

### できることの差

grasp が出して cosense が出せない:
- **行レベル逆リンク（行テキスト同梱）** — cosense `browseRelatedPages` は関連*タイトル*のみ（1hop/2hop）、文脈行が無い。grasp の「行リンク」原理が効く核心。
- **`unresolved`（未解決 link target 列挙）** — cosense に project-wide の unresolved target 一覧コマンドが**存在しない**。grasp の local graph だから出せる機能。
- **1 コールで近傍同梱**（本文 ＋ 行逆リンク ＋ 2hop/source pages ＋ unresolved targets）。cosense は最低 2 コール、しかも unresolved target list は作れない。
- 完全オフライン・認証不要。

cosense が出して grasp が（まだ）出せない:
- **本文全文検索 ＋ ベクトル検索**（`searchFullText` / `searchVector`）。grasp `suggest` は**タイトル部分一致のみ**で recall が桁違い（`盲点`: grasp 8 件 vs cosense 本文ヒット 100 件）。MVP 比較で最大の機能差。
- **生きた状態**（grasp は凍結 export = snapshot）＋ 豊富なメタ（pageRank / telomere / snapshot / accessed 時刻）。

### 含意

中核仮説（AI が CLI だけで Scrapbox 近傍を体験）は成立。cosense に原理的に無い 2 点（行逆リンク*テキスト*・赤リンクキュー）が grasp の存在理由そのもの。弱点（cold-parse latency・本文/ベクトル検索なし）は設計欠陥でなく既知の MVP 割り切り → 次マイルストーンで埋める（[[SPEC]]）。
