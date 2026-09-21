# VOA staff-news source: count under the widened target rule

## Result

The widened target rule multiplies the VOA counts by about 3.1 to 3.7. The source
is still short, and it is not sealed.

| Split | v1 listed-only | v2 widened | Pre-seal target | Lift |
| --- | ---: | ---: | ---: | ---: |
| Development (2022) | 85 | **261** | 300 | 3.07x |
| Blind (2023–2024) | 156 | **571** | 600 | 3.66x |
| Training (2000–2021) | 25 | **68** | 4,000 | partial crawl |

The development and blind counts are complete: the crawl got every sitemap article
URL in the pinned ID window, which covers all of 2022, 2023, and 2024. The training
count is not a measurement. The crawl stopped before the pinned training subset, so
only 1,665 training-period articles of the 153,648 pinned URLs were crawled.

Passage rate against eligible staff articles:

| Split | Eligible articles | Passages | Rate |
| --- | ---: | ---: | ---: |
| Development | 5,503 | 261 | 4.74% |
| Blind | 9,146 | 571 | 6.24% |
| Training | 1,665 | 68 | 4.08% |

## The decisive number: precision

The widened rule has no company list, so a false positive is a different failure
from the v1 rule. Precision was measured on a fixed-order sample of 30 of the 68
**training-period** passages. No development passage and no blind passage was read.

**20 of 30 passages, 67%, hold at least one correct company target.**

The 10 failures group as follows:

| Failure | Count | Examples |
| --- | ---: | --- |
| Place | 4 | "West Bank", "Abidjan", "Siberia's Yamal Peninsula" |
| Generic noun kept as a name | 3 | "Package", "Fund", "Flight 17" |
| Person | 2 | "Yun Sun", "Jack Hanick" |
| Research or policy body | 1 | "Atlas Public Policy" |

The v1 rule measured 7 of 9 on its tuning sample, about 78%. The widened rule is
below that.

Applying 67% to the candidate counts gives the verified projection:

| Split | Candidates | At 67% | Allocation |
| --- | ---: | ---: | ---: |
| Development | 261 | about 175 | 200 |
| Blind | 571 | about 383 | 400 |

**VOA alone cannot fill the development split or the blind split, even under the
widened rule.** The shortfall is small, which is new: the v1 gap was 3.5x, and the
remaining gap is about 14% on development and about 4% on blind.

## Fixed input

- Source ID: `voa-news-staff-company-target-v2`
- Build configuration: `manifests/voa-news.filtered-source-v2.json`
- Target rule: `scripts/claim_company_matcher.py`, SHA-256
  `e3979e7d17ef980a06f8816842a3142f3bd3b287dd49c1e99f2f84046a7d9346`. The rule was
  frozen into the configuration before the count was run.
- Rule tuning: training-period pages in crawl shard 00000 only, 507 eligible
  articles. No 2022–2024 page was read during tuning.
- Input pages: the same 35 crawl shards as the v1 count. No new crawl was made.
- Company snapshot: none. The widened rule holds no company list.

## What the widened rule does

A hit must pass a company test and a claim test, because a mention is not a target.

1. **Company test.** One of: a legal-form word attached to the span; a company-type
   word inside the span; a company descriptor before or after the span; a possessive
   company role; a share reference.
2. **Claim test.** A financial-claim word within 120 characters of the span, outside
   the span itself.

Guards refuse a place, a person, a state or policy bank, a nonprofit or advocacy
body, and a government or court body. One capitalized span gives at most one
company: its longest qualifying tail.

## Artifacts

- Build summary and hashes: `research/voa-news-widened-count-summary.json`
- Candidate list (not sealed): `manifests/stage-1.voa-news-widened-count-pool.json`
- Candidate-pool SHA-256:
  `f88a55b9eea5bf8af1e4b20d6304526ac03c93ef5d1bc3fce81293f640789a02`
- Raw pages, exclusions, and the filtered source stay outside the repository at
  `~/nlp-wayfinder-data/voa-news/build-window-v2/`.

## Open decisions

1. **Precision.** 67% is below the v1 rule. A tightening round on training-period
   passages would raise it. The count in this memo was made with the frozen rule,
   so a tightening round must re-freeze the rule and re-count. Because the counts
   above are now known, a new round cannot claim to be independent of them. This
   needs an explicit call.
2. **The second source.** VOA cannot fill development or blind alone. The research
   memo on branch `research/stage-1-source-candidates` names Multilingual Open Text
   for training and CC-NEWS, manifest-only, for blind. Both need a download, so both
   need approval before any step.
3. **The training crawl.** 68 passages from 1,665 crawled training-period articles
   is 4.08%. At that rate the full pinned subset of 153,648 URLs projects about
   6,200 training passages, above the 4,000 target. This is a projection from a
   partial crawl, not a count.
