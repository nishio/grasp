---
type: decision
summary: 実装言語（Python/Node/Rust/Go）と配布チャネル（PyPI/npm/Homebrew/GH Releases）は独立な2軸。言語論点は実測で溶ける（仕事は全部 SQLite=言語非依存、warm store で Python 起動 ~30ms・read ~83ms）。∴ 長期の実体は配布で、当面は「依存ゼロ Python を pipx で配る」で足りる。native(Go/Rust)→npm 配布は「Python 不要 agent 環境を相手にする」trigger が立った時の手で、SQLite store 契約が段階移行を de-risk する
sources:
  - nishio 指示 2026-06-23「長期視点で Python/Node/Rust 等を比較。Claude Code が npm で更新すること、PyPI から pip で入れる方針など考慮」
  - session 内実測 2026-06-23（warm SQLite store 238MB に対する起動/各 verb の wall time）
  - pyproject.toml（dependencies = []）, PEP 668（externally-managed-environment）
---

# Decision: 実装言語と配布チャネルは別軸。当面 Python+pipx、native は条件付き

決定: grasp の長期実装は **当面 Python のまま**。配布は **依存ゼロを保ったまま PyPI 公開 → `pipx install` で案内**（外部 consumer が出た段で）。**native binary 化（Go/Rust）→ npm 等での配布は単一の trigger が立つまで採らない**（[[delivery-cli-plus-skill]] の delivery 決定に直交する、implementation/distribution 層の決定）。

## 核心: 実装言語 ≠ 配布チャネル（"Node でネイティブビルド" の混同を解く）

nishio の問い（Python/Node/Rust で native build／Claude Code は npm 更新／PyPI は pip）は **2つの独立な軸**を含む。混ぜると誤判断する。

1. **何で書くか**（Python / Node / Rust / Go）
2. **どう届けるか**（PyPI+pipx / npm / Homebrew / GH Releases / cargo|go install）

どの言語で書いても全チャネルに配れる（esbuild・biome・swc は **Rust/Go の binary を npm で**配っている）。「npm 配布したい」は「Node で書く」を強制しない。**[[delivery-cli-plus-skill]] の CLI+Skill 境界が言語非依存**である（Skill は PATH に `grasp` があればよく、中身の言語を知らない）こととも整合する。∴ 言語選択は delivery 決定と直交する別決定。

## 言語論点は実測で溶ける（native 化の latency 便益はほぼ無い）

session 内で warm store（238MB。current default は `~/.grasp/grasp.sqlite`）に対し実測:

| 計測 | median | 含意 |
|---|---:|---|
| bare `python3 -c pass` | 33 ms | 固定インタプリタ起動 |
| `import grasp` | ~27 ms | **依存ゼロ（pyproject `dependencies = []`）ゆえ import がタダ** |
| `read`（近傍同梱）| 83 ms | ← 中核体験。[[grasp-cli-mvp]] の旧「0.7s」は cold/最適化前 |
| `backlinks` / `unresolved` | 52–54 ms | |
| `search`（`lines.text LIKE` 全行スキャン）| 178 ms | SQLite の C 実装が律速。言語非依存 |

→ **固定 Python オーバーヘッドは ~30ms** で、重い仕事はすべて SQLite（どの host 言語から呼んでも同じ C ライブラリ）。native binary（Rust/Go ~5ms 起動）に替えても 1 call あたり削れるのは数十 ms、`search` の 178ms は index 問題（FTS5 hybrid, [[fts5-trigram-search]]）であって言語ではない。**grasp が掲げる「AI が graph を流れるように体験する」（v1 実装は [[grasp-v1-implemented]]）は既に sub-100ms で達成済み**。∴ 長期の論点は実装言語でなく配布チャネルにほぼ収束する。

## 言語マトリクス（書くなら何か）

| | 起動 | SQLite | 配布の素直さ | 今 rewrite する価値 |
|---|---|---|---|---|
| **Python（現状）** | ~30ms | stdlib `sqlite3`・**依存ゼロ** | PyPI+pipx | — |
| **Node** | ~50ms（JSは binary 化しないと native 便益なし）| `better-sqlite3`=native addon / `node:sqlite`=Node22+ experimental。**最弱** | npm 純正 | 低 |
| **Rust** | ~5ms | `rusqlite`（C を bundle, static） | binary を各チャネルへ | 条件付き |
| **Go** | ~5ms | `modernc.org/sqlite`（**pure-Go・cgo 不要**）→ 全 OS を1台から cross-compile | binary を各チャネルへ | 条件付き |

