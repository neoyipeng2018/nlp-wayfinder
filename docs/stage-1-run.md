# Stage 1 Run Control

Create the locked Python environment before you run a command:

```sh
uv sync --locked
```

Use `uv run python` in place of `python3` for the commands below. The lock file
installs Python 3.11 through 3.13 dependencies, including Crowd-Kit 1.4.2 and
the ModernBERT tokenizer support.

The Stage 1 control reads one JSON manifest. It returns one JSON decision. It does
not start an external action.

Use the initial manifest to see the safe initial state:

```sh
python3 -m nlp_wayfinder.stage_run check manifests/stage-1.initial.json \
  --state-dir .wayfinder-state
```

The command returns exit code `2`, decision `no-build`, and stop reason
`source-rights-evidence-incomplete`.

The current initial manifests were checked with this gate. All three return exit
code `2`, decision `no-build`, and stop reason
`source-rights-evidence-incomplete`:

- `manifests/stage-1.initial.json`
- `manifests/stage-2.initial.json`
- `manifests/stage-3.initial.json`

Make and review a new manifest before zero-change confirmation. Then add the
zero-change confirmation evidence to a new file:

```sh
python3 -m nlp_wayfinder.stage_run confirm draft.json \
  --confirmed-by NAME --output confirmed.json
```

Do not edit a confirmed manifest. A semantic change returns
`semantic-manifest-change`. The decision log keeps the attempted change.

Apply the staged feasibility gate:

```sh
python3 -m nlp_wayfinder.stage_run check confirmed.json \
  --state-dir .wayfinder-state
```

A valid result is `build-eligible`. This result does not start work. Get separate
approval before you use an external service.

A Stage 1 manifest gives its one financial-news source in a `source` object. It
gives the route demand in `route_panel`, the schedule in `schedule`, and the
planned cost in `budget.planned_commitments_usd`. A later stage gives a `sources`
array instead, and each record in that array holds its own data plan, route
demand, schedule, and planned cost. `docs/stage-2-run.md` gives that form.

Each source must contain one `eligibility_evidence` record. The record must give
`checked_at`, `terms_url`, `reviewer`, `access_method`,
`data_portfolio_lane`, and `rights`. The lane must be `clean-core`. A
`restricted-auxiliary` source cannot supply cumulative-checkpoint training data.

`rights` must contain one record for each of the five fixed rights. Each record
must give `permitted`, `primary_source_term_url`, `exact_clause`,
`retrieved_at`, `reviewer`, and `audited_object`. The training, weight-release,
and text-redistribution rights must audit `passage-text`. A repository or data
file license is not sufficient. Source evidence must not be in the future and
must be no more than 90 days old at `starts_on`.

Incomplete evidence returns `source-rights-evidence-incomplete`. Old or future
evidence returns `source-rights-evidence-stale`. A restricted lane returns
`source-lane-restricted`.

Use `manifests/stage-1.eligibility-evidence.example.json` as the field guide.
It is an unapproved template. Its placeholder values cannot authorize a build.

Each source must also contain one `yield_evidence` record. The record must
contain `checked_at`, `candidate_pool_size`, `candidate_pool`,
`candidate_pool_sha256`, `sample_size`, `order_salt`, and
`sampled_candidates`. Each candidate-pool item must contain a unique
`candidate_id` and one `split`. The pool length must equal
`candidate_pool_size`, and its hash must equal `candidate_pool_sha256`. The pool
must be in the append-only state before inspection starts. Each sampled candidate
must contain the same fields and `verified_company_target`. The split must be
`training`, `development`, or `blind`.

The `order_salt` must be `20260905`. The gate puts the complete candidate pool
in the fixed order from this salt and `candidate_id`. It selects the first
`sample_size` candidates. The supplied sample must contain exactly these
candidates. The gate calculates the company-target yield, the yield of each
split, and the number of candidates that collection must inspect. The check
passes only when the source can fill its fixed allocation inside its source
inspection limit. A failed check returns `source-yield-unproven` and adds one
source stop record to the decision log. Old or future yield evidence returns
`source-rights-evidence-stale`.

