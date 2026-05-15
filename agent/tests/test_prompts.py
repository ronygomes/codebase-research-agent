import pytest

from agent.prompts import (
    FALLBACK_USER_MESSAGE,
    SYSTEM_PROMPT,
    build_first_user_message,
)
from repos.models import Repository
from research.models import ResearchSession


def test_system_prompt_is_non_empty() -> None:
    assert SYSTEM_PROMPT
    assert "research agent" in SYSTEM_PROMPT.lower()


def test_fallback_user_message_is_non_empty() -> None:
    assert FALLBACK_USER_MESSAGE
    assert "exploration limit" in FALLBACK_USER_MESSAGE.lower()


@pytest.mark.django_db
def test_first_user_message_excludes_hint_when_no_prior_sessions(
    repository: Repository,
) -> None:
    session = ResearchSession.objects.create(
        repository=repository,
        question="What is X?",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
    )

    msg = build_first_user_message(session)

    assert "What is X?" in msg
    assert repository.url in msg
    assert "prior completed" not in msg


@pytest.mark.django_db
def test_first_user_message_includes_hint_when_prior_completed_sessions_exist(
    repository: Repository,
) -> None:
    ResearchSession.objects.create(
        repository=repository,
        question="prior",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
        status=ResearchSession.Status.COMPLETED,
    )
    current = ResearchSession.objects.create(
        repository=repository,
        question="current",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
    )

    msg = build_first_user_message(current)

    assert "1 prior completed" in msg
    assert "get_previous_findings" in msg
