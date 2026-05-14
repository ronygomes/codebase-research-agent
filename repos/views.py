from django.db.models import Count, QuerySet
from rest_framework import viewsets

from repos.models import Repository
from repos.serializers import RepositorySerializer


class RepositoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RepositorySerializer

    def get_queryset(self) -> QuerySet[Repository]:
        return Repository.objects.annotate(session_count=Count("sessions"))
