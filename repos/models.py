from django.db import models


class Repository(models.Model):
    """A GitHub repository that the agent can research."""

    url = models.URLField(unique=True)
    name = models.CharField(max_length=255)
    clone_path = models.CharField(max_length=512, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_analyzed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_analyzed_at", "-id"]
        verbose_name_plural = "repositories"

    def __str__(self) -> str:
        return self.name or self.url
