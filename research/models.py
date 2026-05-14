from django.db import models

from repos.models import Repository


class ResearchSession(models.Model):
    """A single research question asked against a repository."""

    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"

    class TerminationReason(models.TextChoices):
        COMPLETED = "completed"
        MAX_ITERATIONS = "max_iterations"
        MAX_TOKENS = "max_tokens"
        TIMEOUT = "timeout"
        DUPLICATE_CALLS = "duplicate_calls"
        ERROR = "error"

    repository = models.ForeignKey(
        Repository,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    question = models.TextField()
    answer = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )
    termination_reason = models.CharField(
        max_length=30,
        choices=TerminationReason.choices,
        blank=True,
    )
    error_message = models.TextField(blank=True)
    llm_provider = models.CharField(max_length=50)
    llm_model = models.CharField(max_length=100)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    iteration_count = models.IntegerField(default=0)
    celery_task_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["repository", "status"]),
            models.Index(fields=["repository", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Session {self.pk}: {self.question[:60]}"


class Finding(models.Model):
    """An agent-curated note about a file in the repository."""

    session = models.ForeignKey(
        ResearchSession,
        on_delete=models.CASCADE,
        related_name="findings",
    )
    file_path = models.CharField(max_length=512, db_index=True)
    line_start = models.IntegerField(null=True, blank=True)
    line_end = models.IntegerField(null=True, blank=True)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        location = self.file_path
        if self.line_start:
            location += f":{self.line_start}"
            if self.line_end:
                location += f"-{self.line_end}"
        return f"Finding at {location}"


class ToolCall(models.Model):
    """A single tool invocation in a research session's audit trail."""

    session = models.ForeignKey(
        ResearchSession,
        on_delete=models.CASCADE,
        related_name="tool_calls",
    )
    sequence = models.IntegerField()
    tool_name = models.CharField(max_length=100, db_index=True)
    arguments = models.JSONField()
    result_content = models.TextField()
    result_truncated = models.BooleanField(default=False)
    is_error = models.BooleanField(default=False)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField()

    class Meta:
        ordering = ["session", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "sequence"],
                name="unique_toolcall_sequence_per_session",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.tool_name}[{self.sequence}] in session {self.session_id}"
