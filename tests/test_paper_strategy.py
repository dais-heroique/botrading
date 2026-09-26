import unittest

from paper_trader.strategy import StrategyConfig, should_enter, exit_reason


class PaperStrategyTests(unittest.TestCase):
    def setUp(self):
        self.cfg = StrategyConfig()

    def test_entry_filters_real_market_data(self):
        now = 1_000.0
        token = {"timestamp": 950.0}
        market = {"price": 1.0, "liquidity": 20_000, "volume": 10_000}
        ok, reason = should_enter(token, market, now, self.cfg)
        self.assertTrue(ok)
        self.assertEqual(reason, "entry_filter_passed")

    def test_rejects_low_liquidity(self):
        ok, reason = should_enter(
            {"timestamp": 950.0},
            {"price": 1.0, "liquidity": 100, "volume": 10_000},
            1_000.0,
            self.cfg,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "low_liquidity")

    def test_take_profit(self):
        self.assertEqual(
            exit_reason(1.0, 1.25, 0.0, 60.0, 20_000, 20_000, self.cfg),
            "take_profit",
        )

    def test_stop_loss(self):
        self.assertEqual(
            exit_reason(1.0, 0.85, 0.0, 60.0, 20_000, 20_000, self.cfg),
            "stop_loss",
        )

    def test_time_exit(self):
        self.assertEqual(
            exit_reason(1.0, 1.01, 0.0, 901.0, 20_000, 20_000, self.cfg),
            "time_exit",
        )


if __name__ == "__main__":
    unittest.main()
