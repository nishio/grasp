# Log

## [2026-06-25 00:08] file back | cross-project 接続に強弱（strong/weak）軸を追加（v6 決定の境界2点を解決）
- nishio が cross-project 統合の残る境界2点を決定: ①別 project に materialized X があれば、他 project の bare 赤 `[X]` はそれに解決する（「自 project だけでは得られない content を他から発見できる」）②赤ベースの接続は**弱い接続=AI 向けヒント**、人間が書いた明示リンクは**強い接続**。
- [[whole-store-graph-and-cross-project-edges]] に **point 8（接続強弱）** を追加。strong=authored（intra `[X]` / explicit `[/P/T]`）、weak=grasp が normalize title の cross-project 一致で推論。赤-materialized 解決も weak。**誤接続（同綴り別概念）は weak 層に閉じる**ので authored グラフを汚さない＝strength が point 7 の誤接続リスクの封じ込め機構。`edges.connection_strength` を schema に追加、retrieval は strength を label し weak を下に rank。`link_kind` や typed/directional 軸とは直交。
- 旧 Open Q の「赤-materialized 境界」「explicit `[/P/T]` 整合」は point 8 で解決。残るは weak の rank/閾値・誤接続頻度 dogfood・表記ゆれ吸収（[[scrapbubble]]）。backlog v6 spec・index 行も更新。
- PR #2 の merge で判明した運用 gotcha を AGENTS.md に追記。`gh` が無く HTTPS push もできない環境では、GitHub connector で PR merge 自体は成功する一方、local main 側に手元の別 merge commit / follow-up commit が残り、`origin/main` と `ahead/behind` に分岐しうる。
- 対応方針: connector merge 後は `git fetch origin main` → `git log --left-right --cherry-pick origin/main...main` で remote merge commit と local commit を照合する。重複 merge commit をそのまま push せず、必要なら remote merge commit を取り込んで follow-up だけを rebase/cherry-pick する。

## [2026-06-24 23:56] file back | 開発弧の非対称を「行動に移した」と概念へ追補 + 並行 main commit の運用 gotcha
- この session の未捕捉知見を file back。
- [[development-arc-retrieval-ahead-of-authoring]] に `## Updates` 追補: §3 の非対称（retrieval≫authoring）は観察で終わらず同じ弧の中で着手判断に変わった（write 層に alpha 着手 [[write-layer-alpha-and-replay-test]]）。nishio の問い「ローカルキャッシュの改良ばかりで書き込みが進まない／今後どうなるか」が持続メカニズムをあぶり出した＝retrieval は tight dogfood loop（hub 観察→同日 ship）を持つが write は各 session に重い open question しか出さないので後回しは構造的（default で retrieval が勝つ）、崩すには意図的決定が要る。決定は §3 Open Q（authoring で dogfood 駆動が効かないリスク）に replay test（authoring 専用 loop）＋cadence A（big-bang 回避）で直接答える。
- AGENTS.md 運用方針に gotcha 追記: 並行 session が同じ main を同時 commit すると `git add` 後に index がクリアされ HEAD が動く（実例: 本 session の versioning commit が一度空振り）。共有 main への commit は確定した自分のファイルだけ単一コマンドで atomic に add+commit し着地を検証、他 session の hunk は staging に混ぜない。


## [2026-06-24 23:46] file back | cross-project を first-class edge に / whole-store retrieval / 赤リンク統合（v6 決定）
- cross-project-refs を「v5 互換・parse-on-read」で足す方針を nishio が却下（「互換性を捨ててどうあるのが理想か。grasp はまだ SSoT が外にある検索 index に過ぎず破壊を恐れる必要はない」）。互換性を捨てた理想形を v6 decision 化。
- 新規 [[whole-store-graph-and-cross-project-edges]]（decisions/）: ①store=再生成可能 projection ゆえ schema 自由→v6 bump ②discover-broad-filter-post-hoc（pre-filter せず label 付きで surface、絞りは post-hoc、性能は bound で対処し hide しない）③`[/P/T]` を import 時に first-class edge へ materialize ④retrieval は whole-store default・`--project` は絞り込み・結果は project ラベル付き（merge せず labeling で誤読回避）⑤node 状態=page 単位の materialized/referenced-only、project=namespace、acquire=materialize ⑥read 多義は全候補返す ⑦**同名 bare 赤リンクを normalize title で project 横断統合**（nishio 判断、自信は低いが Cosense にない概念ハブ value を採る、tentative）。
- [[multi-project-store]] の2 clause（「cross link 作らない」「retrieval は selected project 内だけ」）を supersede。先行 tentative Update（villagepump 由来、赤リンク統合提案）は ⑦で収束、resolved page 分離 vs labeling は v6 が labeling を採用。
- backlog に v6 実装 spec 節、index に decision 行。lint: 孤立0/broken0/未登録0。実装は [[history]] の `x` bump（再 import 要）。残る境界 Q は decision の Open Questions。
- 「takker の経験から何が言えるか」の分析を distill して既存ページに追補（新規ページなし）。
- [[takker-opencode-villagepump-test-2026-06-24]] 含意を強い順に再構成: ①grasp はモデル水準を下げる（構造化出力を CLI が作り agent は薄い recipe→安いモデルで完走、[[delivery-cli-plus-skill]] 境界の正しさ）②意図した retrieval loop が外部 agent で自然発生（AI consumer option が理由を知らない agent に選ばれた）③scale 余裕は read のみ証明・path/gather 未証明 ④takker が向けたのは Co- corpus＝read には問題ないが write/identity の単一所有前提（[[write-layer-alpha-and-replay-test]]）と将来衝突する伏線 ⑤インサイダーは「offline cosense-cli」= Scrapbox/persona1 枠に入れる→persona2 framing 未検証。
- [[positioning-two-personas]] `## Updates` 追記: インサイダーは Scrapbox 枠 / モデル水準を下げる（persona2 GTM 追い風）/ 公開 dogfooding flywheel は高利回りだが persona1 止まり（PR #2 がその実例、別チャネルが要る）。
- [[grasp-backlog]] Parser fidelity の PR #2 一般化を原理化: admin metadata-ON export は in-the-wild の代表でない→外部 export は fuzz test→import 堅牢性は恒常コスト＝persona2 を狙う代償。tolerant import + 実 export variant を fixture 化。
- 並行で Codex が PR #2 merge（1.5.24）・v6 decision [[whole-store-graph-and-cross-project-edges]] を追加済み。takker entity の PR #2 status は merged に揃っている。自分の hunk だけ commit。

## [2026-06-24 23:29] implementation | PR #2 を mergeし Cosense string line import を許容
- GitHub PR #2（takker99 `fix/string-lines-cosense-import`, `f139c516`）を review し、ローカル main に merge。`grasp/cosense.py` は Cosense JSON export の line が plain string の場合、metadata なし本文行（created/updated/user_id = `None`）として import する。string line 内の `[B]` なども通常通り edge 抽出対象。
- 回帰テスト `tests/test_cosense.py::CosenseStoreTests.test_store_imports_plain_string_lines_without_metadata` を追加。`python3` が system 3.9 だと既存 `requires-python >=3.10` / union type 構文で失敗するため、検証は Codex bundled Python 3.12 を使用。
- public compatibility version を `1.5.24` に bump。store schema は v5 のまま。[[grasp-v1-implemented]] / [[history]] / [[cosense-json-export]] / [[grasp-backlog]] / [[takker-opencode-villagepump-test-2026-06-24]] / README に反映。

