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
