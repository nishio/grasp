---
type: decision
summary: grasp を AI に使わせる面（delivery）は CLI + Agent Skill。SPEC Open Q「純 CLI か MCP か」への決着。nishio の cosense-cli が実証したパターン（CLI は Skill 用、責任境界を cli-vs-skill で SSoT 分割）を踏襲。MCP は当面採らない（将来併設の余地は残す）
sources:
  - nishio 指示 2026-06-23「Skills にする選択肢が出てないのはおかしい。cosense-cli の repo はあれは Skills」
  - /Users/nishio/monika-mentoring-wiki/work/cosense-cli（package.json="Agent Skill 用の CLI", docs/guidelines/cli-vs-skill.md, skills/cosense/）
  - SPEC Open Q「Codex からの呼び方: 純 CLI か MCP server 化か」
---

# Decision: delivery = CLI + Agent Skill（MCP ではない）

決定: grasp を AI（＝設計上の「ユーザ」, [[why-not-scrapbox-clone]] 人間 UI なし）に使わせる面は **CLI ＋ Agent Skill**。SPEC Open Q「純 CLI か MCP server 化か」を **CLI+Skill** で決着。純 CLI 単体 / AGENTS.md 直書き指示 / MCP server 化はいずれも採らない（MCP は将来の併設余地のみ残す）。

## 文脈: 「read 一発で近傍が返るエンジン」と「AI が使う導線」は別物

MVP の read=近傍同梱エンジンは動く（[[grasp-cli-mvp]]）。だが verb が叩けることと、AI が **いつ・どの意図で grasp に手を伸ばすか**は別。後者の導線が無いと grasp は「存在するが使われない CLI」になる。「ユーザはどう使うのか」の実体はこの導線層。

## なぜ Skill か（純 CLI / AGENTS 指示 / MCP との比較）

nishio の cosense-cli が既にこの問いを解いていた。`package.json` は自分を「**Agent Skill 用の CLI**」と定義し、CLI は Skill に駆動される前提。

- **純 CLI 単体**: AI に「存在」「いつ使うか」が伝わらない。発火しない。
- **AGENTS.md 直書き指示**: Skill の劣化版。trigger も progressive disclosure も無く、常時 context を食う（or 埋もれて発火しない）。
- **MCP server 化**: 全 verb を常時 tool として並べ、スキーマを server 側で二重管理し、server を運用する。重い。grasp の verb は既に subcommand + `--json` を持つので、tool 化の追加価値が薄い。
- **Agent Skill（採用）**: description の trigger 語でモデルが**自動発火**。`SKILL.md → 手順.md → `--help`` の **progressive disclosure** で context を食わない。スキーマは `--help` のみが持つ **SSoT**。nishio 自身のエコシステムが収束済みのパターン（cosense は MCP server も別に持つが、grasp には Skill を指した＝選好の表明）。

## 責任境界（cosense-cli の cli-vs-skill.md を grasp に写す）

CLI と Skill で同じ情報を二重に持たず SSoT。抽象的言及の重複は可、**具体的な値・コマンド・スキーマは1箇所だけ**、必要なら参照リンクで繋ぐ。

| 層 | 書く | 書かない | load |
|---|---|---|---|
| `grasp <cmd> --help` | mechanics（引数・戻り値スキーマ・例・一文説明） | 「いつ使うか」「コツ」 | コマンド使用の直前に必ず |
| `skills/grasp/SKILL.md` | grasp の domain 知識、「こういう時はこうする」分岐 → 手順書リンク、verb 一覧表（CLI summary の snapshot） | 各 verb の詳細引数・戻り値 | skill 初回呼び出し時（揮発しうる） |
| `skills/grasp/<手順>.md` | その verb を効果的に使う wisdom、「どの field を見よ・なぜ」の観察指示 | 「いつ使うか」（SKILL.md へ）／スキーマ（`--help` へ） | SKILL.md が指示した時だけ |

→ 次ステップ（Skill 実装）はこの 3 層に従う。`--help` を mechanics の SSoT として充実させるのが前提作業。

## grasp 固有の含意: read=近傍同梱が Skill を薄くする

