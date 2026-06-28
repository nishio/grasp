---
type: decision
summary: grasp の audience は2層。driver = persona1（JP Cosense ヘビーユーザ＝nishio 自身の dogfooding）／upside-risk target = persona2（世界の LLM Wiki・Markdown 束ユーザ）。両者は substrate を共有するが value prop と on-ramp が別。persona2 は設計の再センタリングでなく addition（Markdown adapter＋英語 docs＋一般化 pitch）で狙う。GTM = HN/Reddit、lede は「LLM に Markdown 束でなく local graph store」、Scrapbox は lineage に後置
sources:
  - nishio 指示 2026-06-23「日本語話者で Cosense ヘビーユーザが僕の側面の一つ。一方で LLM Wiki ユーザで Markdown の束よりこっちが有用じゃんとなる世界のユーザは upside risk として狙いたい。HN/Reddit に投稿していくのもあり」
  - nishio 訂正 2026-06-23「Scrapbox はリネーム時に他ページからのリンクを書き換えたり redirect したりして対処している」（→ name=identity 欠陥の精密化）
---

# Decision: audience は2層、driver は persona1・persona2 は addition で狙う

決定: grasp の audience を **2層**として明示し、**設計の driver を persona1 に固定、persona2 は upside-risk な distribution target** とする。persona2 は「設計を削る／再センタリングする」のではなく **addition** で served される（Markdown import adapter＋英語 docs＋一般化した value prop を**足す**）。anchor persona（nishio の dogfooding）がいるから設計が正直で出荷可能なまま保てる。

## 2つの persona

- **persona1 = driver**: 日本語話者で Cosense ヘビーユーザ（＝nishio 自身の一側面）。felt friction を既に持つ（逆リンク維持の手回し、[[persistence-custom-format]] の動機）。dogfooding で設計を駆動する。
- **persona2 = upside-risk target**: 世界の LLM Wiki / Markdown 束ユーザ（日本語に限らない）。「Markdown の束よりこっちの方が LLM に効くじゃん」となりうる層。狙いたいが、ここに引っ張られて設計を曲げない。

## 構造的事実: substrate は共有、value prop と on-ramp が別

| | persona1（JP Cosense） | persona2（世界の Markdown 束） |
|---|---|---|
| felt friction | 逆リンク維持の手回し | そもそも逆リンクを**エミュレートすらしない**。flat な .md に forward link だけ |
| hook | 「Co- 以前の Scrapbox を CLI で AI が体験」（[[why-not-scrapbox-clone]]） | 「.md の束より、自動逆リンク＋近傍同梱の graph store の方が LLM に効く」 |
| 既存資産 = seed | Cosense JSON export がある（[[incremental-sync]]） | **Cosense は無い。あるのは Markdown フォルダ** |
| Scrapbox 文脈 | 共有財産 | **ノイズ**（Scrapbox を知らない） |

## 設計含意1: Markdown import adapter は persona2 の on-ramp そのもの

旧 `SPEC.md` の入力節は「初手＝Cosense JSON export、Markdown adapter は後で足せる」という順序で、これは persona1 の都合。persona2 には Cosense export が存在しないので、**Markdown フォルダ → grasp の取り込みが唯一の入口**。upside-risk を本気で狙うなら、この adapter と「.md フォルダより本当に良い」の**実演可能性**の優先度が上がる（"後で足せる" nice-to-have ではない）。HN/Reddit 読者が最初に殴ってくる問いが文字通り "why not just a folder of markdown / obsidian"。

実証: persona2 視点の fresh onboarding テスト（[[persona2-user-test-2026-06-23]]）で active release は fail。Markdown フォルダの import 経路が無く（directory を渡すと traceback）、英語 README も friendly error も無い。∴ Markdown import adapter は persona2 にとって "re-rank 候補" でなく **release gate**。persona1 dogfooding の MVP としては問題ない。

## 設計含意2: identity-without-name は両 persona に別の言葉で刺さる

rename の失敗モードは3者で**別物**。identity-without-name（id link、表示名を decouple）は両方を同時に消す。

