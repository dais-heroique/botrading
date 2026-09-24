import argparse
from collector.solana import SolanaCollector, load_config
from labeling.pipeline import label_database
from storage.db import connect
from risk.engine import RiskEngine
from models.train import train, save_model


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--collect", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--init-db", action="store_true")
    p.add_argument("--label", action="store_true")
    p.add_argument("--risk-check", action="store_true")
    p.add_argument("--learn", action="store_true")
    p.add_argument("--discover-wallets", action="store_true")
    p.add_argument("--tp", type=float, default=0.05)
    p.add_argument("--sl", type=float, default=0.03)
    p.add_argument("--horizon", type=int, default=20)
    args = p.parse_args()
    cfg = load_config()

    if args.init_db:
        connect(cfg["database"]).close()
        print("database initialized")
    if args.discover_wallets:
        collector = SolanaCollector(cfg)
        try:
            print(f"axiom wallets discovered: {collector.discover_axiom_wallets()}")
        finally:
            collector.close()
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
    if args.learn:
        db = connect(cfg["database"])
        snapshots = db.execute(
            """SELECT s.wallet, s.mint, s.ts, s.price, s.volume, s.liquidity, l.label
            FROM market_snapshots s
            JOIN labels l ON l.wallet = s.wallet AND l.mint = s.mint AND l.ts = s.ts
            WHERE s.price IS NOT NULL AND s.price > 0
            ORDER BY s.wallet, s.mint, s.ts"""
        ).fetchdf()
        db.close()
        if snapshots.empty:
            raise ValueError("no labeled market snapshots; run --label first")
        model, accuracy, features, rows = train(snapshots)
        path = save_model(model, features, accuracy, rows)
        print({"model": path, "rows": rows, "test_accuracy": accuracy, "classes": model.classes_.tolist()})
    if args.risk_check:
        ok, reasons = RiskEngine().validate(0, 0, 0)
        print({"allowed": ok, "reasons": reasons})


if __name__ == "__main__":
    main()
