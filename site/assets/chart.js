/* 個股圖表：TradingView Lightweight Charts（本地 vendored）。
   主圖：K線 + MA20/50/200 + 布林 + 成交量；副圖：RSI / MACD / ATR（可開關）。 */
(function () {
  "use strict";
  const LWC = window.LightweightCharts;
  const UP = "#d92d20", DOWN = "#039855";
  const MA_COLORS = { ma20: "#2563eb", ma50: "#f79009", ma200: "#7c3aed" };

  function histURL(sym) { return "data/history/" + sym.replace(/\./g, "_") + ".json"; }

  function mergeHist(h) {
    const parts = [h.weekly, h.daily].filter((p) => p && p.t && p.t.length);
    const rows = [];
    for (const p of parts) {
      for (let i = 0; i < p.t.length; i++) {
        rows.push({
          time: p.t[i], open: p.o[i], high: p.h[i], low: p.l[i], close: p.c[i], value: p.v[i],
          ma20: p.ma20[i], ma50: p.ma50[i], ma200: p.ma200[i],
          rsi: p.rsi[i], macd: p.macd[i], macd_signal: p.macd_signal[i], macd_hist: p.macd_hist[i],
          bb_up: p.bb_up[i], bb_mid: p.bb_mid[i], bb_low: p.bb_low[i], atr: p.atr[i], vol_ma20: p.vol_ma20[i],
        });
      }
    }
    rows.sort((a, b) => a.time < b.time ? -1 : a.time > b.time ? 1 : 0);
    // 去除重複日期
    const out = [];
    for (const r of rows) if (!out.length || out[out.length - 1].time !== r.time) out.push(r);
    return out;
  }
  function cutByYears(rows, years) {
    if (!years || !rows.length) return rows;
    const last = new Date(rows[rows.length - 1].time);
    const from = new Date(last); from.setFullYear(from.getFullYear() - years);
    const fs = from.toISOString().slice(0, 10);
    return rows.filter((r) => r.time >= fs);
  }
  const line = (rows, k) => rows.filter((r) => r[k] !== null && r[k] !== undefined).map((r) => ({ time: r.time, value: r[k] }));

  function baseOptions() {
    return {
      layout: { background: { color: "#ffffff" }, textColor: "#6b7280", fontSize: 11 },
      grid: { vertLines: { color: "#f1f3f7" }, horzLines: { color: "#f1f3f7" } },
      rightPriceScale: { borderColor: "#e5e7eb" },
      timeScale: { borderColor: "#e5e7eb", timeVisible: false },
      crosshair: { mode: LWC.CrosshairMode.Normal },
    };
  }

  function create(mainEl, subsEl, meta, opts) {
    const state = Object.assign({ range: 0, ind: {} }, opts || {});
    let rowsAll = [];

    function draw() {
      const rows = cutByYears(rowsAll, state.range);
      mainEl.innerHTML = ""; subsEl.innerHTML = "";
      const chart = LWC.createChart(mainEl, Object.assign(baseOptions(), { height: mainEl.clientHeight || 360 }));
      const cs = chart.addCandlestickSeries({ upColor: UP, downColor: DOWN, borderUpColor: UP, borderDownColor: DOWN, wickUpColor: UP, wickDownColor: DOWN, priceLineVisible: false });
      cs.setData(rows.map((r) => ({ time: r.time, open: r.open, high: r.high, low: r.low, close: r.close })));

      if (state.ind.vol) {
        const vs = chart.addHistogramSeries({ priceScaleId: "vol", priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false });
        chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
        vs.setData(rows.map((r) => ({ time: r.time, value: r.value, color: r.close >= r.open ? "rgba(217,45,32,.45)" : "rgba(3,152,85,.45)" })));
      }
      ["ma20", "ma50", "ma200"].forEach((k) => {
        if (!state.ind[k]) return;
        const s = chart.addLineSeries({ color: MA_COLORS[k], lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
        s.setData(line(rows, k));
      });
      if (state.ind.boll) {
        [["bb_mid", "#64748b", false], ["bb_up", "#94a3b8", true], ["bb_low", "#94a3b8", true]].forEach(([k, c, dash]) => {
          const s = chart.addLineSeries({ color: c, lineWidth: 1, lineStyle: dash ? 2 : 0, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
          s.setData(line(rows, k));
        });
      }

      // 副圖
      const subCharts = [];
      function sub(title, height, build) {
        const box = document.createElement("div");
        box.className = "subchart";
        box.style.position = "relative";
        const lab = document.createElement("div");
        lab.className = "legend"; lab.style.position = "absolute"; lab.style.left = "8px"; lab.style.top = "2px"; lab.style.zIndex = "2";
        lab.textContent = title;
        subsEl.appendChild(box);
        const c = LWC.createChart(box, Object.assign(baseOptions(), { height }));
        c.timeScale().applyOptions({ visible: false });
        build(c);
        subCharts.push(c);
      }
      if (state.ind.rsi) sub("RSI(14)", 100, (c) => {
        const s = c.addLineSeries({ color: "#2563eb", lineWidth: 1, priceLineVisible: false });
        s.setData(line(rows, "rsi"));
        s.createPriceLine({ price: 70, color: "#f79009", lineWidth: 1, lineStyle: 2, axisLabelVisible: true });
        s.createPriceLine({ price: 50, color: "#94a3b8", lineWidth: 1, lineStyle: 2, axisLabelVisible: true });
        s.createPriceLine({ price: 30, color: "#039855", lineWidth: 1, lineStyle: 2, axisLabelVisible: true });
      });
      if (state.ind.macd) sub("MACD(12,26,9)", 100, (c) => {
        const hs = c.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false });
        hs.setData(rows.filter((r) => r.macd_hist !== null).map((r) => ({ time: r.time, value: r.macd_hist, color: r.macd_hist >= 0 ? "rgba(217,45,32,.5)" : "rgba(3,152,85,.5)" })));
        c.addLineSeries({ color: "#2563eb", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }).setData(line(rows, "macd"));
        c.addLineSeries({ color: "#f79009", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }).setData(line(rows, "macd_signal"));
      });
      if (state.ind.atr) sub("ATR(14)", 100, (c) => {
        c.addLineSeries({ color: "#7c3aed", lineWidth: 1, priceLineVisible: false }).setData(line(rows, "atr"));
      });

      // 時間軸同步
      const all = [chart].concat(subCharts);
      let syncing = false;
      all.forEach((c) => c.timeScale().subscribeVisibleLogicalRangeChange((r) => {
        if (syncing || !r) return;
        syncing = true;
        all.forEach((o) => { if (o !== c) { try { o.timeScale().setVisibleLogicalRange(r); } catch (e) {} } });
        syncing = false;
      }));

      // 圖例（十字線）
      const legend = document.getElementById("legend");
      if (legend && rows.length) legend.textContent = meta.symbol + "・" + (meta.name || "") +
        "・顯示 " + rows.length + " 個資料點（" + rows[0].time + " → " + rows[rows.length - 1].time + "）";
      chart.subscribeCrosshairMove((p) => {
        if (!p || !p.time) { legend.innerHTML = meta.symbol + "・" + (meta.name || "") + "・" + meta.adjustment; return; }
        const r = rows.find((z) => z.time === p.time); if (!r) return;
        legend.innerHTML = p.time + "　開 " + r.open + "　高 " + r.high + "　低 " + r.low + "　收 " + r.close +
          "　量 " + (r.value == null ? "—" : Number(r.value).toLocaleString()) +
          (r.ma20 != null ? "　MA20 " + r.ma20 : "") + (r.ma50 != null ? "　MA50 " + r.ma50 : "") +
          (r.ma200 != null ? "　MA200 " + r.ma200 : "") + (r.rsi != null ? "　RSI " + r.rsi : "");
      });

      // 自適應寬度
      const ro = new ResizeObserver(() => {
        chart.applyOptions({ width: mainEl.clientWidth });
        subCharts.forEach((c) => c.applyOptions({ width: subsEl.clientWidth }));
      });
      ro.observe(mainEl);
      chart.applyOptions({ width: mainEl.clientWidth });
      subCharts.forEach((c) => c.applyOptions({ width: subsEl.clientWidth }));
      chart.timeScale().fitContent();
      window.__stockRanges = all;
    }

    fetch(histURL(meta.symbol), { cache: "no-store" })
      .then((r) => { if (!r.ok) throw new Error("history " + r.status); return r.json(); })
      .then((h) => { rowsAll = mergeHist(h); draw(); })
      .catch((e) => { mainEl.innerHTML = '<div class="empty">此股未預載歷史圖表（' + e.message + "）。</div>"; });

    // 工具列（依初始狀態標示）
    document.querySelectorAll("#range button").forEach((b) => b.classList.toggle("on", +b.dataset.r === state.range));
    document.querySelectorAll("[data-ind]").forEach((b) => b.classList.toggle("on", !!state.ind[b.dataset.ind]));
    document.querySelectorAll("#range button").forEach((b) => b.onclick = () => {
      document.querySelectorAll("#range button").forEach((x) => x.classList.remove("on"));
      b.classList.add("on"); state.range = +b.dataset.r; draw();
    });
    document.querySelectorAll("[data-ind]").forEach((b) => b.onclick = () => {
      const k = b.dataset.ind; state.ind[k] = state.ind[k] ? 0 : 1;
      b.classList.toggle("on", !!state.ind[k]); draw();
    });
  }

  window.StockChart = { create: create };
})();
