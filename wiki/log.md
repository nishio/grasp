# Log

## [2026-06-24 03:55] file back | come-from（宣言された用語単位の gather）を設計に取り込み
- 親 llm-wiki の 2026-06-24 設計対話（link overloading → grasp-最適）から grasp に効く部分を取り込んだ。背景厚めの原理ページ [[come-from-declared-gather]] を新規作成。
- 核の言語化: リンクには4仕事（recall / attention / navigation / **読者ケア**）があり、Cosense は substrate が他チャネルを持たないため全部を1つの `[X]` に束ねる。これが [[kj-link-hub-audit-2026-06-24]] の exact 144 → bare 490 の根。原因は **per-occurrence 局所判断 × 双方向 → hub という大域帰結のレベルミスマッチ**（誰も hub を作ろうと決めていない、親切な個別 `[KJ法]` の副作用で創発）。
- come-from（howm 由来）は判断単位を出現→用語に上げ、判断と帰結を用語-大域で揃える。「この語は一般に伝わりにくい」の1判断で全出現が読者に親切。read 側は grasp `mentions`（＝nishio 2022 howm 考察「キーワードページ＝仮想出現一覧」）で既に体現、declare 層と render 層（Markdown mirror で裸出現を自動リンク化）が未実装。
- backlog 反映: (1) `gather` 節に hub 膨張の why（レベルミスマッチ）と come-from declare/render 候補、`mentions --unlinked` の3分類化（(a)意図的 / (b)gap / (c)**AI 作 default 裸**＝`🌀KJ法` 266occ は AI 作）＋ come-from 昇格候補（uncommon×頻度×一意）。(2) "Local write and identity layer" に **リンク2型を別 first-class object に**（felt-sense=行キー / come-from=用語キー）要件。安全域＝必要域（uncommon≈一意）。
- decision 反映: [[ai-consumer-cost-and-trust]] に `## Updates` で第3消費者軸（substrate を持たない公開人間読者。読者ケアは AI 2軸モデルの外。公開面を frozen にすると届かない。come-from-at-render が軽量機構。grasp scope 判断点は nishio）。
- 親 llm-wiki 側の対応ページ: `come-fromリンクは1宣言で全出現を親切にする` / `grasp最適設計はlinkからrecallを剥がす-20260624` / `KJ法リンクハブはリンク密度でなく用法分解で扱う-20260624`。
- 統合: concepts/ 新ページ + grasp-backlog.md 2節追記 + ai-consumer-cost-and-trust.md Updates + index.md concepts に1行。

## [2026-06-24 02:38] file back | peek に line offset を追加
- `peek --line-offset N` を追加し、`--line-limit M` と組み合わせて本文行だけをページングできるようにした。既定 offset は 0。
- JSON は `line_offset`, `lines_truncated_before`, `lines_truncated_after` を返す。互換用の `lines_truncated` は後方省略（`lines_truncated_after`）と同じ値を維持する。text 出力は前方/後方省略を `...` で表示し、offset 指定時は `line_offset: N` を出す。
- [[grasp-v1-implemented]] / [[history]] / [[grasp-backlog]] / README / skill を更新し、version は schema `5` compatible の `1.5.12` に上げた。
- 検証: `python3 -m unittest discover -s tests` OK（42 tests）、`python3 scripts/lint_wiki.py` OK、skill validator OK。

## [2026-06-24 02:36] file back | KJ法 hub の desired state を明文化
- [[kj-link-hub-audit-2026-06-24]] に、改善後の姿を「`[KJ法]` を増やす」ではなく **root link + 用途別 slice handle** に分岐することとして追記した。
- 具体例: `[KJ法]` は KJ法そのもの・川喜田二郎・原理・全体像に残し、通常言及は `表札づくり` / `グループ編成` / `考える花火` / `Kozaneba` / `探検ネット` / `AIにKJ法を教える` へ逃がす。本文の `KJ法` は bare text のままでよく、link は後で読みたい retrieval handle に付ける。
- [[grasp-backlog]] の `gather` 候補に success contract を追加: huge hub banner、exact / bare mention counts、top co-link slices、unlinked mention candidates、`co-links` / `mentions --unlinked` recipes、AI clustering handoff 用 bounded rows を返す。

## [2026-06-24 02:30] file back | search hit に bounded context を同梱
- `search --context N` を追加し、検索 semantics は literal / boolean / scope とも既存のまま、返却 hit に前後 N 行の `context_lines[]` と `context_window` を同梱する形にした。
- text 出力では hit 直下に `context: lines A-B` と周辺行を表示する。JSON では `context` top-level と per-hit context fields を返す。既定 `context=0` では既存 hit に context fields を付けない。
- [[grasp-v1-implemented]] / [[history]] / [[grasp-backlog]] / README / skill を更新し、version は schema `5` compatible の `1.5.11` に上げた。
- 検証: `python3 -m unittest discover -s tests` OK（41 tests）、`python3 scripts/lint_wiki.py` OK、skill validator OK。

## [2026-06-24 02:22] file back | KJ法 hub audit を記録し、bare mention / co-link slice を backlog 化
- nishio の相談「KJ法 が 100+ backlink で広すぎ、リンクにしないで KJ法 とだけ書くケースもある」を受け、`~/.grasp/grasp.sqlite` project `nishio` を `sync` 後に実測。
- 結果: exact `[KJ法]` は 151 links / 144 pages。一方 literal `KJ法` は 681 pages / 2,333 lines / 2,765 occurrences、internal-link span 外の bare `KJ法` は 519 pages / 1,866 lines / 2,246 occurrences、body bare mention は 490 pages / 1,777 lines / 2,156 occurrences。body bare mention があるが exact `[KJ法]` が無い page は 415、`KJ法` 系 link target が一切無い page は 339。
- 判断: 全部を `[KJ法]` にリンク化すると hub を悪化させる。`[KJ法]` は root / representative link とし、通常言及は `表札づくり` / `グループ編成` / `考える花火` / `Kozaneba` / `探検ネット` / `こざね法` など subtopic link に逃がす方がよい。
- [[kj-link-hub-audit-2026-06-24]] を追加。[[grasp-backlog]] に `mentions` / `search --mentions --link-gap`、`co-links`、`gather` の huge hub handling を未実装候補として追記。`--cluster` 却下は維持しつつ、`KJ法` が「rare だが load-bearing な hub」実例であると補正。

## [2026-06-24 02:21] file back | PR #1 Markdown mirror を main に merge
- GitHub PR #1 `feat/read-only-markdown-mirror`（read-only Markdown mirror import）は draft / conflict 状態だったため、PR worktree で `origin/main` を merge し conflict を解消した。解消 commit は `bf206bf`。
- conflict は version/current facts/log まわりで、package version と [[history]] の current version は `1.5.10` に統合した。`import --markdown` と `read --around-line` の両 surface を保持。
- GitHub 上で PR を ready 化し、head SHA `bf206bf3ef6665bb96132c151fa65892add04886` 固定で merge。merge commit は `2a3972d`。`/Users/nishio/grasp` の `main` worktree は `origin/main` に fast-forward 済み。
- 検証: conflict 解消前に PR worktree で `python3 -m unittest discover -s tests` OK（39 tests; sqlite ResourceWarning 1件）、`python3 scripts/lint_wiki.py` OK、`git diff --check --cached` OK。

## [2026-06-24 02:19] file back | log entry は current fact ではなく transition event
- nishio 指摘「A→B→C と変わった時に `B になった` log だけを見ると誤答する」を受け、[[markdown-obsidian-indexed-mirror]] の log/event stream 節に current-state projection と stale-log guard を追記。
- 判断: log entry は「その時点で起きた transition」であり、現在状態の主張ではない。現在状態は entity / decision / backlog などの current page、または event stream を fold して materialize した current projection から読む。
- query 方針: 既定の「今どうなっているか」は current state を読む。temporal / provenance query は event log を読む。log entry を返す時は同じ subject の later events を `superseded_by` / `later_events` として同梱し、中間状態を current fact と誤読させない。
- [[grasp-backlog]] に未実装項目を追加: log entry subject extraction、stale-log guard、`read` と `history` の surface 分離、current projection と provenance links の分離。

## [2026-06-24 02:18] file back | stable line ID は position と分離する
- nishio 指摘「行を挿入した瞬間に後続行の ID が変わる設計は良くない」を受け、[[why-not-scrapbox-clone]] / [[grasp-v1-implemented]] / [[grasp-backlog]] に反映。
- 判断: v1 の `page.id:line-index` は read-only snapshot 内の positional locator であり、write / transclude / 長期引用を跨ぐ安定 line identity ではない。current surface の「line-id」は歴史的呼称として残るが、identity 層では `line.id` と `line_index` を分ける。
- 方針: stable line id は opaque に mint し、store / identity journal に保持する。外部 source に line id が無い場合も deterministic hash / line index に逃げず、sync / reimport では diff で同一判定できる line だけ id を引き継ぐ。挿入は新 id、削除は tombstone、split / merge / 曖昧一致は自動同一視しない。
- 原則: **stable ID requires memory**。content hash は text=identity、line index は position=identity になり、identity-without-name の目的に反する。

## [2026-06-24 02:12] file back | LLM Wiki log を event stream として扱う判断を記録
- nishio の問い「LLM Wiki の `log.md` は並行エージェント衝突の話なのか」を受け、[[markdown-obsidian-indexed-mirror]] に `log.md` / `wiki/log/*.md` の扱いを追記。
- 判断: 並行 agent が1ファイルへ追記して conflict する問題は運用上の理由だが、grasp 側の本筋は **log entry を巨大 page 内 section でなく first-class event record として materialize すること**。
- 方針: 既存 `log.md` は header ごとに仮想 log-entry record へ split し、将来の record-per-file 形式も読む。log は search / provenance query 対象にはするが、既定の content graph edge / `related` / `path` の根拠ページとは分ける。
- [[grasp-backlog]] に未実装項目を追加: log split importer、record-per-file importer、entry id policy、log artifact の graph 除外、`grasp log` / `grasp history <page>`、人間向け `log.md` 生成 surface。

