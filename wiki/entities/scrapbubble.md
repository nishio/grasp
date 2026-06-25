---
type: entity
summary: ScrapBubble（takker99）は Scrapbox の UserScript で、リンクを hover すると遷移せずに飛び先ページを「吹き出し（bubble）」で表示し、関連ページリスト（2-hop）・逆リンクへ再帰的に潜れる。whiteList で複数 project を透過的に繋ぎ（自分の public+private、TamperMonkey 版は他者 project も）、空リンク（赤）は接続検知次第 blue に切替、cache-first・最大3 fetch・api/projects 更新時刻チェックで bounded、`?followRename=true` で改名追従する。**grasp の read 模型（近傍同梱・2-hop・逆リンク・赤リンク解決・cross-project）を、消費者だけ替えて AI-CLI でなく人間ブラウザ hover GUI として実装した双子**。同じ Scrapbox graph を「遷移せず近傍を見る」primitive にした並行先行例で、grasp の whole-store cross-project / read=近傍同梱（軸1）/ incremental-sync の cache reuse / identity-without-name を別経路で裏付ける。followRename は grasp が data model で直す name=identity 欠陥を fetch 時 workaround で当てた downstream 証拠。whiteList は grasp が削ぐ Co-（他者 project 読み）と非 Co-（自分の public+private）を束ねており、grasp の cross-project は後者だけ。
sources:
  - https://github.com/takker99/ScrapBubble （README: "Show n-hop link destination pages beyond projects" / MIT / TypeScript+Deno / Preact / ~45 releases, latest 0.9.15 2025-09）
  - https://scrapbox.io/villagepump/ScrapBubble （UserScript 紹介・使い方・リリースノート, raw/scrapbubble--villagepump-ScrapBubble.json）
  - https://scrapbox.io/takker/takker99%2FScrapBubble （実装メモ・設計・実装したいこと, raw/scrapbubble--takker-takker99-ScrapBubble.json）
  - https://scrapbox.io/villagepump/複数のprojectを透過的に扱う （cross-project 透過の動機と daiiz deferral 議論, raw/scrapbubble--villagepump-multi-project-transparent.json）
  - https://scrapbox.io/takker/ScrapBubbleのcache戦略 （cache-first / api/projects 更新時刻チェック / WebSocket realtime, raw/scrapbubble--takker-scrapbubble-cache.json）
  - 全文 raw は raw/scrapbubble--*.json（2026-06-24 公開 API 取得, gitignored）
---

# entity: ScrapBubble

`ScrapBubble`（takker99）は **Scrapbox（Cosense）の UserScript**。リンクを hover すると、そのページに**遷移せずに飛び先の中身を「吹き出し（bubble）」でその場に表示**する。「一つのページ上で全てのリンクをたどってページを閲覧することができる」「[タイトルから中身を推測できない]ページでも中身をさっと見ることができる」（villagepump 紹介ページ）。

このページは外部ツールの current facts と、それが **grasp の設計判断をどう裏付ける / 対比するか**を保持する（[[cosense-cli]] と同じく、比較対象として grasp 内に置く既存ツール）。grasp と ScrapBubble の関係を一言で言うと: **同じ Scrapbox の read グラフ模型を、消費者だけ替えて実装した双子**。ScrapBubble は人間がブラウザで hover する GUI、grasp は AI が CLI で読む surface。両者は独立に「**遷移せず近傍を見る**」という同じ primitive に収束している。

## 何をするツールか（facts）

- **配布形態**: Scrapbox UserScript。TypeScript + Deno でビルド、**Preact app を `Element.shadowRoot` に mount**（web components は使わない）。MIT。~45 releases、最新 0.9.15（2025-09）。scrapbox-bundler でコード生成 → 自分の project の code block に貼り → `script.js` で `mount()` する導入。「UserScript は上級者向け機能」と注意書きあり。
- **bubble は2種**:
  - **text-bubble**（`scrapbox-text-bubble`）= 飛び先ページの**本文**。コードブロック・テーブル・数式（KaTeX）・YouTube/location 記法も表示、テキスト選択可。
  - **card-bubble**（`scrapbox-card-bubble`）= **関連ページリスト（2-hop / 逆リンク）のカード**。
