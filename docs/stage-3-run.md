# Stage 3 Run Control

Stage 3 adds earnings calls and financial social media. The operator starts the
two new sources together. All earlier accepted training data stays in use. One
final cumulative checkpoint must pass the two new source tests and the three
earlier regression tests.

Stage 3 uses the same commands as Stage 2. Read `docs/stage-1-run.md` and
`docs/stage-2-run.md` first. This document gives only the differences.

## The Stage 3 gate

Use the initial manifest to see the safe initial state:

```sh
python3 -m nlp_wayfinder.stage_run check manifests/stage-3.initial.json \
  --state-dir .wayfinder-state
```

The command returns exit code `2`, decision `no-build`, and stop reason
`source-rights-failed`.

A Stage 3 manifest has `stage` 3 and a `sources` array. The array must hold one
record for `earnings-calls` and one record for `financial-social-media`. A
missing source returns `stage-source-incomplete`. A source of an earlier stage
returns `source-rights-failed`. The record fields and the gate checks of each
source do not change from Stage 2.

A valid result is `build-eligible` with `permitted_external_actions`
`["stage-3-build"]`.

## The data of each new source

Each new source has its own sealed annex with a `silver_candidate_limit` of
3,333, a `development_target` of 200, and a `blind_target` of 400. Each new
source adds 2,000 accepted silver examples, 200 development examples, and 400
blind examples. The five sources together inspect no more than 20,000 silver
candidates.

Run `seal-candidates`, `inspect-candidate`, `allocate-source`, `collect-votes`,
and `aggregate-silver` one time for each new source. The blind cell, event-group,
company, and unseen-company rules do not change.

## The GPT blind files

Run `predict-blind-gpt` one time for each new source. The command makes no new
GPT call for financial news, company announcements, or regulatory filings. Each
earlier source keeps the sealed prediction file of its own stage, and the Stage 3
report reads that file from `gpt-blind-log.jsonl`.

## The final cumulative checkpoint

Give `StageRun.train_specialist` a `sources` list with five items: financial
news, company announcements, regulatory filings, earnings calls, and financial
social media. Each item holds the sealed `candidate_manifest`, the complete
`allocation`, and the complete `aggregation` of that source. An incomplete list
returns `cumulative-sources-incomplete`.

The training rows are the accepted silver examples of all five sources. The
checkpoint selection uses the development examples of all five sources together.
The sealed record keeps `development_macro_f1_by_source`. This selection number
is not a source guardrail.

## The final staged decision

```sh
python3 -m nlp_wayfinder.stage_run report-stage confirmed-stage-3.json \
  stage-3-sources.json \
  --output stage-3-report.json --state-dir .wayfinder-state
```

The sources file is a JSON array with five items, one for each source.

The report gives a separate decision to each of the five sources.
`decision.source_guardrail` holds one result for each source, and
`decision.stage_guardrail` passes only when all five sources pass.
`metrics.pooled` stays `diagnostic_only` and cannot offset a source that failed
its own guardrail.

The report also holds a `claim` record:

- `scope` limits the result to the sealed, balanced, company-only, four-aspect
  blind test of each listed source. It makes no natural-distribution claim, no
  general-parity claim, no return forecast, and no trading claim.
- `tested_sources` gives the five tested sources.
- `final_staged_decision` is `true` only in the last stage.
