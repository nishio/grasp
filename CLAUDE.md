# grasp

## テーマ
単一の **AI 自身が所有する local な Scrapbox 型グラフ知識ストア**を CLI で扱うツール `grasp` の開発 wiki。
Scrapbox のグラフモデル（自動双方向リンク・2-hop・**行リンク**・**赤リンク**）を、browser / Web UI なしに **CLI から AI が "体験" できる** ようにする。Co-（多人数協調）層は削ぎ、Scrapbox の name=identity 欠陥を **identity-without-name** で直す。

由来: nishio の llm-wiki での設計対話（2026-06-23）。「Cosense は複数人前提の設計だが、一人で使っても Markdown 集合より効く。"Co-" になる前の Scrapbox を CLI で扱える substrate が LLM に良いのでは」。名前 `grasp` = graph × scrap（box）＋「把握する / grasp」。設計判断は [[why-not-scrapbox-clone]]、v1 実装済み事実は [[grasp-v1-implemented]]、未実装項目は [[grasp-backlog]]。

## 分業（重要）

- **この wiki（＋ nishio / 設計担当 AI）** = 実装済み事実・backlog・設計判断・原理・open question・gotcha を保持。**Codex が読む context**。
- **Codex** = 実装。本 wiki を読んでコードを書く。Codex の作業で判明したこと（制約・落とし穴・設計変更）は本 wiki に **file back** する。
- ∴ ページは **coding agent 向け** に書く（人間向け解説でなく、実装の source of truth）。

## source of truth

- **[[grasp-v1-implemented]]** = v1 リリース時点で実装済みの CLI surface / data model / parser / delivery。current facts。
- **[[grasp-backlog]]** = 旧 SPEC / 旧 v1-todo にあったが未実装のもの。次に実装する候補。
- **[[why-not-scrapbox-clone]]**（`decisions/`）= なぜこの形か（Scrapbox を Co- / グラフに分解、B を選んだ理由、各 fork）。決定の記録。覆すときは新 decision を追記。
- 旧 `SPEC.md` は定義ではなく v0.5 実装指示だったため、v1 リリース後に上記2ページへ分解して削除済み。

## ディレクトリ構造

```
grasp/
├── CLAUDE.md          # このファイル（スキーマ）
├── raw/               # 外部ソース（設計対話ログ・Codex 作業ログ等、不変・gitignored）
├── wiki/
│   ├── index.md
│   ├── log.md         # 出来事の時系列
│   ├── grasp-backlog.md # 未実装項目
│   ├── decisions/     # なぜ（design rationale, ADR 風）
│   ├── concepts/      # 原理・横断概念
│   └── entities/      # 具体リソース（v1実装済み事実・依存ライブラリ・既存ツール等）
└── scripts/
    └── lint_wiki.py
```

## ページルール

- 冒頭に YAML フロントマター: type, summary, sources
- 実装済み事実は `entities/` に current facts として更新する。未実装項目は [[grasp-backlog]] に移す。`decisions/` は追記（覆すときも履歴を残す）。`concepts/` は通常 wiki ルール（`## Updates` 追記）。
- 主張に出典、矛盾・未解決は `## Open Questions`
- 親 llm-wiki の概念を参照するときは **バックティックのプレーン名**で（例: `名前ではなくIDで識別する設計`）。`[[...]]` は grasp 内リンク専用（cross-wiki link は lint が broken 扱いするため）。

## 操作

### Ingest / File back
設計対話や Codex の作業ログを raw/ に置いて ingest、または会話の洞察を file back。実装済み事実なら `entities/`、未実装なら [[grasp-backlog]]、判断なら `decisions/` に。log に `## [YYYY-MM-DD HH:MM] <op> | <desc>`。

file back は **grasp write first**。通常編集の authority は SQLite store 側に置く。tracked `wiki.grasp/events.jsonl` は `1.8.18` で退役・削除済みで、通常 file-back は repo に JSONL を作らない。まず `git fetch origin main` 後に `python3 scripts/check_file_back_preflight.py`（no-journal default）を走らせ、remote 分岐なし / wiki dirty なし / 退役済み JSONL path の再作成なし / `write-status --no-journal --strict` / SQLite authority projection を確認してから、`append-section` / `write-page` / `append-log` を `--no-journal --output wiki` 付きで使う。write 後に `python3 scripts/check_file_back_postwrite.py`（no-journal default）が通らない時、または任意 frontmatter merge / canonical docs など grasp alpha が表現できない時だけ direct Markdown patch に fallback し、理由を log に残す。

`--journal` / `--with-journal` は CLI の legacy/ad hoc audit 用には残るが、repo runbook では `--with-journal` を使わない。JSONL 調査が必要な時は task-local の明示 path を使い、別途 migration decision を切るまで repo artifact として commit しない。

同じ SQLite store に対する write 系 command は **直列実行**する。並列に `write-page` などを投げると store update と projection export の順序が interleave し、projection が一時的に stale になる。起きた場合は対象 page を直列で再 `write-page --from-file --no-journal` し、`python3 scripts/check_file_back_postwrite.py`（no-journal default）で clean に戻す。

複数 wiki page を direct patch fallback してから grasp store に戻す場合も、**1 page patch → 直列 `write-page --from-file --no-journal` → 次 page** の順にする。`write-page` は全 Markdown projection を export するため、まだ store に入っていない別 page の direct patch は projection に上書きされる。

### Lint
`python3 scripts/lint_wiki.py`（孤立・壊れたリンク・未登録）→ 意味的 lint（実装済み事実・backlog・decision の矛盾 / stale open q）→ log に `## [YYYY-MM-DD HH:MM] lint | <summary>`。

### Ship loop
Claude Code では `/ship-next`（`.claude/commands/ship-next.md`）で、差分理解 → wiki file back → `python3 -m unittest discover -s tests` / `python3 scripts/lint_wiki.py` / `python3 scripts/check_file_back_runbook.py` / `git diff --check` → commit → push → "what's next?" 提示までを一つの作業ループとして閉じる。空差分なら empty commit せず、current backlog から次候補だけ答える。

## 運用方針

- **実装事実 first だが over-spec しない**。Codex が実装して初めて分かる制約は file back で戻す（親 llm-wiki `書いてから整理する` の実装版）。
- ソースは参考、無批判採用しない。スキーマも実験で改善する。
