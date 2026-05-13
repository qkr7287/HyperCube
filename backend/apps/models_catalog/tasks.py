from celery import shared_task

from .prepare import cleanup_stale_model_prepare_jobs


@shared_task
def cleanup_stale_model_prepare_jobs_task():
    count = cleanup_stale_model_prepare_jobs()
    return f"stale model prepare jobs failed={count}"
