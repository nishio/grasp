---
type: entity
summary: Cosense (Scrapbox) 管理画面「Export Pages (JSON, metadata 込み)」の実スキーマ。v1 import adapter の source of truth。実物 (nishio project, 25791 pages, 2026-06-23 export) で確認。lines に安定 id は無し（grasp が採番）、リンク graph は未保存（text から parse）、`[...]` は overloaded
sources:
  - raw/nishio.json（nishio project export, exported 1782200013 = 2026-06-23T07:33Z, 25791 pages / 724981 lines）
  - 管理画面 Export Pages: "Include metadata such as line.created and line.updated" を ON
  - https://github.com/nishio/grasp/pull/2 （villagepump export で metadata なし plain string line を確認, merged 2026-06-24）
---

# entity: Cosense JSON export schema（import adapter の実物確認）

v1 入力 = この形式（[[grasp-v1-implemented]] / [[persistence-custom-format]]）。以下は **実物の export で確認した確定スキーマ**。Codex の import adapter はこれに合わせる。旧 `SPEC.md` が「Codex が実物で確認」と保留していた項目（line-id 有無・リンク構文）はここで確定。

## JSON 構造（確定）

```
root: {
  name: str,              # project name ("nishio")
  displayName: str,
  exported: int,          # epoch seconds
  users: [ {id, name, displayName, email} ],   # ★複数人いうる（下記）
  pages: [ page, ... ]
}
page: {
  title: str,             # 表示名 = identity（Scrapbox の name=identity 欠陥の本体）
  id: str,                # ★安定 page id（24hex）。grasp の page.id の seed に使える
  created: int,           # epoch
  updated: int,
  views: int,             # ★閲覧数。unresolved/related の ranking signal に使える
  lines: [ line, ... ]
}
line (metadata ON 時): {
  text: str,
  created: int,
  updated: int,
  userId: str             # 行ごとの著者 id（users[].id を指す）
}
line (metadata なし / older export variant):
  str                     # 行本文そのもの。created/updated/userId は無し
```

## 確定した gotcha（旧 SPEC の保留を解決）

### 1. line に安定 id は無い → grasp が採番（原理4 と整合）
line は `{text, created, updated, userId}` のみ。**`id` フィールドは存在しない**（138220 行サンプルで 0/138220）。
→ 旧 `SPEC.md` の「line-id は機械が自動採番」「import 時に grasp が line-id を採番」が確定。export の `(created, userId)` は安定 key にならない（重複・編集で変わる）ので、grasp が import 時に採番する。

2026-06-24 追記: `villagepump` export では一部 line が dict でなく plain string（metadata なし）だった。これは line id 不在だけでなく line metadata 自体が無い variant。`grasp` 1.5.24 以降は plain string line を `text=<文字列>`, `created/updated/user_id=None` として import する。

### 2. リンク graph は export に無い → text から parse
page のキーは `title/id/created/updated/views/lines` のみ。**forward link も backlink も保存されていない**（Scrapbox 内部の `links`/`linksLc` は export に含まれない）。
→ import adapter は **各 line.text を parse してエッジを抽出**し、grasp 側で graph を materialize する。これは「Cosense の行/グラフモデルを正規化して native にする」の実体（[[persistence-custom-format]] / [[grasp-cli-mvp]]）。

### 3. `[...]`（単角括弧）は overloaded — 内部リンクは 62.7% だけ
旧 `SPEC.md` の「link 構文は `[title]`」は不正確。単角 `[...]` トークン全 212052 個の内訳（実測, 全 page）:

| 種別 | 例 | 件数 | 割合 | import で |
|---|---|---|---|---|
| **内部リンク** | `[ページ名]` | 133022 | 62.7% | エッジ抽出（これだけ） |
| 外部 URL | `[https://… ラベル]` / `[ラベル https://…]` | 49587 | 23.4% | リンクでない（外部参照） |
| icon/img | `[name.icon]` `[….img]` | 14194 | 6.7% | 装飾、スキップ |
| 装飾 | `[* 太字]` `[/ 斜体]` `[- 取消]` `[_ …]` | 7704 | 3.6% | 装飾、スキップ |
| cross-project | `[/proj/page]` | 5975 | 2.8% | 別 project リンク（MVP 外） |
| 数式 | `[$ …]` | 1570 | 0.7% | 装飾、スキップ |

判別規則（import の link 抽出ロジック）:
- `https?://` を含む → 外部 URL
- 先頭が `* / - _` ＋空白 → 装飾、`$ `＋空白 → 数式
- 先頭 `/` → cross-project
- `*.icon` / `*.img` → icon/img
- 残り → **内部リンク**

実装後の補正: broad bracket 分類の「残り」は code/list/decoration notation も含む。`grasp` MVP parser は unresolved target noise を減らすため、inline backtick 内、ASCII index 風 `xs[i]` / `func()[0]`、数字のみ `[1]`、連続 `*`/`-`/`_` 装飾 `[** x]` を link から除外する（[[grasp-cli-mvp]]）。

`[[...]]`（二重角括弧）は **bold であってリンクではない**（全 page で 272 個のみ）。grasp の `[[wikilink]]` とは意味が逆 ← 重要。`#tag`（4506 個）も別系統（ハッシュタグ＝リンク等価だが構文別）。

### 4. title = lines[0].text（≈99.7%）
各 page の先頭行 text はタイトルと一致（5000 page 中 4986）。残りは旧データの揺れ。import は lines[0] を本文に含めるか除くか決める（タイトル重複を避けるなら除く）。

### 5. リンク解決は normalize（linksLc）= case-insensitive ＋ 空白畳み込み
Scrapbox はリンク照合を正規化（小文字化・連続空白畳み込み）して行う。実測では exact match の unresolved target 45911 → normalize で 45703（**208 件だけ**既存 page に解決、title 衝突は 1 group のみ）。
→ MVP は exact でもほぼ正しいが、**正確には normalize して resolve / unresolved target 判定**すべき。

### 6. users は複数（単一所有の前提に注釈）
`users` に 2 人: `nishio` 本人 ＋ `garbot`（"Scbox Nishio", bot アカウント）。line.userId も複数値を取る。grasp は「単一 AI 所有」だが、**import 元データは複数 author を含みうる**。MVP は author を捨ててよい（grasp は単一所有）が、line.userId は将来 provenance に使える。

## scale（実測 → MVP / perf への含意）

- pages 25791 / lines 724981 / JSON 118MB。
- 内部リンク instance 133022、**distinct link target 61613**、うち **既存 page に解決 15702 / unresolved target 45703**。
- `grasp` MVP の strict parser では 120693 edges / unresolved target 41750。上記 133022 / 61613 / 45703 は broad bracket 分類の値。
- unresolved targets は ~45700 件返りうる → **必ず ranking（link count・views・recency）が要る**。素の全列挙は使えない。
- 118MB JSON の全 load は初期 MVP の in-memory なら可（数百MB RAM）だったが、毎回 parse は遅い → v1 は SQLite on-disk store（[[grasp-v1-implemented]]）。

## Open Questions

- ~~lines[0]（タイトル行）を本文に残すか除くか~~ → MVP は残す（完全性と `page.id:line-index` の安定性優先）。
- `#tag` を内部リンクと同一エッジ扱いにするか（Scrapbox は等価扱い）。
- cross-project `[/proj/page]` を MVP でどう扱うか（単一 project 前提なら無視 → 外部リンク扱い）。
- 装飾記法（`[* ]` 等）を line text に残すか strip するか（read の見た目 vs 原文保存）。
