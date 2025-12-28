import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.services.rechtspraak_fetcher import CaseRecord, fetch_cases

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a cases sync operation."""

    fetched_count: int
    existing_count: int
    new_count: int


def _parse_date(value: str | None) -> date | None:
    """Parse a date string (YYYY-MM-DD) to a date object."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        logger.warning(f"Could not parse date: {value}")
        return None


def _record_to_case(record: CaseRecord) -> Case:
    """Convert a CaseRecord dict to a Case model instance."""
    return Case(
        ecli=record.get("ecli"),
        link=record.get("link"),
        creator=record.get("creator"),
        date=_parse_date(record.get("date")),
        issued=_parse_date(record.get("issued")),
        subject=record.get("subject"),
        procedure=record.get("procedure"),
        type=record.get("type"),
        inhoudsindicatie=record.get("inhoudsindicatie"),
        uitspraak=record.get("uitspraak"),
    )


def sync_cases(db: Session, *, max_results: int | None = None) -> SyncResult:
    """
    Fetch cases from rechtspraak.nl and insert new ones into the database.

    Args:
        db: SQLAlchemy session
        max_results: Maximum number of cases to fetch (None for unlimited)

    Returns:
        SyncResult with counts of fetched, existing, and new cases
    """
    logger.info("Fetching cases from rechtspraak.nl...")
    fetched_records = fetch_cases(max_results=max_results)
    fetched_count = len(fetched_records)
    logger.info(f"Fetched {fetched_count} cases from API")

    logger.info("Querying existing ECLIs from database...")
    existing_eclis = set(db.execute(select(Case.ecli)).scalars().all())
    existing_count = len(existing_eclis)
    logger.info(f"Found {existing_count} existing cases in database")

    new_records = [r for r in fetched_records if r.get("ecli") not in existing_eclis]
    new_count = len(new_records)

    if new_count == 0:
        logger.info("No new cases to insert")
        return SyncResult(
            fetched_count=fetched_count,
            existing_count=existing_count,
            new_count=0,
        )

    logger.info(f"Inserting {new_count} new cases...")
    new_cases = [_record_to_case(record) for record in new_records]
    db.add_all(new_cases)
    db.commit()
    logger.info(f"Successfully inserted {new_count} new cases")

    return SyncResult(
        fetched_count=fetched_count,
        existing_count=existing_count,
        new_count=new_count,
    )
