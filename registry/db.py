"""Database plumbing: connection factory, schema runner and the Transaction helper."""
import os

import pymysql
from pymysql.cursors import DictCursor

from .exceptions import DatabaseError, DuplicateError, RegistryError

try:                                   # .env is optional; real environment variables also work
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:                    # pragma: no cover
    pass

MYSQL_DUPLICATE_KEY = 1062


def _settings():
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": os.environ.get("DB_USER", "root"),
        "password": os.environ.get("DB_PASSWORD", ""),
    }


def get_connection(with_database=True):
    """Opens a MySQL connection. autocommit is OFF so commit/rollback are explicit."""
    try:
        return pymysql.connect(
            database=os.environ.get("DB_NAME", "blood_registry") if with_database else None,
            cursorclass=DictCursor,
            charset="utf8mb4",
            autocommit=False,
            **_settings(),
        )
    except Exception as e:
        raise DatabaseError("Cannot reach the database right now. Please try again later.") from e


def split_statements(script):
    """Splits an SQL script on ';' but not on semicolons inside quoted strings."""
    statements, current, quote = [], [], None
    in_comment = False
    previous = ""
    for ch in script:
        if in_comment:                               # "-- comment" runs to the end of the line
            if ch == "\n":
                in_comment = False
            continue
        if not quote and ch == "-" and previous == "-":
            current.pop()                            # drop the first '-' we already kept
            in_comment = True
            previous = ""
            continue
        previous = ch
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            current.append(ch)
        elif ch == ";":
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def init_schema(conn, sql_dir):
    """Runs every .sql file in `sql_dir` in filename order (01_schema.sql, 02_seed.sql, ...)."""
    for name in sorted(os.listdir(sql_dir)):
        if not name.endswith(".sql"):
            continue
        with open(os.path.join(sql_dir, name), encoding="utf-8") as f:
            statements = split_statements(f.read())
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
        conn.commit()


class Transaction:
    """Context manager for a unit of work.

        with Transaction(conn, "Could not save."):
            repo_a.add(...)
            repo_b.add(...)

    Commits when the block finishes, rolls back when anything fails. Deliberate
    RegistryErrors pass through unchanged; any other error becomes a DatabaseError.
    """

    def __init__(self, conn, error_message="Something went wrong while saving. Please try again.",
                 duplicate_message="That value is already taken."):
        self.conn = conn
        self.error_message = error_message
        self.duplicate_message = duplicate_message

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            try:
                self.conn.commit()
            except Exception as e:
                self.conn.rollback()
                raise DatabaseError(self.error_message) from e
            return False

        self.conn.rollback()
        if issubclass(exc_type, RegistryError):
            return False
        if exc.args and exc.args[0] == MYSQL_DUPLICATE_KEY:
            raise DuplicateError(self.duplicate_message) from exc
        raise DatabaseError(self.error_message) from exc
