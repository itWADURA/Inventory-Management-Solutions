from django.urls import path

from apps.catalog import views

app_name = "catalog"

urlpatterns = [
    # Items
    path("", views.item_list_view, name="item_list"),
    path("items/new/", views.item_create_view, name="item_create"),
    path("items/<int:item_id>/", views.item_detail_view, name="item_detail"),
    path("items/<int:item_id>/edit/", views.item_edit_view, name="item_edit"),
    path("items/<int:item_id>/archive/", views.item_archive_view, name="item_archive"),
    # Categories
    path("categories/", views.category_list_view, name="category_list"),
    path("categories/new/", views.category_create_view, name="category_create"),
    path("categories/<int:category_id>/edit/", views.category_edit_view, name="category_edit"),
    path(
        "categories/<int:category_id>/delete/", views.category_delete_view, name="category_delete"
    ),
    # Suppliers
    path("suppliers/", views.supplier_list_view, name="supplier_list"),
    path("suppliers/new/", views.supplier_create_view, name="supplier_create"),
    path("suppliers/<int:supplier_id>/edit/", views.supplier_edit_view, name="supplier_edit"),
    path("suppliers/<int:supplier_id>/delete/", views.supplier_delete_view, name="supplier_delete"),
]
