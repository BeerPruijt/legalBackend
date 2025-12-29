#!/usr/bin/env python
"""
Analyze wordgate pass rate across all cases in the database.

Usage:
    python -m app.cli.analyze_wordgate
"""
import sys

from app.database import SessionLocal
from app.models.case import Case
from app.services.rechtspraak_fetcher import (
    fetch_document,
    parse_uitspraak_structured,
    ensure_min_paragraph_length,
)
from app.services.wordgate_service import check_words

# Hardcoded configuration
TARGET_WORDS = [
    "arbeidscontract",
    "arbeidsovereenkomst",
    "dienstverband",
    "contract van arbeid",
    "werkovereenkomst",
    "looptijd",
    "proeftijd",
    "opzegtermijn",
    "salaris",
    "arbeidsvoorwaarden",
    "functieomschrijving",
    "werkuren",
    "cao",
    "concurrentiebeding",
    "vast contract",
    "ontslag",
    "tijdelijk contract",
    "onbepaalde tijd",
    "arbeidsduur",
    "vakantiedagen",
    "ziekteverzuim",
    "loonbetaling",
    "beding",
    "rechtspositie"
]
MIN_PARAGRAPH_LENGTH = 500
MAX_PARAGRAPH_LENGTH = 5000


def main() -> int:
    db = SessionLocal()
    try:
        cases = db.query(Case).all()
        print(f"Found {len(cases)} cases in database\n")

        total_paragraphs = 0
        passed_paragraphs = 0
        success = 0
        errors = 0

        for i, case in enumerate(cases, 1):
            try:
                doc = fetch_document(case.ecli)
                uitspraak = parse_uitspraak_structured(doc)

                # Flatten all paragraphs from all sections
                all_paragraphs = []
                for section in uitspraak.sections:
                    all_paragraphs.extend(section.paragraphs)

                # Apply minimum length merging
                merged = ensure_min_paragraph_length(
                    all_paragraphs,
                    min_length=MIN_PARAGRAPH_LENGTH,
                    max_length=MAX_PARAGRAPH_LENGTH,
                )

                # Check each paragraph against wordgate
                for para in merged:
                    result = check_words(para.text, TARGET_WORDS)
                    total_paragraphs += 1
                    if result.matched:
                        passed_paragraphs += 1

                success += 1

            except Exception:
                errors += 1

            if i % 100 == 0:
                print(f"Processed {i}/{len(cases)} ({success} ok, {errors} errors)...")

        # Output results
        print(f"\nProcessed {len(cases)} cases: {success} success, {errors} errors\n")
        print("=" * 40)
        print("WORDGATE ANALYSIS RESULTS")
        print("=" * 40)
        print(f"Target words: {TARGET_WORDS}")
        print(f"Min paragraph length: {MIN_PARAGRAPH_LENGTH}")
        print(f"Max paragraph length: {MAX_PARAGRAPH_LENGTH}")
        print("-" * 40)
        print(f"Total paragraphs: {total_paragraphs}")
        print(f"Passed wordgate: {passed_paragraphs}")
        pct = (passed_paragraphs / total_paragraphs * 100) if total_paragraphs else 0
        print(f"Pass rate: {pct:.1f}%")

        return 0

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