## [2026-06-24 02:08] file back | LLM Wiki index/navigation の grasp 境界を決定
- nishio の問い「LLM Wiki の index を grasp の中に入れるのか外に別の仕組みをつけるのか」を受け、[[markdown-obsidian-indexed-mirror]] に判断を追記。
- 決定: grasp に入れるのは pages / lines / content links / frontmatter summary などの substrate。`index.md` / `index.txt` / `forest-index.md` は通常の根拠ページでなく、store から生成できる projection / navigation layer として扱う。
- 理由: `index.md` を ordinary graph edge として混ぜると巨大 hub になり、`related` / `path` が「全部 index 経由で近い」と壊れる。親 llm-wiki の「index は複製でなく射影にする」診断、kouchou pattern、`探索の地図と事実の分離` と整合。
- [[grasp-backlog]] に未実装項目を追加: navigation artifact 分類、既定で navigation outgoing edges を content graph から除外、`--include-navigation` escape hatch、frontmatter summary からの catalog generation、wiki森 registry は外側 orchestration として保持。

## [2026-06-24 02:05] integration | Markdown mirror PR を main へ追従
- PR #1 `feat/read-only-markdown-mirror` が main の `1.5.8` / `1.5.9` 変更（line-id alias / `read --around-line`）と version 履歴で conflict したため、Markdown mirror series を final `1.5.10` として統合した。
- conflict は package version、[[history]]、[[grasp-v1-implemented]]、log の時系列だけ。実装 surface は `import --markdown` と `read --around-line` の両方を保持。
- 検証: `python3 -m unittest discover -s tests` OK（39 tests; ResourceWarning 1件は既存の unclosed sqlite warning）、`python3 scripts/lint_wiki.py` OK、`python3 -m py_compile grasp/cli.py grasp/sqlite_store.py` OK。

## [2026-06-24 01:58] implementation | read --around-line を追加
- `grasp read --around-line <line-id> --line-context N` を追加。完全 `line_id` から所属ページを解決し、中心行の前後 N 行だけを `lines[]` として返す。
- JSON は `line_window`（around_line_id / center_index / start_index / end_index / context / truncated_before / truncated_after）を返す。通常 read / missing target read では `line_window: null`。
- text 出力は line-id alias と連動し、`line_window: P1:12 (lines A-B, context N)` を表示する。local alias は入力には使えず、存在しない line-id の場合は `--json` / `--full-ids` の完全 ID を使うよう error で案内する。
- Skill の長大ページ手順を、`search --json` → 完全 `line_id` → `read --around-line` の流れに更新。store schema は v5 のまま、public compatibility version は `1.5.9`。検証: `python3 -m unittest discover -s tests` OK（29 tests）、`python3 scripts/lint_wiki.py` OK、`git diff --check` OK。

## [2026-06-24 01:49] implementation | text 出力の line-id をローカル別名化
- text 出力で `page-id:line-index` を既定で `P1:0` のような実行内ローカル別名に畳み、先頭付近に `line-id aliases: P1=<page-id>` legend を出すようにした。
- JSON は従来通り完全 `line_id` を返す。text で完全 ID が必要な場合は `--full-ids` を使う。`--full-ids` は root option だが、`--json` と同じく verb 後にも置ける hidden alias として受ける。
- 対象は `read` / `backlinks` / `related` / `path` / `link-stats` の recovery hints / `peek` / `search` / `unresolved` の text formatter。`export-ai` は本文 bundle なので対象外。
- store schema は v5 のまま、public compatibility version は `1.5.8`。検証: `python3 -m unittest discover -s tests` OK（28 tests）、`python3 scripts/lint_wiki.py` OK、`git diff --check` OK。

## [2026-06-24 01:45] implementation | Markdown mirror の manifest-based 差分 index
- `grasp import --markdown <folder>` が project metadata に Markdown manifest を保存するようにした。manifest は relative path ごとの content hash / mtime_ns / page id / title / aliases を持つ。
- 再 import 時、title / id / aliases / file set が不変で content hash だけ変わった file は page / lines / outgoing edges を差し替える。unresolved targets と project counts は再計算する。title / id / aliases / file set が変わった時は、他 file の alias 解決済み edges が変わりうるため safe full rebuild に戻す。
- JSON / text import output に `markdown_import.mode`, `changed_files`, `full_rebuild_reason` を追加。Dogfood: `wiki/` は 21 pages / 2086 lines / 249 edges / unresolved 0。旧 manifest 不在の1回目は `mode=full, reason=manifest_missing`、直後の2回目は `mode=incremental, changed_files=0`。
- store schema は v5 のまま。Markdown mirror series は main 追従後に public compatibility version `1.5.10` として release。alias-aware なより細かい差分 rebuild は [[grasp-backlog]] に残す。

## [2026-06-24 01:39] implementation | path no-path recovery hints を追加
- `grasp path <A> <B>` で端点は resolve できるが bounded search 内に経路が無い時、`recovery_hints.path` を返すようにした。
- JSON は `reason`（`no_path_within_max_depth` / `search_truncated`）、`next_max_depth`、両端の `link_stats`、`related`、`backlinks` を小さく同梱。text 出力は次に試す `path --max-depth N` / `related` / `backlinks` と候補データを表示する。
- これで negative-result contract は `read` / `link-stats` / `search` / `related` / `path no-path` まで揃った。`gather` など将来 verb は継続監査。
- store schema は v5 のまま、public compatibility version は `1.5.7`。検証: `python3 -m unittest discover -s tests` OK（27 tests）。

## [2026-06-24 01:12] implementation | Markdown frontmatter title / aliases / tags 対応
- Markdown mirror が frontmatter `title` / `id` / `aliases` / `tags` を読むようにした。`title` は canonical title、`id` は page id、`aliases` と file stem は title resolve 候補、`tags` は page から tag target への outgoing edge として扱う。
- `[[alias]]` は import 時に canonical title へ解決して edge 化し、store metadata の alias map により `read <alias>` / `backlinks <alias>` / `link-stats <alias>` でも canonical page を読める。
- Dogfood: `wiki/` は 21 pages / 2077 lines / 248 edges / unresolved 0。frontmatter の `sources: [[...]]` は従来通り本文行 link として edge 化され、バックティック参照は edge にならない。
- store schema は v5 のまま。Markdown mirror series は main 追従後に public compatibility version `1.5.10` として release。first H1 title resolution / Obsidian block refs は [[grasp-backlog]] に残す。

## [2026-06-24 00:58] implementation | read-only Markdown mirror の最小実装
- `grasp import --markdown <folder>` を追加。Markdown folder を既存 SQLite graph store に read-only mirror として materialize し、file stem を title、relative path hash を page id、`[[wikilink]]` / `#tag` を edge として扱う。
- `[[Page|alias]]`, `[[Page#Heading]]`, `[[folder/Page.md]]`, `![[Embed]]` は target title に畳んで edge 化する。inline backtick / fenced code block 内は edge にしないため、grasp wiki のバックティック親 llm-wiki 参照は graph に混ぜない。
- Dogfood: `python3 -m grasp --store /tmp/grasp-wiki.sqlite import --markdown wiki --project grasp-wiki` で `wiki/` を 21 pages / 2072 lines / 248 edges / unresolved 0 として index。`read markdown-obsidian-indexed-mirror` が backlinks 7 / related を返した。
- store schema は v5 のまま。Markdown mirror series は main 追従後に public compatibility version `1.5.10` として release。frontmatter title / aliases / Obsidian block refs / 差分 index は [[grasp-backlog]] に残す。

## [2026-06-24 00:56] implementation | search を default literal + explicit boolean/scope に変更
- nishio 指摘: 空白で query を刻んで AND 検索する既定は「クエリーを書けない人間向け」の interface で、英文 phrase を検索するなら既定は入力文字列通りの literal search が自然。AND / OR / NOT と行単位 / ページ単位を明示的に組み合わせられる方が良い。
- `grasp search <query>` の既定を、空白も含む literal line substring に戻した。literal 0件時の normalized fallback は維持。
- `--mode boolean` を追加。AND / OR / NOT、括弧、quoted phrase、隣接 term の implicit AND に対応。`--scope line|page` を追加し、式を同一行で評価するか同一ページ全体で評価するかを切り替える。旧「空白区切り page AND」は `--mode boolean --scope page "alpha beta"` で明示的に再現。
- dogfood: `search "KJ法 表札"` は既定 literal なので `(none)`、`search "KJ法 AND 表札" --mode boolean --scope page --limit 3` は `Scrapboxベストプラクティス` / `KJ法` の該当行を返した。
- store schema は v5 のまま、public compatibility version は `1.5.6`。検証: `python3 -m unittest discover -s tests` OK（27 tests）。

## [2026-06-24 00:33] implementation | `/ship-next` と Skill の日本語応答方針を反映
- nishio 指摘「日本語で(skillも更新しといて)」を受け、`.claude/commands/ship-next.md` の最終 summary / "what's next?" を日本語で返す運用に更新。
- `skills/grasp/SKILL.md` の回答形式に「ユーザの言語に合わせ、nishio/grasp の開発 wiki / ship loop は日本語 default」を追記。
- 併せて、Markdown mirror は未実装なので、この repo の `wiki/` を読む時に `grasp import --cosense` で folder を代用しないこと、将来 mirror では `[[...]]` を grasp 内 edge、バックティックのプレーン名を親 wiki 非 edge と扱うことを Skill / [[delivery-cli-plus-skill]] に反映。

## [2026-06-24 00:24] file back | grasp wiki 自身を Markdown mirror 層の最初の dogfood corpus にする動機 ＋ dual-link policy 論点を backlog に追記
- nishio 「いつかのタイミングでこのプロジェクトの wiki 自体をこのシステムで作りたい」を受け、[[grasp-backlog]] の Markdown / Obsidian indexed mirror 節に小節を追加。
- 動機: grasp wiki（`wiki/`, Markdown+frontmatter+`[[...]]`）を mirror 層の最初のテスト corpus にすると「設計判断グラフを近傍同梱で辿りながら次を実装する」ループが閉じる。段階は read-only mirror が write 層より先。
- 設計含意: このwikiは **リンク記法が2系統混在**（`[[...]]`=grasp内→edge、バックティックのプレーン名=親 llm-wiki への cross-wiki link→edge にしない）。∴ Markdown parser TODO に「どの記法を edge とみなすか policy」を明示項目として追加。Cosense JSON だけ見ていると気づけない論点。詳細決定は [[markdown-obsidian-indexed-mirror]]。
- nishio 提案「file back, commit, push, what's next? までを一つのカスタムコマンドにする？」を受け、`.claude/commands/ship-next.md` を追加。
- 目的: grasp の作業ループ（差分理解 → wiki file back → `unittest` / wiki lint / diff check → commit → push → 次実装候補提示）を毎回同じ形で閉じる。空差分なら empty commit せず、current backlog から "what's next?" だけ答える。

