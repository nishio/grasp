---
type: decision
summary: write/identity 層に着手する。3 つの決定。①位置づけ＝当面 write は alpha testing で、信用してここに大事なものを預ける人は自己責任（read 経路の信頼性 v1 stable と write 経路 alpha を別 SLA にする。これで authority/undo/原典関係を設計し切る前に実装を進められる）。②テスト方法＝このリポジトリ自身の過去 wiki 編集（git history＝page 作成/rename/本文編集/リンク追加の実列）を grasp の write/rename で再現でき、差別化の約束（rename で [[..]] 参照が壊れず redirect stub も溜まらず参照文も保たれる）が実データで成り立つかを ground truth に検証する。③実装順序＝最高リスク先行（nishio 指示）。最高リスク＝edit を跨ぐ stable identity（stable ID requires memory）＋ rename で参照が壊れないこと。plain write は低リスクで差別化でもないので最後。順序: stable identity + re-import diff → rename → write → transclude / come-from。
sources:
  - nishio 指示 2026-06-24「当面書き込み機能は alpha testing と位置付ける。信用してここに大事なものを預ける人は自己責任。テスト方法はこのリポジトリの過去の wiki 編集を grasp で同様にやれるかとする」
  - nishio 指示 2026-06-24「実装順序は最もリスクが高いものの検証を先にすべき」
  - nishio 合意 2026-06-26「Markdown を出力し続けるが、人間や Codex は直接 Markdown を編集せず grasp write が native store を更新し、そこから Markdown を再生成する」
  - wiki/concepts/development-arc-retrieval-ahead-of-authoring.md（retrieval≫authoring の非対称と Open Questions）
  - wiki/grasp-backlog.md「Local write and identity layer」「stable line identity」
  - wiki/decisions/native-authority-markdown-projection.md
  - wiki/decisions/why-not-scrapbox-clone.md / wiki/decisions/positioning-two-personas.md（identity-without-name = 存在理由）
---

# Decision: write 層は当面 alpha、検証は「過去 wiki 編集の再現」、最高リスク（identity/rename）から作る

決定: grasp の write/identity 層に着手する。[[development-arc-retrieval-ahead-of-authoring]] が記述した「retrieval は厚く実装済みだが差別化核の authoring は全部 [[grasp-backlog]]」という非対称を、ここから埋めにいく。着手にあたり 3 つを固定する。

## 決定1: 当面 write は alpha testing（信頼性は自己責任）

v1 が read-only であることは制約ではなく **信頼性の源**だった。store は import で再構築でき、誤った状態は re-import で消える＝**undo が無料**。write を入れた瞬間この安全網が外れる（書いた state が権威になり、原典との関係・undo・壊れた時の回復が未設計、[[development-arc-retrieval-ahead-of-authoring]] Open Questions）。

∴ **「動く」と「信頼して大事なデータを預けられる」を分離する**。当面 write 機能は **alpha testing** と明示し、信用してここに大事なものを預ける人は **自己責任**とする。

- これは出荷判断であって、設計を止める理由ではない。alpha と明示することで、authority/undo/原典関係を完全に設計し切る**前に**実装を前へ進められる。
- **read 経路と write 経路を別 SLA にする**: read は v1 で stable（[[grasp-v1-implemented]]）、write は alpha。CLI / README / Skill は write 系 verb に alpha 警告を出し、「local store への破壊的変更は再現不能になりうる」ことを明記する。
- 安全側の既定: write は原典（Cosense export / Markdown mirror）を直接書き換えず、grasp local store に対して行う。原典は引き続き re-import の source of truth に保てる（read-only の安全網を write 対象の外側に残す）。具体的な store 上の authority/undo 表現は実装で詰めて file back する。

## 決定2: テスト方法 = このリポジトリ自身の過去 wiki 編集を grasp で再現する

検証 corpus を外から探さない。**この grasp リポジトリ自身**（`wiki/` = Markdown + frontmatter + `[[...]]`）の **git history が、実際に起きた編集の列**そのもの: page 作成・rename・本文編集・`[[...]]` リンクの追加/削除。すでに Markdown mirror の dogfood corpus（[[markdown-obsidian-indexed-mirror]]、`import --markdown wiki`）。

テストの形:

- git の連続 revision を **ground truth** に取る。revision N を grasp store に import した状態から、N→N+1 の diff（page 追加・rename・行編集・リンク変更）を grasp の write/rename/transclude で **適用**する。
- 合格条件は2系統:
  1. **一致**: 適用後の store が、revision N+1 を素朴に import した store と（page/line/edge/unresolved の意味で）一致する。
  2. **差別化の約束が実データで成り立つ**: rename したとき `[[旧名]]` 参照が壊れず（id を指す）、redirect stub も溜まらず、参照行の surface text も author のまま（[[positioning-two-personas]] の identity-without-name 表、[[why-not-scrapbox-clone]]）。
- これは [[use-case-experiment-as-outcome-story]] の authoring 版。outcome story = 「nishio がこの wiki で手 / file-back skill でやってきた編集を、grasp に任せられるか」。raw に diff を流すだけでなく、再現できた編集・壊れた編集・identity を引き継げなかった行を bounded な結果として読めること。
- 注意: この wiki はリンク記法が2系統（`[[...]]` = grasp 内 edge、バックティックのプレーン名 = 親 llm-wiki への cross-wiki 非 edge、[[markdown-obsidian-indexed-mirror]]）。replay test の edge 判定は mirror parser の policy に揃える。

## 決定3: 実装順序 = 最もリスクが高いものを先に検証する（nishio 指示）

nishio 指示（2026-06-24）: **実装順序は最もリスクが高いものの検証を先に**。

最高リスク = **edit を跨いで stable な identity**（[[grasp-backlog]]「stable line identity」: content hash は本文編集で変わり、line index は挿入で変わる → **stable ID requires memory**）＋ **rename で参照が壊れないこと**。これが成り立たなければ grasp は Markdown+grep / Scrapbox に対する**存在理由を失う**（identity-without-name が差別化核、[[why-not-scrapbox-clone]] / [[positioning-two-personas]]）。逆に plain write（append/update）は低リスクで差別化でもない。

∴ 検証順序（楽な順でなく、危険な順）:

1. **stable page/line identity + re-import diff で id 引き継ぎ**（最高リスク・最も未知）。決定2の git 連続 revision を diff source に使い、行の split/merge/大幅編集で identity がどこまで引き継げて、どこで壊れるかを**実データで測る**。schema 方向は [[grasp-backlog]]「stable line identity」の `lines(id, line_index, ...)` ＋ `line_tombstones`。曖昧一致（split/merge/重複行/大幅編集）は自動同一視せず新 id にする方針をここで実証する。
2. **rename**（参照は id を指すので surface text を保ったまま動く）。redirect stub なし・参照文破壊なしを、この wiki の実 rename 履歴で実証する。
3. **write**（page create/update + edge 自動更新。相対的に低リスク、最後）。
4. **transclude（line-id 行参照）/ come-from declare・render**（[[come-from-declared-gather]]）は identity 層が立ってから。

逆順（write を先に作る）は実装が楽だが、**検証価値が一番低いものを先に作る**ことになり、決定3に反する。

felt-sense link（行キー・著者 retrieval 意図）と come-from link（用語キー・読者ケア standing rule）を別 first-class object にする要件（[[come-from-declared-gather]] / [[grasp-backlog]]）は維持。identity 層（1）は felt-sense / line に効き、come-from（4）は term identity に紐づく別経路。

## 運用: worktree で Codex が実装、判明事項は file back

- 作業は `feat/write-identity-alpha` 相当の **別 git worktree**で行う（AGENTS.md 運用方針: 既存差分と混ぜない / 撤収前に clean & main へ ff）。本 wiki（main）は Codex が読む context として先に固定する。
- Codex が実装して初めて分かる制約（identity diff の曖昧一致の壊れ方、authority/undo の store 表現、replay test の不一致パターン）は本 wiki に file back する。実装済みになった surface は [[grasp-v1-implemented]] へ、未着手の残りは [[grasp-backlog]] に残す。

## Open Questions

- alpha の store authority/undo を具体的にどう表現するか（journal / 原典との二層 / snapshot）。決定1は「原典は書き換えない」までで、store 内 undo 表現は実装で詰める。
- replay test の「一致」判定の厳密さ。line id まで一致を要求するか、page/edge/text の意味一致で足すか。identity 引き継ぎ自体を測るテストなので、id 一致は別レイヤの assertion にする。
- 単一 dogfooder（nishio）の git history を ground truth にするので、編集パターンが nishio 固有（file-back skill 経由が多い）。外部 persona2 の編集様式（手編集・rename 頻度）は別 corpus が要るかもしれない（[[development-arc-retrieval-ahead-of-authoring]] の dogfood 転移リスク）。