## [2026-06-24 23:28] decision | write line の versioning を合意 — メジャー 2 = authoring line / alpha は SLA ラベル / cadence A
- nishio の問い「write系完了まで worktree で並行開発 → merge の段階で 2.x.y にする感じ?」を起点に合意形成。3点を file back。
- ①メジャー `2` = 「grasp が write/authoring line を持つ」。read-only(`1`)→read+write は本プロジェクト最大の概念変化（[[development-arc-retrieval-ahead-of-authoring]]）なので store-compat 台帳のメジャーで標す。②alpha/stable は version 番号に載せず、write 系 verb の SLA ラベルで表す（決定1の read=stable/write=alpha 別 SLA をそのまま使う）→ `2.0.0` は alpha ラベル付き write verb が載る最初の line。③cadence A: worktree 並行は最高リスクスライス（① stable identity ② rename）が replay test を通るまで、そこで merge して `2.0.0` 境界、以降 `2.x.y`。big-bang merge を避ける（authoring が tight dogfood loop を失う罠を回避、決定1 で隔離の安全上の必要も消えた）。
- [[write-layer-alpha-and-replay-test]] に Updates 追記＋ Open Q #4 を解決、[[history]] の Versioning policy に「major=product line / alpha=SLA ラベル / 2.0.0 境界」を追記。
- worktree `feat/write-identity-alpha` を main に fast-forward して Codex の context を最新化。


## [2026-06-24 23:21] ingest | Scrapbox `villagepump/grasp` の公開設計対話 + takker 外部試用ログを取り込み
- 出典: https://scrapbox.io/villagepump/grasp （raw/grasp-villagepump-page_2026-06-24.txt に保存, gitignored）。既出と重複しない新規分のみ file back。
- 新ページ [[takker-opencode-villagepump-test-2026-06-24]]（entities/）: **nishio 以外の第三者による初の実走**。takker が OpenCode + Deepseek v4 flash で bare 指示「このリポジトリを設定して」から self-setup → `villagepump.json`（43,742 pages / 1,454,430 lines / 413,605 edges / 171,316 unresolved ≈ nishio store の pages 1.7x・lines 2x）を import → グラフ理論 / リンク構造 / カテゴリ論争の多ターン retrieval を完走。確認3点: persona1 が nishio 固有でなく一般化 / cross-agent（OpenCode）・cross-model（Deepseek）portability / scale headroom。観測の主役は答えでなく `suggest→search(--context/--scope)→read(--related-snippets/--backlinks-limit)→related 辿り` のツール列＝read=近傍同梱 loop の実走証跡（nishio メタ観察「答えより LLM がどう使うかが重要」）。
- [[grasp-backlog]] Parser fidelity に PR #2 を記録: villagepump export の一部 line が dict でなく plain string（metadata なし）で importer が落ちた。takker 側 agent が修正し https://github.com/nishio/grasp/pull/2 （takker99, `fix/string-lines-cosense-import`）として提出 → **2026-06-24 時点 OPEN（未 merge）**。review/merge 後 [[grasp-v1-implemented]] import facts に反映。
- [[multi-project-store]] に `## Updates` 追記（tentative）: nishio 判断「異なる project の赤リンク（unresolved target）は接続する」。resolved page graph の namespace 分離（本 decision の核）は維持し、本文を持たない unresolved target に限って cross-project 接続を許す非対称。明示的に撤回ありの暫定方針。
- [[grasp-v1-implemented]] delivery に license=MIT を追記（LICENSE / pyproject、2026-06-24 追加。inajob の「土台にするので明記してほしい」要望対応、persona2 GTM 前提）。
- index.md entities/ に [[takker-opencode-villagepump-test-2026-06-24]] 1行追加。
- 既出につき再記録しないもの: 複数 project 対応 / Markdown folder import / read=近傍同梱 / gather・mentions・co-links / 25,792 pages count / parser の `#tag`・数字 link edge 化（すべて [[grasp-v1-implemented]] / [[grasp-backlog]] に既載）。

## [2026-06-24 23:09] decision | write/identity 層に着手 — alpha testing 位置づけ・過去 wiki 編集 replay でテスト・最高リスク先行

- nishio 指示2点: ①「当面書き込み機能は alpha testing と位置付ける。信用してここに大事なものを預ける人は自己責任。テスト方法はこのリポジトリの過去の wiki 編集を grasp で同様にやれるかとする」②「実装順序は最もリスクが高いものの検証を先にすべき」。これを言語化して Codex が読む context に固定した。
- 新 decision [[write-layer-alpha-and-replay-test]]（decisions/）: ①位置づけ＝write は alpha、read(v1 stable)/write(alpha) を別 SLA、原典(Cosense export / Markdown mirror)は書き換えず local store に対して write し re-import 安全網を write 対象の外に残す。②テスト方法＝この repo 自身の git history（page 作成/rename/本文編集/リンク変更の実列、既に markdown mirror dogfood corpus）を ground truth に、連続 revision の diff を grasp write/rename で適用し「素朴 import との一致」＋「rename で `[[..]]` 参照不壊・redirect stub なし・参照文保存」を実データで検証（[[use-case-experiment-as-outcome-story]] の authoring 版）。③実装順序＝危険な順: stable identity + re-import diff（最高リスク, stable ID requires memory）→ rename → write → transclude/come-from。
- [[grasp-backlog]]「Local write and identity layer」冒頭に着手判断と decision 参照を追記、未実装リストを「楽な順でなく危険な順に読む」と明示。index に decision 行追加。
- 背景は [[development-arc-retrieval-ahead-of-authoring]]（retrieval≫authoring の非対称）。差別化核 identity-without-name（[[why-not-scrapbox-clone]] / [[positioning-two-personas]]）の write 半分を埋めにいく。
- 次: 本 wiki を main に固定後、`feat/write-identity-alpha` worktree を切り Codex が①から実装。判明した制約は file back。

