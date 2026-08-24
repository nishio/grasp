---
type: entity
summary: 2026-08-24 に write 側の2ブロッカー（projection コストの density 超線形／並行書き込みの silent lost）を現行版（schema 14）で再測定した記録。両方とも再現しない。Part A=7 corpus の size ladder（39–505 md）で export-markdown 生成時間は edges にほぼ線形・505p/1万edgeで 0.88s（超線形なし、[[mode2-parallel-edit-stress-2026-06-30]] の 25s timeout は再現せず）。Part B=8 writer×25 の並行 append-log 同一ページ（200）と write-page 別ページ全projection export（200）で消失0・`database is locked`0・projection clobber 0（06-30 の 50中24 silent lost は再現せず）。∴ write プリミティブは並行安全になっている（SQLite write ロック待機で直列化＝消失なしが最も自然な説明）。残る壁は write 消失でなく runbook/協調層で、本 session 自身が postwrite の file-back lock 消失でガード停止を踏んだのが live evidence。
sources:
  - `~/.grasp/grasp.sqlite` 由来ではなく throwaway temp store（accessism/wiki 等の markdown import）、schema v14
  - session stress harness 2026-08-24: `scratchpad/fn_probe.py` の write 版（Part A `stress/`、Part B `stressB/`）
  - Part A ladder: connecting-dot(39) vt-wiki(40) accessism(56) lenchi(75) kozaneba(108) monika(224) llm-wiki(505) を temp store に import → `export-markdown` 生成/`--check` を計測
  - Part B: temp store + temp output に 8 thread が別プロセス grasp を並行起動
  - live incident: 本 session の file-back postwrite で `.grasp/file-back.lock.json` が消失し `check_file_back_postwrite.py` が停止（内容は strict green、手動検証で代替）
id: 0bbe0c02c7888cd0c6958160
title: parallel-write-stress-remeasure-2026-08-24
---

## Context

[[grasp vs grep 偽陰性 A/B]]（[[false-negative-recall-benchmark-2026-08-24]]）で retrieval 側の価値を実証した続きに、
[[parallel-agent-substrate-goal]]（goal 1＝並行 agent 知識共有基盤）を本気目標とする前提で、
write 側の2ブロッカーを現行版で再測定した。両ブロッカーの一次ソースは 2026-06〜07 の incident で、
古い log から現状を推論しないという規律（親 CLAUDE.md）に従い、測定で status を更新する。

## Part A: projection コストの density 依存（超線形か）

7 corpus の size ladder を temp store に import し、`export-markdown`（全 projection 生成＝毎 write が払うコスト）と `--check` を計測。

| corpus | pages | lines | edges | e/p | gen_s | chk_s | ms/edge |
|---|---|---|---|---|---|---|---|
| vt-wiki | 40 | 2,545 | 285 | 7.1 | 0.14 | 0.26 | 0.49 |
| connecting-dot | 39 | 3,440 | 440 | 11.3 | 0.17 | 0.10 | 0.39 |
| accessism | 56 | 4,054 | 483 | 8.6 | 0.18 | 0.23 | 0.37 |
| lenchi | 75 | 4,334 | 1,120 | 14.9 | 0.19 | 0.15 | 0.17 |
| kozaneba | 108 | 12,393 | 2,197 | 20.3 | 0.28 | 0.23 | 0.13 |
| monika | 224 | 25,354 | 4,031 | 18.0 | 0.46 | 0.27 | 0.11 |
| llm-wiki | 505 | 63,435 | 10,214 | 20.2 | 0.88 | 0.94 | 0.09 |

**結論**: ms/edge は 0.49→0.09 と*下がる*（固定オーバヘッド amortize）。生成時間は edges にほぼ線形で、密度 e/p（7〜20）で爆発しない。[[mode2-parallel-edit-stress-2026-06-30]] の「高密度グラフで export-markdown --check 25s timeout・link 密度に superlinear 疑い」は現行版では**再現しない**。

## Part B: 並行書き込みの silent lost（無協調）

temp store + temp output に別プロセス grasp を並行起動し、消失（rc==0 なのに materialized state に無い）を数える。

