---
type: decision
summary: native の保存形式は独自フォーマット（Markdown ではない）。Markdown は逆リンクを「テキスト」にして維持の手回しを生む発生源だから。独自＝ゼロ発明でなく Cosense の行/グラフモデルを正規化して native にする。既存資産の読込は native format でなく import adapter の責務
sources:
  - llm-wiki 設計対話 2026-06-23（nishio 訂正）
---

# Decision: 保存形式は独自フォーマット、import は別責務

決定: native の保存形式は **独自フォーマット**。Markdown にしない。「既存資産を読める」は import adapter で別途達成する。

## 文脈

[[why-not-scrapbox-clone]] / [[SPEC]] を書いた時点で「永続化を既存 Markdown 互換にすれば既存森を即読める」と Open Q に書いた。nishio が2点訂正:

1. **保存形式は独自であるべき。Markdown であることが逆リンクメンテのしがらみを生んでいる。**
2. **「読める」こと自体は保存形式と独立**（Markdown を native にしなくても読める）。イメージは「まず Cosense の JSON エクスポートを1ファイル渡して CLI で読めるようにする」。

## なぜ Markdown が「しがらみの発生源」か（核心）

- Markdown ではリンクは **ファイル内のテキスト**。逆リンクは *どこにも保存されていない* → 全文スキャンで導出するか、相手ページに書き戻して「維持」する（これが file-back skill の「被リンクも足す」手回し）。
- Markdown は **リンクと逆リンクを2つの別々のテキスト事実**にする → drift する（片方だけ消える＝孤立/壊れリンク、lint が検出する欠陥）。
- 独自フォーマットならリンクは **グラフのエッジ**。forward と backward は *同一エッジの両読み*。「逆リンクの維持」という概念自体が消え、O(1) で引ける。

→ Markdown 互換に寄せた瞬間、grasp が逃げたかった問題（[[why-not-scrapbox-clone]] の felt friction）を native に**再輸入**する。だから native は独自。

## 「独自」＝ゼロからの発明ではない

nishio の MVP イメージ（Cosense JSON export から始める）が指すのは: **Cosense の export は既に line ベース＋リンク構造を持つ** → 独自フォーマットは *Cosense のグラフ/行モデルを正規化して native にする* こと。export から始める＝モデルから始める。Markdown はそのモデルを潰した lossy ダウングレードだった。

## 帰結: 三層に分離

```
[native store（独自・グラフ/行・エッジ保持）]
        ↑ import adapter（Cosense JSON / 後で Markdown）
[CLI 動詞（read=近傍同梱 / backlinks / unresolved ...）]
```

- 「既存 wiki森 40+ を読める」利点は **Markdown import adapter** で達成（native を Markdown にしない）。
- MVP の入力 = **Cosense JSON export 1ファイル**、読み取り専用（[[SPEC]] MVP 節）。

## Update (2026-06-23): on-disk store = SQLite（or better）、JSON は持ち続けない

実測比較（[[cosense-cli]]）で in-memory（export を毎回 full parse）が全コマンド一律 ~3.4s の律速と判明。nishio 判断: **渡された JSON はあくまで handoff 形式。JSON のまま保存し続ける必要はなく、SQLite もしくはより良いデータ構造で持ってよい**。

→ 下の Open Q「on-disk か in-memory か」は **on-disk = yes** で解決。具体は SQLite（pages / lines / edges / unresolved_targets を materialize したテーブル）を起点に、必要なら専用構造へ。これが [[SPEC]] M2-1。JSON export は import adapter の**入力**にのみ使い、保存層では捨てる。store は後の差分更新（[[incremental-sync]]）のため **upsert 可能**に設計する。

## Update (2026-06-23): store は global に1個（per-project に複製しない）

nishio 判断「同一 Cosense を project ごとに別々に持ちたいことはない → global に入れて DB も global」。store は **単一 AI 所有の knowledge store ＝ どこで作業していても同じ1個**であって、cwd ごとの cache ではない。

- 既定の置き場は global home: `$GRASP_STORE` → `$GRASP_HOME/grasp.sqlite` → `~/.grasp/grasp.sqlite`。seed も `~/.grasp/nishio.json`（repo `raw/` への symlink）。`grasp/cli.py` の `default_store_path()` を cwd 相対 (`./.grasp/...`) から home 基準へ変更済み。
- ∴ どの cwd からも flag 無しで同じ store を引く。これは delivery を global skill にした判断（[[delivery-cli-plus-skill]]）と同根 — **「1つの外部脳 = 1つの store = どこからでも同じ skill」**。`[[why-not-scrapbox-clone]]` の「単一 AI 所有」が永続層に降りた形。
- 設計含意: store path は project state でなく user/agent state。repo を clone し直しても store は残る。複数の異なる knowledge set を切り替えるなら `$GRASP_HOME` で home ごと差し替える（per-project flag ではなく）。

## Open Questions

- ~~独自 store を on-disk で持つか、MVP は in-memory か~~ → **解決: on-disk（SQLite or better）**（上 Update）。
- ~~Cosense export の正確なスキーマ（line-id の有無、リンク `[title]` 構文、メタデータ）は Codex が実物の export で確認~~ → **解決: 実物 25791 pages で確定**（[[cosense-json-export]]）。line に安定 id 無し（grasp 採番）、link graph 未保存（text parse）、`[...]` overloaded。
