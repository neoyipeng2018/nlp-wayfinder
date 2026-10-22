# A fresh open-rights news source for a sealed test

Researched 2026-10-22/23 for issue #159 (map #157). The question: which public-domain or CC BY / BY-SA news sources can supply about 400–600 fresh company-target passages for a sealed test, disjoint from what the quick loop has used (VOA/MOT, Common Pile News, CC-News), with unused periods of those counting too.

**Containment.** This note holds counts, URLs of rights pages and rates only. It quotes no passage text and no company names. It reads no EX-99 text.

## Answer

No single *new-period* source reaches 400 by itself. Three routes do, alone or combined:

| # | Route | Rights | Period | Passages (est.) | Access | Status |
|---|---|---|---|---|---|---|
| A | **Stage 1 clean-core blind split, never read** (+ unread dev) | VOA public domain; CP publishers CC BY 3.0/4.0, BY-SA 4.0 (already audited) | blind 2023–2024; dev 2022 | **555 built** blind (VOA crawl 336 + CP 219) → roughly 370–430 after the company check; + about 199 unread dev | already on disk: `~/nlp-wayfinder-data/stage-1-clean-core-v5/` | Ready now. **It is #46's sealed blind set.** Using it for #157 spends it. |
| B | **Same 8 CP publishers + VOA, after the archive/crawl** | same first-party statements, re-checked 2026-10-23 | CP: Jun 2024 → Oct 2026; VOA: 1 Jan → about 14 Mar 2025, plus a 2026 trickle | about **280 candidates**, about 190 after the company check | publisher sitemaps + fresh crawl (or Common Crawl CC-NEWS WARCs filtered to these hosts) | New crawl and build. Short on its own. |
| C | **English Wikinews** (new source) | CC BY 4.0 after 16 Dec 2024; CC BY 2.5 from 25 Sep 2005 to 16 Dec 2024; public domain before that | mostly 2005–2012; a few articles a year now | about **790 business articles with a hit**, about 530 after matcher precision | Wikimedia dumps or the MediaWiki API | New build. Source-disjoint, but **not period-fresh**. |

**Recommendation.** Route A is the only one that is built, period-fresh and large enough today. It costs #46 its blind set, so that is a user call. If #46's blind set must stay untouched, use **B + C**. B gives the period-fresh core (about 190). C fills it to about 400–600 and adds a source the model has never trained on. Report B and C as separate slices, because C shares the 2005–2021 training period.

## Route A: the never-read Stage 1 splits

