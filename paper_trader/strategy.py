from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyConfig:
    starting_cash: float = 1000.0
    max_position_fraction: float = 0.10
    min_liquidity_usd: float = 10_000.0
    min_volume_24h_usd: float = 5_000.0
    max_entry_age_minutes: float = 10.0
    take_profit: float = 0.20
    stop_loss: float = 0.10
    max_hold_minutes: float = 15.0
    liquidity_stop_fraction: float = 0.30
    fee_fraction: float = 0.005
    slippage_fraction: float = 0.005

    @property
    def position_fraction(self):
        return min(self.max_position_fraction, 1.0)


def should_enter(token, market, now_ts, cfg):
    if not market:
        return False, "no_market_data"

    price = market.get("price")
    liquidity = market.get("liquidity")
    volume = market.get("volume")
    created = token.get("timestamp") or token.get("_received_at")
    if not price or not liquidity or not volume or not created:
        return False, "incomplete_market_data"

    age_minutes = max(0.0, (now_ts - float(created)) / 60.0)
    if age_minutes > cfg.max_entry_age_minutes:
        return False, "too_old"
    if liquidity < cfg.min_liquidity_usd:
        return False, "low_liquidity"
    if volume < cfg.min_volume_24h_usd:
        return False, "low_volume"
    return True, "entry_filter_passed"


def exit_reason(
    entry_price,
    current_price,
    entry_ts,
    now_ts,
    entry_liquidity,
    current_liquidity,
    cfg,
):
    change = current_price / entry_price - 1.0
    if change >= cfg.take_profit:
        return "take_profit"
    if change <= -cfg.stop_loss:
        return "stop_loss"
    if now_ts - entry_ts >= cfg.max_hold_minutes * 60:
        return "time_exit"
    if entry_liquidity and current_liquidity is not None:
        if current_liquidity <= entry_liquidity * (1.0 - cfg.liquidity_stop_fraction):
            return "liquidity_exit"
    return None
