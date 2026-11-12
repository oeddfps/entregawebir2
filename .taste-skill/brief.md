# Clean&Process contract UI brief

## Data inventory

- One or two source captures, each with a stable label and processing state.
- Four contractual answers: price range, visual presentation, keywords, and category opinions.
- Price groups keep variant, currency, conditions, comparison period, average, observed value, limits, and individual offers separate.
- Image appearances keep subjects, order, context, visibility, declared functions, and resources separate.
- Keyword groups keep definition, subject, corpus, kind, voice, language, occurrences, content units, and author independence separate.
- Opinion groups keep category, basis, aspect, sentiment, voice, quotes, counts, and published aggregates separate.
- Evidence is addressed by assertion IDs and opened from the claim it supports.
- Optional visualizations include an RDF graph and one category word cloud.
- Brand intelligence groups only backend-declared brands and joins each price group through declared `variant_refs`.
- Cross-source product matching requires an exact declared GTIN and `identity_status: resolved`; names and images are never used as identity heuristics.
- High-value and category-leader designations require explicit declared image functions on at least two sources; absent declarations remain an honest unavailable state.
- The primary users are analysts reviewing one source or comparing two sources on desktop; phone use is for status and focused inspection.
- The frequent jobs are starting an analysis, checking contract coverage, comparing supported facts, and opening evidence.

## Screen contract

- Question: What did each source actually demonstrate, with what coverage and evidence?
- Primary action: Start the selected one-source or two-source analysis.
- Finding: Partial and unavailable answers must be visible before any comparison is interpreted.
- Face: blue-grey `#f2f4f7` ground from the product's data/audit context; white working surfaces.
- Signature element: a four-question by source coverage matrix driven by `question_id`, never list position.
- Brand screen question: Which declared brands and resolved GTIN products have comparable evidence across the captured sources?
- Brand screen signature: brand galleries followed by source lanes for price groups and an exact-GTIN comparison matrix.
- Mobile: navigation folds; result tables become two-line records; graph and word cloud stay full width.
- Rejected patterns: hero copy, numbered feature cards, tinted KPI tiles, gradients, coloured chrome, inferred labels, and client-side aggregation that changes contract meaning.

## Direction

- Style: `achromatic-ledger`
- Seed: `420518857`
- Redraws: none.
