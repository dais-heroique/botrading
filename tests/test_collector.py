import tempfile
import unittest

from collector.solana import SolanaCollector


TEST_WALLET = "111111111111111111111111111111111111111111111111111111"


class FakeCollector(SolanaCollector):
    def __init__(self, config):
        super().__init__(config)
        self.calls = []

    def rpc_call(self, method, params):
        self.calls.append((method, params))
        if method == "getAccountInfo":
            return {"value": {"lamports": 1}}
        if method == "getSignaturesForAddress":
            options = params[1]
            if options.get("limit") == 1:
                return [{"signature": "sig-new"}]
            if options.get("before") == "sig-old":
                return []
            return [
                {"signature": "sig-new", "slot": 2, "blockTime": 2},
                {"signature": "sig-old", "slot": 1, "blockTime": 1},
            ]
        if method == "getTransaction":
            return {"slot": 2}
        if method == "getTokenAccountsByOwner":
            return {"value": []}
        raise AssertionError(method)


def make_config(tmp):
    return {
        "database": f"{tmp}/test.duckdb",
        "rpc": {
            "primary": "fake",
            "fallback": "fake",
            "signature_limit": 2,
            "max_pages": 2,
        },
        "wallets": [{"name": "test", "address": TEST_WALLET}],
    }


class CollectorTests(unittest.TestCase):
    def test_cursor_stops_at_existing_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(tmp)
            collector = FakeCollector(config)
            collector.db.execute(
                """INSERT INTO wallet_events
                (wallet, signature, slot)
                VALUES (?, ?, ?)""",
                [TEST_WALLET, "sig-old", 1],
            )
            collector.db.execute(
                """INSERT INTO collector_state
                (wallet, last_signature, updated_at)
                VALUES (?, ?, current_timestamp)""",
                [TEST_WALLET, "sig-old"],
            )
            collector.db.commit()

            self.assertEqual(collector.collect_once(), 1)
            self.assertEqual(
                collector.db.execute("SELECT COUNT(*) FROM wallet_events").fetchone()[0],
                2,
            )

    def test_repeated_collection_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            collector = FakeCollector(make_config(tmp))
            self.assertEqual(collector.collect_once(), 2)
            self.assertEqual(collector.collect_once(), 0)
            self.assertEqual(
                collector.db.execute("SELECT COUNT(*) FROM wallet_events").fetchone()[0],
                2,
            )


if __name__ == "__main__":
    unittest.main()
