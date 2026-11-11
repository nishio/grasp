---
type: entity
summary: Monika（川端薫、未踏ジュニア2026、`KijitoraFinch/Monika` v0.1.0、Rust、MIT）は、LLM エージェントが文書・コード・データの「部分」の間に Link を張り、確認時点の内容（Capture）と今の内容を比べて変化を検査する CLI。grasp とは扱う単位が違う（grasp=自分が所有するページ／行のグラフ、Monika=自分が所有しない外部の対象の範囲）が、grasp の未決のうち4つに具体的な参照実装を持つ。(1) 自分では ID を振れない対象を「意味のセレクタ＋保存した content の比較」で同定し、変化は Link ごとに見直す（stable line identity の外側の答え。grasp wiki の current facts がコードの変化で黙って古くなる問題に直接効く）、(2) 型付き関係に代数的な法則（同値関係・半順序）を契約として書き、`extension test` で機械検査する（typed / directional link を入れる時の型）、(3) 辺の注釈を本文から外した Sidecar の自由 JSON に置き、Core は等値以外を解釈しない（non-semantic edge annotation の置き場）、(4) Resource ごとに鮮度方針（observe／refreshed）を設定で宣言し、全操作に同じく効かせて、結果に使った Observation を添える（Sync freshness の read 以外への反映）。逆引きを専用 verb にせず links|jq|compare|check のパイプで組む点は grasp（AI に bounded な verb を渡す）と逆の選択
sources:
  - https://github.com/KijitoraFinch/Monika （v0.1.0 2026-11-08, README / EXTENSIONS.md / BUNDLED_EXTENSIONS.md / docs/AGENT_GUIDE.md / src/model.rs / src/operations.rs / examples/demo.py。2026-11-11 に local clone `/Users/nishio/monika-mentoring-wiki/work/Monika` で読んだ）
  - monika-mentoring-wiki `wiki/analyses/monika-alpha-beta-release-comparison-20261111.md`（Alpha／Beta／リリース版の比較と、実装を読んだ Updates）
id: 131dd4d8fee604a174fd21f9
title: monika
---

## 何か

- 作者は川端薫（未踏ジュニア2026、メンター西尾）。Monika の設計判断は100%作者のもの。ここでは grasp 側の参考として読む。
- 単位: `Link {id, source, target, annotation}`。端点は `RegionSelector {extension, resource, query}`（または名前付き指定）。`query` の意味は拡張が決める（Markdown の見出しの道筋、コードの symbol、JSON pointer、行範囲、CSS selector など）。
- 正本は `monika.links.json`（Sidecar）。Link を作る CLI は無く、エージェントが通常の編集ツールで書く。CLI は `links`／`read`／`compare`／`check`／`capture`／`refresh`／`gc` で、読む・比べる・固定する・検査するだけ。入出力は JSON Lines、`--at` で JSON pointer を選ぶ。
- 拡張は外部プロセス（JSON Lines プロトコル）。同梱15種も同じプロトコルで動く（`@monika extension serve <name>`）。

## grasp への示唆

### 1. ID を振れない対象の同定と変化検出 —— stable line identity の外側

grasp の [[grasp-backlog]]「stable line identity」は、grasp 自身が `line_id` を mint し、tombstone で記憶する（stable ID requires memory）。これは grasp が所有するページにしか使えない。

Monika は ID を振らない:

- 対象は意味のセレクタで指す（関数名、見出しの道筋など）。行番号で指せば、同じ行番号が指す今の内容を見る。
- `capture` で、その時点の解決結果（Region の `content`）を保存し、Link の端点に Capture ID を記録する。
- `check` は Capture の selector と今の selector が一致しなければエラー（捕捉し直し）。一致すれば `content` だけを比べ、違えば不合格（exit 1）。選択範囲の外への追記で行番号がずれただけでは変化にならない。
- AGENT_GUIDE は「全 Link の確認基準を一括で現在に置き換えない。変わった Link ごとに対応を見直し、成立する場合だけ捕捉し直す」とエージェントに禁じている。split / merge を自動同一視しない grasp の `line_identity` policy と同じ保守方針。

