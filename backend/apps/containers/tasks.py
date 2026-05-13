from celery import shared_task

from apps.containers.services.gpu_allocation import cleanup_expired_gpu_reservations


@shared_task
def cleanup_expired_gpu_reservations_task():
    count = cleanup_expired_gpu_reservations()
    return f"expired gpu reservations failed={count}"
