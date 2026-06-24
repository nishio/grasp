---
type: entity
summary: nishio 以外の第三者（takker）が OpenCode + Deepseek v4 flash で grasp を bare な「このリポジトリを設定して」指示から立ち上げ、`villagepump.json`（43,742 pages / 1,454,430 lines / 413,605 edges / 171,316 unresolved＝nishio store の約2倍規模）を import し、グラフ理論・リンク構造・カテゴリ論争の多ターン retrieval research を完走した外部検証。3つの確認: ①persona1（JP Cosense ヘビーユーザ）が nishio 以外でも刺さる ②Claude 以外の coding agent / 安い LLM でも動く（cross-agent / cross-model portability）③1.45M 行規模でも壊れない（scale headroom）。発見した gap = metadata なし string line で import が落ちる → takker 側が修正し PR #2 として提出、2026-06-24 に merge 済み（1.5.24）。観測の主役は「答え」でなく「LLM が grasp をどう叩いたか」のツール列 = read=近傍同梱 loop の実走証跡。
sources:
  - https://scrapbox.io/villagepump/grasp （2026-06-24 の公開設計対話・takker 試用ログ）
  - raw/grasp-villagepump-page_2026-06-24.txt
  - https://github.com/nishio/grasp/pull/2 （takker99 "handle string-type lines without metadata", merged 2026-06-24）
---

# takker × OpenCode × villagepump 外部検証 2026-06-24

## なぜ重要か

これは **nishio 以外の第三者による初めての grasp 実走**。これまでの user test（[[persona1-user-test-2026-06-23]] / [[persona2-user-test-2026-06-23]]）はいずれも nishio 自身の dogfooding だった。takker は JP Cosense ヘビーユーザ（cosense / ScrapBubble エコシステム側の人物）で、[[positioning-two-personas]] の **persona1 の demographic にちょうど当てはまる別人**。∴ この test は「persona1 が nishio 固有でなく一般化するか」「Claude 以外の agent / 安い LLM で動くか」「nishio store より大きい corpus で壊れないか」の3つを同時に検証した。

nishio のメタ観察（出典 Scrapbox）: 「graspの設計的に、答えそのものより**答えを出すまでに LLM が grasp をどう使っているのか**のほうが重要そう」。∴ この entity の主眼は research の結論でなく、**LLM が叩いたツール列**＝ read=近傍同梱 loop が別 agent + 別 model でも自然に回ったことの証跡。

## セットアップ（bare 指示からの自走）

OpenCode + `Deepseek v4 flash`（takker 曰く「おかねないので」＝安いモデル）で、指示は1行:

> `https://github.com/nishio/grasp を設定して。`

agent はこれだけで clone → `.venv` に `pip install -e .` → `~/.bash_aliases` に `grasp` alias 追加 → `~/.claude/skills/grasp` に symlink → `grasp --help` 動作確認、まで完走した。**README が「主たるユーザは AI agent」前提で書かれている（[[grasp-v1-implemented]] delivery）ことが、bare 指示での self-setup を成立させている。**

## import 規模（scale headroom）

```
grasp import --cosense villagepump.json
store: ~/.grasp/grasp.sqlite
project: villagepump
schema: 5
pages: 43,742
lines: 1,454,430
edges: 413,605
unresolved_targets: 171,316
```

nishio store（25,791 pages / 724,981 lines / 125,409 edges / 42,770 unresolved）との比較:

| | nishio | villagepump | 比 |
|---|---:|---:|---:|
| pages | 25,791 | 43,742 | ~1.7x |
| lines | 724,981 | 1,454,430 | ~2.0x |
| edges | 125,409 | 413,605 | ~3.3x |
| unresolved | 42,770 | 171,316 | ~4.0x |

villagepump は多人数公開 wiki なので edges / unresolved が pages 比以上に多い（赤リンク・共起が密）。**1.45M 行・41万 edge でも import と read が成立した**ことは scale 余裕の data point。`path` のような dense-hub primitive はこの規模で performance 要再測（[[grasp-backlog]] の path 残課題）。

## import で発見した gap → PR #2（merged）

villagepump export は一部 line が `{text, created, updated, userId}` の dict でなく **plain string**（line metadata なし形式）だった。grasp v1 importer は [cosense.py](../../grasp/cosense.py) で `line_data.get("text", ...)` と dict 前提で読むため、string line に当たって落ちた。

takker 側の agent が local で修正 → `https://github.com/nishio/grasp/pull/2`（takker99, branch `fix/string-lines-cosense-import`）として PR。2026-06-24 に review/merge 済み。`grasp` 1.5.24 以降は string line を metadata なし本文行として import する。current facts は [[grasp-v1-implemented]]、履歴は [[history]]。

## 実走した retrieval（ツール列が主役）

3つの多ターン research を OpenCode 上で完走。いずれも **suggest → search → read（近傍同梱）→ related ページを辿る** という loop で、CLI を summarizer なしの薄い primitive 群として使い、合成は agent 側がやっている（[[delivery-cli-plus-skill]] の「薄い CLI / agent がオーケストレーション」が別 agent でも成立）。

1. **「グラフ理論について誰が何を書いた？関連ページも辿って」**
   - `search "グラフ理論" --context 2` → `suggest "グラフ理"` → `read "グラフ理論" --related-snippets --backlinks-limit 5` → 関連ページ（専門用語っぽくない専門用語 / デライト談義 / 2 hop link / NP完全 / ミュンヒハウゼンのトリレンマ 等）を個別 read、本文 grep。
   - 出力: Summer498 / takker / sta / yosider の発言を**ページ出典つきで**整理。
