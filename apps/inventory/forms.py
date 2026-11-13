from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from apps.catalog.models import Item
from apps.inventory.models import Location, StockBalance


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ["name", "notes", "is_active"]
        widgets = {
            "name": forms.TextInput(
                attrs={"placeholder": "e.g. Warehouse 1, Back Storage, Main Shop"}
            ),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, workspace=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace = workspace

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise ValidationError("Location name is required.")
        qs = Location.objects.filter(workspace=self.workspace, name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A location with this name already exists in this workspace.")
        return name


class StockReceiveForm(forms.Form):
    item = forms.ModelChoiceField(
        queryset=Item.objects.none(),
        label="Item to receive",
        help_text="Choose the item being added to stock.",
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.none(),
        label="Destination location",
        help_text="Where this stock is being placed.",
    )
    quantity = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Quantity received (+)",
        help_text="Positive number of units arriving.",
        widget=forms.NumberInput(attrs={"step": "any", "placeholder": "e.g. 10"}),
    )
    unit_cost = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        min_value=Decimal("0.00"),
        label="Unit purchase cost (optional)",
        help_text="Cost per unit for this delivery.",
        widget=forms.NumberInput(attrs={"step": "0.01", "placeholder": "e.g. 15.50"}),
    )
    reason = forms.CharField(
        widget=forms.TextInput(
            attrs={"placeholder": "e.g. Supplier invoice #10432, restock shipment"}
        ),
        label="Reason or reference",
        help_text="A brief note or reference document number.",
        required=True,
    )

    def __init__(
        self, *args, workspace=None, initial_item_id=None, initial_location_id=None, **kwargs
    ):
        super().__init__(*args, **kwargs)
        if workspace:
            self.fields["item"].queryset = Item.objects.filter(
                workspace=workspace, is_active=True
            ).order_by("name")
            self.fields["location"].queryset = Location.objects.filter(
                workspace=workspace, is_active=True
            ).order_by("name")

            if initial_item_id:
                self.fields["item"].initial = initial_item_id
            if initial_location_id:
                self.fields["location"].initial = initial_location_id
            else:
                first_loc = Location.objects.filter(workspace=workspace, is_active=True).first()
                if first_loc:
                    self.fields["location"].initial = first_loc


class StockUsageForm(forms.Form):
    item = forms.ModelChoiceField(
        queryset=Item.objects.none(),
        label="Item used or sold",
        help_text="Choose the item being removed from inventory.",
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.none(),
        label="Source location",
        help_text="Where the item was taken from.",
    )
    quantity = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Quantity used or sold (-)",
        help_text="Positive number of units to deduct from inventory.",
        widget=forms.NumberInput(attrs={"step": "any", "placeholder": "e.g. 2"}),
    )
    reason = forms.CharField(
        widget=forms.TextInput(
            attrs={"placeholder": "e.g. Customer sale receipt #882, internal repair use"}
        ),
        label="Reason or reference",
        help_text="Explain where or why the stock was consumed.",
        required=True,
    )

    def __init__(
        self, *args, workspace=None, initial_item_id=None, initial_location_id=None, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.workspace = workspace
        if workspace:
            self.fields["item"].queryset = Item.objects.filter(
                workspace=workspace, is_active=True
            ).order_by("name")
            self.fields["location"].queryset = Location.objects.filter(
                workspace=workspace, is_active=True
            ).order_by("name")

            if initial_item_id:
                self.fields["item"].initial = initial_item_id
            if initial_location_id:
                self.fields["location"].initial = initial_location_id
            else:
                first_loc = Location.objects.filter(workspace=workspace, is_active=True).first()
                if first_loc:
                    self.fields["location"].initial = first_loc

    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get("item")
        location = cleaned_data.get("location")
        qty = cleaned_data.get("quantity")

        if item and location and qty:
            balance = StockBalance.objects.filter(item=item, location=location).first()
            current_qty = balance.quantity if balance else Decimal("0.00")
            if current_qty < qty:
                raise ValidationError(
                    f"Insufficient stock on hand at '{location.name}'. "
                    f"Available: {current_qty} {item.get_unit_display()}, requested: {qty}."
                )
        return cleaned_data


class StockAdjustmentForm(forms.Form):
    item = forms.ModelChoiceField(
        queryset=Item.objects.none(),
        label="Item to adjust",
        help_text="Choose the item whose count is being reconciled.",
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.none(),
        label="Physical location",
        help_text="Where the physical count was conducted.",
    )
    counted_quantity = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        label="New physical counted quantity",
        help_text="The exact count of units currently found on the shelf.",
        widget=forms.NumberInput(attrs={"step": "any", "placeholder": "e.g. 45"}),
    )
    reason = forms.CharField(
        widget=forms.TextInput(
            attrs={"placeholder": "e.g. Monthly physical inventory audit, discovered damaged units"}
        ),
        label="Reason for adjustment",
        help_text="Required: Explain why this count differs from system records.",
        required=True,
    )
    confirm_adjustment = forms.BooleanField(
        required=True,
        label="I confirm that this physical count is verified and correct.",
        help_text="Check this box to confirm this inventory balance correction.",
    )

    def __init__(
        self, *args, workspace=None, initial_item_id=None, initial_location_id=None, **kwargs
    ):
        super().__init__(*args, **kwargs)
        if workspace:
            self.fields["item"].queryset = Item.objects.filter(
                workspace=workspace, is_active=True
            ).order_by("name")
            self.fields["location"].queryset = Location.objects.filter(
                workspace=workspace, is_active=True
            ).order_by("name")

            if initial_item_id:
                self.fields["item"].initial = initial_item_id
            if initial_location_id:
                self.fields["location"].initial = initial_location_id
            else:
                first_loc = Location.objects.filter(workspace=workspace, is_active=True).first()
                if first_loc:
                    self.fields["location"].initial = first_loc
