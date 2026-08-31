---
type: concept
summary: hosted Cosense は rapid read を HTTP 429 で絞る。cosense CLI は "HTTP 429" テキストのみで Retry-After 非露出。実測(2026-08)はリセット分オーダー(token-bucket的)・fresh window で ~57 連続 fetch は 0 失敗・数百連打で通過率20-33%。mitigation は `_run_json` の 429 検知＋指数backoff retry (commit 55240a7, env GRASP_COSENSE_*)。scope=retry-only で pacing と sync 部分コミットは未実装。
sources:
  - grasp/cosense_cli.py
  - tests/test_cosense_cli.py
  - "[[sqlite-write-concurrency]]"
  - "[[incremental-sync]]"
id: 25e40adba63f932e365b1fcd
title: cosense-fetch-rate-limit
---

# Cosense hosted fetch のレート制限 (HTTP 429)

`sync` / `acquire` / `refresh-page` は hosted Cosense を `@helpfeel/cosense-cli` の `readPage` / `listPages` / `searchFullText` 経由で読む。rapid な連続 read は **HTTP 429 Too Many Requests** で絞られる。管理者 export が無い project を per-page で舐める `acquire --full-list` と、変更ページを全 fetch する `sync` が特に踏む。

## 実測 (2026-08, private project 2 件)

公式なレート閾値・リセット窓は非公開。観測は以下:

- **Cloudflare 前段・認証アカウント単位** — 429 は `cf-ray` 付き。未認証 curl は 401、認証済み CLI は 429。IP/project でなくログイン中トークン単位。
- **リセットは分オーダー (token-bucket 的)** — 429 を返した当該ページが数分後に 200 復活。時間/日単位ではない。
- **fresh window で ~57 連続 fetch は 0 失敗**。数百件を無休止連打すると通過率 **20-33%** まで低下 (窓が枯れ、回復した分だけ数件おきに通る)。
- 安全域 ≈ **1 バースト 50-60 件 + パス間 2-3 分** ≒ 20-25 req/min。この刻みなら 429 を踏まずに完走できた。
- **cosense CLI は `Retry-After` を露出しない** — grasp が見えるのは stderr の "HTTP 429" 文字列だけ。∴ 正確な待機秒は読めず、盲目的 (blind) 指数 backoff にするしかない。

## Mitigation (実装済み, commit 55240a7)

全 hosted read が通る choke-point `_run_json` ([grasp/cosense_cli.py](grasp/cosense_cli.py)) に 429 retry を一枚噛ませた。listPages / readPage / searchFullText 全経路を通るので **sync も acquire も refresh-page も**この一箇所で救われる。

- `classify_cosense_cli_failure` に **`rate-limited`** クラスを追加 (`429` / `too many requests` / `rate limit`)。本物のエラー (permission / page-not-found / command-env) と区別する。
- `_run_json`: `rate-limited` を検知したら `sleep(base·2^n)` (上限 `max_delay`) で `max_retries` 回まで待って再試行。使い切ってなお 429 なら従来通り `CosenseCliError` を送出。
- env knobs: `GRASP_COSENSE_MAX_RETRIES`=5 / `GRASP_COSENSE_RETRY_BASE_SECONDS`=2.0 / `GRASP_COSENSE_RETRY_MAX_SECONDS`=60.0。`CosenseCliClient.sleep` は注入可能で、test は実時間を消費しない (`RateLimitRetryTest`)。
- 実証: 862p の private project 862p の `acquire --full-list` が **0 失敗**で完走 (retry 前は同じ acquire で 577/862 が 429 失敗)。

## scope の限界 (未実装, backlog 候補)

意図的に **retry-only** に絞った (owner 判断)。残る弱点:

- **proactive pacing (最小リクエスト間隔) は無い** → 依然として連打で窓を枯らしやすい。枯れても待って回復する reactive のみ。
- **sync は部分コミットしない** — `sync_from_cosense` は changed page を全 fetch してから最後に一括 upsert。retry で 429 は吸収されるが、retry を使い切って落ちると 1 件もコミットされない (acquire は per-page try で耐える)。
- Retry-After 非露出の制約は不変。

## 関連

- [[sqlite-write-concurrency]] — この 429 待ちと直交して、別 session が shared default store を握ると fetch 成功後の最終 write が `database is locked` で全喪失しうる (acquire の fetch-then-replace 構造)。
- [[incremental-sync]] — sync の設計 (updated 降順 listPages + changed 判定)。
