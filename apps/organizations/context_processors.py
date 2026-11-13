from apps.organizations.models import Membership, Role


def workspace_context(request):
    """
    Exposes active workspace and user membership context to all templates.
    """
    if not request.user.is_authenticated:
        return {
            "current_workspace": None,
            "current_membership": None,
            "user_workspaces": [],
            "is_owner": False,
            "is_manager": False,
            "is_staff_only": False,
        }

    workspace = getattr(request, "workspace", None)
    membership = getattr(request, "membership", None)

    user_memberships = (
        Membership.objects.select_related("workspace")
        .filter(user=request.user)
        .order_by("workspace__name")
    )
    user_workspaces = [m.workspace for m in user_memberships]

    is_owner = membership.role == Role.OWNER if membership else False
    is_manager = membership.role in (Role.OWNER, Role.MANAGER) if membership else False
    is_staff_only = membership.role == Role.STAFF if membership else False

    return {
        "current_workspace": workspace,
        "current_membership": membership,
        "user_workspaces": user_workspaces,
        "is_owner": is_owner,
        "is_manager": is_manager,
        "is_staff_only": is_staff_only,
    }
