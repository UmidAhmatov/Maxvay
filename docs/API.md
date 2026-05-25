# Maxway API

Base URL: `http://127.0.0.1:8000`

Backend varianti: Django + SQLite. Docker bilan ishga tushirish:

```powershell
docker compose up --build
```

## Health

```http
GET /api/health
```

## Kategoriyalar

```http
GET /api/categories
```

## Mahsulotlar

```http
GET /api/products
GET /api/products?category=lavash
GET /api/products?q=burger
GET /api/products/1
```

## Buyurtma yaratish

```http
POST /api/orders
Content-Type: application/json
```

```json
{
  "customer_name": "Ali Valiyev",
  "phone": "+998 90 123 45 67",
  "address": "Toshkent, Chilonzor 7",
  "payment_method": "cash",
  "delivery_type": "delivery",
  "comment": "Qo'ng'iroq qilib keling",
  "items": [
    { "product_id": 1, "quantity": 2 },
    { "product_id": 9, "quantity": 1 }
  ]
}
```

`payment_method`: `cash`, `card`, `click`, `payme`

`delivery_type`: `delivery`, `pickup`

## Buyurtmani ko'rish

```http
GET /api/orders/1
```

## Admin

```http
GET /api/admin/dashboard
GET /api/admin/orders?limit=50
PATCH /api/admin/orders/1/status
```

Status yangilash uchun body:

```json
{
  "status": "preparing",
  "note": "Oshxonaga uzatildi"
}
```

Statuslar: `new`, `accepted`, `preparing`, `on_way`, `delivered`, `cancelled`
