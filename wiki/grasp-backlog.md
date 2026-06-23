---
type: todo
summary: 旧 SPEC.md と旧 v1-todo.md に書かれていたが、v1 時点で未実装の項目。v1 実装済み事実は grasp-v1-implemented に分離した。
sources:
  - 旧 wiki/SPEC.md（v0.5 実装指示, deleted after split）
  - 旧 wiki/v1-todo.md（一時 TODO, deleted after split）
  - wiki/entities/persona1-user-test-2026-06-23.md
  - wiki/entities/persona2-user-test-2026-06-23.md
  - wiki/entities/fts5-trigram-search.md
  - nishio design note 2026-06-23: non-admin project acquisition
  - `cosense searchFullText/listPages/readPage --help` 2026-06-23
---

# grasp backlog

このページは、旧 `SPEC.md` / 旧 `v1-todo.md` に書かれていたが **v1 リリース時点でまだ実装していないもの**を保持する。完了済みの v1 surface は [[grasp-v1-implemented]]。

## Parser fidelity

2026-06-23 21:49: `#tag` link 化と数字のみ `[1]` / `[2024]` link 化は実装済み。current facts は [[grasp-v1-implemented]]。

### parser false-negative 監査

現状の strict parser は unresolved target noise を減らすため保守的。短い英数字 title などを落としていないか未監査。

## CLI and agent UX

2026-06-23 21:49: zero-hit recovery hints、`grasp read ... --json` 後置許容、help example drift、store missing diagnostics は実装済み。current facts は [[grasp-v1-implemented]]。

### long page navigation

現状: 長大ログ page の default `read` は CLI 一括出力として多すぎることがある。

候補:

- `search --context N`
- `read --around-line <line-id>`
- `peek --line-offset`

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

## Hosted Cosense acquisition without admin export

現状: `import --cosense <json>` は管理画面の JSON export を初回 seed にするため、user が管理者でない project では使えない。`sync` は full seed 済み project の freshness path なので、seed なしの project 取得とは意味を分ける。

候補:

- **full list seed**: `cosense listPages <projectUrl> --sort ... --skip ...` で readable page metadata を pagination し、各 page を `readPage` で取得する。export に近いが、非 admin project で全ページ列挙できるか、rate limit / private page / permission error を要実測。
- **search seed**: `cosense searchFullText <projectUrl> <query>` で特定文字列を含む page を集める。例: キーワード、`[nishio.icon]`、`[/nishio/`。project 全体でなく「自分に関係する slice」を作る用途に向く。検索 query の literal 性、bracket / slash を含む検索挙動、hit 上限と pagination は要確認。
- **author/icon filter seed**: `cosense listPages --filter <name>` は本文中の `[name.icon]` と、その user が編集した page を返す。自分が管理者でない project の「自分が関わった page」取得に使える可能性がある。
- **link crawl seed**: 指定 page / title / URL から `readPage` し、本文の internal links / `projectLinks` を parse して BFS で辿る。`--depth`, `--limit`, `--include-cross-project`, `--same-project-only` のような境界が必要。孤立 page や seed から到達不能な page は拾えない。
- **manual seed list**: URL/title のリストを渡して `readPage` する。Slack や会話ログから抽出した page list、または user が明示した重要 page 群の取り込みに向く。

設計上の注意:

- これは full mirror とは限らないため、store metadata に acquisition mode / seed query / start pages / depth / limit / acquired_at / failed pages を残す。
- 部分取得 corpus 上の `backlinks` / `related` / `unresolved` は「取得済み subset 内」の結果であり、project 全体の事実として表示してはいけない。
- 同じ hosted project の複数 slice を同じ project namespace に混ぜると coverage の意味が曖昧になる。`--project` override で `project:slice` 相当の namespace に分けるか、coverage metadata を project 単位で合成する方針が必要。
- 権限は「その user / token が通常読める page だけ」。admin export の代替であって、非公開データを越権取得する経路ではない。

surface 候補:

- `grasp acquire <project-url> --full-list [--limit N]`
- `grasp acquire <project-url> --search <query> [--search <query> ...]`
- `grasp acquire <project-url> --from-page <title-or-url> --depth N --limit N`
- `grasp acquire <project-url> --seed-file pages.txt`

Open Questions:

- `listPages` は非 admin readable project で全ページを pageinate できるか。
- `searchFullText` は `[nishio.icon]` や `[/nishio/` を literal に扱うか。検索上限を超えた場合の pagination / continuation はあるか。
- `readPage` の hosted line id を採用するか。現行方針は export/sync と同じく grasp 側で `page.id:line-index` を維持。
- partial corpus で `sync` する時、seed predicate 外の recently updated page を取り込むべきか、acquisition mode ごとの sync 動詞に分けるべきか。

## Packaging and distribution

未実装:

- PyPI 公開時の package 名確認。
- `pipx install` 前提の配布導線。
- user-level Skill symlink と package install の統合。
- Python 不可 agent 環境が現実化した場合の native binary 配布。
