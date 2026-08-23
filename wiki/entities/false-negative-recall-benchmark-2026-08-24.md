---
type: entity
summary: nishio 全コーパス（project nishio, 25,897 pages）で「grasp read の 2-hop related は grep が原理的に落とすページを回収するか」を偽陰性で実測した記録。[[read-vs-grep-benchmark-2026-06-24]] の Open Question（gather/近傍が grep の出せない 2-hop を bounded token で返せるか）を閉じる続編。5 query の A/B（grep-arm=literal substring search / grasp-arm=read 近傍同梱）で、hub 概念（KJ法/知的生産/発想法）は related の 60–90% が grep 不可視（本文に literal Q が無い同族ページ）かつ出力は 10–30倍 bounded、疎な leaf 概念（ベイズ/中動態）は利得ゼロ〜負。∴ grasp の対 grep 優位は「有用」一般でなく「リンクグラフが密な hub の retrieval で、同 wall-clock・1/10–1/30 token で grep が落とす同族ページを回収する」という density-conditional な形でだけ立つ。
sources:
  - `~/.grasp/grasp.sqlite` project `nishio`, schema v14, source raw/nishio.json
  - session A/B probe 2026-08-24: `scratchpad/fn_probe.py`（grep-arm=`grasp search --limit 100000`, grasp-arm=`grasp read`）
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

## 結論（3点）

1. **hub 概念では grasp が grep の偽陰性を実際に回収する。** related の 60–90%（KJ法 12/20・発想法 18/20）が literal Q を含まない同族ページ。これは token-bounded AI に固有の失敗モード＝absence の hallucination（[[ai-consumer-cost-and-trust]] 軸2）を直接潰す。行レベル backlink は `[Q]` を含むので grep でも拾えるが、**2-hop related こそ grep が原理的に出せない到達範囲**で、[[read-vs-grep-benchmark-2026-06-24]] 結論3・Open Question の実証。
2. **同時に出力は 10–30倍 bounded。** grep は hub で 500KB–1MB を無制限に吐く。grasp は 33–64KB。token 換算（日本語 UTF-8 ≈3B/字）で KJ法 grep ≈120–160K token 対 grasp ≈10K token。別軸で [[read-vs-grep-benchmark-2026-06-24]] を再現。
3. **利得は density-conditional（誇張の歯止め）。** 疎な leaf 概念では grasp は何も足さない: ベイズ（related 2, 偽陰性 0）・中動態（related 0, かつ grasp 7KB > grep 0.5KB で僅かに重い）。∴ 正しい主張形は「grasp は有用」一般でなく **「リンクグラフが密な hub 概念の retrieval で、同 wall-clock・1/10–1/30 token で grep が落とす同族ページを回収する。疎な leaf では利得ゼロ〜負」**。[[value-is-problem-solving-not-novelty]] の「唯一未踏＝token-bounded AI のコスト関数」に対応する測定可能な value proof で、[[use-case-experiment-as-outcome-story]] の outcome story 形。

## Open Questions

- 偽陰性の **precision** は未測定。回収した grep 不可視 related が全て「有用に関連」かは per-page 判断が要る（本 entity は KJ法 3 page のみ本文確認）。noise 混入率を測れば「recall を上げて precision を落とす」トレードオフの位置が出る。
- density の閾値が未定量。related 数や link-stats N を density proxy にして「grasp が grep を上回る境界」を回帰で引けるはず。leaf/hub の二分でなく連続量で示すのが次段。
- grep-arm は `grasp search`（同一 store の literal substring）を proxy にした。実 ripgrep on flat MD との差は速度のみで recall 同値のはずだが未確認。
