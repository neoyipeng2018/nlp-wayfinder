import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from claim_company_matcher import ClaimCompanyMatcher  # noqa: E402

MATCHER = ClaimCompanyMatcher()


def names(sentence: str) -> list[str]:
    return [hit["name"] for hit in MATCHER.find(sentence)]


def test_company_evidence_admits_a_named_company() -> None:
    assert names("Drugmaker Pfizer said sales rose.") == ["Pfizer"]
    assert names("Apple Inc. announced a new factory.") == ["Apple Inc"]
    assert names("Tesla's factory in Shanghai resumed production.") == ["Tesla"]
    assert names("Shares of Alibaba fell 5 percent.") == ["Alibaba"]
    assert names("Boeing shares rose after the deal.") == ["Boeing"]
    assert names("Huawei, the Chinese telecom giant, was banned.") == ["Huawei"]


def test_the_widened_rule_admits_an_unlisted_company() -> None:
    assert names("Privately held Koch Industries invested in the plant.") == [
        "Koch Industries"
    ]
    assert names("Belarusian national carrier Belavia cut its fleet costs.") == [
        "Belavia"
    ]


def test_a_mention_without_a_financial_claim_is_not_a_target() -> None:
    assert names("Pfizer was founded in Brooklyn.") == []


def test_a_non_company_proper_noun_is_refused() -> None:
    assert names("President Biden said the economy grew.") == []
    assert names("The Ministry of Finance said revenue rose.") == []
    assert names("The Supreme Court ruled on the antitrust lawsuit.") == []
    assert names("The Federal Reserve raised interest rates.") == []
    assert names("Bank of England raised rates as profits fell.") == []
    assert names("China's Export-Import Bank gave the loan.") == []
    assert names("Ukraine said it would buy more gas.") == []


def test_a_person_and_a_nonprofit_are_refused() -> None:
    assert names(
        "Costs rose, according to Wendy White, a supply chain expert."
    ) == []
    assert names(
        "The auction went on despite a lawsuit by the activist group Earthjustice."
    ) == []
    assert names(
        "Itai Rusike, head of the nonprofit Community Working Group, said costs rose."
    ) == []


def test_a_tail_does_not_escape_a_whole_span_guard() -> None:
    # "States" from "United States" and "Kong" from "Hong Kong".
    assert names("United States imports fell by 5 percent.") == []
    assert names("Hong Kong's chief executive approved the deal.") == []


def test_one_span_gives_one_company() -> None:
    assert names("Greece's Division of Internal Affairs cut its payroll.") == []
    assert names(
        "Investors sold bonds of Country Garden Holdings and Vanke Inc."
    ) == ["Country Garden Holdings", "Vanke Inc"]


def test_a_name_keeps_no_sentence_stop() -> None:
    assert names("Officials signed a fuel contract at the National Oil Company.") == [
        "National Oil Company"
    ]
