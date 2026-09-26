# Blind-set rights for the frontier calibration panel

Researched on 2026-09-26 for issue 93 (map 90). This is a clause-level project
audit, not legal advice. No manifest was changed.

## Question

May the Stage 1 blind passages (clean core plus manifest-only CC-NEWS) be sent
to jev (typesafe.ai), an Anthropic model, and a Google model for the
confidence calibration comparison, as they are for the GPT-5.6-sol baseline?

## Answer

- **Clean core, 555 blind candidates: yes, for all four panel providers.**
  Every clean-core blind passage is public domain (VOA) or under CC BY 3.0,
  CC BY 4.0, or CC BY-SA 4.0 (Common Pile News allowlist). These grants are not
  tied to a recipient, so the provider does not matter.
- **Manifest-only CC-NEWS, 76 blind candidates: no, for any external
  provider, and this includes GPT-5.6-sol.** The current publisher terms bar
  or do not grant transmission of the text to a third-party service. The
  recorded audit captured only the permissive sentences of each page.
- **Effect:** the panel can use at most 555 of the 631 blind candidates. In the
  frozen allocation, the panel can use the 350 clean-core blind examples, not
  the 50 CC-NEWS examples. That is 350 of 400.

## What permits GPT today

No recorded document names a model provider. The permission is structural:

1. `docs/stage-1-run.md` requires a `restricted-auxiliary` source to prove
   only `access_permitted` and `private_evaluation_permitted`
   (`BLIND_ONLY_RIGHTS` in `nlp_wayfinder/stage_run.py`). These rights attach
   to the source, not to an evaluator. The gate has no field for a recipient
   or provider.
2. `manifests/cc-news.filtered-source-v1.json` records, for each publisher,
   one permissive clause and `"private_evaluation_bar_found": false`. The
   basis is the absence of a bar, not an affirmative grant.
3. `predict-blind-gpt` sends the passage, company, and aspect to
   `cx/gpt-5.6-sol-medium` (ChatGPT Codex OAuth through OmniRoute, per
   `research/comparison-systems-evidence.md`).

So the recorded basis extends to jev, Anthropic, and Google with no change:
the record makes no provider distinction. The basis itself is the problem.
"Private evaluation" was read to include sending text to a remote model, and
the full publisher terms do not support that reading.

## Manifest-only CC-NEWS: publisher terms

The manifest-only blind passage definition in `CONTEXT.md` states that
manifest-only status does not override source terms that prohibit collection,
retention, or model evaluation.

The private filtered source
(`nlp-wayfinder-data/cc-news/filtered-source-v8`, metadata only; no passage
text was read) has **66 IOL** and **10 Business Recorder** blind candidates.

### Business Recorder, `brecorder.com` (10 candidates)

Source: <https://www.brecorder.com/term-of-use/>. The live page returns HTTP
403 and a bot check, which was not bypassed. The text below is from the
Wayback Machine capture `20260904030056`, the most recent capture before the
2026-09-22 manifest retrieval.

- COPYRIGHT section: the user may not "modify, copy, reproduce, republish,
  upload, post, transmit, or distribute, in any manner" the site material,
  including text.
- The one exception, which the manifest recorded: print and download portions
  "solely for your own non-commercial use".
- NO COMMERCIAL USE: any commercial use needs express permission.

Sending a passage to any remote model API uploads and transmits it. The
exception covers only printing and downloading. **Exclude from every external
provider, GPT-5.6-sol included.** The manifest's
`private_evaluation_bar_found: false` is not correct for a remote model call.
This bar is not specific to AI, but it covers the action.

### IOL, `iol.co.za` (66 candidates)

Source: <https://iol.co.za/iol-terms-and-conditions/>, rendered in a browser
on 2026-09-26. "Date of Last Review 15 January 2009", which is the same as the
audit.

- Clause 4: copy, download, or print visible text "for personal use". It cites
  clause 42 for a definition of personal use, and clause 42 has no such
  definition.
- **Clause 43**, which the audit summarised without its limit: a personal,
  non-transferable licence to use, print, and display content "on any machine
  of which the user is the primary user for non-commercial purposes only".
- Clause 71: users may not "cede, sub-license or otherwise transfer" rights
  obtained through the site.
- Clause 6: any use must carry the notice "© Independent On-line [year]. All
  rights reserved."

A remote provider processes the text on its own machines, not on a machine
of which the project is the primary user. The licence does not reach that
processing. **Exclude from every external provider, GPT-5.6-sol included.**
The audit is correct that no clause names AI evaluation. The grant is still
machine-scoped and cannot be transferred, so the absence of a bar does not
create permission.

### Common Crawl

<https://www.commoncrawl.org/terms-of-use>: crawled content "may be subject to
separate terms" of its owners. Users agree to "respect the copyrights and
other applicable rights of third parties". Common Crawl adds no permission, so
the publisher terms decide.

## Clean core: licence basis

The blind-candidate composition comes from
`nlp-wayfinder-data/stage-1-clean-core-v5/filtered-source.jsonl.gz`
(metadata fields only).

