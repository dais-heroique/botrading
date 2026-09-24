import json
from pathlib import Path

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().sort_values("ts").reset_index(drop=True)
    price = pd.to_numeric(out["price"], errors="coerce")
    volume = pd.to_numeric(out["volume"], errors="coerce")
    liquidity = pd.to_numeric(out["liquidity"], errors="coerce")

    out["return_1"] = price.pct_change(1)
    out["return_3"] = price.pct_change(3)
    out["return_10"] = price.pct_change(10)
    out["volume_change_1"] = volume.pct_change(1)
    out["liquidity_change_1"] = liquidity.pct_change(1)
    out["volatility_10"] = price.pct_change().rolling(10).std()
    out["volume_z_20"] = (volume - volume.rolling(20).mean()) / volume.rolling(20).std()
    out["liquidity_z_20"] = (liquidity - liquidity.rolling(20).mean()) / liquidity.rolling(20).std()
    return out


def train(df, target="label"):
    features = build_features(df)
    numeric = [
        "return_1", "return_3", "return_10", "volume_change_1",
        "liquidity_change_1", "volatility_10", "volume_z_20", "liquidity_z_20",
    ]
    data = features[numeric + [target]].replace([float("inf"), float("-inf")], pd.NA).dropna()
    if len(data) < 100 or data[target].nunique() < 2:
        raise ValueError("not enough labeled feature data: need >=100 rows and >=2 classes")

    split = int(len(data) * 0.8)
    if split < 1 or split >= len(data):
        raise ValueError("not enough data for time-series split")
    Xtr, Xte = data[numeric].iloc[:split], data[numeric].iloc[split:]
    ytr, yte = data[target].iloc[:split], data[target].iloc[split:]
    if ytr.nunique() < 2:
        raise ValueError("training window contains only one label class")

    model = GradientBoostingClassifier(random_state=42).fit(Xtr, ytr)
    accuracy = float(model.score(Xte, yte)) if len(Xte) else None
    return model, accuracy, numeric, len(data)


def save_model(model, features, accuracy, rows, path="models/artifacts/model.json"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": model,
        "features": features,
        "accuracy": accuracy,
        "rows": rows,
    }
    import pickle
    with open(path, "wb") as f:
        pickle.dump(payload, f)
    return path
