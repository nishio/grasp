# Log

## [2026-06-23 15:41] 作成 + 設計対話 ingest | grasp dev wiki を新規 scaffold し、llm-wiki での設計対話を founding pages に固定
- **由来**: nishio の llm-wiki 対話。「Cosense は複数人前提だが一人でも Markdown 集合より効く。"Co-" になる前の Scrapbox を CLI で扱える substrate が LLM に良い」→ design B を選択。
- **分業**: 本 wiki ＝ spec / 設計判断 / gotcha（Codex が読む context）、Codex ＝ 実装。
- **固定した founding pages**:
  - [[SPEC]] — CLI 動詞（read=近傍同梱 / backlinks=行つき / related=2-hop / wanted=赤リンク / write=グラフ自動更新 / transclude / rename=identity保持）＋ data model（page id / line-id / materialized backlinks）＋ 5 中核原理 ＋ Open Q。
  - [[why-design-B]]（decisions/）— Scrapbox を Co-層 / グラフモデル層に分解、A（忠実clone, name=identity欠陥相続）vs B（あるべき姿, identity-without-name 追加）の fork で B 採用。用途は（あ）LLM-author 向け・人間UIなし。cosense-cli との区別。
- **次**: 永続化形式（既存 Markdown 互換 or 独自）の決定 → Codex に最小プロトタイプ（read / backlinks / wanted の 3 動詞、読み取り専用）を渡す。
- メタ: 親 llm-wiki の `LLM Wiki 設計のトレードオフ` 軸5（機械 vs 意味）× `名前ではなくIDで識別する設計`（identity-without-name）の収束として本プロジェクトが立った。
