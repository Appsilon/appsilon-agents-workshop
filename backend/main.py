import json
import os

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from db import AdverseEventRecord, NarrativeJob, SessionLocal
from models import AdverseEvent

REDIS_URL = os.environ["CELERY_BROKER_URL"]

app = FastAPI(title="Adverse Event Narratives")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    # Codespaces/devcontainer port forwarding serves the frontend from
    # "https://<name>-5173.<forwarding-domain>" instead of localhost.
    allow_origin_regex=r"https://.*-5173\..+",
    allow_methods=["*"],
    allow_headers=["*"],
)


def _serialize(record: AdverseEventRecord) -> dict:
    return {
        "id": record.id,
        "narrative": record.narrative,
        **AdverseEvent.model_validate(record).model_dump(mode="json"),
    }


def statuses_for(adverse_event_ids: list[int]) -> dict[str, dict]:
    with SessionLocal() as session:
        jobs = session.scalars(
            select(NarrativeJob)
            .distinct(NarrativeJob.adverse_event_id)
            .where(NarrativeJob.adverse_event_id.in_(adverse_event_ids))
            .order_by(
                NarrativeJob.adverse_event_id,
                NarrativeJob.status.in_(["queued", "running"]).desc(),
                NarrativeJob.created_at.desc(),
            )
        )
        return {
            str(job.adverse_event_id): {
                "adverse_event_id": job.adverse_event_id,
                "status": job.status,
                "error": job.error,
            }
            for job in jobs
        }


@app.get("/adverse-events")
def adverse_events(page: int = 1, page_size: int = Query(default=10, le=25)):
    offset = (page - 1) * page_size
    with SessionLocal() as session:
        total = session.scalar(select(func.count()).select_from(AdverseEventRecord))
        records = session.scalars(
            select(AdverseEventRecord).order_by(AdverseEventRecord.id).limit(page_size).offset(offset)
        )
        return {
            "items": [_serialize(record) for record in records],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


@app.get("/narrative-status/stream")
async def narrative_status_stream(
    adverse_event_ids: str = Query(alias="adverseEventIds"),
):
    visible_ids = [int(value) for value in adverse_event_ids.split(",") if value]

    async def stream():
        client = redis.from_url(REDIS_URL, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe("narrative-status")
        try:
            yield f"data: {json.dumps(statuses_for(visible_ids))}\n\n"
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                update = json.loads(message["data"])
                if update["adverseEventId"] in visible_ids:
                    yield f"data: {json.dumps(update)}\n\n"
        finally:
            await pubsub.unsubscribe("narrative-status")
            await pubsub.aclose()
            await client.aclose()

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/adverse-events/{adverse_event_id}/narrative", status_code=202)
def create_narrative(adverse_event_id: int):
    # WORKSHOP TODO: Schedule narrative generation for the given adverse event, if the adverse event exists.
    raise HTTPException(
        status_code=501,
        detail="Narrative generation is not implemented yet.",
    )
