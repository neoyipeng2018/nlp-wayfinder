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
