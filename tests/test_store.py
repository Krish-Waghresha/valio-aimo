import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from aimo_gateway.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "fixture.sqlite"
        self.store = Store(self.path, "fixture")

    def request(self):
        request = {"id": str(uuid4()), "customerId": "kitchen", "status": "active"}
        with self.store.transaction() as connection:
            self.store.put(connection, "request", request, "kitchen")
        return request

    def commit(self, request):
        try:
            with self.store.transaction() as connection:
                self.store.commit_order(connection, request, {
                    "id": str(uuid4()), "totals": {"grossMinor": 600},
                }, 1000, "2026-11-14")
            return "ordered"
        except ValueError as error:
            return str(error)

    def test_shared_daily_limit_is_atomic(self):
        requests = [self.request(), self.request()]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.commit, requests))
        self.assertCountEqual(results, ["ordered", "DAILY_LIMIT_EXCEEDED"])

    def test_same_request_commits_once(self):
        request = self.request()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.commit, [request, request]))
        self.assertCountEqual(results, ["ordered", "REQUEST_ALREADY_ORDERED"])

    def test_commit_survives_restart(self):
        request = self.request()
        self.assertEqual(self.commit(request), "ordered")
        self.store = Store(self.path, "fixture")
        self.assertEqual(self.commit(request), "REQUEST_ALREADY_ORDERED")

    def test_modes_cannot_share_database(self):
        with self.assertRaises(ValueError):
            Store(self.path, "live")


if __name__ == "__main__":
    unittest.main()