## [2026-06-24 22:40] file back | 「MD 全読み vs grep vs grasp search」速度比較を実測 → 速度は非論点・token が論点
- nishio の問い「大規模 MD を読むのと grep の速度比較」を本番コーパス（store project `nishio`, 25,798 pages）で実測。全行を flat MD（53.2MB ≈ 14M token, `/tmp/nishio_flat.md`）に dump し、cat / `grep -n` / `python3 -m grasp search` を `/usr/bin/time` で計測。
- 結論が反転: ①ディスク wall-clock は3手法とも sub-second（cat 0.02s / grep 0.3s / grasp 0.25–0.75s）で**論点でない**。効くのは context に入る token 量で、MD 全読みは ~14M token = 1M window の14倍で**そもそも入らない**。②grep vs grasp は速度でなく出力規律の差（grep 無制限: `民主主義` 1 クエリ 498KB≈125K token / grasp bounded 7–14KB）。③∴ grasp の対 grep 優位は「速さ」では立証できず「同等 wall-clock で bounded・ranked・structured」が立つ。
- 新ページ [[read-vs-grep-benchmark-2026-06-24]]（entities/, 日付つき実測 dogfood ジャンル）。[[ai-consumer-cost-and-trust]] に `## Updates` で軸1（round-trip/token 経済）の実測裏付けとして反映。index.md entities/ に1行追加。caveat: token は bytes/4 概算（日本語は実際もっと多く「全読み不可」は強まる向き）/ grasp は cold start 込み（[[language-and-distribution]] warm 値参照）。

## [2026-06-24 22:10] file back | 開発弧の自己観察を concept 化（retrieval 厚く authoring 未着手）
- 親 llm-wiki での「最近の grasp 開発を観察して考察」session の成果を grasp 側へ file back。新ページ [[development-arc-retrieval-ahead-of-authoring]]（concepts/）。
- 主張3点: ①2日 87 commits の速度は「層を分けて束ねを解く」単一原理の再適用ゆえ（[[why-not-scrapbox-clone]]/[[come-from-declared-gather]]/[[cosense-delite-howm-synthesis]]/[[delivery-cli-plus-skill]] が同じ手）。②[[history]] の x/y store-compat 規律は本番 dogfooding の帰結（parser 変更=「意味が違う」になる）。③retrieval は厚いが差別化核の authoring（id-link write / come-from declare・render）は全部 [[grasp-backlog]] 未着手＝次の山。
- index.md concepts/ に1行追加。親側 file back は llm-wiki `analyses/graspは親llm-wikiの理論が数時間でコードになる-20260624`（親子の数時間ループ観点はあちら）。
- 既存ページとの非重複: [[cosense-delite-howm-synthesis]] は製品組成、本ページは開発弧。current facts は [[grasp-v1-implemented]] / [[grasp-backlog]] を参照（重複させない）。

## [2026-06-24 21:58] implementation | acquire の取得条件・日時範囲記録と未更新ページ reuse を追加
- `grasp acquire` が acquisition criteria fingerprint / candidate updated range / page manifest を store metadata に保存するようにした。同じ criteria で再実行した時、hosted metadata の `updated` と前回 manifest / local page が一致するページは `readPage` せず local store から再利用する。
- JSON/text に `remote_fetched` / `reused` / `same_criteria_as_previous` を追加し、`stats` の Acquisition 節でも criteria fingerprint と updated range を確認できるようにした。updated metadata が無い search/seed 由来候補は stale 回避のため従来通り読む。
- 検証: `python3 -m unittest tests/test_cosense_cli.py` OK。

## [2026-06-24 21:58] lint | wiki lint clean
- `python3 scripts/lint_wiki.py` を実行。broken wikilink / 未登録 / frontmatter 不備はいずれも 0。

## [2026-06-24 21:49] implementation | cross-project-acquire の取得後 summary を拡張
- `cross-project-acquire` の successful project row に `reciprocal_refs` と `top_internal_links` を追加。取得した `<project>:semantic` slice 内で source project へ戻る `[/source/...]` refs と、partial corpus 内の上位 internal link targets を bounded に返す。
- `SQLiteStore.cross_project_refs_to()` と `SQLiteStore.top_internal_links()` を追加。どちらも既存 lines/edges を読む summary primitive で、store schema は v5 のまま。
- public compatibility version は `1.5.22`。README / Skill / current facts / backlog / cross-project dogfood entity / outcome-story concept を更新した。

## [2026-06-24 21:26] implementation | cross-project-acquire を追加
- `cross-project-acquire` command を追加。選択中 source project の `cross-project-refs --semantic-only` 相当の seed titles から、複数 target project を `<project>:semantic` namespace に順次 partial acquire する。
- `--dry-run` で plan のみ確認可能。実行結果は target project ごとの status / fetched / failed / skipped_nonpersistent / diagnostic / page_sample / failed_page_sample を bounded summary として返し、full acquire payload は返さない。
- public compatibility version は `1.5.21`。store schema は v5 のまま。README / Skill / current facts / backlog / cross-project dogfood entity / outcome-story concept を更新した。

## [2026-06-24 20:47] implementation | acquire fetch failure diagnostics を追加
- `acquire` の page fetch failure に `failed_pages[].error_class` を追加し、全 candidate fetch 失敗時は `diagnostic.type=all_failed` / `severity=warning` / `next_actions[]` を返すようにした。`cosense` symlink は存在するが shebang の `env node` が失敗する case は `command-env` に分類する。
- text output でも Diagnostic 節を出し、空の partial corpus を成功結果として誤読しにくくした。exit code は partial acquisition report として従来通り 0。
- public compatibility version は `1.5.20`。current facts / history / backlog / cross-project dogfood entity / README / Skill を更新した。

## [2026-06-24 20:26] implementation | cross-project-refs seed preflight を追加
- `cross-project-refs` に seed preflight を追加。各 target project に semantic `seed_titles` / `seed_candidates` / `acquire_recipe` を返し、`--seed-dir <folder>` 指定時は project 別 seed file を書いて runnable `grasp --project <project>:semantic acquire <url> --seed-file <file> --limit N` command を出す。
- `--seed-limit` / `--project-url-base` / `--acquire-limit` を追加。通常の extraction は read-only のまま、seed file 書き込みは明示 option の時だけ。
- public compatibility version は `1.5.19`。current facts / history / backlog / cross-project dogfood entity / README / Skill を更新した。

## [2026-06-24 19:30] implementation | cross-project-refs を追加
- `cross-project-refs` command を追加。保存済み行テキストから Cosense shorthand `[/project/page]` を parsed link target として抽出し、semantic / icon / project-root / self-project に分類して target project ごとに rank する。既定では self-project refs を除外し、`--semantic-only` で `.icon` / project root / self-project を落とした acquisition seed 向け view を返す。
- 通常 internal edge parser / materialized graph は変えず、schema v5 compatible の extraction primitive として実装。`search "[/"` + one-off script の gap は解消し、残るのは seed-file generation / acquire preflight、cosense/node diagnostics、all-failed acquisition warning、direct public API fallback。
- public compatibility version は `1.5.18`。current facts は [[grasp-v1-implemented]]、残課題は [[grasp-backlog]] と [[cross-project-reference-acquire-2026-06-24]] に反映した。

## [2026-06-24 18:47] file back | icon-history report 化の観察
- `villagepump` `[nishio.icon]` raw 抽出を `nishio in villagepump: 公開共同日記から見る grasp 前史 30 scene` へ再構成した過程の学びを [[use-case-experiment-as-outcome-story]] に追記。
- 核: 抽出と report composition は別工程。CLI は raw dump でなく、icon hit kind 分類、年/月 counts、theme counts、代表候補、hosted line id / snippet 付き provenance を返し、agent/report layer がユーザ言語で bounded narrative artifact を書くのがよい。
- [[grasp-backlog]] に `use-case report composition（icon/person history）` を追加。仮 surface は `grasp report icon-history ...` だが、重要なのは command 名ではなく `slice acquisition -> hit classification -> representative candidate bundle -> agent-authored report` の標準 workflow。

