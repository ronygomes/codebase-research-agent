from rest_framework.routers import DefaultRouter

from research.views import SessionViewSet

router = DefaultRouter()
router.register(r"sessions", SessionViewSet, basename="session")

urlpatterns = router.urls
