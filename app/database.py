from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "maxway.sqlite3"


def get_db_path() -> Path:
    configured_path = os.environ.get("MAXWAY_DB_PATH")
    return Path(configured_path).resolve() if configured_path else DEFAULT_DB_PATH


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL REFERENCES categories(id),
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                price INTEGER NOT NULL CHECK (price >= 0),
                image_url TEXT NOT NULL,
                calories INTEGER NOT NULL DEFAULT 0,
                weight TEXT NOT NULL DEFAULT '',
                is_spicy INTEGER NOT NULL DEFAULT 0,
                is_popular INTEGER NOT NULL DEFAULT 0,
                stock INTEGER NOT NULL DEFAULT 100,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT NOT NULL,
                comment TEXT NOT NULL DEFAULT '',
                payment_method TEXT NOT NULL,
                delivery_type TEXT NOT NULL DEFAULT 'delivery',
                status TEXT NOT NULL DEFAULT 'new',
                subtotal INTEGER NOT NULL,
                delivery_fee INTEGER NOT NULL,
                discount INTEGER NOT NULL,
                total INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id),
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                unit_price INTEGER NOT NULL,
                line_total INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                status TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        if _table_is_empty(connection, "categories"):
            _seed_categories(connection)

        if _table_is_empty(connection, "products"):
            _seed_products(connection)


def _table_is_empty(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(f"SELECT COUNT(*) AS total FROM {table_name}").fetchone()
    return int(row["total"]) == 0


def _seed_categories(connection: sqlite3.Connection) -> None:
    categories = [
        ("Lavash", "lavash", "Tandir noni, sous va yangi masalliqlar", 10),
        ("Burger", "burger", "Mol goshti, tovuq va pishloqli burgerlar", 20),
        ("Pizza", "pizza", "Issiq, to'yimli va ko'p pishloqli pizza", 30),
        ("Setlar", "sets", "Do'stlar va oila uchun tayyor kombinatsiyalar", 40),
        ("Ichimlik", "drinks", "Sovuq ichimliklar va limonadlar", 50),
        ("Desert", "dessert", "Shirin yakun uchun desertlar", 60),
    ]
    connection.executemany(
        """
        INSERT INTO categories (name, slug, description, sort_order)
        VALUES (?, ?, ?, ?)
        """,
        categories,
    )


def _seed_products(connection: sqlite3.Connection) -> None:
    categories = {
        row["slug"]: row["id"]
        for row in connection.execute("SELECT id, slug FROM categories").fetchall()
    }
    products = [
        (
            categories["lavash"],
            "Max Lavash",
            "max-lavash",
            "Mol goshti, chips, pomidor, bodring, salat va maxsus qizil sous.",
            42000,
            "/static/assets/lavash.png",
            650,
            "410 g",
            0,
            1,
            10,
        ),
        (
            categories["lavash"],
            "Tovuqli Lavash",
            "tovuqli-lavash",
            "Grill tovuq, qaymoqli sous, salat bargi va yangi sabzavotlar.",
            36000,
            "/static/assets/lavash.png",
            560,
            "380 g",
            0,
            0,
            20,
        ),
        (
            categories["burger"],
            "Cheese Burger",
            "cheese-burger",
            "Yumshoq bulochka, mol go'shti kotleti, cheddar, tuzlangan bodring.",
            39000,
            "/static/assets/burger.png",
            710,
            "320 g",
            0,
            1,
            10,
        ),
        (
            categories["burger"],
            "Spicy Chicken Burger",
            "spicy-chicken-burger",
            "Qarsildoq tovuq, jalapeno, pishloq va achchiq sous.",
            37000,
            "/static/assets/burger.png",
            680,
            "300 g",
            1,
            0,
            20,
        ),
        (
            categories["pizza"],
            "Pepperoni Pizza",
            "pepperoni-pizza",
            "Pepperoni, mozzarella, tomat sousi va oregano.",
            78000,
            "/static/assets/pizza.png",
            1100,
            "30 sm",
            1,
            1,
            10,
        ),
        (
            categories["pizza"],
            "Margarita Pizza",
            "margarita-pizza",
            "Mozzarella, tomat sousi, reyhan va zaytun moyi.",
            69000,
            "/static/assets/pizza.png",
            950,
            "30 sm",
            0,
            0,
            20,
        ),
        (
            categories["sets"],
            "Family Set",
            "family-set",
            "2 lavash, 2 burger, kartoshka fri va 2 ichimlik.",
            159000,
            "/static/assets/combo.png",
            2600,
            "4 kishi",
            0,
            1,
            10,
        ),
        (
            categories["sets"],
            "Student Set",
            "student-set",
            "Burger, kartoshka fri va limonad.",
            59000,
            "/static/assets/combo.png",
            1050,
            "1 kishi",
            0,
            0,
            20,
        ),
        (
            categories["drinks"],
            "Berry Limonad",
            "berry-limonad",
            "Rezavor mevali sovuq limonad, muz va yalpiz bilan.",
            18000,
            "/static/assets/drink.png",
            120,
            "450 ml",
            0,
            1,
            10,
        ),
        (
            categories["drinks"],
            "Cola",
            "cola",
            "Sovuq gazli ichimlik.",
            12000,
            "/static/assets/drink.png",
            140,
            "500 ml",
            0,
            0,
            20,
        ),
        (
            categories["dessert"],
            "Choco Cake",
            "choco-cake",
            "Shokoladli biskvit, krem va karamelli sous.",
            26000,
            "/static/assets/dessert.png",
            430,
            "160 g",
            0,
            1,
            10,
        ),
        (
            categories["dessert"],
            "Donut",
            "donut",
            "Vanilli glazur, rangli sepma va yumshoq xamir.",
            17000,
            "/static/assets/dessert.png",
            310,
            "90 g",
            0,
            0,
            20,
        ),
    ]
    connection.executemany(
        """
        INSERT INTO products (
            category_id, name, slug, description, price, image_url, calories,
            weight, is_spicy, is_popular, sort_order
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        products,
    )
