# Hugging Face datasets for the staged source plan

Date checked: 2026-09-05

## Decision

Hugging Face does not remove the complete data gate.

- Use `sfd-anonymous/sfd-v1` for the regulatory-filing source in the non-commercial research lane.
- Test a two-dataset earnings-call route. Use Earnings-22 for training and development. Use Earnings25 for the blind set. This route needs a small passage and date audit before approval.
- Test Common Pile News as the first financial-news candidate. Do not approve it until a sample proves the required company-specific yield and date split.
- Do not use the current Hugging Face company-announcement candidates.
- Do not use full-text X or Twitter datasets for the financial-social-media source.

Thus, regulatory filings pass now. Earnings calls and financial news are conditional. Company announcements and financial social media still fail.

This is a source-rights and metadata review. It is not legal advice. No model call, account creation, dataset download, or external spend occurred.

## Test used for this review

The frozen size for each later source is 2,000 accepted training examples, 200 development examples, and 400 blind examples. Financial news needs 4,000 training examples, 200 development examples, and 400 blind examples. The plan also needs separate time periods and separate event groups.

A candidate passes only when all these facts are clear:

1. The source and the license can be traced to the owner.
2. The license permits the planned evaluation, training, and text release.
3. The data has English text, a company identifier, a date, and an event identifier or enough data to make one.
4. The available data can meet the frozen size and split rules.

A Hugging Face license tag alone does not pass this test. A repository owner cannot grant rights that the owner does not have.

## Result by source

| Source | Best candidate | Rights result | Data and size result | Verdict |
| --- | --- | --- | --- | --- |
| Regulatory filings | SFD-v1 | CC BY-NC 4.0 permits non-commercial sharing and adaptation with attribution. SEC site information can also be copied and distributed. | About 3.8 million filings from 2022 to June 2025. Each row has an accession number, year, month, parsed text, and SEC header data such as CIK. | **Pass for the research lane.** |
| Financial news | Common Pile News | Each row has source license data. The listed sources use CC BY or CC BY-SA. | 172,308 English news documents. It has text, source, created date, URL, author, and license. It has no company field. It is general news. | **Conditional.** A sample must prove at least 4,600 acceptable company passages and the time split. |
| Company announcements | IDX Stock Announcements | The card says that IDX terms control use. The official terms page did not permit an independent check during this review. The card limits use to educational, academic, and non-commercial work. | The repository is 293 GB and has 100,000 to 1 million mixed Indonesian and English records. It has date, ticker, title, and PDF attachments. The card does not give an English count. | **Fail now.** Rights and English quota are not proved. |
| Earnings calls | Earnings-22 plus Earnings25 | Earnings-22 transcripts use CC BY-SA 4.0. Earnings25 transcripts and metadata use CC BY 4.0. Earnings25 is evaluation-only. | Earnings-22 has 125 calls and 57,391 text chunks. It has a ticker, but its Hugging Face schema has no call date. Earnings25 has 514 full calls from 2025 Q4 with company and release date. | **Conditional.** Use Earnings25 only for blind evaluation. First recover and verify each Earnings-22 call date. Then test passage yield and company coverage. |
| Financial social media | Twitter Financial News Sentiment | The Hugging Face card says MIT, but X rules limit downloadable datasets to post or user IDs in the usual case. The dataset distributes full text. | 11,931 English rows. It has text and labels, but no date or post ID in the stated schema. | **Reject.** The repository license tag does not resolve the upstream X rules. |

## Approved regulatory-filing route

