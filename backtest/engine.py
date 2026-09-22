def backtest(prices, signals, fee=.001, slippage=.001):
    cash=1.0; units=0.0; trades=[]
    for price,signal in zip(prices,signals):
        if signal > 0 and units == 0:
            cost=price*(1+fee+slippage); units=cash/cost; cash=0; trades.append(("buy",price))
        elif signal < 0 and units > 0:
            cash=units*price*(1-fee-slippage); units=0; trades.append(("sell",price))
    final=cash + units*(prices[-1] if prices else 0)
    return {"final_equity":final,"pnl":final-1,"trades":trades}
