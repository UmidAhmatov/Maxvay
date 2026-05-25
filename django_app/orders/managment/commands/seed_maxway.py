from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from orders.models import Category, Product


CATEGORIES = [
    ("Lavash", "lavash", "Tandir noni, sous va yangi masalliqlar", 10),
    ("Burger", "burger", "Mol goshti, tovuq va pishloqli burgerlar", 20),
    ("Pizza", "pizza", "Issiq, to'yimli va ko'p pishloqli pizza", 30),
    ("Setlar", "sets", "Do'stlar va oila uchun tayyor kombinatsiyalar", 40),
    ("Ichimlik", "drinks", "Sovuq ichimliklar va limonadlar", 50),
    ("Desert", "dessert", "Shirin yakun uchun desertlar", 60),
]


PRODUCTS = [
    ("lavash", "Max Lavash", "max-lavash", "Mol goshti, chips, pomidor, bodring, salat va maxsus qizil sous.", 42000, "/static/assets/lavash.png", 650, "410 g", False, True, 10),
    ("lavash", "Tovuqli Lavash", "tovuqli-lavash", "Grill tovuq, qaymoqli sous, salat bargi va yangi sabzavotlar.", 36000, "/static/assets/lavash.png", 560, "380 g", False, False, 20),
    ("burger", "Cheese Burger", "cheese-burger", "Yumshoq bulochka, mol go'shti kotleti, cheddar, tuzlangan bodring.", 39000, "/static/assets/burger.png", 710, "320 g", False, True, 10),
    ("burger", "Spicy Chicken Burger", "spicy-chicken-burger", "Qarsildoq tovuq, jalapeno, pishloq va achchiq sous.", 37000, "/static/assets/burger.png", 680, "300 g", True, False, 20),
    ("pizza", "Pepperoni Pizza", "pepperoni-pizza", "Pepperoni, mozzarella, tomat sousi va oregano.", 78000, "/static/assets/pizza.png", 1100, "30 sm", True, True, 10),
    ("pizza", "Margarita Pizza", "margarita-pizza", "Mozzarella, tomat sousi, reyhan va zaytun moyi.", 69000, "/static/assets/pizza.png", 950, "30 sm", False, False, 20),
    ("sets", "Family Set", "family-set", "2 lavash, 2 burger, kartoshka fri va 2 ichimlik.", 159000, "/static/assets/combo.png", 2600, "4 kishi", False, True, 10),
    ("sets", "Student Set", "student-set", "Burger, kartoshka fri va limonad.", 59000, "/static/assets/combo.png", 1050, "1 kishi", False, False, 20),
    ("drinks", "Berry Limonad", "berry-limonad", "Rezavor mevali sovuq limonad, muz va yalpiz bilan.", 18000, "/static/assets/drink.png", 120, "450 ml", False, True, 10),
    ("drinks", "Cola", "cola", "Sovuq gazli ichimlik.", 12000, "/static/assets/drink.png", 140, "500 ml", False, False, 20),
    ("dessert", "Choco Cake", "choco-cake", "Shokoladli biskvit, krem va karamelli sous.", 26000, "/static/assets/dessert.png", 430, "160 g", False, True, 10),
    ("dessert", "Donut", "donut", "Vanilli glazur, rangli sepma va yumshoq xamir.", 17000, "/static/assets/dessert.png", 310, "90 g", False, False, 20),
]


class Command(BaseCommand):
    help = "Seed Maxway categories, products, and optional local demo admin."

    def handle(self, *args, **options) -> None:
        categories_by_slug: dict[str, Category] = {}
        for name, slug, description, sort_order in CATEGORIES:
            category, _ = Category.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": description,
                    "sort_order": sort_order,
                },
            )
            categories_by_slug[slug] = category

        for (
            category_slug,
            name,
            slug,
            description,
            price,
            image_url,
            calories,
            weight,
            is_spicy,
            is_popular,
            sort_order,
        ) in PRODUCTS:
            Product.objects.update_or_create(
                slug=slug,
                defaults={
                    "category": categories_by_slug[category_slug],
                    "name": name,
                    "description": description,
                    "price": price,
                    "image_url": image_url,
                    "calories": calories,
                    "weight": weight,
                    "is_spicy": is_spicy,
                    "is_popular": is_popular,
                    "sort_order": sort_order,
                    "stock": 100,
                },
            )

        if os.environ.get("DJANGO_CREATE_DEMO_ADMIN", "0") == "1":
            self._create_demo_admin()

        self.stdout.write(self.style.SUCCESS("Maxway seed data is ready."))

    def _create_demo_admin(self) -> None:
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@maxway.local")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "admin12345")
        User = get_user_model()

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
            self.stdout.write(self.style.WARNING(f"Demo admin created: {username} / {password}"))
        elif not user.is_staff or not user.is_superuser:
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=["is_staff", "is_superuser"])
