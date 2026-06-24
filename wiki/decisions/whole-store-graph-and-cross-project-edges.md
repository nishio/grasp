---
type: decision
summary: grasp store は外部 source から再生成可能な projection なので schema は自由に壊してよい（v6 へ）。cross-project link `[/P/T]` を import 時に first-class edge として materialize し、intra link と同じ backlinks/related/path/unresolved 機構に乗せる。retrieval は whole-store default（`--project` は絞り込み、結果は project ラベル付き、materialized page node は namespace 分離のまま）。node 状態は page 単位の materialized / referenced-only で、project は単なる namespace、acquire = referenced-only node の materialize。**referenced-only（赤）node は normalize title で project 横断統合**（Cosense にない概念ハブ、nishio tentative）。原則は discover-broad-filter-post-hoc（relevance で pre-filter せず、ラベル付きで全部 surface、絞りは post-hoc、性能は bound で対処し hide しない）。multi-project-store の2 clause を supersede。
sources:
  - nishio 設計対話 2026-06-24（cross-project-refs を互換重視で実装する方針への反論「互換性を捨ててどうあるのが理想か」）
  - nishio 判断 2026-06-24「人間が気付けないものを AI が気づくのは良い。不要なものは見つけた後に filter」「明示的に project を限定しない限り default で全体から検索」「project でなく page 単位で『参照されているがまだ実体取得していない』がある」
  - grasp/sqlite_store.py（現 `cross_project_refs` = parse-on-read / `_require_project` = 複数 project で error / `recover_store_from_import_cache`）
  - grasp/cosense.py（`CrossProjectLink` raw/project/title/target_class, `classify_cross_project_target`）
  - [[cross-project-reference-acquire-2026-06-24]]（dogfood: 183 project / 4,141 refs / reciprocal refs）
---

# Decision: whole-store グラフと cross-project first-class edge（v6）

決定の塊。cross-project-refs を「v5 互換・schema bump なし・保存済み本文から parse-on-read」で足す方針を破棄し、互換性を捨てた理想形を v6 として確定した。Codex はこれを実装し、実装で判明した制約を [[grasp-v1-implemented]] / 本ページへ file back する。**本ページは design intent であり current facts ではない**（実装済み事実は entities/ 側）。

## 決定（要点）

1. **store = 再生成可能な projection。schema は自由に壊す。** SSoT は SQLite の行ではなく外部 source（Cosense export / Markdown folder / acquire 結果、すべて `<store>.imports/` に cache 済み）。`ensure_store_schema` は `SCHEMA_VERSION` 不一致で store を作り直し、`recover_store_from_import_cache` が cache から全 project 再 import する機構が既にある。∴「schema bump を避ける」ことに価値はない。理想形を決めて `SCHEMA_VERSION = "6"` に上げ、再 import する。

2. **原則: discover-broad, filter post-hoc。** CLI は relevance で **pre-filter しない**。target_project / link_kind / scope ラベル付きで全部 surface し、絞り込み（semantic-only, same-project-only 等）は **見えた集合への post-hoc flag** にする。出力量は rank + omitted-count で bound する（discover ≠ 無制限に吐く）。性能問題は bound（limit / depth / ranking / index）で対処し、**hide では対処しない**。grasp が既に持つ「raw + ranking を返し AI が畳む」「`returned_counts` / `omitted_counts`」方針（[[grasp-backlog]] の `--cluster` 却下・`gather` counts）を cross-project / whole-store に拡張しただけで、新しい哲学ではない。

3. **cross-project link を first-class edge として materialize。** `[/P/T]` を import 時に解決し edge にする。`CrossProjectLink`（`raw / project / title / target_class`）をそのまま流せる。intra link と同じ `backlinks` / `related` / `path` / `unresolved` 機構に乗る。現状の parse-on-read `cross_project_refs`（`LIKE '%[/%'` 全スキャン + 毎回 re-parse / re-classify、edge にならず backlinks/related/path に入れず赤リンク node にもなれない）を置換する。

