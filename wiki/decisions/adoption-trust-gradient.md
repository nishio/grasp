---
type: decision
summary: grasp の採用は authority の矢印が逆な2モードの信頼勾配として設計する。mode1（Markdown=SSoT・grasp=捨てられる派生 index）は新規/低信頼ユーザの永続オンランプ、mode2（grasp=SSoT・Markdown は export-only projection）は信頼が育った高信頼端 dogfood の目標形。両モードは同一コンテンツに同時 on 不可（authority は1本）。mode1→mode2 の信頼を稼ぐ手段は cutover 条件と同一の grasp-native recovery/review surface（二重役割で優先度が上がる）。mode2 の北極星は並行 agent の共有知識基盤。協調レイヤは単一 agent では不要に degrade。
sources:
  - nishio との設計対話 2026-06-28（新規ユーザは grasp を信じるまで mode2 にならない / 我々は mode2 + 並行 agent 知識共有へ）
  - nishio feedback 2026-06-29（README の「SSoT は移動しません」は言いすぎ。正しくは段階的に移行できる）
  - [[markdown-obsidian-indexed-mirror]]
  - [[native-authority-markdown-projection]]
  - [[positioning-two-personas]]
  - [[parallel-agent-substrate-goal]]
  - [[sqlite-write-concurrency]]
id: b2d110b7910ad222faf19a44
title: adoption-trust-gradient
---

# Decision: 採用は信頼勾配（mode1 オンランプ → mode2 dogfood）

決定: grasp の採用経路を、**authority の矢印が逆な2モードを両端とする信頼勾配 (trust gradient)** として設計する。低信頼端から入り、grasp を信頼できて初めて高信頼端へ進む。両端は別物でなく1本の連続軸。

## 2モード（authority の向き）

- **mode1 — Markdown=SSoT、grasp=派生 index。** authority は Markdown ファイル。grasp は検索・リンクグラフを materialize する read-only mirror（[[markdown-obsidian-indexed-mirror]]）。壊れたら捨てて Markdown から再 import すればよい。
- **mode2 — grasp=SSoT、Markdown=export-only projection。** authority は grasp native store（[[native-authority-markdown-projection]]）。人間/agent は Markdown を直接編集せず `grasp write` が store を更新し projection を再生成する。

**authority は同一コンテンツに対して1本の矢印。** mode1 と mode2 を同じページに同時 on にはできない（両方 authority にすると lost-update＝[[parallel-agent-write-incident-2026-06-26]] の症状）。混在には reject/adopt/merge ポリシーが要る。現設計は mode2 を目標、mode1 を on-ramp / emergency として時系列・コンテンツ集合で分ける。

## 信頼勾配（なぜこの形）

新規ユーザは、若く binary で不透明な grasp に唯一コピーを預けることを day-1 では受け入れない。だから:

- **低信頼端（新規ユーザ）= mode1。** grasp は捨てられる派生 index ＝ **データ損失リスク 0** が安全の根拠。これが on-ramp の成立理由。
- **高信頼端（我々・dogfood）= mode2。** grasp が唯一コピーを持ち、並行 agent が共有する基盤。

信頼勾配とは「safe で git で人間可読な Markdown から、どれだけ authority を grasp へ移す勇気があるか」の連続量。

**重要: mode1 は adopt phase（cutover 前の一時状態）でなく永続オンランプ。** [[native-authority-markdown-projection]] は mode1 を「cutover 前の source import か emergency path」と書くが、新規/低信頼ユーザにとって mode1 はずっと正規にサポートされる低信頼モードであり、mode1→mode2 は migration でなく信頼の漸進。

## 非自明な梃子（投資判断）

mode1→mode2 へ進める信頼を稼ぐのは、**cutover 条件と同一物**＝ grasp-native recovery / review surface（`history` / `revert-plan` / safety-net としての Markdown projection）。「grasp はデータを失わない、git-diff-of-md なしで復元・review できる」と確信できて初めてユーザは authority を移す。∴「信頼を稼ぐ作業」と「mode2 化の作業」は別努力でなく **1つを作れば両方満たす** → recovery surface の優先度が二重に上がる。

## 高信頼端の北極星

mode2 の到達目標は **並行 agent が同一 canonical store を共有して知識共有しながら開発する基盤**（[[parallel-agent-substrate-goal]]）。これは grasp を write 先だけでなく協調のための read 先にする。

## スコープの歯止め（degrade）

協調レイヤ（in-flight 認識 / claim / lease）は **単一 agent 利用では一切要らない形に degrade** する。協調コストを低信頼端（新規 mode1 ユーザ）に漏らさない。要求が増えるのは高信頼端だけ。

## positioning-two-personas との関係

[[positioning-two-personas]] は audience を persona1（JP Cosense ヘビーユーザ＝nishio dogfooding）/ persona2（世界の Markdown 束ユーザ）の2層に分けた。本 decision はそれを **authority-direction の連続軸**として一般化する: persona の別でなく「authority をどれだけ grasp へ移したか」の信頼度で並べ、mode1=低信頼端・mode2=高信頼端とする。persona2 への on-ramp が mode1（捨てられる index）であること、driver の dogfood が mode2 であることは両 decision で整合する。

## Updates

### 2026-06-29: 外向き表現は「SSoT は動かない」ではなく「初期移行を要求しない」

README wording で「SSoT（信頼できる元データ）は移動しません」と書いたが、これは mode1 だけを不変の約束として読ませるので強すぎる。正しくは **最初から SSoT 移行を要求しない** であり、mode1（既存 Markdown / Cosense が SSoT、grasp は派生 index）から始めて、信頼が育ったら mode2（grasp が SSoT、Markdown は projection）へ段階移行できる、という信頼勾配である。

含意: 外向き pitch / README / onboarding docs では「grasp never moves your source of truth」と断定しない。「start without moving your source of truth」「no up-front migration」「gradual migration to grasp as authoring store」のように、mode1 の安全性と mode2 への移行可能性を同時に出す。mode1 を永続オンランプとして守ることと、mode2 を高信頼端の目標として持つことは矛盾しない。

## Open Questions

- mode2 で人間/別 agent が Markdown を直接編集した場合の reject / adopt / merge（[[native-authority-markdown-projection]] の Open Q と同じ）。信頼勾配では「mode2 では Markdown は read-only 出力、編集は grasp 経由」が最もクリーン。
- 信頼を「測る」指標は何か（recovery を何回成功したら mode2 に進めてよいか）。
- mode1 ↔ mode2 を **コンテンツ集合単位**で混在運用する時の境界管理。
