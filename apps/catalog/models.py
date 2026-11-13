from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum


class Category(models.Model):
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="categories",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"],
                name="unique_workspace_category_name",
            )
        ]
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Supplier(models.Model):
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="suppliers",
    )
    name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Supplier"
        verbose_name_plural = "Suppliers"

    def __str__(self):
        return self.name


class Item(models.Model):
    STANDARD_UNITS = [
        ("piece", "Piece (pc)"),
        ("box", "Box"),
        ("pack", "Pack"),
        ("kg", "Kilogram (kg)"),
        ("g", "Gram (g)"),
        ("litre", "Litre (L)"),
        ("ml", "Millilitre (ml)"),
        ("meter", "Meter (m)"),
        ("set", "Set"),
        ("pair", "Pair"),
        ("roll", "Roll"),
        ("bottle", "Bottle"),
        ("can", "Can"),
        ("other", "Other"),
    ]

    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="items",
    )
    name = models.CharField(max_length=200, help_text="Item title or product name.")
    sku = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Item code (SKU). Unique within this workspace when provided.",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    unit = models.CharField(
        max_length=50,
        choices=STANDARD_UNITS,
        default="piece",
        help_text="Unit of measurement.",
    )
    description = models.TextField(blank=True, help_text="Detailed item notes or description.")
    barcode = models.CharField(max_length=100, blank=True, help_text="EAN/UPC or barcode string.")
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Estimated purchase or cost price per unit.",
    )
    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Default sales price per unit.",
    )
    reorder_level = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Alert when stock falls at or below this level (0 means no alert).",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive items are archived and hidden from daily entry forms.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["workspace", "name"]),
            models.Index(fields=["workspace", "sku"]),
            models.Index(fields=["workspace", "barcode"]),
            models.Index(fields=["workspace", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "sku"],
                condition=models.Q(sku__isnull=False) & ~models.Q(sku=""),
                name="unique_workspace_item_sku",
            )
        ]
        verbose_name = "Item"
        verbose_name_plural = "Items"

    def clean(self):
        super().clean()
        if self.sku:
            self.sku = self.sku.strip()
            # Workspace uniqueness check
            duplicate = (
                Item.objects.filter(workspace=self.workspace, sku__iexact=self.sku)
                .exclude(pk=self.pk)
                .exists()
            )
            if duplicate:
                raise ValidationError(
                    {"sku": "An item with this item code (SKU) already exists in this workspace."}
                )

    def __str__(self):
        if self.sku:
            return f"{self.name} [{self.sku}]"
        return self.name

    @property
    def total_quantity(self):
        res = self.stock_balances.aggregate(total=Sum("quantity"))["total"]
        return res if res is not None else Decimal("0.00")

    @property
    def is_low_stock(self):
        if self.reorder_level <= Decimal("0.00"):
            return False
        return self.total_quantity <= self.reorder_level
