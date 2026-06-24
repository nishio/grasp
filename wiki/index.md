# grasp — 開発 wiki index

単一 AI 所有の local な Scrapbox 型グラフ知識ストア `grasp`（graph × scrap / 把握）の開発 wiki。
Codex が実装し、本 wiki が実装済み事実・backlog・設計判断・gotcha を保持する（分業の詳細は `../CLAUDE.md`）。

## source of truth

| ページ | 役割 |
|---|---|
| [history](history.md) | release / store compatibility history。v1 系は `1.x.y` とし、store format / materialized index semantics が変わる時は `x`、それ以外は `y` を進める |
| [grasp-v1-implemented](entities/grasp-v1-implemented.md) | ★ v1 リリース時点で実装済みの CLI surface / data model / parser / delivery。旧 SPEC / v1-todo の完了済み側を分離した current facts |
| [grasp-backlog](grasp-backlog.md) | ★ 旧 SPEC / v1-todo にあったが v1 時点で未実装の項目。parser fidelity・UX・Markdown adapter（navigation/log artifact handling 含む）・write/identity・search・sync・distribution |
| [why-not-scrapbox-clone](decisions/why-not-scrapbox-clone.md) | なぜこの形か。Scrapbox 忠実 clone でなく identity-without-name を足したあるべき姿を作る（内部呼称 design B） |
| [persistence-custom-format](decisions/persistence-custom-format.md) | 保存形式は独自フォーマット（Markdown ではない＝逆リンク維持の発生源）。読込は import adapter の別責務。on-disk store = SQLite（or better） |
| [incremental-sync](decisions/incremental-sync.md) | 最新化は export 反復でなく初回 seed＋cosense-cli で最近更新ページのみ差分 upsert。cosense-cli は比較対象から freshness 経路へ昇格（post-MVP） |
| [multi-project-store](decisions/multi-project-store.md) | 複数 Cosense JSON export は同じ graph に merge せず、1つの SQLite store 内で project name namespace ごとに保持する |
| [delivery-cli-plus-skill](decisions/delivery-cli-plus-skill.md) | AI に使わせる面 = CLI + Agent Skill（cosense-cli パターン）。旧 SPEC Open Q「純 CLI か MCP か」を決着。`--help`=mechanics SSoT / SKILL.md=いつ・どう使うか。read=近傍同梱が Skill を薄くする |
| [language-and-distribution](decisions/language-and-distribution.md) | 実装言語と配布チャネルは別軸。言語論点は実測で溶ける（仕事は全部 SQLite、warm store で起動 ~30ms・read ~83ms）。当面 Python+pipx、native(Go/Rust)→npm は「Python 不要 agent 環境」trigger 待ち。SQLite store 契約が段階移行を de-risk |
| [positioning-two-personas](decisions/positioning-two-personas.md) | audience は2層。driver=persona1（JP Cosense ヘビーユーザ＝nishio dogfooding）／upside-risk=persona2（世界の Markdown 束ユーザ）。substrate 共有・value prop と on-ramp は別。persona2 は addition（Markdown adapter＋英語 docs＋一般化 pitch）で狙い設計は曲げない。GTM=HN/Reddit、lede は「Markdown 束でなく local graph store」 |
| [markdown-obsidian-indexed-mirror](decisions/markdown-obsidian-indexed-mirror.md) | persona2 向け Markdown / Obsidian folder 対応は read-only indexed mirror。Skill ではなく adapter/indexer が検索・リンク graph を materialize し、Skill は薄い利用層。LLM Wiki の index/navigation/log は通常 edge でなく current projection / event stream として扱う |

## concepts/

