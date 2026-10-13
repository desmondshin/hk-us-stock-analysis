# -*- coding: utf-8 -*-
"""長線 / 短線兩套獨立評分、理由與確認狀態。原則：寧遲勿錯（以收盤確認）。"""
import numpy as np
import pandas as pd

from . import config as C


# ---------- 小工具 ----------
def _num(x):
    try:
        v = float(x)
        if np.isnan(v):
            return None
        return v
    except Exception:
        return None


def _pct(x):
    v = _num(x)
    return None if v is None else v * 100.0


def _last(s, n=1):
    s = s.dropna()
    if len(s) < n:
        return None
    return float(s.iloc[-1])


def _held(days_true, n):
    """最近 n 日是否持續為真。"""
    if len(days_true) < n:
        return False
    return bool(days_true.iloc[-n:].all())


class Acc:
    """累積分項分數與理由。"""

    def __init__(self):
        self.pts = 0.0
        self.max = 0.0
        self.reasons = []
        self.fails = []

    def add(self, pts, mx, ok, met_text, fail_text):
        """條件成立才給分。"""
        if ok:
            self.pts += pts
        self.max += mx
        (self.reasons if ok else self.fails).append(met_text if ok else fail_text)

    def add_graded(self, pts, mx, ok, met_text, fail_text):
        """無論是否達標都按比例給分（用於量能等連續值）。"""
        self.pts += max(0.0, min(float(pts), float(mx)))
        self.max += mx
        (self.reasons if ok else self.fails).append(met_text if ok else fail_text)

    def add_na(self, mx, text):
        self.max += mx
        self.fails.append(text)

    def score(self):
        return round(100.0 * self.pts / self.max, 1) if self.max > 0 else 0.0