Before you inspect the yield sample, seal the pool in the append-only state:

```sh
python3 -m nlp_wayfinder.stage_run seal-yield-pool yield-pool.json \
  --sealed-by NAME --state-dir .wayfinder-state
```

The pool file must contain `stage`, `source_id`, `source_type`,
`candidate_pool_size`, `candidate_pool`, and `order_salt`. The later source
record must use the SHA-256 value that this command returns. The gate rejects a
pool that has no prior matching seal. The yield `checked_at` timestamp must not
be earlier than the seal record timestamp.

Admit one target–aspect example before you send it to a person or a model:

```sh
python3 -m nlp_wayfinder.stage_run admit-example example.json
```

The example file must contain one verified public company, one Stage 1 aspect,
and a consecutive list of complete sentences. It must identify the sentence
positions that contain the target and the required evidence. An optional label
must be `positive`, `neutral`, `negative`, or `insufficient evidence`.

Use this JSON structure:

```json
{
  "company": {
    "name": "Harbor Grid Ltd",
    "ticker": "HGL",
    "exchange": "LSE",
    "publicly_traded": true
  },
  "aspect": "operations, supply, and capacity",
  "sentences": [
    {
      "position": 20,
      "text": "Harbor Grid said the shutdown will have no material effect on output."
    }
  ],
  "target_evidence_positions": [20],
  "required_evidence_positions": [20],
  "label": "neutral"
}
```

The command uses the pinned ModernBERT tokenizer. It returns one serialized input
for the human, each labeling route, the specialist, and GPT. It counts the complete
serialized input, field separators, and model special tokens. It does not truncate
the input. It returns the schema result `Invalid` and a stop reason when the input
does not pass a check or has more than 1,024 tokens.

Before labeling, make one candidate manifest for the financial-news source. The
`annex` must use structured records for acquisition, rights, extraction,
normalization, target-and-aspect expansion, event grouping, duplicate review,
split rules, limits, and software versions. The target-and-aspect expansion
record must state the full four-aspect rule: the annex expands each
passage-and-company pair to all four Stage 1 aspects. An aspect that the
passage does not support then gives `insufficient evidence` in its natural
form. The 6,668 limit counts inspected candidates, not passages, so this
expansion does not change the passage count gate. The split rules must give the start
and end date of each training, development, and blind period. The limits record
must set the Stage 1 silver-candidate limit to 6,668. Each candidate must have
these fields:

- `candidate_id`
- `event_group_id`
- `company_id`, for the same publicly traded company in related records
- `company`, with the `name` that the human labeler sees. Each voter, GPT, and
  the specialist receive this name as the company target, not `company_id`.
- `aspect`, from the Stage 1 aspect set
- `published_at`
- `normalized_passage`
- `near_duplicate_reviewed`, with the value `true`

An optional `near_duplicate_group_id` records a reviewed near-duplicate group.
The final manifest can contain only one candidate from that group. The seal
calculates `content_sha256` from the normalized passage. It rejects repeated
content hashes. It assigns `split` from the publication time and the recorded
periods. It rejects an event group that occurs in more than one split.

Seal the annex and create the fixed candidate order:

```sh
python3 -m nlp_wayfinder.stage_run seal-candidates draft-candidates.json \
  --sealed-by NAME --output sealed-candidates.json
```

The order is the ascending SHA-256 of
`nlp-wayfinder + stage + source + split + candidate_id + 20260905`. The seal
hash covers the full annex and ordered candidates.

Inspect only the next candidate in this order:

```sh
python3 -m nlp_wayfinder.stage_run inspect-candidate \
  sealed-candidates.json CANDIDATE_ID --state-dir .wayfinder-state
```

The command writes an append-only inspection record. It rejects an absent or
changed seal and an out-of-order candidate. It also validates duplicate and
event-group split controls again before inspection.

