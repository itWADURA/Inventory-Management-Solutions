from apps.audit.models import AuditEvent


def get_client_ip(request):
    if not request:
        return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_audit_event(workspace, user, action, description, request=None, metadata=None):
    """
    Creates an immutable audit log record for workspace-level compliance and tracking.
    """
    if not workspace:
        return None

    ip_address = get_client_ip(request) if request else None

    return AuditEvent.objects.create(
        workspace=workspace,
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        description=description,
        ip_address=ip_address,
        metadata=metadata or {},
    )
