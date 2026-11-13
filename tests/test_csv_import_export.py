from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.catalog.models import Item
from apps.inventory.models import Location, StockBalance
from apps.organizations.models import Membership, Role, Workspace
from apps.reports.services import (
    commit_item_import,
    generate_csv_template,
    parse_and_validate_item_csv,
)

User = get_user_model()


@pytest.mark.django_db
class TestCsvImportAndExport:
    @pytest.fixture
    def setup_env(self):
        user = User.objects.create_user(username="csv_user", password="password123!")
        ws = Workspace.objects.create(name="CSV Testing Hub", slug="csv-testing-hub")
        Membership.objects.create(user=user, workspace=ws, role=Role.MANAGER)
        Location.objects.create(workspace=ws, name="Main location")
        return {"user": user, "workspace": ws}

    def test_csv_template_generation(self):
        content = generate_csv_template()
        assert "name,sku,category,unit" in content
        assert "Sample Hammer 16oz" in content

    def test_csv_validation_rejects_missing_name_and_invalid_numbers(self, setup_env):
        ws = setup_env["workspace"]
        bad_csv = b"""name,sku,category,unit,cost_price,selling_price,reorder_level,initial_quantity
,SKU-01,Tools,piece,10.00,15.00,5.00,2.00
Valid Item,SKU-02,Tools,piece,INVALID_NUMBER,15.00,5.00,2.00
"""
        is_valid, parsed_rows, errors = parse_and_validate_item_csv(bad_csv, ws)
        assert is_valid is False
        assert any("'name' is required" in e for e in errors)
        assert any("must be a valid number" in e for e in errors)

    def test_csv_validation_rejects_duplicate_sku_in_csv_and_existing(self, setup_env):
        ws = setup_env["workspace"]
        # Existing item in workspace
        Item.objects.create(workspace=ws, name="Existing Saw", sku="SAW-99")

        csv_with_dupes = b"""name,sku,category,unit,cost_price,selling_price,reorder_level,initial_quantity
New Saw,SAW-99,Tools,piece,20.00,25.00,5.00,0.00
Chisel 1,CHISEL-01,Tools,piece,5.00,10.00,2.00,0.00
Chisel 2,CHISEL-01,Tools,piece,6.00,12.00,2.00,0.00
"""
        is_valid, parsed_rows, errors = parse_and_validate_item_csv(csv_with_dupes, ws)
        assert is_valid is False
        # Conflicted with existing
        assert any("already exists in this workspace" in e for e in errors)
        # Conflicted with duplicate in same CSV
        assert any("Duplicate SKU 'CHISEL-01' found multiple times" in e for e in errors)

    def test_csv_commit_imports_items_and_opening_balances(self, setup_env):
        ws = setup_env["workspace"]
        user = setup_env["user"]

        valid_csv = b"""name,sku,category,unit,cost_price,selling_price,reorder_level,initial_quantity,initial_location
Cordless Drill,DRILL-18V,Power Tools,piece,45.00,79.99,3.00,12.00,Main location
Drill Bit Set,BITS-SET,Accessories,set,12.00,19.99,5.00,25.00,Main location
"""
        is_valid, parsed_rows, errors = parse_and_validate_item_csv(valid_csv, ws)
        assert is_valid is True
        assert len(errors) == 0

        # Commit import
        count = commit_item_import(ws, parsed_rows, user)
        assert count == 2

        drill = Item.objects.get(workspace=ws, sku="DRILL-18V")
        assert drill.category.name == "Power Tools"
        assert drill.cost_price == Decimal("45.00")
        assert drill.reorder_level == Decimal("3.00")

        # Verify initial opening movement and balance
        drill_balance = StockBalance.objects.get(item=drill, location__name="Main location")
        assert drill_balance.quantity == Decimal("12.00")

        bits = Item.objects.get(workspace=ws, sku="BITS-SET")
        bits_balance = StockBalance.objects.get(item=bits, location__name="Main location")
        assert bits_balance.quantity == Decimal("25.00")

    def test_csv_export_scoped_to_active_workspace(self, client, setup_env):
        ws = setup_env["workspace"]
        Item.objects.create(workspace=ws, name="Workspace 1 Exclusive Item", sku="WS1-ITEM")

        # Create another workspace and item
        ws2 = Workspace.objects.create(name="Workspace 2", slug="ws2")
        Item.objects.create(workspace=ws2, name="Workspace 2 Exclusive Item", sku="WS2-ITEM")

        client.login(username="csv_user", password="password123!")

        # Export items CSV from active workspace
        response = client.get(reverse("reports:export_items"))
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        assert "Workspace 1 Exclusive Item" in content
        assert "Workspace 2 Exclusive Item" not in content  # Strict tenant isolation
