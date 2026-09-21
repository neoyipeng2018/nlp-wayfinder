"""Build the staff-written, listed-company-filtered VOA News source."""

from __future__ import annotations

import argparse
import gzip
import html
import json
import re
import sys
from collections import Counter
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_filtered_common_pile_news import (  # noqa: E402
    MAX_PASSAGE_CHARS,
    MIN_PASSAGE_CHARS,
    MIN_PASSAGE_SENTENCES,
    SENTENCE_BOUNDARY,
    canonical_json,
    deterministic_gzip_text,
    file_sha256,
    sentence_reason,
    sha256_text,
    split_for,
    write_json_line,
    write_pool_manifest,
)
from crawl_voa_news import ARTICLE_ID  # noqa: E402

AGENCY_AUTHOR = re.compile(
    r"\b(?:reuters|associated press|ap|afp|agence france[- ]presse)\b", re.IGNORECASE
)
AGENCY_CREDIT = re.compile(
    r"\b(?:Reuters|Associated Press|AP|AFP|Agence France[- ]Presse)\b"
)
THIRD_PARTY_NOTICE = re.compile(
    r"©|\bcopyright\b|all rights reserved|used with permission|"
    r"originally (?:published|appeared)|republished (?:with|under)|"
    r"creative commons|licensed under",
    re.IGNORECASE,
)
PUBDATE = re.compile(r'<time pubdate="pubdate" datetime="(\d{4}-\d{2}-\d{2})T')
COMPANY_CUE = re.compile(
    r"\b(?:compan(?:y|y's|ies)|firms?|corporations?|conglomerates?|subsidiar(?:y|ies)|"
    r"shares?|stocks?|shareholders?|investors?|stock market|nasdaq|nyse|"
    r"chief executive|ceo|chairman|executives?|founder|"
    r"makers?|manufacturers?|automakers?|carmakers?|drugmakers?|chipmakers?|"
    r"retailers?|airlines?|carriers?|lenders?|banks?|insurers?|brands?|giants?|"
    r"revenue|profits?|earnings|sales|contracts?|acquisitions?|merger|deal)\b",
    re.IGNORECASE,
)
CUE_WINDOW = 60
LEGAL_FORM_AFTER = re.compile(
    r"^(?:,?\s+|\s*&\s*)(?:inc|corp|corporation|co|company|ltd|limited|plc|llc|"
    r"n\.v|s\.a|ag|se|group|holdings)\b\.?",
    re.IGNORECASE,
)
ABBREVIATION = re.compile(
    r"(?:^|[\s(])(?:(?:[A-Z]\.)+|(?:[a-z]\.){2}|(?:Mr|Mrs|Ms|Dr|St|Jr|Sr|Gen|Sen|Rep|Gov|Lt|"
    r"Col|Sgt|Capt|Adm|Prof|Rev|No|Inc|Corp|Co|Ltd|Jan|Feb|Mar|Apr|Aug|Sept?|Oct|Nov|"
    r"Dec|vs|etc|approx)\.)$"
)
LEGAL_SUFFIX = re.compile(
    r"(?:[\s,]+(?:inc|incorporated|corp|corporation|co|company|ltd|limited|plc|"
    r"l\.?p|llc|n\.?v|s\.?a|ag|se|asa|ab|oyj|s\.?p\.?a|holdings?|group|"
    r"the|/[a-z]{2,3}/?|/adr|adr|\([^)]*\))\.?)+$",
    re.IGNORECASE,
)