After candidate review and labeling, make one JSON array of review records. Each
record must contain `candidate_id`, `disposition`, `label`, and `labeled_at`.
`disposition` is `accepted` or `excluded`. `label` is one of the four fixed result
labels. `labeled_at` is a UTC time that ends in `Z`.

Create the complete Stage 1 allocation:

```sh
python3 -m nlp_wayfinder.stage_run allocate-source \
  sealed-candidates.json reviews.json --state-dir .wayfinder-state \
  --output stage-1-allocation.json
```

The operation reads the append-only inspection log. Each inspected training
candidate counts against the limit of 6,668, even if it has no review record. The source
stops if it does not produce 4,000 accepted silver examples before this limit. It
also stops if it cannot select 200 accepted development examples and 400 accepted
blind examples.

For the blind set, the operation selects the next eligible candidate in each
required aspect-and-label cell. It selects exactly 25 candidates in each of the 16
cells. If one selection breaks a balance rule, the operation searches later
candidates in the same cell in sealed order. The result stops only when no valid
complete selection exists. The result must have at least 320 event groups. An event
group can have no more than two examples. A company can have no more than five
examples. The result must have at least 100 unseen companies.

The result uses seed `20260905` to select 60 blind examples for a second label.
Each cell has three or four examples in this sample. Each sample record gives the
first permitted relabel time, which is 14 days after its first human label. The
first label stays unchanged. The allocation contains the sealed candidate-manifest
hash and its own SHA-256 hash.

Collect one independent vote from each frozen route:

```sh
python3 -m nlp_wayfinder.stage_run collect-votes \
  confirmed.json sealed-candidates.json stage-1-allocation.json \
  --state-dir .wayfinder-state --base-url http://127.0.0.1:20128
```

The operation first applies the staged feasibility gate. It then freezes the
complete set of eligible routes for the stage in `vote-collection-log.jsonl`. The
gate permits no fewer than three eligible routes. A later change of the routes,
the stage manifest, the candidate manifest, or the prompt returns
`frozen-vote-collection-changed`.

Each candidate route must give complete account evidence under `evidence`. The
record must give `checked_at`, `account`, `terms_url`, `observed_route_id`,
`observed_free_requests_remaining`, `observed_requests_per_day`,
`account_no_paid_overflow`, and a `training_use` term record. Route evidence
must not be in the future and must be no more than 30 days old at `starts_on`.
The observed route ID and free-limit figures must equal the declared route
values. An incomplete or stale candidate is not in the eligible panel. Three
other valid routes can still pass. An identity or free-limit mismatch stops the
stage. The build decision records each evidence record, its SHA-256 value, and
the accepted route set.

A route with `kind` set to `capped-paid` is a paid route with a prepaid hard
stop. It gives no free-limit evidence and no `account_no_paid_overflow` field.
In their place it gives `account_no_auto_recharge`, `account_no_stored_card`,
`observed_prepaid_balance_usd`, `observed_cap_usd`, and a `prices` record with
`input_usd_per_million` and `output_usd_per_million`. The route itself gives
`cap_usd`, `cap_verified`, and `worst_case_request_cost_usd`. The cap must equal
the declared cap, the prepaid balance must be no less than the cap, and the cap
must be no more than the USD 20.00 `paid-silver-labels` limit. The capacity of a
capped route is `floor(cap / worst-case request cost)` in place of the free
limit. All other route rules do not change.

Two routes on one account share one daily grant. Each such route must give
`account_requests_per_day_grant`, and the sum of their
`observed_requests_per_day` values must be no more than that grant. If it is
more, the stage returns `route-demand-exceeds-free-capacity`.

The route refusal reasons are `route-evidence-incomplete` and
`route-evidence-stale`. If fewer than three routes remain, the stage returns
`insufficient-eligible-routes`. A free-limit mismatch returns
`route-evidence-inconsistent`. A route-identity mismatch returns
`route-identity-unconfirmed`.

Each accepted silver candidate and each development example receives one vote
from each frozen route. Blind examples never enter this path. Each request goes
to the dedicated provider endpoint with the fully qualified model, no cache, and
no memory. There is no automatic routing, no Fusion, no fallback, and no bare
alias.

