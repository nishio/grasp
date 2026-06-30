---
type: entity
summary: 2026-06-30、throwaway な mode2 SQLite-SSoT store（~/llm-wiki 743 pages を adopt）に2プロセスを並行 loop 編集させ「並行下で何が壊れるか」を実走観測した記録。結論は2つ。(A) 無協調 mode2 は silent lost-update を起こす — 同一 hot pages を奪い合う2プロセスで 50 write 中 24 が `database is locked` も WRITEFAIL も出さず last-writer-wins で消え、なお `write-status --no-journal --strict` は GREEN（store↔projection 整合は守るが content の喪失は検出しない＝整合≠正しさ）。(B) `claim-page` soft lease + `--defer-projection` を入れると 25 write で lost=0、staleness は strict が exit 1 で正しく検出、ただし ~50% の iteration が他者 claim で skip され編集が捨てられる（throughput 半減＋dropped-work）。cutover の go/no-go 材料。
sources:
  - session 2026-06-30 stress run, throwaway store /tmp/grasp-mode2-stress/store.sqlite, project llmwiki（~/llm-wiki md-only copy 743 pages / 94,327 lines / 9,958 edges を adopt）
  - harness: /tmp/grasp-mode2-stress/agent_loop.sh（read→append MARK→write-page の RMW loop, 2 procs × 25 iters, hot pages 10）
  - 関連: [[sqlite-write-concurrency]] / [[parallel-agent-write-incident-2026-06-26]] / [[adoption-trust-gradient]] / [[grasp-backlog]]
---

# Mode2 parallel-edit stress test 2026-06-30

## なぜやったか

cutover 判断「dogfood を mode2（grasp=SSoT）に倒すか」（[[adoption-trust-gradient]]）の go/no-go 材料を、データ損失リスク 0 の throwaway store で実走させて得るため。北極星は並行 agent が同一 canonical store を共有する基盤なので、まさに「2プロセスが同じ store を同時編集したとき何が壊れるか」を観測した。2026-06-26 incident（[[parallel-agent-write-incident-2026-06-26]]）以降ガードが大きく進んだ後の current state での再検証である。

## セットアップ

- throwaway store `/tmp/grasp-mode2-stress/store.sqlite`（default `.grasp/file-back.sqlite` と分離、消えてよい）。
- project `llmwiki` = `~/llm-wiki` の md-only コピー（raw/drafts 除外、743 pages）を `adopt-markdown`。**adopt は12秒で完了**。
- 2 プロセスを「2 agent」とした。並行下で store/projection の race を踏む単位は**プロセス（multi-process single-owner）**であり、LLM 推論を挟むと遅く非再現になるため、各プロセスが `read → MARK 行 append → write-page` の RMW loop を回す純 substrate 試験にした。
- workload: hot pages 10 枚（>=8 行）を2プロセスが奪い合う（衝突確率最大化）。各 25 iteration。

## Round A — 無協調・write 毎 full projection export

- 各 write は `write-page --output wiki --no-journal`（projection を毎回 full export）、claim なし。
- 結果: agent1=25 OK / agent2=25 OK、**`database is locked` 0 / WRITEFAIL 0**。だが store（authority）に生存した MARK は **agent1=25 / agent2=1**。
- → **50 write 中 24 が silent に消滅**（last-writer-wins）。エラーは一切出ず両 agent は全 write を OK と報告。SQLite の文ロックは効いても `read→write-page` の**論理 RMW が isolate されない**（[[sqlite-write-concurrency]] (c) の実証）。
- さらに Round A 後の `write-status --no-journal --strict` は **strict_ok: true / projection_ok: true / event_streams_match: true（exit 0）**。**現行 strict guard は lost-update を検出できない** — store↔projection 整合は守るが、並行で消えた content は見ない。**整合 ≠ 正しさ**。「postwrite が緑なら安全」は並行 write では成り立たない。

## Round B — `claim-page` soft lease + `--defer-projection`（mode2 想定モデル）

- 各 iteration: `claims` を見て対象 page を他 actor が active claim 中なら skip、でなければ `claim-page` → read → `write-page --no-journal --defer-projection` → `release-claim`。
- 結果: agent1=12 OK / 13 skip、agent2=13 OK / 12 skip。store に生存した MARK は **agent1=12 / agent2=13 = lost 0**。
- defer-projection 中は `write-status --no-journal --strict` が **exit 1（STALE を正しく報告）** → batch `export-markdown` 後に exit 0。Round A の沈黙と対照的に**検出可能**。
- → claim による直列化 + per-write export 廃止で **lost-update 0**。ただし代償: **~50% の iteration が back-off で skip**（throughput 半減）。しかも現 loop では skip した編集は**捨てられる**（retry/merge せず）＝別種の喪失。

## 結論（cutover への含意）

「倒せるが無条件ではない」。mode2 + 並行 agent を成立させる前提条件:
1. `claim-page` を soft signal から**実効的な直列化**（file-back lock 相当）へ格上げ（soft lease には check→claim の TOCTOU 窓が残り、本 run の 0-loss は窓を踏まなかった幸運も含む）。
2. claim で skip した編集の **retry / merge**（dropped-work をなくす）。
3. **content-level の lost-update 検出 guard**（`write-status --strict` の整合チェックでは不足）。
4. `--defer-projection` を並行 write の default にする（per-write full export の clobber 経路を断つ。staleness は strict が捕捉できる）。

Round B が「協調さえ入れれば 0 loss」を示したので方向は正しい。

## Finding（実装ブロッカー）: 高密度グラフの projection/graph compute が病的に遅い

この実験結果を grasp wiki に file back しようとして発覚。`grasp --project grasp-wiki write-page ... --no-journal --output wiki`（grasp-wiki は ~60 pages / 7.6MB と小さいが wikilink が高密度）が **96% CPU で 8 分超 spin して未完**。同パターンで `/nishio` import（25,791 pages）も 6 分で中断していた。**コーパスサイズは無関係**（巨大 nishio と極小 grasp-wiki で同症状）。切り分け: read-only の `grasp --project grasp-wiki export-markdown --output wiki --check` 単体が 25s でタイムアウト → **遅いのは write でなく projection/graph compute path**。対照的に temp の `llmwiki`（743 pages だが edge 密度 ~13/page と低い）の write-page は Round A/B で高速。

∴ 仮説: **projection / graph materialize が link 密度に superlinear**（O(edges²) 級の疑い）。これは grasp が標的にする Scrapbox 型の密リンクグラフで正面から効く。環境は Homebrew Python 3.14.5 / RSS は両症状とも ~18MB で平ら（tight loop で allocation していない）。なお過去（2026-06-29）の grasp-wiki file-back は完走しており、**確定 regression かは未切り分け**（Python 3.14 か最近の変更か corpus 成長か要二分）。この finding により本ページの file-back は grasp write-first を断念し direct Markdown patch fallback で着地した。

## Caveats / 未確定

- **soft claim の 0-loss は1 run の観測**。check→claim は別コマンドで TOCTOU 窓があり、より速い timing / 3+ agent では skip 漏れ→lost が起きうる。回帰試験として固定し再現性を測るべき。
- Round A の極端な非対称（agent1=25 / agent2=1）の機序は未分析。headline（silent loss）は揺るがない。
- **大規模 import は本 run では未完**: `/nishio`（25,791 pages / 123MB）の `import` は CPU 6分超で store に1行も書けず中断した。ただし [[read-vs-grep-benchmark-2026-06-24]] は同コーパスを 2026-06-23 に import 済みと記録しており、**確定的な regression ではない**（性能の再計測が必要な open item）。本 stress は llmwiki adopt で実施した。
