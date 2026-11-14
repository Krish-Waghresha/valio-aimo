import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class Store:
    def __init__(self, path, mode):
        self.path = str(path)
        self.mode = mode
        Path(path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with closing(self.connect()) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documents (
                    kind TEXT NOT NULL, id TEXT NOT NULL, customer TEXT NOT NULL,
                    parent TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY (kind, id)
                );
                CREATE INDEX IF NOT EXISTS documents_parent ON documents(kind, parent);
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
                    customer TEXT NOT NULL, day TEXT NOT NULL, gross INTEGER NOT NULL CHECK(gross >= 0),
                    data TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS orders_budget ON orders(customer, day);
                CREATE TABLE IF NOT EXISTS events (
                    request_id TEXT NOT NULL, sequence INTEGER NOT NULL, data TEXT NOT NULL,
                    PRIMARY KEY(request_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS idempotency (
                    scope TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, owner TEXT NOT NULL,
                    lease REAL NOT NULL, state TEXT NOT NULL, response TEXT
                );
                CREATE TABLE IF NOT EXISTS locks (resource TEXT PRIMARY KEY, owner TEXT NOT NULL, lease REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS throttle (principal TEXT NOT NULL, bucket INTEGER NOT NULL,
                    count INTEGER NOT NULL, PRIMARY KEY(principal, bucket));
            """)
            connection.execute("INSERT OR IGNORE INTO metadata VALUES ('mode', ?)", (mode,))
            if connection.execute("SELECT value FROM metadata WHERE key='mode'").fetchone()[0] != mode:
                raise ValueError("Live and fixture modes must use separate databases.")
        Path(path).chmod(0o600)

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def transaction(self):
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def put(self, connection, kind, value, customer, parent=""):
        connection.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data",
            (kind, value["id"], customer, parent, encode(value)),
        )

    def get(self, connection, kind, identity, customer=None):
        row = connection.execute("SELECT customer,data FROM documents WHERE kind=? AND id=?", (kind, identity)).fetchone()
        if row is None or (customer is not None and row["customer"] != customer):
            return None
        return json.loads(row["data"])

    def spent(self, connection, customer, day):
        return connection.execute("SELECT COALESCE(SUM(gross),0) FROM orders WHERE customer=? AND day=?", (customer, day)).fetchone()[0]

    def commit_order(self, connection, request, order, daily_limit, day):
        current = self.get(connection, "request", request["id"], request["customerId"])
        if current["status"] != "active":
            raise ValueError("REQUEST_ALREADY_ORDERED" if current["status"] == "ordered_mock" else "REQUEST_CANCELLED")
        gross = order["totals"]["grossMinor"]
        if self.spent(connection, request["customerId"], day) + gross > daily_limit:
            raise ValueError("DAILY_LIMIT_EXCEEDED")
        connection.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)", (
            order["id"], request["id"], request["customerId"], day, gross, encode(order),
        ))
        self.put(connection, "order", order, request["customerId"], request["id"])
        current["status"] = "ordered_mock"
        self.put(connection, "request", current, request["customerId"])

    def event(self, connection, request_id, value):
        sequence = connection.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM events WHERE request_id=?", (request_id,)).fetchone()[0]
        event = {**value, "requestId": request_id, "sequence": sequence}
        connection.execute("INSERT INTO events VALUES (?, ?, ?)", (request_id, sequence, encode(event)))
        return event