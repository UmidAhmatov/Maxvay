from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.database import ROOT_DIR
from app.repository import (
    APIError,
    dashboard_summary,
    create_order,
    get_order,
    get_product,
    list_categories,
    list_orders,
    list_products,
    update_order_status,
)


STATIC_DIR = ROOT_DIR / "static"


class MaxwayRequestHandler(BaseHTTPRequestHandler):
    server_version = "MaxwayBackend/1.0"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        if parsed_url.path.startswith("/api/"):
            try:
                self._dispatch_api_get(parsed_url)
            except APIError as error:
                self._send_json_error(error.message, error.status_code, error.code, error.details)
            return
        self._serve_static(parsed_url.path)

    def do_POST(self) -> None:
        parsed_url = urlparse(self.path)
        if parsed_url.path == "/api/orders":
            self._handle_api(lambda: create_order(self._read_json()), HTTPStatus.CREATED)
            return
        self._send_json_error("Endpoint not found", HTTPStatus.NOT_FOUND, "not_found")

    def do_PATCH(self) -> None:
        parsed_url = urlparse(self.path)
        parts = _path_parts(parsed_url.path)
        if len(parts) == 5 and parts[:2] == ["api", "admin"] and parts[2] == "orders" and parts[4] == "status":
            try:
                order_id = _parse_positive_int(parts[3], "order_id")
            except APIError as error:
                self._send_json_error(error.message, error.status_code, error.code, error.details)
                return
            self._handle_api(lambda: update_order_status(order_id, self._read_json()))
            return
        self._send_json_error("Endpoint not found", HTTPStatus.NOT_FOUND, "not_found")

    def log_message(self, format: str, *args) -> None:
        print(f"[Maxway] {self.address_string()} - {format % args}")

    def _dispatch_api_get(self, parsed_url) -> None:
        parts = _path_parts(parsed_url.path)
        query = parse_qs(parsed_url.query)

        if parsed_url.path == "/api/health":
            self._send_json({"status": "ok", "service": "maxway-backend"})
            return

        if parsed_url.path == "/api/categories":
            self._handle_api(lambda: {"categories": list_categories()})
            return

        if parsed_url.path == "/api/products":
            category_slug = _first(query.get("category"))
            search_query = _first(query.get("q"))
            self._handle_api(lambda: {"products": list_products(category_slug, search_query)})
            return

        if len(parts) == 3 and parts[:2] == ["api", "products"]:
            product_id = _parse_positive_int(parts[2], "product_id")
            self._handle_api(lambda: {"product": get_product(product_id)})
            return

        if len(parts) == 3 and parts[:2] == ["api", "orders"]:
            order_id = _parse_positive_int(parts[2], "order_id")
            self._handle_api(lambda: {"order": get_order(order_id)})
            return

        if parsed_url.path == "/api/admin/orders":
            limit = int(_first(query.get("limit"), "50"))
            self._handle_api(lambda: {"orders": list_orders(limit)})
            return

        if parsed_url.path == "/api/admin/dashboard":
            self._handle_api(lambda: dashboard_summary())
            return

        self._send_json_error("Endpoint not found", HTTPStatus.NOT_FOUND, "not_found")

    def _handle_api(self, callback, status: HTTPStatus = HTTPStatus.OK) -> None:
        try:
            payload = callback()
        except APIError as error:
            self._send_json_error(error.message, error.status_code, error.code, error.details)
            return
        except ValueError as error:
            self._send_json_error(str(error), HTTPStatus.BAD_REQUEST, "bad_request")
            return
        self._send_json(payload, status)

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        if content_length <= 0:
            return {}
        if content_length > 1_000_000:
            raise APIError("Request body is too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "body_too_large")

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise APIError("Request body must be valid JSON", HTTPStatus.BAD_REQUEST, "invalid_json") from error

        if not isinstance(payload, dict):
            raise APIError("Request body must be a JSON object", HTTPStatus.BAD_REQUEST, "invalid_json")
        return payload

    def _serve_static(self, request_path: str) -> None:
        if request_path in ("", "/", "/index.html"):
            file_path = STATIC_DIR / "index.html"
        elif request_path.startswith("/static/"):
            file_path = ROOT_DIR / request_path.lstrip("/")
        else:
            file_path = STATIC_DIR / "index.html"

        try:
            resolved_path = file_path.resolve()
            resolved_path.relative_to(ROOT_DIR)
        except ValueError:
            self._send_json_error("File not found", HTTPStatus.NOT_FOUND, "not_found")
            return

        if not resolved_path.is_file():
            self._send_json_error("File not found", HTTPStatus.NOT_FOUND, "not_found")
            return

        content_type, _ = mimetypes.guess_type(str(resolved_path))
        body = resolved_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if resolved_path.name == "index.html" else "public, max-age=3600")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_json_error(
        self,
        message: str,
        status: int | HTTPStatus,
        code: str,
        details: dict | None = None,
    ) -> None:
        self._send_json(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {},
                }
            },
            HTTPStatus(status),
        )

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), MaxwayRequestHandler)


def _path_parts(path: str) -> list[str]:
    return [part for part in path.split("/") if part]


def _parse_positive_int(value: str, field_name: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise APIError(f"{field_name} must be a number", HTTPStatus.BAD_REQUEST, "invalid_id") from None
    if number <= 0:
        raise APIError(f"{field_name} must be positive", HTTPStatus.BAD_REQUEST, "invalid_id")
    return number


def _first(values: list[str] | None, default: str | None = None) -> str | None:
    if not values:
        return default
    return values[0]
