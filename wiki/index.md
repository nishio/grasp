# grasp — 開発 wiki index

単一 AI 所有の local な Scrapbox 型グラフ知識ストア `grasp`（graph × scrap / 把握）の開発 wiki。
Codex が実装し、本 wiki が実装済み事実・backlog・設計判断・gotcha を保持する（分業の詳細は `../CLAUDE.md`）。

## source of truth

| ページ | 役割 |
|---|---|
| [grasp-v1-implemented](entities/grasp-v1-implemented.md) | ★ v1 リリース時点で実装済みの CLI surface / data model / parser / delivery。旧 SPEC / v1-todo の完了済み側を分離した current facts |
| [grasp-backlog](grasp-backlog.md) | ★ 旧 SPEC / v1-todo にあったが v1 時点で未実装の項目。parser fidelity・UX・Markdown adapter・write/identity・search・sync・distribution |
| [why-not-scrapbox-clone](decisions/why-not-scrapbox-clone.md) | なぜこの形か。Scrapbox 忠実 clone でなく identity-without-name を足したあるべき姿を作る（内部呼称 design B） |
| [persistence-custom-format](decisions/persistence-custom-format.md) | 保存形式は独自フォーマット（Markdown ではない＝逆リンク維持の発生源）。読込は import adapter の別責務。on-disk store = SQLite（or better） |
| [incremental-sync](decisions/incremental-sync.md) | 最新化は export 反復でなく初回 seed＋cosense-cli で最近更新ページのみ差分 upsert。cosense-cli は比較対象から freshness 経路へ昇格（post-MVP） |
| [delivery-cli-plus-skill](decisions/delivery-cli-plus-skill.md) | AI に使わせる面 = CLI + Agent Skill（cosense-cli パターン）。旧 SPEC Open Q「純 CLI か MCP か」を決着。`--help`=mechanics SSoT / SKILL.md=いつ・どう使うか。read=近傍同梱が Skill を薄くする |
| [language-and-distribution](decisions/language-and-distribution.md) | 実装言語と配布チャネルは別軸。言語論点は実測で溶ける（仕事は全部 SQLite、warm store で起動 ~30ms・read ~83ms）。当面 Python+pipx、native(Go/Rust)→npm は「Python 不要 agent 環境」trigger 待ち。SQLite store 契約が段階移行を de-risk |
| [positioning-two-personas](decisions/positioning-two-personas.md) | audience は2層。driver=persona1（JP Cosense ヘビーユーザ＝nishio dogfooding）／upside-risk=persona2（世界の Markdown 束ユーザ）。substrate 共有・value prop と on-ramp は別。persona2 は addition（Markdown adapter＋英語 docs＋一般化 pitch）で狙い設計は曲げない。GTM=HN/Reddit、lede は「Markdown 束でなく local graph store」 |
| [markdown-obsidian-indexed-mirror](decisions/markdown-obsidian-indexed-mirror.md) | persona2 向け Markdown / Obsidian folder 対応は read-only indexed mirror。Skill ではなく adapter/indexer が検索・リンク graph を materialize し、Skill は薄い利用層。pitch は faster grep でなく graph reader for LLM agents |

## concepts/

_まだ無し。read＝近傍同梱 / 行リンク / 未解決 link target / identity-without-name が実装・設計をまたいで育ったら切り出す。_

## entities/

| ページ | 役割 |
|---|---|
| [cosense-json-export](entities/cosense-json-export.md) | v1 入力 = Cosense JSON export の**実物確認スキーマ**。import adapter の source of truth。lines に id 無し（grasp 採番）・link graph 未保存（text parse）・`[...]` overloaded・unresolved targets ~45700→ranking 必須 |
| [grasp-cli-mvp](entities/grasp-cli-mvp.md) | 2026-06-23 時点の read-only CLI 実装。`python3 -m grasp` の verbs・data model・parser 補正・性能課題 |
| [grasp-v1-implemented](entities/grasp-v1-implemented.md) | v1 リリース時点の実装済み facts。今後はこちらを current implementation の入口にする |
| [fts5-trigram-search](entities/fts5-trigram-search.md) | `grasp search` 高速化候補としての SQLite FTS5 trigram 検証。safe query の prefilter には有効だが、literal substring semantics には `LIKE` fallback / post-filter が必要 |
| [cosense-cli](entities/cosense-cli.md) | `@helpfeel/cosense-cli` / `cosense` binary の local availability・grasp との使い分け・**実測比較（速度/機能差）**・post-MVP の freshness 経路 |
| [persona1-user-test-2026-06-23](entities/persona1-user-test-2026-06-23.md) | persona1（JP Cosense ヘビーユーザ=nishio dogfooding）視点の CLI ユーザテスト。read=近傍同梱の価値確認と、表記ゆれ空振り・global option 位置・長大ページ出力・store default docs drift の発見 |
| [persona2-user-test-2026-06-23](entities/persona2-user-test-2026-06-23.md) | persona2（世界の LLM Wiki / Markdown 束ユーザ）視点の fresh onboarding テスト。現状は Markdown folder import が無く、英語 README / friendly error も無いため active acquisition はまだ早い |

## メタ

- [grasp-backlog](grasp-backlog.md) — v1 時点で未実装の backlog
- [[log]] — 出来事の時系列（現状ではない）
