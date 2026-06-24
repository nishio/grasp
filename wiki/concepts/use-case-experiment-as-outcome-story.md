---
type: concept
summary: ユースケース実験は「ユーザがこう依頼したら、こういう有用な結果が得られる」という outcome story として記録する。実装上の摩擦や gotcha だけでなく、結果がユーザにとっていい感じかを評価対象にする。
sources:
  - nishio feedback 2026-06-24: ユースケース実験はユーザがこういうことをしたらこうなります、という事例で、いい感じの結果になることが好ましい
  - [[cross-project-reference-acquire-2026-06-24]]
  - [[persona1-user-test-2026-06-23]]
  - [[ai-consumer-feedback-2026-06-23]]
  - [[grasp-backlog]]
---

# concept: use-case experiment as outcome story

ユースケース実験は、単に「この作業で何が壊れた / 何が未実装だった」を集める dogfood ではない。coding agent 向けには次の形で残す:

> ユーザがこういうことをしたら、grasp はこう振る舞い、こういう有用な結果が得られる。

したがって成功条件には、実装上の到達可否だけでなく **結果がユーザにとっていい感じか** を含める。`いい感じ` は曖昧な賞賛ではなく、少なくとも次を満たす状態:

- ユーザの自然な依頼が、短い手順で再現できる。
- 出力が raw dump だけでなく、読む・判断する・次に使う単位にまとまっている。
- 範囲、抽出ルール、coverage、失敗件数、partial corpus caveat が明示される。
- その事例を次のユーザや agent が「この用途ならこう使えばよい」と真似できる。

## Why

`grasp` は AI が CLI で graph substrate を体験する道具なので、評価も CLI primitive の存在確認だけでは足りない。良い primitive でも、ユースケース実験の結果が「長大 JSON を生成した」「途中で script を書いた」「gotcha が分かった」だけで終わると、ユーザ価値の事例にならない。

逆に、少し摩擦があっても、最後に「依頼 → コマンド/手順 → bounded artifact → caveat → 次の判断」が揃えば、use case として強い。[[persona1-user-test-2026-06-23]] や [[ai-consumer-feedback-2026-06-23]] はこの型に近い。

## Recording contract

ユースケース実験を file back する時は、実装 gotcha と outcome story を分ける:

- **Outcome story**: ユーザの依頼、対象 corpus、実行した grasp surface、結果の形、件数、代表例、ユーザにとっての価値。
- **Friction / backlog**: 途中で必要になった fallback script、CLI 欠落、遅さ、API 制約、diagnostic 不足。
- **Quality judgement**: 今の結果は「いい感じ」か。raw artifact だけなら、何が足りないと再利用可能な事例になるか。

## Villagepump extraction lesson

2026-06-24 の `villagepump` 日記ページから `[nishio.icon]` 付き段落を抽出する実験では、公開 API から 2,079 日記ページを読み、1,481 hit pages / 6,488 paragraphs を抽出できた。これは到達としては成功。

ただし outcome story としてはまだ弱い。最終結果は raw Markdown / JSON artifact で、`[nishio.icon]さん` のような言及も含む broad extraction だった。ユーザにとってより「いい感じ」にするには、少なくとも次を選べる必要がある:

- `author marker` としての `[nishio.icon]`、単なる `[nishio.icon]さん` 言及、reaction icon list を分類する。
- 抽出結果を全部出すだけでなく、期間別・件数・代表段落・外れ値を bounded summary にする。
- `grasp acquire` / hosted acquisition surface で同じことを再現でき、custom one-off script に依存しない。

この不足は失敗ではなく、ユースケース実験が次に実装すべき surface と output contract を露出した、という扱いにする。

## Icon-history report lesson

上の raw 抽出を `nishio in villagepump: 公開共同日記から見る grasp 前史 30 scene` へ再構成した過程で、さらに次が分かった。

