# Choose financial target families and the shared aspect ontology

GitHub: https://github.com/neoyipeng2018/nlp-wayfinder/issues/6

Type: grilling
Status: closed
Blocked by: 01

## Question

Which financial-target families belong in the first experiment, which roughly 8–12 canonical aspects form the shared ontology, and which target–aspect combinations are applicable, invalid, or intentionally out of scope? The decision must make company, instrument, asset, institution, government, and macro-indicator examples labelable without collapsing into free-text aspects.

## Answer

Ontology version 1 has exactly two target families: **company** and **macro indicator**. A company target is a publicly traded issuer, including a listed bank, insurer, exchange, or other financial firm when treated as a company. Its shares, bonds, and other securities are distinct instrument targets and are out of scope. A macro target is one of nine normalized, colloquial news concepts: inflation and cost of living; economic growth and output; employment and unemployment; wages and household income; consumer spending and retail activity; business and industrial activity; housing and construction activity; trade and external balance; or the interest-rate environment. The passage may supply geography and timeframe; unnormalizable broad language such as "the economy" is invalid.

The shared ontology is this fixed 12-aspect union:

| Aspect | Company | Macro indicator |
|---|:---:|:---:|
| Financial performance | Applicable | Invalid |
| Demand and commercial traction | Applicable | Invalid |
| Operations, supply, and capacity | Applicable | Invalid |
| Financial position and funding | Applicable | Invalid |
| Capital allocation | Applicable | Invalid |
| Management and governance | Applicable | Invalid |
| Legal and regulatory position | Applicable | Invalid |
| Risk and resilience | Applicable | Applicable |
| Outlook and expectations | Applicable | Applicable |
| Current condition | Invalid | Applicable |
| Trend and momentum | Invalid | Applicable |
| Drivers and pressures | Invalid | Applicable |

An applicable company pair is classified as positive, neutral, negative, or insufficient evidence. An applicable macro-indicator pair is classified as increase, unchanged, decrease, or insufficient evidence. An invalid pair is rejected before classification. Instruments, assets, governments, stand-alone institutions, market-performance/valuation aspects, and any target outside the two families are intentionally out of scope. Out-of-scope entities may still appear as evidence in a passage.

Company polarity means favorability for the supplied company–aspect condition. Macro-indicator direction means the indicator's stated movement, regardless of whether that movement is desirable or differs from expectations. For example, inflation that rose by less than forecast is still `increase`, and unemployment that fell while remaining above forecast is still `decrease`. `Unchanged` requires evidence of stability or no material movement; absent or inadequate directional evidence is `insufficient evidence`.

Use the narrowest independently supported aspect: one claim is not copied across facets merely because its consequences could reach them. Outlook requires explicit forward-looking evidence, and risk requires explicit exposure, uncertainty, vulnerability, or shock-absorption evidence. A passage may yield multiple examples only when it independently supports each aspect. This is ontology version 1; **Draft and test the labeling manual** may propose revisions if concrete edge cases expose ambiguity.
