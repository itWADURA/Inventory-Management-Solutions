from django.core.paginator import Paginator
from django.shortcuts import render

from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.permissions import manager_required, workspace_required


@workspace_required
@manager_required
def audit_log_view(request):
    workspace = request.workspace
    queryset = AuditEvent.objects.filter(workspace=workspace).select_related("user")

    action_filter = request.GET.get("action", "").strip()
    if action_filter:
        queryset = queryset.filter(action=action_filter)

    paginator = Paginator(queryset, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "audit/log.html",
        {
            "page_obj": page_obj,
            "action_choices": AuditAction.choices,
            "selected_action": action_filter,
        },
    )
