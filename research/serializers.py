import re
from typing import Any

from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from repos.models import Repository
from repos.serializers import RepositoryNestedSerializer
from research.models import Finding, ResearchSession, ToolCall

GITHUB_URL_PATTERN = re.compile(r"^https?://github\.com/[\w.-]+/[\w.-]+/?$")


def _derive_repo_name(url: str) -> str:
    parts = url.removesuffix("/").split("/")
    return f"{parts[-2]}/{parts[-1]}"


class CreateSessionSerializer(serializers.Serializer):
    repo_url = serializers.CharField()
    question = serializers.CharField(max_length=2000)

    def validate_repo_url(self, value: str) -> str:
        if not GITHUB_URL_PATTERN.match(value):
            raise serializers.ValidationError(
                "Must be a valid GitHub URL like https://github.com/owner/repo"
            )
        return value.removesuffix("/")

    def create(self, validated_data: dict[str, Any]) -> ResearchSession:
        repo_url = validated_data["repo_url"]
        question = validated_data["question"]

        with transaction.atomic():
            repository, _ = Repository.objects.get_or_create(
                url=repo_url,
                defaults={"name": _derive_repo_name(repo_url)},
            )
            session = ResearchSession.objects.create(
                repository=repository,
                question=question,
                llm_provider=settings.LLM_PROVIDER,
                llm_model=settings.LLM_MODEL,
            )
        return session


class SessionAcceptedSerializer(serializers.ModelSerializer):
    repo_url = serializers.CharField(source="repository.url", read_only=True)
    polling_url = serializers.SerializerMethodField()

    class Meta:
        model = ResearchSession
        fields = ["id", "status", "repo_url", "question", "polling_url", "created_at"]

    def get_polling_url(self, obj: ResearchSession) -> str:
        return f"/api/v1/sessions/{obj.id}/"


class SessionListSerializer(serializers.ModelSerializer):
    answer_preview = serializers.SerializerMethodField()

    class Meta:
        model = ResearchSession
        fields = [
            "id",
            "question",
            "status",
            "answer_preview",
            "termination_reason",
            "created_at",
            "completed_at",
        ]

    def get_answer_preview(self, obj: ResearchSession) -> str:
        return obj.answer[:200]


class FindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Finding
        fields = ["id", "file_path", "line_start", "line_end", "note", "created_at"]


class ToolCallSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolCall
        fields = [
            "id",
            "sequence",
            "tool_name",
            "arguments",
            "result_content",
            "result_truncated",
            "is_error",
            "started_at",
            "completed_at",
        ]


class SessionDetailSerializer(serializers.ModelSerializer):
    repository = RepositoryNestedSerializer(read_only=True)
    findings = FindingSerializer(many=True, read_only=True)
    tool_calls = ToolCallSerializer(many=True, read_only=True)

    class Meta:
        model = ResearchSession
        fields = [
            "id",
            "repository",
            "question",
            "answer",
            "status",
            "termination_reason",
            "error_message",
            "llm_provider",
            "llm_model",
            "input_tokens",
            "output_tokens",
            "iteration_count",
            "created_at",
            "started_at",
            "completed_at",
            "findings",
            "tool_calls",
        ]
