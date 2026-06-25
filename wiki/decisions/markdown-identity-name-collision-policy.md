---
type: decision
summary: Markdown mirror の duplicate title / alias collision は import error の UX 問題ではなく、Scrapbox の name=identity 欠陥を identity/name 分離で解く問題として扱う。page identity は path/id、display/link handle は非一意な名前として別管理し、path-qualified string を page name へ昇格しない
sources:
  - nishio 指摘 2026-06-25「これこそ同一名称で複数のページがある問題(IDと名前を分けることで解決)」
  - [[markdown-obsidian-indexed-mirror]]
  - [[wiki-forest-markdown-import-dogfood-2026-06-25]]
  - [[whole-store-graph-and-cross-project-edges]]
---

# Decision: Markdown identity と name を collision policy で分ける

決定: Markdown mirror の duplicate title / alias collision は、単に「import を止めるか止めないか」の問題として扱わない。これは Scrapbox / Markdown の visible name を identity にしていることの限界であり、grasp の核である `identity-without-name` を Markdown adapter に適用する問題である。

## 分離するもの

- **page identity**: `(project, page_id)`。Markdown source では frontmatter `id` があればそれを使い、無ければ relative path 由来の stable id を使う。identity は unique でなければならない。
- **source address**: relative path。source file を指す locator / fallback handle であり、表示名ではない。
- **display name**: frontmatter `title` / first H1 / file stem から得る人間向け title。非一意でありうる。
- **link handle**: wikilink target, file stem, frontmatter aliases など、リンク解決に使われる名前。1 handle が 0 / 1 / N identities に束縛されうる。

path は一意性を持つが、path-qualified string を page name に混ぜない。`foo/bar/README` のような名前は source address としては有用だが、LLM / 人間が期待する `[[README]]` の意味とは違う。

## collision の扱い

- **duplicate id**: hard error。これは同じ identity を複数 source が主張している source inconsistency。
- **duplicate display title**: identity 衝突ではない。同名の別 page として store できるべき。ただし `read Title` は曖昧なので、query は候補 identities と path / summary を返して選択を促す。
- **duplicate alias / file-stem handle**: handle ambiguity。import は page materialization を失敗させるべきではないが、`[[Handle]]` を黙って一方へ解決してはいけない。edge は `target_handle_norm=handle` として保持し、resolution status を `ambiguous` にする。
- **unresolved handle**: 従来の赤リンク。0 件束縛。

したがって将来の edge resolution は三値ではなく四値になる:

- `resolved_unique`: handle が 1 page identity に束縛される。
- `ambiguous`: handle が複数 page identities に束縛される。
- `unresolved`: handle に対応する page が無い。
- `non_semantic`: `#1` など link-shaped だが意味リンクではない annotation。これは collision とは別問題。

## v6 でも急に import softening しない理由

SQLite schema v6 は `page_handles` で handle ambiguity を表現できるが、query 実装全体はまだ normalized title が一意である前提を多く残す。`read <handle>` は ambiguity result を返せるようになった一方、`backlinks` / `related` / unresolved / Markdown outgoing edge resolution は `target_norm` を title handle として扱う。ここで duplicate title import を全面的に許すと、store は作れても retrieval の一部が暗黙に片方を選ぶ、または ambiguous handle を unresolved と誤分類する。

よって短期は structured diagnostics を出し、同名を自動改名しない。import softening を進める時は、`read` 以外の query surface と edge resolution も ambiguity-aware にする。

## 実装順

1. **diagnostic phase**: 実装済み。`MarkdownCollisionError` は title / id / alias collision の kind, key, paths, entries を返す。
2. **artifact reduction / source role phase**: 実装済みの最小形。`raw/` は heavy original dump なので `--markdown-exclude-dir raw` で除外可能。`source/` は raw を読んで作った digest / source-backed synthesis なので default exclude せず、`graph_role=source` として保持し content と同じく edge を materialize する。`drafts/` や generated temp files は `graph_role=artifact` として search には残すが outgoing edges を除外する。ただしこれは duplicate title を許す実装ではない。
3. **handle binding phase**: 最小実装済み。schema v6 で `page_handles` を導入し、`handle_norm -> page_id` は 1:N を許す。Cosense title と Markdown title / alias / source path / graph_role を materialize する。旧 `title_aliases` metadata は unique handle の fast path に残る。
4. **ambiguous query phase**: `read <handle>` は最小実装済み。N 件束縛を見たら、勝手に選ばず `ambiguity.type=handle_ambiguity` と title / page_id / source path / graph_role を返す。`backlinks <handle>` など他 query surface は未実装。
5. **edge resolution phase**: edges に source handle と resolution status を持たせる。unique の時だけ target page identity に解決し、ambiguous の時は unresolved hub とも existing page とも別に扱う。
6. **explicit identity read phase**: 最小実装済み。`read --page-id <id>` または `read --path <relative-path>` で identity を指定して読む。path は selection key であり page name ではない。

`import-forest` orchestration はこの後でよい。先に作ると、既知 collision を集計する command になり、identity/name 分離の問題を隠す。

## Query UX

`read README` が複数候補を持つ場合、JSON は次のような形を返す:

```json
{
  "query": "README",
  "page": null,
  "ambiguity": {
    "type": "handle_ambiguity",
    "handle_norm": "readme",
    "candidates": [
      {"page_id": "...", "title": "README", "path": "pkg/a/README.md", "graph_role": "content"},
      {"page_id": "...", "title": "README", "path": "pkg/b/README.md", "graph_role": "source"}
    ]
  }
}
```

text output では「候補 N 件。`read --path ...` か `read --page-id ...` で選ぶ」と短く出す。

## 非目標

- path-qualified title を自動生成して page title にすること。
- duplicate alias を黙って捨て、リンクを unresolved に見せること。
- duplicate handle の一方を import order / lexical order で勝手に選ぶこと。

## Open Questions

- `read --path` の path は project root relative で足りるか、source folder identity も必要か。
- frontmatter `id` が重複した時、path-derived id へ自動 fallback してよいか。現時点では hard error。
- ambiguous handle に対する `backlinks` は「ambiguous handle への incoming lines」として返すか、候補 page ごとの resolved backlinks に分けるか。
- `page_handles` と [[whole-store-graph-and-cross-project-edges]] の weak cross-project title match を将来同じ handle 層に統合するか。

## Related

- [[markdown-obsidian-indexed-mirror]]
- [[wiki-forest-markdown-import-dogfood-2026-06-25]]
- [[grasp-backlog]]
