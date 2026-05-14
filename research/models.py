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
