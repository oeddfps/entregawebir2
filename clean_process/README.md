# Clean&Process

Independent Python package and versioned JSON contracts for evidence-backed
content processing. Does not import, run or fetch through the scraper. Does not
implement presentation UI or choose RDF storage.

## Run

From this repository in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m clean_process clean_process/examples/input.json --output data/clean-process/example-output.json
.\.venv\Scripts\python.exe -m clean_process --write-schemas clean_process/schemas
```

The package can also be installed independently with `pip install .` from the
repository root. Its runtime dependency is Pydantic 2; Playwright, FastAPI,
PostgreSQL and the `src` package are not package dependencies. This installs the
`clean-process` command.

Python API:

```python
from clean_process import Input, process

request = Input.model_validate(payload)
result = process(request)
json_output = result.model_dump(mode="json")
```

## Producer integration

The producer must satisfy `schemas/input.schema.json`. The historical scraper
format is handled by an external adapter, not by the semantic package:

```powershell
.\.venv\Scripts\python.exe -m src.integrations.clean_process data/manual-vichy/resultado.json --output data/clean-process/vichy-input.json
.\.venv\Scripts\python.exe -m clean_process data/clean-process/vichy-input.json --output data/clean-process/vichy-output.json
```

The adapter preserves original blocks in evidence, marks prior producer
classifications as interpretations where appropriate and never fetches URLs.
It does not turn a price on a card into an offer for an invented variant. A
failed historical page needs an explicit producer-side representation; the
adapter rejects malformed/missing results instead of silently dropping them.

## Consumer contract

`schemas/output.schema.json` defines typed product/category lists and the four
question projections. `data` is the lightweight read model; `knowledge` and
`evidence` hold the complete ontology and provenance. Consumers can separate
those sections for display without reinterpreting source content.

`clean_process.presentation.present(output)` provides a separately versioned,
validated read projection with images, ratings, descriptions, findings and chart
rows. Its schema is `schemas/presentation.schema.json`, exported by the same CLI
schema command. The independent comparison orchestrator and UI are documented in
`src/comparison/README.md`; they are not dependencies of this package.

- `data.products`: directly consumable names, brands, destinations and related
  entity IDs. `field_assertion_refs` explains each projected field.
- `data.question_results`: typed price groups, contextual image uses, keyword
  counts and category opinion groups with supporting assertion IDs.
- `findings`: material individual experiences with evidence and explicit scope.
- `issues`: unknown attribution, invalid fields, unavailable interpretation,
  sampling, conflicts and not-found-in-scope are explicit.

IDs are deterministic for the same input namespace and origins. A processing ID
is unique to each run. Provisional entity identity is not a global guarantee.
Prices are decimal strings, not binary floating-point numbers. A single price
is not a range; differing currencies, presentations or conditions are separate.
Capture time is never substituted for offer validity. Output validates links
between projections, assertions, evidence and entities.

`scope` currently supports `source_refs` and `sample_refs` filters. Other filter
keys are rejected rather than echoed as though they had been applied. Temporal
comparability comes from explicit offer validity, or is confined to one sample
without pretending that capture time establishes validity.

## Optional natural language interpretation

The default mode performs **no network calls**. It processes provided semantic
fields and retains unknown text with unresolved diagnostics. It does not claim
that replaying structured fields is new NLP.

To opt into text interpretation, set `TYPESAFE_API_KEY` in the process environment
and select `--interpreter jev`:

```powershell
.\.venv\Scripts\python.exe -m clean_process input.json --interpreter jev --output output.json
```

Credentials are never a CLI argument or output field. In test mode
(`TYPESAFE_TEST_MODE=1`), only `TYPESAFE_TEST_API_KEY` is used.

The Jev interpreter classifies source units and exact text spans using a
hierarchical taxonomy with `other`. All selected questions about a sample are
sent together with its context once. Limits are explicit (`--max-questions`,
`--max-request-bytes`); omitted units/spans are reported, never silently split
across requests. Calls are not automatically retried. Reported provider tokens,
including failures, are recorded in output usage. Unknown usage remains partial;
input costs use USD 0.042/million and output tokens cost zero.

`process(..., interpreter=...)` supports an injected interpreter. It must return
an `Interpretation` containing original units plus additional, exact-span-backed
interpretations. The processor rejects rewritten source text, metadata or
invented quotations.

## Current limits

This is the first implementation, not a claim of universal semantic extraction.

- Jev live behavior has not been validated by the automated tests; they use
  injected predictors and simulated HTTP responses. No paid live calls are
  necessary to run tests or examples.
- The bundled interpreter is text-only. It does not inspect image pixels or
  infer image functions from filenames/alt text. Explicit visual source
  declarations can be supplied through the contract; unknown visual meaning
  stays unknown.
- Free-text classification does not yet construct arbitrary multi-entity
  relations or normalize ambiguous locale-specific prices. Such associations
  must be supplied with evidence or remain unresolved.
- Keyword expressions are selected clause spans, not a complete linguistic
  keyphrase extractor. Topic labels are an initial explicit vocabulary with
  abstention. Counts are deterministic for the selected, evidenced spans.
- Fuzzy identity matching, conversion between currencies/scales and causal
  conclusions are deliberately absent. The same name/text alone does not merge
  products or reviews. Declared aggregates are not manufactured review text.
- No database, background worker, API server, UI or automatic crawler wiring is
  introduced. Contract production is an explicit adapter step.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_clean_process.py tests/test_clean_process_integration.py -q
```

