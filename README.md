# 港股＋美股分析網站 — 第二階段 MVP（部署＋每日排程）

> **方案 A：靜態優先。** 全站為每日收市後產生的**靜態快照**，非即時報價、無互動式後端、無回測。
> **第三階段電郵提醒未獲授權，未實作、未寄任何郵件。**
> 本 repo 不含任何帳號、密鑰或個人資料（監察名單存於使用者瀏覽器 localStorage）。

---

## 1. 線上網址

- 部署平台：**GitHub Pages**（分支 `main` 的 Actions 成品，發布目錄＝`site/`）。
- 公開網址：**`https://desmondshin.github.io/hk-us-stock-analysis/`**
  （首次部署完成後即生效；任何時候可開啟，不依賴本機或沙箱。）

> 若之後要改用自訂網域，於 repo `Settings → Pages → Custom domain` 設定，並在 `site/` 放 `CNAME` 即可。

---

## 2. 每日自動更新（GitHub Actions）

`.github/workflows/daily.yml` 於**每個交易日**港股、美股收市後各跑一次：

| 場次 | cron（UTC） | 當地時間 | 說明 |
|---|---|---|---|
| 港股收市後 | `30 8 * * 1-5` | 16:30 HKT | 港股 16:00 收市後抓當日線 |
| 美股收市後 | `0 21 * * 1-5` | 17:00 ET（夏令）／16:00 EST（冬令） | 美股 16:00 收市後抓當日線 |

- **cron 一律使用 UTC**；`1-5` 代表週一至五（港、美公眾假期當日抓不到新日線，屬正常）。
- 另支援 `workflow_dispatch` 手動觸發，以及 push 到 `main` 時跑一次（首次部署即會產生完整快照）。
- 每次流程：`checkout → pip install → python -m pipeline.build_snapshot --refresh`（重抓價格）`→ commit 快照回 repo → 部署 site/ 到 Pages`。
- **每次排程都會產生一次 commit**，因此 repo 不會連續 60 天無活動，Actions 的排程不會被自動停用。
  （若真的要長期停跑，GitHub 會在連續 60 天無活動後停用排程，屆時在 Actions 頁面按一次 Enable 即可。）

### 「大聲失敗」與「本次未更新」

- 管線每次都會在 `site/data/status.json` 寫下本次結果。
- 若**抓取失敗**（例如 NASA／來源限流、僅取得少量價格）：`status.json.ok = false`，頁面頂部會出現紅色橫幅 **「⚠ 本次未更新」**，並註明目前顯示的是**上一次成功快照**及其資料截止日——**不會靜默沿用舊數**。
- 同時該次 Action 會**標紅失敗並發出通知**（最後一步 `exit 1`），但**仍會部署**橫幅頁面，讓人一眼看到未更新。
- 只有當次真的取得新資料時，才會覆蓋 `site/data/` 並顯示新截止日。

---

## 3. 部署步驟（repo 已備妥，只需啟用 Pages）

1. 建立公開 repo `hk-us-stock-analysis`，把本專案 push 到 `main`。
   ```bash
   git init && git add -A && git commit -m "init: HK/US stock analysis MVP"
   git branch -M main
   git remote add origin https://github.com/desmondshin/hk-us-stock-analysis.git
   git push -u origin main
   ```
2. repo `Settings → Pages → Build and deployment → Source` 選 **GitHub Actions**。
3. 到 `Actions` 頁確認 `每日快照更新與部署` 首次執行成功（push 會自動觸發一次）。
4. 完成後開啟 `https://desmondshin.github.io/hk-us-stock-analysis/`。

> 免費帳號的 Pages 需**公開 repo**；本專案不含私人資料，公開可接受。
> `site/.nojekyll` 已放好，避免 Pages 以 Jekyll 處理而漏掉 `data/` 底線路徑。

---

## 4. 本機執行與測試

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt

./venv/bin/python -m pipeline.build_snapshot            # 增量（有快取）
./venv/bin/python -m pipeline.build_snapshot --refresh  # 重新抓價（排程用）
./venv/bin/python -m pipeline.build_snapshot --backup   # 啟用 AkShare 備援（見 §7）
./venv/bin/python -m pipeline.build_snapshot --limit 40 # 小樣本自測（會跳過大量失敗判定）

