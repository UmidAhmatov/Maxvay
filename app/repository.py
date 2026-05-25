from __future__ import annotations

import re
import secrets
from datetime import datetime
from typing import Any

from app.database import connect


VALID_ORDER_STATUSES = (
    "new",
    "accepted",
    "preparing",
    "on_way",
    "delivered",
    "cancelled",
)
VALID_PAYMENT_METHODS = ("cash", "card", "click", "payme")
VALID_DELIVERY_TYPES = ("delivery", "pickup")


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
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, name, slug, description, sort_order
            FROM categories
            ORDER BY sort_order, id
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_products(category_slug: str | None = None, query: str | None = None) -> list[dict[str, Any]]:
    filters: list[str] = []
    params: list[Any] = []

    if category_slug and category_slug != "all":
        filters.append("c.slug = ?")
        params.append(category_slug)

    if query:
        filters.append("(LOWER(p.name) LIKE ? OR LOWER(p.description) LIKE ?)")
        like_query = f"%{query.lower()}%"
        params.extend([like_query, like_query])

    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""

    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT
                p.id,
                p.name,
                p.slug,
                p.description,
                p.price,
                p.image_url,
                p.calories,
                p.weight,
                p.is_spicy,
                p.is_popular,
                p.stock,
                c.id AS category_id,
                c.name AS category_name,
                c.slug AS category_slug
            FROM products p
            JOIN categories c ON c.id = p.category_id
            {where_sql}
            ORDER BY c.sort_order, p.sort_order, p.id
            """,
            params,
        ).fetchall()

    return [_normalize_product(row) for row in rows]


def get_product(product_id: int) -> dict[str, Any]:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                p.id,
                p.name,
                p.slug,
                p.description,
                p.price,
                p.image_url,
                p.calories,
                p.weight,
                p.is_spicy,
                p.is_popular,
                p.stock,
                c.id AS category_id,
                c.name AS category_name,
                c.slug AS category_slug
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE p.id = ?
            """,
            (product_id,),
        ).fetchone()

    if row is None:
        raise APIError("Product not found", 404, "product_not_found")
    return _normalize_product(row)


def create_order(payload: dict[str, Any]) -> dict[str, Any]:
    customer_name = _required_text(payload, "customer_name", min_length=2, max_length=80)
    phone = _clean_phone(_required_text(payload, "phone", min_length=7, max_length=30))
    address = _required_text(payload, "address", min_length=5, max_length=180)
    comment = _optional_text(payload.get("comment"), max_length=240)
    payment_method = _choice(payload.get("payment_method", "cash"), VALID_PAYMENT_METHODS, "payment_method")
    delivery_type = _choice(payload.get("delivery_type", "delivery"), VALID_DELIVERY_TYPES, "delivery_type")
    requested_items = _parse_order_items(payload.get("items"))

    product_ids = [item["product_id"] for item in requested_items]
    with connect() as connection:
        products = _load_products_by_id(connection, product_ids)
        missing_ids = [product_id for product_id in product_ids if product_id not in products]
        if missing_ids:
            raise APIError(
                "Some products are not available",
                404,
                "products_not_found",
                {"product_ids": missing_ids},
            )

        order_lines = []
        subtotal = 0
        for item in requested_items:
            product = products[item["product_id"]]
            quantity = item["quantity"]
            if int(product["stock"]) <= 0:
                raise APIError(
                    f"{product['name']} is out of stock",
                    409,
                    "out_of_stock",
                    {"product_id": product["id"]},
                )
            line_total = int(product["price"]) * quantity
            subtotal += line_total
            order_lines.append(
                {
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "quantity": quantity,
                    "unit_price": int(product["price"]),
                    "line_total": line_total,
                }
            )

        delivery_fee = _delivery_fee(subtotal, delivery_type)
        discount = _discount(subtotal)
        total = subtotal + delivery_fee - discount
        order_number = _make_order_number()

        cursor = connection.execute(
            """
            INSERT INTO orders (
                order_number, customer_name, phone, address, comment,
                payment_method, delivery_type, subtotal, delivery_fee, discount, total
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_number,
                customer_name,
                phone,
                address,
                comment,
                payment_method,
                delivery_type,
                subtotal,
                delivery_fee,
                discount,
                total,
            ),
        )
        order_id = int(cursor.lastrowid)

        connection.executemany(
            """
            INSERT INTO order_items (
                order_id, product_id, product_name, quantity, unit_price, line_total
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    order_id,
                    line["product_id"],
                    line["product_name"],
                    line["quantity"],
                    line["unit_price"],
                    line["line_total"],
                )
                for line in order_lines
            ],
        )
        connection.execute(
            "INSERT INTO status_history (order_id, status, note) VALUES (?, ?, ?)",
            (order_id, "new", "Order created"),
        )
        return _get_order(connection, order_id)