Each vote uses the full auditable vote schema. The strict JSON schema holds
`label`, `confidence_band`, `evidence_start`, `evidence_end`, `evidence_text`,
and `reason_code`. It permits no added property. The band is `high`, `medium`,
or `low`. The output-token cap is 300 tokens.

The reason code is one of these values:

- `favorable evidence`
- `unfavorable evidence`
- `stated stability or no material effect`
- `evidence absent`
- `evidence about another aspect`
- `evidence about another target`
- `conflicting without resolution`

The operation writes one append-only record for each attempt in
`raw-votes.jsonl`. The record contains the prompt, the request and response
hashes, the returned route and model identity, the label, the confidence band,
the evidence offsets and text, the reason code, the token use, the times, and
the cost metadata.

The operation validates each answer against the item that it requested. The
item identity is the passage itself: the collector accepts the evidence only
when it is in the normalized passage of the requested item, which rejects an
answer about a different item. The label, the band, and the reason code must
be members of their lists. The
evidence text must be the exact substring of that item's normalized passage
between `evidence_start` and `evidence_end`. The span must hold one character
or more, and it must stay inside the passage. The three evidence fields are null
only for the `insufficient evidence` label. An answer that fails any of these
checks is a malformed answer.

A refusal, a malformed answer, a timeout, a route substitution, or a cache hit is
an abstention. An abstention has no label, no band, no evidence, and no reason
code. It is not `insufficient evidence`.

The self-reported band is not a probability. It stays in the record as
provenance. Aggregation does not use it as a weight until human development
labels calibrate it.

A malformed answer earns one repair request to the same route with an identical
request. No other abstention earns one. Both attempts stay in `raw-votes.jsonl`,
and each attempt holds its own position in `retry_ordinal`. Only the final
attempt gives the vote, so each route and item still contributes one vote to
aggregation.

The repair is a full request. It counts against the route free limit, and it can
itself stop collection with `free-limit-failure` or `paid-overflow-detected`. Give
`current_stage_requests` in the route panel a margin for the repairs, because the
schedule uses that number. A repair that hits the free limit spends no repair,
so the route gets its repair again after the quota resets.

A free-limit failure or a paid response stops collection. The command returns
exit code `2` with stop reason `free-limit-failure` or `paid-overflow-detected`.
A capped paid route is the one exception. A paid answer on such a route is a
valid vote. Collection measures its own cost from the `usage` record and the
frozen prices, and it does not use the `x-omniroute-response-cost` header. The
cost of each attempt in `raw-votes.jsonl` counts, so a new run does not lose the
spend. An attempt that gives no response costs nothing. An attempt with no
`usage` record costs the worst-case amount. Collection stops the route one
worst-case request before the cap. After that stop, and also if the provider
refuses the route for a spent balance, each later attempt on that route is a
kept `transport-error` abstention, and collection continues with the other
routes. The panel then has three voters and does not fail the three-route gate.
A capped route carries its frozen request fields. The Kimi route sends
`thinking` with type `disabled`.
Run the command again after the free quota resets. Collection does not repeat a
vote that is already in the log, but it does collect again each vote that stopped
on the free limit.

The command also stops with `unsealed-annex` for a candidate manifest that has no
valid seal, `allocation-not-complete` for an allocation that is not complete or
does not agree with the candidate manifest, and `vote-candidate-invalid` for a
selected example that is not in the candidate manifest or is in a different
split.

Aggregate the collected votes into accepted silver labels:

```sh
uv run python -m nlp_wayfinder.stage_run aggregate-silver \
  confirmed.json sealed-candidates.json stage-1-allocation.json \
  --state-dir .wayfinder-state --output accepted-silver.json
```

The operation applies the staged feasibility gate again. It then reads the
append-only raw vote log. It keeps the last outcome for each example and route.
An abstention is a missing vote. It is not a label.

The operation stops with `development-class-underfilled` if any of the four human
development classes has fewer than 25 examples. It also stops with
`unsealed-annex`, `allocation-not-complete`, `development-label-invalid`,
`no-valid-votes`, `crowd-kit-missing`, or `crowd-kit-version-mismatch`.

