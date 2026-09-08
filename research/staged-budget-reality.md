# Staged experiment budget reality

**Research date:** 2026-09-08  
**Question:** Can the complete staged experiment fit within USD 100?  
**Spend made or approved by this report:** USD 0

## Answer

The experiment can fit within USD 100, but this result is conditional. The current category limits are useful stop limits. They are not proof that the complete experiment will finish.

The normal planning case fits. The worst permitted retry case does not fit with standard OpenAI API prices. The complete training cost is also unresolved until the 1,024-token pilot measures speed and memory.

Use this decision:

- Keep the USD 100 total limit.
- Keep USD 0 as the hard paid-silver-label limit.
- Keep USD 35 as the hard specialist limit, subject to the pilot gate below.
- Treat USD 25 for GPT as a normal-case limit, not a three-attempt guarantee.
- Keep no more than USD 20 for data and storage. Expect this category to use much less when all data rights are free.
- Keep USD 20 as an untouched contingency reserve.
- Stop before a category limit or the total limit will be exceeded.

The experiment is feasible only if all preflight gates in this report pass. If a gate does not pass, stop that stage. Do not use paid overflow.

## Fixed workload

The staged plan has these accepted silver training sets:

| Stage | Training examples | Development examples | New blind examples |
| --- | ---: | ---: | ---: |
| 1 | 4,000 | 200 | 400 |
| 2, cumulative | 8,000 | 600 | 800 |
| 3, cumulative | 12,000 | 1,000 | 800 |
| Complete experiment | 12,000 accepted | 1,000 | 2,000 |

The silver-label intake can inspect at most 20,000 candidates. Each free route must also label the 1,000 development examples. Thus:

```text
calls for each free route = 20,000 candidates + 1,000 development examples
                          = 21,000 calls

calls for R eligible routes = 21,000 x R
```

The specialist uses three seeds at each stage. Let `E` be the number of epochs:

```text
training example-passes
  = (4,000 + 8,000 + 12,000) x 3 seeds x E
  = 72,000 x E

maximum token-passes
  = 72,000 x E x 1,024 tokens
  = 73,728,000 x E
```

If `E = 3`, the job has 216,000 example-passes and no more than 221,184,000 token-passes. The epoch count must be fixed before the pilot.

The GPT file is made once for each source and is reused for later regression tests. Thus, the normal blind demand is 2,000 successful GPT labels, not one new GPT run at each stage.

## USD 0 paid silver labels

### Current eligible routes

The current verified panel has three routes:

1. `mistral/mistral-medium-3-5`
2. `cf/@cf/zai-org/glm-4.7-flash`
3. `groq/qwen/qwen3.6-27b`

No additional route has current proof for all fixed-model, rights, free-quota, audit, and no-paid-overflow checks. A new route can enter only after it passes all these checks.

