# VOA staff-news source rights evidence

Source ID: `voa-news-staff-listed-company-v1`

## Clause

- URL: https://www.voanews.com/p/5338.html
- Retrieved: 2026-09-19
- Response SHA-256 of the stored copy: `b2b12710fd5facdb788813579ab467a4249bb2782be615bf19cec757bd63db29`
  (the page is dynamic, so each retrieval has a different hash)
- Exact clause: "All text, audio and video material produced exclusively by the Voice of America is in the public domain."
- License ID in the source: `public-domain-voa-produced`

Public domain meets the open-license rule (see **Open-rights passage text** in `CONTEXT.md`).

## Wire-copy exclusion

The same page says: "VOA has individual licenses from Agence France Presse (AFP), the Associated Press (AP) and Reuters to use their text, video, audio, photos and graphics on our website. All three agencies' material is copyrighted and the property of AFP, AP and Reuters respectively, and may not be copied, published or redistributed without the written permission of each agency."

Thus the build rejects an article when:

- a byline names Reuters, Associated Press, AP, AFP, or Agence France-Presse;
- any article text names one of these agencies (for example, "Some information for this report came from Reuters");
- the article text has a third-party copyright or license notice.

## Stated uncertainty

17 U.S.C. §105 covers works of federal employees. Many VOA journalists are contractors. This source relies on VOA's first-party statement about material "produced exclusively by the Voice of America". It does not have proof of the employment status of each author. Each candidate records this uncertainty.

## Freshness

The evidence must be no more than 90 days old at `starts_on`. Retrieval on 2026-09-19 is valid until 2026-12-18.
