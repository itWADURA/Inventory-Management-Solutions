import csv
import io
from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.catalog.models import Category, Item
from apps.inventory.models import Location, MovementType
from apps.inventory.services import record_stock_movement

EXPECTED_HEADERS = [
    "name",
    "sku",
    "category",
    "unit",
    "cost_price",
    "selling_price",
    "reorder_level",
    "initial_quantity",
    "initial_location",
]


def generate_csv_template():
    """Generates a downloadable sample CSV template for item import."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(EXPECTED_HEADERS)
    writer.writerow(
        [
            "Sample Hammer 16oz",
            "HAM-001",
            "Hand Tools",
            "piece",
            "12.50",
            "19.99",
            "5.00",
            "20.00",
            "Main location",
        ]
    )
    writer.writerow(
        [
            "Galvanized Nails 2-inch",
            "NL-GALV-2",
            "Fasteners",
            "box",
            "4.20",
            "8.50",
            "10.00",
            "50.00",
            "Main location",
        ]
    )
    return output.getvalue()


def _parse_row_decimal(row_dict, row_num, field_name, error_list, default="0.00"):
    val_str = row_dict.get(field_name, "").strip() or default
    try:
        dec = Decimal(val_str)
        if dec < Decimal("0.00"):
            error_list.append(
                f"Row {row_num}: '{field_name}' cannot be negative (got '{val_str}')."
            )
            return Decimal("0.00")
        return dec
    except InvalidOperation:
        error_list.append(
            f"Row {row_num}: '{field_name}' must be a valid number (got '{val_str}')."
        )
        return Decimal("0.00")


def parse_and_validate_item_csv(file_content, workspace):
    """
    Parses and thoroughly validates an uploaded CSV file.
    Returns: (is_valid, parsed_data, errors)
    """
    errors = []
    parsed_rows = []
    seen_skus_in_csv = set()

    try:
        decoded_file = file_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            decoded_file = file_content.decode("latin-1")
        except Exception:
            return (
                False,
                [],
                ["File could not be decoded. Please ensure file is UTF-8 encoded text."],
            )

    reader = csv.DictReader(io.StringIO(decoded_file))
    if not reader.fieldnames:
        return False, [], ["Uploaded CSV file is completely empty."]

    # Normalize header names (lowercase, stripped)
    headers = [h.strip().lower() for h in reader.fieldnames if h]
    if "name" not in headers:
        return False, [], ["Missing required 'name' column in CSV header."]

    # Query existing SKUs in workspace for conflict detection
    existing_skus = set(
        Item.objects.filter(workspace=workspace, sku__isnull=False)
        .exclude(sku="")
        .values_list("sku", flat=True)
    )
    existing_skus_lower = {s.lower() for s in existing_skus}

    for row_idx, raw_row in enumerate(reader, start=2):
        row = {k.strip().lower(): v.strip() for k, v in raw_row.items() if k}
        name = row.get("name", "").strip()

        if not name:
            errors.append(f"Row {row_idx}: 'name' is required and cannot be blank.")
            continue

        sku = row.get("sku", "").strip()
        if sku:
            sku_lower = sku.lower()
            if sku_lower in seen_skus_in_csv:
                errors.append(
                    f"Row {row_idx}: Duplicate SKU '{sku}' found multiple times in this CSV file."
                )
            elif sku_lower in existing_skus_lower:
                errors.append(f"Row {row_idx}: SKU '{sku}' already exists in this workspace.")
            seen_skus_in_csv.add(sku_lower)

        cost_price = _parse_row_decimal(row, row_idx, "cost_price", errors, "0.00")
        selling_price = _parse_row_decimal(row, row_idx, "selling_price", errors, "0.00")
        reorder_level = _parse_row_decimal(row, row_idx, "reorder_level", errors, "0.00")
        initial_quantity = _parse_row_decimal(row, row_idx, "initial_quantity", errors, "0.00")

        category_name = row.get("category", "").strip()
        unit = row.get("unit", "").strip().lower() or "piece"
        initial_location = row.get("initial_location", "").strip() or "Main location"

        parsed_rows.append(
            {
                "row_idx": row_idx,
                "name": name,
                "sku": sku or None,
                "category_name": category_name,
                "unit": unit,
                "cost_price": cost_price,
                "selling_price": selling_price,
                "reorder_level": reorder_level,
                "initial_quantity": initial_quantity,
                "initial_location": initial_location,
            }
        )

    is_valid = len(errors) == 0 and len(parsed_rows) > 0
    if len(parsed_rows) == 0 and not errors:
        errors.append("No data rows found in CSV.")

    return is_valid, parsed_rows, errors


def commit_item_import(workspace, parsed_rows, user, request=None):
    """
    Executes the validated import transactionally.
    Creates categories, items, locations, and opening movements atomically.
    """
    with transaction.atomic():
        # Pre-cache or create categories
        categories = {}
        for r in parsed_rows:
            cname = r["category_name"]
            if cname and cname not in categories:
                cat, _ = Category.objects.get_or_create(
                    workspace=workspace,
                    name=cname,
                    defaults={"description": "Imported via CSV"},
                )
                categories[cname] = cat

        # Pre-cache or create locations
        locations = {}
        for r in parsed_rows:
            lname = r["initial_location"]
            if lname and lname not in locations:
                loc, _ = Location.objects.get_or_create(
                    workspace=workspace,
                    name=lname,
                    defaults={"notes": "Imported via CSV"},
                )
                locations[lname] = loc

        items_created = 0
        for r in parsed_rows:
            cat = categories.get(r["category_name"])
            item = Item.objects.create(
                workspace=workspace,
                name=r["name"],
                sku=r["sku"],
                category=cat,
                unit=r["unit"],
                cost_price=r["cost_price"],
                selling_price=r["selling_price"],
                reorder_level=r["reorder_level"],
                is_active=True,
            )
            items_created += 1

            # Opening balance if > 0
            if r["initial_quantity"] > Decimal("0.00"):
                loc = locations.get(r["initial_location"])
                record_stock_movement(
                    workspace=workspace,
                    item=item,
                    location=loc,
                    movement_type=MovementType.OPENING_BALANCE,
                    quantity=r["initial_quantity"],
                    reason="Initial balance imported from CSV.",
                    user=user,
                    unit_cost=r["cost_price"] if r["cost_price"] > Decimal("0.00") else None,
                    request=request,
                )

        log_audit_event(
            workspace=workspace,
            user=user,
            action=AuditAction.CSV_IMPORTED,
            description=f"Imported {items_created} items from CSV.",
            request=request,
            metadata={"count": items_created},
        )

        return items_created
