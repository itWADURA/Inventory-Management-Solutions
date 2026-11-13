from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    WORKSPACE_CREATED = "WORKSPACE_CREATED", "Workspace Created"
    SETTINGS_UPDATED = "SETTINGS_UPDATED", "Workspace Settings Updated"
    MEMBER_ADDED = "MEMBER_ADDED", "Member Added"
    MEMBER_ROLE_CHANGED = "MEMBER_ROLE_CHANGED", "Member Role Changed"
    MEMBER_REMOVED = "MEMBER_REMOVED", "Member Removed"
    ITEM_CREATED = "ITEM_CREATED", "Item Created"
    ITEM_UPDATED = "ITEM_UPDATED", "Item Updated"
    ITEM_ARCHIVED = "ITEM_ARCHIVED", "Item Archived"
    ITEM_RESTORED = "ITEM_RESTORED", "Item Restored"
    STOCK_RECEIVED = "STOCK_RECEIVED", "Stock Received"
    STOCK_USED = "STOCK_USED", "Stock Used"
    STOCK_ADJUSTED = "STOCK_ADJUSTED", "Stock Adjusted"
    CSV_IMPORTED = "CSV_IMPORTED", "Items Imported from CSV"


class AuditEvent(models.Model):
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="audit_events",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=50, choices=AuditAction.choices)
    description = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workspace", "-created_at"]),
            models.Index(fields=["action"]),
        ]
        verbose_name = "Audit Event"
        verbose_name_plural = "Audit Events"

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.get_action_display()}: {self.description}"
