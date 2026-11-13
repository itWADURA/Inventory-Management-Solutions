import csv
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import BooleanField, Case, F, Sum, Value, When
from django.http import HttpResponse
from django.shortcuts import redirect, render

from apps.catalog.models import Category, Item
from apps.inventory.models import Location, MovementType, StockBalance, StockMovement
from apps.organizations.permissions import (
    manager_required,
    staff_or_higher_required,
    workspace_required,
)
from apps.reports.forms import CsvImportForm
from apps.reports.services import (
    commit_item_import,
    generate_csv_template,
    parse_and_validate_item_csv,
)


@workspace_required
@staff_or_higher_required
def reports_index_view(request):
    return render(request, "reports/index.html")


@workspace_required
@staff_or_higher_required
def stock_summary_report_view(request):
    workspace = request.workspace
    export_csv = request.GET.get("export") == "csv"

    queryset = (
        Item.objects.filter(workspace=workspace, is_active=True)
        .select_related("category")
        .annotate(total_on_hand=Sum("stock_balances__quantity"))
        .annotate(
            is_low=Case(
                When(
                    reorder_level__gt=0,
                    total_on_hand__lte=F("reorder_level"),
                    then=Value(True),
                ),
                default=Value(False),
                output_field=BooleanField(),
            )
        )
        .order_by("name")
    )

    category_id = request.GET.get("category", "").strip()
    if category_id:
        queryset = queryset.filter(category_id=category_id)

    if export_csv:
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="current_stock_{workspace.slug}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(
            [
                "Item Name",
                "Item Code (SKU)",
                "Category",
                "Unit",
                "On Hand Quantity",
                "Reorder Level",
                "Low Stock Alert",
                "Cost Price",
                "Selling Price",
            ]
        )
        for item in queryset:
            qty = item.total_on_hand if item.total_on_hand is not None else Decimal("0.00")
            is_low_str = "YES" if (item.reorder_level > 0 and qty <= item.reorder_level) else "NO"
            writer.writerow(
                [
                    item.name,
                    item.sku or "",
                    item.category.name if item.category else "",
                    item.get_unit_display(),
                    qty,
                    item.reorder_level,
                    is_low_str,
                    item.cost_price,
                    item.selling_price,
                ]
            )
        return response

    paginator = Paginator(queryset, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    categories = Category.objects.filter(workspace=workspace)

    return render(
        request,
        "reports/stock_summary.html",
        {"page_obj": page_obj, "categories": categories, "category_id": category_id},
    )


@workspace_required
@staff_or_higher_required
def low_stock_report_view(request):
    workspace = request.workspace
    export_csv = request.GET.get("export") == "csv"

    queryset = (
        Item.objects.filter(workspace=workspace, is_active=True, reorder_level__gt=0)
        .select_related("category")
        .annotate(total_on_hand=Sum("stock_balances__quantity"))
        .filter(total_on_hand__lte=F("reorder_level"))
        .order_by("name")
    )

    if export_csv:
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="low_stock_{workspace.slug}.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Item Name",
                "Item Code (SKU)",
                "Category",
                "Unit",
                "Current Stock",
                "Reorder Level",
                "Deficit",
            ]
        )
        for item in queryset:
            qty = item.total_on_hand if item.total_on_hand is not None else Decimal("0.00")
            deficit = item.reorder_level - qty
            writer.writerow(
                [
                    item.name,
                    item.sku or "",
                    item.category.name if item.category else "",
                    item.get_unit_display(),
                    qty,
                    item.reorder_level,
                    deficit,
                ]
            )
        return response

    paginator = Paginator(queryset, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "reports/low_stock.html", {"page_obj": page_obj})