## [2026-06-24 18:46] file back | `search` は parsed link classifier ではない
- `[/` cross-project 実験の follow-up として、現行 `grasp search` だけでは `.icon` refs を link target として除外できないことを記録。`search "[/ AND NOT .icon" --mode boolean --scope line` は line-level lexical workaround で、同じ行の semantic link まで落とし、root refs は残り、複数 target の分類もできない。
- [[cross-project-reference-acquire-2026-06-24]] に、target-aware extraction が必要という process observation を追記。[[grasp-backlog]] には `cross-project-refs` / `links --cross-project --classify-targets` 相当の parsed link extraction surface を候補化。
- 教訓: outcome が parsed links に依存する use-case では、text search を本命 surface として扱わず、検索→外部 script の gap を product gap として明示する。

## [2026-06-24 18:19] file back | ユースケース実験は outcome story として記録する
- nishio feedback「ユースケース実験はユーザがこういうことをしたらこうなります、という事例で、いい感じの結果になることが好ましい」を [[use-case-experiment-as-outcome-story]] に concept 化。
- 核: use-case dogfood は gotcha / 未実装発見だけでなく、ユーザの自然な依頼から有用で再利用可能な結果が得られるかを評価する。file back では outcome story、friction/backlog、quality judgement を分けて残す。
- `villagepump` 抽出は到達として成功だが、raw artifact 中心・broad `[nishio.icon]` literal 抽出のため outcome story としてはまだ弱い。author marker / mention / reaction icon list の分類、bounded summary、custom script 非依存の再現 surface が「いい感じ」にする次候補。
- 追記: [[cross-project-reference-acquire-2026-06-24]] は outcome story としては強い。`/nishio` の `[/project/page]` refs を seed bibliography として使い、semantic refs 上位 project を acquire して AI/Cosense/Plurality/熟議/人物辞書の周辺 map を作れる。ただし one-off script / `cosense` PATH wrapper は product gap。

## [2026-06-24 17:36] file back | `villagepump` 日記ページ抽出 dogfood
- public `https://scrapbox.io/villagepump/` の `YYYY/MM/DD` 日記ページ（2020-10-09..2026-06-24）2,079 pages から `[nishio.icon]` を含む block を抽出。結果は raw artifact として 1,481 hit pages / 6,488 paragraphs / 19,134 lines、failed 0。
- `grasp acquire` は `cosense` binary が PATH に無く使えなかった。一方 Scrapbox public API は `pages?sort=title` と page body API で読めた。`search/query?q=[nishio.icon]` は 100 件固定で `skip` が効かなかったため、網羅抽出は title list -> date filter -> page body fetch が必要。
- [[grasp-backlog]] の hosted acquisition 節へ、`cosense-cli` 依存なしの direct public API fallback を候補として追記。

## [2026-06-24 17:31] file back | `/nishio` cross-project refs acquire dogfood
- `/nishio` snapshot の `[/` shorthand を抽出し、other-project refs 4,141 mentions / 183 projects、`.icon` と root refs を除く semantic refs 2,222 mentions / 142 projects と実測した。
- semantic refs 上位 12 project から最大 20 page ずつ seed 取得し、task-local `/tmp/grasp-cross-project.sqlite` に 8 project / 140 pages を partial acquire。主クラスタは AI x Cosense / Plurality・熟議 / Cosense 設計哲学 / public project operation / MITOU 人物辞書。
- gotcha: raw `[/` は `.icon` refs が大きく混ざるため seed 生成前に semantic/icon/root 分類が必要。`cosense` symlink は存在しても PATH に `node` が無いと shebang で exit 127 になる。`grasp acquire` は全 seed failed でも exit 0 で partial result を返すため、agent-facing warning が欲しい。
- 記録: [[cross-project-reference-acquire-2026-06-24]]。残課題は [[grasp-backlog]] の hosted acquisition 節へ追記。

## [2026-06-24 16:27] implementation | co-links に slice/raw rank と target_relation を追加
- `co-links` に `--rank slice|raw` を追加。既定 `slice` は target title 自体が query を含む `query-containing-title` を後ろへ回し、独立した `slice-handle` を先に出す。`raw` は従来の line/page count order。
- 各 co-link item に `target_relation` / `target_relation_rank` を追加し、`gather` は `co_link_rank_mode: slice` を明示する。
- store schema は v5 のまま、public compatibility version は `1.5.17`。current facts は [[grasp-v1-implemented]]、KJ法 dogfood の残課題は [[grasp-backlog]] と [[kj-link-hub-audit-2026-06-24]] に整理した。
- 検証: `python3 -m unittest discover -s tests` OK（43 tests）、`python3 scripts/lint_wiki.py` OK、skill validator OK、`git diff --check` OK。

## [2026-06-24 16:08] file back | Cosense / デライト / howm を grasp と照らした3ツール合成論
- nishio 依頼で Cosense・デライト・howm の UX を列挙し grasp と照合した対話を file back。原理ページ [[cosense-delite-howm-synthesis]] を新規作成。
- 核: grasp は Scrapbox 一本の clone でなく、3ツールから**別々の核を1軸ずつ**抜いた合成。Cosense=グラフモデル / デライト=identity-without-name（知番）/ howm=「ページ＝投影」と come-from。3ツールの弱点は全部「本来別々の仕事を1つの仕掛けに束ねた」に帰着し、grasp の一貫した手は層分離で束ねを解く（Cosense は `[X]` に4仕事、デライトは意味を独自語彙に、howm は retrieval を人間の Emacs 操作に）。捨てたもの: 多人数協調編集 / 独自語彙 / 時間駆動リマインダ。
- backlog 反映（nishio 指摘）: デライトの**引き入れ**（多重所属）は「前景/後景」の向き付き包含が乗った **typed link**（親 llm-wiki `型付きリンク` の構造型）。"Local write and identity layer" に `### typed / directional link` 節を追加。felt-sense / come-from の2型に直交する「型を持たせるか」軸、向き×無向グラフの両立、著者宣言 vs AI 自動推定を論点に。
- 用語方針（nishio feedback）: ページは coding-agent 向け source of truth なので、内部 shorthand（"Co-" / "design A/B"）を裸で使わず、本ページでは「多人数リアルタイム協調編集」「Scrapbox に欠けている層を足したあるべき姿」と明示し、[[why-not-scrapbox-clone]] への pointer に留めた。
- 統合: concepts/ 新ページ + grasp-backlog.md 1節追記 + index.md concepts に1行 + come-from-declared-gather.md 関連に被リンク1本（新ページの孤立回避）。