## [2026-06-24 00:05] implementation | related recovery hints と path 初期実装
- `related <title>` の空結果に `recovery_hints` を追加し、`read` / `link-stats` / `search` と同じ negative-result contract に揃えた。JSON は `query, related[], recovery_hints|null`、text は空結果時に Recovery Hints を表示する。
- `path <A> <B> --max-depth 4 --limit 3` を追加。pages ∪ unresolved targets を node、materialized internal links を無向 edge として bounded shortest path を返す。edge には source page / line-id / line text を同梱し、bridge の根拠を確認できる。
- Dogfood: `grasp path KJ法 弱い紐帯 --max-depth 4 --limit 1` は 3-hop（KJ法 → Scrapbox情報整理術 → 情報と秩序 → 弱い紐帯）を返した。現状は command ごとに一時 adjacency を構築するため、nishio store では約2-5sで、hot read path ではなく実験的 graph reasoning primitive として扱う。
- store schema は v5 のまま、public compatibility version は `1.5.5`。検証: `python3 -m unittest discover -s tests` OK（26 tests）、`python3 scripts/lint_wiki.py` OK、`git diff --check` OK。

## [2026-06-23 23:58] file back | path の hop 距離を簡易計測
- `path <A> <B>` の go/no-go 基準として、`~/.grasp/grasp.sqlite`（project `nishio`, schema v5）で pages ∪ unresolved targets をノード、materialized edges を無向エッジとして距離分布を標本計測した。グラフは 66092 nodes / 115075 undirected edges、最大連結成分 63490 nodes（96.06%）。
- uniform pages 300 pairs は ≤2-hop 0.3%、≤4-hop 9.0%、≤6-hop 63.3%。top-degree pages 300 pairs でも ≤2-hop 4.3%、≤3-hop 30.0%、≤4-hop 76.7%、≤6-hop 99.3%。「大半が ≤2-hop なら path の純増価値は小さい」という懐疑は少なくともこの標本では成立せず、`path --max-depth 4` の試作価値ありと [[grasp-backlog]] に追記した。

## [2026-06-23 23:42] implementation | read related snippets を追加
- [[grasp-backlog]] / [[ai-consumer-feedback-2026-06-23]] の Tier 2 に対応。`grasp read <title> --related-snippets` を追加し、related 2-hop / missing target の source pages に先頭 N 行（`--related-snippet-lines`, default 5）を同梱できるようにした。
- JSON は related/source item に `snippet_lines` / `snippet_truncated` を opt-in で追加し、text 出力は related item 直下に行を表示する。未指定時の `related[]` shape は維持。
- store schema は v5 のまま、public compatibility version は `1.5.4`。検証: `python3 -m pytest tests/test_sqlite_store.py tests/test_cli_help.py` OK、`python3 -m unittest discover -s tests` OK（24 tests）、`python3 scripts/lint_wiki.py` OK、`git diff --check` OK。

## [2026-06-23 23:10] implementation | search normalized fallback を追加
- `search` の literal 0件時に normalized fallback を追加。NFKC query 正規化＋長音除去は SQLite `REPLACE` で実行し、`ﾕｰｻﾞﾃｽﾄ` が `ユーザテスト` / `ユーザーテスト` 行に hit する。text 出力は `[normalized]`、JSON は `match_mode: "normalized"` / `match_terms` を返す。
- 完全なかな/カナ変換は Python 全行 scan になるため、50k lines 以下の小規模 store のみに制限。nishio 規模での zero-hit kana query は 20s 級だったため、大規模 store では schema/index なしに実行しない。
- store schema は v5 のまま、public compatibility version は `1.5.3`。検証: `python3 -m unittest discover -s tests` OK、実データで `search ﾕｰｻﾞﾃｽﾄ --limit 5` が normalized hits を返すことを確認。

## [2026-06-23 22:39] file back | path の Open Q（グラフモデル）を CLAUDE が解決
- nishio が AI consumer feedback の `path <A> <B>` に「リンクとは？ ページがノード？」と問うた件への回答を [[grasp-backlog]] Graph-native primitives に file back。
- 回答: **ノード = pages ∪ unresolved targets**（page-only にすると page-less の概念ハブ＝最も中心的な connector を落とす）、**エッジ = materialize 済み internal-link edges を無向で**。
- 構造的含意: unresolved target は sink（incoming のみ）なので path の端点か hinge（`A→T←B` = co-cite）。∴ **`path` = `related` を 2-hop 超に一般化したもの**で、related のエッジ集合を再利用できる。
- go/no-go: 密グラフでは大半の対が ≤2-hop（related が繋ぐ）ため path の純増価値は稀。**試作前に hop 距離分布を実測**して falsifiable に判定（>2-hop が稀なら工数を Tier-1 recall へ）。
- 監査: 別 session の ai consumer ingest（22:18-22:31）を raw + 本 session の nishio adjudication と突き合わせて faithful と確認。code claim 2件も実機検証（backlinks は `source.views DESC` ランク済 sqlite_store.py:713 / `Page.to_summary` は `id` 含む cosense.py:186）。

## [2026-06-23 22:36] implementation | search recall の page 単位 AND と空結果 recovery hints を実装

- [[grasp-backlog]] / [[ai-consumer-feedback-2026-06-23]] の Tier 1 に対応。`grasp search "KJ法 表札"` のような空白区切り複数語 query は、同一行の literal substring ではなく **page 単位 AND** として、全語を含む page の該当行を返す。単一語 search は従来通り `lines.text LIKE` の line-level substring。
- `search --json` の空結果に `recovery_hints` を追加し、`read` / `link-stats` と同じ negative-result contract へ寄せた。text output も空結果時に Recovery Hints を表示する。
- SQLite schema / parser semantics は変えないため public compatibility version は `1.5.2`、internal `SCHEMA_VERSION` は `5` のまま。
- 検証: `python3 -m unittest discover -s tests` OK（24 tests）。`python3 scripts/lint_wiki.py` OK（壊れた wikilink 0 / index 未登録 0 / frontmatter 不備 0）。`git diff --check` OK。実データで `grasp search "KJ法 表札"` が `(none)` ではなく `Scrapboxベストプラクティス` / `KJ法` の該当行を返すことを確認。

## [2026-06-23 22:31] file back | AI consumer feedback への nishio 採否を反映

- 22:18 ingest した [[ai-consumer-feedback-2026-06-23]] の候補に nishio が adjudication。live status を [[grasp-backlog]] に、原理の訂正を [[ai-consumer-cost-and-trust]] に、event の採否要約を entity に反映。
- **採用**: `read --related-snippets`（**実 Cosense UI も related 先頭 5 行を表示**するので default snippet=先頭 ~5 行 = Cosense parity）。line-id ローカル別名（agree）。backlinks finer ranking（agree、既に views ランク済み）。
- **却下** `--strip-decoration`: decoration は noise でない。`[nishio.icon]`=block の著者、bare image URL=今の AI に読めずとも人間に画像提示・将来 AI も読む。畳んではいけない。token 削減は line-id 別名側でやる。concept page の cost 軸の例示からも除去し「fidelity を捨てない」を明記。
- **却下** 近傍クラスタリング `--cluster`: クラスタリングは AI がやるべき（AI の方が賢い）。CLI は embeddings 後の雑な embedding クラスタリング程度。そもそも 100+ リンクの hub は rare case。raw＋ranking→AI が畳む方針を確定。
- **experimental** `path <A> <B>`: 研究的には筋が良いが実用性は未知、試作可。要確定 Open Q＝グラフモデル（ノード=page か、エッジ=materialize 済み internal-link edges か）を backlog に記録。
- 検証: `python3 scripts/lint_wiki.py` OK（壊れた wikilink 0 / index 未登録 0 / frontmatter 不備 0）。`python3 -m unittest discover -s tests` OK（22 tests）。`git diff --check` OK。

## [2026-06-23 22:19] lint | AI consumer feedback ingest 後の検証

- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。新設 [[ai-consumer-cost-and-trust]]（concept, sources あり）と [[ai-consumer-feedback-2026-06-23]]（entity）は孤立せず（concept は 4 incoming）。既存の孤立 `multi-project-store` 警告は継続（index 登録済み）。
- `python3 -m unittest discover -s tests` OK（22 tests）。`git diff --check` OK。

## [2026-06-23 22:18] ingest | AI consumer（主たるユーザ視点）の v1 フィードバックを取り込み

- `raw/claude-feedback-2026-06-23.md`（Claude Opus 4.8 が grasp の設計上の主たるユーザ＝CLI 越しにグラフを読む AI として v1 を実走したレビュー、25792 pages の実 store で `stats`/`read`/`related`/`search`/miss を実行）を ingest。仮説（採否 nishio 判断）として routing した。
- **concept 新設** [[ai-consumer-cost-and-trust]]: AI consumer の cost-and-trust model を最初の concept page として切り出し。軸1 round-trip/token の経済（read=近傍同梱の why、gather/snippets/token economy backlog の ranking 原理）、軸2 negative-result contract（沈黙の偽陰性 = absence の hallucination、recall を vector より先に直す理由）。read=近傍同梱（実装済）＋ delivery の Skill orchestration ＋ Tier 1-2 backlog をまたいで育っていたため「育ったら切り出す」trigger 成立と判断。
- **entity 新設** [[ai-consumer-feedback-2026-06-23]]: persona1/persona2 user test と同型の review event 記録。validated（read=近傍同梱・related co-citation rank・miss recovery・scale-first）＋ Tier 1-4 findings ＋ 各 finding の routing 先。
- **backlog 追加** [[grasp-backlog]]: Tier 1 search recall（page 単位 AND / OR / 正規化、vector の前＝最優先）、Tier 2 read --related-snippets / `gather --budget` verb（薄CLI テンション付き）/ output token economy（line-id ローカル別名・--strip-decoration）、Tier 3 Graph-native primitives（path / backlinks finer ranking / --cluster）、横断 Negative-result contract（search/related へ拡張＋実データ hint）、Tier 4 を write/identity の consumer 要件に。
- **decision Update** [[why-not-scrapbox-clone]]: identity-without-name の consumer 側価値（AI 引用が write/rename を跨いで腐らない時間安定性）を著者側 rationale に追記。[[delivery-cli-plus-skill]]: `gather` verb vs 薄CLI の orchestration 置き場を Open Question 化。
- **ingest 時の code 確認で既済2点を訂正記録**（既done な ask を積まないため）: ① backlinks は既に `source.views DESC...` でランク済み（grasp/sqlite_store.py）→ Tier 3 の「挿入順かも」懸念は不成立、未済は finer weighting のみ。② `read --json` は既に安定 page-id を含む（`Page.to_summary()` の `id`、grasp/cosense.py）→ Tier 4 の未済は read field でなく rename を跨ぐ identity 層。

