from apps.organizations.models import Membership


class WorkspaceMiddleware:
    """
    Identifies the active workspace for the logged-in user and attaches
    `request.workspace` and `request.membership` to each request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.workspace = None
        request.membership = None

        if request.user.is_authenticated:
            workspace_id = request.session.get("active_workspace_id")
            membership = None

            if workspace_id:
                try:
                    membership = (
                        Membership.objects.select_related("workspace")
                        .filter(user=request.user, workspace_id=workspace_id)
                        .first()
                    )
                except (ValueError, TypeError):
                    membership = None

            # Fallback to the user's first available membership
            if not membership:
                membership = (
                    Membership.objects.select_related("workspace").filter(user=request.user).first()
                )
                if membership:
                    request.session["active_workspace_id"] = str(membership.workspace.id)

            if membership:
                request.workspace = membership.workspace
                request.membership = membership

        response = self.get_response(request)
        return response
