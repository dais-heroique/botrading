import argparse
from collector.solana import SolanaCollector, load_config
from labeling.pipeline import label_database
from storage.db import connect
from risk.engine import RiskEngine


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--collect", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--init-db", action="store_true")
    p.add_argument("--label", action="store_true")
    p.add_argument("--risk-check", action="store_true")
    p.add_argument("--tp", type=float, default=0.05)
    p.add_argument("--sl", type=float, default=0.03)
    p.add_argument("--horizon", type=int, default=20)
    args = p.parse_args()
    cfg = load_config()

    if args.init_db:
        connect(cfg["database"]).close()
        print("database initialized")
    if args.collect or args.watch:
        collector = SolanaCollector(cfg)
        try:
            if args.watch:
                collector.watch()
            else:
                print(f"events collected: {collector.collect_once()}")
        finally:
            collector.close()
    if args.label:
        print(
            f"labels written: "
            f"{label_database(cfg, tp=args.tp, sl=args.sl, horizon=args.horizon)}"
        )
    if args.risk_check:
        ok, reasons = RiskEngine().validate(0, 0, 0)
        print({"allowed": ok, "reasons": reasons})


if __name__ == "__main__":
    main()
