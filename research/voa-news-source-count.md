# VOA staff-news source: pre-seal count

## Result

The filtered VOA source does not reach the pre-seal counts. The source is not sealed.

| Split | Passages found | Passages required | Short by |
| --- | ---: | ---: | ---: |
| Development (2022) | 85 | 300 | 215 |
| Blind (2023–2024) | 156 | 600 | 444 |
| Training (2000–2021) | 25 (partial crawl) | 4,000 | not countable |

The development and blind counts are complete: the crawl got every sitemap article URL
in the pinned ID window, which covers all of 2022, 2023, and 2024. The training count is
partial, because the crawl stopped before the pinned training subset. Yi Peng approved
this stop when the development and blind counts fell short.

## Fixed input

- Source ID: `voa-news-staff-listed-company-v1`
- Build configuration: `manifests/voa-news.filtered-source-v1.json` (all rules pinned
  before any count, commit `b9404b7`)
- Sitemap index: https://www.voanews.com/sitemap.xml, retrieved 2026-09-19,
  URL-list SHA-256 `da17cfbac577979d586570594714f6ef13da973fa2237f509850bc070deff039`
  (940,149 URLs, of which 939,960 are `/a/` article URLs)
- Crawl set: 327,008 URLs. 173,360 in the ID window 6,300,000–7,959,999 (development and
  blind), and 153,648 in the pinned 20% SHA-256 subset of the other URLs (training).
- Crawled: 175,000 pages (shards `00000`–`00034`), at 4 requests each second.
- Company snapshot: SEC `company_tickers_exchange.json`, retrieved 2026-09-19,
  SHA-256 `a4aa20329b32644f7ac3b50ef5fa431343ada802f91286c58423afa88c8f0e55`,
  NYSE and Nasdaq rows only, giving 6,020 distinct match names.
- Rights evidence: `research/voa-news-source-rights.md`.

## Why the count is short

Of the crawled pages, 118,000 are staff-written English text articles in the fixed
periods: 5,503 in 2022 and 9,146 in 2023–2024. Only 1.5% to 1.7% of them have a safe
passage that names a company in the pinned snapshot.

Main exclusions:

| Reason | Records or sentences |
| --- | ---: |
| No safe passage naming a listed company | 321,859 |
| Not a text article (video, audio, photo pages) | 81,088 |
| Not an English VOA `/a/` article URL | 42,422 |
| Byline names a wire agency | 24,038 |
| A sentence credits a wire agency | 7,522 |
| Byline missing | 3,118 |

The estimate in [Choose the fallback Stage 1 financial-news source](https://github.com/neoyipeng2018/nlp-wayfinder/issues/63)
(about 1,400 filtered staff articles for 2022) was about 16 times too high. That estimate
measured staff articles, not staff articles that name a listed company.

Scale of the gap: the development split needs a rate of 5.5% instead of 1.5%. A matcher
with twice the recall would still give about 170 development and about 310 blind
passages. The gap is in the source, not in the matcher.

## Match quality

The 266 passages name mostly large listed companies: Microsoft (20), Apple (14),
Tesla (13), Boeing (10), Taiwan Semiconductor Manufacturing (9), Alibaba (9),
Lockheed Martin (8), Chevron (7), Shell (7), Nike (6). Some false matches remain, for
example "People" (People Corp) and "Cohen" (Cohen & Co).

The matcher rule was tuned only on training-period (2021) pages before any count. On that
tuning sample, 9 of about 507 eligible articles passed, and 7 of the 9 named a real
listed company.

## Artifacts

- Build summary and hashes: `research/voa-news-source-count-summary.json`
- Candidate list (not sealed): `manifests/stage-1.voa-news-short-count-pool.json`
- Candidate-list SHA-256: `03b7221d9534ea0a119d8c9115fad9406b0904e29a5b0e7f1580d68c1c70689e`
- Raw pages, exclusions, and the filtered source stay outside the repository at
  `~/nlp-wayfinder-data/voa-news/`.

## Next

The ticket rule applies: do not seal, record the counts, and open a decision ticket for a
rule change or a new destination.
