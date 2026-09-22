import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split

def train(df, target="label"):
    X=df.select_dtypes(include="number").drop(columns=[target],errors="ignore").fillna(0)
    y=df[target]
    if len(X)<20 or y.nunique()<2: raise ValueError("not enough labeled data")
    Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.2,shuffle=False)
    model=GradientBoostingClassifier(random_state=42).fit(Xtr,ytr)
    return model, model.score(Xte,yte)
