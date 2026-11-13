from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import Item
from apps.inventory.models import Location, MovementType, StockBalance
from apps.inventory.services import StockMovementServiceError, record_stock_movement
from apps.organizations.models import Membership, Role, Workspace

User = get_user_model()


@pytest.mark.django_db
class TestStockMovementsAndIntegrity:
    @pytest.fixture
    def setup_data(self):
        user = User.objects.create_user(username="inv_manager", password="password123!")
        ws = Workspace.objects.create(name="Central Depot", slug="central-depot")
        Membership.objects.create(user=user, workspace=ws, role=Role.MANAGER)
        location = Location.objects.create(workspace=ws, name="Main Warehouse")
        item = Item.objects.create(
            workspace=ws,
            name="Industrial Valve 2-inch",
            sku="VALVE-02",
            unit="piece",
            reorder_level=Decimal("10.00"),
        )
        return {"user": user, "workspace": ws, "location": location, "item": item}

    def test_stock_receipt_increases_balance_and_creates_movement(self, setup_data):
        ws = setup_data["workspace"]
        item = setup_data["item"]
        loc = setup_data["location"]
        user = setup_data["user"]

        movement = record_stock_movement(
            workspace=ws,
            item=item,
            location=loc,
            movement_type=MovementType.RECEIVED,
            quantity=Decimal("50.00"),
            reason="PO #9921 arrived from supplier",
            user=user,
            unit_cost=Decimal("15.75"),
        )

        assert movement.quantity_delta == Decimal("50.00")
        assert movement.quantity_before == Decimal("0.00")
        assert movement.quantity_after == Decimal("50.00")

        # Verify balance row
        balance = StockBalance.objects.get(item=item, location=loc)
        assert balance.quantity == Decimal("50.00")
        assert item.total_quantity == Decimal("50.00")

    def test_stock_usage_decreases_balance(self, setup_data):
        ws = setup_data["workspace"]
        item = setup_data["item"]
        loc = setup_data["location"]
        user = setup_data["user"]

        # First receive 20
        record_stock_movement(
            workspace=ws,
            item=item,
            location=loc,
            movement_type=MovementType.RECEIVED,
            quantity=Decimal("20.00"),
            reason="Initial delivery",
            user=user,
        )

        # Now use 7
        movement = record_stock_movement(
            workspace=ws,
            item=item,
            location=loc,
            movement_type=MovementType.USED,
            quantity=Decimal("7.00"),
            reason="Issued for repair job #402",
            user=user,
        )

        assert movement.quantity_delta == Decimal("-7.00")
        assert movement.quantity_before == Decimal("20.00")
        assert movement.quantity_after == Decimal("13.00")

        balance = StockBalance.objects.get(item=item, location=loc)
        assert balance.quantity == Decimal("13.00")

    def test_stock_usage_prevents_negative_balance(self, setup_data):
        ws = setup_data["workspace"]
        item = setup_data["item"]
        loc = setup_data["location"]
        user = setup_data["user"]

        # Only 5 on hand
        record_stock_movement(
            workspace=ws,
            item=item,
            location=loc,
            movement_type=MovementType.RECEIVED,
            quantity=Decimal("5.00"),
            reason="Delivery",
            user=user,
        )

        # Try to use 6 -> should raise StockMovementServiceError
        with pytest.raises(StockMovementServiceError, match="Insufficient stock on hand"):
            record_stock_movement(
                workspace=ws,
                item=item,
                location=loc,
                movement_type=MovementType.USED,
                quantity=Decimal("6.00"),
                reason="Attempting to over-consume",
                user=user,
            )

        # Balance remains 5
        balance = StockBalance.objects.get(item=item, location=loc)
        assert balance.quantity == Decimal("5.00")

    def test_stock_adjustment_records_audit_trail_and_delta(self, setup_data):
        ws = setup_data["workspace"]
        item = setup_data["item"]
        loc = setup_data["location"]
        user = setup_data["user"]

        # Current stock is 30
        record_stock_movement(
            workspace=ws,
            item=item,
            location=loc,
            movement_type=MovementType.RECEIVED,
            quantity=Decimal("30.00"),
            reason="Delivery",
            user=user,
        )

        # Physical count reveals 27 (3 lost/damaged)
        adj_movement = record_stock_movement(
            workspace=ws,
            item=item,
            location=loc,
            movement_type=MovementType.ADJUSTMENT,
            quantity=Decimal("27.00"),
            reason="Annual audit count found 3 damaged units",
            user=user,
        )

        assert adj_movement.quantity_before == Decimal("30.00")
        assert adj_movement.quantity_after == Decimal("27.00")
        assert adj_movement.quantity_delta == Decimal("-3.00")

        balance = StockBalance.objects.get(item=item, location=loc)
        assert balance.quantity == Decimal("27.00")

    def test_cross_workspace_movement_rejection(self, setup_data):
        ws_other = Workspace.objects.create(name="Other Workspace", slug="other-ws")
        loc_other = Location.objects.create(workspace=ws_other, name="Other Location")

        # Attempt movement using item from ws and location from ws_other
        with pytest.raises(
            StockMovementServiceError, match="does not belong to the active workspace"
        ):
            record_stock_movement(
                workspace=setup_data["workspace"],
                item=setup_data["item"],
                location=loc_other,
                movement_type=MovementType.RECEIVED,
                quantity=Decimal("10.00"),
                reason="Invalid cross-workspace attempt",
            )
