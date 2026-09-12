# Stage 1 Run Control

The Stage 1 control reads one JSON manifest. It returns one JSON decision. It does
not start an external action.

Use the initial manifest to see the safe initial state:

```sh
python3 -m nlp_wayfinder.stage_run check manifests/stage-1.initial.json \
  --state-dir .wayfinder-state
```

The command returns exit code `2`, decision `no-build`, and stop reason
`source-rights-failed`.

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
split rules, limits, and software versions. The split rules must give the start
and end date of each training, development, and blind period. The limits record
must set the Stage 1 silver-candidate limit to 6,668. Each candidate must have
these fields:

- `candidate_id`
- `event_group_id`
- `company_id`, for the same publicly traded company in related records
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
python3 -m nlp_wayfinder.stage_run allocate-stage-1 \
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

Each accepted silver candidate and each development example receives one vote
from each frozen route. Blind examples never enter this path. Each request goes
to the dedicated provider endpoint with the fully qualified model, no cache, and
no memory. There is no automatic routing, no Fusion, no fallback, and no bare
alias.

The operation writes one append-only record for each attempt in
`raw-votes.jsonl`. The record contains the prompt, the request and response
hashes, the returned route and model identity, the token use, the times, and the
cost metadata.

A refusal, a malformed answer, a timeout, a route substitution, or a cache hit is
an abstention. An abstention has no label. It is not `insufficient evidence`.

A free-limit failure or a paid response stops collection. The command returns
exit code `2` with stop reason `free-limit-failure` or `paid-overflow-detected`.
Run the command again after the free quota resets. Collection does not repeat a
vote that is already in the log, but it does collect again each vote that stopped
on the free limit.

The command also stops with `unsealed-annex` for a candidate manifest that has no
valid seal, `allocation-not-complete` for an allocation that is not complete or
does not agree with the candidate manifest, and `vote-candidate-invalid` for a
selected example that is not in the candidate manifest or is in a different
split.

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
python3 -m unittest discover -s tests -v
```
