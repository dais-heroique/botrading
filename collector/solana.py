import json
import time
import requests
from storage.db import connect


class SolanaCollector:
    def __init__(self, config):
        self.config = config
        self.rpc = [config["rpc"]["primary"], config["rpc"]["fallback"]]
        self.db = connect(config["database"])

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
            return 0

        synced = 0
        for item in result.get("value", []):
            info = item.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
            token_amount = info.get("tokenAmount", {})
            self.db.execute(
                """INSERT OR REPLACE INTO wallet_tokens
                (wallet, mint, token_account, amount, decimals, updated_at)
                VALUES (?, ?, ?, ?, ?, current_timestamp)""",
                [
                    address,
                    info.get("mint"),
                    item.get("pubkey"),
                    float(token_amount.get("uiAmount") or 0),
                    int(token_amount.get("decimals") or 0),
                ],
            )
            synced += 1
        return synced

    def collect_once(self):
        limit = int(self.config["rpc"].get("signature_limit", 100))
        total = 0

        for wallet in self.config["wallets"]:
            address = str(wallet["address"])
            state = self.db.execute(
                "SELECT last_signature FROM collector_state WHERE wallet = ?",
                [address],
            ).fetchone()
            last_signature = state[0] if state else None

            rows = self.rpc_call(
                "getSignaturesForAddress", [address, {"limit": limit}]
            ) or []

            fresh = []
            for row in rows:
                if row["signature"] == last_signature:
                    break
                fresh.append(row)

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

            if rows:
                self.db.execute(
                    """INSERT OR REPLACE INTO collector_state
                    (wallet, last_signature, updated_at)
                    VALUES (?, ?, current_timestamp)""",
                    [address, rows[0]["signature"]],
                )

            self._sync_tokens(address)

        self.db.commit()
        return total

    def watch(self):
        interval = max(5, int(self.config["rpc"].get("interval_seconds", 30)))
        while True:
            started = time.monotonic()
            print(f"events collected: {self.collect_once()}", flush=True)
            time.sleep(max(0, interval - (time.monotonic() - started)))


def load_config(path="configs/config.yaml"):
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    collector = SolanaCollector(load_config())
    collector.watch()
