#!/usr/bin/env python
"""
Analyze paragraph lengths across all cases in the database.

Usage:
    python -m app.cli.analyze_sections
"""
import sys

from app.database import SessionLocal
from app.models.case import Case
from app.services.rechtspraak_fetcher import fetch_document, parse_uitspraak_structured


def get_bucket(length: int) -> str:
    if length < 500:
        return "<500"
    elif length < 1000:
        return "500-1000"
    elif length < 1500:
        return "1000-1500"
    elif length < 2000:
        return "1500-2000"
    elif length < 3000:
        return "2000-3000"
    elif length < 4000:
        return "3000-4000"
    elif length < 5000:
        return "4000-5000"
    elif length < 10000:
        return "5000-10000"
    elif length < 30000:
        return "10000-30000"
    else:
        return "30000+"


def main() -> int:
    db = SessionLocal()
    try:
        cases = db.query(Case).all()
        print(f"Found {len(cases)} cases in database\n")

        buckets = {
            "<500": 0,
            "500-1000": 0,
            "1000-1500": 0,
            "1500-2000": 0,
            "2000-3000": 0,
            "3000-4000": 0,
            "4000-5000": 0,
            "5000-10000": 0,
            "10000-30000": 0,
            "30000+": 0,
        }
        success = 0
        errors = 0

        for i, case in enumerate(cases, 1):
            try:
                doc = fetch_document(case.ecli)
                uitspraak = parse_uitspraak_structured(doc)

                for section in uitspraak.sections:
                    for para in section.paragraphs:
                        bucket = get_bucket(len(para.text))
                        buckets[bucket] += 1

                success += 1

            except Exception:
                errors += 1

            if i % 100 == 0:
                print(f"Processed {i}/{len(cases)} ({success} ok, {errors} errors)...")

        print(f"\nProcessed {len(cases)} cases: {success} success, {errors} errors\n")
        print("=" * 40)
        print("PARAGRAPH LENGTH DISTRIBUTION")
        print("=" * 40)

        total = sum(buckets.values())
        for bucket, count in buckets.items():
            pct = (count / total * 100) if total else 0
            print(f"{bucket:>12}  {count:6d}  ({pct:5.1f}%)")

        print(f"{'TOTAL':>12}  {total:6d}")

        return 0

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
