# -*- coding: utf-8 -*-
"""抓取日線價格（yfinance 主力，含磁碟快取與失敗回報）。"""
import os
import time
import pickle
import warnings
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "data", "cache", "prices")
os.makedirs(CACHE, exist_ok=True)


def _cache_path(sym):
    return os.path.join(CACHE, f"{sym.replace('/', '_')}.pkl")


def _load_cache(sym):
    p = _cache_path(sym)
    if os.path.exists(p):
        try:
            with open(p, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None


def _save_cache(sym, df):
    with open(_cache_path(sym), "wb") as f:
        pickle.dump(df, f)


def fetch_one(sym, years=20):
    df = yf.Ticker(sym).history(period=f"{years}y", interval="1d", auto_adjust=False)
    if df is None or df.empty:
        return None
    df = df[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].copy()
    df = df[~df.index.duplicated(keep="last")]
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    return df


def fetch_prices(symbols, years=20, chunk=40, sleep=1.0, refresh=False, log=print):
    """回傳 {symbol: DataFrame}。有快取則用快取（除非 refresh）。"""
    out, failed = {}, []
    todo = []
    for s in symbols:
        if not refresh:
            c = _load_cache(s)
            if c is not None:
                out[s] = c
                continue
        todo.append(s)

    for i in range(0, len(todo), chunk):
        batch = todo[i:i + chunk]
        log(f"  fetch prices {i + 1}-{i + len(batch)}/{len(todo)} ...")
        try:
            data = yf.download(batch, period=f"{years}y", interval="1d",
                               auto_adjust=False, group_by="ticker",
                               threads=True, progress=False)
        except Exception as e:
            log("   batch error", repr(e)[:120])
            data = None
        got = set()
        if data is not None and not data.empty:
            for s in batch:
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        if s not in data.columns.get_level_values(0):
                            continue
                        d = data[s].copy()
                    else:
                        d = data.copy()
                    d = d.dropna(how="all")
                    if d.empty or "Close" not in d:
                        continue
                    d = d[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].dropna(subset=["Close"])
                    if d.empty:
                        continue
                    if getattr(d.index, "tz", None) is not None:
                        d.index = d.index.tz_localize(None)
                    out[s] = d
                    _save_cache(s, d)
                    got.add(s)
                except Exception:
                    continue
        for s in batch:
            if s not in got:
                failed.append(s)
        time.sleep(sleep)

    log(f"  prices ok={len(out)} failed={len(failed)}")
    return out, failed


AK_CACHE = os.path.join(ROOT, "data", "cache", "ak")
os.makedirs(AK_CACHE, exist_ok=True)


def fetch_hk_latest(symbols, log=print, workers=1):
    """以 AkShare（東方財富）補齊港股最新一根日線（Yahoo 當日 Close 常為 NaN）。

    回傳 {sym: DataFrame}（含 Open/High/Low/Close/Volume，日期索引），失敗者不列入。
    """
    import akshare as ak
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timedelta

    today = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=40)).strftime("%Y%m%d")
    end = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")

    def one(s, retries=3):
        path = os.path.join(AK_CACHE, f"{s.replace('.', '_')}_{today}.pkl")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return s, pickle.load(f)
            except Exception:
                pass
        code = f"{int(s.split('.')[0]):05d}"
        for k in range(retries):
            try:
                raw = ak.stock_hk_hist(symbol=code, period="daily", start_date=start,
                                       end_date=end, adjust="")
                if raw is None or raw.empty:
                    return s, None
                d = pd.DataFrame({
                    "Open": raw["开盘"].astype(float).values,
                    "High": raw["最高"].astype(float).values,
                    "Low": raw["最低"].astype(float).values,
                    "Close": raw["收盘"].astype(float).values,
                    "Volume": raw["成交量"].astype(float).values,
                }, index=pd.to_datetime(raw["日期"]))
                d.index.name = "Date"
                with open(path, "wb") as f:
                    pickle.dump(d, f)
                return s, d
            except Exception:
                time.sleep(0.4 * (k + 1))
        return s, None

    out = {}
    if workers and workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(one, symbols))
    else:
        results = []
        for i, s in enumerate(symbols):
            results.append(one(s))
            time.sleep(0.2)
    for s, d in results:
        if d is not None and not d.empty:
            out[s] = d
    log(f"  AkShare 港股最新資料 ok={len(out)}/{len(symbols)}")
    return out


def merge_akshare(prices, ak_map, log=print, max_days=7):
    """把 AkShare 較新的日線併入 Yahoo 資料（以重疊日比例校正至 Yahoo 調整價）。"""
    filled = 0
    details = []
    for s, akd in ak_map.items():
        y = prices.get(s)
        if y is None or y.empty or akd is None or akd.empty:
            continue
        last = y.index[-1]
        add = akd[akd.index > last].copy()
        if add.empty:
            continue
        if len(add) > max_days:
            add = add.iloc[-max_days:]
        # 以重疊日比例校正
        overlap = akd.index.intersection(y.index)
        ratio = 1.0
        if len(overlap):
            od = overlap[-1]
            try:
                ratio = float(y.loc[od, "Close"]) / float(akd.loc[od, "Close"])
            except Exception:
                ratio = 1.0
        for col in ["Open", "High", "Low", "Close"]:
            add[col] = add[col] * ratio
        add["Adj Close"] = add["Close"]
        merged = pd.concat([y, add])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
        prices[s] = merged
        filled += 1
        details.append(f"{s}:+{len(add)}")
    log(f"  以 AkShare 補齊 {filled} 檔港股最新日線")
    return prices, details


def fetch_info(sym, retries=2):
    for k in range(retries + 1):
        try:
            info = yf.Ticker(sym).info
            if info:
                return info
        except Exception:
            pass
        time.sleep(0.5 * (k + 1))
    return {}


def fetch_dividends(sym):
    try:
        return yf.Ticker(sym).dividends
    except Exception:
        return None
