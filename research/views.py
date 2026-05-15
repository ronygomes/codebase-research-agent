from django.db.models import Prefetch, QuerySet
from rest_framework import mixins, status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from research.models import Finding, ResearchSession, ToolCall
from research.serializers import (
    CreateSessionSerializer,
    SessionAcceptedSerializer,
    SessionDetailSerializer,
    SessionListSerializer,
)
from research.tasks import run_research_session


class SessionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    def get_queryset(self) -> QuerySet[ResearchSession]:
        queryset = ResearchSession.objects.select_related("repository")

        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                Prefetch("findings", queryset=Finding.objects.order_by("created_at")),
                Prefetch("tool_calls", queryset=ToolCall.objects.order_by("sequence")),
            )

        repo_url = self.request.query_params.get("repo_url")
        if repo_url:
            queryset = queryset.filter(repository__url=repo_url.removesuffix("/"))

        return queryset

    def get_serializer_class(self) -> type[Serializer]:
        if self.action == "list":
            return SessionListSerializer
        return SessionDetailSerializer

    def create(self, request: Request) -> Response:
        serializer = CreateSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = serializer.save()
        run_research_session.delay(session.id)
        response_serializer = SessionAcceptedSerializer(session)
        return Response(response_serializer.data, status=status.HTTP_202_ACCEPTED)
