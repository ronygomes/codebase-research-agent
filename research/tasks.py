from typing import Any

from celery import shared_task
from django.utils import timezone

from repos.git_client import get_git_client
from repos.services import ensure_cloned
from research.models import ResearchSession


@shared_task(bind=True, soft_time_limit=270, time_limit=300)
def run_research_session(self: Any, session_id: int) -> None:
    session = ResearchSession.objects.select_related("repository").get(id=session_id)
    session.celery_task_id = self.request.id
    session.status = ResearchSession.Status.RUNNING
    session.started_at = timezone.now()
    session.save(update_fields=["celery_task_id", "status", "started_at"])

    git_client = get_git_client()
    ensure_cloned(session.repository, git_client)
