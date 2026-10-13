# -*- coding: utf-8 -*-
"""建立港股＋美股掃描池（可追溯來源，供網站標示掃描範圍）。

港股池 = 恒生指數 + 恒生科技指數 + 恒生中國企業指數成分 + 策展中小型股補充
美股池 = S&P 500 + Nasdaq 100
指數成分以 Wikipedia 表格／恒生指數公司 factsheet PDF 抓取；抓取失敗時退回內建快照清單。
"""
import io
import os
import json
import re
import warnings
import requests
import pandas as pd

warnings.filterwarnings("ignore")

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "universe_snapshot.json")


def _get(url, **kw):
    return requests.get(url, headers=UA, timeout=40, **kw)


def _to_hk(code):
    code = re.sub(r"\D", "", str(code))
    if not code:
        return None
    return f"{int(code):04d}.HK"


def _to_us(sym):
    return str(sym).strip().replace(".", "-")


def sp500():
    r = _get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    r.raise_for_status()
    t = pd.read_html(io.StringIO(r.text))[0]
    col = "Symbol" if "Symbol" in t.columns else t.columns[0]
    return sorted({_to_us(x) for x in t[col].dropna()})


def nasdaq100():
    r = _get("https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies")
    r.raise_for_status()
    t = pd.read_html(io.StringIO(r.text))[0]
    col = "Ticker" if "Ticker" in t.columns else t.columns[0]
    return sorted({_to_us(x) for x in t[col].dropna()})


def _hk_from_wiki(url, table_idx):
    r = _get(url)
    r.raise_for_status()
    t = pd.read_html(io.StringIO(r.text))[table_idx]
    col = "Ticker" if "Ticker" in t.columns else t.columns[0]
    out = []
    for x in t[col].dropna():
        m = re.search(r"(\d{1,5})", str(x))
        if m:
            out.append(_to_hk(m.group(1)))
    return sorted({c for c in out if c})


def hsi():
    return _hk_from_wiki("https://en.wikipedia.org/wiki/Hang_Seng_Index", 6)


def hscei():
    return _hk_from_wiki("https://en.wikipedia.org/wiki/Hang_Seng_China_Enterprises_Index", 3)


def hstech():
    """恒生科技指數成分：由恒生指數公司 factsheet PDF 抽取 4 位數代碼。"""
    from pypdf import PdfReader
    url = "https://origin-www.hsi.com.hk/static/uploads/contents/zh_hk/dl_centre/factsheets/hstechc.pdf"
    r = _get(url)
    r.raise_for_status()
    path = "/tmp/hstech_factsheet.pdf"
    with open(path, "wb") as f:
        f.write(r.content)
    txt = "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)
    i = txt.find("成份股")
    seg = txt[i:] if i >= 0 else txt
    codes = re.findall(r"(?m)^\s*(\d{4})\s+", seg)
    return sorted({_to_hk(c) for c in codes})


def build(force_snapshot=False):
    """回傳 dict：hk/us 池、各指數成分、來源狀態。"""
    if os.path.exists(SNAP) and not force_snapshot:
        with open(SNAP, "r", encoding="utf-8") as f:
            return json.load(f)

    from . import config as C

    status = {}
    res = {}

    def safe(name, fn, fallback):
        try:
            v = fn()
            if v:
                status[name] = f"ok:{len(v)}"
                return v
        except Exception as e:  # noqa
            status[name] = f"fail:{type(e).__name__}"
        status[name] = status.get(name, "empty")
        return fallback

    res["sp500"] = safe("sp500", sp500, [])
    res["ndx"] = safe("ndx", nasdaq100, [])
    res["hsi"] = safe("hsi", hsi, [])
    res["hscei"] = safe("hscei", hscei, [])
    res["hstech"] = safe("hstech", hstech, [])

    hk = sorted(set(res["hsi"]) | set(res["hscei"]) | set(res["hstech"]) | set(C.HK_SUPPLEMENT))
    us = sorted(set(res["sp500"]) | set(res["ndx"]))
    res["hk"] = hk
    res["us"] = us
    res["status"] = status

    with open(SNAP, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    return res


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(HERE))
    from pipeline import universe  # type: ignore
    d = universe.build(force_snapshot=True)
    print("status:", d["status"])
    print("HK pool:", len(d["hk"]), " US pool:", len(d["us"]))
    print("HK sample:", d["hk"][:10])
    print("US sample:", d["us"][:10])