The operation fits Crowd-Kit 1.4.2 Dawid–Skene with 100 iterations and tolerance
`1e-8`. The human development labels anchor the fit. The result keeps one full
four-by-four confusion matrix for each frozen route, including a route that
abstained on every example. The model has no route-dependency
parameter. The operation then applies the fitted matrices and priors to each
example again, without the gold correction, to get the raw posterior.

Calibration uses five out-of-fold temperature folds with seed `20260905`. Each
development example gets its fold from the SHA-256 of
`nlp-wayfinder1financial-news-silver-calibration + candidate_id + 20260905`. Each
fold temperature comes from the other four folds. Each temperature comes from a
golden-section search of 80 steps between 0.05 and 10.0. The mean of the five
fold temperatures calibrates the training examples.

The operation rejects a training candidate for one of these reasons:

- `insufficient-votes`, for fewer than two valid votes
- `posterior-tie`, for two top probabilities within `1e-12`
- `no-strict-majority`, when no single class has more valid votes than each other
  class
- `top-class-unsupported`, when the strict majority class is not the calibrated
  top class
- `low-confidence`, for a calibrated top probability below 0.70

The operation seals the fit and the posterior artifacts in
`silver-aggregation-log.jsonl`. A later change of the fit or the posteriors
returns `frozen-aggregation-changed`. The result contains the accepted silver
labels with their calibrated distributions, the rejection counts, the artifact hashes, and its own SHA-256 hash.

The operation also gives a true out-of-fold development macro-F1. It fits
Dawid-Skene again on four of the five calibration folds, with the gold anchor
of those folds only, and predicts the fifth fold. The majority of each held-out
posterior gives the label. The number goes in the result and in the sealed fit
as `development_out_of_fold_macro_f1`. It is a report-only diagnostic. No stop
rule reads it.

Seal the GPT blind prediction file for the source:

```sh
python3 -m nlp_wayfinder.stage_run predict-blind-gpt \
  confirmed.json sealed-candidates.json stage-1-allocation.json \
  gpt-forecast.json --state-dir .wayfinder-state \
  --output gpt-blind-predictions.json
```

The forecast file is the non-blind token check. It must contain
`measured_split`, which is `training` or `development`, `measured_candidate_ids`,
`prompt_tokens_per_example`, `completion_tokens_per_example`,
`prompt_usd_per_1k_tokens`, `completion_usd_per_1k_tokens`, and
`charged_retry_reserve_attempts`. The operation projects the 2,000 first attempts
of the complete plan and the declared reserve against the unspent part of the USD
25 GPT allocation. It stops with `gpt-forecast-blind-exposure`,
`gpt-forecast-incomplete`, or `gpt-budget-exceeded` before it makes a call.
Record the GPT cost commitment with `record-cost` before you start the run.

The operation applies the staged feasibility gate. It then freezes the route
`cx/gpt-5.6-sol-medium`, medium reasoning effort, one zero-shot prompt, the
strict four-label JSON schema, the attempt limit, and the fixed delays in
`gpt-blind-log.jsonl`. A later change returns `frozen-gpt-run-changed`.

Each blind example gets one request. The request contains only the passage, the
company, and the aspect. A candidate manifest that carries a label stops the run
with `blind-label-exposed`.

A timeout, a connection error, HTTP 429, or HTTP 5xx gets up to three total
identical attempts. The delays are 5 seconds and 20 seconds. A refusal or a
malformed answer gets no retry, no repair, and no replacement. Three failed
transport attempts, a refusal, a malformed answer, a route mismatch, or a missing
prediction makes the source run invalid. The operation writes one append-only
record for each attempt.

The operation also stops with `unsealed-annex`, `allocation-not-complete`, and
`gpt-candidate-invalid` for an example that is not in the candidate manifest or
is not in the blind split. `missing-prediction` stops a run that does not have one
label for each scheduled example.