Tests cover isolated contracts and consumer references, offer comparability,
currency/variant separation, conflicts, image uses, exact quotations, review
identity, category attribution, material findings, provider failure accounting,
budget omissions, independent imports, CLI and scraper-format integration.

## Description keywords (description_words_v1)

Keywords are individual Unicode words present in at least two distinct accepted
`description` values within a corpus. NFC/casefold/whitespace normalization
removes duplicate descriptions. Each word counts once per distinct description;
Spanish and English function words are excluded by the auditable list in
`keywords.py`. Accents, inflections and languages are not merged or inferred.
Provenance and language counts remain separate; eligibility is corpus-wide.
`expression_occurrences` equals the description count for these keyword rows.
Topics retain their separate semantic interpretation and counting rules.

By default each source_ref defines a corpus. A producer may explicitly group
pages using `sample.context.keyword_corpus_ref`; the scraper adapter uses its
export_ref for the capture corpus. Each comparison source is processed separately.
Corpus-wide keyword rows have null subject_ref and an explicit corpus_id; their
assertion_refs point to the original description assertions. The projection
records `definition: description_words_v1`; old saved outputs are not rewritten.

## Review recognition: vocabulary + multilingual E5

`vocabularies/reviews.v1.json` contains versioned multilingual phrase/word signals,
concept definitions and contrasting examples. Unknown producer fields are retained
as `Datum(property="raw_field", value={"name": ..., "label": ..., "value": ...})`;
the adapter also preserves explicit standardized rating-scale bounds. They remain
in original evidence even when they cannot be classified.

The optional independent stage is injected with
`process(input, review_recognizer=ReviewRecognizer(E5Scorer()))`. It does not
import or run the scraper. The comparison worker enables this stage by default,
including when the text interpreter is `declared`; requests can explicitly set
`review_recognition` to `e5`, `lexical` or `off`. The CLI exposes the same modes
with `--review-recognition`, defaulting to `off` for backwards compatibility.

Install: `python -m pip install -e ".[embeddings]"` (or repository requirements).
Provision the pinned model once: `python -m clean_process.review_recognition --download-model`.
E5 uses `intfloat/multilingual-e5-base`, revision
`d128750597153bb5987e10b1c3493a34e5a4502a`, CPU, normalized embeddings and `query:`
prefixes on both inputs for symmetric semantic similarity. Inference uses only
cached files and never downloads at runtime or sends text to an embedding API.

Semantic rankings retrieve candidates; cosine scores are not probabilities and
have no calibrated acceptance threshold. Only explicit lexical field meaning
plus structural validation can add normalized fields. Controls, links and arrays
remain distinct from individual reviews. Existing incompatible values are never
overwritten. Both explicit scale bounds are required. Unattributed opinions,
ambiguous numbers and semantic-only matches remain unresolved; no product
association or sentiment is invented.

Coverage (`review_recognition_summary`) and each decision
(`review_recognition_decision`) are exposed in output issues and the UI Opinions
tab. Decisions retain field names, raw values, rule, lexical matches, semantic
ranking, source location and evidence. Up to 96 fields per sample are examined,
prioritizing lexical hits; E5 caches repeated blocks and encodes up to 128 unique
contexts per processing request. Further fields still receive lexical validation;
semantic omissions are recorded separately. Omissions, character truncation and E5's 512-token
limit are reported. If E5 fails, lexical recognition continues with explicit
model_available=false; there is no silent successful-model claim. This is not a
measured accuracy guarantee or a claim of complete review capture. Previously
saved outputs are not changed automatically.
