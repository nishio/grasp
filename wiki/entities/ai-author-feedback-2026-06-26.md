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

## Updates

### 2026-06-27 (live, 共有 journal 実走): sandbox が原理的に出せない並行下の failure mode

本ページ本文は **sandbox（throwaway store /tmp、共有 journal を触らない）**実走に基づく。一方、本ページが friction 1 gotcha / friction 5 で引く「並行 session が共有 log/journal を dirty にした」**その並行 session が私**で、私は **共有 `wiki.grasp/events.jsonl` と本番 `wiki/` に live で write**した（`come-from` / `positioning` の §Updates、log 23:07）。sandbox が隔離ゆえ構造的に出せない並行下 failure mode を一次体験として足す:

- **stale store × export 副作用 ＝ 蘇生 / clobber。** 私の `.grasp/file-back.sqlite` は import 時点（22:54）で固定され、その後 並行 session が `wiki/` を変えた。`append-log` の `export-markdown` 副作用が **stale store の page を `wiki/` に再 materialize** し、私が作っていない `value-is-problem-solving-not-novelty.md` が untracked で出現した。write op の export が安全なのは **store == wiki/ の時だけ**で、並行 writer 下では store が黙って stale 化する。sandbox（隔離 store）はこの面を出せない。CLAUDE.md「write-page は全 projection を export」警告の実害形。

- **write-status は divergence を検出するが「誰の変更か」を言わない。** `append-log` 後に write-status が `projection_ok:false / strict_ok:false / journal_log_stale:true` に転じたが、これは **私のミスでなく並行 writer が `wiki/` を触った**ため。AI は `strict_ok:false` を見ても「自分由来」か「他 writer 由来」かを **in-band で区別できない**。trust 信号が、最も要る並行下でちょうど劣化する（read 面「沈黙＝偽陰性」の write 版＝「赤信号の出所不明」）。

- **append-log の placement gotcha（2つ目の "成功だが意味的に誤り"）。** append-section の二重 heading（friction 1）に加え、`append-log` は **newest-first の log なのに entry を末尾寄り（~1040 行下）に置いた**。成功を返すが、top から最近を読む人/AI に埋もれる。手で正位置へ reorder したが、その Edit で隣の entry heading を一度落として復元した（手編集 reorder 自体が誤りを生む）。

- **回復は grasp でなく git 層で行うしかなかった。** grasp-write に並行 primitive が無いので AI の安全策は git に降りた: 自分の確定ファイルだけの **pathspec commit**（`git commit -m … -- <paths>`、他 session の staged を巻き込まない）／**`git checkout HEAD -- events.jsonl`** で自分の journal events を撤回／reorder の誤りを **amend**。それでも私の log 23:07 entry は 並行 session の commit が staged `log.md` ごと **取り込んで**しまった。→ friction 5 の解は「lock」だけでなく **変更の attribution（誰の hunk か）** が要る、と尖る。

- **meta 確認 ＋ 追補。** 本ページの結論「不確実下の AI の安全な既定＝共有 write path を使わない」は live で裏付いた: 私は使うと決めて入ったのに、共有 journal が私を direct-patch + git 手術へ押し戻した。追補: confidence コストは **upfront（--help を読む）だけでなく ongoing** — 並行可能性がある限り **各 write op の後に git レベル検証**が要り、これが per-op 固定費になる。∴ atomic file-back command / journal lock に加え、**「自分の store が `wiki/` に対し stale か」を write 前に出す staleness check**（friction 5 の前段）が、AI が共有 write を安全に既定化できる最小条件。

### 2026-06-27 (sandbox 実走2): rename は graph では参照を保つが、title==H1 page では Markdown projection に alias が残らず import で red 化

差別化核 `rename-page` を sandbox（throwaway store/journal、共有不触、実行後 rm -rf）で直接検証。grasp の存在理由（[[why-not-scrapbox-clone]] / [[write-layer-alpha-and-replay-test]]「rename で `[[..]]` 参照が壊れないか」）の make-or-break。

**graph/store では参照保存は効く（✅）。** `rename-page` は page_id を保持し、旧 handle も新 handle も同一 page に解決、backlinks 生存、`heading_updated:true` で H1 自動更新。回復 toolkit も実は揃っていた: `revert-event <id>` で rename を **in-tool に綺麗に undo**（前 Updates の「回復は git に降りた」は **単発 undo には不要**＝revert-event がある。git 降下が要るのは並行/attribution の方）。`write-diff` は store↔projection drift を安く検出（ok/diffs:N）。`replay-journal` は projection 再生成（ただし **journal-authored page のみ**＝import baseline は含まない、2/40）。

