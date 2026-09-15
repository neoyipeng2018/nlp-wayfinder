# Audit of the fixed free-route terms

**Checked:** 2026-09-15

**Scope:** This memo answers [Audit the fixed free-route terms](https://github.com/neoyipeng2018/nlp-wayfinder/issues/48). Stage 1 sends financial-news passages to three fixed routes. It keeps their text labels and uses the labels to train a narrow sentiment classifier. The local control requires fresh account, route, free-limit, no-paid-overflow, and training-use evidence before a route can enter the panel. See [Stage 1 Run Control](../docs/stage-1-run.md).

This memo is an operational terms audit. It is not legal advice. It uses public primary sources. It does not inspect Yi Peng's provider accounts and does not make a model call.

## Decision

Do not admit the three-route panel yet.

| Fixed route | Training-use terms | Current public route and free-limit evidence | Decision |
| --- | --- | --- | --- |
| `mistral/mistral-medium-3-5` | Pass for text-label training | The exact provider model exists. Mistral documents Free mode, but it does not publish the account's exact limits. | Conditional pass. Yi Peng must complete the account checks below. |
| `cf/@cf/zai-org/glm-4.7-flash` | Pass | The exact model is on Workers AI. Workers Free gives 10,000 Neurons each day and fails after the limit. | Conditional pass. Yi Peng must complete the account checks below. |
| `groq/qwen/qwen3.6-27b` | The terms can permit this narrow training use, subject to the competition restriction below. | Fail. Groq's current active-model catalog and Free-plan limit table omit the exact model. | Do not admit. Replace the route, or get current account-scoped evidence that the exact model is active and free. |

The pinned OmniRoute registry contains all three route mappings. It proves how OmniRoute builds the route names. It does not prove current provider access or free capacity. See the pinned [Mistral registry](https://github.com/diegosouzapw/OmniRoute/blob/488f57e9d3fccc8d1741fdf21d35d5730b118a18/open-sse/config/providers/registry/mistral/index.ts), [Cloudflare registry](https://github.com/diegosouzapw/OmniRoute/blob/488f57e9d3fccc8d1741fdf21d35d5730b118a18/open-sse/config/providers/registry/cloudflare-ai/index.ts), and [Groq registry](https://github.com/diegosouzapw/OmniRoute/blob/488f57e9d3fccc8d1741fdf21d35d5730b118a18/open-sse/config/providers/registry/groq/index.ts).

## Mistral Medium 3.5

### Terms result

Mistral lists the exact provider model ID `mistral-medium-3-5`. It is a General Availability text model. The model page also states that the weights use the Modified MIT license. See the official [Mistral Medium 3.5 model page](https://docs.mistral.ai/models/mistral-medium-3-5-26-04).

The current commercial terms give the customer the rights that Mistral has in text output. The only output-training restriction in section 3.3 is for image output used to train a competing image product. The Stage 1 use trains from text labels, not image output. Therefore, the published terms permit the planned use. The customer must have the rights needed to send each input, and the customer is responsible for output use. See sections 3.1 to 3.3 of the [Mistral Commercial Terms of Service](https://legal.mistral.ai/terms/commercial-terms-of-service/).

Mistral states that Free mode is the default API mode and is for evaluation and prototyping. It also states that exact limits are organization-level and model-specific, and that the account Limits page is the source for the current values. The limits are requests per second, tokens per minute, and tokens per month. See the official [API rate-limit guide](https://help.mistral.ai/en/articles/698531-why-am-i-hitting-api-rate-limits-and-how-do-i-increase-them). Mistral's API reference states that `GET /v1/models` lists all models available to the user and that a chat response contains a `model` field. See the [Models API](https://docs.mistral.ai/api/endpoint/models) and [Chat API](https://docs.mistral.ai/api).

### Evidence Yi Peng must observe

Before admission, save one dated evidence record with these items:

1. The organization and workspace names, with secrets removed.
2. The API plan shown as **Free mode**. The API pay-as-you-go setting must be off. The key must be an API key for this free-mode workspace, not a Vibe plan key. Mistral explains how to return the API plan to Free mode in its [subscription guide](https://help.mistral.ai/en/articles/455205-how-can-i-upgrade-or-cancel-my-subscription).
3. The account-scoped `GET /v1/models` result must contain `mistral-medium-3-5`.
4. The Limits page must show the exact current limits for `mistral-medium-3-5`: requests per second, tokens per minute, tokens per month, and remaining monthly use. Record the values. Do not use the one-billion-token value from OmniRoute as provider evidence.
5. One fixed-route preflight must request `mistral/mistral-medium-3-5`. The Mistral response `model` and the OmniRoute provider/model headers must identify `mistral-medium-3-5`. The OmniRoute record must show zero fallback attempts, no cache, and zero response cost.
6. The subscription capture must show that pay-as-you-go is off. A `429` after a free limit is acceptable. A charge, credit use, paid tier, or automatic paid continuation is not acceptable.

This evidence is a conditional pass only if all values support the planned Stage 1 request count and schedule.

## Cloudflare GLM-4.7-Flash

### Terms result

Cloudflare lists the exact provider model ID `@cf/zai-org/glm-4.7-flash` and gives a direct REST path for it. See the official [GLM-4.7-Flash model page](https://developers.cloudflare.com/workers-ai/models/glm-4.7-flash/).

Cloudflare states that inputs, outputs, embeddings, and training data are Customer Content. The customer owns that content. Cloudflare does not use it to train models without explicit consent. Cloudflare also requires the customer to follow the third-party model license. See [Your Data and Workers AI](https://developers.cloudflare.com/workers-ai/platform/data-usage/). The official Z.ai [GLM-4.7-Flash model card](https://huggingface.co/zai-org/GLM-4.7-Flash) marks the model as MIT licensed. These terms do not prohibit the planned text-label training use.

Workers AI gives the Workers Free plan 10,000 Neurons each day. The limit resets at 00:00 UTC. Later operations fail after the limit. GLM-4.7-Flash uses 5,500 Neurons per million input tokens and 36,400 Neurons per million output tokens. The list of models that require a paid method does not include GLM-4.7-Flash. See the current [Workers AI pricing page](https://developers.cloudflare.com/workers-ai/platform/pricing/). Cloudflare documents error `3036` with HTTP `429` after the daily free allocation. See the [Workers AI error table](https://developers.cloudflare.com/workers-ai/platform/errors/).

### Evidence Yi Peng must observe

Before admission, save one dated evidence record with these items:

1. The Cloudflare account ID and account name, with the API token removed.
2. The Workers plan must be **Workers Free**. It must not be Workers Paid.
3. The Workers AI dashboard must show the 10,000-Neuron daily allocation, current used Neurons, and remaining Neurons for the account.
4. The model catalog or a direct provider request must show `@cf/zai-org/glm-4.7-flash` as available to this account.
5. One fixed-route preflight must request `cf/@cf/zai-org/glm-4.7-flash`. The request path and OmniRoute provider/model headers must show `@cf/zai-org/glm-4.7-flash`. The OmniRoute record must show zero fallback attempts, no cache, and zero response cost.
6. The account must have no Workers Paid plan. Do not route the request through AI Gateway Unified Billing, and do not attach prepaid AI Gateway credits. On this state, use after the daily free allocation must fail instead of creating a charge.

This evidence is a conditional pass only if the planned daily Neuron demand is no more than the remaining daily allocation.

## Groq Qwen3.6-27B

### Terms result

Groq's current agreement says that inputs and outputs are Customer Data. The customer keeps its intellectual-property rights in them. Groq does not use them for model training unless the customer gives permission. See sections 4.2 and 8.1 of the [Groq Services Agreement](https://console.groq.com/docs/legal/services-agreement).

Section 6.3(e) of that agreement prohibits use of Groq Cloud Services to develop or improve an offering that is similar to, or competes with, Groq Cloud Services. Stage 1 trains a narrow financial-news sentiment classifier. It does not build a hosted general inference service. On that stated scope, the restriction does not prohibit the planned use. Recheck the decision if the destination becomes a hosted general model service. Qwen also states that all Qwen3.6 open-weight models use Apache 2.0. See the official [Qwen3.6 repository](https://github.com/QwenLM/Qwen3.6).

The route fails the current identity and free-limit audit. Groq's current [Supported Models](https://console.groq.com/docs/models) page does not list `qwen/qwen3.6-27b`. It lists `qwen/qwen3.8-27b`. The page states that `GET https://api.groq.com/openai/v1/models` returns all active models. Groq's current [Free-plan rate-limit table](https://console.groq.com/docs/rate-limits) also omits `qwen/qwen3.6-27b` and lists `qwen/qwen3.8-27b` instead. A deprecation-history page still mentions Qwen3.6 as an old replacement recommendation. This mention is not current active-model or limit evidence.

### Evidence needed to remove the block

Do not admit `groq/qwen/qwen3.6-27b` now. A later check can remove the block only if Yi Peng saves all these items:

1. The organization and project names, with the API key removed.
2. The Billing page must show **Free tier**. Groq states that an upgrade to Developer tier needs a payment method and that paid use stops after a downgrade to Free tier. See the official [Billing FAQs](https://console.groq.com/docs/billing-faqs).
3. The account-scoped `GET /openai/v1/models` result must contain the exact ID `qwen/qwen3.6-27b`.
4. The account Limits page must give the exact Free-tier RPM, RPD, TPM, TPD, and remaining requests for that exact model. Groq says that account limits can differ from its summary table. Do not copy an old public value into the evidence.
5. One fixed-route preflight must request `groq/qwen/qwen3.6-27b`. The provider response and OmniRoute provider/model headers must identify `qwen/qwen3.6-27b`. Groq's documented rate-limit headers must show the request and token limits and the remaining amounts. The OmniRoute record must show zero fallback attempts, no cache, and zero response cost.
6. The account must stay on Free tier. It must have no Developer-tier billing and no service-credit auto-reload. A `429` at a free limit is acceptable. Any paid continuation is not acceptable.

If any item is absent, choose a new fixed route through a separate decision. Do not silently replace Qwen3.6 with Qwen3.8.

## Required capture format

For each route, keep the official URLs, UTC retrieval time, reviewer name, account or organization name, exact observed route ID, exact account limits, remaining free capacity, account tier, and the no-paid-overflow state. Remove API keys, tokens, payment details, and other secrets. Keep a screenshot or an official API response for each account-only fact. Hash the complete evidence record before manifest confirmation.

Repeat the check if it becomes more than 30 days old before `starts_on`, or if a provider changes a model, plan, limit, or term.