- **再帰的な潜行**: 吹き出した関連ページリストから更に別の bubble を出せる。「逆リンクの方向にどんどん潜っていける」。タイトル行を hover すると**逆リンク**を表示する。
- **複数 project を透過的に扱う**（`whiteList`）: `mount({ whiteList: [...] })` で指定 project のページを**同じ project であるかのように**繋ぐ。動機（villagepump `複数のprojectを透過的に扱う`）は「**private project に書いたことを public project から参照できる**／書き出しを公開・非公開で分けても、全て自分が考えたこととしてページを繋げられる ＝ 多分これが一番魅力的な機能」。TamperMonkey 版を使うと**他者の project** も繋げられ、「あるキーワードについて他者が書いたことと自分が書いたことを同時に閲覧できる」。
- **空リンク（赤リンク）解決**: 「**基本空リンク（赤リンク）にし、繋がりを検知し次第 blue（解決済み）に切り替える**」。`links2hops` で先回り prefetch。**edge case**: 「全ての project で空リンクなリンク」は、全 project からページデータを取得しないと空判定できない（＝赤判定が全 namespace 走査を要する）。
- **cache 戦略**（takker `ScrapBubbleのcache戦略`）: cache-first。`api/projects` で各 project の更新時刻をまとめて確認し、**更新が無い project はページを再 fetch しない**（更新されたページのうち cache にあるものだけ fetch）。**最大3本しか fetch を走らせない**設計なので「projects を増やしても fetch 総量が変わるだけで叩く頻度は変わらない」＝ project を足すコストが bounded。realtime は level1 時間 cache → level2 WebSocket 簡易更新 → level3 完全 stream の段階設計。
- **改名追従**: `?followRename=true`（「[タイトル変更を考慮してScrapboxのページデータを取得]する」）で、title が変わってもページデータを追える。
- **未実装 / やりたいこと**（takker `実装したいこと`）: **リンク同一判定のカスタム化**（例 `/villagepump/yyyy/MM/dd` を `yyyy-MM-dd` にマッチ＝実質「表記ゆれ吸収」）、**類似タイトルのページを関連ページとして表示**、編集機能（閲覧⇄編集 textarea ＋ `patch()` で送信）、card の並び替え（更新日時順 → Most related + project 順）、mobile の hover 代替操作（`attachHover()`）。

## grasp との対応（同じ模型・別消費者）

ScrapBubble の各機構は grasp の surface / 決定にほぼ1対1で対応する。**消費者が「人間 hover GUI」か「AI CLI」かが違うだけで、模型は同じ**:

| ScrapBubble（人間ブラウザ GUI） | grasp（AI CLI） | 共通原理 |
|---|---|---|
| hover bubble ＝ 遷移せず飛び先本文を読む | `read` ＝近傍同梱 / `--related-snippets` | **遷移を畳む＝round-trip を畳む**（[[ai-consumer-cost-and-trust]] 軸1）。bubble は人間版の近傍同梱 |
| card-bubble（関連ページリスト） | `related`（2-hop） | 同じ 2-hop 関連模型 |
| タイトル hover →逆リンク、再帰的に潜行 | `backlinks` ＋ 反復 read | 同じ逆リンク graph。人間は nested bubble、AI は反復 call |
| 赤リンク→接続検知で blue／全 project 空は全走査 | `unresolved_targets`、whole-store cross-project の target_project 存在チェック | 同じ赤リンク semantics。**「全 namespace を見ないと赤判定できない」コストも共通**（[[whole-store-graph-and-cross-project-edges]]） |
| `whiteList` で複数 project 透過 | whole-store default retrieval | 同じ cross-project graph の価値。grasp は project ラベル付きで全体から検索（[[whole-store-graph-and-cross-project-edges]]） |
| `?followRename=true`（改名追従） | identity-without-name（page `id`/`aliases`） | **同じ name=identity 欠陥への別解**（下記） |
| リンク同一判定カスタム／表記ゆれ吸収／類似タイトル関連 | normalized search fallback / `mentions` の正規化 / 赤 node の normalize-title 統合 | 同じ「title が identity ゆえの表記ゆれ」問題 |
| cache-first・最大3 fetch・api/projects 更新時刻チェック | `acquire`/`sync` の bounded fetch ＋ updated metadata 一致で reuse | 同じ bounded-fetch + cache-reuse な freshness（[[incremental-sync]]） |

### 1. 双子の read surface（先行例・validating prior art）

ScrapBubble と grasp は**独立に同じものを作った**: Scrapbox の graph を「**遷移せず近傍を見る**」primitive にする。ScrapBubble の bubble は人間にとっての near-context co-delivery で、grasp の `read`=近傍同梱は AI にとっての同じもの。**「近傍同梱／no-navigation が正しい primitive」という grasp の中核仮説（[[why-not-scrapbox-clone]] の「ブラウザで人間がやっている関連リンク・行リンクの所作を CLI だけで AI が体験できる」）を、別消費者で実装した先行例が裏付ける**。grasp の存在理由は「これを人間 GUI でなく AI CLI で出す」＝ ScrapBubble との差分は**模型でなく消費者**にある。

### 2. cross-project: ScrapBubble は Co- と非 Co- を束ねる／grasp は非 Co- だけ

ScrapBubble の `whiteList` は2種の cross-project 価値を**束ねている**:

- **非 Co-（単一所有者）**: 自分の public project + 自分の private project を繋ぐ。「書き出しを公開・非公開で分けても全て自分が考えたこと」。villagepump ページが「多分これが一番魅力的な機能」と呼ぶのはこちら。
- **Co-（多人数）**: TamperMonkey 版で**他者の project** を繋ぐ。「他者が書いたことと自分が書いたことを同時に閲覧」。

