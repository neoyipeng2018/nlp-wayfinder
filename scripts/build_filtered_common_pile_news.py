"""Build the passage-rights-filtered Common Pile News source."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import urllib.parse
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator, Mapping, TextIO


SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
DIRECT_QUOTE = re.compile(r'["\u201c\u201d]|\u2018[^\u2019]+\u2019')
THIRD_PARTY_MARKER = re.compile(
    r"\b(?:photo|image|video|audio|twitter|tweet|facebook|instagram|youtube|"
    r"republish|originally published|used with permission|copyright|wire copy|"
    r"associated press|reuters|agence france-presse|afp)\b",
    re.IGNORECASE,
)
UNCLEAR_MARKER = re.compile(
    r"\b(?:share this|related stor(?:y|ies)|leave a comment|your email address|"
    r"subscribe|newsletter|all rights reserved)\b",
    re.IGNORECASE,
)
CONFLICTING_NOTICE = re.compile(
    r"\b(?:all rights reserved|CC\s+BY-(?:NC|ND)|Creative Commons[^\n]{0,40}"
    r"(?:NonCommercial|NoDerivatives))\b",
    re.IGNORECASE,
)
URL_DATE = re.compile(
    r"/(20\d{2}|19\d{2})/(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])(?:/|$)"
)
MIN_PASSAGE_CHARS = 400
MIN_PASSAGE_SENTENCES = 3
MAX_PASSAGE_CHARS = 6_000


def canonical_json(value: object) -> str:
    """Serialize one value for a stable hash."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def deterministic_gzip_text(path: Path) -> Iterator[TextIO]:
    """Open a gzip text file with stable metadata."""
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            import io

            with io.TextIOWrapper(zipped, encoding="utf-8", newline="\n") as text:
                yield text


def normalized_host(url: str) -> str:
    host = urllib.parse.urlparse(url).hostname or ""
    return host.lower().removeprefix("www.")


