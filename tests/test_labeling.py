import unittest

import pandas as pd

from labeling.triple_barrier import triple_barrier


class TripleBarrierTests(unittest.TestCase):
    def test_take_profit(self):
        prices = pd.DataFrame({"price": [100.0, 106.0, 100.0]})
        result = triple_barrier(prices, tp=0.05, sl=0.03, horizon=2)
        self.assertEqual(result.loc[0, "label"], 1)
        self.assertEqual(result.loc[0, "barrier"], "take_profit")

    def test_stop_loss(self):
        prices = pd.DataFrame({"price": [100.0, 96.0, 100.0]})
        result = triple_barrier(prices, tp=0.05, sl=0.03, horizon=2)
        self.assertEqual(result.loc[0, "label"], -1)
        self.assertEqual(result.loc[0, "barrier"], "stop_loss")

    def test_timeout(self):
        prices = pd.DataFrame({"price": [100.0, 102.0, 101.0]})
        result = triple_barrier(prices, tp=0.05, sl=0.03, horizon=2)
        self.assertEqual(result.loc[0, "label"], 0)
        self.assertEqual(result.loc[0, "barrier"], "timeout")


if __name__ == "__main__":
    unittest.main()
