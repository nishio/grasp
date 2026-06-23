---
type: todo
summary: 旧 SPEC.md と旧 v1-todo.md に書かれていたが、v1 時点で未実装の項目。v1 実装済み事実は grasp-v1-implemented に分離した。
sources:
  - 旧 wiki/SPEC.md（v0.5 実装指示, deleted after split）
  - 旧 wiki/v1-todo.md（一時 TODO, deleted after split）
  - wiki/entities/persona1-user-test-2026-06-23.md
  - wiki/entities/persona2-user-test-2026-06-23.md
  - wiki/entities/fts5-trigram-search.md
---

# grasp backlog

このページは、旧 `SPEC.md` / 旧 `v1-todo.md` に書かれていたが **v1 リリース時点でまだ実装していないもの**を保持する。完了済みの v1 surface は [[grasp-v1-implemented]]。

## Parser fidelity

### `#tag` を page link と同等に扱う

現状: Cosense parser は `[link]` を対象にし、`#tag` を edge にしない。

やること:

- Scrapbox / Cosense と同じく `#foo` を `[foo]` と同等の internal link として materialize する。
- `# ` decoration や URL fragment など、誤検出しやすいケースの規則を確認する。
- edge / unresolved_targets / backlinks / related に反映する。

### 数字のみ `[1]` / `[2024]` を link として拾う

現状: v1 parser は `token.isdigit()` を除外している。

判断: Scrapbox では `[2024]` は正当な page link なので、これは parser fidelity bug。

やること:

- 数字のみ token の除外を外す。
- `xs[0]` / `func()[1]` のような ASCII index false positive は従来どおり除外する。

### parser false-negative 監査

現状の strict parser は unresolved target noise を減らすため保守的。短い英数字 title などを落としていないか未監査。

## CLI and agent UX

### zero-hit recovery

現状: `read` / `link-stats` が missing + 0 incoming になると、表記ゆれや記憶違いから回復しにくい。

やること:

- zero-hit 時に `suggest <query>` と `search <query> --limit 3` 相当の hints を返す。
- 近い unresolved target も候補に含めるか検討する。

### root option recovery

現状: `grasp --json read ...` が正だが、`grasp read ... --json` は argparse error になる。

やること:

- subcommand 後の `--json` を受ける、または error に `grasp --json read ...` の具体例を出す。

### help examples の global store 化

現状: root help / subcommand help の一部 example が `--store .grasp/grasp.sqlite` をまだ出す。実 default は `~/.grasp/grasp.sqlite`。

やること:

- help の example を global store 前提に合わせる。
- README / Skill / help の path 表現を揃える。

### long page navigation

現状: 長大ログ page の default `read` は CLI 一括出力として多すぎることがある。

候補:

- `search --context N`
- `read --around-line <line-id>`
- `peek --line-offset`

### store missing diagnostics

現状: store が無い状態で `stats` も error になる。

やること:

- `stats` は store missing を診断として返すか、次アクションを friendly に提示する。
- Markdown folder を import しようとした persona2 に対し、未対応であることを traceback ではなく product language で返す。

## Markdown / Obsidian indexed mirror

persona2 向け on-ramp。詳細決定は [[markdown-obsidian-indexed-mirror]]。

未実装:

- `index-md` / `import-md` / `import --format markdown <folder>` の surface 決定。
- filename / first H1 / frontmatter title / aliases の title resolution。
- frontmatter `id` / `aliases` / `tags` の扱い。
- `[[Page]]`, `[[Page|alias]]`, `[[Page#Heading]]`, embeds, block refs, `#tag` の parser。
- duplicate title / alias collision。
- source folder を壊さない read-only indexed mirror としての差分 index。

## Local write and identity layer

v1 は read-only。local store への write / rename / transclude は未実装。

未実装:

- `write`: page 作成 / 更新と edge 自動更新。
- `rename`: stable id を保った rename。Scrapbox の参照書き換え / redirect stub の二択を避ける。
- `transclude`: line-id を使った行参照。
- aliases / page-id policy。page id を「いつ」「誰が」「どの意味判断で」振るか。

補足: hosted Cosense に AI から書く用途は [[cosense-cli]] の `previewEdit` / `submitEdit` が担う。grasp の write 層は local-only store や非 Cosense ユーザ向けの別目的。

## Search and retrieval

未実装:

- vector search。
- FTS5 trigram hybrid による `search` 高速化。literal substring semantics を守るには [[fts5-trigram-search]] の通り `LIKE` fallback / post-filter が必要。
- backlink line の前後文脈窓。
- related ranking の重み調整と、大規模化した時の 2-hop cost 対策。

## Sync freshness

`grasp sync` の basic upsert は実装済みだが、未実装が残る:

- hosted 側で削除された page の tombstone / local delete detection。
- rename detection。
- last-sync cursor の運用精度。

## Packaging and distribution

未実装:

- PyPI 公開時の package 名確認。
- `pipx install` 前提の配布導線。
- user-level Skill symlink と package install の統合。
- Python 不可 agent 環境が現実化した場合の native binary 配布。