## Updates

### 2026-07-02: stable identity は「IDがある」ではなく「再取り込み後も引き継げる」

villagepump/grasp で takker が「pageId や lineId は既にあるのでは」と指摘した。ここで言う stable identity は、現在のページや行を指す ID の存在ではなく、**edit / re-import / rename の後も同じページ・行だと引き継げること**。`read --json` が page id を返すことは consumer 価値として既済だが、write/identity 層のリスクは「次の import や rename 後に同じ identity として扱えるか」にある。

同じ文脈で `re-import diff` の意味も明確化する。前回の store と新しく読み込んだ source を比べ、同じページ/行には前の ID を引き継ぎ、消えたものは tombstone、新しいものは new ID にする差分取り込み。split / merge / 大幅編集のように曖昧なものは、無理に同一視せず new ID に倒す方針。この言い方にすると、既存 `pageId/lineId` と未実装の stable identity の差が誤読されにくい。

### 2026-06-26: LLM Wiki migration target は native authority + Markdown projection

nishio と合意: LLM Wiki を grasp infrastructure へ移す目標形は [[native-authority-markdown-projection]]。**Markdown は出力し続けるが authority ではなく generated projection**。人間や Codex が直接 Markdown を patch するのではなく、`grasp write` が native store（＋ durable journal）を更新し、そこから Markdown を再生成する。

この合意は本 decision の「原典は書き換えず local store に write」から一段進み、LLM Wiki cutover 後の原典関係を定義する。cutover 前は Markdown import が source、cutover 後は native store / journal が source、`wiki/` は review / backup / publish / interoperability の projection。したがって write 実装の最小 slice は一般 editor ではなく、file-back dogfood に必要な page create/update、append section、append log event、rename、export Markdown projection、status/diff/revert event。

### 2026-06-24: write line の versioning — メジャー `2`、alpha は SLA ラベル（version 非依存）、cadence A

nishio と合意（上の Open Questions #4 を解決、versioning policy 本体は [[history]]）。

- **メジャー `2` ＝「grasp が write/authoring line を持つ」**。read-only(`1`) → read+write は本プロジェクト最大の概念変化（[[development-arc-retrieval-ahead-of-authoring]]：「存在理由の半分」がここで埋まる）なので、store-compat 台帳（[[history]]）のメジャーを上げて標す。`1` = read line、`2` = authoring line を持つ line。`x` / `y` の意味は major を跨いでも同じ。
- **alpha/stable は version 番号に載せない**。決定1の「read=stable / write=alpha を別 SLA」をそのまま使い、alpha かどうかは **write 系 verb に付く SLA ラベル**（直交チャネル）で表す。version は product line(major) / store generation(`x`) / compatible(`y`) を追う。∴ `2.0.0` は write verb が alpha ラベル付きで載った最初の line として出せる。`2.0.0-alpha.N` の prerelease 運用に逃げず、alpha→stable 卒業はラベルを外す SLA 変更として version bump と独立に扱う。
- **cadence A（big-bang を避ける）**。worktree で並行開発するのは「最高リスクのスライス（決定3 ① stable identity + re-import diff、次いで ② rename）が replay test を通る」まで。そこで main に merge し、その merge を `2.0.0` 境界にする（store generation が上がり、最初の authoring verb=rename が alpha ラベルで載る）。以降 ③ write / ④ transclude・come-from は `2.x.y`。
  - 理由: write系完了まで merge しない長寿命ブランチは、[[development-arc-retrieval-ahead-of-authoring]] が warn した「authoring が tight dogfood loop を失う」罠そのもの。かつ決定1（原典は書き換えず local store に write、re-import 安全網を write 対象の外に残す）が**隔離の安全上の必要を消した**ので、完了まで隔離する理由がない。`1.5.x` の retrieval 改良が main で動いている間の branch drift も避ける。
  - worktree は探索 churn を散らかさない用途として ①（最高リスク・schema が動く）まで保つ。②以降は main 上で alpha ラベル付きで刻んでよい。
- ~~write を alpha と明示することと、read を含む grasp 全体の version（[[history]] の 1.x.y）の関係。write 着手で store generation `x` が上がるか、alpha surface は別 channel にするか。~~ → **解決（下記 Updates 2026-06-24）**: メジャー `2` ＝ write/authoring line、alpha は SLA ラベルで version 非依存、cadence A で ①+② が replay test を通った時点を `2.0.0` 境界にする。