A complete run writes one sealed prediction file with its own SHA-256 hash, the
sealed software versions, and the projection. A later regression comparison reads
the sealed file from the log. It does not make a new GPT call. A sealed file for a
different candidate manifest returns `frozen-gpt-run-changed`.

Train the pinned specialist and seal its blind prediction file with
`StageRun.train_specialist`. The operation has no command-line form. The
training backend runs on the rented GPU and on the M3 computer. The operator
calls the method from the run script. The operator also supplies one backend
object with a `train` method and a `predict` method.

The `sources` input is a list. Each item holds the sealed `candidate_manifest`,
the complete `allocation`, and the complete `aggregation` of one source. The list
must hold each source of this stage and of each earlier stage, or the operation
returns `cumulative-sources-incomplete`. One stage trains one cumulative
checkpoint on all of them. A candidate ID that occurs in two sources returns
`duplicate-candidate-id`.

The `device_checks` input must contain `m3` and `gpu_pilot`. The `m3` check must
contain `device_id`, `unified_memory_gb`, `max_sequence_tokens`, which must be
512, `compatibility_verified`, `local_inference_verified`, and `evidence`. An
absent field returns `m3-check-incomplete`. A failed value returns
`m3-check-failed`.

The `gpu_pilot` check is the measured 1,024-token pilot. It must contain
`gpu_model`, `gpu_architecture`, `gpu_memory_gb`, `peak_memory_gb`,
`max_sequence_tokens`, `pilot_usd`, `initial_loss`, `final_loss`,
`examples_per_second`, `training_examples_per_seed`, `hourly_usd`, `storage_gb`,
`storage_usd_per_gb_month`, `storage_months`, and `tax_rate`. The operation
projects three seed runs and one operational repeat. It adds the storage cost
and the tax. It then compares the result with the unspent part of the USD 35
specialist allocation. The measured pilot cost also lowers that balance. A USD 5
pilot leaves a USD 30 balance. Give `training_examples_per_seed` as the complete
number of examples for one seed run, which is the epoch count multiplied by the
accepted silver examples. It stops with `specialist-pilot-incomplete`,
`specialist-pilot-architecture` for a GPU that is older than Ampere,
`specialist-pilot-token-limit` for a pilot that is not 1,024 tokens,
`specialist-pilot-memory`, `specialist-pilot-loss` for a loss that does not
decrease, `specialist-pilot-cost-exceeded` for a pilot above USD 5, or
`specialist-budget-exceeded`.

Each seed run uses the pinned ModernBERT revision, a new four-class head, and
explicit `passage`, `target`, and `aspect` fields. The training rows carry the
calibrated four-class distribution of each accepted silver label as
`label_distribution`, and the run trains with soft cross-entropy. An accepted
silver label without a valid distribution stops the run with
`silver-labels-not-accepted`. The development rows carry no label, because the human
development labels stay in the scoring code. The run stops with
`specialist-training-invalid` when a checkpoint reports another initialization,
another token limit, another head, or an incomplete development prediction set.

Each seed run also uses the frozen training settings: learning rate 5e-5, 3
epochs, batch size 32, AdamW, linear decay with 10% warmup, and weight decay
0.01. These values are in `base_config`, so `training_config_sha256` covers
them. The backend must report them back in `training_settings`. Another value
stops the run with `specialist-training-settings-mismatch`. No development or
silver number can select them.

The specialist is the average of the softmax probabilities of the three seeds.
Each of the three checkpoints predicts the full blind set on the checked M3
device. The operation averages the three probability rows of each blind
example. It then subtracts the logarithm of the class prior of that aspect,
with a fixed `tau` of 1, and takes the argmax. The prior of an aspect is the
mean accepted silver distribution of that aspect. An aspect with no accepted
silver takes a flat prior. The development macro-F1 of each seed is a reported
diagnostic. It selects nothing.

The blind inference must run on the checked M3 device. Another device returns
`local-inference-device-mismatch`. An incomplete or invalid probability row
returns `missing-prediction`. A result with no probabilities returns
`specialist-inference-invalid`.

