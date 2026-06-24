---
type: entity
summary: nishio 全コーパス（25,798 pages / 750,858 lines / フラット MD 53.2MB ≈ 14M token）で「MD 全読み vs grep vs grasp search」を実測した記録。結論は速度比較が反転する — ディスク wall-clock は3手法とも sub-second で論点でない。効くコスト軸は context に入る token 量で、MD 全読みは ~14M token（1M window の14倍）で物理的に不可能、grep は無制限（1 クエリ 498KB≈125K token もありうる）、grasp search は bounded（7–14KB）。∴ grasp の対 grep 優位は「速さ」では立証できず、立つのは「同等 wall-clock で bounded・ranked・structured を返す」点。[[ai-consumer-cost-and-trust]] 軸1（round-trip/token 経済）の実測裏付け。
sources:
  - `~/.grasp/grasp.sqlite` project `nishio`, schema v5, source raw/nishio.json, imported 2026-06-23
  - session benchmark 2026-06-24: read-vs-grep speed comparison
  - 生成物 `/tmp/nishio_flat.md`（全 pages を `updated DESC` で flat MD 化, 55,823,958 bytes）
  - 計測: `/usr/bin/time -p` で cat / `grep -n` / `python3 -m grasp search`
---

# read vs grep vs grasp benchmark 2026-06-24

## Context

nishio の問い「大規模な Markdown を読んだ上で grep するのとの速度比較をしたい」を実測した。
当初は「大規模 MD を読むのは遅い／grep は速い」という *速度* の話だと想定したが、
本番規模で測ると**速度は論点でなくなり、token 量が論点になる**ことが判明した（結論が反転）。

## 方法

同一コーパス（grasp store の project `nishio`）に対し3手法を測る:

1. **MD 全読み** — store 全行を Scrapbox 順（`# title` + 各行）で flat MD に dump し、その I/O floor（`cat`）と byte/token 量。
   - dump SQL: `pages JOIN lines GROUP BY page ORDER BY updated DESC`、出力 `/tmp/nishio_flat.md`。
2. **grep** — `grep -n "<query>" flat.md` の wall-clock と、返る行の byte/token 量（= LLM が読む量）。
3. **grasp search** — `python3 -m grasp search "<query>"` の wall-clock と出力 byte/token 量。

token は **bytes ÷ 4** の粗い概算（後述 caveat: 日本語は実際もっと多く、「全読み不可」はより強く成立する向きの誤差）。

## コーパス規模

| 項目 | 値 |
|---|---|
| pages | 25,798 |
| lines | 750,858 |
| flat MD | 55,823,958 bytes ≈ **53.2 MB** |
| flat MD ≈ token | **~14M**（bytes/4。日本語混在で実際はさらに多い） |
| dump 時間 | 1.44s（sqlite group_concat、1回限り） |

## 実測値

I/O floor: `cat` 53.2MB MD = **0.02s**（ディスク読み自体は一瞬）。

| query | grep hits | grep bytes (≈token) | grep 時間 | grasp out bytes (≈token) | grasp 時間 |
|---|---|---|---|---|---|
| アイコン | 392 | 55,945 (~14K) | 0.34s | 9,641 (~2.4K) | 0.75s |
| 民主主義 | 2,231 | **498,028 (~125K)** | 0.30s | 14,134 (~3.5K) | 0.26s |
| plurality | 464 | 62,285 (~16K) | 0.35s | 12,947 (~3.2K) | 0.25s |
| 盲点カード | 281 | 35,305 (~9K) | 0.29s | 7,005 (~1.8K) | 0.28s |
| broken | 26 | 7,293 (~1.8K) | 0.34s | 9,139 (~2.3K) | 0.24s |

## 結論（3点）

1. **ディスクの速度は論点でない。** cat 53MB=0.02s、grep=0.3s、grasp=0.25–0.75s。全部 sub-second。
   「大規模 MD を読むのは遅い」のではなく、**そもそも context に入らない**（~14M token = 1M window の14倍）。
   "速度" だと思っていた軸は実は token 量の軸。MD 全読みは規模が数百 KB を超えた時点で
   wall-clock でなく token で死ぬ。

2. **grep vs grasp は速度ではなく出力規律の差。** wall-clock はほぼ互角
   （grasp の 0.75s = Python cold start + sqlite + 構造組立込み。warm store なら ~30ms 起動 / ~83ms read 級、[[language-and-distribution]]）。
   差が出るのは**出力量**: grep は無制限で query 依存（`民主主義` 1 クエリで 498KB≈125K token = 0.5M 予算の1/4を生ログで食う）、
   grasp search は bounded（7–14KB）かつ行レベル構造つき。

3. **∴ grasp の対 grep 優位は「速さ」では立証できない。** 立つのは
   **「同等 wall-clock で bounded・ranked・structured を返す」**点。
   これは [[ai-consumer-cost-and-trust]] 軸1（round-trip が実費 / 中間出力が context を食う）の実測裏付けであり、
   read=近傍同梱・`gather --budget`・related-snippets（[[grasp-backlog]]）の token-economy 動機を数字で支える。
   grep が出せない 2-hop / 行レベル backlink を同じ token 予算で返せるかが、grasp が grep に対して主張すべき差別化（速度ではなく到達範囲×規律）。

## Caveats

- **token は bytes/4 の粗概算。** 日本語は UTF-8 3 bytes/char かつ ~1 token/char 級なので実 token はもっと多い
  → 「MD 全読み不可」は概算よりさらに強く成立する。grep の生ログ token も過小評価。
- **grasp の wall-clock は cold start 込み。** 毎回 Python interpreter + import を払っている。
  warm / long-lived process なら縮む（[[language-and-distribution]] の warm store 実測）。逆に grep は cold でも速い。
- **grep をさらに速くしても結論は変わらない。** agent が実際使う ripgrep は grep より速いが、
  それは「速度は非論点」を強めるだけ。grep を不利にしているのは速度でなく**出力の無制限さ**。
- **公平性の留保。** grasp search は内部で ranking / 構造組立をしている分 grep より「多くの仕事」をしている。
  同じ仕事を grep + 後処理スクリプトで組めば token は絞れるが、その後処理こそ grasp が CLI に内蔵している価値。

## Open Questions

- grasp `gather --budget`（近傍同梱の token 予算 orchestration、[[grasp-backlog]]）を同じ harness で測ると、
  grep が原理的に出せない 2-hop neighborhood を bounded token で返せることを示せるはず。次に測る候補。
- warm process（daemon / persistent）での grasp 再計測。cold start を除いた純粋な検索 wall-clock を grep と並べる。
