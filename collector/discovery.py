import os
import requests


class WalletDiscovery:
    URL = "https://data.solanatracker.io/v2/pnl/leaderboard/top"

    def __init__(self, timeout=20):
        self.timeout = timeout

    def top_axiom_wallets(
        self,
        limit=10,
        days=7,
        min_trades=20,
        min_invested=1000,
    ):
        api_key = os.getenv("SOLANA_TRACKER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "SOLANA_TRACKER_API_KEY is required for automatic Axiom trader discovery. "
                "Use the free Solana Tracker API tier; never put the key in the repository."
            )

        params = {
            "days": int(days),
            "platform": "axiom",
            "sort": "realized",
            "direction": "desc",
            "limit": int(limit),
            "minTrades": int(min_trades),
            "minInvested": float(min_invested),
            "pnlMode": "adjusted",
        }
        response = requests.get(
            self.URL,
            params=params,
            headers={"x-api-key": api_key},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        rows = data.get("traders") or []

        wallets = []
        for row in rows:
            wallet = row.get("wallet") or row.get("address")
            if not wallet:
                continue
            period = row.get("period") or {}
            days_stats = period.get("days") or {}
            pnl = row.get("pnl") or {}
            realized_pnl = (
                period.get("realized")
                or period.get("realizedPnl")
                or period.get("realizedRaw")
                or pnl.get("realized")
                or row.get("realized_pnl")
                or row.get("realizedPnl")
            )
            win_rate = (
                period.get("winRate")
                or days_stats.get("winRate")
                or row.get("win_rate")
                or row.get("winRate")
            )
            trades = (
                period.get("trades")
                or days_stats.get("trades")
                or row.get("trades")
                or row.get("totalTrades")
            )
            wallets.append(
                {
                    "wallet": wallet,
                    "realized_pnl": realized_pnl,
                    "win_rate": win_rate,
                    "trades": trades,
                    "source": "solana_tracker_axiom",
                }
            )
        return wallets