def parse_published_date(url: str, created: object) -> date | None:
    """Read an exact date from the article URL or source date field."""
    match = URL_DATE.search(url)
    if match:
        try:
            return date(*(int(part) for part in match.groups()))
        except ValueError:
            return None

    value = str(created or "").strip()
    value = re.sub(r"^(?:Published|Updated)\s+(?:on\s+)?", "", value, flags=re.I)
    value = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value)
    for pattern in (
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    return None


def split_for(published: date, periods: Mapping[str, Mapping[str, str]]) -> str | None:
    for split in ("training", "development", "blind"):
        period = periods[split]
        if date.fromisoformat(period["start"]) <= published <= date.fromisoformat(
            period["end"]
        ):
            return split
    return None


def sentence_reason(sentence: str) -> str | None:
    if len(sentence.strip()) < 20:
        return "unclear-short-fragment"
    if DIRECT_QUOTE.search(sentence):
        return "direct-or-block-quotation"
    if THIRD_PARTY_MARKER.search(sentence) or "\u00a9" in sentence:
        return "marked-third-party-or-media-text"
    if UNCLEAR_MARKER.search(sentence):
        return "navigation-or-page-furniture"
    return None


def longest_safe_passage(text: str) -> tuple[str | None, list[dict[str, object]]]:
    """Keep one consecutive run and return a hash record for all removed text."""
    lines = text.splitlines()
    body = " ".join(lines[3:]).strip()
    sentences = [item.strip() for item in SENTENCE_BOUNDARY.split(body) if item.strip()]
    runs: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    exclusions: list[dict[str, object]] = []

    for position, sentence in enumerate(sentences):
        reason = sentence_reason(sentence)
        if reason is None:
            current.append((position, sentence))
            continue
        if current:
            runs.append(current)
            current = []
        exclusions.append(
            {
                "kind": "sentence",
                "position": position,
                "reason": reason,
                "sha256": sha256_text(sentence),
            }
        )
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
                window = []
                size = 0
            window.append(item)
            size += len(item[1]) + (1 if len(window) > 1 else 0)
        if window:
            windows.append(window)

    eligible = [
        window
        for window in windows
        if len(window) >= MIN_PASSAGE_SENTENCES
        and len(" ".join(sentence for _, sentence in window)) >= MIN_PASSAGE_CHARS
    ]
    if not eligible:
        for run in runs:
            for position, sentence in run:
                exclusions.append(
                    {
                        "kind": "sentence",
                        "position": position,
                        "reason": "no-eligible-consecutive-passage",
                        "sha256": sha256_text(sentence),
                    }
                )
        return None, sorted(exclusions, key=lambda item: int(item["position"]))

    selected = max(
        eligible,
        key=lambda window: (
            sum(len(sentence) for _, sentence in window),
            -window[0][0],
        ),
    )
    selected_positions = {position for position, _ in selected}
    for run in runs:
        for position, sentence in run:
            if position not in selected_positions:
                exclusions.append(
                    {
                        "kind": "sentence",
                        "position": position,
                        "reason": "outside-selected-consecutive-passage",
                        "sha256": sha256_text(sentence),
                    }
                )
    passage = " ".join(sentence for _, sentence in selected)
    return passage, sorted(exclusions, key=lambda item: int(item["position"]))


def record_id(record: Mapping[str, object]) -> str:
    return f"{record.get('source', '')}:{record.get('id', '')}"


def write_json_line(handle: TextIO, value: object) -> None:
    handle.write(canonical_json(value) + "\n")


def write_pool_manifest(path: Path, manifest: Mapping[str, object]) -> None:
    """Write a readable pool with one candidate on each line."""
    candidates = manifest["candidate_pool"]
    assert isinstance(candidates, list)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write('{\n  "candidate_pool": [\n')
        for index, candidate in enumerate(candidates):
            suffix = "," if index + 1 < len(candidates) else ""
            handle.write(f"    {canonical_json(candidate)}{suffix}\n")
        handle.write("  ],\n")
        remaining = [key for key in sorted(manifest) if key != "candidate_pool"]
        for index, key in enumerate(remaining):
            suffix = "," if index + 1 < len(remaining) else ""
            handle.write(f"  {json.dumps(key)}: {canonical_json(manifest[key])}{suffix}\n")
        handle.write("}\n")


def build(config_path: Path, input_dir: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    archive = config["archive"]
    publishers: Mapping[str, Mapping[str, object]] = config["publishers"]
    output_dir.mkdir(parents=True, exist_ok=True)

    for relative, expected in archive["files"].items():
        path = input_dir / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise ValueError(f"archive-file-mismatch:{relative}")

    source_path = output_dir / "filtered-source.jsonl.gz"
    exclusion_path = output_dir / "exclusions.jsonl.gz"
    pool_path = output_dir / "candidate-pool.json"
    record_counts: Counter[str] = Counter()
    passage_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    license_counts: Counter[str] = Counter()
    exclusion_counts: Counter[str] = Counter()
    candidate_pool: list[dict[str, str]] = []

    with deterministic_gzip_text(source_path) as source_output, deterministic_gzip_text(
        exclusion_path
    ) as exclusion_output:
        for relative in sorted(archive["files"]):
            path = input_dir / relative
            with gzip.open(path, "rt", encoding="utf-8") as records:
                for raw_line in records:
                    record = json.loads(raw_line)
                    source = str(record.get("source", ""))
                    identifier = record_id(record)
                    record_counts[source] += 1
                    publisher = publishers.get(source)
                    if publisher is None:
                        reason = "publisher-rights-not-approved"
                        exclusion_counts[reason] += 1
                        write_json_line(
                            exclusion_output,
                            {"kind": "record", "record_id": identifier, "reason": reason},
                        )
                        continue

                    metadata = record.get("metadata")
                    if not isinstance(metadata, Mapping):
                        metadata = {}
                    url = str(metadata.get("url") or "").strip()
                    author = str(metadata.get("author") or "").strip()
                    lines = str(record.get("text") or "").splitlines()
                    title = lines[0].strip() if lines else ""
                    host = normalized_host(url)
                    stop_reason = None
                    if host not in publisher["allowed_hosts"]:
                        stop_reason = "article-host-not-approved"
                    elif not url or not author or not title:
                        stop_reason = "attribution-incomplete"
                    elif CONFLICTING_NOTICE.search("\n".join(lines[:8] + lines[-8:])):
                        stop_reason = "article-notice-conflicts"
                    published = parse_published_date(url, record.get("created"))
                    split = (
                        split_for(published, config["split_periods"])
                        if published is not None
                        else None
                    )
                    if stop_reason is None and split is None:
                        stop_reason = "publication-date-outside-fixed-periods"

                    if stop_reason is not None:
                        exclusion_counts[stop_reason] += 1
                        write_json_line(
                            exclusion_output,
                            {
                                "article_url": url,
                                "kind": "record",
                                "record_id": identifier,
                                "reason": stop_reason,
                            },
                        )
                        continue

                    passage, removals = longest_safe_passage(str(record.get("text") or ""))
                    for removal in removals:
                        reason = str(removal["reason"])
                        exclusion_counts[reason] += 1
                        write_json_line(
                            exclusion_output,
                            {"record_id": identifier, **removal},
                        )
                    if passage is None:
                        reason = "no-eligible-publisher-created-passage"
                        exclusion_counts[reason] += 1
                        write_json_line(
                            exclusion_output,
                            {
                                "article_url": url,
                                "kind": "record",
                                "record_id": identifier,
                                "reason": reason,
                            },
                        )
                        continue

                    raw_sha256 = sha256_text(canonical_json(record))
                    filtered_sha256 = sha256_text(passage)
                    candidate_id = sha256_text(
                        "\0".join(
                            [config["source_id"], identifier, filtered_sha256, split]
                        )
                    )
                    excerpt = str(publisher["evidence_excerpt"])
                    result = {
                        "article_evidence_sha256": None,
                        "article_url": url,
                        "attribution_text": (
                            f"{author}, {title}, {publisher['publisher']}, {url}; "
                            f"licensed under {publisher['license_id']} at "
                            f"{publisher['license_url']}; passage text changed by removal "
                            "of marked third-party or unclear text."
                        ),
                        "author": author,
                        "candidate_id": candidate_id,
                        "common_pile_revision": archive["revision"],
                        "common_pile_source": source,
                        "filtered_text_sha256": filtered_sha256,
                        "license_id": publisher["license_id"],
                        "license_url": publisher["license_url"],
                        "normalized_passage": passage,
                        "published_at": published.isoformat(),
                        "publisher": publisher["publisher"],
                        "publisher_evidence_excerpt": excerpt,
                        "publisher_evidence_excerpt_sha256": sha256_text(excerpt),
                        "publisher_evidence_response_sha256": publisher[
                            "evidence_response_sha256"
                        ],
                        "publisher_evidence_retrieved_at": publisher[
                            "evidence_retrieved_at"
                        ],
                        "publisher_evidence_url": publisher["evidence_url"],
                        "raw_record_sha256": raw_sha256,
                        "record_id": identifier,
                        "removed_parts": removals,
                        "review_status": "pass",
                        "source_id": config["source_id"],
                        "split": split,
                        "title": title,
                    }
                    write_json_line(source_output, result)
                    candidate_pool.append({"candidate_id": candidate_id, "split": split})
                    passage_counts[source] += 1
                    split_counts[split] += 1
                    license_counts[str(publisher["license_id"])] += 1

    candidate_pool.sort(key=lambda item: (item["candidate_id"], item["split"]))
    pool_manifest = {
        "candidate_pool": candidate_pool,
        "candidate_pool_size": len(candidate_pool),
        "order_salt": config["order_salt"],
        "source_id": config["source_id"],
        "source_type": config["source_type"],
        "stage": 1,
    }
    write_pool_manifest(pool_path, pool_manifest)

    summary = {
        "archive_dataset": archive["dataset"],
        "archive_revision": archive["revision"],
        "built_on": config["built_on"],
        "candidate_pool_sha256": sha256_text(canonical_json(candidate_pool)),
        "candidate_pool_size": len(candidate_pool),
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "license_counts": dict(sorted(license_counts.items())),
        "output_sha256": {
            "candidate-pool.json": file_sha256(pool_path),
            "exclusions.jsonl.gz": file_sha256(exclusion_path),
            "filtered-source.jsonl.gz": file_sha256(source_path),
        },
        "passage_counts_by_source": dict(sorted(passage_counts.items())),
        "record_counts_by_source": dict(sorted(record_counts.items())),
        "source_id": config["source_id"],
        "split_counts": dict(sorted(split_counts.items())),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.config, args.input_dir, args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
