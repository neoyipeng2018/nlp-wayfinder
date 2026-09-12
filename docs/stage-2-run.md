# Stage 2 Run Control

Stage 2 adds company announcements and regulatory filings. The operator starts
the two new sources together. The earlier accepted training data stays in use.
One cumulative checkpoint must pass the two new source tests and the
financial-news regression test.

Stage 2 uses the same commands as Stage 1. Read `docs/stage-1-run.md` first. This
document gives only the differences.

## The Stage 2 gate

Use the initial manifest to see the safe initial state:

```sh
python3 -m nlp_wayfinder.stage_run check manifests/stage-2.initial.json \
  --state-dir .wayfinder-state
```

The command returns exit code `2`, decision `no-build`, and stop reason
`source-rights-failed`.

A Stage 2 manifest has `stage` 2 and a `sources` array. The array must hold one
record for `company-announcements` and one record for `regulatory-filings`. A
missing source returns `stage-source-incomplete`. A source outside the stage
returns `source-rights-failed`.

Each source record must contain:

- `source_id` and `source_type`
- `access_permitted`, `private_evaluation_permitted`, `training_permitted`,
  `weight_release_permitted`, and `text_redistribution_permitted`, each `true`
- the complete source `evidence` record that `docs/stage-1-run.md` defines
- `data_plan`, with `silver_candidate_limit` 3,333, `training` 2,000,
  `development` 200, and `blind` 400
- `route_requests`, with the request count of this source for each eligible route
- `schedule`, with `starts_on`, `must_finish_by`, and `evidence`
- `planned_commitments_usd`, with one amount for each budget category

The gate applies each check to each source separately:

- The source and rights flags check stops with `source-rights-failed`.
- The clause evidence check stops with `source-rights-evidence-incomplete`,
  `source-rights-evidence-stale`, or `source-lane-restricted`.
- The data check stops with `source-data-plan-invalid`.
- The route and schedule check stops with `route-schedule-infeasible` or
  `invalid-route-demand`.
- The budget check adds the amounts of the two sources. It stops with
  `category-budget-exceeded` or `total-budget-exceeded`.

The stage-level `route_panel` gives the shared route eligibility, the free
limits, and the daily rates. The account-wide free capacity check stops with
`route-demand-exceeds-free-capacity`.

A valid result is `build-eligible` with `permitted_external_actions`
`["stage-2-build"]`. The evidence holds one record for each source under
`sources` and one schedule record for each source under `schedule`.

## The data of each new source

Each new source has its own sealed annex, its own candidate manifest, and its own
allocation. Use `seal-candidates`, `inspect-candidate`, and `allocate-source` one
time for each source.

A Stage 2 annex must set `silver_candidate_limit` to 3,333, `development_target`
to 200, and `blind_target` to 400. Another value returns
`source-annex-incomplete`. The candidate manifest must give `stage` 2 and a
`source` of the stage.

`allocate-source` selects 2,000 accepted silver examples, 200 development
examples, and 400 blind examples for each new source. The blind rules do not
change: 16 cells of 25 examples, at least 320 event groups, no more than two
examples for each event group, no more than five examples for each company, and
at least 100 unseen companies.

A candidate ID must occur in only one source. The cumulative training run stops
with `duplicate-candidate-id`.

## Votes and silver labels

Run `collect-votes` and `aggregate-silver` one time for each new source. Each
source keeps its own frozen route set, its own Dawid–Skene fit, and its own
sealed posteriors. A later change of one source returns
`frozen-vote-collection-changed` or `frozen-aggregation-changed`. A change of one
source does not touch another source.

## The GPT blind files

Run `predict-blind-gpt` one time for each new source. Each new source gets one
sealed prediction file of its own.

The command makes no new GPT call for financial news. The sealed file from
Stage 1 stays in `gpt-blind-log.jsonl`. A Stage 2 call with the financial-news
candidate manifest returns that same sealed file. The Stage 2 report reads it
from the log.

## The cumulative checkpoint

One stage trains one checkpoint. Give `StageRun.train_specialist` a `sources`
list with three items: financial news, company announcements, and regulatory
filings. Each item holds the sealed `candidate_manifest`, the complete
`allocation`, and the complete `aggregation` of that source.

The training rows are the accepted silver examples of all three sources. The
development rows are the development examples of all three sources. The blind
rows are the blind examples of all three sources.

The operation selects the checkpoint that has the highest macro-F1 over the
development examples of all three sources together. A tie takes the lowest seed.
One cumulative checkpoint needs one selection number. The sealed record also
keeps `development_macro_f1_by_source`, so an audit can see the result of each
source. This selection number is not a source guardrail. Only the blind
comparison decides a source.

An incomplete list returns `cumulative-sources-incomplete`. The Stage 1
checkpoint stays sealed under stage 1. The Stage 2 checkpoint seals under stage
2. A later Stage 2 call with another candidate manifest returns
`frozen-specialist-run-changed`.

## The Stage 2 report

```sh
python3 -m nlp_wayfinder.stage_run report-stage confirmed-stage-2.json \
  stage-2-sources.json \
  --output stage-2-report.json --state-dir .wayfinder-state
```

The sources file is a JSON array with three items. Each item gives the file path
of the `candidate_manifest`, the `allocation`, and the `relabels` of one source:

```json
[
  {
    "candidate_manifest": "financial-news-candidates.json",
    "allocation": "financial-news-allocation.json",
    "relabels": "financial-news-relabels.json"
  },
  {
    "candidate_manifest": "company-announcements-candidates.json",
    "allocation": "company-announcements-allocation.json",
    "relabels": "company-announcements-relabels.json"
  },
  {
    "candidate_manifest": "regulatory-filings-candidates.json",
    "allocation": "regulatory-filings-allocation.json",
    "relabels": "regulatory-filings-relabels.json"
  }
]
```

The report gives a separate decision for company announcements, for regulatory
filings, and for financial news. `decision.source_guardrail` holds one result for
each source. `decision.stage_guardrail` passes only when each of the three
sources passes. `metrics.by_source` holds the class F1 values, the macro-F1
values, the paired bootstrap, and the relabel agreement of each source.

`metrics.pooled` gives the pooled macro-F1 of all blind examples. It carries
`diagnostic_only` with the value `true`. A pooled result cannot offset a source
that failed its own guardrail.