# ---------- 長線 ----------
def long_score(d, info, div):
    p = C.LONG_PARAMS
    close = d["Close"]
    ma50, ma200 = d["ma50"], d["ma200"]
    last = _last(close)

    # 趨勢分
    tr = Acc()
    above200 = close > ma200
    met = _held(above200, p["confirm_days"])
    tr.add(30, 30, met,
           f"收盤 {last:.2f} 站上 200 日均線（連續 {p['confirm_days']} 日確認）",
           "收盤未連續站上 200 日均線")
    slope = ma200 - ma200.shift(20)
    rising = slope > 0
    tr.add(25, 25, _held(rising, p["confirm_days"]),
           "200 日均線走平向上",
           "200 日均線仍向下")
    gold = ma50 > ma200
    cross_days = _held(gold, p["confirm_days"])
    tr.add(25, 25, cross_days,
           "50 日線高於 200 日線（黃金交叉成立）",
           "50 日線未高於 200 日線（未黃金交叉）")
    order = (d["ma20"] > ma50) & (ma50 > ma200)
    tr.add(20, 20, _held(order, p["confirm_days"]),
           "均線多頭排列（20>50>200）",
           "均線未呈多頭排列")
    trend = tr.score()

    # 基本面分
    fu = Acc()
    roe = _num(info.get("returnOnEquity"))
    if roe is not None:
        if roe >= p["roe_good"]:
            fu.add(25, 25, True, f"ROE {roe*100:.1f}%（≥{p['roe_good']*100:.0f}%）", "")
        elif roe >= p["roe_ok"]:
            fu.add_graded(12, 25, True, f"ROE {roe*100:.1f}%（中等）", "")
        else:
            fu.add(0, 25, False, "", f"ROE {roe*100:.1f}%（低於門檻）")
    else:
        fu.add_na(25, "ROE 資料缺失（未評分）")
    gm = _num(info.get("grossMargins"))
    if gm is not None:
        fu.add(12, 12, gm >= 0.30, f"毛利率 {gm*100:.1f}%", f"毛利率偏低 {gm*100:.1f}%")
    else:
        fu.add_na(12, "毛利率資料缺失")
    om = _num(info.get("operatingMargins"))
    if om is not None:
        fu.add(12, 12, om >= 0.12, f"營業利益率 {om*100:.1f}%", f"營業利益率偏低 {om*100:.1f}%")
    else:
        fu.add_na(12, "營業利益率資料缺失")
    de = _num(info.get("debtToEquity"))
    if de is not None:
        ratio = de / 100.0 if de > 10 else de
        fu.add(12, 12, ratio <= 1.0, f"負債權益比 {ratio:.2f}", f"負債權益比偏高 {ratio:.2f}")
    else:
        fu.add_na(12, "負債比資料缺失")
    fcf = _num(info.get("freeCashflow"))
    if fcf is not None:
        fu.add(10, 10, fcf > 0, "自由現金流為正", "自由現金流為負")
    else:
        fu.add_na(10, "自由現金流資料缺失")
    rg = _num(info.get("revenueGrowth"))
    if rg is not None:
        fu.add(12, 12, rg > 0, f"營收成長 {rg*100:.1f}%", f"營收衰退 {rg*100:.1f}%")
    else:
        fu.add_na(12, "營收成長資料缺失")
    eg = _num(info.get("earningsGrowth"))
    if eg is not None:
        fu.add(12, 12, eg > 0, f"盈利成長 {eg*100:.1f}%", f"盈利衰退 {eg*100:.1f}%")
    else:
        fu.add_na(12, "盈利成長資料缺失")
    pe = _num(info.get("trailingPE"))
    pb = _num(info.get("priceToBook"))
    if pe is not None or pb is not None:
        ok = (pe is not None and 0 < pe < 30) and (pb is None or pb < 5)
        txt = f"估值 PE {pe:.1f}" if pe else ""
        if pb is not None:
            txt += (f"／PB {pb:.2f}" if txt else f"PB {pb:.2f}")
        fu.add(8, 8, ok, txt, txt + "（估值偏高）")
    else:
        fu.add_na(8, "估值資料缺失")
    fundamental = fu.score()

    # 股息分
    dv = Acc()
    dy = _num(info.get("dividendYield"))
    if dy is not None and dy > 1.0:      # yfinance 新格式為百分比
        dy = dy
    elif dy is not None and dy <= 1.0:
        dy = dy * 100.0
    if dy is not None and dy > 0:
        dv.add(30, 30, dy >= p["min_dividend_yield"],
               f"股息率 {dy:.2f}%（≥{p['min_dividend_yield']:.0f}%）",
               f"股息率 {dy:.2f}%（低於 {p['min_dividend_yield']:.0f}% 門檻）")
    else:
        dv.add(0, 30, False, "", "無派息或股息資料缺失")
    pr = _num(info.get("payoutRatio"))
    if pr is not None:
        ratio = pr if pr <= 2 else pr / 100.0
        dv.add(25, 25, ratio <= p["max_payout_ratio"],
               f"派息比率 {ratio*100:.0f}%（可持續）",
               f"派息比率 {ratio*100:.0f}%（高於 {p['max_payout_ratio']*100:.0f}% 上限）")
    else:
        dv.add_na(25, "派息比率資料缺失")
    streak = dividend_streak(div)
    if streak is not None:
        dv.add(25, 25, streak >= 3, f"連續派息 {streak} 年", f"連續派息僅 {streak} 年")
    else:
        dv.add_na(25, "派息紀錄資料缺失")
    growth = dividend_growth(div)
    if growth is not None:
        dv.add(20, 20, growth > 0, f"近年股息成長約 {growth*100:.0f}%", f"近年股息下滑約 {growth*100:.0f}%")
    else:
        dv.add_na(20, "股息成長資料不足")
    dividend = dv.score()

    w = C.LONG_WEIGHTS
    total = round(w["fundamental"] * fundamental + w["dividend"] * dividend + w["trend"] * trend, 1)
    if trend >= 80 and total >= 65:
        state = "確認"
    elif trend >= 50 and total >= 50:
        state = "觀察"
    else:
        state = "未符合"
    grade = "A" if total >= 72 else "B" if total >= 58 else "C" if total >= 42 else "D"
    return {
        "score": total, "grade": grade, "state": state,
        "components": {"fundamental": fundamental, "dividend": dividend, "trend": trend},
        "weights": w,
        "reasons": tr.reasons + fu.reasons + dv.reasons,
        "fails": tr.fails + fu.fails + dv.fails,
    }


