from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from apps.catalog.models import Category, Item, Supplier
from apps.inventory.models import Location


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Tools, Stationery, Beverages"}),
            "description": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Optional description."}
            ),
        }

    def __init__(self, *args, workspace=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace = workspace

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise ValidationError("Category name is required.")
        qs = Category.objects.filter(workspace=self.workspace, name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A category with this name already exists in this workspace.")
        return name


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "contact_person", "phone", "email", "address", "notes", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Acme Supplies Co."}),
            "address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class ItemForm(forms.ModelForm):
    # Optional opening balance on creation
    opening_quantity = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        min_value=Decimal("0.00"),
        label="Opening stock quantity",
        help_text="Optional starting physical quantity on hand.",
    )
    opening_location = forms.ModelChoiceField(
        queryset=Location.objects.none(),
        required=False,
        label="Storage location for opening stock",
        help_text="Where the starting stock is physically located.",
    )

    class Meta:
        model = Item
        fields = [
            "name",
            "sku",
            "category",
            "supplier",
            "unit",
            "description",
            "barcode",
            "cost_price",
            "selling_price",
            "reorder_level",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Standard Hammer 16oz"}),
            "sku": forms.TextInput(attrs={"placeholder": "e.g. HAM-001 (optional item code)"}),
            "barcode": forms.TextInput(attrs={"placeholder": "e.g. 012345678905"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, workspace=None, is_edit=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace = workspace
        self.is_edit = is_edit

        if workspace:
            self.fields["category"].queryset = Category.objects.filter(workspace=workspace)
            self.fields["supplier"].queryset = Supplier.objects.filter(
                workspace=workspace, is_active=True
            )
            self.fields["opening_location"].queryset = Location.objects.filter(
                workspace=workspace, is_active=True
            )

            # Default to first active location
            if not is_edit:
                first_loc = Location.objects.filter(workspace=workspace, is_active=True).first()
                if first_loc:
                    self.fields["opening_location"].initial = first_loc

        # If editing, hide opening quantity fields (movements handle all subsequent updates)
        if is_edit:
            self.fields.pop("opening_quantity", None)
            self.fields.pop("opening_location", None)

    def clean_sku(self):
        sku = self.cleaned_data.get("sku", "")
        if sku:
            sku = sku.strip()
            qs = Item.objects.filter(workspace=self.workspace, sku__iexact=sku)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    "An item with this item code (SKU) already exists in this workspace."
                )
        return sku or None

    def clean(self):
        cleaned_data = super().clean()
        if not self.is_edit:
            qty = cleaned_data.get("opening_quantity")
            loc = cleaned_data.get("opening_location")
            if qty and qty > Decimal("0.00") and not loc:
                raise ValidationError(
                    {"opening_location": "Please select a location for the opening stock quantity."}
                )
        return cleaned_data
