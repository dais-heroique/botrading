from pathlib import Path
import duckdb

SCHEMA = """
CREATE TABLE IF NOT EXISTS wallet_events (
 wallet TEXT,
 signature TEXT,
 block_time TIMESTAMP,
 slot BIGINT,
 err TEXT,
 memo TEXT,
 raw_json TEXT,
 tx_json TEXT,
 PRIMARY KEY(wallet, signature)
);
CREATE TABLE IF NOT EXISTS wallet_tokens (
 wallet TEXT,
 mint TEXT,
 token_account TEXT,
 amount DOUBLE,
 decimals INTEGER,
 updated_at TIMESTAMP,
 PRIMARY KEY(wallet, mint, token_account)
);
CREATE TABLE IF NOT EXISTS collector_state (
 wallet TEXT PRIMARY KEY,
 last_signature TEXT,
 updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS market_snapshots (
 wallet TEXT,
 ts TIMESTAMP,
 price DOUBLE,
 volume DOUBLE,
 liquidity DOUBLE,
 holders BIGINT
);
CREATE TABLE IF NOT EXISTS labels (
 wallet TEXT,
 ts TIMESTAMP,
 label INTEGER,
 barrier TEXT,
 return DOUBLE
);
"""

def connect(path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(path)
    for stmt in SCHEMA.split(";"):
        if stmt.strip():
            con.execute(stmt)
    con.execute("ALTER TABLE wallet_events ADD COLUMN IF NOT EXISTS tx_json TEXT")
    return con