Mistral identifies `mistral-medium-3-5` as a fixed major-and-minor model ID. Mistral says that this type of ID does not receive silent model changes. The model supports structured output. Mistral also has a Free API mode. However, Mistral does not publish one numeric Free account limit. The account Admin panel gives the applicable limit. This value is unresolved until account preflight. See the [Mistral model page](https://docs.mistral.ai/models/mistral-medium-3-5-26-04), [model lifecycle policy](https://docs.mistral.ai/inference/model-lifecycle), and [usage and limits page](https://docs.mistral.ai/admin/billing-usage/usage-limits).

Cloudflare gives 10,000 free Neurons each day. The limit resets at 00:00 UTC. Use above the Free limit fails. GLM-4.7-Flash uses 5,500 Neurons for one million input tokens and 36,400 Neurons for one million output tokens. See the [Workers AI pricing page](https://developers.cloudflare.com/workers-ai/platform/pricing/) and the [GLM-4.7-Flash page](https://developers.cloudflare.com/workers-ai/models/glm-4.7-flash/).

Groq publishes these Free limits for `qwen/qwen3.6-27b`: 1,000 requests each day, 8,000 tokens each minute, and 200,000 tokens each day. Groq says that the exact organization limit is in the account Limits page. See the [Groq rate-limit page](https://console.groq.com/docs/rate-limits) and [Groq model page](https://console.groq.com/docs/models).

### Free-route schedule

Use the planning size of 800 input tokens and 80 output tokens for each vote. This size must be replaced by measured use before a stage starts.

```text
tokens for each route = 21,000 x (800 + 80)
                      = 18,480,000 tokens

Cloudflare Neurons
  = 21,000 x ((800 x 5,500 / 1,000,000)
            + (80 x 36,400 / 1,000,000))
  = 153,552 Neurons

Cloudflare daily grants = ceiling(153,552 / 10,000) = 16 days

Groq daily grants = ceiling(18,480,000 / 200,000) = 93 days
```

For the current three-route panel, the complete maximum is 63,000 calls. Each additional eligible route adds 21,000 calls. It does not add cash cost when its free mode has a hard stop. It can add schedule time. The slowest accepted route sets the schedule.

Mistral states that the customer owns text output. Its image-output restriction does not apply to this text-label task. Cloudflare states that the customer owns its Customer Content and that Cloudflare does not use it to train models without consent. Groq states that it does not use input or output for model training without permission. Groq also restricts work that develops a service that is similar to the Groq cloud service. Confirm that the internal classifier is permitted before use. See the [Mistral commercial terms](https://legal.mistral.ai/terms/commercial-terms-of-service/), [Cloudflare data-use page](https://developers.cloudflare.com/workers-ai/platform/data-usage/), and [Groq Services Agreement](https://console.groq.com/docs/legal/services-agreement).

**Result:** USD 0 is possible. It is not yet confirmed for an account. Stop before labeling if one route has no exact free quota record, no hard free-mode stop, or no clear training-use permission. At least three routes must pass.

## USD 35 specialist compute and device checks

The fixed model has 149,655,232 parameters. Its pinned model card supports inputs longer than 1,024 tokens. The model facts are in the [pinned ModernBERT configuration](https://huggingface.co/answerdotai/ModernBERT-base/blob/8949b909ec900327062f0ebf497f51aef5e6f0c8/config.json), [model card](https://huggingface.co/answerdotai/ModernBERT-base/blob/8949b909ec900327062f0ebf497f51aef5e6f0c8/README.md), and [model API record](https://huggingface.co/api/models/answerdotai/ModernBERT-base/revision/8949b909ec900327062f0ebf497f51aef5e6f0c8).

Runpod listed an A40 with 48 GB memory at USD 0.49 per hour on 2026-09-08. Storage can add cost. Lambda listed an A6000 with 48 GB memory at USD 1.09 per GPU-hour, plus applicable tax. Modal listed an L4 at USD 0.7992 per GPU-hour before separate CPU and memory charges. See [Runpod pricing](https://www.runpod.io/pricing), [Lambda instance pricing](https://lambda.ai/instances), and [Modal pricing](https://modal.com/pricing).

For the Runpod A40:

```text
compute cost = GPU hours x USD 0.49 + storage + tax

hours available before added costs:
  USD 20 / USD 0.49 = 40.82 hours
  USD 25 / USD 0.49 = 51.02 hours
  USD 35 / USD 0.49 = 71.43 hours
```

For three epochs and 216,000 example-passes, the measured end-to-end rate must be at least:

```text
for a USD 20 run: 216,000 / 40.82 / 3,600 = 1.47 examples/second
for a USD 25 run: 216,000 / 51.02 / 3,600 = 1.18 examples/second
for a USD 35 run: 216,000 / 71.43 / 3,600 = 0.84 examples/second
```

These rates do not include setup time, storage, tax, or a failed run. No primary source gives a measured rate for this exact model, data, software, and sequence length. Therefore, the full cost is unresolved.

The earlier 24-hour Stage 1 allowance cannot be copied to the full experiment. The full three-stage workload is six times the Stage 1 workload because `(4,000 + 8,000 + 12,000) / 4,000 = 6`. A simple six-times allowance is 144 A40 hours. At the current price, this is USD 70.56 before storage and tax. This value is a conservative allowance, not a measured forecast.

**Result:** USD 35 can be enough only if the 1,024-token pilot proves it. Reserve USD 5 for the pilot. Do not start the full three-stage run unless the measured projection, with storage, tax, and one allowed operational repeat, is no more than the remaining USD 30. Stop if memory use is more than 80% of GPU memory, the loss is invalid, the instance continues to bill after shutdown, or the projection exceeds the limit.

## USD 25 GPT blind comparison

OpenAI listed GPT-5.6 Sol at USD 4 for one million input tokens and USD 20 for one million output tokens on 2026-09-08. Cached input is USD 0.40 for one million tokens. The promotional price is available at least through 2026-11-21. The model supports the Batch endpoint. See the [official GPT-5.6 Sol page](https://developers.openai.com/api/docs/models/gpt-5.6-sol).

OpenAI states that `max_output_tokens` includes visible output tokens and reasoning tokens. The response usage record separates reasoning tokens but includes them in output use. See the [Responses API create reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).

Use this standard-price formula. Count each charged attempt:

```text
GPT cost
  = attempts x ((input tokens x USD 4)
              + (output tokens x USD 20)) / 1,000,000
```

The ModernBERT 1,024-token limit is not an OpenAI token count. The GPT prompt, schema, and tokenizer can change the count. The following values are planning cases only.

| Average tokens for each attempt | 2,000 attempts | 6,000 attempts |
| --- | ---: | ---: |
| 1,200 input and 300 total output | USD 21.60 | USD 64.80 |
| 1,500 input and 300 total output | USD 24.00 | USD 72.00 |

The 6,000-attempt case means that every blind item uses all three fixed attempts. It is conservative. A server failure might have no output charge. The provider does not give a general promise that all failed attempts have no charge. Thus, the ledger must count the billed use that the provider returns.

At 1,200 input tokens and 300 output tokens, USD 25 pays for about 2,314 attempts. This gives a reserve of only 314 retry attempts after the 2,000 required first attempts. At 1,200 input tokens and no retries, the average total output must be no more than 385 tokens to stay within USD 25.

OpenAI states that the Batch API gives a 50% discount and returns work within 24 hours. At the first planning size, Batch gives USD 10.80 for 2,000 attempts and USD 32.40 for 6,000 attempts. See the [official Batch API reference](https://platform.openai.com/docs/api-reference/batch/object?api-mode=responses). Batch use changes the transport. It needs a separate planning decision before the blind freeze.

An existing subscription route can have USD 0 added cash cost under the project's budget definition. However, this report did not find a public account quota or a public promise that this route can make 2,000 blind calls. It also did not verify that it supports the same output limit and retry controls. Treat these points as unresolved.

**Result:** USD 25 is reasonable for one standard API attempt for each item with short output. It does not cover the maximum three-attempt case. Before the blind run, count tokens on non-blind development inputs with the final prompt and schema. Stop if the projected first attempts plus a declared charged-retry reserve exceed USD 25. Do not start with an uncapped reasoning-output path.

## USD 20 data and storage

The model has about 0.30 GB of BF16 weights or 0.60 GB of FP32 weights. Nine BF16 final seed checkpoints use about 2.7 GB. Three selected BF16 checkpoints use about 0.9 GB. Optimizer state can add about 2.4 GB for one active full-parameter run before activations and temporary files.

GitHub Free includes 10 GiB of Git LFS storage and 10 GiB of monthly LFS bandwidth. A USD 0 LFS budget blocks added use after the free limit. Hugging Face lists 100 GB of private storage for a Free user or organization. See [GitHub LFS billing](https://docs.github.com/en/billing/concepts/product-billing/git-lfs) and [Hugging Face storage limits](https://huggingface.co/docs/hub/storage-limits).

These free limits can hold the selected checkpoints and compact text artifacts. They do not prove that all raw source data can be stored or uploaded. Source terms can require local or private storage. A paid data license can also exceed USD 20.

Use this formula:

```text
data and storage cost
  = source-access fees
  + cloud volume GB-hours
  + retained storage GB-months
  + transfer charges
  + tax
```

**Result:** USD 20 is generous for storage of the planned compact artifacts. It is not a valid reserve for an unknown data license. Keep raw passages local when rights require this. Stop a source if required access or rights cost more than its remaining category balance.

## USD 20 contingency

USD 20 is a reasonable reserve for price movement, tax, a small billed retry count, or temporary storage. It must not hide a failed category plan. Do not use it for paid silver labels, an alternate model, a missing data right, or an automatic blind rerun.

Use contingency only after a new recorded decision names the amount, cause, and new category total.

## Complete budget test

One normal planning case uses 1,200 GPT input tokens, 300 GPT output tokens, no charged retry, and no paid data:

| Category | Planning amount |
| --- | ---: |
| Specialist compute and checks | USD 35.00 limit |
| GPT blind comparison | USD 21.60 estimate |
| Data and storage | USD 5.00 working reserve |
| Contingency | USD 20.00 reserve |
| Total | USD 81.60 |

This case leaves USD 18.40 below the total cap. It still requires the compute pilot and GPT token preflight.

One conservative case uses the six-times training allowance and three charged GPT attempts for every item:

```text
USD 70.56 training allowance
+ USD 64.80 GPT attempts
= USD 135.36 before data, storage, tax, and contingency
```

This case does not fit within USD 100.

Therefore, USD 100 is a valid hard experiment cap. It is not a guaranteed completion budget. The experiment can finish within the cap only when measured use stays in the normal case.

## Required preflight stop conditions

Stop before a stage starts if any condition is true:

1. Fewer than three free non-GPT routes pass all route checks.
2. A route has no exact account quota record.
3. A route can use paid overflow or an automatic model fallback.
4. A provider or model term does not clearly permit the planned text-label and training use.
5. The measured 95th-percentile vote size is more than 800 input and 80 output tokens, and the revised free-route schedule is not accepted.
6. The 1,024-token ModernBERT pilot does not pass memory, loss, speed, and shutdown checks.
7. The projected complete remaining specialist cost is more than the remaining USD 35 category balance.
8. The final GPT prompt and schema have no measured input and total-output token record.
9. The GPT first-attempt forecast plus its declared charged-retry reserve is more than USD 25.
10. The selected GPT transport does not enforce the frozen model, prompt, schema, output limit, and retry log.
11. A source has no free access method and no confirmed right for private evaluation, training, and the planned release.
12. Committed spend will exceed a category limit or the USD 100 total.

## Uncertainty

- Mistral's numeric Free account quota is not public. Check the account Admin panel.
- Groq states that account limits can differ from the public summary. Check the account Limits page.
- No primary source gives training speed for this exact ModernBERT job. Measure it in the pilot.
- ModernBERT tokens and OpenAI tokens are not equal. Count both with the frozen inputs.
- GPT reasoning output can vary. Count all output use, including reasoning tokens.
- A retryable server error does not have one public, universal billing result. Count the provider's returned billed use.
- GPU availability, storage price, tax, and model prices can change. Check them again on the start date.
- Data access and release rights can add an unknown cost. An unknown price is a stop, not a zero-price assumption.

## Final conclusion

Keep the current USD 100 cap and the current category limits for now. They are reasonable control limits for the normal case. Do not state that the complete experiment is already funded.

The two important gates are the complete three-stage ModernBERT pilot projection and the GPT token forecast with retry reserve. If both fit their category limits, and all data and label routes remain free, the experiment can fit within USD 100. If either gate fails, stop and make a new planning decision.