def get_order(order_id: int) -> dict[str, Any]:
    with connect() as connection:
        return _get_order(connection, order_id)


def list_orders(limit: int = 50) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 100))
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT
                o.*,
                COUNT(oi.id) AS item_count,
                SUM(oi.quantity) AS unit_count
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            GROUP BY o.id
            ORDER BY o.id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    return [_normalize_order_summary(row) for row in rows]


def update_order_status(order_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    status = _choice(payload.get("status"), VALID_ORDER_STATUSES, "status")
    note = _optional_text(payload.get("note"), max_length=180)

    with connect() as connection:
        existing = connection.execute("SELECT id FROM orders WHERE id = ?", (order_id,)).fetchone()
        if existing is None:
            raise APIError("Order not found", 404, "order_not_found")

        connection.execute(
            """
            UPDATE orders
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, order_id),
        )
        connection.execute(
            "INSERT INTO status_history (order_id, status, note) VALUES (?, ?, ?)",
            (order_id, status, note),
        )
        return _get_order(connection, order_id)


def dashboard_summary() -> dict[str, Any]:
    with connect() as connection:
        totals = connection.execute(
            """
            SELECT
                COUNT(*) AS orders_count,
                COALESCE(SUM(total), 0) AS revenue,
                COALESCE(AVG(total), 0) AS average_check
            FROM orders
            """
        ).fetchone()
        statuses = connection.execute(
            """
            SELECT status, COUNT(*) AS total
            FROM orders
            GROUP BY status
            ORDER BY total DESC
            """
        ).fetchall()
        popular = connection.execute(
            """
            SELECT product_name, SUM(quantity) AS units
            FROM order_items
            GROUP BY product_name
            ORDER BY units DESC, product_name
            LIMIT 5
            """
        ).fetchall()

    return {
        "orders_count": int(totals["orders_count"]),
        "revenue": int(totals["revenue"]),
        "average_check": round(float(totals["average_check"]), 2),
        "statuses": [_row_to_dict(row) for row in statuses],
        "popular_products": [_row_to_dict(row) for row in popular],
    }


def _get_order(connection, order_id: int) -> dict[str, Any]:
    order = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise APIError("Order not found", 404, "order_not_found")

    items = connection.execute(
        """
        SELECT product_id, product_name, quantity, unit_price, line_total
        FROM order_items
        WHERE order_id = ?
        ORDER BY id
        """,
        (order_id,),
    ).fetchall()
    history = connection.execute(
        """
        SELECT status, note, created_at
        FROM status_history
        WHERE order_id = ?
        ORDER BY id
        """,
        (order_id,),
    ).fetchall()

    order_data = _normalize_order(_row_to_dict(order))
    order_data["items"] = [_row_to_dict(item) for item in items]
    order_data["history"] = [_row_to_dict(item) for item in history]
    return order_data


def _load_products_by_id(connection, product_ids: list[int]) -> dict[int, dict[str, Any]]:
    placeholders = ",".join("?" for _ in product_ids)
    rows = connection.execute(
        f"""
        SELECT id, name, price, stock
        FROM products
        WHERE id IN ({placeholders})
        """,
        product_ids,
    ).fetchall()
    return {int(row["id"]): _row_to_dict(row) for row in rows}


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


def _choice(value: Any, choices: tuple[str, ...], field_name: str) -> str:
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
    if delivery_type == "pickup" or subtotal >= 120000:
        return 0
    return 15000


def _discount(subtotal: int) -> int:
    if subtotal >= 250000:
        return int(subtotal * 0.1)
    return 0


def _make_order_number() -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    token = secrets.token_hex(2).upper()
    return f"MXW-{stamp}-{token}"


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row)


def _normalize_product(row: Any) -> dict[str, Any]:
    product = _row_to_dict(row)
    product["is_spicy"] = bool(product["is_spicy"])
    product["is_popular"] = bool(product["is_popular"])
    return product


def _normalize_order(order: dict[str, Any]) -> dict[str, Any]:
    for key in ("subtotal", "delivery_fee", "discount", "total"):
        order[key] = int(order[key])
    return order


def _normalize_order_summary(row: Any) -> dict[str, Any]:
    order = _normalize_order(_row_to_dict(row))
    order["item_count"] = int(order["item_count"] or 0)
    order["unit_count"] = int(order["unit_count"] or 0)
    return order
