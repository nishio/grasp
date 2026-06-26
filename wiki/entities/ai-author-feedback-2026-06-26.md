---
type: entity
summary: 2026-06-26、grasp の write 面（alpha write path）を AI（Claude Opus 4.8）が初めて実走した記録。前 session で「新規 page + frontmatter + index 表編集は alpha write が表現できない」と判断し direct Markdown に fallback したが、sandbox（throwaway store/journal）で write-page/append-section/append-log を実走するとその理由はほぼ誤りだった: write-page --create は frontmatter を verbatim 保持し id/title/aliases を注入（identity-without-name を file に materialize）、body の [[link]] を edge 化、export-markdown --check は3 write op を通して ok のまま。真の friction は capability でなく (1) 構造化 arg の mental model（append-section=heading+line / append-log=op+summary、markdown blob を渡せない）(2) arg 必須の surprise（write-status は --output 必須）(3) title/H1/filename が別物（identity-without-name）(4) index 行に write op が無く write-page と direct 編集が混在（cutover 未完）(5) 共有 journal が lock-free で並行 writer 下では serial-execution 規約を安全に満たせない。meta: AI が write path を避ける決定因は correctness でなく confidence 獲得コスト + 並行安全性。
sources:
  - sandbox 実走 2026-06-26（throwaway store /tmp/grasp-write-trial、write-page --create / append-section / append-log / export-markdown --check / read を実走）
  - 前 session の file back 判断（value-is-problem-solving-not-novelty を direct Markdown で patch した経緯）
---

# entity: AI author (write-path) feedback (2026-06-26)

[[ai-consumer-cost-and-trust]] / [[ai-consumer-feedback-2026-06-23]] が read（消費）面の AI 体験なら、本ページはその **write（著作）面の対**。grasp の差別化核は authoring（[[development-arc-retrieval-ahead-of-authoring]]）なので、AI が write path をどう体験するかは存在理由の半分の実地評価。

## 経緯: 前 session の fallback とその誤り

前 session で [[value-is-problem-solving-not-novelty]] を file back したとき、`wiki.grasp/events.jsonl` がある（=grasp write-first 規約）のに **direct Markdown patch に fallback** し、理由を「新規 concept page + frontmatter + index 表の行編集は alpha write 層が clean に表現できない」と書いた。

本 session で sandbox（throwaway store + throwaway journal、共有 journal は触らない）で実走した結果、**この理由はほぼ誤りだった**:

- `write-page --create --path X.md --from-file body.md --output wiki` は**新規 page を frontmatter ごと**作れた。投入 frontmatter（type/summary/sources）は **verbatim 保持**され、さらに grasp が `id` / `title` / `aliases` を frontmatter に**注入**した（identity-without-name が file に materialize、`名前ではなくIDで識別する設計` の可視化）。
- body 中の `[[positioning-two-personas]]` は **edge 1 本に parse**された（write-page 戻り値 edges:1）。これは direct Markdown では**得られない**（store に再 import するまで backlink が立たない）— fallback が forfeit した具体的 value。
- `append-section` / `append-log` も実行でき、3 write op を通して `export-markdown --check` は **ok:true / written:0**（projection は store と整合のまま）。

∴「alpha が frontmatter を表現できない」は overcaution。capability は在った。

## 実走で判明した本当の friction（capability でなく ergonomics）

1. **構造化 arg ⇄ markdown blob の mismatch。** append-section は `--heading <text> --line <...>`（`--from-file` 無し）、append-log は `--op --summary --timestamp --line`（`## [ts] op | summary` 見出しを**構成**する。raw markdown 見出しを渡せない）。「markdown チャンクがある、書け」と思う AI は **2 回 mis-invoke**してから適応した。error は argparse の required-arg で明快 → 復帰は各 1 round-trip だが friction。
   - **gotcha（並行 file-back が共有 journal の実走で発見、log 23:07）**: `append-section --heading 'Updates'` は既存の同名 `## Updates` に **merge せず EOF に新規 heading を作る**（二重 `## Updates`）。位置指定も merge も無いので、既存節への追記は direct patch → 直列 `write-page --from-file` で journal 再同期 → `export-markdown --check` / lint clean、に fallback するしかなかった。本 wiki の `## Updates` 追記規約と append-section の append-only 意味論が衝突する点で、friction 4（content は write-page で綺麗だが節編集は projection 手編集に逃げる）の section 版。
