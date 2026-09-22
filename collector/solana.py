import json, time, requests
from storage.db import connect

class SolanaCollector:
    def __init__(self, config):
        self.config=config
        self.rpc=[config["rpc"]["primary"], config["rpc"]["fallback"]]
        self.db=connect(config["database"])

    def rpc_call(self, method, params):
        payload={"jsonrpc":"2.0","id":1,"method":method,"params":params}
        for url in self.rpc:
            try:
                r=requests.post(url,json=payload,timeout=15); r.raise_for_status(); data=r.json()
                if "error" not in data: return data.get("result")
            except requests.RequestException: pass
        raise RuntimeError("RPC unavailable")

    def collect_once(self):
        for w in self.config["wallets"]:
            rows=self.rpc_call("getSignaturesForAddress",[w["address"],{"limit":100}]) or []
            for x in rows:
                self.db.execute("INSERT OR IGNORE INTO wallet_events VALUES (?, ?, to_timestamp(?), ?, ?)",[w["address"],x["signature"],x.get("blockTime") or 0,x.get("slot"),json.dumps(x)])
        return True

def load_config(path="configs/config.yaml"):
    import yaml
    with open(path) as f: return yaml.safe_load(f)

if __name__ == "__main__":
    c=SolanaCollector(load_config()); c.collect_once(); print("ok")