grasp は Co-（多人数協調編集・他者 project 読み）を削ぐ（[[why-not-scrapbox-clone]]）ので、grasp の whole-store cross-project（[[whole-store-graph-and-cross-project-edges]]）が継ぐのは**前者だけ**＝1つの AI が複数 store（namespace）を所有して横断する形。∴ ScrapBubble は「**cross-project は Co- が無くても価値がある**（自分の public+private 統合が最も魅力的）」ことの実例で、grasp が Co- を削いでも cross-project graph を残す判断を支える。逆に「他者が書いたことと同時に」の魅力は grasp が**意図的に捨てている** Co- 側の価値だと位置づけが鮮明になる。

### 3. followRename ＝ grasp が data model で直す欠陥を fetch 時に当てた証拠

ScrapBubble は title が動くと飛び先を見失うため `?followRename=true` で**改名を追いかける**必要がある。これは [[why-not-scrapbox-clone]] の **name=identity 欠陥**（Scrapbox は page-title=identity）が、popular な閲覧ツールにとって**実際に felt な問題**であることの downstream 証拠。直し方が対照的:

- **ScrapBubble**: fetch 時の workaround（改名を追う）。identity 層は足さず、その都度追従する。
- **grasp**: data model で直す（page `id` / `aliases`、stable line-id）。参照が改名を跨いで壊れない（identity-without-name）。

∴ ScrapBubble は「title=identity だと閲覧側も改名追従を払う」ことを示し、grasp の identity 層の必要性を消費者の外から補強する。

### 4. cache 戦略は incremental-sync と独立収束

ScrapBubble の「`api/projects` で更新時刻をまとめて確認 → 更新の無い project は再 fetch しない／最大3 fetch」は、grasp の [[incremental-sync]]（初回 seed ＋ 以降は更新ページのみ差分 upsert）と **`acquire` reuse（criteria fingerprint ＋ candidate updated range が一致するページは local 再利用）** の独立した収束。両者とも「host を叩きすぎず、updated metadata で cache を再利用する」同じ bounded-freshness 機構に至っている。

### 5. 「リンクを貼っただけで満足」テンション（読者ケア／publish 軸に接続）

villagepump `複数のprojectを透過的に扱う` に、daiiz が cross-project text preview を**意図的に見送った**議論がある: 「自分の project にもそのページを作り、引用記法で自分なりにまとめていくのが Wiki を育てる作業」「闇雲に外部 project の中身を表示できると**リンクを貼っただけで満足する現象**が起きる」。これは grasp の come-from / over-link 懸念（[[come-from-declared-gather]]）と、**「他者の content を読む」vs「自分の wiki を育てる」**という第3消費者（公開人間読者）軸（[[ai-consumer-cost-and-trust]] の Updates）に接続する論点。preview の利便と「育てる労力」のトレードオフは grasp が write/publish 層で再訪する。

## Open Questions

- ScrapBubble の `links2hops` 先回り prefetch（ページ内全リンクの空判定を一度に行う）は、grasp の whole-store `unresolved` 再構築の bulk 化に転用できるか。grasp は per-target 走査だが、ScrapBubble は「ページ内全リンクを一括 2-hop 取得」している。
- ScrapBubble が「実装したい」と挙げる**リンク同一判定のカスタム化**（`/villagepump/yyyy/MM/dd` ⇄ `yyyy-MM-dd`）は、grasp の赤 node normalize-title 統合（[[whole-store-graph-and-cross-project-edges]] point 7）や正規化 search と**同じ問題**。両者の normalize 規則を揃える価値があるか（日付・表記ゆれ）。
- ScrapBubble の card 並び替え「Most related + project 順」は、grasp の `related` ranking（whole-store で project 相対 views は比較不能、[[whole-store-graph-and-cross-project-edges]]）と同じ cross-project ranking 問題に当たっている。先行知見を借りられるか。

## 関連

- [[why-not-scrapbox-clone]] — 双子だが grasp は Co- を削ぎ identity-without-name を足す。followRename はその name=identity 欠陥の downstream 証拠
- [[whole-store-graph-and-cross-project-edges]] — whiteList 透過 ↔ whole-store cross-project。決定ページが `[/takker/ScrapBubble]` を slash-in-title の実例に使っている
- [[ai-consumer-cost-and-trust]] — bubble ＝人間版の近傍同梱（軸1 round-trip 畳み）／「リンク貼って満足」は第3消費者軸
- [[incremental-sync]] — cache-first・updated 時刻チェックの独立収束
- [[come-from-declared-gather]] — daiiz deferral の「育てる vs preview」テンション
- [[cosense-cli]] — 同じく grasp 内に置く Cosense 系既存ツール（こちらは hosted CLI、ScrapBubble は閲覧 UserScript）