**だが Markdown projection の alias durability に条件依存の穴（❌、要 Codex 確認）。** 機構を repro で特定:

- write-page --create が `id/title/aliases` frontmatter を注入するのは **title ≠ H1 の時だけ**（title==H1 なら identity は H1 から導出可ゆえ未注入）。実 wiki page は規約上 **title==H1**（grep で実 page の `id:`/`aliases:` frontmatter は **皆無**を確認）。
- ∴ 通常 page（title==H1, frontmatter 無し）を rename すると、`heading_updated` が H1 を新名に更新して **title==H1 のまま**になり、**旧名は projection のどこにも残らない**。fresh `import --markdown` で `[[旧名]]` は **unresolved（red）化**、renamed page は backlink を失う。
- 対照実験: title≠H1 page（frontmatter 注入済み）を rename すると `aliases: [..., 旧名]` が追記され、fresh re-import 後も `[[旧名]]` が **解決（✅）**。2 page 同時 import で「title==H1 の旧名→red / title≠H1 の旧名→解決」が同時に出て境界を確定。

**含意（重要）。** backlog L87 の「rename identity を frontmatter 化し direct re-import 後も alias を保つ（1.7.16-17）」「`why-design-B`→`why-not-scrapbox-clone` rename invariant を replay harness で確認（1.7.36）」と、本 repro（**最頻ケース title==H1 の通常 page で alias が落ちる**）が食い違う。未reconcile の境界仮説2つ: ①harness は **`replay-journal`** path を test するが、本 repro の失敗は **`import --markdown`** path（rename event は journal にあるので replay なら復元、plain re-import なら喪失）②default の H1 更新が title==H1 を保ち frontmatter 注入を trigger しない。**→ これは「rename が壊れている」断定でなく、Codex に渡す調査 flag**（harness が write-page-create(title==H1)→rename→`import --markdown` path を cover しているか）。

**silent な点が肝。** rename 直後の `export-markdown --check` は **ok:true**（store と projection は整合）。lossiness は **fresh re-import の時だけ**顕在化＝read 面の absence-hallucination（沈黙＝偽陰性）の write 版（緑信号のまま identity が落ちる）。私が前 log で書いた reconcile 手順「次の grasp-write session は `import --markdown wiki` で reconcile」は **rename を跨ぐと silent に参照を壊す**ので、identity authority は Markdown でなく journal（replay-journal）に置くべき＝[[native-authority-markdown-projection]] を一段強く要求する。

→ backlog 候補（actionable）: (1) title==H1 page でも rename 時に旧名 alias を projection に durable 化。(2) replay harness に create(title==H1)→rename→**import-markdown** path を追加。(3) `import --markdown` が rename 跨ぎで lossy な点を明文化、reconcile 既定を replay-journal に。

### 2026-06-28 (本番実走): 別 harness (Claude Code) × SQLite-SSoT runbook — 前回 candidate は実装され、摩擦は git 手術から setup へ移った

本ページ本文と前 Updates は **lock-free JSONL 時代**（2026-06-26/27）の記録。その後 grasp は SQLite-SSoT へ cutover し、file-back は guard-script runbook（preflight stamp + session uniqueness + write-start staleness + postwrite session marker + file-back lock）+ `revert-plan --scope session` を持つ。本節は **開発担当の Codex とは別の agent/harness（Claude Code）が、その runbook 通りに本番 `wiki/` へ file-back した一次記録**。前回提案した候補の多くが実装済みになっており、摩擦の質が変わった。

- **前回 candidate がほぼ実装され、git 手術に逃げず grasp-write で完走できた。** 前 Updates の「lock / 変更の attribution（誰の hunk か）/ write 前 staleness check / 共有 write を安全に既定化」は、今 runbook の guard 群（preflight stamp・write-start の `event_sequence=unchanged` staleness・postwrite の session marker・file-back lock）と `revert-plan --scope session`（= friction 5 sharpening の attribution）として存在する。今回は前回のような pathspec commit / `git checkout` 退避を**一度も使わず** grasp-write path 内で閉じた。confidence コストは「各 write 後の git 検証」から「runbook guard を順に通す」へ移った＝本ページ meta「不確実下の AI 既定＝共有 write を使わない」は **runbook が confidence を肩代わりしたことで今回は覆った**。