## [2026-06-24 16:03] implementation | gather omitted rows と come-from 候補 score を追加
- `mentions` summary に `come_from_candidate` を追加。bare occurrence/page spread、unlinked-page、query shape から score / thresholds / signals / rationale を返す初期 heuristic。多義語や AI 作ページ判定は確定しない。
- `gather` に `returned_counts` / `total_counts` / `omitted_counts` / `row_count_basis` を追加。counts は mentions=bare mention lines、co_links=ranked co-link targets、backlinks=incoming link rows の row 単位で、token omitted count ではない。
- store schema は v5 のまま、public compatibility version は `1.5.16`。current facts は [[grasp-v1-implemented]]、残課題は [[grasp-backlog]] に整理した。
- 検証: `python3 -m unittest discover -s tests` OK（43 tests）、`python3 scripts/lint_wiki.py` OK、skill validator OK、`git diff --check` OK。

## [2026-06-24 14:57] file back | gather KJ法 dogfood の co-link ranking caveat
- `grasp gather KJ法 --budget 1500 --json` を `1.5.13` 系実装後の nishio store で dogfood した観測を [[kj-link-hub-audit-2026-06-24]] に追記。huge-hub banner、151 exact links / 144 pages、681 literal pages、519 bare pages、page status counts が出た。
- 重要な caveat: `mentions` summary は all literal lines 基準なので body-only audit の 490 bare pages とは別指標。default summary は 519 bare pages。
- `co-links` の上位は `KJ法 渾沌をして語らしめる` / `KJ法勉強会@ロフトワーク` など query-containing bibliographic / session / title pages が先に出た。raw fidelity としては正しいが、narrower use-slice handle を見たい時には broad query-containing title の分類・filter・weighting が必要。[[grasp-backlog]] に残課題として追記。

## [2026-06-24 12:56] implementation | mentions に unlinked filter を追加
- `mentions --unlinked` を追加。既定 bare-only は維持し、`--unlinked` では page に query-containing link target が無い `unlinked-page` の bare mention 行だけを返す。
- summary は従来通り全 literal hit の total / bare / linked occurrence と page status counts を保持し、`mentions[]` と `returned_lines` だけを filter 後の値にする。
- store schema は v5 のまま、public compatibility version は `1.5.15`。current facts は [[grasp-v1-implemented]]、backlog の `mentions --unlinked` surface gap は実装済みに移した。
- 検証: `python3 -m unittest discover -s tests` OK（43 tests）、`python3 scripts/lint_wiki.py` OK、skill validator OK。

## [2026-06-24 12:52] implementation | related snippet に edge mode を追加
- `read --related-snippets --related-snippet-mode edge` を追加。従来の先頭行 snippet（`lead`）は既定のまま維持し、`edge` では related/source item を導いたリンク行を中心に `snippet_lines[]` を返す。
- JSON では `snippet_mode` と `snippet_window` を返す。text 出力では edge mode の根拠 line-id と target を `snippet: edge ...` として表示する。
- store schema は v5 のまま、public compatibility version は `1.5.14`。current facts は [[grasp-v1-implemented]]、backlog の「該当行モード」は実装済みに移した。
- 検証: `python3 -m unittest discover -s tests` OK（43 tests）、`python3 scripts/lint_wiki.py` OK、skill validator OK。

## [2026-06-24 12:32] implementation | mentions / co-links / gather 初期 surface を追加
- `mentions <query>` を追加。literal query の occurrence を parsed internal-link span 内/外に分け、既定では bare mention 行だけ返す。summary は total / bare / linked occurrence、bare line/page、page status counts を返し、各行を `exact-link-page` / `query-link-page` / `unlinked-page` に分類する。`--include-linked` と `--context N` あり。
- `co-links <query>` を追加。query を含む行で同時に出る internal links を target ごとに rank し、link_count / line_count / source_page_count / examples を返す。exact query target は既定で除外し、`--include-self` で含められる。
- `gather <query>` 初期版を追加。link stats、bare mention summary、representative mentions、co-link slices、backlinks、次に実行する recipe を bounded bundle として返す。`--budget` は厳密 token packing ではなく row limit selector。huge hub では bulk-linking を避ける banner を返す。
- store schema は v5 のまま、public compatibility version は `1.5.13`。current facts は [[grasp-v1-implemented]]、残課題（正規化 index、AI default 裸 / come-from 昇格 scoring、厳密 token packing）は [[grasp-backlog]] に残した。

## [2026-06-24 03:55] file back | come-from（宣言された用語単位の gather）を設計に取り込み
- 親 llm-wiki の 2026-06-24 設計対話（link overloading → grasp-最適）から grasp に効く部分を取り込んだ。背景厚めの原理ページ [[come-from-declared-gather]] を新規作成。
- 核の言語化: リンクには4仕事（recall / attention / navigation / **読者ケア**）があり、Cosense は substrate が他チャネルを持たないため全部を1つの `[X]` に束ねる。これが [[kj-link-hub-audit-2026-06-24]] の exact 144 → bare 490 の根。原因は **per-occurrence 局所判断 × 双方向 → hub という大域帰結のレベルミスマッチ**（誰も hub を作ろうと決めていない、親切な個別 `[KJ法]` の副作用で創発）。
- come-from（howm 由来）は判断単位を出現→用語に上げ、判断と帰結を用語-大域で揃える。「この語は一般に伝わりにくい」の1判断で全出現が読者に親切。read 側は grasp `mentions`（＝nishio 2022 howm 考察「キーワードページ＝仮想出現一覧」）で既に体現、declare 層と render 層（Markdown mirror で裸出現を自動リンク化）が未実装。
- backlog 反映: (1) `gather` 節に hub 膨張の why（レベルミスマッチ）と come-from declare/render 候補、`mentions --unlinked` の3分類化（(a)意図的 / (b)gap / (c)**AI 作 default 裸**＝`🌀KJ法` 266occ は AI 作）＋ come-from 昇格候補（uncommon×頻度×一意）。(2) "Local write and identity layer" に **リンク2型を別 first-class object に**（felt-sense=行キー / come-from=用語キー）要件。安全域＝必要域（uncommon≈一意）。
- decision 反映: [[ai-consumer-cost-and-trust]] に `## Updates` で第3消費者軸（substrate を持たない公開人間読者。読者ケアは AI 2軸モデルの外。公開面を frozen にすると届かない。come-from-at-render が軽量機構。grasp scope 判断点は nishio）。
- 親 llm-wiki 側の対応ページ: `come-fromリンクは1宣言で全出現を親切にする` / `grasp最適設計はlinkからrecallを剥がす-20260624` / `KJ法リンクハブはリンク密度でなく用法分解で扱う-20260624`。
- 統合: concepts/ 新ページ + grasp-backlog.md 2節追記 + ai-consumer-cost-and-trust.md Updates + index.md concepts に1行 + kj-link-hub-audit へ相互リンク（"wrong direction" の why を come-from へ前方参照、監査ページの outgoing 0 を解消）。

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

