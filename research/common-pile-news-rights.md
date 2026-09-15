# Evidence memo: Common Pile News rights and access

**Retrieval date:** 2026-09-15  
**Scope:** Evidence for [Audit Common Pile News rights and access](https://github.com/neoyipeng2018/nlp-wayfinder/issues/47). This memo audits passage text. It uses only primary sources. It does not give legal advice.

## Decision

Do not approve the complete `common-pile/news` collection as a Stage 1 clean-core source.

The public download route permits access. A valid CC BY or CC BY-SA license permits private evaluation, training, weight release, and text redistribution. You must meet the license conditions. However, the Common Pile license field is not passage-level license evidence. The build code assigns one license to a complete site. It does not read a license notice from each article. The dataset authors also warn that some document licenses can be incorrect.

Use a new, filtered Common Pile News source only if each selected passage has current primary evidence. The evidence must identify the article, author, license version, and license URL. It must also record an exception for third-party content. Remove a passage when this evidence is absent or conflicts with the dataset metadata.

## Planned access method

Download the raw dataset from the public Hugging Face repository at pinned revision [`13e76bdc8d49ed14d710fac7e3b61186cf74c8d3`](https://huggingface.co/datasets/common-pile/news/tree/13e76bdc8d49ed14d710fac7e3b61186cf74c8d3). Use HTTPS or the Hugging Face dataset client. Pin each file hash in the candidate annex. Do not scrape the original news sites for passage text.

Hugging Face describes its public Hub as a service that is “accessible by all Users.” Its terms also state that content use remains subject to the terms that accompany the content. See [Hugging Face Terms of Service, Your Use of the Services and Content](https://huggingface.co/terms-of-service#3-your-use-of-the-services).

**Access result:** Permitted for the pinned public files. This access result does not prove rights in each passage.

## Collection audit

The pinned repository contains 17 compressed data files. A complete scan found 172,308 records:

| Metadata value | Records |
| --- | ---: |
| CC BY 4.0 | 153,299 |
| CC BY-SA 4.0 | 19,009 |

Every record has a non-empty `metadata.license` value and URL. See the pinned [dataset card](https://huggingface.co/datasets/common-pile/news/blob/13e76bdc8d49ed14d710fac7e3b61186cf74c8d3/README.md) and [data files](https://huggingface.co/datasets/common-pile/news/tree/13e76bdc8d49ed14d710fac7e3b61186cf74c8d3/v0/documents).

These fields are not sufficient evidence for passage-text rights:

- The parser receives `--license` as one command-line value for each site. It writes that value to every record. It does not extract a license notice from the article. See [`parse_pages.py`, lines 36 and 78-91](https://github.com/r-three/common-pile/blob/9457f04a14cb2355ab00023420369d46ffd4a395/sources/news/parse_pages.py#L36) and [`parse-pages.sh`, lines 6-30](https://github.com/r-three/common-pile/blob/9457f04a14cb2355ab00023420369d46ffd4a395/sources/news/parse-pages.sh#L6).
- The dataset card says that “license laundering and inaccurate metadata” can cause an incorrect license for a document. See [License Issues](https://huggingface.co/datasets/common-pile/news/blob/13e76bdc8d49ed14d710fac7e3b61186cf74c8d3/README.md#license-issues).
- The source README says that Milwaukee has many links that are not from the same site. See [`sources/news/README.md`, line 45](https://github.com/r-three/common-pile/blob/9457f04a14cb2355ab00023420369d46ffd4a395/sources/news/README.md#L45).
- A scan found 1,650 of 26,867 `news-milwaukeenns` records with another host or an invalid URL. These hosts include commercial news sites. This result confirms the repository warning. It does not prove the license of those passages.
- Current source terms also conflict with the recorded license version. All 4,172 Alt News records and all 102,552 Global Voices records state CC BY 4.0. Alt News currently states “Content licensed under CC BY 3.0.” Global Voices currently states that its site uses Creative Commons Attribution 3.0. See the [Alt News source page](https://www.altnews.in/about-us/) and the [Global Voices source page](https://globalvoices.org/about/).

The version conflict does not make the text closed. CC BY 3.0 also gives broad rights. However, it shows that the Common Pile field is not an exact current clause for the passage.

## Rights audit

The table separates the valid CC terms from the evidence for the complete collection.

| Required right | Valid CC BY or CC BY-SA passage | Complete Common Pile News collection | Exact primary clause or condition |
| --- | --- | --- | --- |
| Access | Yes | Yes, for the pinned public files | Hugging Face public Hub is “accessible by all Users.” |
| Private evaluation | Yes | Not proven for every passage | CC BY 4.0 section 2(a)(1) grants the right to “reproduce and Share the Licensed Material, in whole or in part.” Private use does not Share the material. |
| Training | Yes | Not proven for every passage | CC BY and CC BY-SA 4.0 section 2(a)(1) permits reproduction and Adapted Material. Creative Commons states that a developer who relies on a CC license for training must follow its requirements. |
| Weight release | Yes, with conditions | Not proven for every passage | Creative Commons states that public models based on ShareAlike content must use the same CC license under its conservative compliance method. Test memorization before release. |
| Text redistribution | Yes, with conditions | Not proven for every passage | CC BY and CC BY-SA 4.0 section 2(a)(1) permits reproduction and sharing. Section 3 requires attribution. CC BY-SA section 3(b) also requires a compatible ShareAlike license for Adapted Material. |

Primary license sources:

- [CC BY 4.0 legal code](https://creativecommons.org/licenses/by/4.0/legalcode.en), sections 2(a), 3(a), and 4.
- [CC BY-SA 4.0 legal code](https://creativecommons.org/licenses/by-sa/4.0/legalcode.en), sections 2(a), 3(a), 3(b), and 4.
- [CC BY 3.0 legal code](https://creativecommons.org/licenses/by/3.0/legalcode.en), sections 3 and 4.
- [Creative Commons AI training guidance](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/).

The licenses cover only rights that the licensor has authority to grant. They do not license privacy, publicity, patent, or trademark rights. CC BY and CC BY-SA 4.0 section 2(b) states these limits. Both licenses also give the material without a warranty of title or non-infringement in section 5.

## Manifest-ready result for the unfiltered collection

Use these values only for the unfiltered collection. They record the present decision. They do not authorize a build.

| Field | Value |
| --- | --- |
| `access_method` | HTTPS download of pinned `common-pile/news` revision `13e76bdc8d49ed14d710fac7e3b61186cf74c8d3` |
| `data_portfolio_lane` | Do not assign `clean-core` |
| `access_permitted` | `true` |
| `private_evaluation_permitted` | `false` because passage-level permission is not proven for all records |
| `training_permitted` | `false` because passage-level permission is not proven for all records |
| `weight_release_permitted` | `false` because passage-level permission and ShareAlike handling are not proven |
| `text_redistribution_permitted` | `false` because passage-level permission and attribution data are not proven |
| `audited_object` | `passage-text` |
| `retrieved_at` | `2026-09-15` |
| `reviewer` | `Yi Peng` |

For each false right, use this exact dataset clause as the stop evidence: “license laundering and inaccurate metadata can cause us to erroneously assign the incorrect license to some documents.”

## Conditions for a clean-core subset

A later ticket can define a filtered source. The source must apply these controls before the yield seal:

1. Keep the pinned Common Pile record and content hash.
2. Open the original article URL.
3. Record the article-level license notice or a site term that clearly covers that article.
4. Record the exact license version. Do not replace CC BY 3.0 with CC BY 4.0.
5. Record the author, title, article URL, license URL, retrieval time, and an archive or evidence hash.
6. Remove third-party text, quoted material, images, and other items that the license does not cover.
7. Remove an unavailable page unless an authoritative license record still identifies the passage.
8. For CC BY-SA passages, release applicable Adapted Material under a compatible license. Apply the conservative Creative Commons guidance to public model weights.
9. Publish an attribution file with redistributed text and any released model.
10. Run a memorization test before weight release. Do not release memorized passage text without the required attribution and ShareAlike terms.

If these controls pass for every selected passage, mark the filtered source as a separate source ID. Then Yi Peng can review it for the `clean-core` lane.
