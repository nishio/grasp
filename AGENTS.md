# grasp

## テーマ
単一の **AI 自身が所有する local な Scrapbox 型グラフ知識ストア**を CLI で扱うツール `grasp` の開発 wiki。
Scrapbox のグラフモデル（自動双方向リンク・2-hop・**行リンク**・**赤リンク**）を、browser / Web UI なしに **CLI から AI が "体験" できる** ようにする。Co-（多人数協調）層は削ぎ、Scrapbox の name=identity 欠陥を **identity-without-name** で直す。

由来: nishio の llm-wiki での設計対話（2026-06-23）。「Cosense は複数人前提の設計だが、一人で使っても Markdown 集合より効く。"Co-" になる前の Scrapbox を CLI で扱える substrate が LLM に良いのでは」。名前 `grasp` = graph × scrap（box）＋「把握する / grasp」。設計の全体は [[why-not-scrapbox-clone]] / [[SPEC]]。

## 分業（重要）

- **この wiki（＋ nishio / 設計担当 AI）** = spec・設計判断・原理・open question・gotcha を保持。**Codex が読む context**。
- **Codex** = 実装。本 wiki を読んでコードを書く。Codex の作業で判明したこと（制約・落とし穴・設計変更）は本 wiki に **file back** する。
- ∴ ページは **coding agent 向け** に書く（人間向け解説でなく、実装の source of truth）。

## source of truth

- **[[SPEC]]** = grasp が提供する CLI 動詞 ＋ データモデル。Codex はこれに実装を合わせる。design が固まるにつれ **上書き更新**（spec は現状、log は出来事 = 現状 ≠ 記録）。
- **[[why-not-scrapbox-clone]]**（`decisions/`）= なぜこの形か（Scrapbox を Co- / グラフに分解、B を選んだ理由、各 fork）。決定の記録。覆すときは新 decision を追記。

## ディレクトリ構造

```
grasp/
├── AGENTS.md          # このファイル（スキーマ）
├── raw/               # 外部ソース（設計対話ログ・Codex 作業ログ等、不変・gitignored）
├── wiki/
│   ├── index.md
│   ├── log.md         # 出来事の時系列
│   ├── SPEC.md        # ★ Codex 向け source of truth（CLI surface + data model）
│   ├── decisions/     # なぜ（design rationale, ADR 風）
│   ├── concepts/      # 原理・横断概念
│   └── entities/      # 具体リソース（依存ライブラリ・既存ツール等）
└── scripts/
    └── lint_wiki.py
```

## ページルール

- 冒頭に YAML フロントマター: type, summary, sources
- **SPEC は上書き更新**（現状を表す）。`decisions/` は追記（覆すときも履歴を残す）。`concepts/` は通常 wiki ルール（`## Updates` 追記）。
- 主張に出典、矛盾・未解決は `## Open Questions`
- 親 llm-wiki の概念を参照するときは **バックティックのプレーン名**で（例: `名前ではなくIDで識別する設計`）。`[[...]]` は grasp 内リンク専用（cross-wiki link は lint が broken 扱いするため）。

## 操作

### Ingest / File back
設計対話や Codex の作業ログを raw/ に置いて ingest、または会話の洞察を file back。spec に効くなら SPEC.md を上書き、判断なら `decisions/` に。log に `## [YYYY-MM-DD HH:MM] <op> | <desc>`。

### Lint
`python3 scripts/lint_wiki.py`（孤立・壊れたリンク・未登録）→ 意味的 lint（矛盾・stale spec・open q）→ log に `## [YYYY-MM-DD HH:MM] lint | <summary>`。

## 運用方針

- **spec-first だが over-spec しない**。Codex が実装して初めて分かる制約は file back で戻す（親 llm-wiki `書いてから整理する` の実装版）。
- ソースは参考、無批判採用しない。スキーマも実験で改善する。
