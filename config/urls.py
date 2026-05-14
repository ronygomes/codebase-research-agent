from django.urls import include, path

urlpatterns = [
    path("api/v1/", include("repos.urls")),
    path("api/v1/", include("research.urls")),
]
