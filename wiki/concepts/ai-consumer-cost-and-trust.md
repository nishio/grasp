---
type: concept
summary: grasp の設計上の主たるユーザ＝CLI 越しにグラフを読む AI は、人間 CLI operator と消費コスト構造・失敗許容度が違う。2軸 — round-trip/token の cost（少呼び出しで必要十分に rich）と negative-result の trust（空結果は情報でなければならない＝沈黙の偽陰性は absence の hallucination）。read=近傍同梱の why であり、backlog の ranking 原理。
sources:
  - raw/claude-feedback-2026-06-23.md（grasp v1 への AI 消費者フィードバック, Claude Opus 4.8）
  - wiki/entities/ai-consumer-feedback-2026-06-23.md
---

# Concept: AI consumer の cost-and-trust model

grasp の設計上の主たるユーザは **CLI 越しにグラフを読む AI エージェント**（[[why-not-scrapbox-clone]] 用途あ・人間 UI なし）。その消費コスト構造と失敗許容度は人間 CLI operator と違う。grasp が「retrieval substrate として AI に効くか」は raw capability でなく **AI にとってどう振る舞うか**で決まる。軸は2つ。

## 軸1: cost（round-trip / token の経済）

AI にとって 1 回の `grasp` 呼び出しは:

- **レイテンシ**（tool round-trip）
- **中間出力が context window を消費**（次の推論まで残り続ける）
- **次にどの verb を叩くか決める推論トークン**

∴ 最適は「**少ない呼び出しで、必要十分に rich な返り**」。これが read=近傍同梱（中核原理1, 実装済み [[grasp-v1-implemented]]）の *why*: 1 read が本文＋行レベル backlinks＋related＋unresolved を返し、read→backlinks→related の 3-4 往復を 1 往復に畳む。

同じ原理が backlog の複数候補を ranking する（[[grasp-backlog]]）:

- `read --related-snippets`: hub 探索を 1 往復で（各 related の中身を追加 read せずに見る。default は Cosense UI 同様 先頭 ~5 行）。
- `gather "<query>" --budget`: 問いから「最小ページ集合＋近傍」を token 予算内で返す retrieval orchestration。
- text 出力の **line-id 別名**（2026-06-24 実装済み）: 24 桁 page-id＋index を全行に付けるのは冗長なので `P1:0` 等に畳み context を空ける。完全 ID は `--json` / `--full-ids`。

ただし token 削減は**意味のある token を捨てない範囲**で。`[nishio.icon]`（block の著者）や bare image URL（人間に画像提示・将来 AI も読む）のような decoration を畳む `--strip-decoration` は **却下**（[[grasp-backlog]]）— decoration は noise でなく情報。cost 軸は「畳めるところを畳む」のであって「fidelity を捨てる」ことではない。

**設計テンション**: 太い `gather` verb は orchestration を CLI に寄せ、「薄い CLI / Skill がオーケストレーション」境界（[[delivery-cli-plus-skill]]）と緊張する。薄さを保つなら Skill 側に gather レシピを明文化、太くするなら `gather` verb。判断は nishio に委ねるが、**round-trip は AI には実費**という事実は薄さの議論の前提になる。

## 軸2: trust（negative-result contract）

人間は検索が空振りしても自然に言い回しを変えて再試行する。AI が retrieval ツールに `(none)` を返された最悪のシナリオは「**書かれていない**」と結論してユーザにそう答えること＝**absence の hallucination（沈黙の偽陰性）**。retrieval-augmented な回答で最も信頼を壊す。

∴ 空結果は **情報**でなければならない。AI が区別したいのは:

- **絶対的不在**: ストアにその概念が無い（→ ユーザに「書かれていない」と言える）
- **マッチ失敗**: 有るが surface form / 検索意味論で取れなかった（→ 別の引き方を試すべき・断定してはいけない）

grasp の `read` / `link-stats` の zero-hit、`search` の空結果、`related` の空結果、`path` の no-path は `recovery_hints` を返す（実装済み）。ヒントは command 文字列だけでなく **実データ**（近い title 候補・正規化で寄せた候補・部分一致 line、related/backlinks/link-stats）を載せると、1 往復節約＋判断材料になる。この contract は今後追加する retrieval verb（例: `gather`）にも揃える。

これが **recall（明示 boolean / page scope / 正規化マッチ）を vector search より先に直す**理由でもある: 沈黙の偽陰性は AI には人間より危険なので、embeddings の前に boolean/正規化/negative-contract で底上げするのが AI 価値の順序。page 単位 AND は 2026-06-23 に一度 implicit に実装したが、2026-06-24 に default literal + 明示 `--mode boolean --scope page` へ変更した。`search` 空結果の recovery hints は 2026-06-23 に実装済み。

## 根

両軸の根は同じ — grasp は AI 消費者にとって **round-trip が実費で、沈黙が主張**。capability の絶対量でなく recall と往復コストに AI は依存する。この model が read=近傍同梱（implemented）を正当化し、Tier 1-2 backlog（remaining recall・negative-contract・snippets・gather・token economy）の優先度を決める。dated な観測元は [[ai-consumer-feedback-2026-06-23]]。

## Updates

### 2026-06-24: 第3の消費者軸 — substrate を持たない公開人間読者

本ページは主ユーザを「CLI 越しに読む AI（人間 UI なし）」と明示し、[[positioning-two-personas]] も author / Markdown 束ユーザの2層。come-from 対話（[[come-from-declared-gather]] §8）で、この2軸モデルの**外**にいる第3の消費者が surface した: **公開された PKM を読む人間ストレンジャー**（個人 PKM ×世界公開という二重性が生む）。

この消費者は **grasp を実行できない**（substrate を持たない）。AI 消費者の「round-trip / negative-contract」とは別の失敗モードを持つ —— リンクの4番目の仕事「読者ケア」（一般的でない語の説明へ辿らせる親切）が、公開面が frozen 静的エクスポートだと届かない。これは backlog が index/log で警戒する「frozen view」問題を**本文 hub と公開人間読者**へ拡張したもの。

grasp scope の判断点（nishio）: 「substrate-backed な公開 view を出す」を grasp が担うか publish に委譲か。少なくとも come-from-at-render（[[come-from-declared-gather]] §4 render 層）が、著者を over-link させずにこの消費者を served にする軽量機構。本 2軸モデルは AI 消費者に閉じているが、**読者ケア軸はその外にある**ことを明記しておく。

### 2026-06-24: 軸1 の実測裏付け — コスト軸は wall-clock でなく token

本番コーパス（25,798 pages / flat MD 53.2MB ≈ 14M token）で「MD 全読み vs grep vs grasp search」を実測（[[read-vs-grep-benchmark-2026-06-24]]）。軸1 の主張「round-trip が実費 / 中間出力が context を食う」が数字で裏付いた:

- **ディスク wall-clock は3手法とも sub-second**（cat 0.02s / grep 0.3s / grasp 0.25–0.75s）→ 速度は論点でない。効くのは context に入る token 量。MD 全読みは ~14M token で 1M window の14倍、**そもそも入らない**。
- **grep は出力が無制限**（`民主主義` 1 クエリで 498KB≈125K token の生ログ）、**grasp search は bounded**（7–14KB）。∴ grasp の対 grep 優位は「速さ」ではなく「**同等 wall-clock で bounded・ranked・structured を返す**」点 = read=近傍同梱 / `gather --budget` / related-snippets の token-economy 動機の実証。
