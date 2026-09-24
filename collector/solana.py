import json
import os
import time
import requests

from collector.market import MarketData
from collector.discovery import WalletDiscovery
from storage.db import connect


class SolanaCollector:
    def __init__(self, config):
        self.config = config
        self.rpc = [config["rpc"]["primary"], config["rpc"]["fallback"]]
        self.db = connect(config["database"])
        self.market = MarketData()
        self.discovery = WalletDiscovery()

    def rpc_call(self, method, params):
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        last = None
        for url in self.rpc:
            try:
                response = requests.post(url, json=payload, timeout=20)
                response.raise_for_status()
                data = response.json()
                if "error" not in data:
                    return data.get("result")
                last = RuntimeError(str(data["error"]))
            except (requests.RequestException, ValueError) as exc:
                last = exc
        raise RuntimeError(f"RPC unavailable: {last}")

    def _transaction(self, signature):
        return self.rpc_call(
            "getTransaction",
            [
                signature,
                {
                    "encoding": "jsonParsed",
                    "maxSupportedTransactionVersion": 1,
                },
            ],
        )

    def _record_observed_mints(self, address, tx):
        mints = set()
        meta = (tx or {}).get("meta") or {}
        for key in ("preTokenBalances", "postTokenBalances"):
            for balance in meta.get(key) or []:
                mint = balance.get("mint")
                if mint:
                    mints.add(mint)

        for mint in mints:
            self.db.execute(
                """INSERT INTO observed_tokens (wallet, mint, first_seen, last_seen)
                VALUES (?, ?, now(), now())
                ON CONFLICT (wallet, mint) DO UPDATE SET last_seen = now()""",
                [address, mint],
            )
        return mints

    def _backfill_observed_tokens(self, address):
        rows = self.db.execute(
            "SELECT tx_json FROM wallet_events WHERE wallet = ? AND tx_json IS NOT NULL",
            [address],
        ).fetchall()
        count = 0
        for (raw_json,) in rows:
            try:
                tx = json.loads(raw_json)
            except (TypeError, ValueError):
                continue
            count += len(self._record_observed_mints(address, tx))
        return count

    def _sync_tokens(self, address):
        try:
            result = self.rpc_call(
                "getTokenAccountsByOwner",
                [
                    address,
                    {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                    {"encoding": "jsonParsed"},
                ],
            ) or {}
        except RuntimeError:
            return []

        tokens = []
        for item in result.get("value", []):
            info = item.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
            token_amount = info.get("tokenAmount", {})
            mint = info.get("mint")
            if not mint:
                continue

            amount = float(token_amount.get("uiAmount") or 0)
            decimals = int(token_amount.get("decimals") or 0)
            if amount <= 0:
                continue

            self.db.execute(
                """INSERT OR REPLACE INTO wallet_tokens
                (wallet, mint, token_account, amount, decimals, updated_at)
                VALUES (?, ?, ?, ?, ?, current_timestamp)""",
                [address, mint, item.get("pubkey"), amount, decimals],
            )
            tokens.append(mint)

        return sorted(set(tokens))

    def _snapshot_markets(self, address, mints):
        written = 0
        for mint in mints:
            try:
                snapshot = self.market.token_snapshot(mint)
            except (requests.RequestException, ValueError):
                continue
            if not snapshot or snapshot["price"] is None:
                continue

            self.db.execute(
                """INSERT INTO market_snapshots
                (wallet, mint, ts, price, volume, liquidity, holders, source)
                VALUES (?, ?, current_timestamp, ?, ?, ?, ?, ?)""",
                [
                    address,
                    mint,
                    snapshot["price"],
                    snapshot["volume"],
                    snapshot["liquidity"],
                    snapshot["holders"],
                    snapshot["source"],
                ],
            )
            written += 1
        return written

    def _new_signatures(self, address, last_signature, limit, max_pages):
        fresh = []
        before = None

        for _ in range(max_pages):
            config = {"limit": limit}
            if before:
                config["before"] = before

            rows = self.rpc_call("getSignaturesForAddress", [address, config]) or []
            if not rows:
                break

            reached_cursor = False
            for row in rows:
                if row["signature"] == last_signature:
                    reached_cursor = True
                    break
                fresh.append(row)

            if reached_cursor or len(rows) < limit:
                break

            before = rows[-1]["signature"]

        return fresh

    def _configured_wallets(self):
        wallets = []
        for wallet in self.config.get("wallets", []):
            address = str(wallet.get("address", "")).strip()
            if address and address != "REPLACE_WITH_YOUR_PUBLIC_WALLET":
                wallets.append((address, wallet.get("name", "configured"), "configured"))

        rows = self.db.execute(
            "SELECT wallet, name, source FROM tracked_wallets ORDER BY updated_at DESC"
        ).fetchall()
        seen = {address for address, _, _ in wallets}
        for address, name, source in rows:
            if address not in seen:
                wallets.append((address, name or "discovered", source or "discovered"))
                seen.add(address)
        return wallets

    def discover_axiom_wallets(self):
        discovery = self.config.get("discovery", {})
        rows = self.discovery.top_axiom_wallets(
            limit=discovery.get("top_n", 10),
            days=discovery.get("days", 7),
            min_trades=discovery.get("min_trades", 20),
            min_invested=discovery.get("min_invested_usd", 1000),
        )
        for row in rows:
            self.db.execute(
                """INSERT INTO tracked_wallets
                (wallet, name, source, realized_pnl, win_rate, trades, discovered_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, now(), now())
                ON CONFLICT (wallet) DO UPDATE SET
                    source = excluded.source,
                    realized_pnl = excluded.realized_pnl,
                    win_rate = excluded.win_rate,
                    trades = excluded.trades,
                    updated_at = now()""",
                [
                    row["wallet"],
                    "axiom_top_trader",
                    row["source"],
                    row["realized_pnl"],
                    row["win_rate"],
                    row["trades"],
                ],
            )
        self.db.commit()
        return len(rows)

    def collect_once(self):
        limit = max(1, int(self.config["rpc"].get("signature_limit", 100)))
        max_pages = max(1, int(self.config["rpc"].get("max_pages", 10)))
        total = 0

        for address, wallet_name, wallet_source in self._configured_wallets():
            if len(address) < 32 or len(address) > 48:
                raise ValueError("Invalid Solana wallet address length")

            self.rpc_call("getAccountInfo", [address, {"encoding": "base64"}])
            state = self.db.execute(
                "SELECT last_signature FROM collector_state WHERE wallet = ?",
                [address],
            ).fetchone()
            last_signature = state[0] if state else None

            fresh = self._new_signatures(address, last_signature, limit, max_pages)

            for row in reversed(fresh):
                signature = row["signature"]
                exists = self.db.execute(
                    "SELECT 1 FROM wallet_events WHERE wallet = ? AND signature = ?",
                    [address, signature],
                ).fetchone()
                if exists:
                    continue

                try:
                    tx = self._transaction(signature)
                except RuntimeError:
                    tx = {"collector_error": "transaction_unavailable"}

                self.db.execute(
                    """INSERT INTO wallet_events
                    (wallet, signature, block_time, slot, err, memo, raw_json, tx_json)
                    VALUES (?, ?, CASE WHEN ? IS NULL THEN NULL ELSE to_timestamp(?) END,
                            ?, ?, ?, ?, ?)""",
                    [
                        address,
                        signature,
                        row.get("blockTime"),
                        row.get("blockTime"),
                        row.get("slot"),
                        json.dumps(row.get("err")),
                        row.get("memo"),
                        json.dumps(row),
                        json.dumps(tx),
                    ],
                )
                total += 1

            latest = self.rpc_call("getSignaturesForAddress", [address, {"limit": 1}]) or []
            if latest:
                self.db.execute(
                    """INSERT OR REPLACE INTO collector_state
                    (wallet, last_signature, updated_at)
                    VALUES (?, ?, current_timestamp)""",
                    [address, latest[0]["signature"]],
                )

            self._backfill_observed_tokens(address)
            mints = self._sync_tokens(address)
            observed = self.db.execute(
                "SELECT mint FROM observed_tokens WHERE wallet = ?",
                [address],
            ).fetchall()
            mints = sorted(set(mints) | {row[0] for row in observed})
            self._snapshot_markets(address, mints)

        self.db.commit()
        return total

    def watch(self):
        interval = max(5, int(self.config["rpc"].get("interval_seconds", 30)))
        discovery_cfg = self.config.get("discovery", {})
        discovery_enabled = bool(discovery_cfg.get("enabled", True))
        discovery_every = max(1, int(discovery_cfg.get("refresh_minutes", 15)))
        last_discovery = 0.0

        while True:
            started = time.monotonic()
            if discovery_enabled and time.monotonic() - last_discovery >= discovery_every * 60:
                try:
                    found = self.discover_axiom_wallets()
                    print(f"axiom wallets discovered: {found}", flush=True)
                    last_discovery = time.monotonic()
                except (requests.RequestException, ValueError, RuntimeError) as exc:
                    print(f"wallet discovery skipped: {exc}", flush=True)

            print(
                f"events collected: {self.collect_once()} | "
                f"tracked wallets: {len(self._configured_wallets())}",
                flush=True,
            )
            time.sleep(max(0, interval - (time.monotonic() - started)))

    def close(self):
        self.db.close()


def load_config(path="configs/config.yaml"):
    import yaml

    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    env_wallet = os.getenv("SOLANA_WALLET_ADDRESS")
    if env_wallet:
        config["wallets"][0]["address"] = env_wallet.strip()
    return config


if __name__ == "__main__":
    collector = SolanaCollector(load_config())
    collector.watch()
