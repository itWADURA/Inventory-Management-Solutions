from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.catalog.models import Item
from apps.inventory.models import Location, MovementType
from apps.inventory.services import record_stock_movement
from apps.organizations.models import Workspace


@pytest.mark.django_db
class TestCatalogAndLowStock:
    def test_item_sku_uniqueness_within_workspace(self):
        ws = Workspace.objects.create(name="Test Shop A", slug="shop-a")
        Item.objects.create(workspace=ws, name="Widget 1", sku="WIDGET-01")

        duplicate_item = Item(workspace=ws, name="Widget 2", sku="WIDGET-01")
        with pytest.raises(ValidationError):
            duplicate_item.clean()

    def test_item_same_sku_in_different_workspace_allowed(self):
        ws_a = Workspace.objects.create(name="Shop Alpha", slug="shop-alpha")
        ws_b = Workspace.objects.create(name="Shop Beta", slug="shop-beta")

        item_a = Item.objects.create(workspace=ws_a, name="Screw M4", sku="SCREW-M4")
        item_b = Item.objects.create(workspace=ws_b, name="Screw M4", sku="SCREW-M4")

        assert item_a.sku == item_b.sku
        assert item_a.workspace_id != item_b.workspace_id

    def test_low_stock_detection_logic(self):
        ws = Workspace.objects.create(name="Hardware Store", slug="hardware-store")
        loc = Location.objects.create(workspace=ws, name="Shelf 1")

        # Item with reorder level 10
        item = Item.objects.create(
            workspace=ws,
            name="Paint Brush 2-inch",
            reorder_level=Decimal("10.00"),
        )

        # Total quantity 0 <= 10 -> is_low_stock should be True
        assert item.total_quantity == Decimal("0.00")
        assert item.is_low_stock is True

        # Receive 15 units -> total 15 > 10 -> is_low_stock should be False
        record_stock_movement(
            workspace=ws,
            item=item,
            location=loc,
            movement_type=MovementType.RECEIVED,
            quantity=Decimal("15.00"),
            reason="Restock",
        )
        assert item.total_quantity == Decimal("15.00")
        assert item.is_low_stock is False

        # Use 5 units -> total 10 == reorder_level 10 -> is_low_stock should be True (at or below)
        record_stock_movement(
            workspace=ws,
            item=item,
            location=loc,
            movement_type=MovementType.USED,
            quantity=Decimal("5.00"),
            reason="Customer sale",
        )
        assert item.total_quantity == Decimal("10.00")
        assert item.is_low_stock is True

    def test_reorder_level_zero_does_not_trigger_low_stock(self):
        ws = Workspace.objects.create(name="No Alert Shop", slug="no-alert-shop")
        item = Item.objects.create(
            workspace=ws,
            name="Custom Made Ornament",
            reorder_level=Decimal("0.00"),
        )
        assert item.total_quantity == Decimal("0.00")
        # When reorder_level is 0, no low-stock alert should be raised
        assert item.is_low_stock is False
