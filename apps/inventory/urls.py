from django.urls import path

from apps.inventory import views

app_name = "inventory"

urlpatterns = [
    # Movements
    path("movements/", views.movement_list_view, name="movement_list"),
    path("receive/", views.receive_stock_view, name="receive_stock"),
    path("use/", views.use_stock_view, name="use_stock"),
    path("adjust/", views.adjust_stock_view, name="adjust_stock"),
    path("api/balance/", views.balance_lookup_api, name="balance_api"),
    # Locations
    path("locations/", views.location_list_view, name="location_list"),
    path("locations/new/", views.location_create_view, name="location_create"),
    path("locations/<int:location_id>/edit/", views.location_edit_view, name="location_edit"),
]
