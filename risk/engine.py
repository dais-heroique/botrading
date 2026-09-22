from dataclasses import dataclass

@dataclass(frozen=True)
class RiskLimits:
    max_position_fraction: float = 0.10
    max_daily_loss_fraction: float = 0.05
    max_slippage_fraction: float = 0.03

class RiskEngine:
    def __init__(self, limits: RiskLimits | None = None):
        self.limits = limits or RiskLimits()

    def validate(self, position_fraction: float, daily_loss_fraction: float, slippage_fraction: float) -> tuple[bool, list[str]]:
        reasons = []
        if position_fraction > self.limits.max_position_fraction: reasons.append("position_limit")
        if daily_loss_fraction > self.limits.max_daily_loss_fraction: reasons.append("daily_loss_limit")
        if slippage_fraction > self.limits.max_slippage_fraction: reasons.append("slippage_limit")
        return not reasons, reasons