4. **retrieval は whole-store default。** 複数 project があっても `--project` 無しで store 全体から検索する。`--project` / `$GRASP_PROJECT` は「省略可能な絞り込み」。**結果は1行ごとに project ラベル付き**。materialized page node は merge しない（namespace 分離＝authorship 保持は維持。referenced-only 赤 node の cross-project 統合は別軸＝下記 7）。安全機構が「scope を1つに絞る」から「全部見せてラベルを付ける」に置き換わる。`stats` が既に「project 未指定なら aggregate」でやっていることを全 retrieval verb に広げる。mutating/source 系（`import` / `sync` / `acquire`）は1つの source への操作なので project-targeted のまま。

5. **node 状態 = page 単位の materialized / referenced-only。project は namespace。** 「参照されているが本文を取得していない」は project 単位の特別カテゴリ（旧称 ghost project = 破棄）ではなく、grasp が既に持つ赤リンク / unresolved target の page 単位状態そのもの。`[/takker/ScrapBubble]` は「takker namespace にある referenced-only page」で、nishio 内の `[存在しないページ]` と同じ node 種別、違うのは所属 namespace だけ。takker project は acquire 有無に関わらず存在する namespace で、「acquire したか」は categorical でなく **coverage（その namespace の materialized page 数、0 でも namespace は存在）** という派生量。**acquire = referenced-only node を materialize する操作**に再定義できる（nishio 内 stub を埋めるのも takker を初取得するのも同じ lifecycle、fetch 失敗 = materialized になれなかった）。

6. **read の多義は disambiguation 契約。** whole-store default で同名 page が複数 namespace に存在しうる。`read <title>` は **error せず・黙って先頭を選ばず・全候補を project ラベル + summary 付きで返し、`--project` か page-id で絞らせる**。negative-result / disambiguation 契約（[[ai-consumer-cost-and-trust]] 軸2）の延長。

7. **referenced-only（赤）node は normalize title で project 横断統合する（nishio 2026-06-24、tentative・撤回あり）。** 別 project の同名 bare 赤リンク `[X]`（どの namespace でも materialized でない unresolved target）は、normalize title を **project 非依存 key** として **1つの cross-project 概念 node に束ねる**。これで「自分の全 project を通じて、誰も本文を書いていないが皆が指している X」が見える＝**project ごとに別 Scrapbox である Cosense が構造的に出せない価値**。materialized page node は (project, id) で namespaced のまま（point 4）で、統合するのは赤 node だけ。nishio は「自信は低いが、一旦この方針で行く方が Cosense にない価値を生む」と判断。同綴り別概念の誤接続リスクは受容（下記 Open Questions で provenance を残して後から判別可能にする）。これにより [[multi-project-store]] の tentative Update（villagepump 由来）と本決定は **この点で収束**した。

## 理由

- cross ref を二級市民にしているのは互換性のためだけだった。[[cross-project-reference-acquire-2026-06-24]] dogfood は `/nishio` が 183 project / 4,141 refs を外に張り、取得した外部 page が `/nishio` へ reciprocal ref を返すこと（共同知識圏の輪郭）を実測した。cross ref を edge にすれば、この reciprocal が **本物の backlink** になり、Scrapbox の自動双方向・2-hop・赤リンクが project を跨いで効く。これは grasp の存在理由（Scrapbox のグラフモデルを CLI で体験させる）そのもの。
- 赤リンク = acquire の bibliography に畳まれる。未取得 namespace への ref は「参照してるが未取得の知識圏を指す referenced-only node」。`unresolved`（whole-store）が「villagepump に未取得の参照 833 件」を link_count 順で出す = dogfood が one-off script でやった seed ranking。`acquire` がそれを materialize し、edge が一斉に resolve する。専用 verb `cross-project-refs` は不要になり、`unresolved` + `acquire` + `backlinks` の組み合わせになる。
- whole-store default は「人間が気付けないものを AI が気づく」を優先する nishio 判断の帰結。project を1つに絞らせる現挙動は、AI に「どの project か」を先に決めさせ、跨ぐ繋がりを発見不能にする。ラベル付き whole-store なら混ぜずに気づける。

