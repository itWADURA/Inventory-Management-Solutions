from decimal import Decimal

from django.db import transaction

from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.inventory.models import MovementType, StockBalance, StockMovement


class StockMovementServiceError(Exception):
    """Raised when a business rule fails during a stock movement transaction."""

    pass


def record_stock_movement(
    workspace,
    item,
    location,
    movement_type,
    quantity,
    reason,
    user=None,
    unit_cost=None,
    request=None,
):
    """
    Atomically updates stock balance and creates an immutable stock movement record.

    Parameters:
    - workspace: Workspace instance
    - item: Item instance (must belong to workspace)
    - location: Location instance (must belong to workspace)
    - movement_type: One of MovementType (RECEIVED, USED, ADJUSTMENT, OPENING_BALANCE)
    - quantity:
        - For RECEIVED, USED, OPENING_BALANCE: positive Decimal representing units to add/subtract
        - For ADJUSTMENT: positive Decimal representing the newly counted physical total
    - reason: Required text explaining the operation
    - user: Optional user recording the movement
    - unit_cost: Optional unit cost
    - request: Optional HTTP request for audit logging IP detection
    """
    if item.workspace_id != workspace.id:
        raise StockMovementServiceError(
            "The selected item does not belong to the active workspace."
        )
    if location.workspace_id != workspace.id:
        raise StockMovementServiceError(
            "The selected location does not belong to the active workspace."
        )

    reason = (reason or "").strip()
    if not reason:
        raise StockMovementServiceError(
            "A reason or reference note is required for all stock movements."
        )

    try:
        qty_val = Decimal(str(quantity))
    except Exception as e:
        raise StockMovementServiceError(f"Invalid quantity value: {e}") from e

    if qty_val < Decimal("0.00"):
        raise StockMovementServiceError("Quantity cannot be negative.")

    cost_val = None
    if unit_cost is not None and str(unit_cost).strip() != "":
        try:
            cost_val = Decimal(str(unit_cost))
            if cost_val < Decimal("0.00"):
                raise StockMovementServiceError("Unit cost cannot be negative.")
        except Exception as e:
            raise StockMovementServiceError(f"Invalid unit cost value: {e}") from e

    with transaction.atomic():
        # Concurrency safety: Lock the balance row if it exists, or create it
        # In PostgreSQL select_for_update() enforces row-level locking.
        balance, created = StockBalance.objects.select_for_update().get_or_create(
            workspace=workspace,
            item=item,
            location=location,
            defaults={"quantity": Decimal("0.00")},
        )

        before_qty = balance.quantity

        if movement_type == MovementType.RECEIVED:
            if qty_val <= Decimal("0.00"):
                raise StockMovementServiceError("Quantity received must be greater than zero.")
            after_qty = before_qty + qty_val
            delta = qty_val
            audit_action = AuditAction.STOCK_RECEIVED

        elif movement_type == MovementType.USED:
            if qty_val <= Decimal("0.00"):
                raise StockMovementServiceError("Quantity used must be greater than zero.")
            if before_qty < qty_val:
                raise StockMovementServiceError(
                    f"Insufficient stock on hand at '{location.name}'. "
                    f"Available: {before_qty} {item.get_unit_display()}, Requested: {qty_val}."
                )
            after_qty = before_qty - qty_val
            delta = -qty_val
            audit_action = AuditAction.STOCK_USED

        elif movement_type == MovementType.ADJUSTMENT:
            # qty_val is the new counted quantity
            after_qty = qty_val
            delta = after_qty - before_qty
            audit_action = AuditAction.STOCK_ADJUSTED

        elif movement_type == MovementType.OPENING_BALANCE:
            # Opening balance directly sets initial balance
            after_qty = qty_val
            delta = after_qty - before_qty
            audit_action = AuditAction.STOCK_RECEIVED

        else:
            raise StockMovementServiceError(f"Unsupported movement type: {movement_type}")

        if after_qty < Decimal("0.00"):
            raise StockMovementServiceError(
                f"Resulting quantity cannot be negative (would be {after_qty})."
            )

        # Update the balance
        balance.quantity = after_qty
        balance.save(update_fields=["quantity", "updated_at"])

        # Create immutable movement record
        movement = StockMovement.objects.create(
            workspace=workspace,
            item=item,
            location=location,
            movement_type=movement_type,
            quantity_delta=delta,
            quantity_before=before_qty,
            quantity_after=after_qty,
            unit_cost=cost_val,
            reason=reason,
            user=user if getattr(user, "is_authenticated", False) else None,
        )

        # Log audit trail
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        log_audit_event(
            workspace=workspace,
            user=user,
            action=audit_action,
            description=(
                f"{item.name} @ {location.name}: {delta_str} "
                f"(balance {before_qty} -> {after_qty}). Reason: {reason}"
            ),
            request=request,
            metadata={
                "item_id": item.id,
                "item_name": item.name,
                "location_id": location.id,
                "location_name": location.name,
                "movement_id": movement.id,
                "quantity_before": str(before_qty),
                "quantity_after": str(after_qty),
                "quantity_delta": str(delta),
                "movement_type": movement_type,
            },
        )

        return movement
