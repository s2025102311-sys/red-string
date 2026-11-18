"""A fake database connection. No MySQL needed: it records every statement, hands back
canned rows, can be told to fail, and checks that every query uses %s placeholders."""


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.lastrowid = None
        self.rowcount = 1
        self._rows = []

    def execute(self, sql, params=()):
        # The rubric: %s parameters only. Values must travel in a tuple, never inside the SQL text.
        assert isinstance(params, (tuple, list)), "parameters must be passed separately"
        assert "?" not in sql, "use %s placeholders, not ?"
        assert sql.count("%s") == len(params), f"placeholder/parameter mismatch in: {sql}"

        if self.conn.fail_on and self.conn.fail_on in sql:
            raise RuntimeError("simulated database failure")
        self.conn.executed.append((sql, tuple(params)))
        self._rows = self.conn.rows_for(sql)
        self.conn.next_id += 1
        self.lastrowid = self.conn.next_id

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConnection:
    def __init__(self, responses=None, fail_on=None):
        """responses: list of (text found in SQL, rows to return) - first match wins."""
        self.responses = responses or []
        self.fail_on = fail_on
        self.executed = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.next_id = 100

    def rows_for(self, sql):
        for needle, rows in self.responses:
            if needle in sql:
                return rows
        return []

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True

    # handy for assertions
    def statements(self, start):
        return [s for s, _ in self.executed if s.startswith(start)]
