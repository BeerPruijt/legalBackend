from datetime import date, datetime, timezone

from sqlalchemy import Date, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Case(Base):
    __tablename__ = "cases"

    # Auto-increment primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ECLI identifier (unique, indexed)
    ecli: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # Feed fields
    link: Mapped[str | None] = mapped_column(String, nullable=True)

    # Document fields
    creator: Mapped[str | None] = mapped_column(String, nullable=True)
    date: Mapped[date | None] = mapped_column(Date, nullable=True)
    issued: Mapped[date | None] = mapped_column(Date, nullable=True)
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    procedure: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str | None] = mapped_column(String, nullable=True)
    inhoudsindicatie: Mapped[str | None] = mapped_column(Text, nullable=True)
    uitspraak: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_cases_ecli", "ecli"),
        Index("ix_cases_date", "date"),
        Index("ix_cases_creator", "creator"),
    )
