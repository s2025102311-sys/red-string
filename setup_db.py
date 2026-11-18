"""Creates the database (if missing) and runs every file in sql/. Run once:  python setup_db.py"""
import os

from registry.db import get_connection, init_schema
from registry.exceptions import RegistryError


def main():
    name = os.environ.get("DB_NAME", "blood_registry")
    if not name.replace("_", "").isalnum():
        raise SystemExit("DB_NAME may only contain letters, numbers and underscores.")
    try:
        server = get_connection(with_database=False)
        with server.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4")
        server.commit()
        server.close()

        conn = get_connection()
        init_schema(conn, os.path.join(os.path.dirname(__file__), "sql"))
        conn.close()
    except RegistryError as e:
        raise SystemExit(f"Setup failed: {e}  (is MySQL running in XAMPP, and is .env correct?)")
    print(f"Database '{name}' is ready.")


if __name__ == "__main__":
    main()
