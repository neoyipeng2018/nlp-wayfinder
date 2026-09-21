"""Open-vocabulary company-target matcher for the widened Stage 1 target rule.

The Stage 1 target is any named company that the bounded passage makes a
financial claim about, whether listed, formerly listed, foreign listed, or
privately held. A pinned exchange snapshot is not used. See decision 4 of
https://github.com/neoyipeng2018/nlp-wayfinder/issues/78.

A hit must pass two tests, because a mention alone is not a target:

1. **Company test.** The capitalized span must carry company evidence: an
   attached legal-form word, a company descriptor beside it, a possessive
   company role, or a share reference. A stoplist removes the proper nouns
   that are not companies, such as states, agencies, courts, and people.
2. **Claim test.** The same sentence must make a financial claim, and the
   span must be a party to it.

The matcher is deterministic and holds no model and no network call.
"""

from __future__ import annotations

import re
from typing import Iterable

# A name token starts with a capital letter or a digit. A span may hold a
# lower-case connector, as in "Bank of America" and "Procter & Gamble".
NAME_TOKEN = r"[A-Z0-9][\w.&'’-]*"
# "and" is not a connector: it merges two names, as in "X Holdings and Y Inc".
CONNECTOR = r"(?:of|de|del|van|von|der|la|le|du|&)"
NAME_SPAN = re.compile(
    rf"{NAME_TOKEN}(?:\s+(?:{CONNECTOR}\s+)?{NAME_TOKEN})*"
)

# A legal-form word attached to the span is the strongest company evidence.
LEGAL_FORM_WORDS = (
    r"inc|incorporated|corp|corporation|co|company|cos|"
    r"ltd|limited|plc|llc|llp|lp|nv|n\.v|bv|sa|s\.a|ag|se|asa|ab|oyj|oy|"
    r"gmbh|spa|s\.p\.a|sas|srl|pte|pvt"
)
LEGAL_FORM = re.compile(rf"^(?:,?\s+|\s*&\s*)?(?:{LEGAL_FORM_WORDS})\b\.?", re.IGNORECASE)
# A company-type word inside the span also names a company, as in
# "Koch Industries", "Lockheed Martin Corp", and "Deutsche Bank".
COMPANY_TYPE_WORD = re.compile(
    rf"^(?:{LEGAL_FORM_WORDS}|holdings?|group|groupe|technologies|systems|"
    r"industries|enterprises|ventures|partners|laboratories|pharmaceuticals|"
    r"motors|airlines|airways|bancorp|bank|telecom|energy|foods|brands|"
    r"stores|networks|studios|media|mobility|semiconductor|semiconductors)$",
    re.IGNORECASE,
)
# A central bank, policy bank, or development bank is an institution, not a
# company target.
STATE_BANK = re.compile(
    r"^(?:the\s+)?(?:central|reserve|national|people's|state|world)\s+bank\b"
    r"|^bank\s+of\b|^(?:federal\s+reserve|bundesbank)\b"
    r"|\b(?:export-?import|exim|development|policy|investment)\s+bank\b",
    re.IGNORECASE,
)
# A nonprofit, charity, or advocacy body is not a company target.
NONPROFIT_CUE = re.compile(
    r"\b(?:non-?profit|not-?for-?profit|charity|charitable|advocacy|activist|"
    r"campaign(?:ing)?|think tank|research|watchdog|rights|humanitarian|aid|"
    r"environmental|conservation|volunteer|community|civil society|ngo)\s+"
    r"(?:[a-z-]+\s+){0,2}(?:group|organi[sz]ation|body|network|coalition)?\s*$",
    re.IGNORECASE,
)
# A role after the span names a person, as in "Wendy White, a supply chain expert".
PERSON_ROLE_AFTER = re.compile(
    r"^\s*,\s+(?:a|an|the)\s+(?:[a-z-]+\s+){0,3}(?:expert|manager|analyst|"
    r"specialist|consultant|professor|researcher|economist|official|adviser|"
    r"advisor|lawyer|attorney|doctor|scientist|engineer|reporter|journalist|"
    r"editor|author|writer|activist|spokes(?:man|woman|person)|head|chief|"
    r"director|president|member|leader|student|worker|resident|father|mother)\b",
    re.IGNORECASE,
)

