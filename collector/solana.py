import json, requests
from storage.db import connect

class SolanaCollector:
    def __init__(self, config):
        self.config = config
        self.rpc = [config["rpc"]["primary"], config["rpc"]["fallback"]]
        self.db = connect(config["database"])

    def rpc_call(self, method, params):
        payload = {"jsonrpc":"2.0","id":1,"method":method,"params":params}
        last = None
        for url in self.rpc:
            try:
                r = requests.post(url, json=payload, timeout=15)
                r.raise_for_status()
                data = r.json()
                if "error" not in data:
                    return data.get("result")
                last = RuntimeError(str(data["error"]))
            except requests.RequestException as exc:
                last = exc
        raise RuntimeError(f"RPC unavailable: {last}")

    def collect_once(self):
        limit = self.config["rpc"].get("signature_limit", 100)
        total = 0
        for wallet in self.config["wallets"]:
            address = wallet["address"]
            rows = self.rpc_call("getSignaturesForAddress", [address, {"limit": limit}]) or []
            for row in rows:
                self.db.execute(
                    """INSERT OR IGNORE INTO wallet_events
                    (wallet, signature, block_time, slot, err, memo, raw_json)
                    VALUES (?, ?, CASE WHEN ? IS NULL THEN NULL ELSE to_timestamp(?) END, ?, ?, ?, ?)""",
                    [address, row["signature"], row.get("blockTime"), row.get("blockTime"),
                     row.get("slot"), json.dumps(row.get("err")), row.get("memo"),
                     json.dumps(row)]
                )
                total += 1
        return total

def load_config(path="configs/config.yaml"):
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

if __name__ == "__main__":
    print(SolanaCollector(load_config()).collect_once())
