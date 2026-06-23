---
type: entity
summary: persona2（世界の LLM Wiki / Markdown 束ユーザ）の視点で、fresh 環境から grasp の初回導線を試したユーザテスト結果。現状は persona2 に active release するには Markdown import と英語 onboarding が gating
sources:
  - [[positioning-two-personas]]
  - grasp CLI 実行 2026-06-23
---

# entity: persona2 user test 2026-06-23

目的: [[positioning-two-personas]] の **persona2 = 世界の LLM Wiki / Markdown 束ユーザ**として、Cosense を知らず、手元に Markdown folder だけがある状態から `grasp` を試す。

## テスト前提

- persona2 は Cosense JSON export を持たない。
- persona2 は Scrapbox/Cosense 文脈を知らない。価値提案は「Markdown の束より、自動逆リンク＋近傍同梱の local graph store の方が LLM に効く」。
- fresh 環境を `GRASP_HOME=/tmp/.../home` と空 cwd で再現し、既存の nishio store に助けられないようにした。
- 最小 Markdown folder として `notes/Alpha.md`（`# Alpha` / `Links to [[Beta]].`）を置いた。

## 結果サマリ

**persona2 に active release する導線としては fail**。理由は、現状の CLI と docs が persona1（Cosense export を持つ nishio dogfooding）には正直だが、persona2 の唯一の入口である Markdown folder import が無く、初回エラーも「まだ未対応」と説明しないため。

これは現 MVP の設計欠陥ではない。v1 実装（[[grasp-v1-implemented]]）は Cosense JSON export first である。ただし [[positioning-two-personas]] の通り persona2 を upside-risk target として狙うなら、Markdown adapter と英語 onboarding は nice-to-have ではなく release gate。

## 観察

### 1. 初回 help が persona2 の hook を出していない

`grasp --help` は "Scrapbox/Cosense-style graph store" と説明し、examples も `盲点カード` / `raw/nishio.json` / Cosense export 前提。persona2 の hook である "local graph store for LLMs from Markdown notes" は出ない。

影響: HN/Reddit 由来の読者は「自分の Markdown ノートに使えるのか」を即判定できない。Scrapbox/Cosense は lineage として後置すべき、という [[positioning-two-personas]] の GTM とまだ一致していない。

### 2. store も export も無い環境で `stats` が onboarding にならない

fresh 環境で `grasp stats` は以下で終了した。

```text
grasp: error: store does not exist and no --export was found: .../home/grasp.sqlite
```

`stats` は「状態確認」の自然な初手なので、store が無い場合は exit 0 or friendly error で `store_exists: false` と次アクションを返す方がよい。

### 3. Markdown folder import の自然な試行が失敗する

persona2 が自然に打つ `grasp import notes` は argparse の `unrecognized arguments: notes` になる。

help を読んで `--export` に folder を渡すと、`grasp --export notes import --force` は Python traceback で落ちる。

```text
IsADirectoryError: [Errno 21] Is a directory: 'notes'
```

影響: 未対応であることが product language で伝わらない。「この tool は自分向けではない」ではなく「壊れている」に見える。

### 4. README / docs が無い

repo root に README / docs は無く、`pyproject.toml` の description も "Scrapbox/Cosense-style"。persona2 の HN/Reddit 導線では、CLI help に到達する前の landing が無い。

### 5. `~/.grasp` default は persona2 にも良い

未コミット中の `GRASP_HOME` / `~/.grasp/grasp.sqlite` default は、単一 AI が一つの local store を持つ体験と一致している。persona2 でも cwd ごとの store より自然。ただし initial seed が Markdown folder でないため、この利点はまだ見えない。

## 推奨

P0（persona2 に見せる前）:
- Markdown import adapter を実装する。surface は `grasp import-md ./notes` か `grasp import --format markdown ./notes` のように、folder を positional に置ける形が自然。
- それまでの暫定として、directory を `--export` に渡した時は traceback でなく「Cosense JSON export only; Markdown folder import is not implemented yet」と出す。
- `stats` は store missing を診断として返し、次アクションを提示する。
- README を置き、lede を "local graph knowledge store for LLMs, better than a flat folder of Markdown notes" にする。Scrapbox/Cosense は lineage に後置。

P1:
- persona2 向けの最小 demo を作る。同一の小さな Markdown folder を import し、`read Alpha` が本文＋`Beta` unresolved target＋逆リンク/related を一体で返すことを見せる。
- root help の examples を persona1 / persona2 の両方に分ける。英語 example は Markdown notes を使い、日本語/Cosense example は別枠にする。
- package description から "Scrapbox/Cosense-style" を後置し、"local graph knowledge store for LLM agents" を先に出す。

P2:
- identity-without-name の persona2 pitch を README に入れる。言葉は「filename=identity をやめるので rename で links が切れない」。
- Markdown import の seed policy（filename title / frontmatter id / aliases / `[[wikilink]]` / `#tag`）を [[grasp-backlog]] から実装計画へ昇格する。

## 判定

- persona1 dogfooding: 現状のまま継続可能。
- persona2 active acquisition: まだ早い。Markdown adapter か、少なくとも「persona2 はまだ未対応」と正直に言う onboarding guard が必要。