| Publisher | Licence | Blind candidates |
| --- | --- | ---: |
| Voice of America | public domain (`public-domain-voa-produced`) | 336 |
| Global Voices | CC BY 3.0 | 93 |
| Factly | CC BY 4.0 | 60 |
| 360info | CC BY 4.0 | 58 |
| Freedom of the Press Foundation | CC BY 4.0 | 6 |
| Balkan Diskurs | CC BY 3.0 | 1 |
| The Public Record | CC BY-SA 4.0 | 1 |
| **Total** | | **555** |

- VOA: "All text, audio and video material produced exclusively by the Voice
  of America is in the public domain" (`research/voa-news-source-rights.md`).
  Wire copy is already rejected. The contractor-authorship caveat recorded
  there still applies. It does not depend on the provider.
- [CC BY 4.0 §2(a)(1)](https://creativecommons.org/licenses/by/4.0/legalcode.en)
  grants the right to "reproduce and Share", with no field-of-use or recipient
  limit. Attribution (§3) applies when material is Shared, which the licence
  defines as providing it to the public. A private API call is reproduction,
  not public sharing. The Stage 1 attribution records still go with any
  release. [CC BY 3.0 §3](https://creativecommons.org/licenses/by/3.0/legalcode.en)
  and [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/legalcode.en)
  work the same way. ShareAlike applies only to adapted material that is
  shared.
- `research/filtered-common-pile-source-rights.md` requires third-party quotes,
  embeds, and wire text to be stripped before admission. This applies to the
  panel as it does to GPT.

No clean-core passage or publisher needs to be excluded for any panel provider.

## Provider-side conditions (blind integrity, not publisher rights)

The clean-core licences allow each provider to retain the text. Retention or
training on blind inputs still harms the blind reference set, so each route
should meet these conditions.

| Provider | Primary term | Condition for the pinned route |
| --- | --- | --- |
| OpenAI (existing GPT route) | [Help: how your data is used](https://help.openai.com/en/articles/5722486-how-your-data-is-used-to-improve-model-performance): for ChatGPT and Codex, "we may use your content to train our models" unless the user opts out. The API is excluded by default. | `cx/` is a consumer ChatGPT Codex route. Record that "Improve the model for everyone" is off and that Codex "Include environments" is off, and give no thumbs-up or thumbs-down feedback. |
| Anthropic | [Commercial Terms](https://www.anthropic.com/legal/commercial-terms) §B: "Anthropic may not train models on Customer Content from Services". §L.1: the customer warrants "all rights and permissions required to submit Inputs". | Use a commercial API route. A consumer subscription route needs its own data-control record. The §L.1 warranty is another reason to leave out IOL and Business Recorder. |
| Google | [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms): Unpaid Services use submitted content to "improve, and develop" products and allow human review. Paid Services do not use prompts to improve products. | **Paid tier only.** A free-tier Gemini route would disclose blind passages to human reviewers and to training. |
| TypeSafe (jev) | [Privacy Policy](https://typesafe.ai/legal/privacy-policy) (updated 2025-11-19): "We will not train or fine tune any … models on your prompts or other Input." Retention has no fixed period. The [Terms](https://typesafe.ai/legal/terms) (updated 2026-09-19) are silent. | Acceptable. Record the privacy-policy clause, and note that the product is in early access and has no retention limit. |

## Exclusions and blind-set effect

| Set | Blind candidates | Allocation (blind examples) |
| --- | ---: | ---: |
| Current Stage 1 pool | 631 (555 clean core + 76 CC-NEWS) | 400 (350 + 50) |
| Panel-eligible | **555** | **350** |
| Excluded: IOL | 66 | shares 50 with BR |
| Excluded: Business Recorder | 10 | shares 50 with IOL |

- The confidence calibration comparison should score only the sealed blind
  examples from the clean-core source, which is about 350. Report the CC-NEWS
  source as excluded for rights reasons. Do not replace it: no manifest
  changes, per the out-of-scope rules on map 90.
- GPT agreement with the sealed Stage 1 GPT labels should use the same 350.
  This keeps all four systems on one common set.

## Finding outside this ticket (for a human decision)

The same terms apply to the **Stage 1 GPT baseline itself**. On the current
publisher text, sending the 50 CC-NEWS blind examples to `cx/gpt-5.6-sol-medium`
is not supported for IOL (the licence is limited to the primary user's
machine) or for Business Recorder ("upload … transmit"). The pre-seal
threshold is 600 blind candidates. Without CC-NEWS, the pool has 555, so it no
longer passes. This affects issue 46 and the issue 82 source plan. This ticket
does not change them. It should go to a human before the Stage 1 GPT run.
Options: get written permission from IOL (clause 5) and Business Recorder, or
find another restricted-lane or clean-core blind source.

## Evidence gaps

- Business Recorder's live page is behind a bot check. The Wayback capture
  from 2026-09-04 was used. Compare it with a browser-rendered live copy
  before a decision relies on it.
- IOL's clause 4 cites a definition of personal use that does not exist. This
  audit reads the scope from clause 43.