## v6 schema 方向（design intent, 未実装）

```text
edges(
  id,
  source_project,        -- 旧 project（source page 側）
  source_page_id,
  line_id,
  target_project,        -- ★追加。intra は source_project と同値、[/P/T] は P
  target_title,
  target_norm,
  link_kind              -- ★追加 'internal' | 'cross-semantic' | 'cross-icon' | 'cross-root'
)

unresolved_targets(
  project,               -- target の namespace。materialized page を1枚も持たない namespace も値に取りうる
  target_norm, title, link_count, source_page_count, total_source_views, latest_source_updated, ...
)
```

- 解決は import 時: `[/P/T]` を source 行（project Q）から → target node (P, norm(T))。P が import 済み & page あれば materialized page node に解決（resolved cross edge）、無ければ P namespace の referenced-only node。
- `rebuild_unresolved_targets` の変更点は1つ: 存在チェックを source project でなく **target_project の pages** に対して行い、`(target_project, target_norm)` で集計する。
- `target_class`（semantic/icon/root）は import 時に `link_kind` として格納（dogfood の `.icon` 1,713 件ノイズを `WHERE` 一発で除外可能に、re-parse しない）。`raw` も保存し slash-in-title の再解決を可能にする。
- 「project の存在」は projects table の行ではなく「その namespace に node（materialized か referenced-only か問わず）がある」で含意。referenced-only namespace を実体行にするかは Open Question。
- **赤 node（referenced-only）は normalize title を project 非依存 key として1ノードに統合する（point 7）。** `unresolved_targets` は per-source provenance（どの project の何ページが赤リンクしたか）を保持しつつ、graph node は norm でまとめる。これにより「N project を跨いで参照される未-written 概念」を **cross-project spread として rank** できる（Cosense にない signal）。materialized page との解決チェック（norm(X) の materialized page がどこかの namespace にあるか）の扱いは Open Question。

## query 既定（design intent）

| verb | cross / whole-store default | 備考 |
|---|---|---|
| `search` / `mentions` / `co-links` / `gather` | whole-store ON | `WHERE project=?` を落とす。row に project ラベル + ranked + omitted-count |
| `backlinks` | cross ON | `WHERE target_project=? AND target_norm=?`。indexed・安い |
| `unresolved` | cross ON（scope ラベル付き） | foreign referenced-only node も default で並ぶ。bibliography が自然に浮く |
| `related` | cross ON（ranked + omitted） | hub 問題は既存で cross 固有でない |
| `path` | cross ON だが bounded | BFS は重い（dense graph で 4-5s）。隠さず max-depth/limit/ranking/`truncated` で bound。最大連結成分 96% なので無意味な経路が量産されうる → rank と link_kind ラベルで agent に判断を渡す |
| `read` | whole-store、多義は全候補返す | 上記 disambiguation 契約 |
| `import` / `sync` / `acquire` | project-targeted のまま | 1 source への操作。whole-store ではない |

`_require_project` の「複数 project で error」は削除。

## supersede するもの

[[multi-project-store]] の以下2点を覆す（node namespace 分離の核は維持）:

- 「project 間リンク / cross-project related は作らない。必要になったら explicit な cross-project query として別設計にする」→ **本決定がその別設計。cross link を first-class edge に materialize する**。
- 「retrieval は selected project 内だけ / 複数なら `--project` 必須」→ **retrieval default は whole-store、`--project` は絞り込み**。「文脈 merge で AI が誤読」懸念は merge せず labeling で解消する。

## 何を直さない / 注意

