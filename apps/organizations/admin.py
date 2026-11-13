from django.contrib import admin

from apps.organizations.models import Membership, Workspace


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "business_type", "currency", "timezone", "created_at"]
    search_fields = ["name", "slug"]
    list_filter = ["business_type", "currency"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "workspace", "role", "created_at"]
    list_filter = ["role", "workspace"]
    search_fields = ["user__username", "user__email", "workspace__name"]
