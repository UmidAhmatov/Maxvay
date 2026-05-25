from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("slug", models.SlugField(max_length=90, unique=True)),
                ("description", models.CharField(blank=True, max_length=220)),
                ("sort_order", models.PositiveIntegerField(default=0)),
            ],
            options={
                "verbose_name_plural": "categories",
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_number", models.CharField(max_length=40, unique=True)),
                ("customer_name", models.CharField(max_length=80)),
                ("phone", models.CharField(max_length=30)),
                ("address", models.CharField(max_length=180)),
                ("comment", models.CharField(blank=True, max_length=240)),
                (
                    "payment_method",
                    models.CharField(
                        choices=[("cash", "Naqd"), ("card", "Karta"), ("click", "Click"), ("payme", "Payme")],
                        max_length=12,
                    ),
                ),
                (
                    "delivery_type",
                    models.CharField(
                        choices=[("delivery", "Yetkazib berish"), ("pickup", "Olib ketish")],
                        default="delivery",
                        max_length=12,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "Yangi"),
                            ("accepted", "Qabul qilindi"),
                            ("preparing", "Tayyorlanmoqda"),
                            ("on_way", "Yetkazilmoqda"),
                            ("delivered", "Yetkazildi"),
                            ("cancelled", "Bekor qilindi"),
                        ],
                        default="new",
                        max_length=16,
                    ),
                ),
                ("subtotal", models.PositiveIntegerField()),
                ("delivery_fee", models.PositiveIntegerField()),
                ("discount", models.PositiveIntegerField()),
                ("total", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("slug", models.SlugField(max_length=130, unique=True)),
                ("description", models.TextField()),
                ("price", models.PositiveIntegerField()),
                ("image_url", models.CharField(max_length=220)),
                ("calories", models.PositiveIntegerField(default=0)),
                ("weight", models.CharField(blank=True, max_length=40)),
                ("is_spicy", models.BooleanField(default=False)),
                ("is_popular", models.BooleanField(default=False)),
                ("stock", models.PositiveIntegerField(default=100)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="products",
                        to="orders.category",
                    ),
                ),
            ],
            options={
                "ordering": ["category__sort_order", "sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product_name", models.CharField(max_length=120)),
                ("quantity", models.PositiveIntegerField()),
                ("unit_price", models.PositiveIntegerField()),
                ("line_total", models.PositiveIntegerField()),
                (
                    "order",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="orders.order"),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="order_items",
                        to="orders.product",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="StatusHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "Yangi"),
                            ("accepted", "Qabul qilindi"),
                            ("preparing", "Tayyorlanmoqda"),
                            ("on_way", "Yetkazilmoqda"),
                            ("delivered", "Yetkazildi"),
                            ("cancelled", "Bekor qilindi"),
                        ],
                        max_length=16,
                    ),
                ),
                ("note", models.CharField(blank=True, max_length=180)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "order",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="history", to="orders.order"),
                ),
            ],
            options={
                "verbose_name_plural": "status history",
                "ordering": ["id"],
            },
        ),
    ]
