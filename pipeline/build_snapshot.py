# -*- coding: utf-8 -*-
"""建立每日收市後資料快照（JSON）供靜態前端讀取。

用法：
    python -m pipeline.build_snapshot                # 增量（用快取）
    python -m pipeline.build_snapshot --refresh       # 重新抓價
    python -m pipeline.build_snapshot --limit 60      # 小樣本測試
"""
import argparse
import json
import os
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE_DATA = os.path.join(ROOT, "site", "data")
CACHE = os.path.join(ROOT, "data", "cache")
os.makedirs(SITE_DATA, exist_ok=True)
os.makedirs(os.path.join(SITE_DATA, "history"), exist_ok=True)
os.makedirs(os.path.join(CACHE, "info"), exist_ok=True)
os.makedirs(os.path.join(CACHE, "div"), exist_ok=True)

from . import config as C          # noqa: E402
from . import universe as U        # noqa: E402
from . import fetch as F           # noqa: E402
from . import indicators as I      # noqa: E402
from . import scoring as S         # noqa: E402

HKT = timezone(timedelta(hours=8))
MAX_YEARS = C.MAX_YEARS


def r(v, n=3):
    if v is None:
        return None
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, n)
    except Exception:
        return None


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def cached_fetch(sym, kind):
    """kind: info / div。以 pickle 快取。"""
    import pickle
    path = os.path.join(CACHE, kind, f"{sym.replace('/', '_')}.pkl")
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    if kind == "info":
        val = F.fetch_info(sym)
    else:
        val = F.fetch_dividends(sym)
    try:
        with open(path, "wb") as f:
            pickle.dump(val, f)
    except Exception:
        pass
    return val


