from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Location(models.Model):
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="locations",
    )
    name = models.CharField(
        max_length=100, help_text="Location name (e.g. Main location, Front Shelf, Warehouse B)."
    )
    notes = models.TextField(
        blank=True, help_text="Notes on where this location is or what is stored."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"],
                name="unique_workspace_location_name",
            )
        ]
        verbose_name = "Stock Location"
        verbose_name_plural = "Stock Locations"

    def __str__(self):
        return self.name


class StockBalance(models.Model):
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="stock_balances",
    )
    item = models.ForeignKey(
        "catalog.Item",
        on_delete=models.CASCADE,
        related_name="stock_balances",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="stock_balances",
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Current physical on-hand quantity.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["item", "location"],
                name="unique_item_location_balance",
            )
        ]
        indexes = [
            models.Index(fields=["workspace", "quantity"]),
        ]
        verbose_name = "Stock Balance"
        verbose_name_plural = "Stock Balances"

    def __str__(self):
        return f"{self.item.name} @ {self.location.name}: {self.quantity}"


class MovementType(models.TextChoices):
    RECEIVED = "RECEIVED", "Stock Received (+)"
    USED = "USED", "Stock Used / Sold (-)"
    ADJUSTMENT = "ADJUSTMENT", "Count Adjustment (+/-)"
    OPENING_BALANCE = "OPENING_BALANCE", "Opening Balance (+)"


class StockMovement(models.Model):
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="stock_movements",
    )
    item = models.ForeignKey(
        "catalog.Item",
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
    )
    quantity_delta = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Positive for additions, negative for reductions.",
    )
    quantity_before = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="On-hand quantity immediately before movement.",
    )
    quantity_after = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="On-hand quantity immediately after movement.",
    )
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Unit cost at the time of movement, if specified.",
    )
    reason = models.TextField(
        help_text="Reason, invoice reference, or explanation for this stock movement.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_stock_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workspace", "-created_at"]),
            models.Index(fields=["item", "-created_at"]),
            models.Index(fields=["movement_type"]),
        ]
        verbose_name = "Stock Movement"
        verbose_name_plural = "Stock Movements"

    def __str__(self):
        sign = "+" if self.quantity_delta > 0 else ""
        return f"{self.created_at:%Y-%m-%d %H:%M} | {self.item.name} | {sign}{self.quantity_delta} ({self.get_movement_type_display()})"