- **[NEW・並行基盤に直結] cross-machine では `.grasp/` 共有 store は git を渡らない。** 開発 Codex はクラウド、私はローカル machine。`.grasp/file-back.sqlite` は gitignored で **git に乗らない**ため、私のローカル store は merge 済み 66 commits より前で固定され、preflight が `semantic_log_stale / strict_ok=False` で正しく停止した。回復＝stale store を退避し現 `wiki/` から fresh bootstrap。**含意（[[parallel-agent-substrate-goal]] の Done-2/3 に直結）**: 「共有 canonical store」は **同一 machine の同一 store file** を指す時だけ成立する。異 machine/異 harness の agent は store を共有しておらず、各自 git-tracked な `wiki/` projection から store を再構成する。∴ 現状 cross-agent の実際の共有経路は **store でなく Markdown projection** であり、これは mode2（grasp=SSoT、Markdown は export-only）の理想と逆向き。並行基盤を cross-machine へ広げるなら canonical store の同期/共有 layer が要る（さもなくば projection が事実上の交換形式に戻る）。[[sqlite-write-concurrency]] の「並行は想定用途」を machine 境界まで延長した形。

- **[解決済み・元 bug 候補] `write-page` の handle 解決が `read` と非対称。** `read <short page_id>` は解決するのに、同じ short page_id を `write-page <id>` に渡すと `page not found` で失敗し、stem handle（`index`）なら成功した。read で得た id を write にそのまま回せない。Codex 確認/修正候補（read と write で handle resolver を揃えるか、write-page が short id を受けるか）。
  - 解決（2026-06-28 / `1.8.78`）: `write-page --target page-id|path` を追加し、`read --page-id` / `history.current_state_target` / `activity` / `claims` が返す page identity または source path を replacement target に直接渡せるようにした。裸の short id を handle として推測するのではなく、write 側の target kind を明示する surface として解決。

- **[NEW] content ページの軽量追記手段が無い（append-section 退役の余波）。** `append-section` は public CLI から削除（1.8.70）。既存 content ページの編集は `write-page` の**全文 full-replace** のみ（`append-log` は log ページ専用）。本 §Updates の追記も大ページ full-replace になり、whitespace risk は postwrite の diff-check で担保したが、「既存節に1行足す/前方リンクを1本張る」だけでも全文 replace が要る。前回 friction 1 gotcha（append-section の二重 heading）は退役で解消した代わりに、**節レベル追記の安価手段が消えた**。

- **[NEW・portability] runbook が単一連続 shell / env 永続を仮定。** `GRASP_SESSION_ID` を preflight → write-start → 各 write → postwrite で1本通す必要があるが、Claude Code の Bash 呼び出しは **呼び出し間で env を保持しない**。SID を file（`/tmp`）に退避し各 command で再 export して通した。Codex の harness では顕在化しないかもしれないが、別 harness では runbook が暗黙に前提する「同一 session env」が崩れる。

- **(minor) orphan: log/index はリンク源に数えない。** 新規 content ページは別 content ページが `[[..]]` で参照するまで lint 孤立扱い。上の「軽量追記手段が無い」と相互作用し、incoming link を1本足すのも full-replace。

**meta（更新）。** 摩擦の主因は前回の correctness/並行安全性から **setup/ergonomics** へ移った: 残るのは (a) cross-machine の store 非共有（最重要・並行基盤 blocker）(c) 軽量追記の欠如（d) env portability。いずれも grasp-write の capability ではなく、**別 agent/harness が同じ substrate に合流する時のコスト**。今日のゴール [[parallel-agent-substrate-goal]] にとって本節最大の datum は (a)＝「`.grasp/` は git を渡らない → 真に共有された store は cross-machine では未成立」。read/write の handle 非対称は `1.8.78` で `write-page --target page-id|path` として解決済み。actionable は [[grasp-backlog]] へ。

## 関連

- [[ai-consumer-cost-and-trust]] — read 面の cost-and-trust。本ページは write 面の対（confidence コスト + 並行安全性）
- [[ai-consumer-feedback-2026-06-23]] — read 面の AI review。本ページは write 面の同型 event
- [[development-arc-retrieval-ahead-of-authoring]] — 「authoring は未実装の差別化核」。本ページは**実装済みで動くが採用が confidence コストで gate される**と update
- [[write-layer-alpha-and-replay-test]] — alpha write 層の位置づけ（read=stable / write=alpha 別 SLA）
- [[native-authority-markdown-projection]] / [[markdown-obsidian-indexed-mirror]] — index/log を projection 化する cutover（friction 4・5 の解）
- [[value-is-problem-solving-not-novelty]] — 前 session でこの fallback が起きた file back