## [2026-06-23 22:07] lint | history / versioning policy 追加後の検証
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。
- `python3 -m unittest discover -s tests` OK（22 tests）。`git diff --check` OK。
- `grasp.__version__` は `1.5.1`。

## [2026-06-23 22:04] implementation | admin export なしの hosted acquisition を実装
- `grasp acquire <project-url>` を追加。`cosense searchFullText` による `--search` seed、`listPages --filter` による `--filter` seed、bounded `--full-list` seed、`readPage` + parsed links による `--from-page --depth` crawl、`--seed-file` に対応。
- `acquire` は対象 project namespace を append せず置き換える。`--project` 省略時は `<remote-project>:acquire` を使い、既存 full export project を誤って partial slice で置き換えない。partial corpus の coverage は store metadata に保存し、`grasp stats` の Acquisition 節で mode / coverage / project_url / fetched を表示する。Skill / README でも backlinks / related / unresolved は取得済み subset 内の結果だと明記。
- 検証: `python3 scripts/lint_wiki.py` OK（真の壊れた wikilink 0、index 未登録 0、frontmatter 不備 0）。`python3 -m unittest discover -s tests` OK（22 tests）。public `https://scrapbox.io/shokai/` に対して `acquire --search codex --limit 2` が `shokai:acquire` に 2 pages / 55 lines / 16 edges / 15 unresolved_targets を作り、`read Codex` が本文 + unresolved targets を返した。`git diff --check` OK。

## [2026-06-23 22:03] file back | history と store 互換 versioning policy を追加
- [[history]] を追加。v1 系の public version は `1.x.y` とし、`x` は SQLite table shape だけでなく parser / materialized index semantics が変わり既存 store を current truth としてそのまま読めない時、`y` は store compatible な CLI / docs / recovery / performance 変更時に進める。
- 2026-06-23 の同日 MVP churn を store compatibility ledger として後付け整理: internal `SCHEMA_VERSION=5` の base は public compatibility version `1.5.0`、current working tree は store-compatible `acquire` 追加を含むため `1.5.1`。`1.4.1` は import cache / auto rebuild の y bump、`1.5.0` は `#tag` / 数字 link の parser/index semantics 変更による x bump。
- `[[grasp-v1-implemented]]` から [[history]] へ current version と source page link を追加。package metadata も `1.5.1` に合わせた。

## [2026-06-23 22:00] file back | install path 検証中に schema auto-rebuild の live 観測
- README/SKILL の install 3 ステップ（`pip install -e`→skill を `~/.claude/skills/grasp` に symlink→`import --cosense`）が nishio primary machine で end-to-end 成立済みと確認（CLI は pyenv 3.10.11 の `grasp`、skill symlink live、store 25791 pages）。install path 自体の dogfooding は persona1/2 test がカバーしていなかった面。
- 検証中に偶発観測: `~/.grasp/grasp.sqlite` が code の `SCHEMA_VERSION` 3→5 に追従して最初の通常 command でサイレント再構築。可視副作用（edges 120693→125409 / unresolved 41750→42770 の drift、`imported_at` 更新、その 1 command だけ import latency）を「期待挙動・corruption でない」gotcha として [[grasp-v1-implemented]] の store 節に追記。rebuild の機構自体は既載なので side-effect の誤読防止だけ足した。

## [2026-06-23 21:54] lint | 長大ページ subagent 委譲 file back 後の検証
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。
- `python3 -m unittest discover -s tests` OK（20 tests）。`git diff --check` OK。
- 既存の孤立ページ警告 `multi-project-store` は継続（index 登録済み）。

## [2026-06-23 21:52] file back | 長大ページ処理の責務を Skill / subagent 側に寄せる判断
- Claude Code / OpenCode 系 harness の shell output は tool result として model に返るが、大きい出力は harness 側で truncate され full output file への導線を返す。subagent は独立 context で探索し、親 conversation には最終結果だけを返す。
- ∴ P0-2 long page navigation は CLI に WebFetch 風 summarizer を入れる話ではなく、Skill が長大ページ探索を subagent / Explore agent に委譲し、親には要約・根拠 page・line-id だけ返す運用を持つのが本筋、と [[delivery-cli-plus-skill]] / [[grasp-backlog]] に file back。

## [2026-06-23 21:52] implementation | Skill に長大ページの subagent 委譲手順を追加
- `skills/grasp/SKILL.md` に「長大ページ・ログページを読む」節を追加。親 conversation に長い `read` 出力を直接持ち込まず、探索用 subagent / Explore agent が `search` / `peek` / limit 付き `read` を使って読み、親には結論・根拠ページ・該当 `line_id`・短い引用/要約だけ返す、と明記。
- CLI は LLM 依存の要約をしない deterministic graph reader として維持し、`search --context N` / `read --around-line <line-id>` は実運用で不足が出た時の bounded primitive 候補に留める。

## [2026-06-23 21:52] lint | persona1 P0 friction file back 後の wiki lint
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。
- 既存の孤立ページ警告 `multi-project-store` は継続（index 登録済み）。

## [2026-06-23 21:49] implementation | persona1 dogfooding P0 friction を解消
- [[persona1-user-test-2026-06-23]] / [[grasp-backlog]] の P0 に対応。parser は `#tag` を `[tag]` と同等の internal link として edge 化し、数字のみ `[1]` / `[2024]` も link として拾う。`xs[0]` / `func()[1]` など ASCII index 風 syntax、inline code、URL fragment は false positive として除外する。
- parser/index semantics 変更のため SQLite schema を v5 に更新。v4 store は通常 command 時に import cache から自動再構築され、新しい edge / unresolved / backlinks / related に反映される。
- `read` / `link-stats` が missing + 0 incoming の時、`recovery_hints` として `suggest`, `search --limit 3`, 近い unresolved target を返す。日本語の `ユーザテスト` / `ユーザーテスト` 型に効くよう、unresolved target 候補では長音記号を落とした loose match も使う。
- `grasp read ... --json` のような command 後 `--json` を hidden alias として受ける。help example の repo-local `.grasp/grasp.sqlite` drift を消し、README / Skill は `--store` / `--project` は root option、`--json` は後置も可に更新。
- store missing 時の `stats` は `diagnostic.type=store_missing` と next actions を返す。通常 command の store missing と folder を `import --cosense` に渡した時は traceback ではなく product language で復旧案 / Markdown import 未実装を返す。
- 検証: `python3 -m unittest discover -s tests` OK（20 tests）。`grasp --store /tmp/grasp-missing-demo.sqlite stats --json` は store missing diagnostic を返し、`grasp --store /tmp/grasp-missing-demo.sqlite read Missing --json` と `grasp import --cosense .` は friendly error を返した。

## [2026-06-23 21:41] file back | 非 admin project の取得候補を backlog 化
- nishio 提案: 自分が管理者でない project の取得方法として、特定文字列を含む page（キーワード、`[nishio.icon]`、`[/nishio/` など）を検索 seed にする、指定 page から link を辿る、など。
- [[grasp-backlog]] に "Hosted Cosense acquisition without admin export" を追加。既存の `import --cosense` は admin export、`sync` は full seed 済み project の freshness path なので、非 admin 取得は別の `acquire` / `crawl` 系 surface として扱う。
- 候補: `listPages` pagination + `readPage` の full list seed、`searchFullText` の search seed、`listPages --filter <name>` の author/icon filter seed、link crawl seed、manual seed list。partial corpus では backlinks / related / unresolved が subset 内の結果であることを metadata / 表示で明示する必要がある。

## [2026-06-23 21:42] lint | 非 admin acquisition file back 後の wiki lint
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。
- 既存の孤立ページ警告 `multi-project-store` は継続（index 登録済み）。

## [2026-06-23 21:38] lint | sync file back 後の wiki lint
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。
- 既存の孤立ページ警告 `multi-project-store` は継続（index 登録済み）。

## [2026-06-23 21:35] implementation | import JSON cache から旧 schema store を自動復旧
- nishio 提案「最後に import した JSON を store のそばに置き、旧 schema store をサイレントに回復」に対応。
- `grasp import --cosense <json>` は import 成功後、store 横の `<store>.imports/` に project ごとの Cosense JSON コピーと `manifest.json` を保存する。`--project` override も manifest に保持する。
- `read` / `peek` など通常 command は schema mismatch を検出したら、まず import cache から current schema store を再構築し、そのまま元の command を続行する。`stats` は診断用なので自動復旧しない。cache が無い旧 store では metadata の `last_source_export` / `source_export` を fallback に使う。import cache は seed snapshot なので、hosted の最新差分は復旧後も `sync` の責務。
- 検証: original export を削除し metadata `schema_version` だけ `3` に戻した store に対して `grasp --json --store <path> peek A` が stderr なしで成功する test を追加。

## [2026-06-23 21:35] verification | sync で hosted/local の page count 一致を確認
- 同期前: `grasp --json stats` は local store `~/.grasp/grasp.sqlite` / project `nishio` が 25791 pages。`cosense listPages https://scrapbox.io/nishio/ --sort updated --limit 1` は hosted count 25792。
- `grasp --json sync https://scrapbox.io/nishio/ --limit 20 --dry-run` は `タブUI` 1 件だけを changed として検出。同期前の `grasp read タブUI` は page なし / backlinks なし。
- 実行: `grasp --json sync https://scrapbox.io/nishio/ --limit 20`。`タブUI` 1 件を upsert し、updated 1。
- 同期後: local stats は 25792 pages / 724986 lines、hosted count 25792。再 dry-run は changed 0 で停止点 `タブUI`。page count mismatch は解消。

## [2026-06-23 21:31] verification | cosense-cli と grasp で同一ページ取得を smoke
- 対象: `盲点カード`。hosted は `cosense readPage https://scrapbox.io/nishio/盲点カード`、local は `grasp --project nishio --json peek 盲点カード`。
- 最初の `grasp peek` は既定 store が schema 3 / current 4 だったため `store schema is 3, current is 4; run \`grasp import --cosense <json>\` to rebuild` で失敗。`grasp import --cosense /Users/nishio/grasp/raw/nishio.json` で `~/.grasp/grasp.sqlite` を schema 4 / project `nishio` として再構築した。
- 再構築後、本文行の full diff は差分なし。両者 124 lines、SHA-256 は `362d6da6a9f2b48693d8b1be7b187cd9d5ee5b082d7c8f3c811918e470fa8357`。`grasp read` も同じページで backlinks / related / unresolved を返すことを確認。
- 付記: `cosense listPages https://scrapbox.io/nishio/ --limit 1` の hosted count は 25792、local store は export snapshot 由来で 25791 pages。freshness は引き続き import/sync の責務。

