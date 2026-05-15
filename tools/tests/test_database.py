import json
from pathlib import Path
from typing import Any

import pytest

from repos.models import Repository
from research.models import Finding, ResearchSession
from tools.base import ToolContext
from tools.database import (
    GetPreviousFindingsTool,
    ListPastSessionsTool,
    SaveFindingTool,
)


@pytest.fixture
def session(repository: Repository) -> ResearchSession:
    return ResearchSession.objects.create(
        repository=repository,
        question="What does main.py do?",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
    )


def _ctx(session: ResearchSession, tmp_path: Path) -> ToolContext:
    return ToolContext(
        session_id=session.id,
        repository_id=session.repository_id,
        repo_path=tmp_path,
    )


@pytest.mark.django_db
def test_save_finding_persists_to_database(
    session: ResearchSession, tmp_path: Any
) -> None:
    tool = SaveFindingTool()

    result = tool.execute(
        _ctx(session, tmp_path),
        SaveFindingTool.args_model(
            file_path="main.py", note="entry point", line_start=1, line_end=10
        ),
    )

    assert Finding.objects.count() == 1
    finding = Finding.objects.get()
    assert finding.session_id == session.id
    assert finding.file_path == "main.py"
    assert finding.line_start == 1
    assert finding.line_end == 10

    data = json.loads(result)
    assert data["saved"] is True
    assert data["finding_id"] == finding.id
    assert "main.py:1-10" in data["message"]


@pytest.mark.django_db
def test_get_previous_findings_returns_only_completed_past_sessions(
    session: ResearchSession, tmp_path: Any
) -> None:
    completed = ResearchSession.objects.create(
        repository=session.repository,
        question="prior",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
        status=ResearchSession.Status.COMPLETED,
    )
    Finding.objects.create(session=completed, file_path="x.py", note="from completed")
    failed = ResearchSession.objects.create(
        repository=session.repository,
        question="failed",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
        status=ResearchSession.Status.FAILED,
    )
    Finding.objects.create(session=failed, file_path="y.py", note="from failed")

    result = GetPreviousFindingsTool().execute(
        _ctx(session, tmp_path),
        GetPreviousFindingsTool.args_model(repo_url=session.repository.url),
    )

    data = json.loads(result)
    assert data["finding_count"] == 1
    assert data["findings"][0]["note"] == "from completed"


@pytest.mark.django_db
def test_get_previous_findings_excludes_current_session(
    session: ResearchSession, tmp_path: Any
) -> None:
    Finding.objects.create(session=session, file_path="x.py", note="from current")

    result = GetPreviousFindingsTool().execute(
        _ctx(session, tmp_path),
        GetPreviousFindingsTool.args_model(repo_url=session.repository.url),
    )

    assert json.loads(result)["finding_count"] == 0


@pytest.mark.django_db
def test_get_previous_findings_rejects_mismatched_repo_url(
    session: ResearchSession, tmp_path: Any
) -> None:
    with pytest.raises(ValueError, match="does not match"):
        GetPreviousFindingsTool().execute(
            _ctx(session, tmp_path),
            GetPreviousFindingsTool.args_model(repo_url="https://github.com/other/repo"),
        )


@pytest.mark.django_db
def test_list_past_sessions_includes_completed_and_failed(
    session: ResearchSession, tmp_path: Any
) -> None:
    ResearchSession.objects.create(
        repository=session.repository,
        question="completed q",
        answer="completed answer",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
        status=ResearchSession.Status.COMPLETED,
    )
    ResearchSession.objects.create(
        repository=session.repository,
        question="failed q",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
        status=ResearchSession.Status.FAILED,
    )

    result = ListPastSessionsTool().execute(
        _ctx(session, tmp_path),
        ListPastSessionsTool.args_model(repo_url=session.repository.url),
    )

    data = json.loads(result)
    assert data["session_count"] == 2


@pytest.mark.django_db
def test_list_past_sessions_includes_finding_count_per_session(
    session: ResearchSession, tmp_path: Any
) -> None:
    other = ResearchSession.objects.create(
        repository=session.repository,
        question="other",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
        status=ResearchSession.Status.COMPLETED,
    )
    Finding.objects.create(session=other, file_path="a.py", note="1")
    Finding.objects.create(session=other, file_path="b.py", note="2")

    result = ListPastSessionsTool().execute(
        _ctx(session, tmp_path),
        ListPastSessionsTool.args_model(repo_url=session.repository.url),
    )

    sessions = json.loads(result)["sessions"]
    assert sessions[0]["finding_count"] == 2
