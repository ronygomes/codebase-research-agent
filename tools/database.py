import json
from typing import Any, ClassVar

from django.db.models import Count
from pydantic import BaseModel, Field

from research.models import Finding, ResearchSession
from tools.base import Tool, ToolContext


def _verify_repo_url(ctx: ToolContext, repo_url: str) -> str:
    normalized = repo_url.removesuffix("/")
    session = ResearchSession.objects.select_related("repository").get(id=ctx.session_id)
    if session.repository.url.removesuffix("/") != normalized:
        raise ValueError("repo_url does not match current session's repository")
    return normalized


class SaveFindingArgs(BaseModel):
    file_path: str = Field(description="File path within the repo this finding is about")
    note: str = Field(max_length=2000, description="The discovery to persist")
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)


class SaveFindingTool(Tool):
    name: ClassVar[str] = "save_finding"
    description: ClassVar[str] = (
        "Persist a noteworthy discovery to the database. Future sessions on this "
        "repository can read your findings via get_previous_findings."
    )
    args_model: ClassVar[type[BaseModel]] = SaveFindingArgs

    def execute(self, ctx: ToolContext, args: SaveFindingArgs) -> str:
        finding = Finding.objects.create(
            session_id=ctx.session_id,
            file_path=args.file_path,
            line_start=args.line_start,
            line_end=args.line_end,
            note=args.note,
        )
        location = args.file_path
        if args.line_start:
            location += f":{args.line_start}"
            if args.line_end:
                location += f"-{args.line_end}"
        return json.dumps(
            {
                "saved": True,
                "finding_id": finding.id,
                "message": f"Finding saved: {location}",
            }
        )


class GetPreviousFindingsArgs(BaseModel):
    repo_url: str = Field(description="The repository URL (must match current session's repo)")


class GetPreviousFindingsTool(Tool):
    name: ClassVar[str] = "get_previous_findings"
    description: ClassVar[str] = (
        "Read findings from past completed research sessions on this repository. "
        "Call this BEFORE exploring to build on prior research."
    )
    args_model: ClassVar[type[BaseModel]] = GetPreviousFindingsArgs

    MAX_RESULTS: ClassVar[int] = 50

    def execute(self, ctx: ToolContext, args: GetPreviousFindingsArgs) -> str:
        normalized = _verify_repo_url(ctx, args.repo_url)

        findings = list(
            Finding.objects.filter(
                session__repository__url=normalized,
                session__status=ResearchSession.Status.COMPLETED,
            )
            .exclude(session_id=ctx.session_id)
            .select_related("session")
            .order_by("-created_at")[: self.MAX_RESULTS]
        )

        return json.dumps(
            {
                "repo_url": args.repo_url,
                "finding_count": len(findings),
                "findings": [
                    {
                        "file_path": f.file_path,
                        "line_start": f.line_start,
                        "line_end": f.line_end,
                        "note": f.note,
                        "from_session": (
                            f"Question: {f.session.question[:80]} (session {f.session_id})"
                        ),
                    }
                    for f in findings
                ],
            }
        )


class ListPastSessionsArgs(BaseModel):
    repo_url: str = Field(description="The repository URL (must match current session's repo)")


class ListPastSessionsTool(Tool):
    name: ClassVar[str] = "list_past_sessions"
    description: ClassVar[str] = (
        "List prior research sessions on this repository, including their questions, "
        "answer previews, statuses, and finding counts."
    )
    args_model: ClassVar[type[BaseModel]] = ListPastSessionsArgs

    MAX_RESULTS: ClassVar[int] = 20

    def execute(self, ctx: ToolContext, args: ListPastSessionsArgs) -> str:
        normalized = _verify_repo_url(ctx, args.repo_url)

        sessions = list(
            ResearchSession.objects.filter(
                repository__url=normalized,
                status__in=[
                    ResearchSession.Status.COMPLETED,
                    ResearchSession.Status.FAILED,
                ],
            )
            .exclude(id=ctx.session_id)
            .annotate(finding_count=Count("findings"))
            .order_by("-created_at")[: self.MAX_RESULTS]
        )

        return json.dumps(
            {
                "repo_url": args.repo_url,
                "session_count": len(sessions),
                "sessions": [
                    {
                        "id": s.id,
                        "question": s.question,
                        "answer_preview": s.answer[:200],
                        "status": s.status,
                        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                        "finding_count": s.finding_count,
                    }
                    for s in sessions
                ],
            }
        )