## [2026-06-25 00:02] ingest | ScrapBubble (takker99) を entity 化、grasp の read 模型の「双子（別消費者）」として file back
- 出典: github.com/takker99/ScrapBubble（README: "Show n-hop link destination pages beyond projects" / TypeScript+Deno / Preact / ~45 releases, 最新 0.9.15）、scrapbox villagepump/ScrapBubble・takker/takker99%2FScrapBubble、関連 villagepump/複数のprojectを透過的に扱う・takker/ScrapBubbleのcache戦略。全文 raw は raw/scrapbubble--*.json（gitignored）。
- 新ページ [[scrapbubble]]（entities/）: Scrapbox UserScript。リンク hover で**遷移せず**飛び先を吹き出し表示（text-bubble=本文 / card-bubble=関連2-hop）、逆リンクへ再帰潜行、`whiteList` で複数 project 透過、赤リンクは接続検知で blue 切替（全 project 空は全走査要）、cache-first・最大3 fetch・api/projects 更新時刻チェック、`?followRename=true` で改名追従。
- 核となる読み: **ScrapBubble = grasp の read グラフ模型を消費者だけ替えて実装した双子**（ScrapBubble=人間ブラウザ hover GUI / grasp=AI CLI）。bubble=人間版の近傍同梱。grasp の whole-store cross-project（v6）/ read=近傍同梱（[[ai-consumer-cost-and-trust]] 軸1）/ [[incremental-sync]] cache reuse / identity-without-name を**別経路で裏付ける先行例**。
- 3つの sharpening: ① `followRename` = grasp が data model で直す name=identity 欠陥を fetch 時 workaround で当てた downstream 証拠（[[why-not-scrapbox-clone]] に Update）。② `whiteList` 透過は Co-（他者 project 読み）と非 Co-（自分 public+private 統合）を束ね、grasp が継ぐ cross-project は後者だけ → cross-project は Co- 無しでも価値（[[whole-store-graph-and-cross-project-edges]] に Update、本決定が使う `[/takker/ScrapBubble]` の出元）。③ daiiz の「リンク貼って満足／育てる vs preview」deferral は come-from・第3消費者軸に接続。
- index.md に entities/ 1行追加。why-not-scrapbox-clone と whole-store-graph に各1 Update 追記。

## [2026-06-25 00:40] file back | 森全体を grasp の次 dogfood corpus にする設計対話を backlog へ
- 出典: [[scrapbubble]] ingest から派生した nishio との設計対話（2026-06-25）。前提整理は本セッションの ScrapBubble entity と whole-store 決定の Update（cross-project の Co-/非 Co- 2層分解）。
- [[grasp-backlog]] の「grasp 自身の wiki を最初の dogfood corpus にする」に 2026-06-25 subsection を追加: corpus を grasp 1 wiki → **wiki森全体（40+ 単一所有者 wiki）**へ拡張。動機＝森は親 llm-wiki `wiki_search.py` の grep 横断止まり＝節点アクセス (a-1)、「N wiki を跨いで参照されるが本文が無い概念」＝俯瞰グラフ (a-2) は出せない。grasp の whole-store cross-project + Markdown mirror が (a-2) を供給。森は全部 nishio 所有＝Co- を削ぐ grasp の cross-project（非 Co- 横断）の理想 corpus。
- 核心: **森用の特別 edge policy は不要**（nishio「import 時バラバラ→query で徐々に有機結合」）。cross-wiki プレーン名参照は import 時に裸の赤 node のまま、[[whole-store-graph-and-cross-project-edges]] point 8 の弱い接続（normalize-title 一致）が query 時に繋ぐ。「束の束」は query 時結合を待つ正常な初期状態（親 llm-wiki `書いてから整理する` の森スケール版）、誤接続は weak 層に封じ込み。
- 論点: 40+ wiki の namespace import オーケストレーション / navigation・log artifact 森規模除外 / raw/ 除外（llm-wiki-about-nishio md 24,968 件）/ weak 接続の cross-wiki spread ranking。森メタ側は親 llm-wiki `wiki-forest-utilization-design-20260610` に file back。

## [2026-06-25 02:00] 整理 | grasp-backlog を「未実装項目だけ」に再構成（412→251行）
- 動機: 次の開発前に backlog を整理。旧 backlog は実装済みの作業ログ（read --around-line / search --context / mentions / co-links / gather / path / acquire 系など）と却下の経緯を本文に抱えて 412 行に膨らみ、未実装項目が埋もれていた。
- 方針（分業 + ページルールに沿う）: 実装済み narration は [[grasp-v1-implemented]]（current facts の SSoT）と本 [[log]]（*いつ* やったかの時系列）に既に二重記録されているので backlog からは消す。事実は失われない（v1-implemented に全 surface が載っていることを突き合わせ確認）。却下案（`--cluster` / `--strip-decoration`）は経緯を畳んで各節末「却下（再提案しない）」の理由つき1行ガードに。設計根拠は `decisions/` / `concepts/` 側にあり backlog はリンクのみ。
- 残したもの: 未実装項目（parser 監査 / Markdown mirror 残 / 森 dogfood 拡張 / navigation・log artifact handling / write・identity 層 / typed link / stable line identity / search recall 残 / gather・mentions・co-links 残課題 / use-case report / come-from declare・render / path・backlinks ranking / sync freshness / cross-project v6 / acquisition 残 / packaging）と、それらに効く settled な設計制約 + 出典リンク。
- 検証: `python3 scripts/lint_wiki.py`（broken link / orphan 増なし）/ `python3 -m unittest discover -s tests`。コード変更なし、wiki のみ。

## [2026-06-25 02:04] implementation | Markdown import の first H1 title resolution を実装
- `grasp import --markdown <folder>` の title resolution を frontmatter `title` → first H1 → file stem に変更。first H1 extractor は frontmatter と fenced code block 内の `# ...` を title とみなさない。file stem は従来通り alias として残るため、`[[file-stem]]` は canonical H1 title へ解決する。
- H1 title が変わると manifest の title / alias map が変わるので、既存の safe full rebuild path に乗る。SQLite table shape は変えないため schema は `5` のまま、public compatibility version は `1.5.25`。既存 Markdown store はそのまま読めるが、H1 title を反映するには `grasp import --markdown <folder>` の再実行が必要。
- file back: [[grasp-v1-implemented]] の Markdown facts を更新し、[[grasp-backlog]] から first H1 title resolution を削除。[[markdown-obsidian-indexed-mirror]] の Open Question から title resolution 問いを閉じ、[history](history.md) に `1.5.25` を追加。README も title resolution 説明を更新。
- 検証: bundled Python 3.12.13 で `python3 -m unittest tests.test_markdown` / `python3 -m unittest discover -s tests` / `python3 scripts/lint_wiki.py` / `git diff --check` OK。system `/usr/bin/python3` は 3.9.6 で package の `>=3.10` 要件を満たさず、既存 union type で失敗する。

