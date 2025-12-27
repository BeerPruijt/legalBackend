import time

import requests
from lxml import etree

ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
BASE_URL = "https://data.rechtspraak.nl/uitspraken/zoeken"
SUBJECT_ARBEIDSRECHT = "http://psi.rechtspraak.nl/rechtsgebied#civielRecht_arbeidsrecht"

def fetch_eclis(
    *,
    subject: str = SUBJECT_ARBEIDSRECHT,
    only_with_summary: bool = False,
    page_size: int = 1000,
    delay: float = 0.2,
    max_results: int | None = None,
) -> list[str]:
    """
    Fetch ECLIs from Rechtspraak API.

    Args:
        subject: Legal subject filter URL
        only_with_summary: If True, only return cases with summary text
        page_size: Number of results per request (max 1000)
        delay: Polite delay between requests in seconds
        max_results: Maximum number of ECLIs to fetch (None for unlimited)

    Returns:
        List of ECLI strings
    """
    eclis: list[str] = []
    offset = 0

    while True:
        if max_results is not None and len(eclis) >= max_results:
            break
        params = {
            "subject": subject,
            "return": "DOC",
            "max": page_size,
            "from": offset,
            "sort": "ASC",
        }

        response = requests.get(BASE_URL, params=params, timeout=30)
        response.raise_for_status()

        feed = etree.fromstring(response.content)
        entries = _parse_entries(feed)

        if not entries:
            break

        for ecli, summary in entries:
            if only_with_summary and not summary:
                continue
            eclis.append(ecli)

        offset += page_size
        time.sleep(delay)

    if max_results is not None:
        return eclis[:max_results]
    return eclis


def _parse_entries(feed: etree._Element) -> list[tuple[str, str]]:
    """Parse Atom feed entries into (ecli, summary) tuples."""
    results = []
    for entry in feed.xpath("//a:entry", namespaces=ATOM_NS):
        ecli = entry.xpath("string(a:id)", namespaces=ATOM_NS).strip()
        summary = entry.xpath("string(a:summary)", namespaces=ATOM_NS).strip()
        if ecli:
            results.append((ecli, summary))
    return results