Pin [SFD-v1 revision `dff50e3`](https://huggingface.co/datasets/sfd-anonymous/sfd-v1/tree/dff50e379949e8a66a0a0a1fc453dc192bd0372f). The [dataset card](https://huggingface.co/datasets/sfd-anonymous/sfd-v1/blob/dff50e379949e8a66a0a0a1fc453dc192bd0372f/README.md) states these facts:

- It has about 3.8 million SEC filings from January 2022 through June 2025.
- The data has more than 350 filing types.
- Each row has `accession`, `year`, `month`, `parsed_md`, and `has_ocr`.
- The parsed corpus uses CC BY-NC 4.0.
- A small PDF part used Mistral OCR.

The [SEC website rule](https://www.sec.gov/about/privacy-information#website-dissemination) permits users to copy and distribute SEC site information without SEC permission. It also says not to use the SEC seal, logos, or artwork. The SEC access rule limits automated access to 10 requests each second and requires identified automated tools.

Use these controls:

- Keep this source in the non-commercial research lane.
- Keep the SFD attribution, license notice, source URL, accession number, and revision.
- Exclude every row where `has_ocr` is true. This removes the separate Mistral OCR term question.
- Exclude logos, artwork, and content that has a separate rights mark.
- Use the accession number as the document and event key. Use the embedded CIK as the company key.
- Use the Hugging Face files when possible. If direct SEC access is necessary, use an identified user agent and no more than 10 requests each second.

The row count is much larger than the required 2,600 examples. The date range permits separate time periods. Therefore, this source passes the size test before passage acceptance filters.

An 8-K exhibit can contain a press release. Do not count that item as a company announcement under the current source taxonomy. The earlier plan classifies it as a regulatory filing.

## Conditional financial-news route

Pin [Common Pile News revision `13e76bd`](https://huggingface.co/datasets/common-pile/news/tree/13e76bdc8d49ed14d710fac7e3b61186cf74c8d3). Its dataset card states that the dataset has 172,308 English documents from 20 news sources. Each row has full text, source, created date, and metadata. The metadata includes the article URL, author, and the source license. The source list uses CC BY or CC BY-SA material.

This is the best candidate because its license data stays with each document. It is not a finance dataset. It has no company field. The dates are not a sealed publication-date range. Therefore, the total row count does not prove the required 4,600 accepted company passages.

Before approval, inspect a deterministic sample. The sample must prove all these points:

- The article has a named company target.
- The source URL and exact license are still valid.
- The article has a usable publication date.
- The source permits the planned text release.
- At least 69% of no more than 6,668 candidates can supply the 4,600 training, development, and blind examples.
- The accepted items support separate time periods and event groups.

Two other candidates do not pass:

- [Wikinews revision `b4c2ec3`](https://huggingface.co/datasets/malteos/wikinews/tree/b4c2ec3857fcac203c40b8d61586e934ed07c128) has 65,919 English articles from 2004 through April 2024. Its card gives title, URL, and date. Text after 2005-09-25 uses CC BY 2.5. This is a clean rights path, but it is general news. There is no evidence that it can meet the company-finance quota.
- [Financial PhraseBank revision `8d3fe0c`](https://huggingface.co/datasets/takala/financial_phrasebank/tree/8d3fe0c36d5feec6b3cc5e455b0fcb4820fb9964) has about 4,840 English financial-news sentences under CC BY-NC-SA 3.0. It has sentence and label fields only. It has no date, article key, publisher, URL, or company identifier. It cannot support the required time and event split. Its total size also leaves almost no room for rejection.

Reject [Multi-Source Financial and General News revision `c25780f`](https://huggingface.co/datasets/Brianferrell787/financial-news-multisource/tree/c25780f336280adb57c64bda7aed605d065c672d) as one source. Its own card says that original content stays with the publishers and that full-text release can need permission. Its Wikinews subset can be reviewed as Wikinews, but the mixed dataset does not have one valid rights path.

## Conditional earnings-call route

Use two datasets with non-overlapping roles.

### Training and development candidate

Pin [Earnings-22 revision `0a034f9`](https://huggingface.co/datasets/distil-whisper/earnings22/tree/0a034f9ed86d33a3859d9025d3e621cf243773ab). The [Hugging Face card](https://huggingface.co/datasets/distil-whisper/earnings22/blob/0a034f9ed86d33a3859d9025d3e621cf243773ab/README.md) has 125 English calls, about 119 hours, and 57,391 chunks. It gives full transcripts, ticker symbols, and file identifiers. The [source license](https://github.com/revdotcom/speech-datasets/blob/main/earnings22/LICENSE.md) puts the transcripts and related text files under CC BY-SA 4.0.

The text count can cover 2,000 training examples and 200 development examples. Split by call before passage extraction. Keep attribution and use ShareAlike for released adapted text.

The card does not give a call-date field. Do not approve this route until a source record gives a verified date for every selected call. Also inspect a fixed sample to prove that the passage acceptance rate can meet the 3,333-candidate limit.

### Blind candidate

Pin [Earnings25 revision `b4864bf`](https://huggingface.co/datasets/florencejiang/earnings25/tree/b4864bf8f0cd1e3b153e502d45bb29cd46993f21). Its card has 514 full calls from 2025 Q4. It gives transcript text, company, release date, speakers, and segments. The transcript, annotation, and metadata license is CC BY 4.0. The card says to use both configurations only for evaluation.

Use it only for the blind set. At two examples for each event group, 200 distinct calls can supply the required 400 blind examples. This count is possible within 514 calls. Do not train on this data. Keep attribution and keep all passages from one call in one split.

The complete earnings route stays conditional until the Earnings-22 date and yield checks pass.

Do not use these alternatives:

- [Lamini Earnings Calls QA revision `2d084a5`](https://huggingface.co/datasets/lamini/earnings-calls-qa/tree/2d084a557bb28250baada291b4fd298e80785d77) says CC BY 4.0 and has 860,164 rows. Its card and source pipeline do not identify the owner or origin of each transcript. The rights chain stops at the uploaded transcript file.
- [`jlh-ibm/earnings_call` revision `0f4669f`](https://huggingface.co/datasets/jlh-ibm/earnings_call/tree/0f4669f29e8cb784a3da60005a8d82f12dad102f) says CC0, but the [original deposit](https://doi.org/10.34894/TJE0D0) says that Thomson Reuters Eikon supplied the transcripts. The deposit does not show that CC0 rights came from Thomson Reuters. Do not treat the CC0 label as proof of upstream rights.
- Earnings25 cannot supply training data because its card reserves the data for evaluation.

## Rejected company-announcement route

Pin the reviewed record only for audit: [IDX Stock Announcements revision `7c8e23b`](https://huggingface.co/datasets/IRedDragonICY/idx-stock/tree/7c8e23b9713054444533f95809032abd294ba5c0).

The card gives an announcement number, publication date, ticker, title, and PDF attachment. It states that the data has Indonesian and English text. It reports 100,000 to 1 million records and 293 GB of files. It does not give the English record count.

The card says that the [IDX terms](https://www.idx.co.id/id/syarat-penggunaan/) control use and that commercial use needs written consent. The official terms page returned an access block during this review. Thus, this review could not confirm training rights or text-release rights from the owner. The unknown English share also prevents a quota decision.

Do not use this dataset now. A later check can reconsider it only when the official terms are saved and translated, and a metadata count proves the English quota.

## Rejected financial-social-media route

Pin the reviewed record only for audit: [Twitter Financial News Sentiment revision `ccbe24d`](https://huggingface.co/datasets/zeroshot/twitter-financial-news-sentiment/tree/ccbe24de388e287beb92dd393a335c376b350ac3).

The card has 11,931 English full-text posts and sentiment labels. It says that the dataset used the Twitter API and that the repository uses the MIT license. Its stated schema has no date and no post ID.

The current [X Developer Policy](https://docs.x.com/developer-terms/policy#content-redistribution) restricts third-party downloadable datasets. In the usual case, a developer can distribute post IDs, direct-message IDs, and user IDs, not full post text. The policy also requires current-content controls for display. The Hugging Face MIT tag does not remove these upstream limits or the post authors' rights.

Reject this dataset for full-text training and release. Reject the similar [Stock Market Tweets Data revision `2931736`](https://huggingface.co/datasets/StephanAkkerman/stock-market-tweets-data/tree/2931736711c6765dea084ed3950d374692395b69) full-text mirror for the same reason. A future social source needs one of these paths:

- direct permission from the post authors and the platform;
- a first-party dataset with a license that covers the post text and the planned use;
- an ID-only source with approved access, deletion controls, and a release plan that does not distribute full text.

No reviewed Hugging Face dataset has this path now.

## Preflight records to keep

For each approved dataset, record these items before collection:

- Hugging Face dataset name and full revision hash;
- upstream source owner and source URL;
- license URL and a dated copy of the terms;
- permitted evaluation, training, and release uses;
- required attribution and ShareAlike terms;
- access method and file list;
- fields used for text, company, date, and event group;
- row count before and after language and rights filters;
- accepted-yield sample and quota result.

The data rule can now be less broad than the earlier rule. Do not require every possible source to pass before any data work starts. Approve and collect one source stage only after that source passes its own preflight. Do not start a later source stage until its own rights, metadata, and quota checks pass.
