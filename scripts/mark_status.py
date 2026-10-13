# -*- coding: utf-8 -*-
"""把本次排程執行結果寫入 site/data/status.json。

用法：
    python scripts/mark_status.py <pipeline_exit_code>

行為：
  - 管線成功（exit 0）且已寫出 status.json → 保留該檔（ok=true）。
  - 管線失敗（exit != 0）或未寫出 status.json → 強制標示「本次未更新」，
    並沿用 meta.json 上一次成功快照的資料截止日，讓頁面橫幅說清楚
    「顯示的是舊資料、非本次快照」。
  這個檔會隨 site/ 一起部署，所以即使抓取失敗，頁面也會明確顯示未更新，
  不會靜默沿用舊數。
"""
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "site", "data")
os.makedirs(DATA, exist_ok=True)

ST = os.path.join(DATA, "status.json")
META = os.path.join(DATA, "meta.json")

code = 1
if len(sys.argv) > 1:
    try:
        code = int(str(sys.argv[1]).strip())
    except ValueError:
        code = 1


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


meta = load(META)
st = load(ST)

now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

if code != 0 or st.get("ok") is not True:
    st = {
        "ok": False,
        "message": st.get("message")
        or "本次未更新：資料抓取／產生流程失敗，頁面顯示的是上一次成功快照。",
        "data_cutoff_hk": st.get("data_cutoff_hk") or meta.get("data_cutoff_hk"),
        "data_cutoff_us": st.get("data_cutoff_us") or meta.get("data_cutoff_us"),
        "last_generated_at_hkt": st.get("last_generated_at_hkt")
        or meta.get("generated_at_hkt"),
    }

st["checked_at_utc"] = now
with open(ST, "w", encoding="utf-8") as f:
    json.dump(st, f, ensure_ascii=False, indent=0)

print("status.json →", json.dumps(st, ensure_ascii=False))
