from django.urls import path
from .views import ProjectListView, AccountView, ProjectRequestView

urlpatterns = [
    path("projects/", ProjectListView.as_view(), name="project-list"),
    path("account/", AccountView.as_view(), name="account"),
    path("project-requests/", ProjectRequestView.as_view(), name="project-requests"),
]