## [2026-06-23 21:28] release | MIT ライセンスを明示
- `LICENSE` に MIT License を追加し、`pyproject.toml` の package metadata と README に MIT 表記を追加。

## [2026-06-23 21:17] implementation | 複数 project を1 store 内の namespace として保持
- nishio 指摘: 複数 JSON は同じ graph に merge する必要はないが、store file を分けるのでなく1つの store に project 名ごとに保持すべき。
- SQLite schema を v4 に更新。`projects` table を追加し、pages / lines / edges / unresolved_targets / unresolved_target_examples を `project` 列で namespace 化。`grasp import --cosense <json>` は export root `name` を project 名にし、同名 project だけを置き換える。他 project は保持する。`grasp import --project <name> --cosense <json>` で override 可能。
- read/search/backlinks/related/unresolved/sync は selected project 内だけを見る。store に1 project だけなら `--project` 省略可、複数 project なら `--project <name>` / `$GRASP_PROJECT` が必要。`stats` は project list と aggregate/project counts を返す。
- [[multi-project-store]] を追加し、[[grasp-v1-implemented]] / README / Skill を更新。検証: `python3 scripts/lint_wiki.py` OK（壊れた wikilink 0、index 未登録 0、frontmatter 不備 0）、`python3 -m unittest discover -s tests` OK（13 tests）、`git diff --check` OK。

## [2026-06-23 21:11] refactor | 旧 SPEC / v1-todo を実装済み facts と backlog に分解
- nishio 判断: `SPEC.md` は定義ではなく v0.5 を実装するための一時指示、`v1-todo.md` も一時 TODO。v1 リリース後に保つ必要はない。
- `[[grasp-v1-implemented]]` を追加し、v1 時点で実装済みの CLI surface / store / parser / delivery / performance facts を集約。`[[grasp-backlog]]` を追加し、旧 SPEC / 旧 v1-todo にあった未実装項目（`#tag`, 数字 link, zero-hit recovery, root option recovery, Markdown adapter, write/identity, search/vector/sync 残課題など）を集約。
- `wiki/SPEC.md` と `wiki/v1-todo.md` を削除。index / AGENTS.md / CLAUDE.md / current decision/entity ページの参照を新ページへ張り替え。`python3 scripts/lint_wiki.py` OK（壊れた wikilink 0、index 未登録 0、frontmatter 不備 0）。

## [2026-06-23 20:59] file back | write の分担（hosted=cosense-cli / local-only=grasp write）を記録
- nishio の README roadmap 編集を [[cosense-cli]] の「使い分け」に固定。hosted Cosense への write/edit は cosense-cli（`previewEdit` / `submitEdit`）が担い、grasp 自身の write 層（旧 `SPEC.md` roadmap, v1 外）は (a) 非 Cosense ユーザ、(b) オンラインでなくローカルに閉じて書きたいケース のサポートが目的。
- ∴ 書き込み先（hosted ↔ local-only）で棲み分け、grasp write は cosense-cli の重複ではない。Cosense ユーザの hosted 編集は cosense-cli が担うので grasp が hosted write を実装する動機は無い、と明記。

## [2026-06-23 20:59] lint | wiki 全体の意味的矛盾チェック
- `python3 scripts/lint_wiki.py` OK（壊れた wikilink 0、index 未登録 0、フロントマター不備 0）。
- 意味的な矛盾候補: 旧 `v1-todo.md` の F4 判断（write/transclude/rename は v1 に載せない）に対し旧 `SPEC.md` の CLI surface 表がまだ3動詞を載せている。F3 判断（数字のみ `[1]`/`[2024]` はリンクとして拾う）に対し旧 `SPEC.md` / [[grasp-cli-mvp]] / [[cosense-json-export]] は strict parser が数字のみを link としない現状を正典風に保持している。旧 `v1-todo.md` F1 は README 未作成と `--consense` typo を含み、後続 README 作成ログ・実装の `--cosense` と食い違う。

## [2026-06-23 20:53] file back | README を「AI が主たるユーザ」前提で再センタリング
- nishio 指示「主たるユーザは CLI を直接叩かず、AI に Skill として入れて AI が CLI を使う」を [[delivery-cli-plus-skill]] に Update として固定（「AI＝設計上のユーザ」の human-facing copy への operationalize）。README lede が「主たる使い方は `grasp` コマンドを叩くことではない」を明示、install に skill symlink を first-class step 化、quickstart の主経路を `grasp read` 直叩きでなく「AI に聞く」に。
- あわせて user docs hygiene を記録: ジャーゴン（"before Co-" 等）と内部 dev wiki（SPEC / decisions）への導線をユーザ向け README に出さない（F1 README で適用済み, 旧 `v1-todo.md`）。

## [2026-06-23 20:52] lint | `stats` README 説明粒度 file back 後の wiki lint
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。既存の孤立 `v1-todo` は index 登録済みのまま。

## [2026-06-23 20:51] file back | README から `read` 生出力例を削除
- nishio 指摘「こんな生データ、人間が直接みるわけじゃないから書かないでいい」に合わせ、README の `read` 出力サンプル節を削除。
- README は人間向けの価値・install・AI Agent Skill 導線に絞り、出力フォーマット詳細は `grasp read --help` と `grasp --json read ...` に寄せる。これは `grasp <verb> --help` を mechanics SSoT にする [[delivery-cli-plus-skill]] の方針とも一致する。

## [2026-06-23 20:51] verification | README / import UX 変更後の検証
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。既存の孤立 `v1-todo` は index 登録済みのまま。
- `python3 -m unittest discover -s tests` OK（12 tests）。`git diff --check` OK。

## [2026-06-23 20:50] file back | README の `stats` 説明粒度を調整
- nishio 判断: README の command 一覧では `stats` の詳細 schema まで書かず、「ストアの件数・更新日時など」程度の人間向け概要に留める。詳細は `grasp stats --help` と [[grasp-cli-mvp]] 側で保持する。
- README の `stats` 行を「ストアの件数・更新日時などを確認」に変更し、[[grasp-cli-mvp]] に README/detail の役割分担を記録。

## [2026-06-23 20:50] lint | `sync` runtime 前提 file back 後の wiki lint
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。既存の孤立 `v1-todo` は index 登録済みのまま。

## [2026-06-23 20:50] file back | `sync` の cosense-cli install 前提を明示
- `grasp sync <project-url>` は hosted freshness path なので、通常の local read/search と違って `@helpfeel/cosense-cli` の `cosense` binary が install 済みで PATH にあり、対象 project に認証済みであることが動作条件。
- 旧 `SPEC.md` M2-4 / CLI 動詞表、[[incremental-sync]]、[[cosense-cli]]、README、Skill の sync 説明に前提を反映。`--cosense-command` で binary 名 / path を差し替え可能であることも記録。

## [2026-06-23 20:49] lint | import `--force` 削除後の wiki lint
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。既存の孤立 `v1-todo` は index 登録済みのまま。

## [2026-06-23 20:48] implementation | import の `--force` を削除し既存 store をそのまま置換
- nishio 指摘「古い store がある時に拒否して欲しいことはない。`--force` は余計な option」に合わせ、`grasp import --cosense <json>` を初回構築・再構築兼用に変更。CLI は既存 store を拒否せず、import 成功時に置き換える。
- 実装上は既存通り temp store を作成してから `os.replace` するため、再構築の途中失敗で既存 store を消す挙動にはしない。
- SPEC / README / Skill / [[grasp-cli-mvp]] / help test を更新。

## [2026-06-23 20:48] lint | FTS5 trigram 検証ページ切り出し後の wiki lint
- `python3 scripts/lint_wiki.py` OK。真の壊れた wikilink 0、index 未登録 0、フロントマター不備 0。既存の孤立 `v1-todo` は index 登録済みのまま。

## [2026-06-23 20:46] file back | FTS5 trigram 検証を独立 entity 化
- [[grasp-cli-mvp]] 内の「FTS5 trigram 検証メモ」を新ページ [[fts5-trigram-search]] に移動。`grasp-cli-mvp` には現状判断（correctness 優先で `lines.text LIKE` 維持）とリンクだけを残した。
- [[markdown-obsidian-indexed-mirror]] / [[language-and-distribution]] の FTS5 hybrid 参照を新ページへ差し替え、search index 設計上の注意点を一箇所に集約した。

## [2026-06-23 20:17] file back | 公式 cosense-cli との速度比較を再計測で更新
- [[cosense-cli]] の実測比較を、旧 MVP（毎回 123MB JSON full parse で ~3.4s）から現行 SQLite warm store ベースへ更新。median of 5 で `grasp read` 67ms / `peek` 65ms / `related` 72ms / `search 盲点 --limit 100` 185ms、公式 `cosense` v1.4.4 は `browsePage` 578ms / `browseRelatedPages` 1169ms / `searchFullText` 875ms / `searchVector` 792ms。
- 初回 seed は別枠として temp store import 8.3s。含意: **反復 read/search は grasp、freshness delta は cosense-cli**。`sync --limit 20 --dry-run` 695ms は `listPages --sort updated --limit 20` 636ms と同程度で、sync の律速が hosted network/API であることも明記。

## [2026-06-23 20:15] implementation | explicit import option を `--cosense` に変更
- nishio 指摘「`grasp import --export your.json` は将来サポート対象が増えた時に何の export か混乱する。`--cosense` がよい」に合わせ、明示 import surface を `grasp import --cosense <json> --force` に変更。
- リリース前なので互換性は取らず、global `--export` / `--rebuild-store` / store 不在時の暗黙 seed は削除。store 作成・再構築は `grasp import --cosense <json> --force` に一本化。
- SPEC / Skill / [[grasp-cli-mvp]] に file back。