| | rename したとき | 失敗モード |
|---|---|---|
| **Markdown フォルダ** | 他ページの filename 参照は自動追従しない | **リンクが切れる**（手で書き換えるしかない） |
| **Scrapbox/Cosense** | 参照側 `[旧名]` を自動で**書き換え** or **redirect** → リンクは生存 | 書き換え＝参照文の**文意が保存されない**／ redirect＝旧名 **stub が累積** |
| **grasp** | リンクは id を指す。表示名は decouple | どちらも起きない。リンクも切れず参照文 surface text も author のまま |

∴ pitch が persona ごとに別の言葉になる（これはむしろ良い）:
- **vs Markdown ユーザ（persona2）**: 「rename してもリンクが切れない」（Markdown には自動修復が無い）。
- **vs Scrapbox ユーザ（persona1）**: 「rename しても参照文が汚れない・redirect stub が溜まらない」（Scrapbox の自動修復が払うコストを払わない）。

> 注: Scrapbox の name=identity 欠陥は「リンクが切れること」ではない（Scrapbox は伝播 or redirect でリンクを生存させる）。欠陥は**そのリンク生存解が払うコスト**（伝播＝文意破壊、redirect＝名前累積）。詳細と精密化は [[why-not-scrapbox-clone]]。

## GTM: HN/Reddit は persona2 の獲得チャネル

- **lede は「LLM に Markdown 束でなく local graph knowledge store を与えた話」**。Scrapbox は intellectual lineage として後置（"before Co-" の洞察は美しいが inside-baseball で、英語圏読者には文脈が無い）。
- identity-without-name の pitch も「Scrapbox を直す」でなく「**filename=identity（rename でリンクが切れる）を直す**」に一般化すると persona2 に通る。

## 罠: design dilution

persona2 向けに振りすぎると「Obsidian-but-for-LLMs / CLI 付き graph DB」に見え、[[why-not-scrapbox-clone]] が明示的に引いた一線（**read＝近傍同梱が「グラフ DB を CLI で叩く」との差**, v1 実装は [[grasp-v1-implemented]]）が溶ける。差別化は「逆リンクがある」ではなく「**read が近傍を一体で返す＝LLM retrieval に最適化された体験**」。messaging はここを前面に出す。

## 帰結

- 設計判断は persona1 の dogfooding を基準に下す（persona2 を理由に削らない）。
- Markdown import adapter は post-v1 の中で persona2 を狙うなら優先度が上がる（[[grasp-backlog]]）。
- リリース文（README / HN / Reddit）は persona2 framing を lede に、Scrapbox を lineage に。delivery 面（[[delivery-cli-plus-skill]]）・配布チャネル（[[language-and-distribution]] の PyPI/npm）はこの audience 判断と直交。

## Open Questions

- persona2 を「今 actively 狙う」か「設計を曲げない範囲で受け皿だけ用意」か。後者がデフォルト（dilution 回避）だが、Markdown adapter をどの milestone で出すかは未定。
- Markdown フォルダの import で何を seed にするか（wikilink 記法・frontmatter id/aliases・既存 llm-wiki 森 40+ の concepts/analyses 階層）。フラット原則との緊張は [[why-not-scrapbox-clone]] Open Q と重なる。
- 「.md 束より良い」を**実演**する最小デモの形（同一ノートを Markdown フォルダと grasp で読ませて retrieval 差を見せる等）。

## Updates

### 2026-06-23: Markdown / Obsidian folder 対応は indexed mirror として切る

[[markdown-obsidian-indexed-mirror]] を追加。persona2 の on-ramp は「Skill が grep を速くする」ではなく、既存 Markdown / Obsidian folder を `grasp` の read-only indexed mirror にし、Skill はそれを使わせる薄い層にする。pitch は "faster grep" ではなく **indexed graph reader for Markdown / Obsidian notes, optimized for LLM agents**。価値は速度より、`read` が本文 + 逆リンク行 + related + unresolved targets を一体で返すこと。

### 2026-06-24: dogfooding は outcome story として評価する

[[use-case-experiment-as-outcome-story]] を追加。persona1 dogfooding は設計 driver だが、単に gotcha や未実装を見つけるだけでは弱い。ユースケース実験は「ユーザがこう依頼したら、こういう有用な結果が得られる」という outcome story として記録し、結果が読む・判断する・次に使う単位にまとまっていて「いい感じ」かを評価対象にする。

