from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import BooleanField, Case, Count, F, Q, Sum, Value, When
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.catalog.forms import CategoryForm, ItemForm, SupplierForm
from apps.catalog.models import Category, Item, Supplier
from apps.inventory.models import MovementType, StockBalance, StockMovement
from apps.inventory.services import record_stock_movement
from apps.organizations.permissions import (
    manager_required,
    staff_or_higher_required,
    workspace_required,
)


@workspace_required
@staff_or_higher_required
def item_list_view(request):
    workspace = request.workspace
    queryset = (
        Item.objects.filter(workspace=workspace)
        .select_related("category", "supplier")
        .annotate(total_on_hand=Sum("stock_balances__quantity"))
    )

    # Search query
    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q)
        )

    # Filter category
    category_id = request.GET.get("category", "").strip()
    if category_id:
        queryset = queryset.filter(category_id=category_id)

    # Filter status: default to active items unless 'all' or 'inactive' specified
    status_filter = request.GET.get("status", "active")
    if status_filter == "active":
        queryset = queryset.filter(is_active=True)
    elif status_filter == "inactive":
        queryset = queryset.filter(is_active=False)

    # Annotate low stock flag: reorder_level > 0 and total_on_hand <= reorder_level
    queryset = queryset.annotate(
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

    # Filter low stock only
    low_stock_only = request.GET.get("low_stock") == "1"
    if low_stock_only:
        queryset = queryset.filter(is_low=True)

    # Sorting
    sort_by = request.GET.get("sort", "name")
    if sort_by == "name_desc":
        queryset = queryset.order_by("-name")
    elif sort_by == "quantity_asc":
        queryset = queryset.order_by("total_on_hand", "name")
    elif sort_by == "quantity_desc":
        queryset = queryset.order_by("-total_on_hand", "name")
    elif sort_by == "low_stock":
        queryset = queryset.order_by("-is_low", "name")
    else:
        queryset = queryset.order_by("name")

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.filter(workspace=workspace)

    context = {
        "page_obj": page_obj,
        "categories": categories,
        "query": q,
        "category_id": category_id,
        "status_filter": status_filter,
        "sort_by": sort_by,
        "low_stock_only": low_stock_only,
    }

    if request.headers.get("HX-Request"):
        return render(request, "catalog/partials/item_table.html", context)

    return render(request, "catalog/item_list.html", context)


@workspace_required
@staff_or_higher_required
def item_detail_view(request, item_id):
    workspace = request.workspace
    item = get_object_or_404(
        Item.objects.select_related("category", "supplier"), id=item_id, workspace=workspace
    )

    balances = (
        StockBalance.objects.filter(item=item, workspace=workspace)
        .select_related("location")
        .order_by("location__name")
    )
    movements = (
        StockMovement.objects.filter(item=item, workspace=workspace)
        .select_related("location", "user")
        .order_by("-created_at")[:15]
    )

    return render(
        request,
        "catalog/item_detail.html",
        {
            "item": item,
            "balances": balances,
            "movements": movements,
            "total_quantity": item.total_quantity,
        },
    )


@workspace_required
@manager_required
def item_create_view(request):
    workspace = request.workspace

    if request.method == "POST":
        form = ItemForm(request.POST, workspace=workspace)
        if form.is_valid():
            with transaction.atomic():
                item = form.save(commit=False)
                item.workspace = workspace
                item.save()

                # Handle initial opening stock if provided
                opening_qty = form.cleaned_data.get("opening_quantity")
                opening_loc = form.cleaned_data.get("opening_location")
                if opening_qty and opening_qty > Decimal("0.00") and opening_loc:
                    record_stock_movement(
                        workspace=workspace,
                        item=item,
                        location=opening_loc,
                        movement_type=MovementType.OPENING_BALANCE,
                        quantity=opening_qty,
                        reason="Initial opening balance recorded at item creation.",
                        user=request.user,
                        unit_cost=item.cost_price if item.cost_price > Decimal("0.00") else None,
                        request=request,
                    )

                log_audit_event(
                    workspace=workspace,
                    user=request.user,
                    action=AuditAction.ITEM_CREATED,
                    description=f"Created item '{item.name}' (SKU: {item.sku or 'None'}).",
                    request=request,
                    metadata={"item_id": item.id, "name": item.name, "sku": item.sku},
                )

            messages.success(request, f"Item '{item.name}' was created successfully.")
            return redirect("catalog:item_detail", item_id=item.id)
    else:
        form = ItemForm(workspace=workspace)

    return render(request, "catalog/item_form.html", {"form": form, "is_edit": False})


@workspace_required
@manager_required
def item_edit_view(request, item_id):
    workspace = request.workspace
    item = get_object_or_404(Item, id=item_id, workspace=workspace)

    if request.method == "POST":
        form = ItemForm(request.POST, instance=item, workspace=workspace, is_edit=True)
        if form.is_valid():
            updated_item = form.save()
            log_audit_event(
                workspace=workspace,
                user=request.user,
                action=AuditAction.ITEM_UPDATED,
                description=f"Updated item details for '{updated_item.name}'.",
                request=request,
                metadata={"item_id": updated_item.id},
            )
            messages.success(request, f"Item '{updated_item.name}' was updated.")
            return redirect("catalog:item_detail", item_id=updated_item.id)
    else:
        form = ItemForm(instance=item, workspace=workspace, is_edit=True)

    return render(
        request,
        "catalog/item_form.html",
        {"form": form, "item": item, "is_edit": True},
    )


@workspace_required
@manager_required
def item_archive_view(request, item_id):
    workspace = request.workspace
    item = get_object_or_404(Item, id=item_id, workspace=workspace)

    if request.method == "POST":
        new_status = not item.is_active
        item.is_active = new_status
        item.save(update_fields=["is_active", "updated_at"])

        action = AuditAction.ITEM_RESTORED if new_status else AuditAction.ITEM_ARCHIVED
        status_word = "restored to active" if new_status else "archived"
        log_audit_event(
            workspace=workspace,
            user=request.user,
            action=action,
            description=f"Item '{item.name}' was {status_word}.",
            request=request,
            metadata={"item_id": item.id, "is_active": new_status},
        )
        messages.success(request, f"Item '{item.name}' has been {status_word}.")
        return redirect("catalog:item_detail", item_id=item.id)

    return render(request, "catalog/item_confirm_archive.html", {"item": item})


# Categories Views
@workspace_required
@manager_required
def category_list_view(request):
    workspace = request.workspace
    categories = (
        Category.objects.filter(workspace=workspace)
        .annotate(item_count=Count("items"))
        .order_by("name")
    )
    return render(request, "catalog/category_list.html", {"categories": categories})


@workspace_required
@manager_required
def category_create_view(request):
    workspace = request.workspace
    if request.method == "POST":
        form = CategoryForm(request.POST, workspace=workspace)
        if form.is_valid():
            category = form.save(commit=False)
            category.workspace = workspace
            category.save()
            messages.success(request, f"Category '{category.name}' created.")
            return redirect("catalog:category_list")
    else:
        form = CategoryForm(workspace=workspace)

    return render(request, "catalog/category_form.html", {"form": form, "is_edit": False})


@workspace_required
@manager_required
def category_edit_view(request, category_id):
    workspace = request.workspace
    category = get_object_or_404(Category, id=category_id, workspace=workspace)

    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category, workspace=workspace)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category '{category.name}' updated.")
            return redirect("catalog:category_list")
    else:
        form = CategoryForm(instance=category, workspace=workspace)

    return render(
        request, "catalog/category_form.html", {"form": form, "category": category, "is_edit": True}
    )


