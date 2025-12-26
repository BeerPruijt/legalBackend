import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
import anthropic

load_dotenv(".env.local")

DB_PATH = "rechtspraak_cases.db"

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


SYSTEM_PROMPT = """You are a Dutch legal-data classifier.
Task: Decide whether a case abstract is primarily a dispute caused by (a) the wording/validity/scope/absence
of a clause in an employment contract (arbeidsovereenkomst), rather than (b) pure facts (misconduct, performance),
statutory issues, or procedure.

Return ONLY valid JSON with exactly these keys:
- is_contract_drafting_issue (boolean)
- reason (string, <= 200 chars, Dutch or English OK)
- confidence (number between 0 and 1)

Rules:
- If the abstract explicitly mentions contract clauses/bedingen, contract interpretation, missing written agreement,
  or validity/voiding/limiting of a clause, that strongly suggests TRUE.
- If the abstract is mainly about facts (e.g., theft, harassment), sickness/reintegration, or procedural matters
  without contract clause interpretation, lean FALSE.
- If unclear, choose FALSE with confidence <= 0.6.
"""


def fetch_one_row(conn: sqlite3.Connection, ecli: str) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT ecli, publicatiedatum, rechtbank, abstract, link FROM cases WHERE ecli = ?",
        (ecli,),
    ).fetchone()
    if not row:
        raise ValueError(f"ECLI not found in DB: {ecli}")
    return {
        "ecli": row[0],
        "publicatiedatum": row[1],
        "rechtbank": row[2],
        "abstract": row[3] or "",
        "link": row[4],
    }


CLASSIFICATION_TOOL = {
    "name": "classify_case",
    "description": "Classify whether a case is primarily about contract drafting issues",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_contract_drafting_issue": {
                "type": "boolean",
                "description": "True if the case is primarily about contract clause wording/validity/scope/absence"
            },
            "reason": {
                "type": "string",
                "description": "Brief explanation (max 200 chars)"
            },
            "confidence": {
                "type": "number",
                "description": "Confidence score between 0 and 1"
            }
        },
        "required": ["is_contract_drafting_issue", "reason", "confidence"]
    }
}


def save_classification(conn: sqlite3.Connection, ecli: str, result: Dict[str, Any]) -> None:
    conn.execute(
        """INSERT INTO classifications (ecli, is_contract_drafting_issue, reason, confidence)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(ecli) DO UPDATE SET
               is_contract_drafting_issue = excluded.is_contract_drafting_issue,
               reason = excluded.reason,
               confidence = excluded.confidence,
               classified_at = datetime('now')""",
        (
            ecli,
            1 if result["is_contract_drafting_issue"] else 0,
            result["reason"],
            result["confidence"],
        ),
    )
    conn.commit()


def classify_contract_relevance(case_row: Dict[str, Any]) -> Dict[str, Any]:
    user_prompt = f"""Classify this case.

ECLI: {case_row['ecli']}
Court: {case_row['rechtbank']}
Publication date: {case_row['publicatiedatum']}
Abstract:
{case_row['abstract']}
"""

    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[CLASSIFICATION_TOOL],
        tool_choice={"type": "tool", "name": "classify_case"}
    )

    # With tool_choice forced, the response will be a tool_use block
    tool_use = next(block for block in msg.content if block.type == "tool_use")
    data = tool_use.input

    # clamp/normalize confidence just in case
    try:
        data["confidence"] = float(data["confidence"])
    except Exception:
        data["confidence"] = 0.0
    data["confidence"] = max(0.0, min(1.0, data["confidence"]))

    return data

def get_already_classified(conn: sqlite3.Connection) -> set[str]:
    """Get all ECLIs that have already been classified."""
    rows = conn.execute("SELECT ecli FROM classifications").fetchall()
    return {row[0] for row in rows}


def read_eclis(path: str) -> List[str]:
    eclis: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            eclis.append(s)
    return eclis

# Thread-local storage for DB connections
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Get a thread-local database connection."""
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(DB_PATH)
    return _local.conn


_counter_lock = threading.Lock()
_counter = 0
_total = 0


def process_ecli(ecli: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Classify a single ECLI. Returns (ecli, result) or None if error."""
    global _counter
    conn = get_connection()

    try:
        case_row = fetch_one_row(conn, ecli)
    except ValueError as e:
        print(f"Error: {e}")
        return None

    result = classify_contract_relevance(case_row)
    save_classification(conn, ecli, result)

    with _counter_lock:
        _counter += 1
        current = _counter

    print(f"[{current}/{_total}] {ecli}: is_contract_drafting_issue={result['is_contract_drafting_issue']}")
    return (ecli, result)


MAX_WORKERS = 8


if __name__ == "__main__":
    all_eclis = read_eclis("eclis.txt")

    # Filter out already classified ECLIs upfront
    conn = sqlite3.connect(DB_PATH)
    already_classified = get_already_classified(conn)
    conn.close()

    eclis_to_process = [e for e in all_eclis if e not in already_classified]
    skipped = len(all_eclis) - len(eclis_to_process)
    _total = len(eclis_to_process)

    print(f"Total ECLIs: {len(all_eclis)}, Already classified: {skipped}, To process: {_total}")

    if _total == 0:
        print("Nothing to do.")
    else:
        classified = 0
        errors = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_ecli, ecli): ecli for ecli in eclis_to_process}

            for future in as_completed(futures):
                result = future.result()
                if result is None:
                    errors += 1
                else:
                    classified += 1

        print(f"\nDone. Classified: {classified}, Errors: {errors}, Already skipped: {skipped}")