# ---------- 短線 ----------
def short_score(d):
    p = C.SHORT_PARAMS
    close = d["Close"]
    last = _last(close)
    high20 = _last(d["high20"])
    vol = d["Volume"]
    volratio = None
    vma = _last(d["vol_ma20"])
    if vma and vma > 0:
        volratio = float(vol.dropna().iloc[-1]) / vma

    pt = Acc()
    n = p["confirm_days"]
    br = (close > d["high20"]) & d["high20"].notna()
    recent = br.iloc[-n:] if len(br) >= 1 else br
    breakout_recent = bool(recent.any())
    breakout_vol_ok = False
    breakout_day = None
    if breakout_recent:
        last_br = recent[recent].index[-1]
        breakout_day = last_br.strftime("%Y-%m-%d")
        v_at, vma_at = d.loc[last_br, "Volume"], d.loc[last_br, "vol_ma20"]
        if vma_at and vma_at > 0:
            breakout_vol_ok = float(v_at) / float(vma_at) >= p["vol_expand"]
    if high20 is not None:
        pt.add(40, 40, breakout_recent,
               f"近 {n} 個交易日內收盤突破 {p['breakout_window']} 日高（{high20:.2f}）",
               f"近 {n} 個交易日內未收盤突破 {p['breakout_window']} 日高")
    else:
        pt.add_na(40, "區間高低資料不足")
    ma_up = d["ma20"] > d["ma50"]
    pt.add(25, 25, _held(ma_up, p["confirm_days"]),
           "20 日線高於 50 日線（短均線偏多）",
           "20 日線未高於 50 日線")
    above = close > d["ma20"]
    pt.add(20, 20, _held(above, p["confirm_days"]),
           "收盤站上 20 日線",
           "收盤未站上 20 日線")
    order = (close > d["ma20"]) & (d["ma20"] > d["ma50"]) & (d["ma50"] > d["ma200"])
    pt.add(15, 15, _held(order, p["confirm_days"]),
           "短、中、長均線多頭排列",
           "均線未完整多頭排列")
    pattern = pt.score()

    mo = Acc()
    rsi = _last(d["rsi"])
    conditions = 0
    if rsi is not None:
        in_zone = (rsi >= p["rsi_low"]) and (rsi <= p["rsi_high"])
        if in_zone:
            conditions += 1
        mo.add(35, 35, in_zone,
               f"RSI {rsi:.0f} 位於健康動能區（{p['rsi_low']}-{p['rsi_high']}）",
               f"RSI {rsi:.0f} 不在健康區（{p['rsi_low']}-{p['rsi_high']}）")
    else:
        mo.add_na(35, "RSI 資料不足")
    hist = _last(d["macd_hist"])
    if hist is not None:
        ok = hist > 0
        if ok:
            conditions += 1
        mo.add(35, 35, ok, "MACD 柱狀體轉正（動能偏多）", "MACD 柱狀體未轉正")
    else:
        mo.add_na(35, "MACD 資料不足")
    ret20 = None
    if len(close.dropna()) > 21:
        ret20 = float(close.dropna().iloc[-1] / close.dropna().iloc[-21] - 1)
    if ret20 is not None:
        ok = ret20 > 0
        if ok:
            conditions += 1
        mo.add(30, 30, ok, f"近 20 日漲幅 {ret20*100:.1f}%", f"近 20 日跌幅 {ret20*100:.1f}%")
    else:
        mo.add_na(30, "價格動能資料不足")
    momentum = mo.score()

    vo = Acc()
    if volratio is not None:
        vr = min(volratio, 3.0)
        pts = max(0.0, (vr - 1.0) / (2.5 - 1.0)) * 60
        ok = volratio >= p["vol_expand"]
        vo.add_graded(pts, 60, ok,
               f"成交量為 20 日均量的 {volratio:.2f} 倍（放量）",
               f"成交量僅 20 日均量的 {volratio:.2f} 倍（未放量）")
    else:
        vo.add_na(60, "量能資料不足")
    t_ok = False
    if _last(d["turnover_ma20"]):
        t_ok = _last(d["turnover"]) >= _last(d["turnover_ma20"])
    vo.add(20, 20, bool(t_ok), "成交額高於 20 日均額", "成交額低於 20 日均額")
    up = d["ret1"] > 0
    uv = (d["Volume"] * up).rolling(10, min_periods=5).sum().dropna()
    dv2 = (d["Volume"] * (~up)).rolling(10, min_periods=5).sum().dropna()
    if len(uv) and len(dv2):
        ok = float(uv.iloc[-1]) > float(dv2.iloc[-1])
        vo.add(20, 20, ok, "近 10 日上漲量能大於下跌量能", "近 10 日量能偏空（下跌量較大）")
    else:
        vo.add_na(20, "量價資料不足")
    volume = vo.score()

    w = C.SHORT_WEIGHTS
    total = round(w["pattern"] * pattern + w["momentum"] * momentum + w["volume"] * volume, 1)
    if breakout_recent and breakout_vol_ok and conditions >= p["min_conditions"]:
        state = "確認"
    elif breakout_recent or pattern >= 45 or momentum >= 65:
        state = "觀察"
    else:
        state = "未符合"
    grade = "A" if total >= 72 else "B" if total >= 58 else "C" if total >= 42 else "D"
    return {
        "score": total, "grade": grade, "state": state,
        "components": {"pattern": pattern, "momentum": momentum, "volume": volume},
        "weights": w, "conditions": conditions,
        "vol_ratio": round(volratio, 2) if volratio is not None else None,
        "breakout_recent": breakout_recent,
        "breakout_day": breakout_day,
        "breakout_vol_ok": breakout_vol_ok,
        "reasons": pt.reasons + mo.reasons + vo.reasons,
        "fails": pt.fails + mo.fails + vo.fails,
    }


# ---------- 股息輔助 ----------
def dividend_streak(div):
    if div is None or len(div) == 0:
        return None
    ys = pd.Series(div.index).dt.year
    years = sorted(set(int(y) for y in ys), reverse=True)
    if not years:
        return None
    streak, expected = 1, years[0] - 1
    for y in years[1:]:
        if y == expected:
            streak += 1
            expected -= 1
        elif y < expected:
            break
    return streak


def dividend_growth(div):
    if div is None or len(div) == 0:
        return None
    s = pd.Series(div)
    by_year = s.groupby(s.index.year).sum()
    if len(by_year) < 4:
        return None
    recent = by_year.tail(3).mean()
    base = by_year.tail(6).head(3).mean() if len(by_year) >= 6 else by_year.head(3).mean()
    if base <= 0:
        return None
    return float(recent / base - 1)
