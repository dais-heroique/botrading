from storage.db import connect
from labeling.triple_barrier import triple_barrier


def label_database(config, tp=0.05, sl=0.03, horizon=20):
    db = connect(config['database'])
    snapshots = db.execute(
        """SELECT wallet, mint, ts, price
        FROM market_snapshots
        WHERE price IS NOT NULL AND price > 0
        ORDER BY wallet, mint, ts"""
    ).fetchdf()

    if snapshots.empty:
        raise ValueError('no market snapshots with valid prices')

    total = 0
    for (wallet, mint), group in snapshots.groupby(['wallet', 'mint'], sort=False):
        group = group.sort_values('ts').reset_index(drop=True)
        labels = triple_barrier(group[['price']], tp=tp, sl=sl, horizon=horizon)

        db.execute('DELETE FROM labels WHERE wallet = ? AND mint = ?', [wallet, mint])
        for row, label in zip(group.itertuples(index=False), labels.itertuples(index=False)):
            db.execute(
                """INSERT INTO labels (wallet, mint, ts, label, barrier, return)
                VALUES (?, ?, ?, ?, ?, ?)""",
                [wallet, mint, row.ts, int(label.label), label.barrier, float(getattr(label, 'return'))],
            )
            total += 1

    db.commit()
    db.close()
    return total
