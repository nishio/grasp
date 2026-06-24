---
type: decision
summary: write/identity 層に着手する。3 つの決定。①位置づけ＝当面 write は alpha testing で、信用してここに大事なものを預ける人は自己責任（read 経路の信頼性 v1 stable と write 経路 alpha を別 SLA にする。これで authority/undo/原典関係を設計し切る前に実装を進められる）。②テスト方法＝このリポジトリ自身の過去 wiki 編集（git history＝page 作成/rename/本文編集/リンク追加の実列）を grasp の write/rename で再現でき、差別化の約束（rename で [[..]] 参照が壊れず redirect stub も溜まらず参照文も保たれる）が実データで成り立つかを ground truth に検証する。③実装順序＝最高リスク先行（nishio 指示）。最高リスク＝edit を跨ぐ stable identity（stable ID requires memory）＋ rename で参照が壊れないこと。plain write は低リスクで差別化でもないので最後。順序: stable identity + re-import diff → rename → write → transclude / come-from。
sources:
  - nishio 指示 2026-06-24「当面書き込み機能は alpha testing と位置付ける。信用してここに大事なものを預ける人は自己責任。テスト方法はこのリポジトリの過去の wiki 編集を grasp で同様にやれるかとする」
  - nishio 指示 2026-06-24「実装順序は最もリスクが高いものの検証を先にすべき」
  - wiki/concepts/development-arc-retrieval-ahead-of-authoring.md（retrieval≫authoring の非対称と Open Questions）
  - wiki/grasp-backlog.md「Local write and identity layer」「stable line identity」
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
- write を alpha と明示することと、read を含む grasp 全体の version（[[history]] の 1.x.y）の関係。write 着手で store generation `x` が上がるか、alpha surface は別 channel にするか。
