import pandas as pd


def triple_barrier(
    df: pd.DataFrame,
    tp: float = 0.05,
    sl: float = 0.03,
    horizon: int = 20,
) -> pd.DataFrame:
    if "price" not in df.columns:
        raise ValueError("price column is required")
    if tp <= 0 or sl <= 0 or horizon < 1:
        raise ValueError("tp, sl and horizon must be positive")

    prices = pd.to_numeric(df["price"], errors="coerce").to_numpy()
    if pd.isna(prices).any() or (prices <= 0).any():
        raise ValueError("price values must be finite and positive")

    out = []
    for i, price in enumerate(prices):
        end = min(i + horizon, len(prices) - 1)
        label = 0
        barrier = "timeout"
        ret = (prices[end] / price) - 1.0

        for j in range(i + 1, end + 1):
            change = (prices[j] / price) - 1.0
            if change >= tp:
                label, barrier, ret = 1, "take_profit", change
                break
            if change <= -sl:
                label, barrier, ret = -1, "stop_loss", change
                break

        out.append((label, barrier, float(ret)))

    return pd.DataFrame(
        out,
        index=df.index,
        columns=["label", "barrier", "return"],
    )
