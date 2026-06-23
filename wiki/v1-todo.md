---
type: todo
summary: v1 リリースに向けた TODO。v1 scope = Export した Scrapbox/Cosense JSON を AI が CLI から高速に読む read-only ツール。Cosense ヘビーユーザ（nishio でない、自前の大きな Cosense project を持つ Scrapbox 熟練者）視点の user test 2026-06-23 で出た F1–F5 への対応方針を nishio が確定したもの。
sources:
  - Cosense ヘビーユーザ user test 2026-06-23（本 session）
  - "[[positioning-two-personas]]"
---

# grasp v1 TODO

v1 の射程: **Export した Scrapbox/Cosense JSON を、AI が CLI から高速に読む read-only ツール**。write / identity 層は v1 に**入れない**。

出典: Cosense ヘビーユーザ（nishio でない、自前の大きな Cosense project を持つ Scrapbox 熟練者。persona1=nishio dogfooding / persona2=Cosense を知らない Markdown ユーザ のどちらとも違う第3の視点）の user test の指摘 F1–F5 ＋ transclude への nishio 判断。

## P0 — 最優先

### F1. README を書く ★最優先
- **決定**: 書くべき、最優先。
- 現状: repo root に README が無い。push 済みの github.com/nishio/grasp は bare file tree で landing が無い。「自分の Cosense project の入れ方」がどこにも書かれていない。help の例・seed default 名はすべて nishio 固有（`nishio.json` / `盲点カード` / `民主主義`）で、新規ユーザは「ファイル名を nishio.json にしないと駄目?」と戸惑う。
- やること:
  - lede = 「LLM のための local graph knowledge store（flat な Markdown 束より効く）」。Scrapbox/Cosense は lineage として後置（[[positioning-two-personas]] の GTM と一致）。
  - quickstart 3 行: Scrapbox project を JSON export（管理画面 → Export Pages, metadata ON）→ `grasp import --consense your.json` → `grasp read <title>`。
  - 例とデフォルト表記を nishio 固有から汎用化。
- 受け入れ: README だけ読んで、自分の Cosense export を import して read できる。

## P1 — parser fidelity（デフォルトで Scrapbox と同じ挙動に）

### F2. `#hashtag` をリンクとしてパースする
- **決定**: デフォルトで **Scrapbox と同じ挙動**にする（`#foo` ≡ `[foo]`、逆リンクが立つ）。無視するオプションを付けるかは将来検討（今は決めない）。
- 現状: parser は `[...]` しか見ず `#tag` を黙って捨てる（実測 `#重要`→`[]`, `#2024-01-01`→`[]`, `[重要]`→`['重要']`）。タグ多用ユーザは逆リンク / 2-hop / 赤リンクが警告なく減り、「タグ未対応」でなく「グラフが壊れてる」と誤解する。
- やること: `parse_cosense_links`（`grasp/cosense.py`）に `#tag` を内部リンクとして追加。Scrapbox の hashtag 規則（区切り文字・許容文字・`# ` 装飾との区別）に合わせる。edge / unresolved_targets に反映。
- 受け入れ: `#民主主義` を含む行が `grasp backlinks 民主主義` に出る。

### F3. 数字だけのリンク `[1]` `[2024]` を捨てない（バグ修正）
- **決定**: これはバグ、修正すべき（＝ Scrapbox に合わせる）。SPEC の strict parser が意図的に落としていた `[1]` を v1 では拾う方針に変更。
- 現状: `is_internal_cosense_link` が `token.isdigit()` で除外。Scrapbox では `[2024]` は正当なページリンク（年号ハブ等）。
- やること: 数字のみ token の除外条件を外す。ただし `xs[0]` / `func()[1]` の false positive は `is_ascii_index_syntax`（直前が非空白 ASCII）で従来どおり除外を維持。
- 受け入れ: 行頭/空白後の `[2024]` が edge になる。`xs[0]` は依然リンクにしない。

## P1 — surface / docs

### F4 + transclude. CLI surface から identity 層動詞を削除
- **決定**: write / transclude / rename は **まずは載せない**（"planned" でもない）。v1 = Export した Scrapbox JSON の AI からの高速利用。transclude は今必要ない。
- 現状: [[SPEC]] の「CLI 動詞（surface）」表が write / transclude / rename を載せており、実行すると `invalid choice`（read-only と分からない）。
- やること: SPEC の CLI surface 表から 3 動詞を削除し、v1 scope = read-only と明記。root help にも「read-only mirror」と 1 行。
- 受け入れ: SPEC 表に未実装動詞が無い。`grasp --help` だけで read-only と分かる。

### F5. help 例 / store default の drift を直す
- **決定**: なおすべき。
- 現状: root help の例が `--store .grasp/grasp.sqlite`（cwd 相対）のままだが、19:53 の global 化で実デフォルトは `~/.grasp/grasp.sqlite`（`grasp_home()`）。help どおり実行すると別 store を指す。
- やること: help の例・epilog のデフォルト path を実装（`$GRASP_HOME or ~/.grasp`）に一致させる。SKILL.md / docs の path 表記も合わせる。
- 受け入れ: help の例どおり実行して global store を指す。

## v1 に入れないもの（明示）

- write / transclude / rename（identity 層）。← F4 + transclude 判断。
- Markdown / Obsidian folder import（persona2 向け、別マイルストーン [[markdown-obsidian-indexed-mirror]]）。
- vector 検索。