class ArticlePage(HTMLParser):
    """Collect the headline, byline links, and direct paragraphs of the body."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.authors: list[str] = []
        self.blocks: list[str | None] = []
        self.body_text: list[str] = []
        self._stack: list[str] = []
        self._in_title = False
        self._in_details = 0
        self._in_author = False
        self._content_depth: int | None = None
        self._wsw_depth: int | None = None
        self._paragraph: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if tag in {"br", "img", "hr", "input", "meta", "link", "source", "wbr"}:
            return
        self._stack.append(tag)
        depth = len(self._stack)
        if tag == "h1" and "pg-title" in classes and not self.title:
            self._in_title = True
        if tag == "div" and "publishing-details" in classes and not self._in_details:
            self._in_details = depth
        if (
            self._in_details
            and tag == "a"
            and "links__item-link" in classes
            and (values.get("href") or "").startswith("/author/")
        ):
            self._in_author = True
            self.authors.append("")
        if tag == "div" and values.get("id") == "article-content":
            self._content_depth = depth
        if (
            self._content_depth is not None
            and self._wsw_depth is None
            and tag == "div"
            and "wsw" in classes
            and not self.blocks
        ):
            self._wsw_depth = depth
            return
        if self._wsw_depth is not None and depth == self._wsw_depth + 1:
            if tag == "p":
                self._paragraph = []
            else:
                self.blocks.append(None)

    def handle_endtag(self, tag: str) -> None:
        if tag not in self._stack:
            return
        while self._stack:
            depth = len(self._stack)
            current = self._stack.pop()
            if current == "h1":
                self._in_title = False
            if current == "a":
                self._in_author = False
            if depth == self._in_details:
                self._in_details = 0
            if self._wsw_depth is not None and depth == self._wsw_depth + 1:
                if self._paragraph is not None:
                    text = re.sub(r"\s+", " ", "".join(self._paragraph)).strip()
                    self.blocks.append(text or None)
                    self._paragraph = None
            if depth == self._wsw_depth:
                self._wsw_depth = -1
            if depth == self._content_depth:
                self._content_depth = None
            if current == tag:
                break

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._in_author:
            self.authors[-1] += data
        if self._paragraph is not None:
            self._paragraph.append(data)
        if self._content_depth is not None:
            self.body_text.append(data)


def parse_page(page_html: str) -> dict[str, Any]:
    parser = ArticlePage()
    parser.feed(page_html)
    match = PUBDATE.search(page_html)
    return {
        "authors": [re.sub(r"\s+", " ", a).strip() for a in parser.authors if a.strip()],
        "blocks": parser.blocks,
        "body_text": re.sub(r"\s+", " ", html.unescape(" ".join(parser.body_text))),
        "published": date.fromisoformat(match.group(1)) if match else None,
        "title": re.sub(r"\s+", " ", parser.title).strip(),
    }


def match_name(edgar_name: str) -> str:
    """Strip legal-form and filing tags from one EDGAR company name."""
    name = re.sub(r"\s+", " ", edgar_name).strip()
    previous = None
    while previous != name:
        previous = name
        name = LEGAL_SUFFIX.sub("", name).strip(" ,.&-")
    return re.sub(r"^the\s+", "", name, flags=re.IGNORECASE)


class CompanyMatcher:
    """Deterministic listed-company name matcher for one pinned snapshot.

    A match is a whole-word, case-insensitive hit of a normalized EDGAR name
    where every word of the hit starts with a capital letter or digit. The hit
    must be followed by a legal-form word, or a company cue word must be within
    CUE_WINDOW characters of the hit in the same sentence. The hit must not
    touch another capitalized word (a longer proper name), except a legal-form
    word after it or the first word of the sentence before it.
    """

    def __init__(self, snapshot: Mapping[str, Any], exchanges: list[str], min_chars: int):
        fields = snapshot["fields"]
        names: dict[str, dict[str, str]] = {}
        for row in snapshot["data"]:
            entry = dict(zip(fields, row))
            if entry["exchange"] not in exchanges:
                continue
            name = match_name(str(entry["name"]))
            if len(name) < min_chars or not re.search(r"[A-Za-z]", name):
                continue
            key = name.casefold()
            known = names.get(key)
            if known is None or int(entry["cik"]) < int(known["cik"]):
                names[key] = {"cik": str(entry["cik"]), "name": name}
        self.names = names
        ordered = sorted(names, key=lambda key: (-len(key), key))
        self.pattern = re.compile(
            r"(?<![\w&-])(?:"
            + "|".join(re.escape(names[key]["name"]).replace(r"\ ", r"\s+") for key in ordered)
            + r")(?![\w&-])",
            re.IGNORECASE,
        )

    def find(self, sentence: str) -> list[dict[str, str]]:
        hits = []
        for match in self.pattern.finditer(sentence):
            text = match.group(0)
            words = text.split()
            if not all(word[0].isupper() or word[0].isdigit() for word in words):
                continue
            before = sentence[: match.start()].split()
            after = sentence[match.end() :]
            if before and before[-1][0].isupper() and len(before) > 1:
                continue
            following = re.match(r"^[\s,]*([^\s,]+)", after) if not re.match(r"^[,;:]", after) else None
            if following and following.group(1)[0].isupper() and not LEGAL_FORM_AFTER.match(after):
                continue
            near = sentence[max(0, match.start() - CUE_WINDOW) : match.end() + CUE_WINDOW]
            has_cue = bool(COMPANY_CUE.search(near.replace(text, " ")))
            if not has_cue and not LEGAL_FORM_AFTER.match(sentence[match.end() :]):
                continue
            entry = self.names[re.sub(r"\s+", " ", text).casefold()]
            hits.append({"cik": entry["cik"], "matched_text": text, "name": entry["name"]})
        return hits


def split_sentences(block: str) -> list[str]:
    """Split at sentence ends, but not after initials or common abbreviations."""
    sentences, start = [], 0
    for boundary in SENTENCE_BOUNDARY.finditer(block):
        if ABBREVIATION.search(block[start : boundary.start()]):
            continue
        sentences.append(block[start : boundary.start()].strip())
        start = boundary.end()
    sentences.append(block[start:].strip())
    return [sentence for sentence in sentences if sentence]


def select_passage(
    blocks: list[str | None], matcher: CompanyMatcher
) -> tuple[str | None, list[dict[str, str]], list[dict[str, object]]]:
    """Keep the longest safe consecutive window that names a listed company."""
    sentences: list[str | None] = []
    for block in blocks:
        if block is None:
            sentences.append(None)
            continue
        sentences.extend(split_sentences(block))

    runs: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    exclusions: list[dict[str, object]] = []
    position = 0
    for sentence in sentences:
        if sentence is None:
            if current:
                runs.append(current)
                current = []
            continue
        reason = sentence_reason(sentence)
        if reason is None:
            current.append((position, sentence))
        else:
            if current:
                runs.append(current)
                current = []
            exclusions.append(
                {"kind": "sentence", "position": position, "reason": reason,
                 "sha256": sha256_text(sentence)}
            )
        position += 1
    if current:
        runs.append(current)

    windows: list[list[tuple[int, str]]] = []
    for run in runs:
        window: list[tuple[int, str]] = []
        size = 0
        for item in run:
            extra = len(item[1]) + (1 if window else 0)
            if window and size + extra > MAX_PASSAGE_CHARS:
                windows.append(window)
                window, size = [], 0
                extra = len(item[1])
            window.append(item)
            size += extra
        if window:
            windows.append(window)

    scored = []
    for window in windows:
        text = " ".join(sentence for _, sentence in window)
        if len(window) < MIN_PASSAGE_SENTENCES or len(text) < MIN_PASSAGE_CHARS:
            continue
        companies = [hit for _, sentence in window for hit in matcher.find(sentence)]
        if companies:
            scored.append((window, text, companies))

    selected_positions: set[int] = set()
    passage, companies = None, []
    if scored:
        window, passage, companies = max(
            scored, key=lambda item: (len(item[1]), -item[0][0][0])
        )
        selected_positions = {pos for pos, _ in window}
    reason = "outside-selected-consecutive-passage" if scored else "no-eligible-listed-company-passage"
    for run in runs:
        for pos, sentence in run:
            if pos not in selected_positions:
                exclusions.append(
                    {"kind": "sentence", "position": pos, "reason": reason,
                     "sha256": sha256_text(sentence)}
                )
    unique = {hit["cik"]: hit for hit in companies}
    return passage, sorted(unique.values(), key=lambda h: int(h["cik"])), sorted(
        exclusions, key=lambda item: int(item["position"])
    )


def article_stop_reason(page: Mapping[str, Any], parsed: Mapping[str, Any]) -> str | None:
    if page["status"] != 200:
        return "page-not-retrieved"
    if not ARTICLE_ID.match(str(page["final_url"])):
        return "not-voa-english-article-url"
    if not parsed["title"] or not any(parsed["blocks"]):
        return "not-text-article"
    if not parsed["authors"]:
        return "byline-missing"
    if any(AGENCY_AUTHOR.search(author) for author in parsed["authors"]):
        return "byline-names-wire-agency"
    if AGENCY_CREDIT.search(parsed["body_text"]):
        return "sentence-credits-wire-agency"
    if THIRD_PARTY_NOTICE.search(parsed["body_text"]):
        return "third-party-copyright-or-license-notice"
    if parsed["published"] is None:
        return "publication-date-missing"
    return None


def build(config_path: Path, data_dir: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    rights = config["rights"]
    company_filter = config["company_filter"]
    snapshot_path = data_dir / company_filter["snapshot_file"]
    if file_sha256(snapshot_path) != company_filter["snapshot_sha256"]:
        raise ValueError("company-snapshot-mismatch")
    matcher = CompanyMatcher(
        json.loads(snapshot_path.read_text(encoding="utf-8")),
        company_filter["exchanges"],
        company_filter["min_name_chars"],
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = output_dir / "filtered-source.jsonl.gz"
    exclusion_path = output_dir / "exclusions.jsonl.gz"
    pool_path = output_dir / "candidate-pool.json"
    split_counts: Counter[str] = Counter()
    exclusion_counts: Counter[str] = Counter()
    pages_by_split: Counter[str] = Counter()
    candidate_pool: list[dict[str, str]] = []
    shards = sorted((data_dir / "pages").glob("*.jsonl.gz"))
    shard_hashes = {shard.name: file_sha256(shard) for shard in shards}

    with deterministic_gzip_text(source_path) as out, deterministic_gzip_text(
        exclusion_path
    ) as excluded:
        for shard in shards:
            with gzip.open(shard, "rt", encoding="utf-8") as handle:
                for line in handle:
                    page = json.loads(line)
                    url = page["url"]
                    parsed = parse_page(page["html"]) if page["status"] == 200 else {}
                    reason = article_stop_reason(page, parsed)
                    split = None
                    if reason is None:
                        split = split_for(parsed["published"], config["split_periods"])
                        if split is None:
                            reason = "publication-date-outside-fixed-periods"
                    if reason is None:
                        pages_by_split[split] += 1
                        passage, companies, removals = select_passage(parsed["blocks"], matcher)
                        for removal in removals:
                            exclusion_counts[str(removal["reason"])] += 1
                            write_json_line(excluded, {"article_url": url, **removal})
                        if passage is None:
                            reason = "no-eligible-listed-company-passage"
                    if reason is not None:
                        exclusion_counts[reason] += 1
                        write_json_line(
                            excluded,
                            {"article_url": url, "kind": "record", "reason": reason,
                             "response_sha256": page["response_sha256"]},
                        )
                        continue

                    filtered_sha256 = sha256_text(passage)
                    candidate_id = sha256_text(
                        "\0".join([config["source_id"], url, filtered_sha256, split])
                    )
                    authors = ", ".join(parsed["authors"])
                    out.write(canonical_json({
                        "article_url": url,
                        "attribution_text": (
                            f"{authors}, {parsed['title']}, Voice of America, {url}; "
                            f"public domain under the VOA copyright statement at "
                            f"{rights['evidence_url']}; passage text changed by removal "
                            "of marked third-party or unclear text."
                        ),
                        "authors": parsed["authors"],
                        "candidate_id": candidate_id,
                        "contractor_authorship_uncertainty": rights["stated_uncertainty"],
                        "filtered_text_sha256": filtered_sha256,
                        "license_id": rights["license_id"],
                        "listed_company_matches": companies,
                        "normalized_passage": passage,
                        "page_fetched_at": page["fetched_at"],
                        "page_response_sha256": page["response_sha256"],
                        "published_at": parsed["published"].isoformat(),
                        "publisher": "Voice of America",
                        "publisher_evidence_excerpt": rights["evidence_excerpt"],
                        "publisher_evidence_excerpt_sha256": sha256_text(rights["evidence_excerpt"]),
                        "publisher_evidence_response_sha256": rights["evidence_response_sha256"],
                        "publisher_evidence_retrieved_at": rights["evidence_retrieved_at"],
                        "publisher_evidence_url": rights["evidence_url"],
                        "removed_parts": removals,
                        "review_status": "pass",
                        "source_id": config["source_id"],
                        "split": split,
                        "title": parsed["title"],
                    }) + "\n")
                    candidate_pool.append({"candidate_id": candidate_id, "split": split})
                    split_counts[split] += 1

    candidate_pool.sort(key=lambda item: (item["candidate_id"], item["split"]))
    write_pool_manifest(pool_path, {
        "candidate_pool": candidate_pool,
        "candidate_pool_size": len(candidate_pool),
        "order_salt": config["order_salt"],
        "source_id": config["source_id"],
        "source_type": config["source_type"],
        "stage": 1,
    })
    summary = {
        "built_on": config["built_on"],
        "candidate_pool_sha256": sha256_text(canonical_json(candidate_pool)),
        "candidate_pool_size": len(candidate_pool),
        "company_names_in_filter": len(matcher.names),
        "eligible_articles_by_split": dict(sorted(pages_by_split.items())),
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "input_page_shard_sha256": shard_hashes,
        "output_sha256": {
            "candidate-pool.json": file_sha256(pool_path),
            "exclusions.jsonl.gz": file_sha256(exclusion_path),
            "filtered-source.jsonl.gz": file_sha256(source_path),
        },
        "source_id": config["source_id"],
        "split_counts": dict(sorted(split_counts.items())),
        "thresholds_met": {
            split: split_counts[split] >= minimum
            for split, minimum in config["minimum_passages"].items()
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.config, args.data_dir, args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