- **Node-native は採らない**: SQLite で損し、runtime 依存を負い、起動便益も Bun compile しないと出ない（matrix の最悪手）。「Claude Code と同言語」は CLI+Skill 境界が言語非依存なので利点にならない。
- native に行くなら **この tool には Go が一番素直**（pure-Go SQLite × 楽な cross-compile = npm の per-platform 配布が安い）。Rust は binary 最小・型が強い分やや cross-compile が重い。どちらも Python に対する実利は「起動 ~30ms 短縮」＋「Python 不要環境で動く」だけ。

## 配布チャネル（こっちが本論点）

| チャネル | コマンド | 前提 | 落とし穴 |
|---|---|---|---|
| **PyPI + pipx** | `pipx install grasp` | Python あり | 素の `pip` は **PEP 668 で system Python に弾かれる** → pipx 必須 |
| **npm / npx** | `npx grasp` / `npm i -g` | Node あり（agent 環境で温まっている）| pure-JS だと SQLite 弱。**native binary を optionalDependencies で配る形なら最良** |
| **Homebrew** | `brew install grasp` | mac 中心（nishio は darwin）| tap 運用 |
| **GH Releases + `curl\|sh`** | universal | なし | 自前 updater |
| **cargo / go install** | dev 用 | toolchain | end user 不可 |

**「Claude Code が npm で更新する」の正体**: npm は agent 環境で温まったチャネル。ただし Claude Code 自身が npm 配布から native binary + 自前 updater へ寄せている — これは **行き先が native binary** で npm は移行/到達チャネルだという signal。だから *もし* native に行くなら最終形は「**native binary を npm でも配る**」（esbuild モデル）が reach と runtime-free を両取りする収束点。

## 決定（段階戦略・trigger 付き）

grasp 固有の事実が判断を決める: **真のユーザは当面 nishio + その AI**（40+ wiki・Codex, [[why-not-scrapbox-clone]]）／**surface はまだ動いている**（write・identity・transclude 未実装, [[grasp-backlog]]）／**SQLite store が言語非依存の契約**。

1. **今〜write/identity 安定まで: Python のまま。** 依存ゼロ・sub-100ms 達成済み・surface churning 中。凍る前の rewrite は over-spec。自分の複数 wiki 横断は git から `pipx install`（隔離 venv で PEP 668 回避）か、現状の editable install + skill symlink を維持。**PyPI 公開はまだ不要**。
2. **少数他者 / 複数マシンに配る段: PyPI 公開 → `pipx install grasp` を案内**（素の pip でなく）。依存ゼロを保てばコストはほぼゼロ。
3. **Python が入らない agent 環境を相手にし始めたら、初めて native を検討。** その時は **Go（or Rust）→ static binary → npm(optionalDependencies) + Homebrew + GH Releases**。**同じ `.sqlite` を読むので、まず hot read path（read/backlinks/related）だけ native 化し import/sync は Python に残す incremental migration が可能** — store 契約が rewrite を de-risk する。
4. **Node-native は採らない。**

### revisit の trigger（早すぎる移行を封じる）
どれも 2026-06-23 時点で満たさない:
- (a) warm store でも実 agent loop で latency が体感問題になる
- (b) Python 不可環境で動かす必要が出る
- (c) graph 成長で 2-hop / search が SQLite を超えるデータ構造を要求する

## Open Questions

- PyPI 公開時の package 名（`grasp` は PyPI で衝突しうる）・console script 名の衝突回避。
- user-level skill（`~/.claude/skills/grasp/`）化（[[delivery-cli-plus-skill]] Open Q）と PyPI 配布の install 順序関係。Skill symlink を pip/pipx の data_files で配れるか。
- `search` の 178ms を index で詰める（FTS5 hybrid, [[fts5-trigram-search]]）のは言語選択と独立に効く — native 化より優先順位が高い可能性。
- trigger (b)（Python 不可環境）が現実に起きるか。Codex / Claude Code はいずれも Python を前提にできる環境か、要観察。
