from rest_framework import serializers

from repos.models import Repository


class RepositorySerializer(serializers.ModelSerializer):
    session_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Repository
        fields = [
            "id",
            "url",
            "name",
            "session_count",
            "last_synced_at",
            "last_analyzed_at",
            "created_at",
        ]


class RepositoryNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = ["id", "url", "name"]