def hist_arrays(df):
    cols = ["Open", "High", "Low", "Close", "Volume", "ma20", "ma50", "ma200",
            "rsi", "macd", "macd_signal", "macd_hist", "bb_up", "bb_mid", "bb_low",
            "atr", "vol_ma20"]
    out = {"t": [d.strftime("%Y-%m-%d") for d in df.index]}
    keymap = {"Open": "o", "High": "h", "Low": "l", "Close": "c", "Volume": "v"}
    for c in cols:
        k = keymap.get(c, c)
        if c == "Volume":
            out[k] = [None if pd.isna(x) else int(x) for x in df[c]]
        else:
            out[k] = [r(x, 3) for x in df[c]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--years", type=int, default=MAX_YEARS)
    ap.add_argument("--backup", action="store_true",
                    help="啟用 AkShare 備援補齊港股最新日線（需穩定網路；預設關閉）")
    args = ap.parse_args()

    t0 = time.time()
    log = lambda *a: print(*a, flush=True)  # noqa: E731

    log("1) 建立股票池 ...")
    uni = U.build(force_snapshot=False)
    hk, us = uni["hk"], uni["us"]
    if args.limit:
        hk, us = hk[:args.limit // 2], us[:args.limit // 2]
    symbols = hk + us
    market_of = {s: "HK" for s in hk}
    market_of.update({s: "US" for s in us})
    log(f"   港股池 {len(hk)} ＋ 美股池 {len(us)} = {len(symbols)} 檔")

    log("2) 抓取日線價格 ...")
    prices, failed_price = F.fetch_prices(symbols, years=args.years,
                                          refresh=args.refresh, log=log)
    backup_details, backup_used = [], 0
    if args.backup:
        log("2b) 備援：以 AkShare 補齊港股最新日線 ...")
        try:
            ak_map = F.fetch_hk_latest(hk, log=log)
            prices, backup_details = F.merge_akshare(prices, ak_map, log=log)
            backup_used = len(backup_details)
        except Exception as e:  # noqa
            log("   AkShare 備援失敗，續用 Yahoo 資料：", repr(e)[:120])

    log("3) 抓取基本面 / 股息資料 ...")
    infos, divs = {}, {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        for s, inf in zip(symbols, ex.map(lambda x: cached_fetch(x, "info"), symbols)):
            infos[s] = inf or {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        for s, dv in zip(symbols, ex.map(lambda x: cached_fetch(x, "div"), symbols)):
            divs[s] = dv

    log("4) 計算指標與評分 ...")
    liq = C.LIQUIDITY
    records = []
    excluded = {"no_price": 0, "short_history": 0, "low_price": 0, "low_turnover": 0, "halted": 0}
    cutoff_dates = []

    for s in symbols:
        d = prices.get(s)
        if d is None or d.empty:
            excluded["no_price"] += 1
            continue
        d = I.compute(d)
        n = len(d)
        if n < liq["min_history_days"]:
            excluded["short_history"] += 1
            continue
        last = d.iloc[-1]
        c = float(last["Close"])
        if pd.isna(c):
            excluded["no_price"] += 1
            continue
        mkt = market_of[s]
        min_price = liq["hk_min_price"] if mkt == "HK" else liq["us_min_price"]
        if c < min_price:
            excluded["low_price"] += 1
            continue
        tov = float(last["turnover_ma20"]) if not pd.isna(last["turnover_ma20"]) else 0.0
        min_tov = liq["hk_min_turnover"] if mkt == "HK" else liq["us_min_turnover"]
        if tov < min_tov:
            excluded["low_turnover"] += 1
            continue
        last_vol = float(last["Volume"]) if not pd.isna(last["Volume"]) else 0.0
        if last_vol <= 0:
            excluded["halted"] += 1
            continue

        info = infos.get(s, {})
        dv = divs.get(s)
        L = S.long_score(d, info, dv)
        Sh = S.short_score(d)
        cutoff_dates.append(d.index[-1])

        prev = d["Close"].iloc[-2] if n >= 2 else np.nan
        chg = (c / float(prev) - 1) * 100 if prev and not pd.isna(prev) else None
        name = info.get("longName") or info.get("shortName") or s
        cur = info.get("currency") or ("HKD" if mkt == "HK" else "USD")

        rec = {
            "symbol": s,
            "code": s.split(".")[0].lstrip("0") or "0",
            "name": name,
            "market": mkt,
            "currency": cur,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "close": r(c, 3),
            "change_pct": r(chg, 2),
            "turnover_ma20": r(tov, 0),
            "market_cap": r(info.get("marketCap"), 0),
            "dividend_yield": r(info.get("dividendYield"), 2),
            "pe": r(info.get("trailingPE"), 2),
            "pb": r(info.get("priceToBook"), 2),
            "roe": r((info.get("returnOnEquity") or 0) * 100, 1) if info.get("returnOnEquity") is not None else None,
            "ma20": r(last["ma20"], 3), "ma50": r(last["ma50"], 3), "ma200": r(last["ma200"], 3),
            "rsi": r(last["rsi"], 1), "macd_hist": r(last["macd_hist"], 4),
            "atr": r(last["atr"], 3),
            "dist_ma200_pct": r((c / float(last["ma200"]) - 1) * 100, 2) if not pd.isna(last["ma200"]) else None,
            "vol_ratio": r(float(last["Volume"]) / float(last["vol_ma20"]), 2) if not pd.isna(last["vol_ma20"]) and last["vol_ma20"] else None,
            "as_of": d.index[-1].strftime("%Y-%m-%d"),
            "history": s.replace("/", "_").replace(".", "_") + ".json",
            "long": L,
            "short": Sh,
        }
        records.append(rec)

        # 歷史檔（供圖表）
        daily, older = I.weekly_downsample(d, C.DAILY_RECENT_DAYS)
        hj = {"symbol": s, "name": name, "market": mkt, "currency": cur,
              "adjustment": "split-adjusted（拆分已調整；除息未回補）",
              "daily": hist_arrays(daily), "weekly": hist_arrays(older)}
        with open(os.path.join(SITE_DATA, "history", rec["history"]), "w", encoding="utf-8") as f:
            json.dump(hj, f, ensure_ascii=False, separators=(",", ":"))

    log(f"   納入掃描 {len(records)} 檔；排除 {excluded}")

    # 市場指數
    log("5) 抓取市場指數 ...")
    idx_syms = [v["yf"] for v in C.MARKET_INDICES.values()]
    idx_prices, _ = F.fetch_prices(idx_syms, years=5, refresh=args.refresh, log=lambda *a: None)
    markets = []
    for key, meta in C.MARKET_INDICES.items():
        d = idx_prices.get(meta["yf"])
        if d is None or len(d) < 2:
            continue
        d = I.compute(d)
        last = d.iloc[-1]
        prev = d["Close"].iloc[-2]
        markets.append({
            "key": key, "name": meta["name"], "market": meta["market"],
            "close": r(last["Close"], 2),
            "change_pct": r((last["Close"] / prev - 1) * 100, 2),
            "rsi": r(last["rsi"], 1),
            "above_ma200": bool(last["ma200"] == last["ma200"] and last["Close"] > last["ma200"]),
            "as_of": d.index[-1].strftime("%Y-%m-%d"),
        })

    # 候選輸出
    longs = [x for x in records if x["long"]["state"] == "確認"]
    long_watch = [x for x in records if x["long"]["state"] == "觀察"]
    shorts = [x for x in records if x["short"]["state"] == "確認"]
    short_watch = [x for x in records if x["short"]["state"] == "觀察"]
    longs.sort(key=lambda x: -x["long"]["score"])
    long_watch.sort(key=lambda x: -x["long"]["score"])
    shorts.sort(key=lambda x: -x["short"]["score"])
    short_watch.sort(key=lambda x: -x["short"]["score"])

    cutoff = max(cutoff_dates).strftime("%Y-%m-%d") if cutoff_dates else None
    hk_cut = [x["as_of"] for x in records if x["market"] == "HK"]
    us_cut = [x["as_of"] for x in records if x["market"] == "US"]
    hk_cutoff = max(hk_cut) if hk_cut else None
    us_cutoff = max(us_cut) if us_cut else None
    gen_utc = datetime.now(timezone.utc)
    now_hkt = gen_utc.astimezone(HKT)
    meta = {
        "generated_at_utc": gen_utc.strftime("%Y-%m-%d %H:%M UTC"),
        "generated_at_hkt": now_hkt.strftime("%Y-%m-%d %H:%M HKT"),
        "data_cutoff": cutoff,
        "data_cutoff_hk": hk_cutoff,
        "data_cutoff_us": us_cutoff,
        "data_cutoff_note": "各市場收市後更新；港股與美股最後一根日線日期可能不同",
        "source_primary": C.SOURCE_PRIMARY,
        "source_backup": C.SOURCE_BACKUP,
        "price_adjustment": "收盤價已按拆股調整；除息未回補（股息另列）",
        "delay_note": "非即時報價：每日收市後更新（延遲／收市後資料）",
        "scan": {
            "universe_hk": len(uni["hk"]), "universe_us": len(uni["us"]),
            "fetched": len(prices), "scanned": len(records),
            "failed_price": len(failed_price),
            "failed_symbols": failed_price[:80],
            "excluded": excluded,
            "scope_hk": "恒生指數＋恒生科技指數＋恒生中國企業指數成分，加策展中小型股補充",
            "scope_us": "S&P 500 ＋ Nasdaq 100",
            "liquidity": C.LIQUIDITY,
            "source_status": uni.get("status", {}),
            "backup_used": backup_used,
            "backup_note": "港股最新一根日線以 AkShare（東方財富）補齊，並以重疊日比例校正至 Yahoo 調整價；" if backup_used else "",
        },
        "portfolio_split": C.PORTFOLIO_SPLIT,
        "market_overview": markets,
        "candidate_counts": {
            "long_confirmed": len(longs), "long_watch": len(long_watch),
            "short_confirmed": len(shorts), "short_watch": len(short_watch),
        },
        "note": "本頁為靜態快照，非即時；每份結果標明實際掃描股數、範圍與資料截止時間（HKT）。",
    }

    def dump(name, obj):
        with open(os.path.join(SITE_DATA, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))

    dump("meta.json", meta)
    dump("screener.json", records)
    dump("long_candidates.json", {"confirmed": longs, "watch": long_watch})
    dump("short_candidates.json", {"confirmed": shorts, "watch": short_watch})
    dump("watchlist.json", {"default": C.DEFAULT_WATCHLIST})

    # ---- 本次執行狀態（供前端「本次未更新」橫幅與排程失敗判定）----
    pool = len(symbols)
    fetched = len(prices)
    ok = True
    message = ""
    if len(records) == 0:
        ok, message = False, "本次未更新：快照沒有納入任何個股（抓取或過濾全數失敗）。"
    elif not args.limit and pool and fetched < pool * 0.5:
        ok, message = False, (f"本次未更新：價格抓取大量失敗（僅取得 {fetched}/{pool} 檔）。"
                             "頁面顯示的是上一次成功快照。")
    status = {
        "ok": ok,
        "run_at_utc": gen_utc.strftime("%Y-%m-%d %H:%M UTC"),
        "run_at_hkt": now_hkt.strftime("%Y-%m-%d %H:%M HKT"),
        "data_cutoff_hk": hk_cutoff,
        "data_cutoff_us": us_cutoff,
        "scanned": len(records),
        "universe": pool,
        "fetched": fetched,
        "message": message,
    }
    dump("status.json", status)
    if not ok:
        log("!! " + message)
        log(f"完成（{ '部分' if len(records) else '失敗' }）：scan={len(records)}；耗時 {round(time.time()-t0,1)}s")
        sys.exit(2)

    log(f"完成：scan={len(records)}；長線候選 {len(longs)}（觀察 {len(long_watch)}）；"
        f"短線候選 {len(shorts)}（觀察 {len(short_watch)}）；耗時 {round(time.time()-t0,1)}s")
    log(f"輸出目錄：{SITE_DATA}")


if __name__ == "__main__":
    main()