## [2026-06-23 20:10] decision | Cosense ヘビーユーザ user test の F1–F5 を v1 TODO に確定
- 第3の視点（nishio でない Cosense 熟練者が GitHub から自前 project を入れようとする。persona1/persona2 のどちらとも違う）で CLI を user test し、新ページ 旧 `v1-todo.md` に nishio 判断を固定。
- F1 README=★最優先（landing 無し・自前 project の入れ方が無い・default/例が nishio 固有）。F2 `#hashtag` をデフォルトで Scrapbox 同様リンク化（無視オプションは将来）。F3 数字のみ `[1]`/`[2024]` を捨てるのはバグ→拾う（`xs[0]` 等の false positive 除外は維持）。F4+transclude write/transclude/rename は v1 に**載せない**("planned"でもない)＝v1=Export JSON の AI 高速 read-only、SPEC 表から削除。F5 help 例 `.grasp/grasp.sqlite` を実デフォルト `~/.grasp/grasp.sqlite` に一致。
- 良かった点（中核仮説）: `read`=近傍同梱が「関連ペインのテキスト版」として ~0.1s で成立、search/suggest/peek/unresolved が Scrapbox の手癖に対応、case/space 正規化一致。
- 未了: persona3（Cosense 熟練者 but not nishio）の user test ページ化は offer のまま未実施。本 TODO は SPEC 反映 action を含むが、SPEC.md は別セッション編集中のため本 session では未編集（commit もしていない）。

## [2026-06-23 20:09] implementation | `export-ai` default を depth 1・limit なしに変更
- nishio 指示「デフォルトは `--depth 1` で limit なし」に合わせ、`grasp export-ai` の `--direct-limit` / `--indirect-limit` default を `None`（無制限）に変更。`--depth` は既に 1 が default。
- SPEC と `skills/grasp/SKILL.md` に default semantics を明記。

## [2026-06-23 19:56] file back | global store の設計原理を canonical な store decision へ昇格
- 19:53 の global 化を mechanics として log/delivery decision に書いたが、**「store は global に1個（per-project 複製しない）」という原理**は store の正典 [[persistence-custom-format]] に無かった。そこへ Update を追加: store は単一 AI 所有 knowledge store ＝ どこでも同じ1個（cwd cache でない）、置き場は `$GRASP_STORE → $GRASP_HOME/grasp.sqlite → ~/.grasp/grasp.sqlite`、store path は project state でなく user/agent state、別 knowledge set は `$GRASP_HOME` で home ごと差し替え。delivery の global skill 判断（[[delivery-cli-plus-skill]]）と同根＝「1つの外部脳=1つの store=どこからでも同じ skill」。
- 同ページの stale な Open Q「Cosense export スキーマは Codex が実物で確認」を解決済みに（[[cosense-json-export]] が 25791 pages で確定済み）。

## [2026-06-23 19:53] implementation | store と skill を global 化（per-project 複製しない）
- nishio 判断「同一 Cosense を per-project に別々に持ちたいことはない → global に入れて DB も global」。`grasp/cli.py` の `default_store_path()` を cwd 相対（`./.grasp/grasp.sqlite`）から **`$GRASP_HOME or ~/.grasp` 配下**に変更、`grasp_home()` helper を追加。`default_export_path()` も `$GRASP_EXPORT → ~/.grasp/nishio.json → cwd raw/nishio.json` の順に。
- 既存 store を `~/.grasp/grasp.sqlite` へ移動、seed を `~/.grasp/nishio.json -> repo raw/nishio.json` の symlink に。**`/tmp` から flag 無しの `grasp read/link-stats` が動作**。`python3 -m unittest discover -s tests` 11 OK（tests は default path 非依存）。
- skill を **user-level 化**: `~/.claude/skills/grasp -> /Users/nishio/grasp/skills/grasp`（SSoT 1本を symlink、全 project で発火）。SKILL.md「実行方法」を global default 前提に更新（別 cwd でも flag 不要）。`*.egg-info/` を gitignore。
- file back: [[delivery-cli-plus-skill]] の install Open Q を「user-level skill＋global store 配置済み」に更新。SPEC は別セッションが既に global store 記述に追随済みで一致。

## [2026-06-23 19:52] file back | Markdown / Obsidian folder は indexed mirror として扱う
- nishio の問い（既存 Markdown 束 or Obsidian folder を point し、grep より高速な検索とリンクたどりを付与する Skill 方向はどうか）を新 decision [[markdown-obsidian-indexed-mirror]] に固定。
- 核心: **Skill が速くするのではなく、Markdown / Obsidian folder adapter が read-only indexed mirror を作る**。SQLite store に pages / lines / edges / unresolved targets / search index を materialize し、Skill は `grasp` CLI を使わせる薄い層にする。
- pitch は "faster grep" では弱い。persona2 には **indexed graph reader for Markdown / Obsidian notes, optimized for LLM agents** と言う。価値は `read` が本文 + 逆リンク行 + related + unresolved targets を一体で返すこと。初期は write-back / rename propagation / Obsidian plugin 完全互換を非目標にし、既存 vault を壊さない point-at-folder 体験を優先。

## [2026-06-23 19:50] file back | persona1 user-test の設計含意を SPEC / entity へ伝播
- [[persona1-user-test-2026-06-23]] の発見を旧 `SPEC.md` と [[grasp-cli-mvp]] に反映。`~/.grasp/grasp.sqlite` global store default（`$GRASP_HOME` で差し替え）を current mechanics として明記し、repo-local `.grasp/grasp.sqlite` 前提の記述を更新。[[delivery-cli-plus-skill]] も「別 cwd では --store 必須」から「global store なので flag なしで読む」に更新。
- SPEC に **M2-5 persona1 dogfooding UX fixes** を追加。zero-hit recovery（`ユーザテスト` vs `ユーザーテスト` などの表記ゆれ空振り）、verb 後 `--json` の回復、search hit line から周辺本文へ行く surface を read-only の次課題として固定。

## [2026-06-23 19:47] user-test | persona1 dogfooding で CLI 体験を検証
- [[persona1-user-test-2026-06-23]] を追加。persona1 を [[positioning-two-personas]] の定義通り「日本語 Cosense ヘビーユーザ = nishio dogfooding」として、`search` → `read` → missing target `read` → source page traversal を実走。
- 結論: **read=近傍同梱**と **linked target without page を backlinks/source pages で読む体験**は persona1 に刺さる。`民主主義` のような page なし概念でも 82 links / 78 source pages で意味が読める。
- 摩擦: `ユーザテスト` vs `ユーザーテスト` の表記ゆれで missing/0 links に落ちる、`--json` を subcommand 後に置くと回復案なしで argparse error、長大ログ page の default read が 513 lines / 66KB、current help/Skill の default store `~/.grasp/grasp.sqlite` と SPEC/entity の repo-local store 記述が drift。

## [2026-06-23 19:46] user-test | persona2 視点で fresh onboarding を検証
- [[persona2-user-test-2026-06-23]] を追加。persona2（世界の LLM Wiki / Markdown 束ユーザ）として、空 cwd + 空 `GRASP_HOME` + 最小 `notes/Alpha.md` から初回導線を試した。
- 結果: persona2 active release としては fail。`grasp --help` / package description は Scrapbox/Cosense 寄りで persona2 の hook（Markdown 束より local graph store）を出していない。README/docs も無い。`grasp stats` は store/export 無しで onboarding にならず、`grasp import notes` は unrecognized args、`grasp --export notes import --force` は `IsADirectoryError` traceback。
- 判断: MVP の persona1 dogfooding には問題ないが、persona2 を狙うなら Markdown import adapter は release gate。暫定でも directory export の friendly error、store missing の診断、英語 README / demo が必要。

## [2026-06-23 19:43] file back | audience を2層 positioning に決定化、name=identity 欠陥を精密化
- nishio の persona 観（JP Cosense ヘビーユーザは自分の一側面／世界の LLM Wiki・Markdown 束ユーザは upside risk として狙う／HN・Reddit 投稿もあり）を新 decision [[positioning-two-personas]] に distill。核心: **substrate は共有だが value prop と on-ramp が persona ごとに別**。driver=persona1（dogfooding）、persona2 は設計の再センタリングでなく **addition**（Markdown adapter＋英語 docs＋一般化 pitch）で狙う。罠＝dilution（read=近傍同梱が「graph DB を CLI で」との差を溶かさない）。
- 設計含意を2つ固定: ①**Markdown import adapter は persona2 の on-ramp そのもの**（旧 `SPEC.md` 入力節の "後で足せる" は persona1 都合で、persona2 を狙うなら re-rank 候補）。②identity-without-name は両 persona に別の言葉で刺さる。
- **nishio 訂正で name=identity 欠陥を精密化**: 「Markdown と Scrapbox は同じバグ」は誤り。Scrapbox は rename でリンクを**書き換え or redirect** して生存させる（リンクは切れない）。欠陥は**そのリンク生存解が払うコスト**（書き換え＝文意破壊／redirect＝旧名 stub 累積）。3者で失敗モードが別物（Markdown=リンク切れ／Scrapbox=文意破壊 or stub 累積／grasp=どちらも無し）。[[why-not-scrapbox-clone]] の該当箇所も redirect コストを補って一段精密化。
- index に decision 1 行を登録。

## [2026-06-23 19:42] file back | warm-store 再計測を実装現状ページへ伝播
- [[language-and-distribution]] の一次データ（warm page cache・median of 5 の各 verb wall time）を、性能事実の source of truth である [[grasp-cli-mvp]] にも反映。`stats` 70ms / `backlinks` 54ms / `read`（近傍同梱）83ms / `unresolved` 52ms / `search` 178ms、固定オーバーヘッドは bare `python3` 33ms・`import grasp` ~free（依存ゼロ）。
- entity ページに残っていた **stale な「read 約 0.7 秒 / wall 1.0 秒」を訂正**: あれは早い時点の cold/単発計測で、warm steady-state は 50–180ms。中核 read は既に sub-100ms、`search` 178ms だけ SQLite `LIKE` 全行スキャン律速（index が lever、host 言語ではない）。
- 上書きせず `## Updates` 流の inline note 追記（entity の既存 update 慣習に合わせた）。decision の主張に entity 側の一次データが整合した。

## [2026-06-23 19:39] file back | 実装言語 × 配布チャネルの長期比較を decision 化
- nishio の問い（Python/Node/Rust で native build／Claude Code は npm 更新／PyPI は pip）を新 decision [[language-and-distribution]] に distill。核心は**実装言語と配布チャネルは独立な2軸**で、混同（"Node でネイティブビルド"）を解いた。
- **言語論点は session 内実測で溶けた**: warm store（238MB）で bare `python3` 起動 33ms / `import grasp` ~27ms（依存ゼロ）/ `read` 83ms / `backlinks` 52ms / `search` 178ms。重い仕事は全部 SQLite=言語非依存、固定 Python オーバーヘッドは ~30ms のみ。旧 `SPEC.md` 原理1「graph を流れる体験」は既に sub-100ms で達成済み → native 化の latency 便益はほぼ無い。[[grasp-cli-mvp]] の旧「read 0.7s」は cold/最適化前と判明。
- **∴ 長期の実体は配布チャネル**。決定: 当面 Python のまま（surface churning 中・依存ゼロ）、外部 consumer が出たら PyPI 公開 → `pipx install`（素の pip は PEP 668 で弾かれる）。**native(Go/Rust)→npm(optionalDependencies)+Homebrew は trigger 待ち**（Python 不可 agent 環境／warm でも latency 体感／SQLite を超える構造要求）。**SQLite store が言語非依存の契約**ゆえ hot read path だけ先に native 化する段階移行で de-risk。**Node-native は採らない**（SQLite 弱・runtime 依存・起動便益なし）。[[delivery-cli-plus-skill]] の CLI+Skill 境界が言語非依存である点とも整合（言語選択は delivery 決定に直交）。
- index に decision 1 行を登録。

