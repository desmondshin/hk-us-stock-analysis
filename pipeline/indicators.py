# -*- coding: utf-8 -*-
"""技術指標（以收盤價／還原後收盤計算）。全部為向量化 pandas 實作。"""
import numpy as np
import pandas as pd


def sma(s, n):
    return s.rolling(n, min_periods=1).mean()


def ema(s, n):
    return s.ewm(span=n, adjust=False, min_periods=1).mean()


def rsi(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    ag = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    al = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = ag / al.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    out = out.where(al != 0, 100.0)
    return out


def macd(close, fast=12, slow=26, signal=9):
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return line, sig, line - sig


def bollinger(close, n=20, k=2.0):
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=1).std(ddof=0)
    return mid, mid + k * sd, mid - k * sd


def atr(df, n=14):
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=1).mean()


def compute(df):
    """回傳帶指標欄位的 DataFrame。"""
    d = df.copy()
    c = d["Close"]
    d["ma20"] = sma(c, 20)
    d["ma50"] = sma(c, 50)
    d["ma200"] = sma(c, 200)
    d["vol_ma20"] = sma(d["Volume"], 20)
    d["rsi"] = rsi(c, 14)
    line, sig, hist = macd(c)
    d["macd"], d["macd_signal"], d["macd_hist"] = line, sig, hist
    m, u, lo = bollinger(c, 20, 2.0)
    d["bb_mid"], d["bb_up"], d["bb_low"] = m, u, lo
    d["atr"] = atr(d, 14)
    d["turnover"] = c * d["Volume"]
    d["turnover_ma20"] = sma(d["turnover"], 20)
    # 20 日高低（型態用）
    d["high20"] = d["High"].rolling(20, min_periods=1).max().shift(1)
    d["low20"] = d["Low"].rolling(20, min_periods=1).min().shift(1)
    d["ret1"] = c.pct_change()
    d["vol20"] = d["ret1"].rolling(20, min_periods=5).std(ddof=0)
    return d


def weekly_downsample(d, keep_days):
    """近期 keep_days 保留每日；更早資料以每週（W-FRI）抽樣。"""
    if len(d) <= keep_days:
        return d, d.iloc[0:0]
    daily = d.iloc[-keep_days:]
    older = d.iloc[:-keep_days]
    if older.empty:
        return daily, older
    wk = older.resample("W-FRI").last().dropna(subset=["Close"])
    return daily, wk
