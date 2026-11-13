from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.organizations.models import Membership, Role, Workspace

User = get_user_model()


class WorkspaceForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = ["name", "business_type", "currency", "timezone"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Downtown Hardware"}),
            "currency": forms.TextInput(attrs={"placeholder": "USD", "maxlength": 3}),
            "timezone": forms.TextInput(attrs={"placeholder": "UTC"}),
        }

    def clean_currency(self):
        currency = self.cleaned_data.get("currency", "").strip().upper()
        if len(currency) != 3:
            raise ValidationError("Currency must be a 3-letter ISO code (e.g. USD, EUR, GBP).")
        return currency


class MemberAddForm(forms.Form):
    username_or_email = forms.CharField(
        max_length=254,
        label="Username or Email",
        help_text="Enter the registered username or email address of the team member.",
    )
    role = forms.ChoiceField(
        choices=Role.choices,
        initial=Role.STAFF,
        label="Role",
        help_text="Owner: full access; Manager: manage catalog & stock; Staff: record stock movements.",
    )

    def __init__(self, *args, workspace=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace = workspace

    def clean_username_or_email(self):
        val = self.cleaned_data.get("username_or_email", "").strip()
        user = (
            User.objects.filter(username__iexact=val).first()
            or User.objects.filter(email__iexact=val).first()
        )
        if not user:
            raise ValidationError("No registered user found with that username or email address.")
        if (
            self.workspace
            and Membership.objects.filter(workspace=self.workspace, user=user).exists()
        ):
            raise ValidationError("This user is already a member of this workspace.")
        self.target_user = user
        return val


class MemberRoleForm(forms.ModelForm):
    class Meta:
        model = Membership
        fields = ["role"]


class WorkspaceDeleteForm(forms.Form):
    confirmation = forms.CharField(
        max_length=150,
        label="Confirm Workspace Name",
        help_text="Type the exact name of the workspace to confirm permanent deletion.",
    )

    def __init__(self, *args, workspace=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace = workspace

    def clean_confirmation(self):
        val = self.cleaned_data.get("confirmation", "").strip()
        if self.workspace and val != self.workspace.name:
            raise ValidationError("The entered name does not match the workspace name.")
        return val