### 2026-06-24: 初の第三者試用 — インサイダーは Scrapbox 枠に入れる / モデル水準を下げる / flywheel は persona1 止まり

[[takker-opencode-villagepump-test-2026-06-24]]（nishio 以外の初実走, OpenCode + Deepseek v4 flash, villagepump 1.45M 行）から、この decision に効く3点:

- **persona1 は一般化する第一証拠、だが persona2 framing は依然未検証。** takker は JP・Cosense native・cosense-cli インサイダーで教科書的 persona1。彼が反射的に grasp を「offline 版 cosense-cli」と呼んだ＝放っておくと**インサイダーは Scrapbox 系譜の枠に入れる**。本 decision の GTM は逆に Scrapbox を lineage に後置し Markdown 束 framing を lede にする方針なので整合はするが、**upside-risk の persona2（Markdown 束・非 Scrapbox・非日本語）framing は実在の persona2 にまだ一度も当たっていない**。下 Open Q3 の「.md 束より良い」実演は依然 nishio の想定に留まる。
- **grasp はモデル水準を下げる（persona2 GTM の追い風）。** 安いモデルで完走したのは、構造化出力を CLI が作り agent は薄い recipe を回すだけだから（[[takker-opencode-villagepump-test-2026-06-24]] / [[delivery-cli-plus-skill]]）。「手持ちの・安い coding agent でも動く」は persona2 獲得の messaging になり、Claude 前提でない portability を裏付ける。
- **公開 dogfooding flywheel は高利回りだが persona1 止まり。** 公開 Scrapbox に書く→エコシステム隣接者が自分の agent/corpus で試す→実バグを踏む→PR まで来る（PR #2 merged）、という自己 dogfooding では出せない検証がタダで来た。HN/Reddit GTM はこれを意図的に回す価値があるが、現状この経路が届くのは persona1 型の人。persona2 を当てるには別チャネル（Markdown/Obsidian コミュニティ）が要る。

### 2026-06-26: grasp の価値は既存リンク密度に比例する → persona2 は逆風（動機と表裏）

本 decision は persona2 の felt friction を「逆リンクをエミュレートすらしない、flat な .md に forward link だけ」と置き、それを grasp が埋める gap として framing している。2026-06-26 対話で同じ事実の**裏面**が surface した: grasp の graph materialization 価値（read=近傍同梱・backlinks・related・unresolved）は **元 corpus のリンク密度に比例**し、edge が多いほど rich に返る。

∴ 非対称: 価値は persona1（高密度＝nishio の 25k Cosense store、[[kj-link-hub-audit-2026-06-24]] の KJ法 hub 144→490）で最大、persona2（低密度＝まばらな .md）で最小。persona2 の定義的特徴（forward link のみ・逆リンク不在）は grasp が埋める**動機**であると同時に、grasp が materialize できる graph が薄いという**構造的逆風**でもある。「逆リンクが無いから grasp が要る」と「逆リンクが無いから grasp が返せるものが少ない」は同じ事実の表裏。§設計含意1 の「persona2 は逆リンクをエミュレートすらしない」を gap でなく headwind 側から読み直したもの。

含意（persona2 に効く正直な pitch は density 非依存側に寄せる）:
- (1) **density 非依存の優位を lede に**: [[read-vs-grep-benchmark-2026-06-24]] の「14M token は window に入らない / grasp search は bounded・ranked・structured」は元 link 密度に依存しない。persona2 への lede は graph 逆リンクでなくこちら（§罠 design dilution とも整合: 差別化は「逆リンクがある」でなく「read が近傍を一体で返す」）。
- (2) **潜在 edge を提案する半-authoring**: 低密度 corpus で価値を出すには「既存リンクを読む」を超え「リンクされていない mention を surface → come-from 昇格提案」（[[come-from-declared-gather]] §6 (c) AI default 裸）まで踏み込む要。これは retrieval でなく authoring 寄りで、Markdown adapter（release gate）の次の persona2 gate になりうる。

Open Q3（「.md 束より良い」最小デモ）への含意: 低密度 corpus では graph 差が出にくいので、高密度デモ corpus を選ぶ（自己選択 bias のリスク）か、低密度でも効く bounded-retrieval 差（grep 比）を見せるか、を分けて設計する。

