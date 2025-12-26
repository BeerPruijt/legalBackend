import time
import requests
from lxml import etree

ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}

BASE = "https://data.rechtspraak.nl/uitspraken/zoeken"
SUBJECT = "http://psi.rechtspraak.nl/rechtsgebied#civielRecht_arbeidsrecht"

def fetch_atom_page(params):
    r = requests.get(BASE, params=params, timeout=30)
    r.raise_for_status()
    return etree.fromstring(r.content)

def parse_entries(feed_root):
    # Returns list of (ecli, summary_text)
    out = []
    for entry in feed_root.xpath("//a:entry", namespaces=ATOM_NS):
        ecli = entry.xpath("string(a:id)", namespaces=ATOM_NS).strip()
        summary = entry.xpath("string(a:summary)", namespaces=ATOM_NS).strip()
        if ecli:
            out.append((ecli, summary))
    return out

def get_all_eclis(*, only_with_inhoudsindicatie: bool = False, polite_sleep=0.2):
    all_eclis = []
    offset = 0
    page_size = 1000

    while True:
        params = {
            "subject": SUBJECT,
            "return": "DOC",   # published docs available
            "max": page_size,
            "from": offset,
            "sort": "ASC",
        }
        feed = fetch_atom_page(params)
        entries = parse_entries(feed)

        if not entries:
            break

        if only_with_inhoudsindicatie:
            # Heuristic: Atom <summary> usually contains the inhoudsindicatie/abstract text (if any)
            entries = [(ecli, s) for (ecli, s) in entries if s]

        all_eclis.extend([ecli for (ecli, _) in entries])

        # next page
        offset += page_size
        time.sleep(polite_sleep)

    return all_eclis

if __name__ == "__main__":
    eclis = get_all_eclis(only_with_inhoudsindicatie=True)
    print("count:", len(eclis))
    open("eclis.txt", "w", encoding="utf-8").write("\n".join(eclis))
