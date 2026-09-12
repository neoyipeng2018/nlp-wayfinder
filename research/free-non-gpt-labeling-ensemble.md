# Evidence memo: free non-GPT labeling ensemble

**Retrieval date:** 2026-09-04  
**Scope:** Evidence for [“Find a valid free non-GPT labeling ensemble”](https://github.com/neoyipeng2018/nlp-wayfinder/issues/19). This memo uses official provider terms, official model and quota pages, official model licenses, and pinned OmniRoute source. It makes no model call and creates no provider account.

## Decision

Use this conditional, fixed ensemble:

1. `mistral/mistral-medium-3-5`
2. `cf/@cf/zai-org/glm-4.7-flash`
3. `groq/qwen/qwen3.6-27b`

These routes use Mistral Medium 3.5, GLM-4.7-Flash, and Qwen3.6-27B. They use three model families and three inference providers. They are not GPT models. Each route names one model. None is an automatic router, Fusion result, or `latest` alias.

This ensemble can have zero marginal labeling cost. However, the full run must be slow enough to stay in the free limits. The Groq route is the limit. A 12,000-example run can need about 53 days. A 20,000-example run can need about 88 days. These estimates use 800 input tokens and 80 output tokens for each vote. They also assume that each route labels each candidate once.

Use the ensemble only after three no-call checks:

- Confirm that each exact route is present in the installed OmniRoute model list.
- Confirm that the provider console gives the expected free mode to the account.
- Disable paid use. A free-limit error must stop that route. It must not cause a paid fallback or a model substitution.

If one check fails, do not start labeling. Use a listed replacement or reduce the candidate count. Do not silently change a route.

## Primary routes

### `mistral/mistral-medium-3-5`

Mistral lists `mistral-medium-3-5` as a fixed major-and-minor model ID. Mistral states that a fixed major-and-minor ID does not receive the silent alias changes that apply to `latest` and major aliases. The model is General Availability and supports structured outputs. See the [Mistral model page](https://docs.mistral.ai/models/mistral-medium-3-5-26-04) and [model lifecycle policy](https://docs.mistral.ai/inference/model-lifecycle).

Mistral Free mode supports API keys without a credit card. Mistral says that Free mode is for evaluation and prototyping. Mistral does not publish the numeric account limit on a public page. It tells users to read the limit in the Admin panel. See the [API quickstart](https://docs.mistral.ai/getting-started/quickstarts/developer/first-api-request) and [rate-limit guide](https://help.mistral.ai/en/articles/698531-why-am-i-hitting-api-rate-limits-and-how-do-i-increase-them).

The pinned OmniRoute catalog records a console check on 2026-09-02 and assigns one shared 1 billion-token monthly pool to Mistral Free mode. This number is secondary evidence because the provider does not publish it. Confirm it in the account before the freeze. See the pinned [free-model catalog](https://github.com/diegosouzapw/OmniRoute/blob/488f57e9d3fccc8d1741fdf21d35d5730b118a18/open-sse/config/freeModelCatalog.data.ts#L278-L289).

Mistral assigns its rights in text output to the customer. Its output restriction applies to image-output training, not text-output training. See Sections 3.1 and 3.3 of the [Mistral Commercial Terms](https://legal.mistral.ai/terms/commercial-terms-of-service/). The task is an internal experiment. Do not give the API key or the service to another person.

The pinned OmniRoute registry maps the provider alias `mistral` to the Mistral API and lists `mistral-medium-3-5` directly. See the pinned [Mistral registry](https://github.com/diegosouzapw/OmniRoute/blob/488f57e9d3fccc8d1741fdf21d35d5730b118a18/open-sse/config/providers/registry/mistral/index.ts).

**Result:** Accept, subject to an account-limit check. The planned volume is much smaller than the recorded free pool.

### `cf/@cf/zai-org/glm-4.7-flash`

Cloudflare lists the exact model ID `@cf/zai-org/glm-4.7-flash`. The model has a 131,072-token context window. The upstream GLM-4.7-Flash model card uses the MIT license. See the [Cloudflare model catalog](https://developers.cloudflare.com/workers-ai/models/) and the official [GLM-4.7-Flash model card](https://huggingface.co/zai-org/GLM-4.7-Flash).

Cloudflare includes Workers AI on the Free plan. The free allocation is 10,000 Neurons each day. The limit resets at 00:00 UTC. On the Free plan, use above the limit fails. It does not create an overage charge. GLM-4.7-Flash uses 5,500 Neurons for 1 million input tokens and 36,400 Neurons for 1 million output tokens. See the [Workers AI price and free-limit table](https://developers.cloudflare.com/workers-ai/platform/pricing/) and [Workers AI errors](https://developers.cloudflare.com/workers-ai/platform/errors/).

Cloudflare states that input, output, and training data are Customer Content. The user owns this content. Cloudflare does not use it to train models without explicit consent. Third-party model terms still apply. See [Your Data and Workers AI](https://developers.cloudflare.com/workers-ai/platform/data-usage/). The MIT model license permits use of the model output for this labeling task.

The pinned OmniRoute registry maps `cf` to Workers AI and lists the exact GLM route. See the pinned [Cloudflare registry](https://github.com/diegosouzapw/OmniRoute/blob/488f57e9d3fccc8d1741fdf21d35d5730b118a18/open-sse/config/providers/registry/cloudflare-ai/index.ts).

**Result:** Accept. The official free limit is a hard stop. At the planning token size, 12,000 examples need about 87,744 Neurons, or nine daily grants. A 20,000-example run needs about 146,240 Neurons, or 15 daily grants.

### `groq/qwen/qwen3.6-27b`

Groq lists the exact model ID `qwen/qwen3.6-27b`. Its Free plan limit is 1,000 requests per day, 8,000 tokens per minute, and 200,000 tokens per day. Groq states that limits apply at organization level. See the official [Groq model catalog](https://console.groq.com/docs/models) and [Free plan limits](https://console.groq.com/docs/rate-limits).

Qwen states that all Qwen3.6 open-weight models use Apache 2.0. See the official [Qwen3.6 repository](https://github.com/QwenLM/Qwen3.6). This license does not prohibit the planned label use.

Groq defines outputs as Customer Data. It does not use input or output to train a model unless the customer gives permission. Groq prohibits use of its cloud service to develop a product or service that is similar to, or competes with, the Groq cloud service. The planned result is an internal, local sentiment classifier, not an inference-cloud service. Keep the work internal during this experiment. Review the terms again before a hosted or commercial release. See Sections 4.2 and 6.3 of the [Groq Services Agreement](https://console.groq.com/docs/legal/services-agreement).

The pinned OmniRoute registry maps `groq` to the Groq API and lists the exact Qwen route. See the pinned [Groq registry](https://github.com/diegosouzapw/OmniRoute/blob/488f57e9d3fccc8d1741fdf21d35d5730b118a18/open-sse/config/providers/registry/groq/index.ts).

**Result:** Accept for this internal experiment. The 200,000-token daily limit controls the schedule. At 880 tokens per vote, 12,000 examples need 10.56 million tokens, or about 53 daily grants. A 20,000-example run needs 17.6 million tokens, or about 88 daily grants.

## Replacements

Use no more than one replacement for a failed primary route. Record the change before collection starts.

1. `groq/qwen/qwen3.8-27b` can replace the Qwen3.6 route. Groq gives it the same published free limits. It stays in the Qwen family, so it does not improve family diversity.
2. `cf/@cf/google/gemma-4-26b-a4b-it` can replace the GLM route. Cloudflare lists this exact model and gives it the same shared Workers AI free allocation. It uses 9,091 Neurons per 1 million input tokens and 27,273 Neurons per 1 million output tokens. It shares the Cloudflare pool, so do not use it as a fourth simultaneous vote. The [Gemma terms](https://ai.google.dev/gemma/terms) state that Google claims no rights in output and expressly define a model trained with synthetic Gemma output as a Model Derivative.

The pinned OmniRoute source lists both replacement IDs. See the pinned [Groq registry](https://github.com/diegosouzapw/OmniRoute/blob/488f57e9d3fccc8d1741fdf21d35d5730b118a18/open-sse/config/providers/registry/groq/index.ts) and [Cloudflare registry](https://github.com/diegosouzapw/OmniRoute/blob/488f57e9d3fccc8d1741fdf21d35d5730b118a18/open-sse/config/providers/registry/cloudflare-ai/index.ts).

## Routes not accepted

- Do not use Gemini API free routes. Google permits professional API use and does not claim output ownership. However, its current terms prohibit use of the service to develop models that compete with Gemini API or Google AI Studio. This project explicitly trains a model to match a frontier service on one task. This is too close to the prohibited case. Google also uses unpaid input and output to improve its products. See the [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms).
- Do not use `latest`, `auto`, `free`, provider-choice, fallback, combo, or Fusion routes. They do not fix one model identity.
- Do not use web-session, keyless, or unofficial proxy routes. Their automated-access permission or stable quota is not clear.
- Do not use one-time credits as a primary source. DeepSeek, Hyperbolic, and Scaleway do not give a recurring free quota large enough for all three stages in the pinned OmniRoute catalog.
- Do not use two routes from one shared quota pool as independent capacity. A pool is capacity for the provider, not capacity for each listed model.

## Capacity and USD 100 limit

The amount of later-stage training data is not fixed. Use both planning cases below.

| Case | Candidate examples | Calls | Tokens per route | Mistral | Cloudflare GLM | Groq Qwen |
| --- | ---: | ---: | ---: | --- | --- | --- |
| 4,000 added at each stage | 12,000 | 36,000 | 10.56M | Fits recorded monthly pool | About 9 days | About 53 days |
| 4,000 for each of five sources | 20,000 | 60,000 | 17.60M | Fits recorded monthly pool | About 15 days | About 88 days |

The calculation uses 800 input tokens and 80 output tokens for each call. Keep a live token ledger. Stop and revise the plan if the measured 95th-percentile call size is above this value.

The labeling cost is USD 0 if all three routes stay in free mode. This leaves the USD 100 external-spend cap for training, storage, and the blind GPT-5.6-sol comparison. A fast run with paid overflow is not safe under the same total cap. At current list prices, paid Mistral and Groq labeling for the 20,000-example case can use about USD 50 before training or comparison costs. Therefore:

- Treat free capacity as a schedule constraint.
- Do not attach a payment method to a labeling route unless a later budget decision permits it.
- Do not use paid fallback or automatic fallback.
- Stop a stage when a free quota ends. Continue after reset.
- Keep the present USD 100 cap. The full staged experiment is feasible only if labeling stays free and the experiment accepts the slower Groq schedule.

## Freeze record

Before the first label call, record:

- OmniRoute commit and installed version;
- exact provider and model route;
- provider-plan name and a dated quota screenshot or exported limit record;
- prompt, schema, reasoning setting, temperature, token limit, and retry rule;
- returned provider and model identity for each vote;
- input, output, error, retry, time, and free-quota use for each call;
- a hard rule that an error cannot trigger a model substitution.

Use pinned OmniRoute source revision [`488f57e9d3fccc8d1741fdf21d35d5730b118a18`](https://github.com/diegosouzapw/OmniRoute/tree/488f57e9d3fccc8d1741fdf21d35d5730b118a18) as the implementation evidence for this decision.
