from __future__ import annotations

from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)
    description = models.CharField(max_length=220, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, related_name="products", on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=130, unique=True)
    description = models.TextField()
    price = models.PositiveIntegerField()
    image_url = models.CharField(max_length=220)
    calories = models.PositiveIntegerField(default=0)
    weight = models.CharField(max_length=40, blank=True)
    is_spicy = models.BooleanField(default=False)
    is_popular = models.BooleanField(default=False)
    stock = models.PositiveIntegerField(default=100)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category__sort_order", "sort_order", "id"]

    def __str__(self) -> str:
        return self.name


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Yangi"
        ACCEPTED = "accepted", "Qabul qilindi"
        PREPARING = "preparing", "Tayyorlanmoqda"
        ON_WAY = "on_way", "Yetkazilmoqda"
        DELIVERED = "delivered", "Yetkazildi"
        CANCELLED = "cancelled", "Bekor qilindi"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Naqd"
        CARD = "card", "Karta"
        CLICK = "click", "Click"
        PAYME = "payme", "Payme"

    class DeliveryType(models.TextChoices):
        DELIVERY = "delivery", "Yetkazib berish"
        PICKUP = "pickup", "Olib ketish"

    order_number = models.CharField(max_length=40, unique=True)
    customer_name = models.CharField(max_length=80)
    phone = models.CharField(max_length=30)
    address = models.CharField(max_length=180)
    comment = models.CharField(max_length=240, blank=True)
    payment_method = models.CharField(max_length=12, choices=PaymentMethod.choices)
    delivery_type = models.CharField(max_length=12, choices=DeliveryType.choices, default=DeliveryType.DELIVERY)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)
    subtotal = models.PositiveIntegerField()
    delivery_fee = models.PositiveIntegerField()
    discount = models.PositiveIntegerField()
    total = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self) -> str:
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="order_items", on_delete=models.PROTECT)
    product_name = models.CharField(max_length=120)
    quantity = models.PositiveIntegerField()
    unit_price = models.PositiveIntegerField()
    line_total = models.PositiveIntegerField()

    def __str__(self) -> str:
        return f"{self.product_name} x {self.quantity}"


class StatusHistory(models.Model):
    order = models.ForeignKey(Order, related_name="history", on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=Order.Status.choices)
    note = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name_plural = "status history"

    def __str__(self) -> str:
        return f"{self.order.order_number}: {self.status}"
