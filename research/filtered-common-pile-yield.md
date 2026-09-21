# Filtered Common Pile News yield review

## Result

The filtered source does not pass the Stage 1 source-yield gate.

The review used the first 100 candidates in the fixed order. The sample has 85
training candidates, 4 development candidates, and 11 blind candidates. Five
candidates name a currently listed company that can be a company target. Four
are in the training split, none are in the development split, and one is in the
blind split.

The projected inspection count is 92,000. The frozen financial-news limit is
6,668. The projected development yield is zero. Thus, the source cannot fill
the frozen Stage 1 allocation.

## Fixed input

- Source ID: `common-pile-news-rights-filtered-v1`
- Candidate count: 43,486
- Candidate-list SHA-256: `a1822a549da659c163c5f2d4fecbba298f0bc8f5d87610ebbf22ef03550d88a8`
- Order salt: `20260905`
- Sample size: 100
- Sample rule: Take the first 100 candidates after the Stage 1 source-yield
  order function sorts the sealed pool.

The pool was sealed before the review. The seal is in the append-only local
decision log. The source build files have the hashes that are in
`research/filtered-common-pile-source-summary.json`.

## Review rule

Set `verified_company_target` to `true` only when the passage explicitly names
a company that has listed equity at the review date. A brand, product, private
company, public body, person, or former listed company does not pass this rule.

The five passing sample candidates are:

| Sample position | Candidate ID | Listed company | Listing evidence |
| ---: | --- | --- | --- |
| 27 | `9c351744fd85fbd96e07f97dfeb9e7d5389ece74dc10e88a21b8949a3331e484` | Walmart Inc. | Walmart reports the `WMT` common-stock listing in its SEC filing. |
| 33 | `113f89767438edf58a4ad3359cf480829b6e1c19eaf4044a1423644318410a42` | Mishra Dhatu Nigam Limited | NSE records `MIDHANI` as an equity company. |
| 76 | `612b1c5305086194167a46524d86f600801c7ddae4462d4989e961530f43c5af` | Morgan Stanley | Morgan Stanley reports its `MS` NYSE listing. |
| 84 | `1f76a3ebf5f2928d47c5594c3dca191a5d223ec040b65aed76f715e9571cd881` | BuzzFeed, Inc. | BuzzFeed reports that `BZFD` trades on Nasdaq. |
| 95 | `0ff03c0e99616f39f00e8b1e7e7a15bb812aeb44c0557831faf9e836c179670b` | Tesla, Inc. | Tesla reports that `TSLA` trades on Nasdaq. |

The review did not count Walgreens. Walgreens became a private company in
August 2025. It did not count Xstrata, Next Digital, or Yahoo because they are
not current listed issuers. It did not count Formosa Ha Tinh, Octarine Bio, or
Knet because the named entities are not listed issuers.

## Listing evidence

- [Walmart filing](https://stock.walmart.com/sec-filings/all-sec-filings/content/0000104169-25-000177/wmt-20251119.htm)
- [MIDHANI NSE filing](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_GOVERNANCE_189457_25082026094046_iXBRL_WEB.html)
- [Morgan Stanley investor relations](https://www.morganstanley.com/about-us-ir/)
- [BuzzFeed investor FAQ](https://investors.buzzfeed.com/ir-resources/investor-faqs)
- [Tesla investor FAQ](https://ir.tesla.com/node/16)
- [Walgreens private-company notice](https://corporate.walgreens.com/news-and-stories/press-releases/2025/walgreen-co-to-operate-as-private-standalone-company-followingacquisition-by-sycamore-partners/)

## Artifact

`manifests/stage-1.filtered-common-pile-yield-evidence.json` contains the
complete sealed pool and the 100 reviewed sample records. It is ready for a
Stage 1 draft manifest.