2. **「Scrapboxのリンク構造に関する言及を深堀り」**
   - `suggest "リンク構造"` → `search "リンク構造" --scope page --context 2` → 上位5ページ read → 毛玉問題・可視化困難・ゴミページ問題・言語化制約・カテゴリ不要論に整理。
3. **「逆に、カテゴリが必要だという主張はないか？」**
   - 一覧性 vs 創発の「宗教戦争」、「分類は破綻するが他にやりようがない」、大きすぎるリンク問題 等を出典つきで対比。

`--context` / `--scope page` / `--related-snippets` / `--backlinks-limit` という、AI consumer feedback 起点で足した bounded retrieval option（[[grasp-backlog]] / [[ai-consumer-cost-and-trust]] 軸1）が、**外部 agent によって実際に選ばれて使われた**。

## takker の評価（positioning の外部裏付け）

- **cross-agent**: 「Claude 想定っぽいけど、OpenCode など他の coding agent でも動く」「雑な指示でも十分使える」「最近の LLM の性能の良さに助けられている」。
- **cross-model**: Deepseek v4 flash（安いモデル）で上記を完走。
- **対 cosense-cli positioning**: 「offline 版の `helpfeel/cosense-cli` といったところ」「読み込み速度の違いや一度に検索可能な範囲が違うだろうから、同じタスクでも cosense-cli と grasp で違いが出そう」。[[cosense-cli]] の「hosted 操作=cosense-cli / local 高速 read=grasp」使い分けに、cosense-cli 側エコシステムの人物からの外部裏付けがついた。
- **multi-project**: 「複数 project を同時に読むこともできるかな」（curiosity。実装は [[multi-project-store]] で1 store 複数 namespace 済み）。

## 含意

非自明な結論（2026-06-24 分析）を強い順に:

- **grasp はモデル水準を下げる。** 安い Deepseek v4 flash + 雑な指示で完走したのは「LLM が賢いから」だけではない。構造化出力（ranked backlinks / related / 近傍同梱）を CLI 側が作るので、モデルは薄い recipe を回すだけでよい。intelligence が CLI の structured output に外部化されている。これは [[delivery-cli-plus-skill]] の「薄い CLI / agent がオーケストレーション」境界が正しかった証拠であり、それ自体「弱いモデルでも使える retrieval」という地味な差別化。
- **意図した retrieval loop が外部 agent で自然発生した。** `suggest→search→read(近傍同梱)→related 辿り` は read=近傍同梱で狙った使われ方そのもので、grasp を知らない別 agent が教えられずそのパターンに導かれた。さらに AI consumer feedback 起点で足した option（`--context` / `--scope page` / `--related-snippets` / `--backlinks-limit`, [[grasp-backlog]] / [[ai-consumer-cost-and-trust]] 軸1）が、なぜ存在するか知らない agent に実際に選ばれた＝あの backlog 群が机上でなかった裏付け。
- **scale 余裕は "read" について証明、"graph 推論" については未証明。** import & hot read path は 1.45M 行 / 41万 edge で成立した。だが villagepump は edge 3.3x・unresolved 4.0x（多人数公開ゆえ密）で、`path` / `gather` は未測。nishio store でも path は既に 4-5s。証明されたのは hot read path だけ。
- **takker が向けたのは Co-（多人数協調）corpus だった。** grasp は Co- 層を削いだ substrate（[[why-not-scrapbox-clone]]）なのに、多人数公開 wiki を読ませて機能した。read には問題ない（他人のグラフを読むリーダー）。だが write/identity 層（[[write-layer-alpha-and-replay-test]]）が来た瞬間、「単一 AI 所有 store」モデルと多人数 authored corpus が「誰の identity か」で衝突する伏線。read-consumable だが write-ownable でない、という線が将来引かれる。
- [[positioning-two-personas]] persona1 は nishio 固有でなく一般化する第一証拠。かつ persona test 未踏の cross-agent（OpenCode）/ cross-model（Deepseek）/ scale を埋めた。**ただし takker は JP・Cosense native・cosense-cli インサイダー = 教科書的 persona1**。彼が反射的に grasp を「offline 版 cosense-cli」と呼んだのは persona1/Scrapbox 枠が自然に出た証拠で、**persona2 framing は実在の persona2 にまだ一度も当たっていない**（→ [[positioning-two-personas]] Updates）。
- README が agent 前提で書かれていることが bare 指示 self-setup を成立させる（delivery の prose が機能している）。
- 外部 corpus は parser の前提（line=dict）を破った。PR #2 で string line は解消済みだが、非 nishio export は事実上 fuzz test で、import 堅牢性は恒常コスト（[[grasp-backlog]] Parser fidelity）。
- これは良い [[use-case-experiment-as-outcome-story]] でもある（依頼 → 出典つき有用回答）が、第三者・別 agent・別 model・大規模という点で **outcome story を超えた portability/scale 検証** として価値がある。

## Open Questions

- villagepump 規模（41万 edge / 17万 unresolved）での `path` / `gather` / `related` の performance 実測。nishio store の path 4-5s がこの規模でどう伸びるか未測。
- cosense-cli と grasp の「同じ task で違いが出る」を実際に並べて測ると何が見えるか（takker 仮説の検証は未実施）。[[read-vs-grep-benchmark-2026-06-24]] と同じ harness で cosense-cli を足せるか。
