import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_filtered_voa_news import (  # noqa: E402
    CompanyMatcher,
    article_stop_reason,
    match_name,
    parse_page,
    select_passage,
    split_sentences,
)

SNAPSHOT = {
    "fields": ["cik", "name", "ticker", "exchange"],
    "data": [
        [78003, "PFIZER INC", "PFE", "NYSE"],
        [320193, "Apple Inc.", "AAPL", "Nasdaq"],
        [1, "JOINT Corp", "JYNT", "Nasdaq"],
        [2, "Tiny OTC Co", "TINY", "OTC"],
    ],
}
BODY = (
    "WASHINGTON - U.S. drugmaker Pfizer said Friday its pill cut hospital stays by most "
    "of the measured amount in a large study of adult patients. The company plans to ask "
    "regulators for approval within the next several weeks, officials said on Nov. 5 "
    "at a briefing. Pfizer shares rose after the news was released to investors in "
    "the morning trading session. Analysts expect other drugmakers to follow soon."
)


def page(byline: str, body: str = BODY) -> dict:
    html = (
        '<h1 class="title pg-title">Pill news</h1><div class="publishing-details ">'
        f'<a class="links__item-link" href="/author/x/1">{byline}</a>'
        '<time pubdate="pubdate" datetime="2022-03-04T10:00:00-04:00"></time></div>'
        f'<div id="article-content"><div class="wsw"><p>{body}</p></div></div>'
    )
    return {
        "final_url": "https://www.voanews.com/a/pill/6400000.html",
        "html": html,
        "status": 200,
    }


def test_staff_page_parses_and_passes() -> None:
    raw = page("Jane Reporter")
    parsed = parse_page(raw["html"])
    assert parsed["authors"] == ["Jane Reporter"]
    assert parsed["published"] == date(2022, 3, 4)
    assert article_stop_reason(raw, parsed) is None


def test_wire_byline_and_credit_are_rejected() -> None:
    raw = page("Reuters")
    assert article_stop_reason(raw, parse_page(raw["html"])) == "byline-names-wire-agency"
    raw = page("VOA News", BODY + " Some information came from The Associated Press.")
    assert article_stop_reason(raw, parse_page(raw["html"])) == "sentence-credits-wire-agency"


def test_splitter_keeps_abbreviations() -> None:
    assert split_sentences("The U.S. firm met Mr. Lee on Nov. 5 in D.C. today. Next.") == [
        "The U.S. firm met Mr. Lee on Nov. 5 in D.C. today.",
        "Next.",
    ]


def test_matcher_rules() -> None:
    assert match_name("PFIZER INC") == "PFIZER"
    matcher = CompanyMatcher(SNAPSHOT, ["NYSE", "Nasdaq"], 3)
    assert [h["name"] for h in matcher.find("Drugmaker Pfizer said sales rose.")] == ["PFIZER"]
    assert matcher.find("Pfizer said it would wait.") == []  # no company cue
    assert matcher.find("The pro-democracy paper Apple Daily lost executives.") == []
    assert matcher.find("The Joint Chiefs chairman spoke.") == []
    assert matcher.find("The OTC firm Tiny OTC Co grew.") == []  # exchange not pinned


def test_passage_needs_listed_company() -> None:
    matcher = CompanyMatcher(SNAPSHOT, ["NYSE", "Nasdaq"], 3)
    passage, companies, _ = select_passage(parse_page(page("A")["html"])["blocks"], matcher)
    assert passage and [c["cik"] for c in companies] == ["78003"]
    no_company = BODY.replace("Pfizer", "the lab")
    passage, _, _ = select_passage(parse_page(page("A", no_company)["html"])["blocks"], matcher)
    assert passage is None
