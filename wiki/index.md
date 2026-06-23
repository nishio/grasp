# grasp — 開発 wiki index

単一 AI 所有の local な Scrapbox 型グラフ知識ストア `grasp`（graph × scrap / 把握）の開発 wiki。
Codex が実装し、本 wiki が spec・設計判断・gotcha を保持する（分業の詳細は `../CLAUDE.md`）。

## source of truth

| ページ | 役割 |
|---|---|
| [SPEC](SPEC.md) | ★ Codex 向け実装の source of truth。CLI 動詞 ＋ data model。上書き更新で現状を表す |
| [why-design-B](decisions/why-design-B.md) | なぜこの形か。Scrapbox を Co- / グラフに分解、B を選んだ理由 |

## concepts/

_まだ無し。SPEC の各原理（read＝近傍同梱 / 行リンク / 赤リンク＝自己宛キュー / identity-without-name）が育ったら切り出す。_

## entities/

_まだ無し。依存ライブラリ・既存ツール（cosense-cli 等）の比較が溜まる。_

## メタ

- [[log]] — 出来事の時系列（現状ではない）
