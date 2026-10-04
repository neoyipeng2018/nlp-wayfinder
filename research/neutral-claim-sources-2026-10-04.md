# Open-rights sources for neutral company claims

Issue: #105 (child of map #103). Retrieved 2026-10-04. This is a project audit,
not legal advice.

## Answer

No clean source exists. No candidate that is dense in neutral company claims
meets **Open-rights passage text** (`CONTEXT.md`). SEC EDGAR 8-K text and EX-99
press releases are written by the issuers. They are not US Government works,
and no first-party evidence puts them under an open licence. Newswire terms
explicitly prohibit ML training. The best built pool is still the clean-core
training split (`~/nlp-wayfinder-data/stage-1-clean-core-v5`, training split
only). In that pool, about 1% of passages match a neutral-claim pattern. Roughly
a third of those matches are company-specific.

| Candidate | Rights for passage text | Bulk access | Neutral regex: docs with a hit | Hits per 1k words | Verdict |
|---|---|---|---|---|---|
| EDGAR 8-K EX-99 press releases | Issuer copyright. Not a §105 government work. Some carry "© ... All rights reserved". | Free: EDGAR indexes at 10 req/s with a declared User-Agent, or the ZipLime HF mirror | 19/100 (all EX-99); 15/46 (Item 2.02 earnings) | 0.09 | Rejected. Not open-rights. |
| Newswires (PR Newswire, Business Wire, GlobeNewswire) | Wire's property. ToS bans scraping and AI training. | Web only | not sampled | – | Rejected |
| Clean core v5 (VOA + MOT-VOA + Common Pile news) | Public domain (VOA) / CC BY (MOT, Common Pile), already audited | Local | 84/8306 (1.0%) | 0.05 | **Best built pool** |
| CC-NEWS filtered v8 (IOL only) | `restricted-auxiliary`, manifest-only, no training use | Local | 6/76 (7.9%) | 0.45 | Densest, but not usable for training or gold text release |
| Common Pile news filtered v6 | CC BY family, audited | Local | 11/1393 (0.8%) | 0.03 | Already inside clean core |

## 1. SEC EDGAR 8-K and EX-99 exhibits

### Rights

- 17 U.S.C. §105(a): "Copyright protection under this title is not available
  for any work of the United States Government". Source:
  <https://www.law.cornell.edu/uscode/text/17/105>
- 17 U.S.C. §101 limits that term: "A 'work of the United States Government' is
  a work prepared by an officer or employee of the United States Government as
  part of that person's official duties." Source:
  <https://www.law.cornell.edu/uscode/text/17/101>. Issuer employees and
  counsel write 8-K items and EX-99 press releases, so §105 does not apply.
  Filing with the SEC does not transfer authorship.
- SEC site policy, under "Website Dissemination": "Information presented on
  sec.gov is considered public information and may be copied or further
  distributed by users of the web site without the SEC's permission." Source:
  <https://www.sec.gov/about/privacy-information> (last updated 2023-11-29).
  The policy says nothing about filer-authored documents. It does not license
  them, and the SEC cannot license copyright it does not own.
