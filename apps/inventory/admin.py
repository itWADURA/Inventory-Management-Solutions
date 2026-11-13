from django.contrib import admin

from apps.inventory.models import Location, StockBalance, StockMovement


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["name", "workspace", "is_active", "created_at"]
    search_fields = ["name", "workspace__name"]
    list_filter = ["is_active", "workspace"]


@admin.register(StockBalance)
class StockBalanceAdmin(admin.ModelAdmin):
    list_display = ["item", "location", "workspace", "quantity", "updated_at"]
    search_fields = ["item__name", "item__sku", "location__name", "workspace__name"]
    list_filter = ["workspace", "location"]
    readonly_fields = ["updated_at"]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "item",
        "location",
        "workspace",
        "movement_type",
        "quantity_delta",
        "quantity_before",
        "quantity_after",
        "user",
    ]
    search_fields = ["item__name", "item__sku", "location__name", "reason", "workspace__name"]
    list_filter = ["movement_type", "workspace", "location", "created_at"]
    readonly_fields = [
        "workspace",
        "item",
        "location",
        "movement_type",
        "quantity_delta",
        "quantity_before",
        "quantity_after",
        "unit_cost",
        "reason",
        "user",
        "created_at",
    ]

    def has_add_permission(self, request):
        # Disallow manually creating movements in Django admin - movements must follow application transactional logic
        return False

    def has_delete_permission(self, request, obj=None):
        # Disallow casual deletion of movements in Django admin to preserve immutable audit trail
        return False
