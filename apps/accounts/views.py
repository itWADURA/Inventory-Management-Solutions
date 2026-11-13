from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.text import slugify

from apps.accounts.forms import ProfileForm, SignUpForm
from apps.inventory.models import Location
from apps.organizations.models import Membership, Role, Workspace


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("organizations:dashboard")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                workspace_name = form.cleaned_data["workspace_name"].strip()

                # Generate unique slug
                base_slug = slugify(workspace_name) or "workspace"
                slug = base_slug
                counter = 1
                while Workspace.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1

                workspace = Workspace.objects.create(
                    name=workspace_name,
                    slug=slug,
                )

                Membership.objects.create(
                    user=user,
                    workspace=workspace,
                    role=Role.OWNER,
                )

                # Initialize default location
                Location.objects.create(
                    workspace=workspace,
                    name="Main location",
                    notes="Default primary stock storage location.",
                    is_active=True,
                )

            # Log user in and set active workspace in session
            login(request, user)
            request.session["active_workspace_id"] = str(workspace.id)
            messages.success(
                request,
                f"Welcome to Itwadura Inventory! Your workspace '{workspace.name}' is ready.",
            )
            return redirect("organizations:dashboard")
    else:
        form = SignUpForm()

    return render(request, "accounts/signup.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("organizations:dashboard")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            next_url = request.GET.get("next") or request.POST.get("next")
            if next_url:
                return redirect(next_url)
            return redirect("organizations:dashboard")
    else:
        form = AuthenticationForm()

    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been signed out.")
    return redirect("accounts:login")


@login_required
def profile_view(request):
    user = request.user
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile details have been updated.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=user)

    return render(request, "accounts/profile.html", {"form": form})


@login_required
def change_password_view(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your password was successfully updated!")
            return redirect("accounts:profile")
    else:
        form = PasswordChangeForm(request.user)

    return render(request, "accounts/change_password.html", {"form": form})