## [2026-06-25 02:17] correction | `#1` noise は log 除外でなく edge annotation 問題
- nishio 指摘: grasp wiki dogfood で見えた `log.md` が graph を汚す問題と、`PR #2` / `Open Q #4` のような `#1` 系が hashtag edge になる問題は別。前者は page/file の artifact handling、後者は link-shaped expression が意味ある概念リンクかの annotation 問題。
- 方針修正: Scrapbox 互換では `#1` は link として成立するので parser で消さない。人間は必要なら `` `#1` `` のように escape してきた。grasp 側は edge を保持したまま、system / LLM / human が「表現としてはリンクだが意味リンクではない」と annotation し、`unresolved` / `related` / `path` ranking で弱く扱う。
- file back: [[grasp-backlog]] に link-shaped but non-semantic edge annotation 節を追加。[[markdown-obsidian-indexed-mirror]] に correction を追記し、log/navigation artifact handling と edge annotation を混同しないよう明記。

## [2026-06-25 02:39] implementation | issue-number hashtag edge の system annotation を追加
- `PR #2` / `Open Question #4` のような numeric hashtag edge に system `semantic_annotation` を付ける初期 heuristic を追加。annotation は `semantic_role=issue-number`, `graph_scope=non-semantic`, `annotator=system`。parser は edge を捨てず、`Edge.to_dict()` / path edge example / unresolved examples に annotation を出す。
- `unresolved` は既定で少し多めに候補を取得し、sampled examples がすべて non-semantic な target を ranking の後ろへ回す。`link_stats("2")` など raw edge count は保持する。永続 annotation table / LLM annotation workflow / `related`・`path` の本格 ranking policy は未実装として [[grasp-backlog]] に残す。
- dogfood: temp store で `wiki/` を import し、`PR #2` / `PR #1` / `Open Q #4` 由来 target に annotation が付くことを確認。`[[..]]` 由来の `..` は別の link-shaped non-semantic 表現として未対応。
- file back: [[grasp-v1-implemented]] に current facts、[history](history.md) に `1.5.26`、[[grasp-backlog]] に残課題を反映。
- 検証: bundled Python 3.12.13 で `python3 -m unittest discover -s tests` / `python3 scripts/lint_wiki.py` / `git diff --check` OK。

## [2026-06-25 02:44] implementation | Markdown navigation/log artifact の outgoing edges を content graph から除外
- `grasp import --markdown` が `index.md` / `forest-index.md` / `maps/` / `views/` / frontmatter `role: navigation` を navigation、`log.md` / `log/*.md` / frontmatter `type: log-entry` を log artifact と分類し、これらの outgoing edges を既定 content graph から除外するようにした。本文 lines は store に残るため `search` は従来通り hit する。
- Markdown manifest version を `2` に更新し、`graph_role` を manifest identity に含めた。既存 Markdown project は次回 re-import で safe full rebuild される。SQLite schema は v5 のまま、public compatibility version は `1.5.27`。
- dogfood: temp store で `wiki/` を import し、32 pages / 3831 lines / 365 edges / unresolved 5。前回の同条件 580 edges から log/index outgoing edges が落ち、`read grasp backlog` の backlinks から `Log` が消えた。一方で `search "first H1"` は `Log` に hit し、検索対象として残ることを確認。
- file back: [[grasp-v1-implemented]] / [history](history.md) / [[grasp-backlog]] / [[markdown-obsidian-indexed-mirror]] を更新。
- 検証: bundled Python 3.12.13 で `python3 -m unittest discover -s tests` / `python3 scripts/lint_wiki.py` / `git diff --check` OK。

## [2026-06-25 02:50] dogfood | Markdown LLM Wiki が grasp 経由で LLM context として使えるかを検証
- temp store に `wiki/` を `import --markdown wiki --project grasp-wiki` し、32 pages / 3836 lines / 365 edges / unresolved 5 として materialize できることを確認。
- `search "non-semantic" --context 2` は `Log` だけでなく [[grasp-backlog]] と [[markdown-obsidian-indexed-mirror]] の該当行を line_id + 周辺文脈つきで返した。`search "first H1"` は [[grasp-v1-implemented]] / [[grasp-backlog]] / decision / `Log` の実装履歴を拾い、Markdown に file back した current facts と履歴が CLI から再利用できることを確認。
- `read "grasp backlog" --related-snippets --related-snippet-mode edge` は本文・行レベル backlinks・2-hop related・page-local unresolved を同梱し、`backlinks "grasp backlog"` / `related "grasp backlog"` は `Log` に支配されず content pages を返した。`search` では `Log` が残るが、artifact outgoing edge 除外により graph 近傍の汚染は抑えられている。
- `unresolved` は `#2` / `#4` 系 target に system `semantic_annotation` を出し、`path "grasp backlog" "entity: grasp v1 implemented surface"` は根拠 line つき direct path を返した。現状の答え: **Markdown の LLM Wiki に書き込まれたものは、再 import 後、Cosense export と同じ `search` / `read` / `backlinks` / `related` / `path` primitives で LLM が使える**。未解決の差は hosted 最新性や write layer で、Markdown mirror 自体は read-only indexed graph として成立している。

## [2026-06-25 02:54] file back | Markdown mirror dogfood の結論を current facts / decision へ昇格
- 直前の dogfood 結論を [[markdown-obsidian-indexed-mirror]] と [[grasp-v1-implemented]] へ反映。log だけでなく、Markdown mirror の決定根拠と実装済み facts から「file back された Markdown LLM Wiki は再 import 後に LLM context として使える」と読めるようにした。

## [2026-06-25 02:59] implementation | Markdown import に heavy directory 除外を追加
- `grasp import --markdown <folder>` に `--markdown-exclude-dir <name>` を追加。指定した directory basename 配下の `.md` を再帰 import から除外する。森スケール dogfood で `raw/` の大量 source md を mirror に混ぜないための前提。
- Markdown manifest version を `3` に更新し、exclude dirs を manifest identity に含めた。exclude 条件を変えて同じ project を re-import した時は safe full rebuild する。SQLite schema は v5 のまま、public compatibility version は `1.5.28`。
- file back: [[grasp-v1-implemented]] / [history](history.md) / [[grasp-backlog]] / [[markdown-obsidian-indexed-mirror]] / README / Skill を更新。
- 検証: bundled Python 3.12.13 で `python3 -m unittest discover -s tests`（63 tests）/ `python3 scripts/lint_wiki.py` / `git diff --check` OK。temp store で `grasp --json --store <tmp> import --markdown wiki --project grasp-wiki --markdown-exclude-dir raw` も成功。

## [2026-06-25 03:10] dogfood | wiki森全 entries の Markdown import を temp store で検証
- `/Users/nishio/llm-wiki/wikis.yaml` の 42 entries を対象に、各 `<path>/wiki` を temp store へ `import --markdown --project <name> --markdown-exclude-dir raw` で投入。内容本文は読まず、件数・時間・失敗型だけ観測。
- 結果: 37 entries 成功 / 5 entries 失敗 / missing folder 0。成功分 aggregate は 37 projects / 2458 pages / 213,309 lines / 22,550 edges / 1,412 unresolved。合計 import wall time は約 22.3 秒。`stats` は schema v5 / schema_ok true。
- 失敗はすべて duplicate title / alias collision。典型は draft variants の同一 H1、複数 directory の `_overview` / `README` / `index` file stem alias、source/session file と canonical page の alias 衝突。次 blocker は raw 除外や performance でなく collision policy。
- file back: [[grasp-backlog]] の duplicate title / alias collision と wiki森 import orchestration、[[markdown-obsidian-indexed-mirror]] の dogfood section に反映。

