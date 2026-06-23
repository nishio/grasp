---
type: entity
summary: v1 リリース時点で grasp に実装済みの挙動。旧 SPEC.md / v1-todo.md は一時的な実装指示として分解し、このページは current facts だけを保持する。
sources:
  - 旧 wiki/SPEC.md（v0.5 実装指示, deleted after split）
  - 旧 wiki/v1-todo.md（一時 TODO, deleted after split）
  - grasp/cli.py
  - grasp/cosense.py
  - grasp/sqlite_store.py
  - README.md
  - skills/grasp/SKILL.md
---

# entity: grasp v1 implemented surface

このページは **v1 リリース時点で実装済みの事実**だけを保持する。旧 `SPEC.md` は定義ではなく v0.5 実装指示、旧 `v1-todo.md` も一時 TODO だったため削除し、未実装項目は [[grasp-backlog]] に分離した。

## v1 scope

v1 = **エクスポート済み Scrapbox / Cosense JSON を、AI が CLI + Agent Skill から高速に読む read-only tool**。

実装済み:

- Cosense JSON export を `grasp import --cosense <json>` で SQLite store に materialize する。
- `read` が本文だけでなく、行レベル backlinks・related・page-local unresolved targets を一体で返す。
- page が存在しない linked target も graph node として扱い、`backlinks` / `related` / `link-stats` で source context を読める。
- home 配下の global store 1 個を default にする。
- AI 向け delivery は CLI + Agent Skill。詳細引数と JSON key は `grasp <cmd> --help` が mechanics SSoT。

v1 scope 外:

- local write / rename / transclude。
- Markdown / Obsidian folder import。
- vector search。
- Web UI / realtime multi-user collaboration / sharing and permissions。

## delivery

- Python package `grasp`。`python3 -m grasp ...` と console script `grasp` の両方で起動する。
- Python 3.10+、runtime dependencies は無し（stdlib `sqlite3`）。
- `README.md` は「主たるユーザは人間 CLI operator ではなく AI agent」という前提に更新済み。
- `skills/grasp/SKILL.md` が「いつ使うか」を持ち、CLI mechanics は `grasp <cmd> --help` に寄せる。

## store

- store default: `$GRASP_STORE` → `$GRASP_HOME/grasp.sqlite` → `~/.grasp/grasp.sqlite`。
- `grasp import --cosense <json>` は初回構築と再構築を兼ねる。既存 store は確認なしで置き換える。
- legacy `--export` / `--rebuild-store` / `--force` / 暗黙 seed は v1 surface には無い。
- SQLite schema は pages / lines / edges / unresolved_targets / unresolved_target_examples を持つ。
- `stats` は store path, schema version, source export, imported_at, counts などを返す。

## commands

| command | v1 implemented behavior |
|---|---|
| `import --cosense <json>` | Cosense JSON export から SQLite graph store を構築・置換 |
| `stats` | store の schema / metadata / count を表示 |
| `read <title>` | existing page は本文 + backlinks + related + unresolved。missing linked target は link stats + backlinks + source pages |
| `backlinks <title>` | `(source page, line-id, line text)` の行レベル backlinks。missing target にも効く |
| `related <title>` | existing page は page 間 edge の 2-hop pages。missing target は source pages |
| `link-stats <title>` | incoming link count / source page count / none-single-multi を返す |
| `peek <title>` | page lines のみ |
| `suggest <partial>` | title 部分一致候補 |
| `search <query>` | `lines.text LIKE` の literal substring search。行レベル hits を返す |
| `export-ai <title>` / `export-for-ai` | main + 1-hop/2-hop page 本文を Cosense Export for AI 風に単一テキスト化 |
| `sync <project-url>` | optional freshness path。`cosense` CLI で最近更新ページを取得し、SQLite store に upsert |
| `unresolved` | page 実体のない linked target を ranking して返す。TODO list ではない |

## import and parser facts

- Cosense export の line には安定 id が無いので、v1 は `page.id:line-index` を `line-id` として採番する。
- link graph は export に保存されないため、line text から edge を materialize する。
- title / link resolve は case-insensitive + whitespace folding。
- Cosense title 行 `lines[0]` は本文に残す。完全性と line-id 安定性を優先する。
- Cosense `[[...]]` は bold markup であり link ではない。v1 importer は link として扱わない。

v1 parser が link から除外するもの:

- external URL / icon or image / decoration / math / cross-project link。
- inline backtick 内。
- ASCII index 風 `xs[i]` / `func()[0]`。
- 数字のみ `[1]` / `[2024]`。
- 連続 `*` / `-` / `_` decoration の `[** x]` など。

数字のみ link と `#tag` は Scrapbox fidelity 上の未実装項目として [[grasp-backlog]] に分離した。

## performance

実データ（nishio project: 25791 pages / 724981 lines）で、SQLite warm store の主要 command はおおむね 50-200ms:

- `read` は sub-100ms。
- `backlinks` / `unresolved` は約 50-80ms。
- `search` は `LIKE` 全行 scan 律速で約 180ms。FTS5 trigram hybrid は [[fts5-trigram-search]] の通り未実装候補。
- 初回 import は 1 回だけ数秒から十数秒程度。

## source pages

- Cosense JSON export の実スキーマ: [[cosense-json-export]]
- v1 実装の詳細履歴: [[grasp-cli-mvp]]
- CLI + Skill delivery: [[delivery-cli-plus-skill]]
- store 決定: [[persistence-custom-format]]
- freshness path: [[incremental-sync]]
- hosted Cosense との使い分け: [[cosense-cli]]
