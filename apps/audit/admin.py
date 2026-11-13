from django.contrib import admin

from apps.audit.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["created_at", "workspace", "action", "description", "user", "ip_address"]
    list_filter = ["action", "workspace", "created_at"]
    search_fields = ["description", "workspace__name", "user__username", "ip_address"]
    readonly_fields = [
        "workspace",
        "user",
        "action",
        "description",
        "ip_address",
        "metadata",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
