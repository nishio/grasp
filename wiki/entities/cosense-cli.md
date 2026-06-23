---
type: entity
summary: `@helpfeel/cosense-cli` は hosted Cosense を読む・調べる・編集する既存 CLI。grasp とは用途が違うが比較対象として重要。local 環境では `cosense` binary として利用可能
sources:
  - `cosense --help` in local environment 2026-06-23
  - npm global package list 2026-06-23
  - speed re-benchmark 2026-06-23: median of 5, local warm SQLite store, `cosense` v1.4.4 over network
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

`grasp sync <project-url>` を使う環境では、この `cosense` binary が PATH にあることが runtime 前提になる（または `--cosense-command` で path/name を指定する）。`read` / `search` など local store を読む command は cosense-cli を必要としない。

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

`grasp`（local export → SQLite store, read-only）と公式 `@helpfeel/cosense-cli` の `cosense` v1.4.4（hosted, 認証済み, network 込み）を走らせた一次データ。MVP の中核仮説検証と、post-MVP sync 経路の材料。

測定条件:

- project: `https://scrapbox.io/nishio/`
- page: `君主道徳と奴隷道徳`
- query: `盲点`
- `grasp`: `~/.grasp/grasp.sqlite`（227MB）を使う warm steady-state。CLI process startup と stdout 生成込み。
- `cosense`: official hosted API 呼び出し。network/API/server cache の揺れ込み。
- latency: 各 5 回の median（min/max は生ログで確認）。本文や個人情報は出さず、stdout は byte 数だけ確認。

### 速度

| 操作 | grasp（local warm store） | cosense（official hosted CLI） | 読み |
|---|---:|---:|---|
| 初回 seed / import | `import --cosense ~/.grasp/nishio.json` **8.3s**（1回だけ, temp store） | なし | grasp は初期化で 123MB export を SQLite 化する。以後の read path とは分けて見る。 |
| store stats | `stats` **83ms** | なし | local metadata read。 |
| 本文のみ | `peek` **65ms** | `readPage` **634ms** | 出力形は非同一。cosense は hosted page JSON/metadata 込み、grasp は local lines preview。 |
| page を AI 向けに読む | `read` **67ms** | `browsePage` **578ms** | `browsePage` は metadata/telomere/1-hop を持つが、行逆リンク/unresolved は無い。 |
| page + 2-hop 近傍 | `read` **67ms / 1 call** | `browsePage` 578ms + `browseRelatedPages` 1169ms = **1.75s / 2 calls** | grasp は近傍同梱が hot path。約26倍速い。ただし cosense は hosted metadata、grasp は local graph 文脈。 |
| 1-hop/2-hop raw link list | `related --limit 100` **72ms** | `list1hopLinks` **625ms**, `list2hopLinks` **890ms** | `list2hopLinks` はこの page で stdout 約635KB。AI 向けには `browseRelatedPages` が圧縮形。 |
| 行レベル backlinks | `backlinks 盲点 --limit 20` **65ms** | 同等なし | cosense は関連 page title は出せるが、project-wide に「この target へ張る行テキスト」を返す command が無い。 |
| unresolved target queue | `unresolved --limit 100` **76ms** | 同等なし | local graph materialization の価値。 |
| 本文検索 | `search 盲点 --limit 100` **185ms** | `searchFullText` **875ms** | どちらも 100 件返る。grasp は snapshot の literal line search、cosense は hosted search API の page result。 |
| ベクトル検索 | なし | `searchVector` **792ms** | semantic / vector retrieval は cosense だけ。 |
| freshness check | `sync --limit 20 --dry-run` **695ms** | `listPages --sort updated --limit 20` **636ms** | sync の律速は cosense network call。変更ページがあれば追加で `readPage` 約0.6s/page + local upsert。 |

旧 MVP 計測では grasp が毎 command で 123MB JSON を full parse していたため、どの動詞も ~3.4s だった。これは現在の SQLite store 化後の hot path では古い数字。現状の読みは 65-185ms、公式 cosense-cli は 0.58-1.75s 程度。したがって **反復 read/search は grasp、最新化 delta は cosense-cli** という役割分担が妥当。

重要な読み替え:

- 「grasp が速い」は hosted Cosense API より優れた一般 CLI という意味ではない。**local indexed mirror を読む hot path** が速い、という意味。
- cosense-cli は初期 import が不要で、常に生きた hosted project を読む。代わりに各 command が auth/network/server state に依存する。
- grasp は初回 import 8.3s を払う。以後の読みは local store なので、AI が同じ project を何度も探索するほど効く。
- sync は `cosense listPages` / `readPage` を使うため、freshness path の速度は cosense-cli 側の network/API latency に支配される。

### できることの差

grasp が出して cosense が出せない:
- **行レベル逆リンク（行テキスト同梱）** — cosense `browseRelatedPages` は関連*タイトル*のみ（1hop/2hop）、文脈行が無い。grasp の「行リンク」原理が効く核心。
- **`unresolved`（未解決 link target 列挙）** — cosense に project-wide の unresolved target 一覧コマンドが**存在しない**。grasp の local graph だから出せる機能。
- **1 コールで近傍同梱**（本文 ＋ 行逆リンク ＋ 2hop/source pages ＋ unresolved targets）。cosense は最低 2 コール、しかも unresolved target list は作れない。
- 完全オフライン・認証不要。
- 反復 read/search の sub-200ms latency（store 構築済みの場合）。

cosense が出して grasp が（まだ）出せない:
- **ベクトル検索**（`searchVector`）。grasp の `search` は snapshot 上の literal substring search であり、semantic retrieval ではない。
- **生きた状態**（grasp は import/sync 済み snapshot）＋ 豊富なメタ（pageRank / telomere / snapshot / accessed 時刻）。
- hosted page の write/edit（`previewEdit` / `submitEdit`）。grasp v1 は read-only。

### 含意

中核仮説（AI が CLI だけで Scrapbox 近傍を体験）は成立。cosense に原理的に無い 2 点（行逆リンク*テキスト*・赤リンクキュー）が grasp の存在理由そのもの。SQLite store 化で cold-parse latency は hot path から消えた。残る差は **freshness / hosted metadata / vector retrieval は cosense、local graph neighborhood retrieval は grasp** という責務差。
