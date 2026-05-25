from __future__ import annotations

from django.core.management import call_command
from django.test import Client, TestCase

from orders.models import Product


class MaxwayAPITests(TestCase):
    def setUp(self) -> None:
        call_command("seed_maxway", verbosity=0)
        self.client = Client()

    def test_catalog_endpoint_returns_seeded_products(self) -> None:
        response = self.client.get("/api/products")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(len(payload["products"]), 10)
        self.assertEqual(payload["products"][0]["image_url"].startswith("/static/assets/"), True)

    def test_order_flow(self) -> None:
        product = Product.objects.first()

        response = self.client.post(
            "/api/orders",
            data={
                "customer_name": "Ali Valiyev",
                "phone": "+998 90 123 45 67",
                "address": "Toshkent, Chilonzor 7",
                "payment_method": "cash",
                "delivery_type": "delivery",
                "items": [{"product_id": product.id, "quantity": 2}],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        order = response.json()["order"]
        self.assertEqual(order["status"], "new")
        self.assertEqual(order["subtotal"], product.price * 2)
        self.assertEqual(order["delivery_fee"], 15000)

        status_response = self.client.patch(
            f"/api/admin/orders/{order['id']}/status",
            data={"status": "preparing"},
            content_type="application/json",
        )

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["order"]["status"], "preparing")

        dashboard_response = self.client.get("/api/admin/dashboard")
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(dashboard_response.json()["orders_count"], 1)