- **抽出と report composition は別工程**。前者は deterministic に「範囲内の hit と subtree」を返す仕事、後者は theme selection / representative scene / narrative arc / caveat を組む仕事。CLI が全部を narrative 化する必要はないが、agent が narrative 化しやすい候補集合・分類・metadata を返す必要がある。
- **broad `[icon]` hit は分類なしでは読めない**。author marker、文末署名、prefix speaker、reaction icon list、`[nishio.icon]さん` 型の言及が混ざる。report の前段に `icon_hit_kind` のような分類が要る。
- **「いい感じ」は代表例の選び方に依存する**。件数上位だけではなく、時系列上の転換点、設計思想へ接続する scene、共同体境界を示す scene を拾うと、raw dump が outcome story に変わる。
- **source anchor は line index だけでは弱い**。手作業で候補を拾うと line index の取り違えが起きた。hosted API が line `id` を返すなら、report artifact は page URL + line index だけでなく line id / possible line anchor を保持するべき。
- **artifact の言語はユーザの言語に合わせる**。最初の report draft は英語寄りになり、今回の文脈では弱かった。ユーザが日本語で依頼している use-case report は日本語で出すのが自然。

この実験の product implication は、`grasp report icon-history` のような固定 command を急ぐことではなく、**slice acquisition → hit classification → representative candidate bundle → agent-authored bounded report** という分業を見える surface にすること。

## Cross-project reference lesson

[[cross-project-reference-acquire-2026-06-24]] は outcome story としては `villagepump` 抽出より強い:

> `/nishio` で `[/` を探すと、他 Cosense project への参照が bibliography として見つかる。grasp が `.icon` や root refs を除いて semantic refs を ranking し、読める project の referenced pages を partial acquire すると、ユーザは `/nishio` の外側にある AI/Cosense/Plurality/熟議/人物辞書の近傍 map を得る。

この結果は「いい感じ」に近い。理由:

- ユーザの自然な依頼から始まっている。
- 取得範囲と partial corpus caveat が言える。
- 代表 cluster と reciprocal `/nishio` refs があり、次に読む場所を選べる。
- `[/project/page]` が seed bibliography として機能する、という再利用可能な知見がある。

一方で、one-off script / `.icon` filtering / `cosense` PATH wrapper / all-failed acquisition warning は surface gap。したがってこの実験の product implication は「cross-project refs discovery → semantic seed generation → acquire → bounded summary」を標準 workflow に寄せること。

2026-06-24 follow-up: `cross-project-refs --semantic-only --seed-dir` により、parsed cross-project refs discovery、`.icon` / root / self 分類、semantic seed-file generation、acquire command bundle までは first-class surface になった。`acquire` fetch-stage diagnostics により `cosense` / `node` command-env と all-failed warning も返るようになった。さらに `cross-project-acquire` により、semantic seed titles から複数 project を `<project>:semantic` namespace へ一括 partial acquire し、project ごとの fetched / failed / diagnostic / page sample / reciprocal refs / top internal links を bounded summary として返せる。残る gap は、seed discovery phase の環境診断と、取得後 signal の cluster / narrative handoff。

2026-06-24 process observation: the `.icon` issue also clarified a boundary of `search`. `grasp search` answers "which lines contain this text / boolean expression?", not "which parsed links on this line have this target class?". `NOT .icon` is sometimes useful as a quick line-level approximation, but it is not a semantic/icon/root classifier. For use-case experiments, this distinction matters: if the outcome depends on parsed links, the report should say so and avoid presenting clever text search as the real surface.

## Open Questions

- `いい感じ` の最低基準を command ごとに持つか、use-case report template として Skill 側に持つか。
- 巨大抽出系の結果 summary は CLI primitive にするか、agent layer の report composition に任せるか。
- hosted line id を Cosense/Scrapbox の安定 anchor として report artifact に使えるか。page URL + line index だけでは長期参照に弱い。
