import time
from datetime import datetime, timezone

import requests

from storage.db import connect
from paper_trader.strategy import StrategyConfig, should_enter, exit_reason


class PaperTrader:
    DEX_URL = "https://api.dexscreener.com/latest/dex/tokens"

    def __init__(self, database, config=None):
        self.cfg = config or StrategyConfig()
        self.db = connect(database)
        self.positions = {}
        self.session = requests.Session()
        self._load_positions()

    def _load_positions(self):
        rows = self.db.execute(
            """SELECT mint, symbol, entry_ts, entry_price, entry_liquidity,
                      quantity, invested, name
               FROM paper_positions WHERE status = 'open'"""
        ).fetchall()
        for row in rows:
            self.positions[row[0]] = {
                "mint": row[0], "symbol": row[1], "entry_ts": row[2].timestamp(),
                "entry_price": row[3], "entry_liquidity": row[4],
                "quantity": row[5], "invested": row[6], "name": row[7],
            }

    def market(self, mint):
        response = self.session.get(f"{self.DEX_URL}/{mint}", timeout=10)
        response.raise_for_status()
        pairs = [
            p for p in (response.json().get("pairs") or [])
            if p.get("chainId") == "solana"
        ]
        if not pairs:
            return None
        pair = max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))
        return {
            "price": float(pair["priceUsd"]) if pair.get("priceUsd") else None,
            "volume": float((pair.get("volume") or {}).get("h24") or 0),
            "liquidity": float((pair.get("liquidity") or {}).get("usd") or 0),
            "pair": pair.get("pairAddress"),
        }

    def _now(self):
        return time.time()

    def on_token(self, token):
        mint = token.get("mint")
        if not mint or mint in self.positions:
            return

        try:
            market = self.market(mint)
        except Exception as exc:
            self.db.execute(
                """INSERT INTO paper_signals
                   (ts, mint, symbol, action, reason, price, liquidity, volume, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [datetime.utcnow(), mint, token.get("symbol"), "SKIP",
                 "market_error", None, None, None, str(exc)],
            )
            self.db.commit()
            return

        now = self._now()
        ok, reason = should_enter(token, market, now, self.cfg)
        self.db.execute(
            """INSERT INTO paper_signals
               (ts, mint, symbol, action, reason, price, liquidity, volume, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [datetime.utcnow(), mint, token.get("symbol"), "ENTER" if ok else "SKIP",
             reason, market.get("price"), market.get("liquidity"),
             market.get("volume"), token.get("protocol")],
        )

        if ok:
            equity = self.equity()
            cash_to_use = min(equity * self.cfg.position_fraction, self.cash_available())
            if cash_to_use > 0 and market["price"] > 0:
                effective_entry = market["price"] * (
                    1 + self.cfg.fee_fraction + self.cfg.slippage_fraction
                )
                quantity = cash_to_use / effective_entry
                self.db.execute(
                    """INSERT INTO paper_positions
                       (mint, symbol, name, status, entry_ts, entry_price,
                        entry_liquidity, quantity, invested)
                       VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?)""",
                    [mint, token.get("symbol"), token.get("name"),
                     datetime.utcnow(), effective_entry, market["liquidity"],
                     quantity, cash_to_use],
                )
                self.positions[mint] = {
                    "mint": mint, "symbol": token.get("symbol"),
                    "name": token.get("name"), "entry_ts": now,
                    "entry_price": effective_entry,
                    "entry_liquidity": market["liquidity"],
                    "quantity": quantity, "invested": cash_to_use,
                }

        self.db.commit()
        print(
            f"[paper] {token.get('protocol')} {token.get('symbol') or mint[:8]} "
            f"{'ENTER' if ok else 'SKIP'} {reason}",
            flush=True,
        )

    def cash_available(self):
        invested = self.db.execute(
            "SELECT COALESCE(SUM(invested), 0) FROM paper_positions WHERE status='open'"
        ).fetchone()[0]
        realized = self.db.execute(
            "SELECT COALESCE(SUM(pnl), 0) FROM paper_trades"
        ).fetchone()[0]
        return max(0.0, self.cfg.starting_cash + realized - invested)

    def equity(self):
        equity = self.cash_available()
        for position in self.positions.values():
            try:
                market = self.market(position["mint"])
                if market and market.get("price"):
                    equity += position["quantity"] * market["price"]
                else:
                    equity += position["invested"]
            except Exception:
                equity += position["invested"]
        return equity

    def check_positions(self):
        now = self._now()
        for mint, position in list(self.positions.items()):
            try:
                market = self.market(mint)
            except Exception:
                continue
            if not market or not market.get("price"):
                continue

            reason = exit_reason(
                position["entry_price"],
                market["price"],
                position["entry_ts"],
                now,
                position["entry_liquidity"],
                market.get("liquidity"),
                self.cfg,
            )
            if not reason:
                continue

            gross = position["quantity"] * market["price"]
            exit_value = gross * (
                1 - self.cfg.fee_fraction - self.cfg.slippage_fraction
            )
            pnl = exit_value - position["invested"]
            self.db.execute(
                """INSERT INTO paper_trades
                   (ts, mint, symbol, side, entry_price, exit_price,
                    invested, exit_value, pnl, reason)
                   VALUES (?, ?, ?, 'SELL', ?, ?, ?, ?, ?, ?)""",
                [datetime.utcnow(), mint, position["symbol"],
                 position["entry_price"], market["price"],
                 position["invested"], exit_value, pnl, reason],
            )
            self.db.execute(
                """UPDATE paper_positions
                   SET status='closed', exit_ts=?, exit_price=?, pnl=?, exit_reason=?
                   WHERE mint=? AND status='open'""",
                [datetime.utcnow(), market["price"], pnl, reason, mint],
            )
            del self.positions[mint]
            self.db.commit()
            print(
                f"[paper] {position['symbol'] or mint[:8]} EXIT {reason} "
                f"pnl={pnl:+.2f} USD",
                flush=True,
            )

    def run(self, feed):
        print(
            f"[paper] starting with {self.cfg.starting_cash:.2f} USD virtual capital; "
            "no real orders will be sent",
            flush=True,
        )

        def wrapped(token):
            self.on_token(token)
            self.check_positions()

        feed.stream(wrapped)
