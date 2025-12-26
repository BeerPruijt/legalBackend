import sqlite3
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, List, Tuple

import requests
from lxml import etree

DB_PATH = "rechtspraak_cases.db"
ECLIS_FILE = "eclis.txt"

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
MAX_WORKERS = 5  # parallel fetch threads


NAMESPACES = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "dcterms": "http://purl.org/dc/terms/",
}


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cases (
          ecli TEXT PRIMARY KEY,
          publicatiedatum TEXT,
          rechtbank TEXT,
          abstract TEXT,
          link TEXT,
          fetched_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_publicatiedatum ON cases(publicatiedatum)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_rechtbank ON cases(rechtbank)")
    conn.commit()


def first_text(root, xpath: str) -> Optional[str]:
    nodes = root.xpath(xpath, namespaces=NAMESPACES)
    if not nodes:
        return None
    if isinstance(nodes[0], str):
        return nodes[0].strip() or None
    return (nodes[0].text or "").strip() or None


def extract_metadata(xml_bytes: bytes) -> Dict[str, Optional[str]]:
    root = etree.fromstring(xml_bytes)

    # In your sample:
    # - ECLI + rechtbank + publicatiedatum live in the first rdf:Description (no rdf:about)
    # - abstract + deeplink live in rdf:Description with rdf:about=...deeplink...
    return {
        "ecli": first_text(
            root,
            "//rdf:Description/dcterms:identifier[text()[starts-with(., 'ECLI:')]]/text()",
        ),
        "rechtbank": first_text(
            root,
            "//rdf:Description/dcterms:creator/text()",
        ),
        "publicatiedatum": first_text(
            root,
            "//rdf:Description/dcterms:issued[@rdfs:label='Publicatiedatum']/text()",
        ),
        "abstract": first_text(
            root,
            "//rdf:Description/dcterms:abstract/text()",
        ),
        "link": first_text(
            root,
            "//rdf:Description[@rdf:about]/dcterms:identifier/text()",
        ),
    }


def fetch_meta_xml(ecli: str) -> bytes:
    url = "https://data.rechtspraak.nl/uitspraken/content"
    params = {"id": ecli, "return": "META"}

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r.content
        except Exception as e:
            last_err = e
            # backoff with jitter
            sleep = (0.8 * attempt) + random.random() * 0.3
            time.sleep(sleep)

    raise RuntimeError(f"Failed to fetch {ecli} after {MAX_RETRIES} retries: {last_err}")


def upsert_case(conn: sqlite3.Connection, meta: Dict[str, Optional[str]]) -> None:
    conn.execute(
        """
        INSERT INTO cases (ecli, publicatiedatum, rechtbank, abstract, link, fetched_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(ecli) DO UPDATE SET
          publicatiedatum=excluded.publicatiedatum,
          rechtbank=excluded.rechtbank,
          abstract=excluded.abstract,
          link=excluded.link,
          fetched_at=datetime('now')
        """,
        (
            meta.get("ecli"),
            meta.get("publicatiedatum"),
            meta.get("rechtbank"),
            meta.get("abstract"),
            meta.get("link"),
        ),
    )


def read_eclis(path: str) -> List[str]:
    eclis: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            eclis.append(s)
    return eclis


def get_existing_eclis(conn: sqlite3.Connection) -> set:
    cursor = conn.execute("SELECT ecli FROM cases")
    return {row[0] for row in cursor}


def fetch_and_parse(ecli: str) -> Tuple[str, Optional[Dict[str, Optional[str]]], Optional[str]]:
    """Fetch and parse a single ECLI. Returns (ecli, meta, error)."""
    try:
        xml = fetch_meta_xml(ecli)
        meta = extract_metadata(xml)
        if not meta.get("ecli"):
            return (ecli, None, "No ECLI parsed from response (unexpected XML structure).")
        return (ecli, meta, None)
    except Exception as ex:
        return (ecli, None, str(ex))


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)

        all_eclis = read_eclis(ECLIS_FILE)
        if not all_eclis:
            raise SystemExit(f"No ECLIs found in {ECLIS_FILE}")

        existing = get_existing_eclis(conn)
        eclis = [e for e in all_eclis if e not in existing]

        print(f"Found {len(all_eclis)} ECLIs in file, {len(existing)} already in DB, {len(eclis)} to fetch.")
        print(f"Using {MAX_WORKERS} parallel workers.\n")

        if not eclis:
            print("Nothing to do.")
            return

        ok = 0
        failed = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_and_parse, ecli): ecli for ecli in eclis}

            for i, future in enumerate(as_completed(futures), start=1):
                ecli, meta, error = future.result()

                if error:
                    failed += 1
                    print(f"[{i}/{len(eclis)}] FAIL {ecli}: {error}")
                else:
                    upsert_case(conn, meta)
                    conn.commit()
                    ok += 1
                    print(f"[{i}/{len(eclis)}] OK  {ecli}  ({meta.get('rechtbank')}, {meta.get('publicatiedatum')})")

        print(f"\nDone. Inserted/updated: {ok}. Failed: {failed}. DB: {DB_PATH}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
