from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from orders.services import (
    APIError,
    create_order,
    dashboard_summary,
    get_order,
    get_product,
    list_categories,
    list_orders,
    list_products,
    update_order_status,
)


def index(request: HttpRequest) -> FileResponse:
    index_path = Path(settings.PROJECT_ROOT) / "static" / "index.html"
    return FileResponse(index_path.open("rb"), content_type="text/html; charset=utf-8")


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    return json_response({"status": "ok", "service": "maxway-django-backend"})


@require_GET
def categories(request: HttpRequest) -> JsonResponse:
    return handle_api(lambda: {"categories": list_categories()})


@require_GET
def products(request: HttpRequest) -> JsonResponse:
    category_slug = request.GET.get("category")
    search_query = request.GET.get("q")
    return handle_api(lambda: {"products": list_products(category_slug, search_query)})


@require_GET
def product_detail(request: HttpRequest, product_id: int) -> JsonResponse:
    return handle_api(lambda: {"product": get_product(product_id)})


@csrf_exempt
@require_POST
def orders(request: HttpRequest) -> JsonResponse:
    return handle_api(lambda: {"order": create_order(read_json(request))}, status=201)


@require_GET
def order_detail(request: HttpRequest, order_id: int) -> JsonResponse:
    return handle_api(lambda: {"order": get_order(order_id)})


@require_GET
def admin_dashboard(request: HttpRequest) -> JsonResponse:
    return handle_api(dashboard_summary)


@require_GET
def admin_orders(request: HttpRequest) -> JsonResponse:
    return handle_api(lambda: {"orders": list_orders(int(request.GET.get("limit", "50")))})


@csrf_exempt
@require_http_methods(["PATCH"])
def admin_order_status(request: HttpRequest, order_id: int) -> JsonResponse:
    return handle_api(lambda: {"order": update_order_status(order_id, read_json(request))})


def handle_api(callback, status: int = 200) -> JsonResponse:
    try:
        return json_response(callback(), status=status)
    except APIError as error:
        return json_error(error.message, error.status_code, error.code, error.details)
    except ValueError as error:
        return json_error(str(error), 400, "bad_request")


def read_json(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    if len(request.body) > 1_000_000:
        raise APIError("Request body is too large", 413, "body_too_large")
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise APIError("Request body must be valid JSON", 400, "invalid_json") from error
    if not isinstance(payload, dict):
        raise APIError("Request body must be a JSON object", 400, "invalid_json")
    return payload


def json_response(payload: dict, status: int = 200) -> JsonResponse:
    return JsonResponse(payload, status=status, json_dumps_params={"ensure_ascii": False})


def json_error(message: str, status: int, code: str, details: dict | None = None) -> JsonResponse:
    return json_response(
        {
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
        status=status,
    )
