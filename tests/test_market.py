import unittest
from unittest.mock import patch

from collector.market import MarketData


class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {
            'pairs': [
                {'chainId': 'solana', 'priceUsd': '2.50', 'volume': {'h24': 1200}, 'liquidity': {'usd': 8000}},
                {'chainId': 'solana', 'priceUsd': '2.40', 'volume': {'h24': 900}, 'liquidity': {'usd': 3000}},
            ]
        }


class MarketDataTests(unittest.TestCase):
    @patch('collector.market.requests.get', return_value=FakeResponse())
    def test_selects_liquid_solana_pair(self, mock_get):
        result = MarketData().token_snapshot('mint')
        self.assertEqual(result['price'], 2.5)
        self.assertEqual(result['volume'], 1200.0)
        self.assertEqual(result['liquidity'], 8000.0)
        self.assertIsNone(result['holders'])
        mock_get.assert_called_once()


if __name__ == '__main__':
    unittest.main()
