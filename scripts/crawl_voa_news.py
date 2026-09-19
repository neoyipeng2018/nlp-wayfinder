"""Download the pinned VOA crawl set into resumable raw-page shards.

The crawl set is fixed by the source configuration before any page is read:
every sitemap `/a/` URL whose article ID is in the development-and-blind ID
window, plus a SHA-256 subset of all other `/a/` URLs. The page date, not the
ID, decides the split later.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ARTICLE_ID = re.compile(r"^https://www\.voanews\.com/a/(?:[^/]+/)?(\d+)\.html$")
SHARD_SIZE = 5_000


def sitemap_urls(sitemap_dir: Path) -> list[str]:
    urls: set[str] = set()
    for path in sorted(sitemap_dir.glob("*.xml.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            urls.update(re.findall(r"<loc>([^<]+)</loc>", handle.read()))
    return sorted(urls)


def in_subset(url: str, salt: str, fraction: float) -> bool:
    value = int(hashlib.sha256(f"{salt}\0{url}".encode()).hexdigest()[:8], 16)
    return value < fraction * 2**32


def crawl_set(urls: list[str], crawl: Mapping[str, Any]) -> list[str]:
    """Return the pinned crawl list: the ID window first, then the subset."""
    low, high = crawl["full_id_window"]
    window: list[tuple[int, str]] = []
    subset: list[tuple[int, str]] = []
    for url in urls:
        match = ARTICLE_ID.match(url)
        if not match:
            continue
        article_id = int(match.group(1))
        if low <= article_id < high:
            window.append((article_id, url))
        elif in_subset(url, crawl["subset_salt"], crawl["subset_fraction"]):
            subset.append((article_id, url))
    return [url for _, url in sorted(window)] + [url for _, url in sorted(subset)]


class RateLimiter:
    def __init__(self, per_second: float) -> None:
        self.interval = 1.0 / per_second
        self.lock = threading.Lock()
        self.next_at = time.monotonic()

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            delay = self.next_at - now
            self.next_at = max(now, self.next_at) + self.interval
        if delay > 0:
            time.sleep(delay)


def fetch(url: str, limiter: RateLimiter, user_agent: str) -> dict[str, object]:
    for attempt in range(5):
        limiter.wait()
        request = urllib.request.Request(url, headers={"User-Agent": user_agent})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
                status, final_url = response.status, response.geturl()
        except urllib.error.HTTPError as error:
            if error.code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(30 * (attempt + 1))
                continue
            body, status, final_url = b"", error.code, url
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt < 4:
                time.sleep(30 * (attempt + 1))
                continue
            body, status, final_url = b"", 0, url
        return {
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "final_url": final_url,
            "html": body.decode("utf-8", "replace"),
            "response_sha256": hashlib.sha256(body).hexdigest(),
            "status": status,
            "url": url,
        }
    raise AssertionError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--user-agent", default="nlp-wayfinder-research/0.1")
    args = parser.parse_args()
    crawl = json.loads(args.config.read_text(encoding="utf-8"))["crawl"]
    sitemap_dir = args.data_dir / "sitemaps"
    urls = sitemap_urls(sitemap_dir)
    listing_sha256 = hashlib.sha256("\n".join(urls).encode()).hexdigest()
    if listing_sha256 != crawl["sitemap_url_list_sha256"]:
        raise SystemExit(f"sitemap-url-list-mismatch:{listing_sha256}")
    targets = crawl_set(urls, crawl)
    shard_dir = args.data_dir / "pages"
    shard_dir.mkdir(parents=True, exist_ok=True)
    limiter = RateLimiter(crawl["requests_per_second"])
    print(f"crawl set: {len(targets)} URLs", flush=True)
    with ThreadPoolExecutor(max_workers=int(crawl["requests_per_second"]) * 2) as pool:
        for start in range(0, len(targets), SHARD_SIZE):
            shard = shard_dir / f"{start // SHARD_SIZE:05d}.jsonl.gz"
            if shard.exists():
                continue
            batch = targets[start : start + SHARD_SIZE]
            pages = list(pool.map(lambda u: fetch(u, limiter, args.user_agent), batch))
            partial = shard.with_suffix(".partial")
            with gzip.open(partial, "wt", encoding="utf-8") as handle:
                for page in pages:
                    handle.write(json.dumps(page, ensure_ascii=False, sort_keys=True) + "\n")
            partial.rename(shard)
            failed = sum(1 for page in pages if page["status"] != 200)
            print(f"{shard.name}: {len(batch)} pages, {failed} not 200", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