| test | 並行度 | intended | survivors | silent lost | errors |
|---|---|---|---|---|---|
| B1 append 同一ページ | 4×15 | 60 | 60 | 0 | なし |
| B2 append 同一ページ | 8×25 | 200 | 200 | 0 | なし |
| B3 write-page 別ページ（各自が全 projection export） | 8×25 | 200 | store 200 / disk 200 | 0 | clobber 0 |

**結論**: 8 writer / 200 write でも消失0・`database is locked`0・projection clobber 0。[[mode2-parallel-edit-stress-2026-06-30]] の「無協調 50中24 silent lost（last-writer-wins）」と [[parallel-agent-write-incident-2026-06-26]] の「write-page 全 projection export で別 agent patch 上書き」は現行版では**再現しない**。write プリミティブは並行安全になっている（SQLite write ロック待機で直列化＝消失なしが最も自然な説明。ただし直列化なら並列 write スループットは単一書き手上限で、これは未測定）。

## 結論（status 更新）

goal 1 の残作業は再定義される:

1. **「書き込みを消さない」は現行版で達成済み**（Part B）。projection コストの density 病理も解消（Part A）。∴ 2ブロッカーは status から外す。
2. **残る壁は write 消失でなく runbook/協調層**。本 session 自身が postwrite で `.grasp/file-back.lock.json` 消失によりガード停止を踏んだ（内容 strict green・手動検証で代替）。プリミティブは安全なのに、複数 session を仕切る層（lock ライフサイクル・単一 working tree 共有・preflight/stamp guard）がまだ脆い。[[parallel-session-file-back-contention-2026-06-28]] の single-writer ボトルネックも同層。
3. ∴ goal 1 の Done は「消失0」でなく **「協調層が堅牢＆観測可能」**（lock が session 跨ぎで壊れない／互いの in-flight が見える／単一 working tree ボトルネック解消）へ焦点が移る。

## Open Questions

- **直列化 vs 並列のスループット未測定**。消失0が SQLite write ロック直列化で達成されているなら、並行 write の実効スループットは単一書き手上限。200 write を並行 vs 逐次で wall-clock 比較すれば確定する。次に測る候補。
- 消失0が直列化由来なら、[[mode2-parallel-edit-stress-2026-06-30]] の `claim-page` lease は**消失防止としては不要**になり、役割は in-flight 可視化へ移る（lease の ~50% skip=throughput 半減の前提が変わる）。
- 本 session の lock 消失の**根本原因が未特定**。write-start/write-page/postwrite のどれが lock を解放/消去したか、runbook を再走して再現・切り分けが要る。
- Part B は throwaway temp store（accessism 56p 級）での measurement。goal の想定する grasp-wiki/nishio 級の高密度 store での長い real dogfood は未実施（[[parallel-agent-substrate-goal]] 2026-06-28 audit の future monitoring と同じ留保）。

## Updates

### 2026-08-24: 時間差多エージェント file-back がクリーンに共存（本 session 中の live event）

本 remeasure を file back する最中に、別 session が2 file-back（02:37 [[ai-consumer-cost-and-trust]] へ Simon 限定合理性 Updates / 02:39 [[false-negative-recall-benchmark-2026-08-24]] へ precision+density 追記）を入れた。私の #2 file-back は index/goal/log を store から再生成したが、彼らの concept 編集・entity への precision 追記・log 全 entry を**クロバーせず時系列順に共存**（検証済み）。合成 Part B より強い、実リポジトリでの多エージェント coexistence の肯定証拠。ただし全イベントは**時間差**（同時刻でない）で、共有 store が直列化した結果。

**lock 消失の訂正**: 上の結論 §2 と Open Q「本 session の lock 消失」は file-back #1 の1回のみで、#2＋間の別 session 2回は全て lock 正常＝**未再現**。#1 は並行由来でなく自損疑い（zsh 変数失敗→再実行）。「協調層が脆い live evidence」としては弱め、監視項目に格下げ。残る協調層リスクは真に同時刻の write＋working-tree/lock 層＋in-flight 可視化に絞る。
