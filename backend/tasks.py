import os

import psycopg
from celery import Celery
from celery.signals import task_failure, task_prerun, task_success

celery = Celery("narratives", broker=os.environ["CELERY_BROKER_URL"])
DATABASE_URL = os.environ["DATABASE_URL"]


def update_status(job_id: int, status: str):
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute("UPDATE narrative_jobs SET status = %s WHERE id = %s", (status, job_id))


@celery.task
def create_narrative(job_id: int):
    raise NotImplementedError("Workshop task: run the agent and save its narrative here.")


@task_prerun.connect(sender=create_narrative)
def mark_running(task_id, task, args, **kwargs):
    update_status(args[0], "running")


@task_success.connect(sender=create_narrative)
def mark_complete(sender, result, args, **kwargs):
    update_status(args[0], "complete")


@task_failure.connect(sender=create_narrative)
def mark_failed(task_id, exception, args, **kwargs):
    update_status(args[0], "failed")