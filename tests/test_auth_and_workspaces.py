import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.catalog.models import Item
from apps.inventory.models import Location
from apps.organizations.models import Membership, Role, Workspace

User = get_user_model()


@pytest.mark.django_db
class TestAuthenticationAndWorkspaces:
    def test_signup_creates_user_workspace_and_default_location(self, client):
        url = reverse("accounts:signup")
        signup_data = {
            "workspace_name": "Apex Auto Repairs",
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@apex.local",
            "username": "alicesmith",
            "password1": "SecurePass123!@",
            "password2": "SecurePass123!@",
        }
        response = client.post(url, signup_data)
        assert response.status_code == 302

        # Verify user created
        user = User.objects.get(username="alicesmith")
        assert user.email == "alice@apex.local"

        # Verify workspace created with user as OWNER
        workspace = Workspace.objects.get(name="Apex Auto Repairs")
        membership = Membership.objects.get(user=user, workspace=workspace)
        assert membership.role == Role.OWNER

        # Verify default location created automatically
        default_loc = Location.objects.filter(workspace=workspace, name="Main location").first()
        assert default_loc is not None
        assert default_loc.is_active is True

    def test_workspace_isolation_prevent_cross_workspace_access(self, client):
        # Create Workspace A & Owner A
        user_a = User.objects.create_user(username="usera", password="passwordA123!")
        ws_a = Workspace.objects.create(name="Workspace A", slug="workspace-a")
        Membership.objects.create(user=user_a, workspace=ws_a, role=Role.OWNER)
        Item.objects.create(workspace=ws_a, name="Item Exclusive to A")

        # Create Workspace B & Owner B
        user_b = User.objects.create_user(username="userb", password="passwordB123!")
        ws_b = Workspace.objects.create(name="Workspace B", slug="workspace-b")
        Membership.objects.create(user=user_b, workspace=ws_b, role=Role.OWNER)
        item_b = Item.objects.create(workspace=ws_b, name="Item Exclusive to B")

        # Sign in as User A
        client.login(username="usera", password="passwordA123!")

        # User A tries to view Item B (belongs to Workspace B)
        url_item_b = reverse("catalog:item_detail", kwargs={"item_id": item_b.id})
        response = client.get(url_item_b)
        assert response.status_code == 404  # Not found in Workspace A scope

        # User A tries to switch to Workspace B
        switch_url = reverse("organizations:switch", kwargs={"workspace_id": ws_b.id})
        response_switch = client.get(switch_url)
        assert response_switch.status_code == 404  # Cannot switch without membership

    def test_role_permissions_enforced(self, client):
        # Create Owner and Staff in same workspace
        owner = User.objects.create_user(username="owner1", password="passwordO123!")
        staff = User.objects.create_user(username="staff1", password="passwordS123!")
        ws = Workspace.objects.create(name="Role Test Shop", slug="role-test-shop")
        Membership.objects.create(user=owner, workspace=ws, role=Role.OWNER)
        Membership.objects.create(user=staff, workspace=ws, role=Role.STAFF)

        # Staff signs in
        client.login(username="staff1", password="passwordS123!")

        # Staff attempts to access workspace settings (Owner only)
        response_settings = client.get(reverse("organizations:settings"))
        assert response_settings.status_code == 403

        # Staff attempts to access member management (Manager/Owner only)
        response_members = client.get(reverse("organizations:members"))
        assert response_members.status_code == 403

        # Staff attempts to create an item (Manager/Owner only)
        response_item_create = client.get(reverse("catalog:item_create"))
        assert response_item_create.status_code == 403
