from __future__ import annotations

from django.contrib import admin
from django.urls import path

from orders import views


urlpatterns = [
    path("", views.index, name="index"),
    path("admin/", admin.site.urls),
    path("api/health", views.health, name="api-health"),
    path("api/categories", views.categories, name="api-categories"),
    path("api/products", views.products, name="api-products"),
    path("api/products/<int:product_id>", views.product_detail, name="api-product-detail"),
    path("api/orders", views.orders, name="api-orders"),
    path("api/orders/<int:order_id>", views.order_detail, name="api-order-detail"),
    path("api/admin/dashboard", views.admin_dashboard, name="api-admin-dashboard"),
    path("api/admin/orders", views.admin_orders, name="api-admin-orders"),
    path("api/admin/orders/<int:order_id>/status", views.admin_order_status, name="api-admin-order-status"),
]
