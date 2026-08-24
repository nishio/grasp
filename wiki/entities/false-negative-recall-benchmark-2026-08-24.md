---
type: entity
summary: nishio 全コーパス（project nishio, 25,897 pages）で「grasp read の 2-hop related は grep が原理的に落とすページを回収するか」を偽陰性で実測し、続く 8-query 判定で回収ページの precision まで測った記録。[[read-vs-grep-benchmark-2026-06-24]] の Open Question（gather/近傍が grep の出せない 2-hop を bounded token で返せるか）を閉じる続編。recall は確認（hub で related の 60–90% が grep 不可視・出力 10–30倍 bounded）だが precision は低い（lenient 平均 0.40・strict core-only 0.07）。precision は density と正相関（r=+0.81）だが真の driver は bridge-hub の topicality で、grasp の `via` 露出がその判定材料になる（grep には無い）。∴ grasp の対 grep 優位は「密で topical-hub に橋渡しされた hub 概念の retrieval」に絞られ、疎/generic-hub 概念では 2-hop はほぼ noise。
sources:
  - `~/.grasp/grasp.sqlite` project `nishio`, schema v14, source raw/nishio.json
  - session A/B probe 2026-08-24: `scratchpad/fn_probe.py`（grep-arm=`grasp search --limit 100000`, grasp-arm=`grasp read`）
  - density sweep 2026-08-24: `scratchpad/sweep.py` / `sweep_top20.py`（35 concept を incoming-link density 7 bucket で層化サンプル）
  - precision judges 2026-08-24: 8 query の grep 不可視 top-20 related を独立 subagent 判定（core/tangential/noise）
  - 敵対的検証: `grasp peek` で偽陰性 3 page（ブレインストーミング/マインドマップ/U理論）の本文に literal `KJ法` が 0 行であることを直接確認
id: cd68a9777338ee0f35546c4f
title: false-negative-recall-benchmark-2026-08-24
---

## Context

[[read-vs-grep-benchmark-2026-06-24]] は「速度は非論点・出力の bounded さが差」を示し、Open Question として
「grep が原理的に出せない 2-hop neighborhood を bounded token で返せることを示す」を残していた。
本 entity はその測定。軸を **token 量**から **recall（偽陰性）**へ移し、grep が *黙って落とす* ページを数える。

## 方法

query Q に対し同一コーパス（project `nishio`）で2手法:

- **grep-arm** = `grasp search Q --limit 100000`（literal line substring ＝ grep 意味論）。surface する distinct page 集合と生ログ byte を測る。
- **grasp-arm** = `grasp read Q`（本文＋行レベル逆リンク＋2-hop related＋未解決）。bounded 出力 byte と related titles を取る。
- **偽陰性** = grasp が related として出すが grep-arm の page 集合に無いページ（＝本文に literal Q が一度も無いのに Q に構造的に隣接）。

## 実測値（2026-08-24, 5 query バッチ 12s / 各コマンド sub-second）

| Q | grep pages | grep bytes | grasp bytes | related | 偽陰性（grep 不可視 related） |
|---|---|---|---|---|---|
| KJ法 | 695 | 501 KB | 33 KB | 20 | **12** |
| 知的生産 | 956 | 1.0 MB | 64 KB | 20 | 6 |
| 発想法 | 133 | 83 KB | 38 KB | 20 | **18** |
| ベイズ | 49 | 15 KB | 3 KB | 2 | 0 |
| 中動態 | 1 | 0.5 KB | 7 KB | 0 | 0 |

## 敵対的検証（不在主張の裏取り）

「grep がこれらを落とす」は不在主張なので、KJ法 の偽陰性 3 page を `grasp peek` で直接確認:

- **ブレインストーミング**（本文 32 行）・**マインドマップ**（45 行）・**U理論**（12 行）: 本文に `KJ法` の文字列が **0 行**。しかし全て発想法/思考整理の同族概念で、grasp は 2-hop 橋（例 `マインドマップとKJ法`, `KJ法勉強会@サイボウズ`）経由で related に出す。
- **探検ネット**: 本文 0 行の赤リンク概念ハブ。grep は grep する本文が無く原理的に扱えないが、grasp は参照側文脈から related に出す。

