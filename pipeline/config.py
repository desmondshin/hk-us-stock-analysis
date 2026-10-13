# -*- coding: utf-8 -*-
"""MVP 設定：股票池、流動性門檻、長／短線評分權重與參數。

所有門檻皆集中於此；網站端可就「檢視篩選」即時調整（見 site 前端），
完整重掃門檻則改動本檔後重跑 pipeline。
"""

# ---- 歷史長度 ----
MAX_YEARS = 20                      # 最多 20 年（不足則顯示可得範圍）
DAILY_RECENT_DAYS = 1260            # 近期保留「每日」資料約 5 年
# 更早資料以「每週」抽樣（縮小快照體積）

# ---- 流動性門檻（預設值；網站內可調）----
LIQUIDITY = {
    "window_days": 20,              # 平均成交額視窗（交易日）
    "hk_min_turnover": 50_000_000,  # 港股 ≥ 5,000 萬港元／日
    "us_min_turnover": 20_000_000,  # 美股 ≥ 2,000 萬美元／日
    "hk_min_price": 1.0,            # 港股 ≥ HK$1
    "us_min_price": 5.0,            # 美股 ≥ US$5
    "min_history_days": 260,        # 少於約 1 年日線者剔除
}

# ---- 長線（權重 70%）----
LONG_WEIGHTS = {"fundamental": 0.50, "dividend": 0.20, "trend": 0.30}
LONG_PARAMS = {
    "ma_long": 200, "ma_mid": 50,
    "confirm_days": 5,              # 黃金交叉／站上均線需連續確認日數
    "roe_good": 0.15, "roe_ok": 0.08,
    "min_dividend_yield": 2.0,      # %
    "max_payout_ratio": 0.80,       # 派息比率上限（可持續性）
    "min_market_cap": 0,            # 0 = 不設限（網站內可調）
}

# ---- 短線（權重 30%）----
SHORT_WEIGHTS = {"pattern": 0.40, "momentum": 0.35, "volume": 0.25}
SHORT_PARAMS = {
    "breakout_window": 20,          # 突破近 N 日高
    "rsi_low": 50, "rsi_high": 70,  # 健康動能區
    "vol_expand": 1.3,              # 量能放大倍數門檻
    "confirm_days": 3,              # 突破需於近 N 個交易日內發生
    "min_conditions": 2,            # 至少同時成立的動能條件數 K
}

# ---- 市場指數（總覽用）----
MARKET_INDICES = {
    "HSI": {"yf": "^HSI", "name": "恒生指數", "market": "HK"},
    "HSTECH": {"yf": "3033.HK", "name": "恒生科技指數（ETF 代理 3033.HK）", "market": "HK"},
    "HSCEI": {"yf": "^HSCE", "name": "恒生中國企業指數", "market": "HK"},
    "SPX": {"yf": "^GSPC", "name": "S&P 500", "market": "US"},
    "NDX": {"yf": "^NDX", "name": "Nasdaq 100", "market": "US"},
    "IXIC": {"yf": "^IXIC", "name": "Nasdaq Composite", "market": "US"},
    "VIX": {"yf": "^VIX", "name": "VIX 波動率", "market": "US"},
}

# ---- 港股補充：恆指／恒生科技／國企以外、20 日平均成交額較高的中小型股（curated）----
# 說明：免費來源沒有可靠的「全港上市清單 + 成交額排行」API，故以策展名單補足，
# 之後可按同一格式擴充。實際掃描範圍以每頁標示為準。
HK_SUPPLEMENT = [
    "0291.HK",  # 華潤啤酒
    "0322.HK",  # 康師傅
    "0384.HK",  # 中國燃氣
    "0489.HK",  # 東風集團
    "0688.HK",  # 中國海外發展
    "0762.HK",  # 中國聯通
    "0836.HK",  # 華潤電力
    "0902.HK",  # 華能國際
    "0916.HK",  # 龍源電力
    "0960.HK",  # 龍湖集團
    "0968.HK",  # 信義光能
    "1038.HK",  # 長江基建
    "1044.HK",  # 恒安國際
    "1093.HK",  # 石藥集團
    "1099.HK",  # 國藥控股
    "1109.HK",  # 華潤置地
    "1177.HK",  # 中國生物製藥
    "1211.HK",  # 比亞迪股份
    "1299.HK",  # 友邦保險
    "1339.HK",  # 中國人民保險
    "1378.HK",  # 中國宏橋
    "1658.HK",  # 郵儲銀行
    "1919.HK",  # 中遠海控
    "1929.HK",  # 周大福
    "2015.HK",  # 理想汽車
    "2313.HK",  # 申洲國際
    "2331.HK",  # 李寧
    "2382.HK",  # 舜宇光學
    "2628.HK",  # 中國人壽
    "2688.HK",  # 新奧能源
    "3328.HK",  # 交通銀行
    "3968.HK",  # 招商銀行
    "3988.HK",  # 中國銀行
    "6030.HK",  # 中信証券
    "6098.HK",  # 碧桂園服務
    "6618.HK",  # 京東健康
    "6862.HK",  # 海底撈
    "9618.HK",  # 京東集團
    "9633.HK",  # 農夫山泉
    "9868.HK",  # 小鵬汽車
]

# ---- 預設監察名單（使用者可於網站增減，存於瀏覽器 localStorage）----
DEFAULT_WATCHLIST = [
    "0700.HK", "0005.HK", "9988.HK", "3690.HK", "1810.HK",
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
]

# ---- 資料來源（主力／備援）----
SOURCE_PRIMARY = "Yahoo Finance（yfinance 套件，非官方端點）"
SOURCE_BACKUP = ["AkShare（復權因子交叉校驗）", "Stooq（長歷史備援）"]

PORTFOLIO_SPLIT = {"long": 0.70, "short": 0.30}

# 掃描／輸出位置
RAW_CACHE = "data/cache"
