---
type: todo
summary: Codex 実装指示書。`grasp read` の related（2-hop）を co-citation `score` で confidence tier に分け、default read は strong tier のみ prominent に出し、single-bridge の weak tail は count + 明示フラグ裏に降格する。動機は [[false-negative-recall-benchmark-2026-08-24]] の実測: grep 不可視 2-hop related の precision は lenient 0.40 / strict 0.07 で過半が noise。noise は generic/temporal hub 経由で 2-hop 接続しただけ。**先に falsify 済みの案＝bridge-hub の out-degree で down-weight は効かない**（noise/useful とも median degree 8）。効く唯一の構造信号は grasp が既に持つ `score`（＝共有 bridge 数 / co-citation）。embedding は使わない（deterministic reader を保つ）。
sources:
  - wiki/entities/false-negative-recall-benchmark-2026-08-24.md（precision/density/falsification の実測 SSoT）
  - grasp/cosense.py:604 `related()` / :636 `_related_missing_target()`（score = co-citation Counter、既に計算済み）
  - grasp/cli.py:664 `--related-limit`（read, default 20）/ :10505 `format_related_items`（`score` を既に表示）
  - session labels 2026-08-24: 8 query × grep 不可視 top-20 related の core/tangential/noise 判定（validation set）
id: 89e70c8b3a0fabf4d7b0efd6
title: related-confidence-tiering-plan
---

# related confidence tiering plan（Codex 指示書）

## なぜやるか（1段落）

現状 `grasp read` は related（2-hop）を score 降順 20 件、flat に出す。実測（[[false-negative-recall-benchmark-2026-08-24]]）で、grep 不可視 related の precision は平均 0.40（strict 0.07）で**過半が noise**。noise は日記・プロジェクト索引などの generic/temporal hub を 1 本経由してたまたま 2-hop 接続したページ。毎回 flat に 20 件出すと、消費 agent に「grasp の related は信用するな」を学習させ、grasp の差別化（grep が出せない 2-hop 到達）を逆に毀損している。**related を trust できる形にするのが目的。**

## 先に潰した案（再実装しない）

- **bridge-hub out-degree による down-weight**: 「noise は高次数のスーパーノード経由」という仮説は falsify 済み。noise / useful の最強 bridge の out-degree 中央値はともに 8、閾値では noise を 16% しか落とせない。**次数ベースのランキングは作らない。**
- **embedding / vector 類似度での re-rank**: grasp の deterministic reader 原則（[[value-is-problem-solving-not-novelty]] / recall を vector より先に、の方針）に反する。本 plan では使わない。

## 効くと確認済みの信号

grasp が既に計算している related `score`（= Q と候補ページの**共有 bridge 数** = co-citation, `cosense.py:610` の `Counter`）。session labels（160 judged item）での tier 別 precision:

| cut | STRONG n | STRONG precision | STRONG が拾う useful の割合 | WEAK n | WEAK precision |
|---|---|---|---|---|---|
| baseline(flat) | 160 | 0.28 | 100% | – | – |
| score≥2 | 72 | 0.38 | 60% | 88 | 0.20 |
| score≥3 | 28 | 0.50 | 31% | 132 | 0.23 |
| score≥4 | 21 | 0.57 | 27% | 139 | 0.24 |

- **score は confidence 信号でありハードフィルタではない**（strong precision も 0.38–0.57 止まり、useful の 40–70% は single-bridge=score1 で weak に落ちる）。∴ **weak を drop してはならない。demote/label して残す。**
- 定性的に一番きれいな境界は **score==1（single incidental bridge）を weak、score≥2（複数 bridge で corroborated）を strong**。default 推奨 cut = **score≥2**。
- per-query の collapse が本命の価値: score≥2 で strong 件数は webtiling=0 / 主観的な思い込み=0 / ADHD=0（疎・noise 概念は strong が消える＝正しい）、KJ法=20 / イノベーション=20 / LLM=17（密概念は cluster を保つ）。**strong=0 は「この概念は 2-hop が信用できない」という honest な sparsity 信号**（[[ai-consumer-cost-and-trust]] 軸2 の negative-result contract の実装）。

## 実装（`grasp read` と `related`）

### データ