# A descriptor before the span, as in "chipmaker Nvidia" and "the retailer Gap".
COMPANY_DESCRIPTOR = (
    r"(?:compan(?:y|ies)|firm|corporation|conglomerate|subsidiary|affiliate|"
    r"start-?up|unit|maker|makers|manufacturer|producer|supplier|operator|"
    r"automaker|carmaker|drugmaker|chipmaker|planemaker|steelmaker|shipbuilder|"
    r"retailer|grocer|airline|carrier|lender|bank|insurer|broker|brokerage|"
    r"miner|refiner|driller|utility|telecom|broadcaster|studio|publisher|"
    r"developer|contractor|distributor|wholesaler|exporter|importer|"
    r"giant|group|brand|chain|owner|operator|venture|joint venture|"
    r"e-?commerce|tech|technology|software|internet|social media|search|"
    r"energy|oil|gas|mining|pharmaceutical|biotech|aerospace|defense|defence|"
    r"automotive|airline|banking|financial|investment|private equity|"
    r"hedge fund|asset manager|state-?(?:owned|run)|multinational)"
)
DESCRIPTOR_BEFORE = re.compile(
    rf"(?:^|[\s(\"'“])(?:the\s+|a\s+|an\s+)?(?:[a-z-]+\s+){{0,3}}{COMPANY_DESCRIPTOR}s?\s*$",
    re.IGNORECASE,
)
# An appositive after the span, as in "Nvidia, the chipmaker, said".
DESCRIPTOR_AFTER = re.compile(
    rf"^\s*,\s+(?:the|a|an)\s+(?:[a-z-]+\s+){{0,3}}{COMPANY_DESCRIPTOR}s?\b",
    re.IGNORECASE,
)
# A company role or asset held by the span, as in "Boeing's chief executive".
POSSESSIVE_ROLE = re.compile(
    r"^['’]s\s+(?:[a-z-]+\s+){0,2}(?:chief|ceo|cfo|coo|chairman|chairwoman|"
    r"president|founder|board|executives?|shares?|stock|shareholders?|investors?|"
    r"revenue|profits?|earnings|sales|results|guidance|forecast|outlook|"
    r"factory|factories|plant|plants|mill|refinery|warehouse|store|stores|"
    r"workers|employees|staff|workforce|payroll|"
    r"products?|business|operations|unit|division|customers?|market share|"
    r"valuation|market value|debt|loans?|bonds?|dividend|"
    r"headquarters|supply chain|output|production|orders?|backlog)\b",
    re.IGNORECASE,
)
# A share or stake reference around the span.
SHARE_REFERENCE = re.compile(
    r"^\s+(?:shares?|stock|shareholders?|share price|stock price)\b", re.IGNORECASE
)
SHARE_REFERENCE_BEFORE = re.compile(
    r"\b(?:shares?|stock|stake|shareholders?|bonds?)\s+(?:in|of)\s*$", re.IGNORECASE
)