| ページ | 役割 |
|---|---|
| [ai-consumer-cost-and-trust](concepts/ai-consumer-cost-and-trust.md) | grasp の設計上の主たるユーザ＝CLI 越しにグラフを読む AI の cost-and-trust model。軸1 round-trip/token の経済（read=近傍同梱の why、gather/snippets/token economy backlog の ranking 原理）、軸2 negative-result contract（沈黙の偽陰性 = absence の hallucination、recall を vector より先に直す理由）。2026-06-24 Updates: 第3の消費者軸＝substrate を持たない公開人間読者（読者ケアは2軸モデルの外） |
| [come-from-declared-gather](concepts/come-from-declared-gather.md) | リンクの4仕事（recall/attention/navigation/読者ケア）と、Cosense が全部を1リンクに束ねる→ hub 膨張（KJ法 144→490）の *why*＝per-occurrence 局所判断×双方向の大域帰結ミスマッチ。howm の come-from（用語1宣言→全出現 gather）が判断と帰結を用語-大域で揃える。grasp 3層: read=既存 `mentions`（nishio 2022 howm 仮想出現一覧）/ declare・render=未実装。write/identity は come-from（用語キー）と felt-sense link（行キー）を別 object に。今後の `mentions` は (a)意図的/(b)gap/(c)AI default 裸 を分け come-from 昇格候補を出す。第3消費者＝公開人間読者 |
| [cosense-delite-howm-synthesis](concepts/cosense-delite-howm-synthesis.md) | grasp は Scrapbox 一本の clone でなく Cosense / デライト / howm から1軸ずつ抜いた合成。Cosense=グラフモデル（自動双方向・2-hop・赤リンク・行リンク・フラット）/ デライト=identity-without-name（知番）/ howm=「ページ＝投影」と come-from。3ツールの弱点は全部「別々の仕事を1つの仕掛けに束ねた」に帰着し、grasp の一貫した手は層分離で束ねを解く（Cosense は `[X]` に4仕事、デライトは意味を独自語彙に、howm は retrieval を人間の Emacs 操作に）。各ツールから1つずつ捨てる: 多人数協調編集 / 独自語彙 / 時間駆動リマインダ。デライトの引き入れ＝リンクに前景後景型が乗った typed link → [[grasp-backlog]] |
| [use-case-experiment-as-outcome-story](concepts/use-case-experiment-as-outcome-story.md) | ユースケース実験は「ユーザがこう依頼したら、こういう有用な結果が得られる」という outcome story として記録する。gotcha 発見だけでなく、結果が読む・判断する・次に使う単位にまとまっていて「いい感じ」かを評価対象にする |
| [development-arc-retrieval-ahead-of-authoring](concepts/development-arc-retrieval-ahead-of-authoring.md) | 2026-06-23〜24 で 1.0.0→1.5.23（87 commits）まで増殖した開発弧の自己観察。①速度の正体＝「層を分けて束ねを解く」単一原理の再適用（[[why-not-scrapbox-clone]]/[[come-from-declared-gather]]/[[cosense-delite-howm-synthesis]]/[[delivery-cli-plus-skill]] は同じ手の別対象適用）→ アイデアが一個だから増殖しても一貫。②規律（[[history]] の x/y ledger）は dogfooding の帰結（本番25kページ store を使うので parser 変更は「速いが古い」でなく「意味が違う」）。③構造的非対称＝retrieval 厚く実装済み（read近傍同梱/search/mentions/co-links/gather/acquire）だが差別化核の authoring（id-link write/come-from declare・render/rename で参照文不壊）は全部 [[grasp-backlog]] で未着手。今の grasp は read-only リーダーで存在理由の半分が約束。次の山は retrieval→authoring。親 llm-wiki と概念→コード数時間ループ |

_他に: read＝近傍同梱 / 行リンク / 未解決 link target / identity-without-name が実装・設計をまたいで育ったら切り出す。_

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
| [ai-consumer-feedback-2026-06-23](entities/ai-consumer-feedback-2026-06-23.md) | 設計上の主たるユーザ＝CLI 越しに読む AI（Claude Opus 4.8）が v1 を実走したレビュー。validated（read=近傍同梱・related rank・miss recovery）＋ Tier 1-4 findings（recall が最優先）と routing。ingest 時に backlinks ランク済み / read --json の page-id 既済を確認 |
| [kj-link-hub-audit-2026-06-24](entities/kj-link-hub-audit-2026-06-24.md) | `KJ法` が exact `[KJ法]` 144 pages に対し literal mention 681 pages / body bare mention 490 pages に広がる hub だと実測。全部リンク化せず、root link・用途別 subtopic link・co-link slice・AI cluster handoff に分け、巨大入口を分岐点に変える判断。1.5.13 dogfood では `co-links` が broad query-containing title を上位に出す caveat も記録 |
| [cross-project-reference-acquire-2026-06-24](entities/cross-project-reference-acquire-2026-06-24.md) | `/nishio` の `[/` cross-project shorthand から 183 project / 4,141 other-project refs を抽出し、semantic refs 上位 12 project を partial acquire した dogfood。`.icon` と root refs を分ける必要、`cosense` PATH gotcha、all-failed acquisition diagnostic の弱さ、AI/Cosense/Plurality/熟議クラスタを記録 |

## メタ

- [grasp-backlog](grasp-backlog.md) — v1 時点で未実装の backlog
- [[log]] — 出来事の時系列（現状ではない）
