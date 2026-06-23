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

[[SPEC]] の入力節は「初手＝Cosense JSON export、Markdown adapter は後で足せる」という順序で、これは persona1 の都合。persona2 には Cosense export が存在しないので、**Markdown フォルダ → grasp の取り込みが唯一の入口**。upside-risk を本気で狙うなら、この adapter と「.md フォルダより本当に良い」の**実演可能性**の優先度が上がる（"後で足せる" nice-to-have ではない）。HN/Reddit 読者が最初に殴ってくる問いが文字通り "why not just a folder of markdown / obsidian"。

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

persona2 向けに振りすぎると「Obsidian-but-for-LLMs / CLI 付き graph DB」に見え、[[why-not-scrapbox-clone]] が明示的に引いた一線（**read＝近傍同梱が「グラフ DB を CLI で叩く」との差**, [[SPEC]] 原理1）が溶ける。差別化は「逆リンクがある」ではなく「**read が近傍を一体で返す＝LLM retrieval に最適化された体験**」。messaging はここを前面に出す。

## 帰結

- 設計判断は persona1 の dogfooding を基準に下す（persona2 を理由に削らない）。
- Markdown import adapter は post-MVP の中で persona2 を狙うなら優先度が上がる（[[SPEC]] 入力節の "後で" を re-rank する候補）。
- リリース文（README / HN / Reddit）は persona2 framing を lede に、Scrapbox を lineage に。delivery 面（[[delivery-cli-plus-skill]]）・配布チャネル（[[language-and-distribution]] の PyPI/npm）はこの audience 判断と直交。

## Open Questions

- persona2 を「今 actively 狙う」か「設計を曲げない範囲で受け皿だけ用意」か。後者がデフォルト（dilution 回避）だが、Markdown adapter をどの milestone で出すかは未定。
- Markdown フォルダの import で何を seed にするか（wikilink 記法・frontmatter id/aliases・既存 llm-wiki 森 40+ の concepts/analyses 階層）。フラット原則との緊張は [[why-not-scrapbox-clone]] Open Q と重なる。
- 「.md 束より良い」を**実演**する最小デモの形（同一ノートを Markdown フォルダと grasp で読ませて retrieval 差を見せる等）。