## [2026-06-23 19:30] implementation | Claude Code 用 Agent Skill `skills/grasp/SKILL.md` を実装
- [[delivery-cli-plus-skill]] に従い、cosense-cli パターンで grasp Skill を作成。repo に `skills/grasp/SKILL.md`（SSoT）、`.claude/skills -> ../skills` / `.agents/skills -> ../skills` symlink で project skill 化。`pip install -e .`（依存ゼロ）で `grasp` を PATH に通し、別 cwd から `--store` 絶対指定で動くことを smoke 確認。
- 薄く保った: 「いつ使うか」のケース分岐＋verb 一覧 snapshot のみ。各 verb の引数/戻り値は `grasp <cmd> --help`（mechanics SSoT）に委譲し二重化しない。read=近傍同梱ゆえ cosense の read-page.md 相当の traversal 手順書は不要（[[delivery-cli-plus-skill]] の予言通り SKILL.md 1枚で足りた）。
- 解釈ミス2点を skill content に封じた: `unresolved` は「TODO ではない概念ノード rank view」（実例 `民主主義` 82 links/78 pages/本文なし）、リンクは Cosense 原文 `[single]` 表記で grasp 読みでも `[[...]]` を使わない。`cosense` skill（hosted/最新/ベクトル検索）との使い分け表も付けた。
- decision の install Open Q を解決済みに更新。残: user-level skill（`~/.claude/skills/grasp/`）化は未配置（in-repo のみ）。

## [2026-06-23 19:21] implementation | `grasp <cmd> --help` を mechanics SSoT として拡張
- argparse help を拡張し、root help に global option の位置規則と mechanics SSoT 方針を追加。全 subcommand help に arguments / `--json` return keys / Examples / Notes を持たせた。
- `tests/test_cli_help.py` を追加し、全 command help が `Returns (--json):` と `Examples:` を含むこと、`read` が `--unresolved-limit` / `unresolved_targets` を示し旧 `--wanted-limit` を含まないことを固定。
- [[grasp-cli-mvp]] に、Agent Skill は schema を重複保持せず使用直前に `grasp <cmd> --help` を読む、と file back。

## [2026-06-23 19:20] decision | delivery = CLI + Agent Skill（純CLI/MCP でなく）
- nishio 指摘:「Skills にする選択肢が出てないのはおかしい。cosense-cli の repo はあれは Skills」。実際 cosense-cli の `package.json` は自分を「Agent Skill 用の CLI」と定義し、`docs/guidelines/cli-vs-skill.md` が CLI/Skill 責任境界を SSoT 分割。
- 新 decision [[delivery-cli-plus-skill]]: grasp の利用面 = **CLI + Agent Skill**。SPEC Open Q「純 CLI か MCP か」を CLI+Skill で決着（MCP は当面採らない／将来併設余地）。3 層: `grasp <cmd> --help`=mechanics SSoT / `SKILL.md`=いつ・どう使う＋verb 表 / `<手順>.md`=wisdom・観察指示。grasp 固有: read=近傍同梱（原理1）が cosense skill の traversal wisdom を CLI 出力に吸収 → SKILL.md は薄い。
- 私の skill content 案の解釈ミス2点を nishio が訂正、decision に封じた: ①「`unresolved`(旧wanted)＝自己宛TODO」は誤り（原理3 改訂で構造ノード扱い、TODO と決めつけない）。②「grasp のリンクは `[[...]]`」は誤り（read-only MVP は Cosense 原文 `[single]` 保持、`[[X]]` は未来の write 記法でスコープ外）。
- 旧 `SPEC.md` Open Q「Codex からの呼び方」を解決済みに、index に decision を登録。次: `--help` 充実 → `skills/grasp/SKILL.md` 実装。

## [2026-06-23 19:03] implementation | `wanted` 互換を捨て `unresolved` に破壊的変更
- ユーザ判断: まだ利用者はいないので互換性を考えず、設計語彙に合わせて変える。`wanted` command / JSON field / SQLite table 名を削除し、`unresolved` command / `unresolved_targets` field / `unresolved_targets` table に変更。schema_version は 3。
- `read` option は `--wanted-limit` ではなく `--unresolved-limit`。`read` result から `red_link` field を削除し、page なし target の状態は `page: null` + `link_stats` + `related` で表す。
- `unresolved_targets` entries は `count` ではなく `link_count` を持つ。`stats` も `unresolved_targets` count を返す。旧 schema の通常 command は rebuild 必須で止める。

## [2026-06-23 18:53] implementation | missing link target の link stats と related source pages を追加
- 「link があるが page がない」こと自体は `wanted` ではなく unresolved graph node と整理。旧 `SPEC.md` の中核原理・データモデル・CLI surface を更新し、`wanted` は unresolved targets の ranked view と明記。
- `grasp link-stats <title>` を追加。existing page / unresolved target の incoming `link_count`, `source_page_count`, `link_multiplicity` (`none` / `single` / `multi`) を返す。unresolved target は materialized `wanted` row、existing page は `edges.target_norm` index で数える。
- `related <unresolved-target>` は空でなく、その target に link している source pages を `relation=backlink-source` として返す。実データ smoke: `民主主義` は page なしだが 82 links / 78 source pages、`related 民主主義 --limit 5` が source pages を返した。

## [2026-06-23 18:45] file-back | FTS5 trigram 検証メモを記録
- [[grasp-cli-mvp]] に FTS5 trigram の実測と判断を追記。3文字以上の safe query では hybrid（`MATCH` → `LIKE`）が高速だが、2文字日本語 query は trigram に乗らず、記号入り query は FTS query syntax と衝突する。
- `MATCH` は literal substring search ではない（例 `MATCH 'abc bcd'` が `abcd` / `abcde` / `abcXbcd` も返す）ため、grasp の `search` semantics を保つには hybrid でも最後に `line.text LIKE '%query%'` が必要。現段階では特殊化として見送り、correctness 優先で `lines.text LIKE` を維持。

## [2026-06-23 18:31] implementation | store schema status を可視化
- `grasp stats` を追加。store path, schema_version, current_schema_version, schema_ok, source_export, imported_at, pages/lines/edges/wanted を text/JSON で返す。
- 通常 command で古い schema の store を開いた場合、stderr に `--rebuild-store` / `grasp import --force` を促す警告を出す。v1 store は fallback で動くが、schema v2 の `wanted_examples` 最適化を使うには rebuild が必要。
- 検証: unit tests OK。実データ store で `stats` text/JSON を確認。metadata を一時的に schema 1 に書き換えた copy で warning 出力を確認。

## [2026-06-23 18:27] implementation | wanted examples を materialize、FTS search は見送り
- `wanted_examples` table を追加し、import / sync 後の `rebuild_wanted` で各 wanted target の上位 5 example edge を materialize。`wanted --limit N` が N 回 example query を投げないようにした。schema_version は 2。
- Python 内部計測では `wanted(limit=100)` 約 6ms。CLI wall time は Python 起動 + output 込みで約 1.0 秒。
- SQLite FTS5 trigram を試したが、2文字日本語 query（`盲点`）は `MATCH` で拾えず、FTS table `LIKE` では `盲点カード` の recall が落ちた。本文検索は correctness 優先で `lines.text LIKE` のまま維持。
- 実データ import は約 9.6 秒。`search 盲点 --limit 100` 約 1.16 秒、`wanted --limit 100` 約 1.01 秒、`read 盲点カード` 約 1.03 秒（CLI wall time）。

## [2026-06-23 18:19] implementation | M2-4 cosense-cli 差分 sync を実装
- `grasp sync <project-url>` を追加。`cosense listPages --sort updated` で最近更新ページ metadata を inspect し、store の `pages.updated` と比較して changed page だけ `cosense readPage` → SQLite upsert → `wanted` 再 materialize。`--dry-run`, `--limit`, `--batch-size`, `--cosense-command` 対応。
- humanized `updated` は suffix 前の ISO8601 を epoch seconds に変換。pinned page は停止条件から除外。hosted line id は採用せず `page.id:line-index` を維持。
- 検証: fake client unit test で changed page upsert / old edge 削除 / new wanted を確認。実 `cosense` dry-run/no-op smoke: `sync https://scrapbox.io/nishio/ --limit 5` は changed 0 / updated 0。

## [2026-06-23 18:15] implementation | M2-3 parser false-positive `[** x]` 系を修正
- `is_internal_cosense_link` の decoration 判定を「先頭の連続する `*` / `-` / `_` 群 + 空白」に拡張。`[* x]` だけでなく `[** x]`, `[*** x]`, `[-- x]`, `[__ x]` を link としない。
- 実データ再 import: 120693 edges / 41750 wanted。`backlinks '** 深い思考'` は none になり、wanted 上位から消えた。
- 検証: `python3 -m unittest discover -s tests` OK。

## [2026-06-23 18:14] implementation | M2-2 行レベル本文検索 `search` を追加
- `grasp search <query>` を追加。SQLite `lines.text LIKE` で本文行を検索し、`source_page_id/title/views/updated`, `line_id`, `line_index`, `line_text` を返す。text output は backlinks と同じ行リスト形式、`--json` 対応。
- ranking は SPEC 通り暫定: page.views → updated → title → line_index。`suggest` は title 補完として維持。
- 検証: `python3 -m unittest discover -s tests` OK。実データ `search 盲点 --limit 5` は約 0.7 秒で行レベル hits を返した。

