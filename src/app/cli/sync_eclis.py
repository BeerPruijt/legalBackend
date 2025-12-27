#!/usr/bin/env python
"""
CLI script to sync ECLIs from rechtspraak.nl to the database.

Usage:
    python -m app.cli.sync_eclis
    python -m app.cli.sync_eclis --max 100
"""
import argparse
import logging
import sys

from app.database import SessionLocal
from app.services.ecli_sync_service import sync_eclis


def main() -> int:
    """Main entry point for the ECLI sync CLI."""
    parser = argparse.ArgumentParser(
        description="Sync ECLIs from rechtspraak.nl to the database"
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="Maximum number of ECLIs to fetch (default: unlimited)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    logger.info("Starting ECLI sync...")
    if args.max:
        logger.info(f"Limiting to {args.max} ECLIs")

    try:
        db = SessionLocal()
        try:
            result = sync_eclis(db, max_results=args.max)
        finally:
            db.close()

        logger.info(
            f"Sync completed: "
            f"fetched={result.fetched_count}, "
            f"existing={result.existing_count}, "
            f"new={result.new_count}"
        )

        return 0

    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
