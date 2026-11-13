from django.conf import settings
from django.db import models


class Role(models.TextChoices):
    OWNER = "OWNER", "Owner"
    MANAGER = "MANAGER", "Manager"
    STAFF = "STAFF", "Staff"


class Workspace(models.Model):
    BUSINESS_TYPES = [
        ("retail", "Retail Shop"),
        ("workshop", "Workshop / Maker"),
        ("cafe", "Café / Restaurant"),
        ("office", "Office / Supplies"),
        ("school", "School / Educational"),
        ("services", "Service / Maintenance"),
        ("other", "Other Small Business"),
    ]

    name = models.CharField(max_length=150, help_text="Business or organization name.")
    slug = models.SlugField(max_length=160, unique=True)
    business_type = models.CharField(
        max_length=50,
        choices=BUSINESS_TYPES,
        blank=True,
        default="retail",
        help_text="Type of business or activity.",
    )
    currency = models.CharField(
        max_length=3,
        default="USD",
        help_text="Standard 3-letter ISO 4217 currency code (e.g. USD, EUR, GBP, LKR).",
    )
    timezone = models.CharField(
        max_length=64,
        default="UTC",
        help_text="Timezone for records and reporting (e.g. UTC, America/New_York).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Workspace"
        verbose_name_plural = "Workspaces"

    def __str__(self):
        return self.name


class Membership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STAFF,
        help_text="Role within this workspace.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "workspace"],
                name="unique_user_workspace_membership",
            )
        ]
        ordering = ["created_at"]
        verbose_name = "Workspace Membership"
        verbose_name_plural = "Workspace Memberships"

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()}) @ {self.workspace.name}"

    @property
    def is_owner(self):
        return self.role == Role.OWNER

    @property
    def is_manager_or_higher(self):
        return self.role in (Role.OWNER, Role.MANAGER)
