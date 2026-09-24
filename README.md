# botrading

Local Solana wallet collection, market snapshots, labeling, modeling and backtesting.

## Data flow

- Solana public RPC: wallet signatures, full transactions and token accounts.
- DexScreener public endpoint: token price, 24h volume and liquidity snapshots for tokens held by the tracked wallet.
- Holder count is stored as NULL until a reliable public on-chain holder-count method is implemented; the collector never fabricates it.
- DuckDB stores everything locally in `data/botrading.duckdb`.
- No private key or seed phrase is used: the tracked wallet is read-only via its public address.

Set the wallet only in the local shell:

    export SOLANA_WALLET_ADDRESS="YOUR_PUBLIC_SOLANA_WALLET"
    python main.py --collect


## Automatic Axiom trader discovery

Set a free Solana Tracker API key locally:

    export SOLANA_TRACKER_API_KEY="YOUR_FREE_API_KEY"

The collector queries the Axiom-filtered PnL leaderboard, stores discovered public wallet addresses in DuckDB, and then tracks those wallets through Solana public RPC. The key is never committed.

    python main.py --discover-wallets
    python main.py --watch

The watch loop refreshes the Axiom wallet list periodically and collects transactions for the discovered wallets.