import pandas as pd

def triple_barrier(df: pd.DataFrame, tp=0.05, sl=0.03, horizon=20):
    out=[]
    prices=df["price"].tolist()
    for i,p in enumerate(prices):
        end=min(i+horizon,len(prices)-1); label=0; barrier="timeout"; ret=(prices[end]/p)-1 if p else 0
        for j in range(i+1,end+1):
            r=prices[j]/p-1 if p else 0
            if r >= tp: label,barrier=1,"take_profit"; ret=r; break
            if r <= -sl: label,barrier=-1,"stop_loss"; ret=r; break
        out.append((label,barrier,ret))
    return pd.DataFrame(out,index=df.index,columns=["label","barrier","return"])