## 結論（3点・recall 段階）

1. **hub 概念では grasp が grep の偽陰性を実際に回収する。** related の 60–90%（KJ法 12/20・発想法 18/20）が literal Q を含まない同族ページ。これは token-bounded AI に固有の失敗モード＝absence の hallucination（[[ai-consumer-cost-and-trust]] 軸2）を直接潰す。行レベル backlink は `[Q]` を含むので grep でも拾えるが、**2-hop related こそ grep が原理的に出せない到達範囲**で、[[read-vs-grep-benchmark-2026-06-24]] 結論3・Open Question の実証。
2. **同時に出力は 10–30倍 bounded。** grep は hub で 500KB–1MB を無制限に吐く。grasp は 33–64KB。token 換算（日本語 UTF-8 ≈3B/字）で KJ法 grep ≈120–160K token 対 grasp ≈10K token。別軸で [[read-vs-grep-benchmark-2026-06-24]] を再現。
3. **利得は density-conditional（誇張の歯止め）。** 疎な leaf 概念では grasp は何も足さない: ベイズ（related 2, 偽陰性 0）・中動態（related 0, かつ grasp 7KB > grep 0.5KB で僅かに重い）。→ この「recall は取れる」段の主張は、下の Updates で **precision の代償**が判明したことで大きく限定される。

## Updates 2026-08-24: precision と density（上の Open Questions を解決）

上の結論は recall（grep が落とすページを grasp が surface する）だけを見ており、「回収したページが実際に有用か（precision）」を測っていなかった。density sweep（35 concept 層化）と 8-query の独立判定（各 query の grep 不可視 top-20 related を core/tangential/noise 分類）で両 Open Question を埋めた。

**operating point の確定**: 無制限 2-hop では偽陰性 fraction はほぼ 1.0（related はほぼ全て grep 不可視）だが、それは noise tail まで数えているため。grasp が実際に提示する **ranked top-20** を operating point とする。

**precision（8 query, grep 不可視 top-20 related を判定）:**

| Q | density(incoming) | 偽陰性@20 | core | tang | noise | precision(core+tang) | strict(core) |
|---|---|---|---|---|---|---|---|
| webtiling | 2 | 20 | 0 | 1 | 19 | **0.05** | 0.00 |
| 主観的な思い込み | 1 | 20 | 2 | 5 | 13 | 0.35 | 0.10 |
| Accessism | 9 | 19 | 4 | 3 | 12 | 0.37 | 0.21 |
| ADHD | 15 | 18 | 0 | 7 | 11 | 0.39 | 0.00 |
| SNS | 27 | 13 | 0 | 5 | 8 | 0.38 | 0.00 |
| イノベーション | 56 | 9 | 0 | 5 | 4 | 0.56 | 0.00 |
| LLM | 57 | 11 | 1 | 1 | 9 | **0.18** | 0.09 |
| KJ法 | 155 | 12 | 2 | 9 | 1 | **0.92** | 0.17 |

- **平均 precision（lenient core+tang）= 0.40 / median 0.38、strict（core のみ）= 0.07。** ＝ grep が落とすページを grasp は回収するが、**回収物の過半は noise、Q の中核ページはほぼ無い**。recall↑ の代償に precision が低い。上の「結論」は precision 前提なしの過大評価だった。
- **corr(density, precision) = +0.81（log density で +0.63）**: 密な概念ほど precision が高い（KJ法 0.92 ↔ webtiling 0.05）。**density の Open Question はこの正相関で答え、閾値ではなく勾配**。
- **corr(density, recall=偽陰性@20) = −0.66**: 密な概念ほど grep 不可視 fraction は下がる（hub の隣人は Q を literal にも書くので grep が拾う）。recall と precision は density で逆に動く＝トレードオフ。