### 2026-06-28: 初期 persona 設計の再検討 — 1スペクトラムは独立3軸を畳んでいた

2026-06-25〜26 に判明した事実（Markdown import 実装済み / 密度の逆風 / takker test）と本 decision を突き合わせた再検討。初期（2026-06-23）の persona1 ↔ persona2 は単一スペクトラムだが、実際には独立な3軸を一本に押し込んでいた。

3軸:

- **A. on-ramp（substrate）**: Cosense JSON export ↔ Markdown folder。**両端とも解決済み**（`import --markdown` / `import-forest`、schema v7 で duplicate title / alias collision も import を止めない。[[wiki-forest-markdown-import-dogfood-2026-06-25]]）。初期 doc が persona2 の release gate とした「Markdown folder import が無い」障壁は消えた。
- **B. リンク密度**: 高 ↔ 低。grasp の graph materialization 価値（read=近傍同梱・backlinks・related・unresolved）を直接駆動する（§2026-06-26 の密度逆風）。
- **C. corpus 所有者 / GTM チャネル**: nishio dogfooding（日本語・Scrapbox lineage）↔ 冷たい HN/Reddit の他人。persona2 でまだ未検証なのは実は C だけ（[[takker-opencode-villagepump-test-2026-06-24]] の takker は日本語・Cosense インサイダー＝persona1 型で、A も B も persona1 寄り）。

初期 doc は A（on-ramp 障壁）を最大の不確実性として扱ったが、A は解決済み。残る本当の分岐は B（密度）と C（GTM チャネル）。

**二項対立が名前を付け忘れたセル = (Markdown substrate × 高密度 × nishio 所有) = llm-wiki 森（40+ wiki）。** 初期 persona2 の「Markdown だが低密度」と違い、これは Markdown かつ高密度（`[[wikilink]]`・frontmatter id/aliases・concepts 階層）。性質:

- 実在し既に dogfood 済み（persona2 のような仮説でない。import-forest で 42 projects / 3338 pages / 23k edges、[[wiki-forest-markdown-import-dogfood-2026-06-25]]）。
- Markdown substrate を end-to-end で実証する → persona2 の on-ramp 主張を de-risk する。
- 高密度なので §2026-06-26 の密度逆風を回避する（graph 差が実際に出る corpus）。
- nishio 所有なので anchor-persona の「設計が正直・出荷可能に保たれる」性質（§Decision）を保つ。

∴ これは persona1 と persona2 の **bridge persona**。Open Q3（「.md 束より良い」最小デモ）の高密度デモ corpus はこれで、自己選択 bias の懸念（高密度 corpus を恣意的に選ぶこと）も「nishio の実 corpus」という形で正当化される。

**persona2 の分割**（初期は2つの別物を1つの persona に畳んでいたのが歪みの源）:

- **persona2a = 高密度 Markdown wiki ユーザ**（nishio 森＋dense `[[link]]` を持つ Obsidian パワーユーザ）。近接・served 済み・密度価値が効く。事実上の次の driver 候補。
- **persona2b = まばらな .md フォルダ / 冷たい HN/Reddit ユーザ**。遠い・密度逆風が最大・§罠 design dilution の本体。pitch は密度依存の「逆リンクがある」でなく密度非依存の bounded retrieval（[[read-vs-grep-benchmark-2026-06-24]]）に寄せる。

**consumer 軸の明示**: persona1 / persona2 / persona2a / persona2b はすべて *corpus を所有する人間* のセグメントで、設計上の主ユーザ = Skill 越しに読む AI（[[delivery-cli-plus-skill]]）を指していない。cross-model portability（[[takker-opencode-villagepump-test-2026-06-24]] の Deepseek 完走、[[ai-consumer-feedback-2026-06-23]]）は consumer 側の直交属性で、どの人間が corpus を所有するかに依らない。persona は「corpus 所有者」と「AI consumer」のタグを分けて付けるとよい。

含意:

- 次に actively 狙う persona2 は persona2b（冷たい他人）でなく **persona2a（高密度 Markdown）**。森 dogfood がそのまま検証経路になる（別チャネル獲得を待たずに検証が進む）。
- persona2b は依然 design dilution リスクの本体。lede は density 非依存側（bounded retrieval）に固定（§罠 design dilution・§2026-06-26 と整合）。