@workspace_required
@manager_required
def category_delete_view(request, category_id):
    workspace = request.workspace
    category = get_object_or_404(Category, id=category_id, workspace=workspace)

    if request.method == "POST":
        name = category.name
        category.delete()
        messages.success(request, f"Category '{name}' deleted.")
        return redirect("catalog:category_list")

    return render(request, "catalog/category_confirm_delete.html", {"category": category})


# Suppliers Views
@workspace_required
@manager_required
def supplier_list_view(request):
    workspace = request.workspace
    suppliers = (
        Supplier.objects.filter(workspace=workspace)
        .annotate(item_count=Count("items"))
        .order_by("name")
    )
    return render(request, "catalog/supplier_list.html", {"suppliers": suppliers})


@workspace_required
@manager_required
def supplier_create_view(request):
    workspace = request.workspace
    if request.method == "POST":
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.workspace = workspace
            supplier.save()
            messages.success(request, f"Supplier '{supplier.name}' created.")
            return redirect("catalog:supplier_list")
    else:
        form = SupplierForm()

    return render(request, "catalog/supplier_form.html", {"form": form, "is_edit": False})


@workspace_required
@manager_required
def supplier_edit_view(request, supplier_id):
    workspace = request.workspace
    supplier = get_object_or_404(Supplier, id=supplier_id, workspace=workspace)

    if request.method == "POST":
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, f"Supplier '{supplier.name}' updated.")
            return redirect("catalog:supplier_list")
    else:
        form = SupplierForm(instance=supplier)

    return render(
        request, "catalog/supplier_form.html", {"form": form, "supplier": supplier, "is_edit": True}
    )


@workspace_required
@manager_required
def supplier_delete_view(request, supplier_id):
    workspace = request.workspace
    supplier = get_object_or_404(Supplier, id=supplier_id, workspace=workspace)

    if request.method == "POST":
        name = supplier.name
        supplier.delete()
        messages.success(request, f"Supplier '{name}' deleted.")
        return redirect("catalog:supplier_list")

    return render(request, "catalog/supplier_confirm_delete.html", {"supplier": supplier})