# A financial claim in the sentence. The span must be a party to it.
FINANCIAL_CLAIM = re.compile(
    r"\b(?:revenue|revenues|profit|profits|profitable|loss|losses|earnings|"
    r"sales|turnover|income|margin|margins|dividend|dividends|"
    r"shares?|stock|stocks|shareholders?|share price|stock price|market value|"
    r"valuation|market cap|market capitalization|ipo|listing|delisted|"
    r"invest|invests|invested|investment|investments|investors?|funding|"
    r"raised|fundraising|stake|acquire|acquires|acquired|acquisition|"
    r"merger|merge|merged|takeover|buyout|bid|deal|deals|contract|contracts|"
    r"order|orders|backlog|customers?|sold|sell|sells|selling|bought|buy|buys|"
    r"price|prices|priced|pricing|cost|costs|fee|fees|"
    r"quarter|quarterly|fiscal|annual results|guidance|forecast|outlook|"
    r"factory|factories|plant|plants|production|output|capacity|supply|"
    r"shipments?|deliveries|delivered|exports?|imports?|"
    r"jobs|job cuts|layoffs?|laid off|hiring|hire|hires|workers|employees|"
    r"workforce|staff|wages|pay|payroll|strike|union|"
    r"bankrupt|bankruptcy|insolvency|debt|debts|loan|loans|bond|bonds|"
    r"credit|refinanc\w+|restructur\w+|write-?down|impairment|"
    r"fine|fined|penalty|settlement|settle|settled|lawsuit|sued|antitrust|"
    r"sanction|sanctions|sanctioned|ban|banned|tariff|tariffs|duty|duties|"
    r"regulator|regulators|regulatory|licen[cs]e|approval|approved|recall|"
    r"expand|expansion|opened|opening|closure|closing|shut|shutdown|"
    r"launch|launched|unveiled|introduc\w+|"
    r"chief executive|ceo|cfo|chairman|resigned|stepped down|appointed|"
    r"partnership|venture|agreement|agreed|"
    r"rose|rise|risen|fell|fall|fallen|jumped|surged|climbed|gained|"
    r"dropped|slid|slumped|plunged|tumbled|declined|decline|increase|increased|"
    r"cut|cuts|boost|boosted|grew|growth|shrank|"
    r"billion|million|trillion|percent|dollars?)\b",
    re.IGNORECASE,
)

# Proper nouns that are not companies. A span is rejected when it holds one of
# these words, unless a legal-form word is attached to the span.
NOT_A_COMPANY = re.compile(
    r"\b(?:ministry|ministries|department|agency|administration|commission|"
    r"bureau|council|committee|parliament|congress|senate|house|assembly|"
    r"court|tribunal|judiciary|police|army|navy|air force|military|affairs|"
    r"government|state|republic|kingdom|federation|union|nation|"
    r"university|college|school|institute|academy|foundation|charity|"
    r"church|mosque|temple|party|movement|front|alliance|coalition|"
    r"organization|organisation|association|federation|society|"
    r"federal reserve|central bank|treasury|imf|world bank|"
    r"united nations|nato|european union|white house|kremlin|pentagon|"
    r"embassy|consulate|prison|hospital|museum|"
    r"cent(?:er|re)|registry|observatory|initiative|campaign|watch|task force|"
    r"division|office|authority|board of|secretariat|mission|program|programme|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\b",
    re.IGNORECASE,
)
# A title before the span names a person, not a company.
PERSON_TITLE_WORDS = (
    r"\b(?:mr|mrs|ms|miss|dr|prof|sir|lord|lady|president|vice president|"
    r"prime minister|minister|chancellor|senator|representative|governor|"
    r"mayor|general|colonel|major|captain|admiral|sergeant|lieutenant|"
    r"king|queen|prince|princess|pope|imam|rabbi|judge|justice|"
    r"secretary|ambassador|spokesman|spokeswoman|spokesperson|"
    r"chief executive|ceo|cfo|chairman|chairwoman|founder|director|"
    r"analyst|economist|professor|researcher|author|reporter|correspondent)"
)
PERSON_TITLE = re.compile(rf"{PERSON_TITLE_WORDS}\s+$", re.IGNORECASE)
# A span that starts with a title names a person, as in "Secretary Lloyd Austin".
PERSON_TITLE_LEADING = re.compile(rf"^{PERSON_TITLE_WORDS}\s+", re.IGNORECASE)
# A person name follows these verbs of speech more often than a company does,
# so speech alone is never a claim. The claim test covers this.