**真の driver は density でなく bridge-hub の topicality（8 judge の収束所見）:** 判定者は全員独立に、related が Q に *topical な* ハブ（KJ法勉強会@サイボウズ, マインドマップとKJ法, しない理由探し）経由なら有用、*generic/temporal* ハブ（日記2025-xx, XREAL One, pIntEn 英語化, ドラッカー, 主観か客観か…）経由なら noise、と判定した。density はこの topicality を不完全に proxy するだけ（**LLM が反例**: density 57 と高いのに precision 0.18 ＝ 隣人が Plurality/Polis 勉強会という generic hub 経由）。webtiling（precision 0.05）は 2-hop が同週の開発日記ハブに橋渡しされ、ほぼ純 noise。

**∴ 改訂した value 主張:** grasp の grep 越え（2-hop 偽陰性回収）が実利になるのは **①density が高く ②topical な dedicated hub に橋渡しされる概念**（KJ法が代表）に絞られる。疎/generic-hub 概念では 2-hop はほぼ noise で grep 越えの価値は消える。改善の梃子候補として当初は「`via` bridge-hub を topicality で down-weight」を挙げたが、下の Updates 2026-08-24b でこれは falsify した。

## Updates 2026-08-24b: 実装可能な修正の切り分け（down-weight を falsify、co-citation tiering へ）

「有用なツールを作る」観点で、上の precision 問題を潰す具体実装を検討し、案のメカニズムを実装前に手元 labels で検証した。

- **falsify: bridge-hub の out-degree による down-weight は効かない。** 「noise は高次数のスーパーノード（日記・索引）経由」という仮説を、判定済み 118 item の最強 bridge の out-degree で検定したところ、useful / noise とも **out-degree 中央値 8** で分離しない（閾値では noise を 16% しか落とせない）。generic hub は raw な次数では捕まらない。∴ 次数ベースのランカーは作らない。上の「via down-weight」提案は撤回。
- **効く唯一の構造信号 = grasp が既に持つ `score`（共有 bridge 数 = co-citation）。** 160 judged item で tier 別 precision: score≥2 で strong precision 0.38（useful の 60% を保持）/ weak 0.20、score≥3 で strong 0.50（useful 31%）。ハードフィルタではなく **confidence 信号**（strong precision も 0.5 止まり、useful の 40–70% は single-bridge=score1 で weak に落ちる）。∴ weak は drop せず demote する。
- **per-query の collapse が本命価値**: score≥2 で strong 件数は webtiling=0 / 主観的な思い込み=0 / ADHD=0（疎・noise 概念は strong が消える）、KJ法=20 / イノベーション=20 / LLM=17（密概念は cluster を保つ）。strong=0 は「この概念は 2-hop が信用できない」という honest な sparsity 信号＝[[ai-consumer-cost-and-trust]] 軸2（negative-result contract）の実装。
- **実装先**: default `grasp read` を confidence-tiered にする（strong tier を prominent、single-bridge の weak tail は count + `--related-weak` フラグ裏に降格、`related_confidence` summary と `sparse` フラグを出す）。Codex 指示書 = [[related-confidence-tiering-plan]]。code locus は `cosense.py:604 related()`（score 済み）/ `cli.py:10505 format_related_items`。embedding は使わない。新規 A/B でなく本 session の 8 query labels で smoke test する。

## Open Questions

- ~~偽陰性の precision 未測定~~ **解決（上 Updates）**: lenient 0.40 / strict 0.07、density と +0.81 相関。ただし判定は各 query 1 judge（LLM 審査員）で、judge 間一致（複数審査員の κ）は未測定。precision の絶対値には judge バイアスが乗りうる。
- ~~density 閾値が未定量~~ **解決（上 Updates）**: 閾値でなく勾配（corr +0.81）。真の driver は bridge-hub topicality で density はその proxy（LLM が反例）。実装は bridge-hub の次数 down-weight（Updates 2026-08-24b で falsify）でなく co-citation `score` の confidence tiering（[[related-confidence-tiering-plan]]）へ。
- grep-arm は `grasp search`（同一 store の literal substring）を proxy にした。実 ripgrep on flat MD との差は速度のみで recall 同値のはずだが未確認。
- precision judge は grasp の `via`/lead snippet を材料にしており、grasp の出力構造に依存した評価。独立コーパス知識だけで判定した場合に noise 率が上がる/下がるかは未検証。
