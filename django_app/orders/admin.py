from __future__ import annotations

from django.contrib import admin

from orders.models import Category, Order, OrderItem, Product, StatusHistory


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "is_popular", "is_spicy", "sort_order")
    list_filter = ("category", "is_popular", "is_spicy")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_name", "quantity", "unit_price", "line_total")
    can_delete = False


class StatusHistoryInline(admin.TabularInline):
    model = StatusHistory
    extra = 0
    readonly_fields = ("status", "note", "created_at")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "customer_name", "phone", "status", "total", "created_at")
    list_filter = ("status", "payment_method", "delivery_type")
    search_fields = ("order_number", "customer_name", "phone", "address")
    readonly_fields = ("order_number", "subtotal", "delivery_fee", "discount", "total", "created_at", "updated_at")
    inlines = (OrderItemInline, StatusHistoryInline)


@admin.register(StatusHistory)
class StatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "note", "created_at")
    list_filter = ("status",)