python3 -m http.server 8412 --directory site
# 瀏覽 http://127.0.0.1:8412/index.html
```

### 測試步驟（人工驗收）

1. **總覽**：頂部顯示「資料截止 港股…／美股…」「快照產生…」「本次實際掃描 N 檔」與掃描範圍、流動性門檻。
2. **監察名單**：輸入 `9988.HK` 或 `NVDA` 加入、設分類、移除、重設；重新載入確認保留（存 localStorage）。
3. **長線候選**：以「市場＝港股」「最低分 80」篩選；展開任一卡，確認「入選原因／未符合條件」逐條列出。
4. **短線候選**：確認只有嚴格「突破＋放量＋動能」者列於「確認候選」，其餘在「觀察名單」。
5. **個股頁**：切換 1／3／5／10／全部年；開關 MA20/50/200、布林、量、RSI、MACD、ATR；確認下方長／短線兩套評分分開呈現。
6. **手機**：縮到手機寬度或用手機開啟，確認單欄卡片、導覽可橫向滑動、圖表可縮放。
7. **未更新橫幅**：把 `site/data/status.json` 改成 `{"ok": false}` 後重新整理，確認頂部出現紅色「本次未更新」橫幅（測完記得改回）。

---

## 5. 架構與資料流

```
免費來源(yfinance 主力) → 每日收市後 Python 管線
   → 清洗／復權 → 指標(MA/RSI/MACD/BOLL/ATR) → 長、短線評分
   → JSON 快照(site/data/*.json, site/data/history/*.json)
   → 靜態前端(site/assets/app.js + 本地 vendored Lightweight Charts)
   → GitHub Actions 部署 → GitHub Pages
```

## 6. 專案結構

```
.
├─ .github/workflows/daily.yml   # 每日排程：產生快照 → commit → 部署 Pages
├─ scripts/mark_status.py        # 把本次執行結果寫入 status.json（失敗＝本次未更新）
├─ pipeline/                     # 資料管線（Python）
│  ├─ config.py                  # 股票池補充、流動性門檻、長/短線權重（集中調整處）
│  ├─ universe.py                # 建立港/美股池（Wikipedia＋恒生 factsheet PDF）
│  ├─ fetch.py                   # 抓價、基本面、股息；AkShare 備援（可選）
│  ├─ indicators.py              # MA/RSI/MACD/BOLL/ATR/量能
│  ├─ scoring.py                 # 長線、短線兩套獨立評分＋理由
│  └─ build_snapshot.py          # 主程式：產出 JSON 快照與 status.json
├─ site/                         # 靜態前端（發布目錄）
│  ├─ index/watchlist/long/short/stock.html
│  ├─ assets/{styles.css, app.js, chart.js}
│  ├─ vendor/lightweight-charts.standalone.production.js
│  ├─ data/                      # 快照輸出（meta/status/screener/candidates/history）
│  └─ .nojekyll
└─ requirements.txt
```

---

## 7. 已知限制（誠實版）

1. **無即時報價**：只有每日收市後快照。港股可能比美股晚一個交易日結算（來源端結算時間差）。
2. **非官方來源無保證**：`yfinance` 為非官方端點、免 key、無 SLA，可能限流或短暫缺值；本專案已用 20 年日線、流動性過濾降低影響，並以 `status.json` 明示失敗。
3. **AkShare 備援預設關閉**：沙箱環境連線不穩（遠端常被重置），故僅在 `--backup` 時啟用；在 GitHub Actions 的穩定網路可視需要開啟，並以重疊日比例校正至 Yahoo 調整價。
4. **港股基本面／股息較薄**：部分中小型港股欄位缺漏，該分項以可取得欄位正規化，可能偏高或偏低。
5. **不做全市場掃描**：受限免費來源速率，採限定股票池（恒指＋恒生科技＋國企＋策展中小型股補充；S&P 500＋Nasdaq 100），非全港／全美清單。
6. **長線候選數量偏多**：多頭市場中大量個股符合「趨勢＋基本面」，已按分數排序並提供即時篩選，可再收緊 `pipeline/config.py` 門檻。
7. **恒生科技指數**：Yahoo 無該指數歷史，總覽以 `3033.HK` ETF 代理（已標示）。
8. **監察名單存於瀏覽器 localStorage**：換裝置／清快取會遺失，且無跨裝置同步（靜態網站無後端）。
9. **回測未做**：依方案，回測留待 MVP 之後。
10. **排程為「最佳努力」**：GitHub 排程在尖峰時可能延遲數分鐘至數十分鐘；港股假期當日不會有新日線（屬正常，不算失敗）。

---

## 8. 下一階段建議

1. **電郵提醒（第三階段）**：待 Desmond 確認收件地址、頻率與明確授權後實作（預設 `desmondshin@gmail.com`）；建議只寄「確認態」新訊號、每日一次、附當日快照連結並可退訂。**未授權前不實作、不寄。**
2. **資料穩定化**：於 Actions 穩定網路開啟 AkShare／Stooq 交叉校驗；把失敗告警接去 Email／Slack（通知管道可用 GitHub Actions 內建通知或另接 Webhook）。
3. **互動式後端／回測**（需常駐主機或 Cloud Computer，另需成本確認）：參數自訂、訊號回測（勝率／期望值）。
4. **基本面強化**：接 FMP／Alpha Vantage 抽查美股基本面；港股補風控欄位。
5. **前端框架化**：若有編輯需求，再將現有靜態前端改為 Next.js 元件（資料層不動）。

---

## 9. 本階段未做（避免誤解）

- 未實作、未寄任何電郵（第三階段，待授權）。
- 未做即時報價、未做互動式後端、未做回測。
- 未宣稱「全市場掃描／全市場最佳」；結果僅涵蓋頁面標示的實際掃描範圍。

*本工具僅供研究參考，不構成投資建議。*
