# Log

## [2026-06-23 16:45] ingest | Cosense JSON export の実物（raw/nishio.json, 25791 pages）を確認、import スキーマを確定
- nishio が管理画面 Export Pages（metadata ON）で出した実物を raw/ に配置 → 実スキーマを実測。SPEC が「Codex が実物で確認」と保留していた項目を確定。
- 新ページ [[cosense-json-export]]（entities/）: root/page/line スキーマ ＋ 6 gotcha。確定事項: ① **line に安定 id 無し**（138220 行で 0）→ grasp が import 時採番（原理4 と整合）。② **link graph は export に未保存**（page キーは title/id/created/updated/views/lines のみ）→ line.text を parse してエッジ materialize。③ `[...]` は overloaded（内部リンク 62.7% / 外部URL 23.4% / icon 6.7% / 装飾 3.6% / cross-project 2.8% / 数式 0.7%）、`[[...]]` は **bold でリンクでない**（grasp の `[[wikilink]]` と逆）。④ リンク解決は normalize（case-insensitive＋空白畳込, 実測 exact→normalize で 208 件だけ解決, title 衝突 1 group）。⑤ title=lines[0].text（≈99.7%）。⑥ users 2人（nishio＋garbot bot, line.userId あり）→ 単一所有前提に注釈。
- scale: 25791 pages / 724981 lines / 118MB。内部リンク instance 133022・distinct target 61613・既存解決 15702・**red link 45703** → `wanted` は ranking 必須（SPEC Open Q 確定。signal: 出現回数/views/recency）。
- [[SPEC]] 更新: line 40 の保留注記を確定事実＋[[cosense-json-export]] 参照に置換、MVP に実データ scale を追記、Open Q「read の近傍境界」に wanted ranking 必須を追記。

## [2026-06-23 15:56] decision | 保存形式 = 独自フォーマット（Markdown でない）、import は別責務、MVP = Cosense JSON export を読む
- nishio 訂正2点: ①保存形式は独自であるべき — Markdown が逆リンクメンテのしがらみの**発生源**（リンク=テキスト、逆リンクは未保存→全文スキャン or 書き戻し。独自なら逆リンク=エッジの逆読みで「維持」概念が消える）②「読める」は import の話で保存形式と独立。
- 新 decision [[persistence-custom-format]]: native=独自（Cosense の行/グラフモデルを正規化、ゼロ発明でない）。三層分離 native store ← import adapter（Cosense JSON / 後で Markdown）← CLI。「既存森40+を読める」は Markdown adapter で達成（native を Markdown にしない）。
- [[SPEC]] 更新: 保存形式/入力(import)/MVP 節を追加、データモデルを「エッジを native 保持」に、Open Q の永続化を解決済みに。MVP = Cosense JSON export 1ファイルを `read`/`backlinks`/`wanted` の読み取り専用3動詞で扱い、中核仮説を実データで検証。
- Codex への確認事項: Cosense export の実スキーマ（line-id 有無、リンク `[title]` 構文）。

## [2026-06-23 15:41] 作成 + 設計対話 ingest | grasp dev wiki を新規 scaffold し、llm-wiki での設計対話を founding pages に固定
- **由来**: nishio の llm-wiki 対話。「Cosense は複数人前提だが一人でも Markdown 集合より効く。"Co-" になる前の Scrapbox を CLI で扱える substrate が LLM に良い」→ design B を選択。
- **分業**: 本 wiki ＝ spec / 設計判断 / gotcha（Codex が読む context）、Codex ＝ 実装。
- **固定した founding pages**:
  - [[SPEC]] — CLI 動詞（read=近傍同梱 / backlinks=行つき / related=2-hop / wanted=赤リンク / write=グラフ自動更新 / transclude / rename=identity保持）＋ data model（page id / line-id / materialized backlinks）＋ 5 中核原理 ＋ Open Q。
  - [[why-design-B]]（decisions/）— Scrapbox を Co-層 / グラフモデル層に分解、A（忠実clone, name=identity欠陥相続）vs B（あるべき姿, identity-without-name 追加）の fork で B 採用。用途は（あ）LLM-author 向け・人間UIなし。cosense-cli との区別。
- **次**: 永続化形式（既存 Markdown 互換 or 独自）の決定 → Codex に最小プロトタイプ（read / backlinks / wanted の 3 動詞、読み取り専用）を渡す。
- メタ: 親 llm-wiki の `LLM Wiki 設計のトレードオフ` 軸5（機械 vs 意味）× `名前ではなくIDで識別する設計`（identity-without-name）の収束として本プロジェクトが立った。