# A country, region, or demonym is a place, not a company.
PLACE_NAME = re.compile(
    r"^(?:the\s+)?(?:afghan\w*|africa\w*|america\w*|arab\w*|argentin\w*|asia\w*|"
    r"australia\w*|austria\w*|bangladesh\w*|belarus\w*|belgi\w*|brazil\w*|"
    r"britain|british|bulgaria\w*|burma|burmese|cambodia\w*|cameroon\w*|canada|"
    r"canadian|caribbean|chad|chile\w*|china|chinese|colombia\w*|congo\w*|"
    r"croatia\w*|cuba\w*|cypr\w*|czech\w*|denmark|danish|dutch|ecuador\w*|"
    r"egypt\w*|england|english|eritrea\w*|estonia\w*|ethiopia\w*|europe\w*|"
    r"finland|finnish|france|french|georgia\w*|german\w*|ghana\w*|greece|greek|"
    r"guatemala\w*|haiti\w*|holland|hondura\w*|hungar\w*|iceland\w*|india\w*|"
    r"indonesia\w*|iran\w*|iraq\w*|ireland|irish|israel\w*|ital\w*|ivory coast|"
    r"jamaica\w*|japan\w*|jordan\w*|kazakh\w*|kenya\w*|korea\w*|kosov\w*|"
    r"kuwait\w*|kyrgyz\w*|laos|latvia\w*|lebanon|lebanese|liberia\w*|libya\w*|"
    r"lithuania\w*|macedonia\w*|malaysia\w*|mali|mexic\w*|moldova\w*|mongolia\w*|"
    r"morocc\w*|mozambi\w*|myanmar|namibia\w*|nepal\w*|netherlands|"
    r"new zealand|nicaragua\w*|niger\w*|north korea\w*|norway|norwegian|"
    r"pakistan\w*|palestin\w*|panama\w*|paraguay\w*|peru\w*|philippin\w*|"
    r"poland|polish|portug\w*|qatar\w*|romania\w*|russia\w*|rwanda\w*|"
    r"saudi\w*|scotland|scottish|senegal\w*|serbia\w*|singapore\w*|slovak\w*|"
    r"slovenia\w*|somalia\w*|south africa\w*|south korea\w*|soviet|spain|spanish|"
    r"sri lanka\w*|sudan\w*|sweden|swedish|swiss|switzerland|syria\w*|taiwan\w*|"
    r"tajik\w*|tanzania\w*|thai\w*|tibet\w*|tunisia\w*|turk\w*|uganda\w*|"
    r"ukrain\w*|united kingdom|united states|uruguay\w*|u\.?s\.?a?\.?|uk|u\.?k\.?|"
    r"uzbek\w*|venezuela\w*|vietnam\w*|wales|welsh|yemen\w*|zambia\w*|zimbabwe\w*|"
    r"beijing|moscow|washington|london|tokyo|paris|berlin|brussels|geneva|"
    r"hong kong|shanghai|taipei|seoul|delhi|mumbai|dubai|kyiv|kiev)$",
    re.IGNORECASE,
)
# A bare determiner or generic word is not a name.
BARE_WORD = re.compile(
    r"^(?:the|a|an|this|that|these|those|its|his|her|their|our|"
    r"but|and|or|if|when|while|after|before|then|also|however|"
    r"mr|mrs|ms|dr)$",
    re.IGNORECASE,
)

MIN_NAME_CHARS = 3
# The claim must be near the span, not anywhere in a long sentence.
CLAIM_WINDOW = 120


POSSESSIVE_END = re.compile(r"['’]s$")
TOKEN_OFFSETS = re.compile(r"\S+")


LEADING_ARTICLE = re.compile(r"^the\s+", re.IGNORECASE)


def _strip_trailing_stopwords(span: str) -> str:
    """Remove a trailing connector left by the span pattern."""
    return re.sub(rf"\s+{CONNECTOR}$", "", span, flags=re.IGNORECASE).strip()


