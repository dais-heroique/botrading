import argparse
from collector.solana import SolanaCollector, load_config
from storage.db import connect
from risk.engine import RiskEngine

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--collect", action="store_true")
    p.add_argument("--init-db", action="store_true")
    p.add_argument("--risk-check", action="store_true")
    args = p.parse_args()
    cfg = load_config()
    if args.init_db:
        connect(cfg["database"]).close()
        print("database initialized")
    if args.collect:
        print(f"events collected: {SolanaCollector(cfg).collect_once()}")
    if args.risk_check:
        ok, reasons = RiskEngine().validate(0, 0, 0)
        print({"allowed": ok, "reasons": reasons})

if __name__ == "__main__":
    main()