## [2026-06-25 13:04] file back | wiki森 import dogfood を独立 analysis page に昇格し、次計画を整理
- 新ページ [[wiki-forest-markdown-import-dogfood-2026-06-25]] を作成。log/backlog/decision に散っていた dogfood 結果を、Result / Analysis / Plan / Open Questions として coding agent が読める source of truth にした。
- 新計画: collision diagnostics → alias collision softening → draft/source artifact 除外 → forest import orchestration。orchestration は 37/42 成功で価値ありだが、先に collision policy を入れないと失敗集計 command になる。
- repo-local Codex plugin `/next` 用の未コミット差分（AGENTS / `.agents/plugins/marketplace.json` / `plugins/grasp-next/`）もユーザ指示により commit 対象にする。

## [2026-06-25 13:31] implementation+file back | Markdown collision diagnostics と identity/name 計画修正
- Markdown mirror の duplicate title / id / alias collision を `MarkdownCollisionError` と structured diagnostic にした。`grasp --json import --markdown ...` は collision kind / normalized key / paths / entries を stderr JSON に出す。
- ユーザ指摘により、alias collision softening は単なる workaround ではなく `identity-without-name` の本体問題として扱う方針に修正。path は一意性の根拠として diagnostic / fallback handle に使えるが、path-qualified string を page name へ混ぜない。
- 次は alias collision policy（identity=path/id、name=display/link handle の表現）と `drafts/` / `source/` artifact 除外を検討し、`import-forest` orchestration は急がない。

## [2026-06-25 14:03] implementation+file back | ResourceWarning 修正と Markdown identity/name collision decision
- `tests/test_cli_help.py` の raw `sqlite3.connect` を明示 close に修正。Python sqlite3 の connection context manager は commit/rollback 用であり close しないため、ResourceWarning の原因になっていた。
- 新 decision [[markdown-identity-name-collision-policy]] を追加。duplicate title / alias は import UX ではなく、visible handle が複数 page identity に束縛される問題として扱う。path は source address / fallback selection key であり、page name へ混ぜない。
- 次の実装順は artifact reduction（`drafts/` / `source/` 除外または `graph_role=artifact`）→ schema v6 `page_handles` → ambiguous query result。`import-forest` は引き続き急がない。

## [2026-06-25 14:18] correction | `source/` digest は default exclude しない
- nishio 指摘: LLM Wiki の `source/` は `raw/` を読んで作成した digest / source-backed synthesis なので、`raw/` と同列に除外すべきではない。
- 修正方針: `raw/` は heavy original dump として除外候補、`drafts/` / generated temp は artifact reduction 候補。`source/` は保持し、必要なら `graph_role=source` / evidence layer / ranking policy で canonical synthesis と扱いを分ける。
- [[wiki-forest-markdown-import-dogfood-2026-06-25]] / [[grasp-backlog]] / [[markdown-identity-name-collision-policy]] / [[markdown-obsidian-indexed-mirror]] の `draft/source artifact 除外` 表現を修正。

## [2026-06-25 14:30] implementation+file back | Markdown source role と artifact role を実装
- Markdown import が `source/` / `sources/` / frontmatter `role/type: source` を `graph_role=source` と分類するようにした。`source` role は raw digest / source-backed synthesis なので、content と同じく outgoing edges を materialize する。
- `drafts/` / generated temp / frontmatter `role/type: artifact|draft|generated` は `graph_role=artifact` と分類し、search には残すが outgoing edges は除外する。これは duplicate title を許す実装ではなく、handle ambiguity は schema v6 `page_handles` の残件。
- public compatibility version を `1.5.29` に更新。SQLite schema と Markdown manifest version は不変。

## [2026-06-25 16:39] implementation+file back | schema v6 page_handles と read ambiguity を実装
- SQLite schema を v6 に更新し、`page_handles` table を追加。Cosense title と Markdown title / alias / source path / graph_role を page identity `(project,page_id)` とは別に materialize する。
- `read <handle>` は visible handle が複数 page identity に束縛される時、暗黙に片方を選ばず `ambiguity.type=handle_ambiguity` と候補 page_id / path / graph_role を返す。`read --page-id <id>` / `read --path <relative-path>` で identity を明示できる。
- Markdown folder import も import cache manifest に `source_type=markdown` / `exclude_dirs` 付きで保存し、schema mismatch recovery が Cosense JSON copy だけでなく Markdown mirror も再構築できるようにした。
- 残件: Markdown import は duplicate title / alias をまだ hard error にする。`backlinks` / `related` / `link-stats` / outgoing edge resolution も ambiguous handle を first-class に扱う段階は未実装。

## [2026-06-25 16:42] dogfood | schema v6 で wiki森 Markdown import smoke
- `/Users/nishio/llm-wiki/wikis.yaml` の 42 entries を対象に、temp store へ `import --markdown --project <name> --markdown-exclude-dir raw` を再実行。private 本文は出力せず aggregate / failure type のみ観測。
- 結果: 37 success / 5 failure / missing 0。成功 aggregate は schema v6 / schema_ok true / 37 projects / 2460 pages / 213,526 lines / 22,569 edges / 1,412 unresolved、wall time 約 25.8 秒。
- 失敗型は `markdown_collision` のまま（alias collision 4、alias+title collision 1）。v6 `page_handles` は成功 project の import を壊していないが、Markdown import softening は未実装なので 5件の blocker は残る。

## [2026-06-25 19:07] implementation+dogfood | schema v7 edge resolution と Markdown collision softening
- SQLite schema を v7 に更新し、`edges` に `target_handle` / `target_handle_norm` / `target_page_id` / `resolution_status` を追加。`page_handles` から `resolved_unique` / `ambiguous` / `unresolved` を materialize し、ambiguous handle を unresolved target や existing page backlink と誤分類しないようにした。
- Markdown duplicate title / alias は import 全体を止めず、`read <handle>` の ambiguity 候補として surface する。`link-stats <handle>` も ambiguity を返し、recovery hints へ誤分類しない。duplicate frontmatter `id` は identity 衝突なので hard error のまま。
- wiki森 smoke: `/Users/nishio/llm-wiki/wikis.yaml` 42 entries を temp store へ同条件で import し、42 success / 0 failure / missing 0。aggregate は schema v7 / schema_ok true / 42 projects / 3338 pages / 264,963 lines / 23,180 edges / 1,627 unresolved、wall time 約 22.1 秒。
- 検証: `python3 -m unittest discover -s tests`（68 tests）, `python3 -m compileall -q grasp`, `python3 scripts/lint_wiki.py`, `git diff --check` は通過。
- 残件: `backlinks <ambiguous handle>` の UX と JSON contract、forest import orchestration、whole-store cross-project edge との統合。
