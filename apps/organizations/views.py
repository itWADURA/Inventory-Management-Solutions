from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify

from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.catalog.models import Item
from apps.inventory.models import Location, StockBalance, StockMovement
from apps.organizations.forms import (
    MemberAddForm,
    MemberRoleForm,
    WorkspaceDeleteForm,
    WorkspaceForm,
)
from apps.organizations.models import Membership, Role, Workspace
from apps.organizations.permissions import (
    manager_required,
    owner_required,
    workspace_required,
)

User = get_user_model()


@login_required
def dashboard_view(request):
    workspace = getattr(request, "workspace", None)
    if not workspace:
        return redirect("organizations:create")

    # 1. Active items count
    active_items_count = Item.objects.filter(workspace=workspace, is_active=True).count()

    # 2. Total tracked physical stock quantity across all locations (clearly labeled as quantity, not value)
    total_quantity_agg = StockBalance.objects.filter(workspace=workspace).aggregate(
        total=Sum("quantity")
    )["total"]
    total_quantity = total_quantity_agg if total_quantity_agg is not None else Decimal("0.00")

    # 3. Low stock items: items with reorder_level > 0 and sum(stock_balances) <= reorder_level
    # We annotate each active item with total on hand
    tracked_items = (
        Item.objects.filter(workspace=workspace, is_active=True)
        .annotate(on_hand=Sum("stock_balances__quantity"))
        .select_related("category")
    )

    low_stock_items = []
    for item in tracked_items:
        current_qty = item.on_hand if item.on_hand is not None else Decimal("0.00")
        item.current_on_hand = current_qty
        if item.reorder_level > Decimal("0.00") and current_qty <= item.reorder_level:
            low_stock_items.append(item)

    low_stock_count = len(low_stock_items)

    # 4. Recent stock movements (latest 8)
    recent_movements = (
        StockMovement.objects.filter(workspace=workspace)
        .select_related("item", "location", "user")
        .order_by("-created_at")[:8]
    )

    # Default stock location
    default_location = Location.objects.filter(workspace=workspace, is_active=True).first()

    return render(
        request,
        "organizations/dashboard.html",
        {
            "active_items_count": active_items_count,
            "total_quantity": total_quantity,
            "low_stock_count": low_stock_count,
            "low_stock_items": low_stock_items[:5],  # top 5 on dashboard
            "recent_movements": recent_movements,
            "default_location": default_location,
        },
    )


@login_required
def workspace_create_view(request):
    if request.method == "POST":
        form = WorkspaceForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                workspace = form.save(commit=False)
                base_slug = slugify(workspace.name) or "workspace"
                slug = base_slug
                c = 1
                while Workspace.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{c}"
                    c += 1
                workspace.slug = slug
                workspace.save()

                Membership.objects.create(
                    user=request.user,
                    workspace=workspace,
                    role=Role.OWNER,
                )

                Location.objects.create(
                    workspace=workspace,
                    name="Main location",
                    notes="Primary storage location.",
                    is_active=True,
                )

                log_audit_event(
                    workspace=workspace,
                    user=request.user,
                    action=AuditAction.WORKSPACE_CREATED,
                    description=f"Workspace '{workspace.name}' created by {request.user.username}.",
                    request=request,
                )

            request.session["active_workspace_id"] = str(workspace.id)
            messages.success(request, f"Workspace '{workspace.name}' created successfully.")
            return redirect("organizations:dashboard")
    else:
        form = WorkspaceForm()

    return render(request, "organizations/workspace_form.html", {"form": form, "is_new": True})


@login_required
def workspace_switch_view(request, workspace_id):
    # Verify membership before switching
    membership = get_object_or_404(Membership, user=request.user, workspace_id=workspace_id)
    request.session["active_workspace_id"] = str(membership.workspace.id)
    messages.success(request, f"Switched to workspace '{membership.workspace.name}'.")
    return redirect("organizations:dashboard")


@workspace_required
@owner_required
def workspace_settings_view(request):
    workspace = request.workspace
    if request.method == "POST":
        form = WorkspaceForm(request.POST, instance=workspace)
        if form.is_valid():
            form.save()
            log_audit_event(
                workspace=workspace,
                user=request.user,
                action=AuditAction.SETTINGS_UPDATED,
                description=f"Workspace settings updated by {request.user.username}.",
                request=request,
            )
            messages.success(request, "Workspace settings updated successfully.")
            return redirect("organizations:settings")
    else:
        form = WorkspaceForm(instance=workspace)

    return render(request, "organizations/settings.html", {"form": form})


