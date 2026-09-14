"""SQLAlchemy engine, session, and ORM models for the two tables in db/init.sql.

Column names on AdverseEventRecord are the same human-readable names as
models.AdverseEvent (mapped_column aliases each one to its actual, terser
SDTM column, e.g. `term` -> `aedecod`), so a row converts with
AdverseEvent.model_validate(record).
"""

import os
from datetime import date, datetime

from sqlalchemy import ForeignKey, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg://", 1)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class AdverseEventRecord(Base):
    __tablename__ = "adverse_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    study_id: Mapped[str] = mapped_column("studyid")
    domain: Mapped[str]
    subject_id: Mapped[str] = mapped_column("usubjid")
    sequence: Mapped[int] = mapped_column("aeseq")
    sponsor_id: Mapped[str] = mapped_column("aespid")
    reported_term: Mapped[str] = mapped_column("aeterm")
    modified_term: Mapped[str | None] = mapped_column("aemodify")
    term: Mapped[str] = mapped_column("aedecod")
    body_system: Mapped[str] = mapped_column("aebodsys")
    system_organ_class: Mapped[str] = mapped_column("aesoc")
    location: Mapped[str | None] = mapped_column("aeloc")
    severity: Mapped[str] = mapped_column("aesev")
    serious: Mapped[str] = mapped_column("aeser")
    category: Mapped[str | None] = mapped_column("aescat")
    subcategory: Mapped[str | None] = mapped_column("aescat2")
    onset_date: Mapped[date] = mapped_column("aestdtc")
    end_date: Mapped[date | None] = mapped_column("aeendtc")
    ongoing: Mapped[str] = mapped_column("aeongo")
    relationship: Mapped[str] = mapped_column("aerel")
    action_taken: Mapped[str] = mapped_column("aeacn")
    outcome: Mapped[str] = mapped_column("aeout")
    caused_death: Mapped[str] = mapped_column("aedth")
    hospitalization: Mapped[str] = mapped_column("aehosp")
    congenital_anomaly: Mapped[str] = mapped_column("aecong")
    narrative: Mapped[str | None]


class NarrativeJob(Base):
    __tablename__ = "narrative_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    adverse_event_id: Mapped[int] = mapped_column(ForeignKey("adverse_events.id"))
    status: Mapped[str] = mapped_column(default="queued")
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    error: Mapped[str | None]

    adverse_event: Mapped[AdverseEventRecord] = relationship()