cosense の `read-page.md` が長いのは、hosted/多人数ゆえ **traversal の wisdom**（searchVector→list1hop→list2hop→browse、rename 検出、commit 追跡、「どこまで辿るか」を AskUserQuestion）を Skill が背負うから。grasp は **read=近傍同梱**（中核原理1）で、その traversal を **CLI 出力が既に内包**する。∴ grasp の SKILL.md は cosense より劇的に薄くできる。これは原理1の効用が delivery 層に現れたもの。

## Skill content を書くときの正し方（今回の解釈ミスを封じる）

実装時に下記を skill に書かないこと（2026-06-23 nishio 指摘の訂正）:

- **「`unresolved`（旧 wanted）＝ 自己宛 TODO」と教えない**。原理3 改訂後: unresolved target は **構造事実＝page 実体のない概念 graph node**。意味は `link-stats`/`related`/`backlinks` で**文脈から読む**もので、missing target すべてが「書くべき TODO」ではない。`unresolved` は概念ノードに**気づく** ranked view。cosense skill の「観念的タイトルだけで本文がなくても他ページ文脈で説明される」と同型。
- **「grasp のリンクは `[[...]]`」と教えない**。read-only MVP の read 出力は **Cosense 原文を保持** → AI が見るリンクは `[single bracket]`。`[[X]]` は原理5「書く＝グラフ自動更新」の **未来の write 記法**（MVP スコープ外）。importer が Cosense `[[bold]]` を link 扱いしないのは内部規則で、query 時の AI には無関係。「Cosense と逆」は write 層と importer 内部の混同だった。

## Open Questions

- ~~Skill を grasp repo にどう同梱・install するか~~ → **実装済み**: repo に `skills/grasp/SKILL.md`（SSoT）、`.claude/skills -> ../skills` と `.agents/skills -> ../skills` の symlink で project skill 化（cosense-cli と同型）。`pip install -e .`（依存ゼロ）で `grasp` を PATH に通す。store は `~/.grasp/grasp.sqlite` global default なので別 cwd からも flag なしで同じ store を読む（別 store は `--store` or `$GRASP_STORE`、別 home は `$GRASP_HOME`）。**user-level skill 配置済み**（`~/.claude/skills/grasp -> repo skills/grasp` の symlink、全 project で発火）。同一 Cosense を per-project に複製しない方針（nishio 判断）に合わせ store も global 1個。長期の配布チャネル（PyPI/pipx/npm/native binary）と install 順序の決定は [[language-and-distribution]]（この delivery 決定に直交する implementation/distribution 層）。
- trigger 語の具体（「思い出して」「関連は」「何が未解決か」「この概念どこで言及した」等）。over-trigger と under-trigger の調整。
- MCP を将来併設するか（cosense は CLI+Skill と MCP server の両方を持つ）。当面は不要。
- write/identity 層が入った時の Skill 拡張（cosense の edit-page.md 相当。`[[...]]` write 記法の説明はここで初めて要る）。

## Updates

### 2026-06-23: README/onboarding は「人間＝CLI operator」前提を外す

nishio 指示「**主たるユーザは CLI を直接叩くのではなく、AI に Skill としてインストールして AI が CLI を使う**」。本 decision の「AI＝設計上のユーザ」（[[why-not-scrapbox-clone]] 人間 UI なし）を **human-facing copy に operationalize** したもの。F1 README（[[v1-todo]]）で反映:

- lede が「主たる使い方は `grasp` コマンドを叩くことではない」を明示。人間は (1) AI エージェント（Claude Code 等）に Skill を登録し、(2) 自然言語で AI に問いかける主体、(3) CLI は AI が裏で呼ぶ基盤、と位置づける。
- install は「CLI を PATH に通す」＋「skill を `~/.claude/skills/grasp` に symlink」を first-class な2ステップに。quickstart の主経路は `grasp read` 直叩きでなく「AI に聞く」。

**How to apply**: 今後の README / docs / GTM copy で、人間が verb を覚えて叩くフローを主役に据え直さない。CLI surface の詳細（出力フォーマット等）は人間向け本文に展開せず `grasp <verb> --help` / `--json` に寄せる（本 decision の mechanics SSoT 方針と同根）。ユーザ向け docs にはジャーゴン（"before Co-"・CRDT 等）や内部開発 wiki（SPEC / decisions）への導線を出さない。