@workspace_required
@manager_required
def workspace_members_view(request):
    workspace = request.workspace
    memberships = (
        Membership.objects.filter(workspace=workspace)
        .select_related("user")
        .order_by("role", "created_at")
    )

    if request.method == "POST":
        if not request.membership.is_owner:
            messages.error(request, "Only workspace owners can add new team members.")
            return redirect("organizations:members")

        form = MemberAddForm(request.POST, workspace=workspace)
        if form.is_valid():
            target_user = form.target_user
            role = form.cleaned_data["role"]
            new_membership = Membership.objects.create(
                user=target_user,
                workspace=workspace,
                role=role,
            )
            log_audit_event(
                workspace=workspace,
                user=request.user,
                action=AuditAction.MEMBER_ADDED,
                description=f"Added member {target_user.username} with role {role}.",
                request=request,
            )
            messages.success(
                request,
                f"User '{target_user.username}' added to '{workspace.name}' as {new_membership.get_role_display()}.",
            )
            return redirect("organizations:members")
    else:
        form = MemberAddForm(workspace=workspace)

    return render(
        request,
        "organizations/members.html",
        {"memberships": memberships, "form": form},
    )


@workspace_required
@owner_required
def workspace_member_edit_view(request, membership_id):
    workspace = request.workspace
    membership = get_object_or_404(Membership, id=membership_id, workspace=workspace)

    if request.method == "POST":
        form = MemberRoleForm(request.POST, instance=membership)
        if form.is_valid():
            new_role = form.cleaned_data["role"]
            # Ensure not demoting the last owner
            if membership.role == Role.OWNER and new_role != Role.OWNER:
                owner_count = Membership.objects.filter(
                    workspace=workspace, role=Role.OWNER
                ).count()
                if owner_count <= 1:
                    messages.error(
                        request,
                        "Cannot change role: A workspace must have at least one active Owner.",
                    )
                    return redirect("organizations:members")

            form.save()
            log_audit_event(
                workspace=workspace,
                user=request.user,
                action=AuditAction.MEMBER_ROLE_CHANGED,
                description=f"Changed {membership.user.username}'s role to {new_role}.",
                request=request,
            )
            messages.success(
                request,
                f"Updated {membership.user.username}'s role to {membership.get_role_display()}.",
            )
            return redirect("organizations:members")
    else:
        form = MemberRoleForm(instance=membership)

    return render(
        request,
        "organizations/member_edit.html",
        {"membership": membership, "form": form},
    )


@workspace_required
@owner_required
def workspace_member_delete_view(request, membership_id):
    workspace = request.workspace
    membership = get_object_or_404(Membership, id=membership_id, workspace=workspace)

    if membership.role == Role.OWNER:
        owner_count = Membership.objects.filter(workspace=workspace, role=Role.OWNER).count()
        if owner_count <= 1:
            messages.error(
                request,
                "Cannot remove member: The workspace must retain at least one Owner.",
            )
            return redirect("organizations:members")

    if request.method == "POST":
        username = membership.user.username
        membership.delete()
        log_audit_event(
            workspace=workspace,
            user=request.user,
            action=AuditAction.MEMBER_REMOVED,
            description=f"Removed {username} from workspace.",
            request=request,
        )
        messages.success(request, f"Removed '{username}' from the workspace.")
        return redirect("organizations:members")

    return render(
        request,
        "organizations/member_confirm_delete.html",
        {"membership": membership},
    )


@workspace_required
@owner_required
def workspace_delete_view(request):
    workspace = request.workspace
    if request.method == "POST":
        form = WorkspaceDeleteForm(request.POST, workspace=workspace)
        if form.is_valid():
            name = workspace.name
            workspace.delete()
            request.session.pop("active_workspace_id", None)
            messages.info(request, f"Workspace '{name}' has been permanently deleted.")
            return redirect("organizations:dashboard")
    else:
        form = WorkspaceDeleteForm(workspace=workspace)

    return render(
        request,
        "organizations/workspace_confirm_delete.html",
        {"form": form, "workspace": workspace},
    )