GPT output cannot enter this operation. The run stops with
`gpt-artifact-present` when the silver aggregation, the allocation, the device
checks, or the candidate manifest contains a GPT field name or the GPT route
identifier. A passage that mentions GPT is source text and does not stop the
run. A candidate that carries a label stops the run with `blind-label-exposed`.

Record the specialist cost commitment with `record-cost` before the pilot and
before the training runs. The operation does not record cost for you.

The operation seals the run in `specialist-log.jsonl` and returns one prediction
file with its own SHA-256 hash, the three checkpoint identifiers, each seed
result, the aspect priors, the `tau`, the projection, and the sealed software
versions. A later call returns the sealed
file and does not train again. A sealed file for a different candidate manifest
returns `frozen-specialist-run-changed`.

Decide and report the Stage 1 result after both prediction files are sealed:

```sh
python3 -m nlp_wayfinder.stage_run report-stage confirmed.json \
  report-sources.json \
  --output stage-1-report.json --state-dir .wayfinder-state
```

The sources file is a JSON array. Each item gives the file path of the
`candidate_manifest`, the `allocation`, and the `relabels` of one source. Stage 1
has one item for financial news. A later stage has one item for each source of
that stage and of each earlier stage. A missing source returns
`cumulative-sources-incomplete`.

Each relabels file is a JSON array. Each item contains `candidate_id`, `label`,
and `labeled_at`. The array must contain one second label for each of the 60
examples in `blind_relabel_sample`. A second label before `relabel_not_before`
returns `relabel-washout-not-met`. Another candidate set returns
`relabel-sample-mismatch`.

The operation reads both sealed prediction files from the log. It does not
accept a prediction file from the operator. A missing file returns
`specialist-predictions-missing` or `gpt-predictions-missing`. A prediction set
that does not match the blind examples returns `incomplete-paired-predictions`.

The operation applies the staged feasibility gate first, and it returns that
stop reason when the gate does not pass. A candidate manifest that is not sealed
returns `unsealed-annex`. An allocation that is not complete, or that is for
another candidate manifest, returns `allocation-not-complete`. A blind example
without a valid label or event group returns `blind-label-invalid`. A second
label that is not one of the four classes returns `relabel-label-invalid`.

The report gives one decision for each source. For each source it gives each
class F1, the four-class macro-F1 for the specialist model and for the
GPT-5.6-sol baseline, and the specialist-minus-GPT difference. The paired
bootstrap resamples the blind event groups of that source 10,000 times with seed
`20260905`. It gives the two-sided 95% percentile interval of the difference. A
source passes its guardrail only when the lower limit is `-0.03` or more. The
report records superiority only when the lower limit is more than zero. The
stage guardrail passes only when each source passes. The pooled score under
`metrics.pooled` is diagnostic only. It cannot make a failed source pass.

The report also gives
`metrics.silver_development_out_of_fold_macro_f1` for each source, from the
sealed silver fit. It is diagnostic only. No stop rule reads it.

The report also gives the raw agreement and the Cohen kappa of the delayed
60-example relabel. The first human label stays as the reference label. The
second label does not change the benchmark result.

The report contains the decisions, the counts, the model and route identities,
the GPT attempt counts, the manifest and prediction-file hashes, the software
versions, each prediction file, the metrics, the decision records, and the
spend-ledger entries. It carries its own SHA-256 hash. The command returns exit
code `2` and writes no file when the report is not complete.

Record a cost commitment before the related action. Record the actual cost after
the action:

```sh
python3 -m nlp_wayfinder.stage_run record-cost \
  --state-dir .wayfinder-state --action-id gpu-pilot --kind commitment \
  --category specialist --amount-usd 5.00 --evidence "Approved quote"
```

The command stores commitments and actual costs in `spend-ledger.jsonl`. Each
record contains the hash of the previous record. The control rejects a record before
it can exceed a category limit or the USD 100 total limit. It does not permit use
of contingency without a new planning decision.

Run all tests with:

```sh
uv run python -m unittest discover -s tests -v
```