- **identity-without-name は別層。** cross edge も name ベース（`/proj/title`）で resolve するので、相手 project を後で import → rename すると edge が腐る。これは intra と共通の宿題で、stable line/page id 層（[[grasp-backlog]] の write/identity）が両方まとめて id ベースに昇格させるまで deferred。cross-project が identity を解くわけではない（親 llm-wiki `名前ではなくIDで識別する設計` の consumer 側本体は依然 page-id stable 化）。
- **cross-project ranking は専用機構を作らない。** views は project 相対で比較不能だが、relevance を CLI が握らない方針なので既存 per-row signal + project ラベルのままにする（重要度低と判断）。
- **partial corpus caveat。** acquire は部分取得なので foreign node/edge は coverage=partial を持たせ、その slice の backlinks/related/unresolved は「取得済み subset 内の事実」と明記し続ける。
- **link_kind の方向性（typed link / 前景後景）は別課題。** [[grasp-backlog]] の typed/directional link 節に属する将来軸で、今回は混ぜず defer。
- **実装は history の `x` bump。** store format / materialized index semantics が変わるため、[[history]] の x/y ledger では `x` を進める（再 import が要る変更）。

## Open Questions

- referenced-only namespace（materialized page 0 の project）の coverage rollup を `stats` / `projects` でどう surface するか。実体行は作らず query で出す方針だが表示形は未定。
- slash-in-title（`[/takker/takker99/ScrapBubble]`）の確定規則: 第1 segment=project / 残り=title とし、`raw` 保持で規則変更時に再解決可能にする、で暫定。実データで nested project-like path がどれだけあるか要確認。
- whole-store `related` / `path` の cross-project frontier をどこまで bound するか（dense graph 性能の継続 dogfood）。
- **同名 bare 赤リンクの cross-project 統合は採用（point 7、nishio 2026-06-24）。残る境界 Q:**
  - **同綴り別概念の誤接続**（別 project で `Apple`=会社/果物）。nishio は value 優先で受容。`link_kind` / source project provenance を残し、後から判別・分割可能にする。実データで誤接続頻度を dogfood する（tentative なので撤回しうる）。
  - **赤-materialized 境界**: 別 project に materialized page X があるとき、他 project の bare 赤 `[X]` をその materialized X に解決するか（cross-project name resolution）、それとも赤-赤統合のみか。tentative Update の原意は赤-赤のみ。materialized は namespaced のままで、discoverability は whole-store labeling で別途確保する、が暫定。
  - **explicit `[/P/T]` との関係**: P 指定の cross link は (P, norm T) の namespaced 解決のままで、bare 赤統合（project 非依存 key）とは別経路か。両者の node identity の整合を実装時に確定する。

## Updates

### 2026-06-25: ScrapBubble の whiteList 透過が prior art（cross-project は Co- 無しでも価値）

[[scrapbubble]]（takker99 の Scrapbox 閲覧 UserScript、本ページが slash-in-title の実例に使う `[/takker/ScrapBubble]` の出元）を ingest した対比。ScrapBubble の `whiteList` は複数 project を**透過的に**繋ぎ、本決定の whole-store cross-project と同じ価値（project を跨いで「あるキーワードについて書いたこと」を一望）を**人間ブラウザ GUI で先に実装**している。重要な分解: whiteList の魅力は2層あり、villagepump が「多分これが一番魅力的」と呼ぶのは **自分の public + private project の統合（非 Co-、単一所有者）** の方で、TamperMonkey 版の**他者 project 読み（Co-、多人数）**は別軸。grasp は Co- を削ぐ（[[why-not-scrapbox-clone]]）ので本決定の whole-store cross-project が継ぐのは前者＝1 AI が複数 store（namespace）を所有して横断する形。∴ ScrapBubble は「**cross-project graph は Co- が無くても（むしろ自分の public+private 統合こそが）価値**」を実例で示し、本決定を裏付ける。

実装の borrow 候補（[[scrapbubble]] Open Questions）: ① ScrapBubble の `links2hops` 先回り prefetch（ページ内全リンクの空判定を一括取得）は whole-store `unresolved` 再構築の bulk 化のヒント。② 「全 project で空なリンクは全 project を取得しないと赤判定できない」edge case は、本決定の target_project 存在チェックが whole-store 化で払う同じコスト。③ ScrapBubble が「実装したい」とする**リンク同一判定のカスタム化／表記ゆれ吸収**（`yyyy/MM/dd` ⇄ `yyyy-MM-dd`）は point 7 の赤 node normalize-title 統合と同問題で、normalize 規則を揃える価値がある。