class ClaimCompanyMatcher:
    """Find the named companies that one sentence makes a financial claim about."""

    name = "any-named-company-claim-v2"
    no_hit_reason = "no-eligible-company-target-passage"

    def __init__(self, *, claim_window: int = CLAIM_WINDOW) -> None:
        self.claim_window = claim_window

    def _company_evidence(
        self, sentence: str, span: str, start: int, end: int
    ) -> str | None:
        """Give the reason this span names a company, or None."""
        before = sentence[:start]
        after = sentence[end:]
        if LEGAL_FORM.match(after):
            return "legal-form-word"
        last_token = span.split()[-1].rstrip(".,")
        if COMPANY_TYPE_WORD.match(last_token) and len(span.split()) > 1:
            return "company-type-word"
        if DESCRIPTOR_BEFORE.search(before):
            return "descriptor-before"
        if DESCRIPTOR_AFTER.match(after):
            return "descriptor-after"
        if POSSESSIVE_ROLE.match(after):
            return "possessive-company-role"
        if SHARE_REFERENCE.match(after) or SHARE_REFERENCE_BEFORE.search(before):
            return "share-reference"
        return None

    def _rejected(
        self, sentence: str, span: str, start: int, evidence: str, whole: str
    ) -> bool:
        """Hold back a span that names something other than a company."""
        if evidence != "legal-form-word" and (
            NOT_A_COMPANY.search(span) or NOT_A_COMPANY.search(whole)
        ):
            return True
        if STATE_BANK.search(span) or STATE_BANK.search(whole):
            return True
        if PERSON_TITLE.search(sentence[:start]):
            return True
        if NONPROFIT_CUE.search(sentence[:start]):
            return True
        if PERSON_ROLE_AFTER.match(sentence[start + len(span) :]):
            return True
        return False

    def _candidate_spans(self, sentence: str):
        """Give each span and its tails, longest tail first.

        The span pattern absorbs a sentence-initial descriptor, as in
        "Drugmaker Pfizer". A tail moves that word into the text before the
        span, where the descriptor test can see it.
        """
        for match in NAME_SPAN.finditer(sentence):
            whole = _strip_trailing_stopwords(match.group(0))
            tokens = list(TOKEN_OFFSETS.finditer(whole))
            for index in range(len(tokens)):
                # A tail must not start at a connector, or "Bank of England"
                # would give the span "of England".
                if re.fullmatch(CONNECTOR, tokens[index].group(0), re.IGNORECASE):
                    continue
                tail = whole[tokens[index].start() :]
                start = match.start() + tokens[index].start()
                stripped = POSSESSIVE_END.sub("", _strip_trailing_stopwords(tail))
                # A sentence full stop is not part of the name. An initial
                # keeps its stop, as in "J.P. Morgan".
                stripped = stripped.rstrip(",;:")
                if stripped.endswith(".") and not re.search(
                    r"\b[A-Z]\.$", stripped
                ):
                    stripped = stripped[:-1]
                if not stripped:
                    continue
                # The guards read the whole span, so a tail cannot escape them.
                yield (
                    stripped,
                    start,
                    start + len(stripped),
                    POSSESSIVE_END.sub("", whole),
                    match.start(),
                )

    def find(self, sentence: str) -> list[dict[str, str]]:
        """Give one record for each company target of this sentence."""
        hits: dict[str, dict[str, str]] = {}
        done: set[int] = set()
        for span, start, end, whole, origin in self._candidate_spans(sentence):
            # The tails of one span run longest first. One span gives at most
            # one company, so a shorter tail of a span already matched is skipped.
            if origin in done:
                continue
            if len(span) < MIN_NAME_CHARS or not re.search(r"[A-Za-z]", span):
                continue
            span = LEADING_ARTICLE.sub("", span).strip()
            if BARE_WORD.match(span) or PLACE_NAME.match(span):
                continue
            # A tail of a place name is still a place, as in "States" from
            # "United States" and "Kong" from "Hong Kong".
            if PLACE_NAME.match(whole) or PERSON_TITLE_LEADING.match(span):
                continue
            evidence = self._company_evidence(sentence, span, start, end)
            if evidence is None:
                continue
            if self._rejected(sentence, span, start, evidence, whole):
                continue
            done.add(origin)
            window = sentence[
                max(0, start - self.claim_window) : end + self.claim_window
            ]
            if not FINANCIAL_CLAIM.search(window.replace(span, " ")):
                continue
            key = span.casefold()
            if key not in hits:
                hits[key] = {
                    "company_evidence": evidence,
                    "matched_text": span,
                    "name": span,
                }
        return [hits[key] for key in sorted(hits)]


def find_in_sentences(
    sentences: Iterable[str], matcher: ClaimCompanyMatcher
) -> list[dict[str, str]]:
    """Give the company targets of a group of sentences, without repeats."""
    seen: dict[str, dict[str, str]] = {}
    for sentence in sentences:
        for hit in matcher.find(sentence):
            seen.setdefault(hit["name"].casefold(), hit)
    return [seen[key] for key in sorted(seen)]