1. `cosense.py:604 related()` と `:636 _related_missing_target()` の各 item に `tier` を付ける: `score >= STRONG_MIN` → `"strong"`, else `"weak"`。`STRONG_MIN` は定数（既定 2）。既存の `score` / `via` / sort はそのまま（sort は既に `-score` 優先なので strong が上に来る）。
2. read 結果に related summary を足す: `related_confidence = {strong_count, weak_count, strong_min, sparse: bool}`。`sparse = strong_count == 0`。missing-target path でも同様に付ける。

### CLI（read）

3. 既定の read 出力（text / json 両方）は **strong tier を related として prominent に出す**。weak tier は既定では**本体に列挙せず**、末尾に1行で `weak related: N 件（single-bridge, --related-weak で展開）` と件数だけ出す。`sparse` の時は `related: strongに該当なし（N 件の weak を隠匿; 概念が疎/2-hop 低信頼）` と明示する。
4. フラグを追加:
   - `--related-weak`（既定 off）: weak tier も本体に列挙する。旧来の flat 挙動が要る時用。
   - `STRONG_MIN` を上書きする `--related-strong-min N`（既定 2）。0 にすると全 related が strong 扱い＝旧挙動と等価（後方互換のエスケープハッチ）。
   - 既存 `--related-limit` は strong/weak 合算の上限として維持。strong だけの上限が要るなら別途 `--related-strong-limit` を検討（初期は不要）。
5. `format_related_items`（`cli.py:10505`）を tier 対応にする。text では strong を現行フォーマットで、weak は `--related-weak` 時のみ `(weak, single-bridge)` marker 付きで出す。JSON の related item に `tier` を、result 直下に `related_confidence` を追加する。
6. スタンドアロン `grasp related` verb（`cli.py:809`）にも同じ `tier` / `related_confidence` / `--related-weak` / `--related-strong-min` を通す。

### 非目標 / ガード

- weak を drop しない（recall 落ちる: ADHD の useful は全て single-bridge で weak 側にいる）。あくまで default 表示からの降格。
- score の計算式（co-citation Counter）は変えない。次数補正・embedding は入れない。
- `read --json` の後方互換: 既存キーは残し、`tier` / `related_confidence` は additive。`--related-strong-min 0` で旧 flat 挙動を完全再現できること。

## 受け入れ確認（新規 A/B 不要 / 手元 labels で smoke test）

session の 8 query ラベル（`scratchpad/judge_bundles.json` の grep 不可視 related と core/tangential/noise 判定）で回帰的に確認する。ハーネスは `scratchpad/fn_probe.py` / `make_judge_bundles.py` 系。合格条件:

1. **密概念が cluster を保つ**: `grasp read KJ法` の default（strong）related に エンジニアの知的生産術 / マインドマップ / 探検ネット / Kozaneba 等が残る（strong≈12–20 件）。
2. **疎/noise 概念が collapse する**: `grasp read webtiling` / `主観的な思い込み` の default related が `sparse`（strong=0）になり、noise 20 件が本体から消え、weak count + `--related-weak` 案内だけになる。
3. **後方互換**: `--related-strong-min 0` で旧 flat 出力（20 件）に一致。
4. `python3 -m unittest discover -s tests` green、`--help` / JSON schema 回帰、`format_related_*` の text golden 更新。

数値目標は「strong tier precision を baseline 0.28 から上げる」だが、**閾値の最終値（2 か 3）は labels 上で precision と strong-recall のトレードオフを見て決めてよい**。0.38（score≥2, recall60%）を既定初期値とし、agent 運用で strong が薄すぎ/太すぎなら `--related-strong-min` で調整、後で既定を動かす。

## Open Questions（実装前に潰さなくてよい）

- weak tier 内をさらに ranking する価値があるか（single-bridge でも topical hub 経由なら useful: ADHD の例）。将来、bridge hub の topicality を安く測る手段が出たら weak の再ランクに使う。今回は扱わない。
- score の corroboration を 2-hop 共有 bridge 数でなく、bridge hub 側の specificity で重み付けする案は、out-degree では falsify 済み。別 proxy（bridge hub と Q の lexical overlap 等、deterministic）は将来の別 plan。
