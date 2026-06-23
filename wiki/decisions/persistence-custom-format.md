---
type: decision
summary: native の保存形式は独自フォーマット（Markdown ではない）。Markdown は逆リンクを「テキスト」にして維持の手回しを生む発生源だから。独自＝ゼロ発明でなく Cosense の行/グラフモデルを正規化して native にする。既存資産の読込は native format でなく import adapter の責務
sources:
  - llm-wiki 設計対話 2026-06-23（nishio 訂正）
---

# Decision: 保存形式は独自フォーマット、import は別責務

決定: native の保存形式は **独自フォーマット**。Markdown にしない。「既存資産を読める」は import adapter で別途達成する。

## 文脈

[[why-design-B]] / [[SPEC]] を書いた時点で「永続化を既存 Markdown 互換にすれば既存森を即読める」と Open Q に書いた。nishio が2点訂正:

1. **保存形式は独自であるべき。Markdown であることが逆リンクメンテのしがらみを生んでいる。**
2. **「読める」こと自体は保存形式と独立**（Markdown を native にしなくても読める）。イメージは「まず Cosense の JSON エクスポートを1ファイル渡して CLI で読めるようにする」。

## なぜ Markdown が「しがらみの発生源」か（核心）

- Markdown ではリンクは **ファイル内のテキスト**。逆リンクは *どこにも保存されていない* → 全文スキャンで導出するか、相手ページに書き戻して「維持」する（これが file-back skill の「被リンクも足す」手回し）。
- Markdown は **リンクと逆リンクを2つの別々のテキスト事実**にする → drift する（片方だけ消える＝孤立/壊れリンク、lint が検出する欠陥）。
- 独自フォーマットならリンクは **グラフのエッジ**。forward と backward は *同一エッジの両読み*。「逆リンクの維持」という概念自体が消え、O(1) で引ける。

→ Markdown 互換に寄せた瞬間、grasp が逃げたかった問題（[[why-design-B]] の felt friction）を native に**再輸入**する。だから native は独自。

## 「独自」＝ゼロからの発明ではない

nishio の MVP イメージ（Cosense JSON export から始める）が指すのは: **Cosense の export は既に line ベース＋リンク構造を持つ** → 独自フォーマットは *Cosense のグラフ/行モデルを正規化して native にする* こと。export から始める＝モデルから始める。Markdown はそのモデルを潰した lossy ダウングレードだった。

## 帰結: 三層に分離

```
[native store（独自・グラフ/行・エッジ保持）]
        ↑ import adapter（Cosense JSON / 後で Markdown）
[CLI 動詞（read=近傍同梱 / backlinks / wanted ...）]
```

- 「既存 wiki森 40+ を読める」利点は **Markdown import adapter** で達成（native を Markdown にしない）。
- MVP の入力 = **Cosense JSON export 1ファイル**、読み取り専用（[[SPEC]] MVP 節）。

## Open Questions

- 独自 store を on-disk で持つか、MVP は in-memory（export を毎回パース）で済ますか。
- Cosense export の正確なスキーマ（line-id の有無、リンク `[title]` 構文、メタデータ）は Codex が実物の export で確認。
