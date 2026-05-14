from rest_framework.routers import DefaultRouter

from repos.views import RepositoryViewSet

router = DefaultRouter()
router.register(r"repos", RepositoryViewSet, basename="repository")

urlpatterns = router.urls
