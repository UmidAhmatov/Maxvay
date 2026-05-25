from __future__ import annotations

import re
import secrets
from typing import Any

from django.db import transaction
from django.db.models import Avg, Count, IntegerField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from orders.models import Category, Order, OrderItem, Product, StatusHistory


class APIError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        code: str = "bad_request",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}


def list_categories() -> list[dict[str, Any]]:
    return [category_to_dict(category) for category in Category.objects.all()]


def list_products(category_slug: str | None = None, query: str | None = None) -> list[dict[str, Any]]:
    products = Product.objects.select_related("category")
    if category_slug and category_slug != "all":
        products = products.filter(category__slug=category_slug)
    if query:
        products = products.filter(name__icontains=query) | products.filter(description__icontains=query)
    return [product_to_dict(product) for product in products.distinct()]


def get_product(product_id: int) -> dict[str, Any]:
    try:
        product = Product.objects.select_related("category").get(id=product_id)
    except Product.DoesNotExist:
        raise APIError("Product not found", 404, "product_not_found") from None
    return product_to_dict(product)


@transaction.atomic
def create_order(payload: dict[str, Any]) -> dict[str, Any]:
    customer_name = _required_text(payload, "customer_name", min_length=2, max_length=80)
    phone = _clean_phone(_required_text(payload, "phone", min_length=7, max_length=30))
    address = _required_text(payload, "address", min_length=5, max_length=180)
    comment = _optional_text(payload.get("comment"), max_length=240)
    payment_method = _choice(payload.get("payment_method", Order.PaymentMethod.CASH), Order.PaymentMethod.values, "payment_method")
    delivery_type = _choice(payload.get("delivery_type", Order.DeliveryType.DELIVERY), Order.DeliveryType.values, "delivery_type")
    requested_items = _parse_order_items(payload.get("items"))

    product_ids = [item["product_id"] for item in requested_items]
    products = Product.objects.select_for_update().in_bulk(product_ids)
    missing_ids = [product_id for product_id in product_ids if product_id not in products]
    if missing_ids:
        raise APIError(
            "Some products are not available",
            404,
            "products_not_found",
            {"product_ids": missing_ids},
        )

    order_lines: list[dict[str, Any]] = []
    subtotal = 0
    for item in requested_items:
        product = products[item["product_id"]]
        quantity = item["quantity"]
        if product.stock <= 0:
            raise APIError(
                f"{product.name} is out of stock",
                409,
                "out_of_stock",
                {"product_id": product.id},
            )

        line_total = product.price * quantity
        subtotal += line_total
        order_lines.append(
            {
                "product": product,
                "product_name": product.name,
                "quantity": quantity,
                "unit_price": product.price,
                "line_total": line_total,
            }
        )

    delivery_fee = _delivery_fee(subtotal, delivery_type)
    discount = _discount(subtotal)
    total = subtotal + delivery_fee - discount

    order = Order.objects.create(
        order_number=_make_order_number(),
        customer_name=customer_name,
        phone=phone,
        address=address,
        comment=comment,
        payment_method=payment_method,
        delivery_type=delivery_type,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        discount=discount,
        total=total,
    )

    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                product=line["product"],
                product_name=line["product_name"],
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                line_total=line["line_total"],
            )
            for line in order_lines
        ]
    )
    StatusHistory.objects.create(order=order, status=Order.Status.NEW, note="Order created")
    return order_to_dict(get_order_instance(order.id))


def get_order(order_id: int) -> dict[str, Any]:
    return order_to_dict(get_order_instance(order_id))


def get_order_instance(order_id: int) -> Order:
    try:
        return (
            Order.objects.prefetch_related("items", "history")
            .annotate(
                item_count=Count("items"),
                unit_count=Coalesce(Sum("items__quantity"), Value(0), output_field=IntegerField()),
            )
            .get(id=order_id)
        )
    except Order.DoesNotExist:
        raise APIError("Order not found", 404, "order_not_found") from None


def list_orders(limit: int = 50) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 100))
    orders = (
        Order.objects.annotate(
            item_count=Count("items"),
            unit_count=Coalesce(Sum("items__quantity"), Value(0), output_field=IntegerField()),
        )
        .order_by("-id")
        .all()[:safe_limit]
    )
    return [order_summary_to_dict(order) for order in orders]


@transaction.atomic
def update_order_status(order_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    status = _choice(payload.get("status"), Order.Status.values, "status")
    note = _optional_text(payload.get("note"), max_length=180)
    try:
        order = Order.objects.select_for_update().get(id=order_id)
    except Order.DoesNotExist:
        raise APIError("Order not found", 404, "order_not_found") from None

    order.status = status
    order.save(update_fields=["status", "updated_at"])
    StatusHistory.objects.create(order=order, status=status, note=note)
    return order_to_dict(get_order_instance(order.id))


def dashboard_summary() -> dict[str, Any]:
    totals = Order.objects.aggregate(
        orders_count=Count("id"),
        revenue=Coalesce(Sum("total"), Value(0), output_field=IntegerField()),
        average_check=Avg("total"),
    )
    statuses = Order.objects.values("status").annotate(total=Count("id")).order_by("-total", "status")
    popular = (
        OrderItem.objects.values("product_name")
        .annotate(units=Coalesce(Sum("quantity"), Value(0), output_field=IntegerField()))
        .order_by("-units", "product_name")[:5]
    )

    return {
        "orders_count": int(totals["orders_count"] or 0),
        "revenue": int(totals["revenue"] or 0),
        "average_check": round(float(totals["average_check"] or 0), 2),
        "statuses": [{"status": row["status"], "total": int(row["total"])} for row in statuses],
        "popular_products": [{"product_name": row["product_name"], "units": int(row["units"])} for row in popular],
    }


def category_to_dict(category: Category) -> dict[str, Any]:
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "sort_order": category.sort_order,
    }


