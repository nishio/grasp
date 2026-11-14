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

実装後の補正: broad bracket 分類の「残り」は code/list/decoration notation も含む。`grasp` MVP parser は unresolved target noise を減らすため、inline backtick 内、ASCII index 風 `xs[i]` / `func()[0]`、連続 `*`/`-`/`_` 装飾 `[** x]` を link から除外する（[[grasp-cli-mvp]]）。数字のみ `[1]` / `[2024]` は MVP では除外していたが、`1.5.0`（2026-06-23）以降は internal link として拾う（[[grasp-v1-implemented]] / [[history]] `1.5.0`）。2026-11-14 に `parse_cosense_links('[1] [2024]')` が `['1', '2024']` を返すことを確認し、この行の古い記述を直した（2026-06-23 の lint log が食い違いとして挙げたまま残っていた）。

`[[...]]`（二重角括弧）は **bold であってリンクではない**（全 page で 272 個のみ）。grasp の `[[wikilink]]` とは意味が逆 ← 重要。`#tag`（4506 個）も別系統（ハッシュタグ＝リンク等価だが構文別）。

### 4. title = lines[0].text（≈99.7%）
各 page の先頭行 text はタイトルと一致（5000 page 中 4986）。残りは旧データの揺れ。import は lines[0] を本文に含めるか除くか決める（タイトル重複を避けるなら除く）。

### 5. リンク解決は normalize（linksLc）= case-insensitive ＋ 空白畳み込み
Scrapbox はリンク照合を正規化（小文字化・連続空白畳み込み）して行う。実測では exact match の unresolved target 45911 → normalize で 45703（**208 件だけ**既存 page に解決、title 衝突は 1 group のみ）。
→ MVP は exact でもほぼ正しいが、**正確には normalize して resolve / unresolved target 判定**すべき。

2026-11-14 訂正: Cosense の `linksLc` / `titleLc` は小文字化に加えて **空白を `_` に置き換える**（下の Update (2026-11-14)）。上の「小文字化・連続空白畳み込み」は `_` の扱いを落としている。grasp の `normalize_title`（`grasp/cosense.py`）はこの記述どおり casefold ＋連続空白の 1 個化だけで、`_` と空白を同一視しない。

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
- `normalize_title` で `_` と空白を同一視するか（2026-11-14）。Cosense では `[Foo Bar]` と `[Foo_Bar]` が同じ page に解決するが、grasp では別の handle になり、page の無い名前なら unresolved target（概念ハブ）が 2 つに割れる。下の Update (2026-11-14) の実測では差は小さい（リンク 33857 本中 10 本）。意図した差分という記録は wiki と docs に見当たらない。変えるなら store generation と既存 handle の解決が変わる。Markdown 側（Obsidian では `_` と空白は別のファイル名）に同じ規則を当てるかも別に決める必要がある。

## Update (2026-06-26): hosted REST との差分

ScrapBubble / `@cosense/std` / `@cosense/types` の実コード再読と公開 API 実測により、JSON export だけでは落ちる情報が明確になった。JSON export は bulk seed として引き続き有用だが、hosted freshness path で補完できる情報がある。

- REST page (`/api/pages/:project/:title?followRename=true`) は `commitId`、stable `lines[].id`、`links` / `projectLinks` / `icons`、`relatedPages.links1hop` / `links2hop` / `projectLinks1hop`、`linked`、`pageRank`、`accessed`、`snapshotCount`、`lastAccessed`、`persistent` を返す。JSON export はこのうち line id / commitId / resolved link metadata / related pages / access-derived metadata を含まない。
- REST page summary (`/api/pages/:project`) は本文を含まないが、project 全体の `id` / `title` / `updated` / `created` / `linked` / `views` / `linesCount` / `charsCount` / `pin` を pagination できる。これは delete / rename 検出用の full manifest として JSON export 反復より軽い。
- `@cosense/types` 上の backup schema (`/api/project-backup/:project/:backupId.json`) は `linksLc` を持つが、管理画面 JSON export schema は持たない。つまり「export」と「backup」は似ているが同一 schema ではない。
- `@cosense/types` には `/api/commits/:project/:pageId` の `TitleChange` / `DeleteChange` / stable line-id change、`/api/deleted-pages/:project/:pageId`、`/api/page-snapshots/:project/:pageId`、`/api/stream/:project` の delete event 型がある。未ログイン公開 project 実測では commits / snapshots / deleted-pages は 401、stream は 200。rename/delete 補完は認証済み path として扱う。

含意: `grasp import --cosense` は export の text を source of truth として取り込むだけでよいが、`sync` / `acquire` は REST metadata を「補助列・manifest・tombstone・alias history」として保存できる余地がある。特に stable line identity を本気でやるなら、REST `lines[].id` を捨て続ける方針は見直し候補。

## Update (2026-11-14): `_` と空白の正規化の差

Cosense の名前の正規化は「小文字化 ＋ 空白を `_` に置換」。根拠は `@helpfeel/cosense-cli` の実装で、`src/lib/annotateRelations.ts` の `toTitleLc` が `title.replace(/ /g, '_').toLowerCase()` で、`readPage` の help が hosted REST の `linksLc` を「links[] を正規化（小文字化＋空白を _ に置換）した形式」と説明している。grasp の `normalize_title` は `WHITESPACE_RE.sub(" ", title.strip().casefold())` で、`normalize_title('Foo_Bar') == 'foo_bar'`、`normalize_title('Foo Bar') == 'foo bar'`（2026-11-14 実行で確認）。

実測（2026-11-14）: 手元の別 project の export（3536 pages、`_` を含む title 3 件）に grasp の `parse_cosense_links` を当て、title 行を除く本文のリンク 33857 本を 2 つの規則で解決した。

| 規則 | 既存 page に解決 |
|---|---|
| grasp `normalize_title` | 25717 |
| Cosense 近似（空白を畳んで小文字化し、空白を `_` に置換） | 25727 |

差は 10 本（distinct な名前 9 個）で、10 本とも「Cosense の規則なら解決し、grasp では unresolved」の向き。逆向き（grasp だけで解決）は 0 本。nishio project（25791 pages）では測っていない（2026-11-14 時点で手元に export が無い）。Cosense 近似は hosted の実装そのものでなく、上の cosense-cli の規則を写したもの。

経緯: 別 repo で Cosense・grasp・LLM 系の知識グラフ（Graphiti・LightRAG・Cognee）のリンク概念を比べたとき、名前の同一視の規則を並べて気づいた。そこでの比較の要点（grasp に関わる分）:

- Cosense / grasp のリンクは名前に向けて張り、先が無くてもよい（未解決は概念ハブとして資産になる）。LLM 系の 3 つは書き込み時に LLM が確定する「2 つの entity の間の 1 文の主張」で、未解決の先を残すのは LightRAG（`UNKNOWN` 型の node）だけ。
- 名前の同一視の規則は道具ごとにばらばら。Cognee（`uuid5` の seed を小文字化・空白→`_`・アポストロフィ除去で作る）は Cosense にほぼ一致し、LightRAG は大文字小文字を畳まず、Graphiti は名前の一致・MinHash・LLM の 3 段で統合後に表記の揺れを残さない。
