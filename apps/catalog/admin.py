from django.contrib import admin

from apps.catalog.models import Category, Item, Supplier


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "workspace", "created_at"]
    search_fields = ["name", "workspace__name"]
    list_filter = ["workspace"]


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "workspace", "contact_person", "phone", "email", "is_active"]
    search_fields = ["name", "contact_person", "email", "workspace__name"]
    list_filter = ["is_active", "workspace"]


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "sku",
        "workspace",
        "category",
        "unit",
        "cost_price",
        "selling_price",
        "reorder_level",
        "is_active",
    ]
    search_fields = ["name", "sku", "barcode", "workspace__name"]
    list_filter = ["is_active", "workspace", "category", "unit"]
    readonly_fields = ["created_at", "updated_at"]