def product_to_dict(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "name": product.name,
        "slug": product.slug,
        "description": product.description,
        "price": product.price,
        "image_url": product.image_url,
        "calories": product.calories,
        "weight": product.weight,
        "is_spicy": product.is_spicy,
        "is_popular": product.is_popular,
        "stock": product.stock,
        "category_id": product.category_id,
        "category_name": product.category.name,
        "category_slug": product.category.slug,
    }


def order_to_dict(order: Order) -> dict[str, Any]:
    data = order_summary_to_dict(order)
    data.update(
        {
            "address": order.address,
            "comment": order.comment,
            "payment_method": order.payment_method,
            "delivery_type": order.delivery_type,
            "subtotal": order.subtotal,
            "delivery_fee": order.delivery_fee,
            "discount": order.discount,
            "items": [order_item_to_dict(item) for item in order.items.all()],
            "history": [history_to_dict(item) for item in order.history.all()],
        }
    )
    return data


def order_summary_to_dict(order: Order) -> dict[str, Any]:
    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer_name": order.customer_name,
        "phone": order.phone,
        "status": order.status,
        "total": order.total,
        "item_count": int(getattr(order, "item_count", order.items.count())),
        "unit_count": int(getattr(order, "unit_count", sum(item.quantity for item in order.items.all()))),
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
    }


def order_item_to_dict(item: OrderItem) -> dict[str, Any]:
    return {
        "product_id": item.product_id,
        "product_name": item.product_name,
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "line_total": item.line_total,
    }


def history_to_dict(item: StatusHistory) -> dict[str, Any]:
    return {
        "status": item.status,
        "note": item.note,
        "created_at": item.created_at.isoformat(),
    }


def _parse_order_items(raw_items: Any) -> list[dict[str, int]]:
    if not isinstance(raw_items, list) or not raw_items:
        raise APIError("Order must include at least one item", 400, "empty_order")

    parsed_items: list[dict[str, int]] = []
    seen_ids: set[int] = set()
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise APIError("Each order item must be an object", 400, "invalid_item")
        try:
            product_id = int(raw_item.get("product_id"))
            quantity = int(raw_item.get("quantity", 1))
        except (TypeError, ValueError):
            raise APIError("Product id and quantity must be numbers", 400, "invalid_item") from None

        if product_id <= 0:
            raise APIError("Product id must be positive", 400, "invalid_product_id")
        if quantity < 1 or quantity > 20:
            raise APIError("Quantity must be between 1 and 20", 400, "invalid_quantity")
        if product_id in seen_ids:
            raise APIError("Duplicate products are not allowed", 400, "duplicate_product")

        seen_ids.add(product_id)
        parsed_items.append({"product_id": product_id, "quantity": quantity})

    return parsed_items


def _required_text(
    payload: dict[str, Any],
    field_name: str,
    min_length: int = 1,
    max_length: int = 120,
) -> str:
    return _text(payload.get(field_name), field_name, min_length, max_length, required=True)


def _optional_text(value: Any, max_length: int = 120) -> str:
    if value in (None, ""):
        return ""
    return _text(value, "value", 0, max_length, required=False)


def _text(value: Any, field_name: str, min_length: int, max_length: int, required: bool) -> str:
    if not isinstance(value, str):
        if required:
            raise APIError(f"{field_name} is required", 400, "missing_field", {"field": field_name})
        return ""
    clean_value = re.sub(r"\s+", " ", value).strip()
    if required and len(clean_value) < min_length:
        raise APIError(f"{field_name} is too short", 400, "invalid_field", {"field": field_name})
    if len(clean_value) > max_length:
        raise APIError(f"{field_name} is too long", 400, "invalid_field", {"field": field_name})
    return clean_value


def _choice(value: Any, choices: list[str], field_name: str) -> str:
    if not isinstance(value, str) or value not in choices:
        raise APIError(
            f"{field_name} is invalid",
            400,
            "invalid_choice",
            {"field": field_name, "choices": list(choices)},
        )
    return value


def _clean_phone(value: str) -> str:
    if not re.fullmatch(r"[+0-9 ()-]{7,30}", value):
        raise APIError("Phone number is invalid", 400, "invalid_phone")
    return value


def _delivery_fee(subtotal: int, delivery_type: str) -> int:
    if delivery_type == Order.DeliveryType.PICKUP or subtotal >= 120000:
        return 0
    return 15000


def _discount(subtotal: int) -> int:
    if subtotal >= 250000:
        return int(subtotal * 0.1)
    return 0


def _make_order_number() -> str:
    for _ in range(5):
        stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
        token = secrets.token_hex(2).upper()
        order_number = f"MXW-{stamp}-{token}"
        if not Order.objects.filter(order_number=order_number).exists():
            return order_number
    raise APIError("Could not create order number", 500, "order_number_failed")
