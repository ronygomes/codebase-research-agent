from typing import Any

from celery import shared_task
from django.utils import timezone

from research.models import ResearchSession


@shared_task(bind=True, soft_time_limit=270, time_limit=300)
def run_research_session(self: Any, session_id: int) -> None:
    session = ResearchSession.objects.get(id=session_id)
    session.celery_task_id = self.request.id
    session.status = ResearchSession.Status.RUNNING
    session.started_at = timezone.now()
    session.save(update_fields=["celery_task_id", "status", "started_at"])
