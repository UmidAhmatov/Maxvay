from __future__ import annotations

import os
from http.server import ThreadingHTTPServer

from app.database import get_db_path, initialize_database
from app.server import create_server


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))

    initialize_database()
    server: ThreadingHTTPServer = create_server(host, port)

    print("Maxway backend started")
    print(f"Web: http://{host}:{port}")
    print(f"API health: http://{host}:{port}/api/health")
    print(f"SQLite: {get_db_path()}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Maxway backend...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