## [2026-06-23 18:12] implementation | M2-1 SQLite on-disk store を実装
- `grasp import --force` と `--store` / `--rebuild-store` を追加。default store は `.grasp/grasp.sqlite`（gitignored）。通常 command は store が存在すれば `raw/nishio.json` を再 parse しない。
- SQLite schema: `metadata`, `pages`, `lines`, `edges`, `wanted`。`wanted` は import 時に materialize（毎回 group-by しない）。`Page.line_count` は SQLite row 由来の `stored_line_count` を持てるようにした。
- 実データ検証: import 約 8 秒、store 利用時 `read 盲点カード` 約 0.7 秒、`wanted --limit 3` 約 0.7 秒、`backlinks 盲点` 約 0.4 秒。`python3 -m unittest discover -s tests` OK。

## [2026-06-23 17:58] decision | 保存=SQLite ＋ 最新化=cosense-cli 差分更新（next SPEC 改訂）
- nishio 判断2点: ① 渡された JSON を JSON のまま保存し続ける必要はない → on-disk store は **SQLite もしくはより良い構造**。② 最新化は export 反復でなく、**初回 export を seed にし以降 cosense-cli で最近更新ページだけ取得して差分 upsert**。
- [[persistence-custom-format]] に Update 追記（on-disk か in-memory かの Open Q を SQLite で解決、store は upsert 可能に）。新 decision [[incremental-sync]] を作成（`cosense listPages --sort updated` を delta cursor にする grounded メカニズム ＋ humanize timestamp / 削除検出 / line-id の Open Q）。
- [[cosense-cli]] の役割を「比較対象・MVP では非依存」から「**post-MVP の freshness 経路**」へ更新。旧 `SPEC.md` を改訂: M2-1 を on-disk store(SQLite, upsert 可能)に、M2-4「cosense-cli 差分更新」を追加、import adapter を bulk seed＋incremental delta の2モードに、スコープ外から「差分 index 更新」を除外。

## [2026-06-23 17:49] file back | grasp×cosense-cli 実測比較 ＋ Codex 向け次マイルストーン SPEC
- MVP 実装を同一ページ（`君主道徳と奴隷道徳`）で `cosense`（hosted, 認証済み）と同条件比較。一次データを [[cosense-cli]] に「## 実測比較」として固定。
- **速度**: grasp は全コマンド一律 ~3.4s（123MB JSON full parse が律速、cosense は 0.5–1.2s）。**機能**: grasp だけが行レベル逆リンク・赤リンク列挙・1 コール近傍同梱・オフラインを出す。cosense だけが本文/ベクトル検索・生きた状態を出す（`盲点` 検索 grasp 8 vs cosense 100）。中核仮説は成立、弱点は既知の MVP 割り切り。
- parser 残 false-positive を実測: `[** x]` 系装飾（`** 深い思考` count 59）が link 扱い → [[grasp-cli-mvp]] と旧 `SPEC.md` Open Q に記録。
- 旧 `SPEC.md` に「## 次のマイルストーン（post-MVP / step 2）」を追加: M2-1 on-disk index（latency 解消・native store seed, 最優先）/ M2-2 `search`（本文検索）/ M2-3 parser 修正。read-only 維持、write/identity はまだ。リリース（README/push）は人間判断待ちで保留。

## [2026-06-23 17:34] rename | decision ページ why-design-B → why-not-scrapbox-clone
- 「design B」は A/B fork を覚えていないと意味が通らない相対ラベルで、リンク identity / H1 として決定の中身を隠していた（nishio 指摘「タイトルが微妙」）。
- `git mv` で `decisions/why-design-B.md` → `decisions/why-not-scrapbox-clone.md`。H1 を「Scrapbox を忠実 clone せず、identity-without-name を足した『あるべき姿』を作る」に。内部呼称としての design B は本文に注記して残す（A vs B fork の論理は維持）。
- 参照を更新: CLAUDE.md / AGENTS.md / index.md / SPEC.md / persistence-custom-format.md の `[[why-design-B]]` リンク、log.md は履歴 prose を残しリンクのみ追従、cosense-json-export.md は prose の「design B」→「grasp」。

## [2026-06-23 17:33] file-back | MVP 実装知見を entity 化し、cosense-cli 可視性を記録
- 新ページ [[grasp-cli-mvp]]: `python3 -m grasp` の read-only verbs、in-memory data model、line-id 方針、wanted ranking、strict parser、実データ scale、検証、次課題を実装現状として固定。
- 新ページ [[cosense-cli]]: local 環境では `@helpfeel/cosense-cli@1.4.4` が `cosense` binary として利用可能。grasp は local export/native store、cosense-cli は hosted Cosense 操作という使い分けを記録。
- [[cosense-json-export]] 更新: broad bracket 分類値と strict parser 実装値（123170 edges / 58944 targets / 43344 wanted）を区別。lines[0] は MVP では本文に残すと確定。

## [2026-06-23 17:28] implementation | read-only Cosense JSON MVP CLI を追加
- Python package `grasp` を追加。`python3 -m grasp` / console script `grasp` で、`--export`（default: `$GRASP_EXPORT` or `raw/nishio.json`）と `--json` を受ける。
- 実装した read-only verbs: `read`（本文 + line-level backlinks + deterministic 2-hop related + page-local wanted）, `backlinks`, `wanted`; helper として `related`, `peek`, `suggest` も追加。line-id は `page.id:line-index`。Cosense title 行 `lines[0]` は本文に残す。
- Cosense parser は broad bracket 分類から厳しめに調整: 外部 URL / icon/img / decoration / math / cross-project / `[[...]]` に加え、inline backtick 内、ASCII index 風 `xs[i]` / `func()[0]`、数字のみ `[1]` を link から除外。理由: 実データで code/list 由来の `0` / `i` / `1` が `wanted` 上位を汚したため。
- strict parser で `raw/nishio.json`: 25791 pages / 724981 lines / 123170 edges / 58944 distinct targets / 43344 wanted / normalized title collision 1。以前の 133022 edges / 61613 targets / 45703 wanted は broad bracket 分類の値として残す。
- 検証: `python3 -m unittest discover -s tests` OK。実データで `wanted`, `backlinks 盲点`, `read 盲点カード`, `related 盲点カード`, JSON output を確認。毎回 118MB JSON を parse するため 1 command 約4-5秒、on-disk store は次段階の性能課題。

## [2026-06-23 16:45] ingest | Cosense JSON export の実物（raw/nishio.json, 25791 pages）を確認、import スキーマを確定
- nishio が管理画面 Export Pages（metadata ON）で出した実物を raw/ に配置 → 実スキーマを実測。SPEC が「Codex が実物で確認」と保留していた項目を確定。
- 新ページ [[cosense-json-export]]（entities/）: root/page/line スキーマ ＋ 6 gotcha。確定事項: ① **line に安定 id 無し**（138220 行で 0）→ grasp が import 時採番（原理4 と整合）。② **link graph は export に未保存**（page キーは title/id/created/updated/views/lines のみ）→ line.text を parse してエッジ materialize。③ `[...]` は overloaded（内部リンク 62.7% / 外部URL 23.4% / icon 6.7% / 装飾 3.6% / cross-project 2.8% / 数式 0.7%）、`[[...]]` は **bold でリンクでない**（grasp の `[[wikilink]]` と逆）。④ リンク解決は normalize（case-insensitive＋空白畳込, 実測 exact→normalize で 208 件だけ解決, title 衝突 1 group）。⑤ title=lines[0].text（≈99.7%）。⑥ users 2人（nishio＋garbot bot, line.userId あり）→ 単一所有前提に注釈。
- scale: 25791 pages / 724981 lines / 118MB。内部リンク instance 133022・distinct target 61613・既存解決 15702・**red link 45703** → `wanted` は ranking 必須（SPEC Open Q 確定。signal: 出現回数/views/recency）。
- 旧 `SPEC.md` 更新: line 40 の保留注記を確定事実＋[[cosense-json-export]] 参照に置換、MVP に実データ scale を追記、Open Q「read の近傍境界」に wanted ranking 必須を追記。

## [2026-06-23 15:56] decision | 保存形式 = 独自フォーマット（Markdown でない）、import は別責務、MVP = Cosense JSON export を読む
- nishio 訂正2点: ①保存形式は独自であるべき — Markdown が逆リンクメンテのしがらみの**発生源**（リンク=テキスト、逆リンクは未保存→全文スキャン or 書き戻し。独自なら逆リンク=エッジの逆読みで「維持」概念が消える）②「読める」は import の話で保存形式と独立。
- 新 decision [[persistence-custom-format]]: native=独自（Cosense の行/グラフモデルを正規化、ゼロ発明でない）。三層分離 native store ← import adapter（Cosense JSON / 後で Markdown）← CLI。「既存森40+を読める」は Markdown adapter で達成（native を Markdown にしない）。
- 旧 `SPEC.md` 更新: 保存形式/入力(import)/MVP 節を追加、データモデルを「エッジを native 保持」に、Open Q の永続化を解決済みに。MVP = Cosense JSON export 1ファイルを `read`/`backlinks`/`wanted` の読み取り専用3動詞で扱い、中核仮説を実データで検証。
- Codex への確認事項: Cosense export の実スキーマ（line-id 有無、リンク `[title]` 構文）。

## [2026-06-23 15:41] 作成 + 設計対話 ingest | grasp dev wiki を新規 scaffold し、llm-wiki での設計対話を founding pages に固定
- **由来**: nishio の llm-wiki 対話。「Cosense は複数人前提だが一人でも Markdown 集合より効く。"Co-" になる前の Scrapbox を CLI で扱える substrate が LLM に良い」→ design B を選択。
- **分業**: 本 wiki ＝ spec / 設計判断 / gotcha（Codex が読む context）、Codex ＝ 実装。
- **固定した founding pages**:
  - 旧 `SPEC.md` — CLI 動詞（read=近傍同梱 / backlinks=行つき / related=2-hop / wanted=赤リンク / write=グラフ自動更新 / transclude / rename=identity保持）＋ data model（page id / line-id / materialized backlinks）＋ 5 中核原理 ＋ Open Q。
  - [[why-not-scrapbox-clone]]（decisions/, 旧 why-design-B）— Scrapbox を Co-層 / グラフモデル層に分解、A（忠実clone, name=identity欠陥相続）vs B（あるべき姿, identity-without-name 追加）の fork で B 採用。用途は（あ）LLM-author 向け・人間UIなし。cosense-cli との区別。
- **次**: 永続化形式（既存 Markdown 互換 or 独自）の決定 → Codex に最小プロトタイプ（read / backlinks / wanted の 3 動詞、読み取り専用）を渡す。
- メタ: 親 llm-wiki の `LLM Wiki 設計のトレードオフ` 軸5（機械 vs 意味）× `名前ではなくIDで識別する設計`（identity-without-name）の収束として本プロジェクトが立った。