grasp で効く場所: **grasp wiki 自身の current facts**。[[grasp-v1-implemented]] の記述は、コードが変わると黙って古くなる（version ledger checker はバージョン番号の整合しか見ない）。wiki の行 → その事実を説明する関数・CLI 定義への Capture 付きリンクを張れば、「この記述が前提にしている関数が変わった」を検出できる。最安の実験は、grasp repo で Monika をそのまま使うこと（`monika init` の `code` 拡張が Python の symbol を Tree-sitter で選べる）。grasp に同じ機構を入れるかは、その dogfood の後で決めればよい。

### 2. 型付き関係には法則と検査器を付ける —— typed / directional link

[[grasp-backlog]]「typed / directional link（デライトの引き入れ＝前景後景型）」で contains / part_of を入れる場合の型として:

- Monika の EXTENSIONS.md は、同一性を反射・対称・推移の同値関係、包含を反射・推移かつ「相互包含 ⇔ 同一」（半順序）と定め、`compare` は `equal`／`contains`／`within`／`incomparable` を返す。比較不能は失敗（`error`）と区別する。
- `monika extension test --cases FILE` が、決定性・反射性・対称性・反対称性・推移性を検査する。
- grasp 側の読み替え: 前景／後景の包含リンクを入れるなら、著者宣言でも AI 推定でも、**法則で検査する lint**（反対称 ⇒ 循環禁止、推移 ⇒ 祖先の導出が整合）を同時に持つ。`incomparable` と失敗の区別は Negative-result contract と同じ軸。

### 3. 辺の注釈は本文と別の場所に、schema を固定しない —— non-semantic edge annotation

[[grasp-backlog]]「link-shaped but non-semantic edge annotation」の置き場として:

- Monika の `annotation` は任意 JSON で、Sidecar に Link ごとに置く（本文は変えない）。Core が注釈を使うのは `check --duplicates`（注釈が同じ Link どうしで両端が `equal` なら重複）だけ。絞り込みは利用側が jq でやる（`select(.annotation.relation == "supports")`）。
- grasp の読み替え: raw edge は不変、注釈は edge をキーにした別テーブル、`annotator` / `reason` / `confidence` は注釈の field として持ち、Core が意味を解釈する field は最小にする。「reversible / provenance 付き」の要件と合う。

### 4. 鮮度方針を Resource ごとに宣言する —— Sync freshness

- Monika は `monika.json` の `resources` で Resource ごとに `observe`（操作ごとに観測）か `refreshed`（`refresh` で最後に採用した Observation を使う、未保存ならエラー）を宣言する。同じ操作中は同じ Resource の Observation を共有し、全コマンドに同じ方針が効く。結果には使った `observations` が付く。
- grasp の [[grasp-backlog]] Sync freshness の未決「read 以外への source 変更反映」に対し、`read --refresh` / `GRASP_READ_REFRESH` / idle-hydrate のように操作ごとのフラグを増やす代わりに、**source（project）ごとの鮮度方針を一度宣言する**形がありうる（例: local Markdown mirror は observe、hosted Cosense は refreshed）。

### 対照: verb を渡すか、組み立てさせるか

Monika は逆引き（「この範囲を指す Link を全て」）を専用 verb にせず、`monika links | jq '{link:., boundary:{name:"all"}}' | monika compare --left /link/target --right /boundary | jq 'select(.relation=="within" or .relation=="equal") | .input.link' | monika check` と組む（examples/demo.py）。grasp は stdin を受けず、`gather` / `mentions` / `co-links` / `path` など bounded な verb を AI に渡す方向（[[ai-consumer-cost-and-trust]]）。P4（小 context・低能力 consumer）では grasp の選択が有利と見るが、Monika の形は「Core を小さく保ち、合成は AI に任せる」極として比較対象になる。

### 参考にしない所

- 拡張プロセスの仕組み・同梱拡張（形式ごとのパーサ）: grasp の対象は Scrapbox / Markdown のグラフで、形式の多様性は要件にない。
- 配布（Homebrew・ライセンス同梱）: [[language-and-distribution]] の範囲で、現時点の判断材料にならない。

## Open Questions

- grasp repo で Monika を dogfood して、wiki の current facts の陳腐化をどれだけ拾えるか（検出したい変化が「関数の中身」なのか「CLI の出力契約」なのかで、セレクタの粒度が変わる）。
- grasp のページ・行を Monika の Resource として扱う拡張（resource = grasp store の page、query = `line_id`）を書けば、grasp の行とコードの範囲を相互に結べる。grasp 側に入れるのでなく、Monika 側の拡張として外に置けるか。
