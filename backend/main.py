import os
from contextlib import contextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from psycopg.errors import ForeignKeyViolation, UniqueViolation

from tasks import create_narrative as enqueue_narrative

DATABASE_URL = os.environ["DATABASE_URL"]


@contextmanager
def database():
    with psycopg.connect(DATABASE_URL, row_factory=psycopg.rows.dict_row) as connection:
        yield connection


app = FastAPI(title="Adverse Event Narratives")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/adverse-events")
def adverse_events(page: int = 1, page_size: int = Query(default=10, le=25)):
    offset = (page - 1) * page_size
    with database() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS count FROM adverse_events")
        total = cursor.fetchone()["count"]
        cursor.execute(
            """SELECT id, usubjid AS subject_id, aedecod AS term, aesev AS severity,
                      aestdtc AS onset_date, aeout AS outcome, narrative
               FROM adverse_events ORDER BY id LIMIT %s OFFSET %s""",
            (page_size, offset),
        )
        return {"items": cursor.fetchall(), "total": total, "page": page, "page_size": page_size}


@app.get("/narrative-status")
def narrative_status(ids: list[int] = Query()):
    with database() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT DISTINCT ON (adverse_event_id) adverse_event_id, status
               FROM narrative_jobs WHERE adverse_event_id = ANY(%s)
               ORDER BY adverse_event_id, status IN ('queued', 'running') DESC, created_at DESC""",
            (ids,),
        )
        return {str(row["adverse_event_id"]): row["status"] for row in cursor.fetchall()}


@app.post("/adverse-events/{adverse_event_id}/narrative", status_code=202)
def create_narrative(adverse_event_id: int):
    try:
        with database() as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO narrative_jobs (adverse_event_id) VALUES (%s) RETURNING id",
                (adverse_event_id,),
            )
            job = cursor.fetchone()
    except ForeignKeyViolation:
        raise HTTPException(status_code=404, detail="Adverse event not found.") from None
    except UniqueViolation:
        with database() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, status FROM narrative_jobs
                   WHERE adverse_event_id = %s AND status IN ('queued', 'running')""",
                (adverse_event_id,),
            )
            job = cursor.fetchone()
        return {"job_id": job["id"], "status": job["status"]}

    enqueue_narrative.delay(job["id"])
    return {"job_id": job["id"], "status": "queued"}
