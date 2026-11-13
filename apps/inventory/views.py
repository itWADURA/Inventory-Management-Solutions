from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalog.models import Item
from apps.inventory.forms import (
    LocationForm,
    StockAdjustmentForm,
    StockReceiveForm,
    StockUsageForm,
)
from apps.inventory.models import Location, MovementType, StockBalance, StockMovement
from apps.inventory.services import StockMovementServiceError, record_stock_movement
from apps.organizations.permissions import (
    manager_required,
    staff_or_higher_required,
    workspace_required,
)


@workspace_required
@staff_or_higher_required
def movement_list_view(request):
    workspace = request.workspace
    queryset = (
        StockMovement.objects.filter(workspace=workspace)
        .select_related("item", "location", "user")
        .order_by("-created_at")
    )

    # Filter by item
    item_id = request.GET.get("item", "").strip()
    if item_id:
        queryset = queryset.filter(item_id=item_id)

    # Filter by location
    location_id = request.GET.get("location", "").strip()
    if location_id:
        queryset = queryset.filter(location_id=location_id)

    # Filter by movement type
    mtype = request.GET.get("type", "").strip()
    if mtype:
        queryset = queryset.filter(movement_type=mtype)

    # Date range filters (YYYY-MM-DD)
    date_from = request.GET.get("date_from", "").strip()
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)

    date_to = request.GET.get("date_to", "").strip()
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)

    paginator = Paginator(queryset, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    items = Item.objects.filter(workspace=workspace).order_by("name")
    locations = Location.objects.filter(workspace=workspace).order_by("name")

    return render(
        request,
        "inventory/movement_list.html",
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
@staff_or_higher_required
def receive_stock_view(request):
    workspace = request.workspace
    item_id = request.GET.get("item")
    location_id = request.GET.get("location")

    if request.method == "POST":
        form = StockReceiveForm(request.POST, workspace=workspace)
        if form.is_valid():
            item = form.cleaned_data["item"]
            location = form.cleaned_data["location"]
            quantity = form.cleaned_data["quantity"]
            unit_cost = form.cleaned_data.get("unit_cost")
            reason = form.cleaned_data["reason"]

            try:
                record_stock_movement(
                    workspace=workspace,
                    item=item,
                    location=location,
                    movement_type=MovementType.RECEIVED,
                    quantity=quantity,
                    reason=reason,
                    user=request.user,
                    unit_cost=unit_cost,
                    request=request,
                )
                messages.success(
                    request,
                    f"Successfully received +{quantity} {item.get_unit_display()} of '{item.name}' at '{location.name}'.",
                )
                return redirect("catalog:item_detail", item_id=item.id)
            except StockMovementServiceError as e:
                messages.error(request, str(e))
    else:
        form = StockReceiveForm(
            workspace=workspace,
            initial_item_id=item_id,
            initial_location_id=location_id,
        )

    return render(request, "inventory/receive_form.html", {"form": form})


@workspace_required
@staff_or_higher_required
def use_stock_view(request):
    workspace = request.workspace
    item_id = request.GET.get("item")
    location_id = request.GET.get("location")

    if request.method == "POST":
        form = StockUsageForm(request.POST, workspace=workspace)
        if form.is_valid():
            item = form.cleaned_data["item"]
            location = form.cleaned_data["location"]
            quantity = form.cleaned_data["quantity"]
            reason = form.cleaned_data["reason"]

            try:
                record_stock_movement(
                    workspace=workspace,
                    item=item,
                    location=location,
                    movement_type=MovementType.USED,
                    quantity=quantity,
                    reason=reason,
                    user=request.user,
                    request=request,
                )
                messages.success(
                    request,
                    f"Successfully recorded usage of -{quantity} {item.get_unit_display()} of '{item.name}' from '{location.name}'.",
                )
                return redirect("catalog:item_detail", item_id=item.id)
            except StockMovementServiceError as e:
                messages.error(request, str(e))
    else:
        form = StockUsageForm(
            workspace=workspace,
            initial_item_id=item_id,
            initial_location_id=location_id,
        )

    return render(request, "inventory/use_form.html", {"form": form})


@workspace_required
@staff_or_higher_required
def adjust_stock_view(request):
    workspace = request.workspace
    item_id = request.GET.get("item")
    location_id = request.GET.get("location")

    if request.method == "POST":
        form = StockAdjustmentForm(request.POST, workspace=workspace)
        if form.is_valid():
            item = form.cleaned_data["item"]
            location = form.cleaned_data["location"]
            counted_quantity = form.cleaned_data["counted_quantity"]
            reason = form.cleaned_data["reason"]

            try:
                movement = record_stock_movement(
                    workspace=workspace,
                    item=item,
                    location=location,
                    movement_type=MovementType.ADJUSTMENT,
                    quantity=counted_quantity,
                    reason=reason,
                    user=request.user,
                    request=request,
                )
                delta_str = (
                    f"+{movement.quantity_delta}"
                    if movement.quantity_delta > 0
                    else str(movement.quantity_delta)
                )
                messages.success(
                    request,
                    f"Stock adjusted for '{item.name}' at '{location.name}': Count is now {counted_quantity} (change: {delta_str}).",
                )
                return redirect("catalog:item_detail", item_id=item.id)
            except StockMovementServiceError as e:
                messages.error(request, str(e))
    else:
        form = StockAdjustmentForm(
            workspace=workspace,
            initial_item_id=item_id,
            initial_location_id=location_id,
        )

    return render(request, "inventory/adjust_form.html", {"form": form})


@workspace_required
def balance_lookup_api(request):
    """
    Returns current on-hand quantity for an item at a specific location.
    Used for live HTMX display on movement forms.
    """
    workspace = request.workspace
    item_id = request.GET.get("item_id")
    location_id = request.GET.get("location_id")

    if not item_id or not location_id:
        return JsonResponse({"quantity": "0.00", "unit": ""})

    balance = StockBalance.objects.filter(
        workspace=workspace,
        item_id=item_id,
        location_id=location_id,
    ).first()

    item = Item.objects.filter(workspace=workspace, id=item_id).first()
    unit = item.get_unit_display() if item else ""
    qty = str(balance.quantity) if balance else "0.00"

    return JsonResponse({"quantity": qty, "unit": unit})


# Location Management
@workspace_required
@manager_required
def location_list_view(request):
    workspace = request.workspace
    locations = (
        Location.objects.filter(workspace=workspace)
        .annotate(total_stock=Sum("stock_balances__quantity"))
        .order_by("name")
    )
    return render(request, "inventory/location_list.html", {"locations": locations})


@workspace_required
@manager_required
def location_create_view(request):
    workspace = request.workspace
    if request.method == "POST":
        form = LocationForm(request.POST, workspace=workspace)
        if form.is_valid():
            loc = form.save(commit=False)
            loc.workspace = workspace
            loc.save()
            messages.success(request, f"Location '{loc.name}' created successfully.")
            return redirect("inventory:location_list")
    else:
        form = LocationForm(workspace=workspace)

    return render(request, "inventory/location_form.html", {"form": form, "is_edit": False})


@workspace_required
@manager_required
def location_edit_view(request, location_id):
    workspace = request.workspace
    location = get_object_or_404(Location, id=location_id, workspace=workspace)

    if request.method == "POST":
        form = LocationForm(request.POST, instance=location, workspace=workspace)
        if form.is_valid():
            form.save()
            messages.success(request, f"Location '{location.name}' updated.")
            return redirect("inventory:location_list")
    else:
        form = LocationForm(instance=location, workspace=workspace)

    return render(
        request,
        "inventory/location_form.html",
        {"form": form, "location": location, "is_edit": True},
    )