2. **arg 必須の surprise が round-trip を食う。** `write-status` は `--strict` でなく `--output` 必須。CLAUDE.md の例から類推した初手が外れる。`grasp <cmd> --help` が SSoT（global help も「最初に読め」と言う）。**初回 write 前に各 command の --help を読む**のが事実上の前提。
3. **title / H1 / filename は三者別物。** positional `title`=identity handle、`--path`=projection filename、body の `# H1`=本文。trial では title='トライアル書き込み体験' / alias='trial-write-experience'（path 由来）/ H1='# トライアル' が**共存**。identity-without-name を理解していないと混乱する。
4. **index 行に write op が無い。** `write-page`（content）と `append-log`（log）はあるが **`write-index` は無い**。wiki 規約は index.md を手編集するが、[[markdown-obsidian-indexed-mirror]] / [[native-authority-markdown-projection]] では index/nav/log は **projection（edge でない）**。∴ AI は write-page と index.md の direct 編集を**混在**させる。これが残る摩擦で、**cutover 未完**を指す。
5. **共有 journal が lock-free。** `wiki.grasp/events.jsonl` は本 session 中も並行 session で dirty だった。serial-execution は**規約のみ（enforcement 無し）**。stateless な AI session は dirty journal を見て「writer が active か」を安く判定できず、interleave を冒すか route 回避するしかない。**今回 sandbox に逃げた事実そのものが証拠**: 不確実下の AI の安全な既定は共有 write path を**使わない**こと。

## meta: write path 採用の bottleneck は correctness でなく confidence コスト

前 session の回避の決定因は capability gap でなく **(a) 確信を得るコスト**（4 command の --help を読む / 構造化 arg model / identity-without-name / export --check を回す）が、**目視で検証できる direct Markdown 編集のコストを上回った**こと、**(b) 共有 journal の並行安全性**だった。grasp の差別化が authoring である以上、これは最重要の採用 datum: **AI は安く検証できる substrate を既定にする。** write path の正しさは bottleneck でない。下げるべきは confidence 獲得コストと並行安全性。

候補（観察であって要求でない）:

- page + index + log を **1 op で atomic に** file-back する高位 command（手数と mis-invoke を畳む）
- `--dry-run` / preview（AI が安く確信を買える面）
- index を**純 generated projection** にして手編集をなくす（friction 4 を消す＝[[native-authority-markdown-projection]] の cutover）
- 共有 journal の **lock / 「writer active?」check**（friction 5、serial-execution を AI が安全に満たせる形に）

## このページ自体の file back 方式（再帰的 datum）

本ページも write-first 規約下だが、**再び direct Markdown を採った**。ただし理由は前回と違い**正しい**: 実走中も並行 session が共有 log/journal を触っており（log.md dirty）、lock-free な serial-execution 規約を安全に満たせないため（friction 5）。capability ではなく**並行安全性**が blocker。前回の「frontmatter capability」理由は本ページで撤回する。

## Open Questions

- friction 1（構造化 arg）は API として正しい設計（log schema 強制・identity 注入）であり、必要なのは「markdown 意図 → 構造化 arg」を畳む薄い高位層か、それとも AI 側が学べばよいだけか。
- confidence 獲得コストを下げる最小手は dry-run / preview か、atomic file-back command か。実測（次の write-path 実走で round-trip 数を数える）で決める。

## 関連

- [[ai-consumer-cost-and-trust]] — read 面の cost-and-trust。本ページは write 面の対（confidence コスト + 並行安全性）
- [[ai-consumer-feedback-2026-06-23]] — read 面の AI review。本ページは write 面の同型 event
- [[development-arc-retrieval-ahead-of-authoring]] — 「authoring は未実装の差別化核」。本ページは**実装済みで動くが採用が confidence コストで gate される**と update
- [[write-layer-alpha-and-replay-test]] — alpha write 層の位置づけ（read=stable / write=alpha 別 SLA）
- [[native-authority-markdown-projection]] / [[markdown-obsidian-indexed-mirror]] — index/log を projection 化する cutover（friction 4・5 の解）
- [[value-is-problem-solving-not-novelty]] — 前 session でこの fallback が起きた file back
