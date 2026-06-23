# Log

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
