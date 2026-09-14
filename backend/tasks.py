import json
import os

from celery import Celery
from celery.signals import task_failure, task_prerun, task_success
from redis import Redis

from db import NarrativeJob, SessionLocal

# WORKSHOP TODO: Install PydanticAI and Logfire, then pin the approved Claude model.
celery = Celery("narratives", broker=os.environ["CELERY_BROKER_URL"])
REDIS_URL = os.environ["CELERY_BROKER_URL"]


def update_status(job_id: int, status: str, error: str | None = None):
    with SessionLocal() as session:
        job = session.get(NarrativeJob, job_id)
        job.status = status
        job.error = error
        session.commit()
        adverse_event_id = job.adverse_event_id
    Redis.from_url(REDIS_URL).publish(
        "narrative-status",
        json.dumps(
            {
                "adverseEventId": adverse_event_id,
                "error": error,
                "status": status,
            }
        ),
    )


@celery.task
def create_narrative(job_id: int):
    # WORKSHOP TODO: Fetch the adverse event, run the PydanticAI narrative agent,
    # validate its output, persist the narrative, and allow Logfire to trace the run.
    # WORKSHOP TODO: Convert provider, guardrail, and context-limit failures into useful errors.
    raise NotImplementedError("Workshop task: run the agent and save its narrative here.")


@task_prerun.connect(sender=create_narrative)
def mark_running(task_id, task, args, **kwargs):
    update_status(args[0], "running")


@task_success.connect(sender=create_narrative)
def mark_complete(sender, result, **kwargs):
    update_status(sender.request.args[0], "complete")


@task_failure.connect(sender=create_narrative)
def mark_failed(task_id, exception, args, **kwargs):
    update_status(args[0], "failed", str(exception))
