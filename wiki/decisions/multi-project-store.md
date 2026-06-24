---
type: decision
summary: 複数 Cosense JSON export は同じ graph に merge せず、1つの SQLite store 内で project name namespace ごとに保持する。import は store 全体でなく同名 project だけを置き換える。
sources:
  - nishio 指摘 2026-06-23「同じグラフにする必要はないが、1つのテーブルで複数のプロジェクトをプロジェクト名ごとにストアすべき」
  - grasp/sqlite_store.py
  - grasp/cli.py
---

# Decision: 複数 project は同一 store / 別 namespace

決定: 複数の Cosense JSON export を import しても、ページ・リンク・未解決 target を **同じ graph として merge しない**。ただし store file を project ごとに分けるのではなく、1つの SQLite store 内で `project` namespace に分けて保持する。

## 理由

- 複数 project は名前空間・文脈・同名 page の意味が違う。自動 merge すると `read` / `backlinks` / `related` が別 project の文脈を混ぜ、AI が誤読しやすい。
- 一方、store file を project ごとに分けると AI が「どの sqlite を読むか」を外側で管理する必要が増える。単一 AI 所有 store という運用とは、1 file 内に project list を持つ方が合う。
- Cosense export には root `name` があるため、import adapter が project namespace を自然に決められる。

## 実装

- SQLite schema v4 は `projects` table を持ち、`pages` / `lines` / `edges` / `unresolved_targets` / `unresolved_target_examples` に `project` 列を持つ。page id / line id は project と組にした複合 key で扱う。
- `grasp import --cosense <json>` は JSON root `name` を project name として使い、同名 project だけを削除・再構築する。他 project は保持する。
- `grasp import --project <name> --cosense <json>` で namespace を明示 override できる。
- `read` / `search` / `backlinks` / `related` / `unresolved` / `sync` は selected project 内だけを見る。store に project が1つだけなら `--project` は省略可。複数 project なら `--project <name>` / `$GRASP_PROJECT` が必要。
- `stats` は project list と counts を返す。project 未指定で複数 project がある時は aggregate counts を返す。

## 含意

- `1 store = 1 export snapshot` ではなく、`1 store = many project snapshots` になった。
- project 間リンクや cross-project related は作らない。必要になったら explicit な cross-project query として別設計にする。
- schema v3 以前の store は project namespace を持たないため、次回 import 時に v4 store として作り直す。

## Updates

### 2026-06-24（tentative）: 異なる project の赤リンク（unresolved target）は接続する

nishio 設計判断（Scrapbox `villagepump/grasp`, 出典 raw/grasp-villagepump-page_2026-06-24.txt）:

> 複数のプロジェクトを入れた時に1つの SQLite に全部入る／**異なるプロジェクトの赤リンクは接続する**。間違った〜と言って撤回する可能性はあります。

前者は本 decision で既決。後者は本文の「project 間リンクや cross-project related は作らない」を **unresolved target に限って緩める** 新方針で、明示的に tentative（撤回あり）。

精密化（この Update が変える範囲）:

- 変えない: **resolved page graph の namespace 分離**。`read` / `backlinks` / `related` が別 project の page 本文・authorship を混ぜない、という本 decision の核は維持（混ぜると AI が誤読する、が依然成立。[[cross-project-reference-acquire-2026-06-24]] の「namespace を分けたまま explicit acquisition で近傍を観る」も同じ立場）。
- 変える対象: **page 実体のない赤リンク（unresolved target）**。project A の `[X]` と project B の `[X]` は、どちらも本文を持たない概念ハブで、同一概念を指しうる。これを project 横断で同一 node として束ねると「自分の全 project を通じて、誰も本文を書いていないが皆が指している X」が見える。

未実装 / 論点:

- 現 schema は `unresolved_targets` を project 列で namespace 化している（[[grasp-v1-implemented]] store facts）。cross-project 接続は normalize した target title を project 横断 key にする必要がある。同名 unresolved の semantic 衝突（別 project で同綴り別概念）は resolved page と同じく誤接続リスクがあり、赤リンクなら安全と言い切れるかは未検証。
- 接続を import 時に materialize するか、cross-project query 時に都度束ねるか（[[cross-project-reference-acquire-2026-06-24]] / `cross-project-refs` は後者寄り＝materialize せず都度抽出の方針）。
- tentative なので、実装着手前に「resolved は分離 / unresolved は接続」の非対称が AI 読解で本当に有用かを dogfood で確かめる。

### 2026-06-24: v6 全体決定が含意の2 clause を supersede（上の tentative Update を吸収・収束）

[[whole-store-graph-and-cross-project-edges]]（v6）が本 decision の含意 clause を覆す。**materialized page node を namespace ごとに分けて merge しない核は維持**し、変えるのは edge・default scope・赤 node の扱い:

- 「project 間リンク / cross-project related は作らない」→ cross-project link `[/P/T]` を import 時に **first-class edge として materialize** する（上 Update の Q「materialize するか都度束ねるか」を materialize 側で決着）。
- 「retrieval は selected project 内だけ / 複数 project なら `--project` 必須」→ **retrieval default は whole-store、`--project` は絞り込み**。「自動 merge で AI が誤読」懸念は、merge せず **結果を project ラベル付きで返す** ことで解消する（scope を絞る代わりに label を付ける）。

上の tentative Update（villagepump 由来）との関係:

- **resolved page**: tentative Update は「resolved page graph は分離維持」とした。v6 は **whole-store + label で接続**する（`villagepump/Keicho` を read すると `/nishio` が backlink に出る）。誤読回避を「分離」でなく「labeling」で達成する立場（materialized page の identity は (project, id) のまま分離）。
- **同名 bare 赤リンクの統合（収束）**: tentative Update の「別 project の同名赤リンク `[X]` を normalize 名 key で同一 node に束ねる」を **v6 が採用**した（nishio 2026-06-24「自信は低いが Cosense にない価値を生むので一旦この方針」）。赤 node（referenced-only）は normalize title を project 非依存 key として統合し、materialized page は namespaced のまま。誤接続リスク（同綴り別概念）は受容し、provenance を残して後から判別可能にする。tentative（撤回あり）。詳細・残る境界 Q は [[whole-store-graph-and-cross-project-edges]] の point 7 / Open Questions。
