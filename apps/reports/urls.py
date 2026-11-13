from django.urls import path

from apps.reports import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_index_view, name="index"),
    path("stock/", views.stock_summary_report_view, name="stock_summary"),
    path("low-stock/", views.low_stock_report_view, name="low_stock"),
    path("movements/", views.movement_history_report_view, name="movements"),
    path("export/items/", views.csv_export_items_view, name="export_items"),
    path("export/stock/", views.csv_export_stock_view, name="export_stock"),
    path("import/template/", views.csv_template_download_view, name="csv_template"),
    path("import/", views.csv_import_view, name="csv_import"),
]
