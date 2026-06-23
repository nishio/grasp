# grasp — 開発 wiki index

単一 AI 所有の local な Scrapbox 型グラフ知識ストア `grasp`（graph × scrap / 把握）の開発 wiki。
Codex が実装し、本 wiki が spec・設計判断・gotcha を保持する（分業の詳細は `../CLAUDE.md`）。

## source of truth

| ページ | 役割 |
|---|---|
| [SPEC](SPEC.md) | ★ Codex 向け実装の source of truth。CLI 動詞 ＋ data model ＋ MVP。上書き更新で現状を表す |
| [why-design-B](decisions/why-design-B.md) | なぜこの形か。Scrapbox を Co- / グラフに分解、B を選んだ理由 |
| [persistence-custom-format](decisions/persistence-custom-format.md) | 保存形式は独自フォーマット（Markdown ではない＝逆リンク維持の発生源）。読込は import adapter の別責務。MVP は Cosense JSON export を読む |

## concepts/

_まだ無し。SPEC の各原理（read＝近傍同梱 / 行リンク / 赤リンク＝自己宛キュー / identity-without-name）が育ったら切り出す。_

## entities/

| ページ | 役割 |
|---|---|
| [cosense-json-export](entities/cosense-json-export.md) | MVP 入力 = Cosense JSON export の**実物確認スキーマ**。import adapter の source of truth。lines に id 無し（grasp 採番）・link graph 未保存（text parse）・`[...]` overloaded・wanted ~45700→ranking 必須 |

## メタ

- [[log]] — 出来事の時系列（現状ではない）
