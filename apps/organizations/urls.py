from django.urls import path

from apps.organizations import views

app_name = "organizations"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("workspaces/create/", views.workspace_create_view, name="create"),
    path("workspaces/<int:workspace_id>/switch/", views.workspace_switch_view, name="switch"),
    path("settings/", views.workspace_settings_view, name="settings"),
    path("settings/delete/", views.workspace_delete_view, name="delete"),
    path("members/", views.workspace_members_view, name="members"),
    path("members/<int:membership_id>/edit/", views.workspace_member_edit_view, name="member_edit"),
    path(
        "members/<int:membership_id>/delete/",
        views.workspace_member_delete_view,
        name="member_delete",
    ),
]
