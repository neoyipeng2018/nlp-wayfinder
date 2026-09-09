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

Record a cost commitment before the related action. Record the actual cost after
the action:

```sh
python3 -m nlp_wayfinder.stage_run record-cost \
  --state-dir .wayfinder-state --action-id gpu-pilot --kind commitment \
  --category specialist --amount-usd 5.00 --evidence "Approved quote"
```

The command stores commitments and actual costs in `spend-ledger.jsonl`. Each
record contains the hash of the prior record. The control rejects a record before
it can exceed a category limit or the USD 100 total limit. It does not permit use
of contingency without a new planning decision.

Run all tests with:

```sh
python3 -m unittest discover -s tests -v
```
