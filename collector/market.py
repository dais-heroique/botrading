import requests


class MarketData:
    BASE_URL = "https://api.dexscreener.com/latest/dex/tokens"

    def __init__(self, timeout=15):
        self.timeout = timeout

    def token_snapshot(self, mint):
        response = requests.get(f"{self.BASE_URL}/{mint}", timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        pairs = [p for p in data.get("pairs", []) if p.get("chainId") == "solana"]
        if not pairs:
            return None

        pair = max(
            pairs,
            key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0),
        )
        price = pair.get("priceUsd")
        volume = (pair.get("volume") or {}).get("h24")
        liquidity = (pair.get("liquidity") or {}).get("usd")

        return {
            "price": float(price) if price is not None else None,
            "volume": float(volume) if volume is not None else None,
            "liquidity": float(liquidity) if liquidity is not None else None,
            "holders": None,
            "source": "dexscreener",
        }