@workspace_required
@staff_or_higher_required
def movement_history_report_view(request):
    workspace = request.workspace
    export_csv = request.GET.get("export") == "csv"

    queryset = (
        StockMovement.objects.filter(workspace=workspace)
        .select_related("item", "location", "user")
        .order_by("-created_at")
    )

    # Filters
    item_id = request.GET.get("item", "").strip()
    if item_id:
        queryset = queryset.filter(item_id=item_id)

    location_id = request.GET.get("location", "").strip()
    if location_id:
        queryset = queryset.filter(location_id=location_id)

    mtype = request.GET.get("type", "").strip()
    if mtype:
        queryset = queryset.filter(movement_type=mtype)

    date_from = request.GET.get("date_from", "").strip()
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)

    date_to = request.GET.get("date_to", "").strip()
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)

    if export_csv:
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="stock_movements_{workspace.slug}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(
            [
                "Date & Time",
                "Item Name",
                "Item Code (SKU)",
                "Location",
                "Type",
                "Change (+/-)",
                "Before",
                "After",
                "Unit Cost",
                "Reason",
                "Recorded By",
            ]
        )
        for m in queryset:
            writer.writerow(
                [
                    m.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    m.item.name,
                    m.item.sku or "",
                    m.location.name,
                    m.get_movement_type_display(),
                    m.quantity_delta,
                    m.quantity_before,
                    m.quantity_after,
                    m.unit_cost if m.unit_cost is not None else "",
                    m.reason,
                    m.user.username if m.user else "System",
                ]
            )
        return response

    paginator = Paginator(queryset, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    items = Item.objects.filter(workspace=workspace).order_by("name")
    locations = Location.objects.filter(workspace=workspace).order_by("name")

    return render(
        request,
        "reports/movements_report.html",
        {
            "page_obj": page_obj,
            "items": items,
            "locations": locations,
            "movement_types": MovementType.choices,
            "selected_item": item_id,
            "selected_location": location_id,
            "selected_type": mtype,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@workspace_required
@manager_required
def csv_template_download_view(request):
    csv_content = generate_csv_template()
    response = HttpResponse(csv_content, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="itwadura_items_template.csv"'
    return response


@workspace_required
@manager_required
def csv_export_items_view(request):
    workspace = request.workspace
    items = (
        Item.objects.filter(workspace=workspace)
        .select_related("category", "supplier")
        .order_by("name")
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="items_export_{workspace.slug}.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Name",
            "SKU",
            "Category",
            "Supplier",
            "Unit",
            "Barcode",
            "Cost Price",
            "Selling Price",
            "Reorder Level",
            "Is Active",
            "Description",
        ]
    )
    for i in items:
        writer.writerow(
            [
                i.name,
                i.sku or "",
                i.category.name if i.category else "",
                i.supplier.name if i.supplier else "",
                i.unit,
                i.barcode,
                i.cost_price,
                i.selling_price,
                i.reorder_level,
                "1" if i.is_active else "0",
                i.description,
            ]
        )
    return response


@workspace_required
@manager_required
def csv_export_stock_view(request):
    workspace = request.workspace
    balances = (
        StockBalance.objects.filter(workspace=workspace)
        .select_related("item", "location")
        .order_by("item__name", "location__name")
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="stock_balances_{workspace.slug}.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Item Name",
            "Item Code (SKU)",
            "Location",
            "On Hand Quantity",
            "Unit",
            "Last Updated",
        ]
    )
    for b in balances:
        writer.writerow(
            [
                b.item.name,
                b.item.sku or "",
                b.location.name,
                b.quantity,
                b.item.get_unit_display(),
                b.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )
    return response


@workspace_required
@manager_required
def csv_import_view(request):
    workspace = request.workspace
    errors = []
    parsed_rows = []
    is_preview = False

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "commit":
            # Commit previously previewed data stored in session
            session_rows = request.session.get("pending_csv_rows")
            if not session_rows:
                messages.error(
                    request, "No pending import session found. Please re-upload your file."
                )
                return redirect("reports:csv_import")

            # Deserialise Decimal values
            for r in session_rows:
                r["cost_price"] = Decimal(str(r["cost_price"]))
                r["selling_price"] = Decimal(str(r["selling_price"]))
                r["reorder_level"] = Decimal(str(r["reorder_level"]))
                r["initial_quantity"] = Decimal(str(r["initial_quantity"]))

            count = commit_item_import(workspace, session_rows, request.user, request=request)
            request.session.pop("pending_csv_rows", None)
            messages.success(
                request, f"Successfully imported {count} items into '{workspace.name}'."
            )
            return redirect("catalog:item_list")

        else:
            form = CsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                file = request.FILES["csv_file"]
                is_valid, parsed_rows, errors = parse_and_validate_item_csv(file.read(), workspace)

                if is_valid:
                    is_preview = True
                    # Store serialisable version in session for commit
                    serialisable_rows = []
                    for r in parsed_rows:
                        row_copy = dict(r)
                        row_copy["cost_price"] = str(r["cost_price"])
                        row_copy["selling_price"] = str(r["selling_price"])
                        row_copy["reorder_level"] = str(r["reorder_level"])
                        row_copy["initial_quantity"] = str(r["initial_quantity"])
                        serialisable_rows.append(row_copy)
                    request.session["pending_csv_rows"] = serialisable_rows
    else:
        form = CsvImportForm()

    return render(
        request,
        "reports/csv_import.html",
        {
            "form": form,
            "errors": errors,
            "parsed_rows": parsed_rows[:20],  # preview up to 20 rows
            "total_rows": len(parsed_rows),
            "is_preview": is_preview,
        },
    )