- Issuers assert copyright in the exhibits themselves. In the 100-exhibit
  sample, Workday's EX-99.1 ends "© 2026 Workday, Inc. All rights reserved."
  (<https://www.sec.gov/Archives/edgar/data/1327811/000132781126000024/wday-04302026x991.htm>).
  Booz Allen's EX-99.2 carries "Copyright © Booz Allen Hamilton Inc. 2025"
  (<https://www.sec.gov/Archives/edgar/data/1443646/000162828026037519/bahexhibit992q4fy26_fina.htm>).
  No exhibit in the sample mentions Creative Commons.
- The largest HF mirror agrees. Its `NOTICE` says: "The filings themselves are
  written by the issuers that file them, not by the SEC. Distribution through
  EDGAR does not by itself make issuer-authored text a work of the United
  States Government." Its Apache-2.0 licence covers only its normalisation and
  metadata (<https://huggingface.co/datasets/ZipLime/sec-8k-events/blob/main/NOTICE>).
  This is secondary evidence. It is cited only as consistent with the statute.

Result: EDGAR text is publicly accessible, but it is not open-rights passage
text. Training on it would rest on a fair-use argument. The project's rule does
not allow that argument, so EDGAR text would be a **Quarantined dataset** at
best. Filing metadata (accession numbers, item codes, timestamps) is an SEC
work and is free to use, but it contains no claim text.

### Bulk access

- EDGAR daily, full and feed indexes. "Current max request rate: 10
  requests/second." The User-Agent must follow the form "Sample Company Name
  AdminContact@<sample company domain>.com". Source:
  <https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data>
  (last updated 2024-06-26). A User-Agent without an email address got HTTP 403
  today. This audit did not send the user's email, so it did not call EDGAR
  directly.
- Mirror used for the sample: `ZipLime/sec-8k-events`. It has 35,491 exhibits
  for 2026, 29,191 with text, and an `earnings_8k` view that pairs Item 2.02
  with its EX-99.

### Density sample

The sample used shards `data/exhibits/part-00027` and `part-00050` (605
exhibits, 164 EX-99 with text). From these, 100 EX-99 exhibits were drawn with
seed 105. They were accepted between 2026-05-21 and 2026-09-25, with a median
length of 2,172 words.

- 19/100 exhibits have at least one hit (29 hits, 0.09 per 1k words).
- Exhibits linked to Item 2.02 (earnings): 15/46 (32.6%), 0.10 per 1k words.
- Hits are real and company-specific: "Reaffirms Full Year 2026 Guidance"
  (Advance Auto Parts), "Reiterates full-year outlook" (Williams-Sonoma),
  "Adjusted EBITDA Margin ... remained flat at 11.0%", "will not have a
  material adverse effect on the Company's financial position". Some hits are
  boilerplate: accounting-standard adoption notes, and offer terms that "remain
  unchanged".

Per word, EX-99 text is only about twice as dense as the clean core. The hits
cluster in headlines and highlight bullets, so per document it is much richer.

## 2. Issuer press releases and newswires

- PR Newswire terms (last updated 2023-09-01). Content is "the exclusive
  property of PR Newswire". Use is limited to "your personal, noncommercial
  use". Users must not "'scrape'" or "'data mine'" content, or use it "for the
  development of any software program, including ... training a machine
  learning or artificial intelligence (AI) system". Source:
  <https://www.prnewswire.com/terms-of-use/>
- The Business Wire and GlobeNewswire terms pages returned 403/404 to
  automated fetches today, so this audit has no clause-level evidence for them.
  Both are commercial wires. No open licence was found.
- Issuer investor-relations pages carry the same text as EX-99, under the
  issuer's "All rights reserved" footer. The Workday example above shows this.

Result: rejected. These sources are not open-rights.

## 3. Pools already built under `~/nlp-wayfinder-data`

The rights are already audited in `research/voa-news-source-rights.md`,
`research/filtered-common-pile-source-rights.md` and
`research/cc-news-publisher-rights-audit-v2.md`. The sample covered every
passage in each pool (`normalized_passage`).

| Pool | Passages | Median words | Docs with a hit | Hits per 1k words |
|---|---|---|---|---|
| clean-core v5, all | 8,306 | 163 | 84 (1.0%) | 0.05 |
| — MOT-VOA | 6,514 | | 71 (1.1%) | 0.06 |
| — VOA staff | 399 | | 2 (0.5%) | 0.05 |
| — Common Pile news | 1,393 | | 11 (0.8%) | 0.03 |
| CC-NEWS filtered v8 (IOL) | 76 | 188 | 6 (7.9%) | 0.45 |

A random check of 15 clean-core hits found about 5 company-specific neutral
claims. Examples: Tesco's "trading profit ... in line with company guidance",
"National Iranian Gas Co. said ... its pipeline network had not been affected",
and a company "warns earnings are likely to remain flat". The rest are
market-level or macro statements, such as "Bond prices were steady", "the
region's economy was flat", and "Brazilian markets were stable". The clean core
probably holds only **~25–40 usable neutral company claims** across all splits,
and fewer in the training split alone.

CC-NEWS is denser because IOL business copy reads like results reports. Its
approval is `restricted-auxiliary` and manifest-only, so it cannot supply
training or development passages.

## Method

Neutral-claim regex, case-insensitive. It needs at least one of these patterns:

```
no material (adverse )?(effect|impact)
(not|n't) [been|be] [expected|anticipated to] (have|had|has) [a|any] material [adverse] (effect|impact)
(not [been] [materially] |un)(affected|impacted|disrupted)
in line with (\w+ ){0,2}(expectations|estimates|guidance|forecast(s)|consensus|outlook)
(reaffirm|reiterat|maintain|confirm)\w* [its|our|the] ([\w-]+ ){0,3}(guidance|outlook|forecast)
(remain(s|ed)|was|were|is|are|held|kept) [essentially|broadly|largely|relatively] (unchanged|stable|flat|steady)
business as usual | operat\w+ [continue(s|d)] [as] normal(ly)
```

This regex measures recall, not label quality. It counts market-level
"steady/flat" statements, and it misses paraphrases. Treat the numbers as an
upper bound on how often each source states a neutral claim, with a precision
of about one third.

## Implication for v2

For an exploratory neutral gold and silver set, the honest options are:

1. Mine the ~1% of clean-core passages that hit the regex, then hand-filter
   them for company-specific claims. Expect tens of examples, not hundreds.
2. If more volume is essential, EX-99 text is the obvious place, at about 1 in
   3 earnings releases. It would need a deliberate decision to admit a
   quarantined, issuer-copyrighted lane under fair use. The current
   open-rights rule forbids that. This audit does not recommend it without
   that rule change.
