from typing import Any

from celery import shared_task

from agent.core import Agent
from llm.factory import get_llm_provider
from repos.git_client import get_git_client
from repos.services import ensure_cloned
from research.models import ResearchSession
from tools.factory import build_default_registry


@shared_task(bind=True, soft_time_limit=270, time_limit=300)
def run_research_session(self: Any, session_id: int) -> None:
    session = ResearchSession.objects.select_related("repository").get(id=session_id)
    session.celery_task_id = self.request.id
    session.save(update_fields=["celery_task_id"])

    git_client = get_git_client()
    repo_path = ensure_cloned(session.repository, git_client)

    Agent(
        session=session,
        llm_provider=get_llm_provider(),
        tool_registry=build_default_registry(),
        repo_path=repo_path,
    ).run()
