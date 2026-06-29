---
type: entity
summary: 2026-06-29 に public web 上の grasp 直接言及を検索した結果。直接 mention は HN/Reddit では見つからず、Scrapbox/Cosense 圏（井戸端・motoso・stao）に集中。特に inajob の非 admin public backup + OpenCode + grasp skill 試用が、persona1 周辺の organic adoption と public project outsider persona の証拠になった。
sources:
  - https://scrapbox.io/villagepump/grasp
  - https://scrapbox.io/villagepump/grasp%E3%82%92%E8%A9%A6%E3%81%99%28inajob%29
  - https://scrapbox.io/motoso/Cosense%E3%81%AE%E5%86%85%E5%AE%B9%E3%82%92%E3%83%AD%E3%83%BC%E3%82%AB%E3%83%ABLLM%E3%81%8B%E3%82%89%E8%AA%AD%E3%82%80
  - https://scrapbox.io/stao/%E3%82%BF%E3%83%95%E3%83%A9%E3%83%95
  - [[hn-reddit-grasp-adjacent-survey-2026-06-29]]
  - [[takker-opencode-villagepump-test-2026-06-24]]
id: 9da123be425cec3a4edaaf46
title: Grasp organic mentions 2026-06-29
---

# entity: Grasp organic mentions 2026-06-29

目的: 「世の中で grasp 自体が言及されているか」を直接検索し、organic adoption / visibility の現在地を記録する。前回の [[hn-reddit-grasp-adjacent-survey-2026-06-29]] は隣接需要の survey であり、これは **grasp 直接 mention** の survey。

## Findings

- **直接 mention は HN/Reddit では見つからなかった。** `nishio/grasp` / `github.com/nishio/grasp` / Scrapbox/Cosense/CLI などで絞っても、有意な HN/Reddit mention は確認できなかった。したがって cold persona2b への organic spread はまだ起きていない。
- **直接 mention は Scrapbox/Cosense 圏に集中。** 井戸端の `grasp` ページ、`graspを試す(inajob)`、motoso の `Cosenseの内容をローカルLLMから読む`、stao の `タフラフ` が見つかった。
- **inajob 試用が最重要 data point。** 非 admin が public backup release から Cosense data を得て、OpenCode + grasp skill で実際に「inajob について調べる」を走らせている。これは nishio/takker の insider dogfood より一段外側の実利用。
- **motoso のページは positioning の外部再表現。** cloud SSoT / offline unavailability / Co overhead から local SQLite へ落とす、という persona1 向け価値が第三者側の言葉で説明されている。
- **stao の言及は adoption より visibility。** 「井戸端で話題になっていた grasp」として扱われており、周辺コミュニティ内では名前が届き始めている。

## Learnings

1. **persona1 周辺では organic adoption が始まっている。** まだ狭いが、nishio 以外の人が自分の agent / public project / local data で試している。
2. **価値は speed より outcome discovery として出る。** inajob 試用の強い点は、検索速度ではなく「数問で自分でも面白い切り口が出た」こと。[[use-case-experiment-as-outcome-story]] の外部例に近い。
3. **非 admin public project reader は別 persona。** export admin でなくても、public backup release や public API から local graph reader を作り、agent に読ませたい人がいる。[[grasp-backlog]] の P5（public hosted Cosense partial-acquire researcher）を具体化する。
4. **tool routing が弱い。** inajob 観測では、明示的に grasp と言わないと agent が cosense-cli など別 skill を使うことがある。grasp skill は「いつ cosense-cli でなく grasp を使うか」をさらに強く書く必要がある。
5. **HN/Reddit はまだ launch channel であって organic channel ではない。** 現時点で外へ自然伝播しているのは Scrapbox/Cosense 圏。persona2b へは concrete demo / Show HN / Reddit post が必要。

## Implications

- 外向き demo は、まず inajob 試用を抽象化した **public project outsider story** が強い: public backup -> local import -> OpenCode/grasp skill -> 2-3 questions -> source-backed discovery。
- HN/Reddit 向けには「もう話題になっている」ではなく「隣接需要はあるが、grasp 自体はまだ未露出」と見なす。
- README / Skill の routing は、overlap する `cosense-cli` との使い分けをもう一段明確にする。hosted write / fresh hosted state は cosense-cli、offline local graph read / bounded multi-hop retrieval / project memory は grasp。

## Open Questions

- public backup release 導線を docs/demo に入れるか。admin export 前提より open だが、各 public project の backup availability に依存する。
- inajob の outcome story を README/demo に引用してよいか。公開ページだが、外向き docs に使うなら表現を慎重にする。
- tool routing は skill prose だけで足りるか、Codex/Claude command 側にも explicit trigger examples が必要か。
