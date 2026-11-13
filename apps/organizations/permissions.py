from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from apps.organizations.models import Role


def workspace_required(view_func):
    """
    Ensures user is authenticated and has an active workspace selected.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not getattr(request, "workspace", None):
            messages.warning(request, "Please create or select a business workspace first.")
            return redirect("organizations:create")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def role_required(allowed_roles):
    """
    Requires the user to have one of the specified roles in the active workspace.
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")
            if not getattr(request, "workspace", None):
                return redirect("organizations:create")

            membership = getattr(request, "membership", None)
            if not membership or membership.role not in allowed_roles:
                messages.error(
                    request,
                    "You do not have sufficient permissions to perform this action in this workspace.",
                )
                raise PermissionDenied(
                    "Insufficient permissions for the requested workspace action."
                )

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def owner_required(view_func):
    return role_required([Role.OWNER])(view_func)


def manager_required(view_func):
    return role_required([Role.OWNER, Role.MANAGER])(view_func)


def staff_or_higher_required(view_func):
    return role_required([Role.OWNER, Role.MANAGER, Role.STAFF])(view_func)
