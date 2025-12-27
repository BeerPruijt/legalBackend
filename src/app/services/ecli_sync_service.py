import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.services.rechtspraak_fetcher import fetch_eclis

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of an ECLI sync operation."""

    fetched_count: int
    existing_count: int
    new_count: int


def sync_eclis(db: Session, *, max_results: int | None = None) -> SyncResult:
    """
    Fetch ECLIs from rechtspraak.nl and insert new ones into the database.

    Args:
        db: SQLAlchemy session
        max_results: Maximum number of ECLIs to fetch (None for unlimited)

    Returns:
        SyncResult with counts of fetched, existing, and new ECLIs
    """
    logger.info("Fetching ECLIs from rechtspraak.nl...")
    fetched_eclis = fetch_eclis(max_results=max_results)
    fetched_count = len(fetched_eclis)
    logger.info(f"Fetched {fetched_count} ECLIs from API")

    logger.info("Querying existing ECLIs from database...")
    existing_eclis = set(db.execute(select(Case.ecli)).scalars().all())
    existing_count = len(existing_eclis)
    logger.info(f"Found {existing_count} existing ECLIs in database")

    new_eclis = [ecli for ecli in fetched_eclis if ecli not in existing_eclis]
    new_count = len(new_eclis)

    if new_count == 0:
        logger.info("No new ECLIs to insert")
        return SyncResult(
            fetched_count=fetched_count,
            existing_count=existing_count,
            new_count=0,
        )

    logger.info(f"Inserting {new_count} new ECLIs...")
    new_cases = [Case(ecli=ecli) for ecli in new_eclis]
    db.add_all(new_cases)
    db.commit()
    logger.info(f"Successfully inserted {new_count} new ECLIs")

    return SyncResult(
        fetched_count=fetched_count,
        existing_count=existing_count,
        new_count=new_count,
    )