- `stage-1-clean-core-company-target-v1` (`stage-1-clean-core-v5/summary.json`, built 2026-09-22) has 7,412 training / 339 development / **555 blind** passages. The blind split is VOA crawl 336 + Common Pile 219. Dates: VOA blind 2023-01-05 → 2024-12-31 (file); CP blind 2023–2024 (file: 360info 58, Factly 60, Global Voices 93, Freedom 6, Balkan Diskurs 1, The Public Record 1).
- `research/dataset-lineage.md` (§2.1, §5 items 4 and 6): every quick-loop news passage came from the **training** split (2000–2021-dominated). The **blind split was never read**. About 199 of 339 dev passages (2022) are unread.
- The training data never touched 2022–2024, so this split is out-of-period as well as id-disjoint. gold-v5 is not out-of-period (lineage §5 item 6).
- **Company check loss:** 22% of matcher targets were non-companies on clean-core (#107), and 32–34% on random news draws (#131, #139, #149). 555 × 0.66–0.78 ≈ **370–430** usable. The unread dev passages (2022) could top it up to about 500–580.
- **Conflict:** map #46 ("Run the sealed Stage 1 financial-news comparison") is still OPEN and reserves this blind split. Spending it here means #46 needs a new blind set or closes. Note also that the source is the one the Stage 1 counts were tuned around (`voa-news-widened-count.md`), but no 2022–2024 page was read during tuning.

## Route B: unused periods of the sources already admitted

### Rights (primary sources, re-checked 2026-10-23)

- **VOA**: "All text, audio and video material produced exclusively by the Voice of America is in the public domain … voanews.com content may also contain … copyrighted material that is licensed for use in VOA programming only" ([VOA terms, /p/5338.html](https://www.voanews.com/p/5338.html)). The existing byline and wire-credit filters still apply.
- **360info**: "licence all content created and distributed by 360info under the terms of the Creative Commons Attribution 4.0 International Licence … except for" logos and third-party items ([How to use our content](https://360info.org/how-to-use-our-content/)).
- **Factly**: "Except for videos, content on this site is licensed under a Creative Commons Attribution 4.0 International License" ([factly.in](https://factly.in/) footer).
- **Global Voices**: "This site is licensed as Creative Commons Attribution 3.0" and "all content created by Global Voices is published under a Creative Commons Attribution-Only license" ([attribution policy](https://globalvoices.org/about/global-voices-attribution-policy/)).
- **Freedom of the Press Foundation**: "Licensed under Creative Commons CC-BY 4.0 where not otherwise indicated" ([About](https://freedom.press/about/)).
- Alt News, Balkan Diskurs, Oxpeckers and The Public Record were not re-fetched. Their 2026-09-16 evidence is in `research/filtered-common-pile-source-rights.md`, and their yield is near zero anyway (below).

### Where the unused period starts

- The **Common Pile News** archive (`common-pile/news` @ `13e76bd…`) records `added` 2024-05-27, so publisher articles from about **June 2024 on are not in it**.
- The **VOA crawl** pinned an ID window through 2024. The last blind-split article ID is 7920698 (2024-12-31, file).

### Volume (sitemap counts 2026-10-23 × the 2023 passage rate per article)

| Publisher | 2023 articles | 2023 passages (file) | Rate | Unused-period articles | Est. passages |
|---|---:|---:|---:|---|---:|
| Global Voices (URL dates) | 1,204 | 60 | 5.0% | about 600 (H2 2024) + 1,006 (2025) + 484 (2026 YTD) | **about 105** |
| 360info (sitemap lastmod) | 545 | 41 | 7.5% | about 500 (H2 2024) + 331 + 126 | **about 70** |
| Factly (sitemap lastmod; 1 of the sitemaps timed out) | 2,003 | 43 | 2.1% | about 1,180 + 980 + 717 | **about 60** |
| Freedom, Balkan Diskurs, Public Record, Oxpeckers, Alt News | — | 6 | — | — | about 10 |
| VOA English | — | 336 (2023–24) | — | **3,528** article URLs with ID > 7920698 up to about 14 Mar 2025, then **77** up to Oct 2026 | **about 35–40** (time pro-rata of 336 over 24 months) |
| **Total** | | | | | **about 280 candidates → about 190 usable** |

- VOA sitemap (`https://www.voanews.com/sitemap.xml`, 51 shards): 35,876 IDs fall above the blind window, but 32,271 are slugless `/a/<id>.html` stubs. The 3,605 slug URLs run from 2025-01-01 to 2025-03-10 in the IDs sampled, then jump to 2026 (a few dozen). This fits the March 2025 VOA shutdown and the partial 2026 restoration ordered by a court ([WTOP/AP, 2026-03](https://wtop.com/national/2026/03/judge-orders-restoration-of-voice-of-america-putting-hundreds-of-journalists-back-to-work/)). So VOA adds almost nothing new.
- The estimates use sitemap `lastmod` for 360info and Factly, which can be an edit date. Treat them as ±30%.
- **In-archive pocket (same rights, not fresh):** the CP filter dropped 4,146 Alt News and about 400 Oxpeckers records as `publication-date-outside-fixed-periods` because their dates did not parse (`common-pile-news/filtered-source-v6/exclusions.jsonl.gz`). Fixing the date parser would add an unknown, probably small, number of 2014–2024 passages. Alt News has given 0 passages so far.
- **Access:** crawl the publisher sitemaps and rebuild with the existing CP and VOA build controls. An alternative is Common Crawl **CC-NEWS** WARCs from June 2024 on, filtered to these hosts. The licence then comes from the publisher, not from CC-News; `stanford-oval/ccnews` stops in June 2024, so it does not help. The already-audited CC-NEWS IOL lane stays non-commercial and unusable.

## Route C: English Wikinews

- **Rights (first party):** "All material published on Wikinews after December 16, 2024 is licensed under … Creative Commons Attribution 4.0 … Material published prior December 16, 2024 but after September 25, 2005 is licensed under … Creative Commons Attribution 2.5 … This work may be attributed to 'Wikinews'. All material published prior to September 25, 2005, is in the public domain" ([Wikinews:Copyright](https://en.wikinews.org/wiki/Wikinews:Copyright), via the API 2026-10-23). The site rightsinfo reports CC BY 4.0. Common Pile's `wikimedia` card labels all its wikis CC BY-SA ([card](https://huggingface.co/datasets/common-pile/wikimedia)). That is wrong for Wikinews, so take the licence from the Wikinews page, keeping the per-date 2.5/4.0 split. Wikinews is in Common Pile `wikimedia`, not in Common Pile News, so it is disjoint from what we used.
- **Volume:** `Category:Published` has 22,222 pages and `Category:Economy and business` 2,365 (API categoryinfo). Sample: 80 random E&B articles (seed 20261023), body only, `any-named-company-claim-v2` (SHA-256 `e3979e7d…`, the frozen #82 rule) → **27 / 80 (34%) have at least one hit**. That gives about 790 E&B articles with a candidate. At the rule's measured 67% precision (`voa-news-widened-count.md`), that is about **530**. Articles outside E&B add more.
- **Period:** the sample is 2005–2012 heavy (75 of 80), with few articles after 2012. The newest E&B articles are from 2025–2026, but only a handful. So Wikinews is **source-fresh, not period-fresh**: it overlaps the 2000–2021 training period.
- **Caveats:** Wikinews articles are rewrites that cite other outlets. The text is Wikinews's own, but quotations must be stripped (the existing block-quote and direct-quote filters). Editorial style is closer to wire copy than to VOA or Global Voices. Attribution is "Wikinews", with a link and the licence.
- **Access:** `enwikinews` dumps from dumps.wikimedia.org, or the MediaWiki API (`prop=extracts`). Keep only pages in `Category:Published`.

## Checked and rejected

| Source | Reason |
|---|---|
| The Conversation | "publish all our work under a Creative Commons — Attribution/No Derivatives license … You can't edit our material" ([guidelines](https://theconversation.com/us/republishing-guidelines)). ND: no passage extraction. |
| Milwaukee NNS (in CP) | CC BY-ND 4.0, with database extraction banned (`filtered-common-pile-source-rights.md`). |
| Other 8 CP News sources | No exact licence version (same memo); unchanged. |
| CC-NEWS / IOL | Non-commercial only (`cc-news-publisher-rights-audit-v2.md`, #105, #129). |
| Agência Brasil (EBC) | Reported CC BY 4.0, but the site timed out twice and I could not confirm it. Mostly Portuguese. Not verified, so not counted. |
| US agency press releases (SEC, FTC, DOJ) | Public domain under 17 U.S.C. §105, but these are enforcement releases, not news. Their sentiment is skewed negative and the distribution does not match. Not counted. |

## Open decisions for the map

1. **Spend #46's blind set (A), or build fresh (B + C)?** A is ready and period-fresh. B + C needs a crawl, a build and a rights rebuild, with no API spend.
2. If B + C: is a period-overlapping but source-new slice (Wikinews) acceptable in a "fresh" test? The alternative is to report it as a separate source-shift slice.
3. All three routes need the same company check (Opus labeller `x`) and draw spec as gold-v5. Plan for about 30% loss.

## Reproduce

The scratch scripts used (counts only) were `sm.py` (sitemap counts per year), `voa_ids.py` (VOA IDs above the blind window) and `wn_sample.py` (Wikinews hit rate). They stayed in the session scratchpad. Each is about 20 lines and can be rewritten from the descriptions above.
