# Rights evidence for a filtered Common Pile News source

**Retrieval date:** 2026-09-16

**Pinned dataset revision:** `13e76bdc8d49ed14d710fac7e3b61186cf74c8d3`

**Scope:** First-party rights evidence for article text in the 17 source files in the pinned Common Pile News archive. This memo does not give legal advice.

## Result

Use an initial allowlist of eight source names:

- `news-360info`
- `news-altnews`
- `news-balkandiskurs`
- `news-factly`
- `news-freedom`
- `news-globalvoices`
- `news-oxpeckers`
- `news-thepublicrecord`

Each source has a current, first-party statement that covers article or site text and gives an exact Creative Commons license version. Site-level evidence is only the first filter. Each article must still have an author and a source URL. The build must remove or reject third-party material and any article that has a conflicting notice.

Do not admit the other nine source names at this time. Their current first-party evidence does not give an exact license version, does not clearly cover article text, is source-specific, or conflicts with the Common Pile license field.

## Archive inventory and limits

The [pinned data tree](https://huggingface.co/datasets/common-pile/news/tree/13e76bdc8d49ed14d710fac7e3b61186cf74c8d3/v0/documents) has 17 source files. The active source files are 360info, Alt News, Balkan Diskurs, EduCeleb, Factly, Freedom of the Press Foundation, Global Voices, Liberty TV/Radio, Mekong Eye, Milwaukee Neighborhood News Service, Minority Africa, New Canadian Media, Oxpeckers, Propastop, The Solutions Journalism Exchange, The Public Record, and ZimFact.

The prose list in the [pinned dataset card](https://huggingface.co/datasets/common-pile/news/blob/13e76bdc8d49ed14d710fac7e3b61186cf74c8d3/README.md) is not an exact file inventory. It includes sources that have no file in this revision. It also omits EduCeleb and Liberty TV/Radio, which have files.

The Common Pile license field is not publisher evidence. The release code gives one `--license` value to a complete source and writes that value to every record. It does not read a license notice from each article. See the official [`parse_pages.py`](https://github.com/r-three/common-pile/blob/9457f04a14cb2355ab00023420369d46ffd4a395/sources/news/parse_pages.py#L36) and [`parse-pages.sh`](https://github.com/r-three/common-pile/blob/9457f04a14cb2355ab00023420369d46ffd4a395/sources/news/parse-pages.sh#L6). The dataset card also warns that license laundering and inaccurate metadata can assign an incorrect license to a document.

## Sources with sufficient site-level evidence

| Common Pile source | Exact license | What the first-party statement covers | Attribution and exclusion rules | Stable evidence URL |
| --- | --- | --- | --- | --- |
| `news-360info` | CC BY 4.0 | Content created and distributed by 360info, including features and articles | Give the author, title, source link, license link, and change notice. Exclude the logo and third-party copyright. Check each image, graphic, and video separately. | [How to use our content](https://360info.org/how-to-use-our-content/) |
| `news-altnews` | CC BY 3.0 Unported | All Alt News website content, unless the page states another rule | Use the CC BY 3.0 attribution terms. Exclude content from Facebook, Twitter, and other external platforms. Also exclude any item with another notice. | [About Alt News](https://www.altnews.in/about/) |
| `news-balkandiskurs` | CC BY 3.0 | Content created by Balkan Diskurs, including its stories | Credit and link to Balkan Diskurs and the author. Photos, video, and audio have the same terms only when the item does not state another rule. | [Republication Guidelines](https://balkandiskurs.com/en/republishing-guidelines/) |
| `news-factly` | CC BY 4.0 | Site content other than video | Use the CC BY 4.0 attribution terms. Exclude video and any page item with a different notice. | [Factly home page](https://factly.in/) |
| `news-freedom` | CC BY 4.0 | Freedom of the Press Foundation site content, unless the page states another rule | Use the CC BY 4.0 attribution terms. Reject any article or part with another notice. Do not treat media credits as covered by the site statement. | [Freedom of the Press Foundation: About Us](https://freedom.press/about/) |
| `news-globalvoices` | CC BY 3.0 | Content created by Global Voices, unless the page states another rule | Put the author name and a link to the original story at the top. Also retain the license link and change notice. Exclude photos, video, and audio from other creators unless direct permission exists. | [Republishing Guidelines](https://globalvoices.org/about/global-voices-attribution-policy/) |
| `news-oxpeckers` | CC BY-SA 4.0 | Site content made by the Oxpeckers Center for Investigative Environmental Journalism | Use the CC BY-SA 4.0 attribution and ShareAlike terms. Exclude material not made by Oxpeckers, including credited third-party items. | [Oxpeckers: Contribute](https://oxpeckers.org/contribute/) |
| `news-thepublicrecord` | CC BY-SA 4.0 | The Public Record's own work and original content | Credit the author and The Public Record, and link to the source page. Apply ShareAlike to adaptations. Work from other sites keeps the other site's terms. | [Use Our Content: Our Licensing](https://thepublicrecord.ca/use-our-content-our-licensing/) |

These statements clearly cover publisher-created article text. They do not prove that each word in an article belongs to the publisher. Quotes, embeds, wire copy, partner copy, documents, captions, and other credited material can have other rights.

## Sources that are not ready

| Common Pile source | Stop reason |
| --- | --- |
| `news-educeleb` | No current first-party page was found that gives an exact license version and clearly covers EduCeleb article text. |
| `news-libertytvradio` | No current first-party page was found that gives an exact license version and clearly covers Liberty TV/Radio article text. |
| `news-mekongeye` | The official contributor guide says that written stories use a Creative Commons license, but it does not name a license type or version. It also says that photograph and video rights depend on each agreement. See [Information and guidance for contributors](https://www.mekongeye.com/wp-content/uploads/2024/01/2024_Information_and_guidance_MekongEye.pdf). |
| `news-milwaukeenns` | Current articles state CC BY-ND 4.0, not CC BY 4.0. The current republication rules prohibit editing and database extraction. The Common Pile repository also warns that this source contains many links from other sites. Do not use this source without a separate historical, article-level audit. See an [official article with the current republication rules](https://milwaukeenns.org/2026/09/02/new-flock-restrictions-will-apply-to-other-license-plate-reader-systems-mpd-says/) and the official [Common Pile source README](https://github.com/r-three/common-pile/blob/9457f04a14cb2355ab00023420369d46ffd4a395/sources/news/README.md#L45). |
| `news-minorityafrica` | The official About page says that stories use a Creative Commons license, but it does not give the license type or version. See [About Minority Africa](https://minorityafrica.org/about/). |
| `news-newcanadianmedia` | The official archive says that all stories can be used under a Creative Commons license, but it does not give the license type or version. See the [New Canadian Media archive](https://www.newcanadianmedia.ca/). |
| `news-propastop` | No current first-party page was found that gives an exact license version and clearly covers Propastop article text. |
| `news-solutionsjournalism` | The exchange says its stories can be republished under a Creative Commons license, but the stories come from other newsrooms and have story-specific rules. The general page does not give one exact license version that covers all article text. See [The Solutions Journalism Exchange](https://sojoexchange.solutionsjournalism.org/). |
| `news-zimfact` | No current first-party page was found that gives an exact license version and clearly covers ZimFact article text. |

Absence from the allowlist is not a statement that a source is closed. It means that the evidence found for this build is not precise enough.

## License-version corrections

Do not copy the Common Pile license version into the filtered-source manifest without a source check.

- Alt News states CC BY 3.0 Unported, while Common Pile records state CC BY 4.0.
- Balkan Diskurs states CC BY 3.0, while Common Pile records state CC BY 4.0.
- Global Voices states CC BY 3.0, while Common Pile records state CC BY 4.0.
- Milwaukee Neighborhood News Service currently states CC BY-ND 4.0, while Common Pile records state CC BY 4.0.

For each admitted article, record the exact version from the publisher evidence. Do not silently upgrade a 3.0 license to 4.0.

## Required build controls

Apply all controls below before a passage enters the candidate pool.

1. Require an allowlisted `source` value and an exact allowlisted article host. Redirects must stay on that host.
2. Require the original article URL, title, author, and non-empty article text.
3. Check the article for a specific license or copyright notice. A specific notice overrides the site-level rule. Reject a conflict.
4. Keep only publisher-created article text. Remove navigation, related-story text, comments, social embeds, scripts, image captions, photo credits, video transcripts, document text, partner copy, and wire copy.
5. Remove block quotes and other clearly marked external quotations. Reject the article when third-party text cannot be separated with high confidence.
6. For a site that says “except where otherwise noted,” reject an article if a different notice applies to the article or to text inside it.
7. Store the exact license identifier and URL. Use `CC-BY-3.0`, `CC-BY-4.0`, or `CC-BY-SA-4.0`; do not use only `CC-BY` or `CC-BY-SA`.
8. Store the publisher evidence URL, retrieval time, normalized evidence excerpt, and SHA-256 hash. Store an article-page evidence URL and hash when the article gives a specific notice.
9. Build an attribution record for each passage. It must include the author, title, publisher, original article URL, license name and URL, and a change notice.
10. Keep CC BY-SA passages in a separate license group. Apply the ShareAlike rule to adapted material and to any release that the rights review identifies as an adaptation.
11. Reject a passage when its Common Pile source name, host, author, publisher evidence, article notice, or attribution data do not agree.
12. Keep the pinned Common Pile record hash and the filtered-text hash. This makes each removal and change auditable.

## Minimum evidence record

Use at least these fields for each admitted passage:

```json
{
  "source_id": "common-pile-news-rights-filtered-v1",
  "common_pile_source": "news-globalvoices",
  "common_pile_revision": "13e76bdc8d49ed14d710fac7e3b61186cf74c8d3",
  "article_url": "https://globalvoices.org/...",
  "title": "...",
  "author": "...",
  "publisher": "Global Voices",
  "license_id": "CC-BY-3.0",
  "license_url": "https://creativecommons.org/licenses/by/3.0/",
  "publisher_evidence_url": "https://globalvoices.org/about/global-voices-attribution-policy/",
  "publisher_evidence_retrieved_at": "2026-09-16T00:00:00Z",
  "publisher_evidence_sha256": "...",
  "article_evidence_sha256": "...",
  "raw_record_sha256": "...",
  "filtered_text_sha256": "...",
  "removed_third_party_parts": ["..."],
  "attribution_text": "...",
  "review_status": "pass"
}
```

## License conditions to carry forward

- [CC BY 3.0 legal code](https://creativecommons.org/licenses/by/3.0/legalcode.en), section 4(b), requires reasonable credit, the title when supplied, the license URI, and the author or other named attribution parties. An adaptation must also identify the use of the original work.
- [CC BY 4.0 legal code](https://creativecommons.org/licenses/by/4.0/legalcode.en), section 3(a), requires creator and attribution information, copyright and license notices when supplied, a license link, and an indication of changes.
- [CC BY-SA 4.0 legal code](https://creativecommons.org/licenses/by-sa/4.0/legalcode.en), sections 3(a) and 3(b), adds a compatible ShareAlike license for adapted material.
- All three licenses cover only rights held by the licensor. They do not make third-party text part of the licensed article.

## Evidence-response hashes

The following hashes record the raw HTTP response bodies retrieved on 2026-09-16. Dynamic site code can change these hashes. The build must create its own saved, normalized evidence excerpt and hash.

| Source | SHA-256 |
| --- | --- |
| 360info | `fa5e38fa9fc4567b987516aa79d2774ef552619fdf866454bab9291c6494d2a7` |
| Alt News | `1c32bf455e84ea0f2cf17b2e0329074ce725521309664b645a33a1f1902c3097` |
| Balkan Diskurs | `b298b10c1a547012f3b10b5ee32daafc49d775aa0d50ff333dec813f598fed31` |
| Factly | `11793490a082f68cdad694cee6da84a7ab45d12086049a1d4c946c98451aaf80` |
| Freedom of the Press Foundation | `48ada1433737d50fb55c90484b3655bb4fd92647e0fba1a20f819259dbe016ac` |
| Global Voices | `883e1245f6315cddb088936360d5f368802c4455ef6aefe827d94ee3424fc0ab` |
| Oxpeckers | `f19675b1e100a6a12326e52d3bcfd7c6242845610b964ed077d1e90882d1182b` |
| The Public Record | `3be8b5009914705e26f17afc3251fa141a3a679e91b594314e997394af2a10cd` |

## Recommended first build

Start with the eight-source allowlist. Keep only prose that the publisher created. Use the exact 3.0 or 4.0 license shown above. Keep CC BY-SA material separate. Report yield by source after the rights and third-party-content filters run.

If the eight-source yield is too small, open a new rights-research ticket for one blocked source at a time. Do not weaken the evidence rule inside this build.
