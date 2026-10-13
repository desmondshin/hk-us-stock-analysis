/* 港股＋美股分析 — 共用前端邏輯（靜態快照，無後端） */
(function () {
  "use strict";

  const D = { meta: null, screener: [], bySym: new Map(), longs: null, shorts: null, watchDefault: [], status: null };
  const WKEY = "hk_us_watchlist_v2";

  async function jget(url) {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error(url + " → " + r.status);
    return r.json();
  }

  async function loadCore() {
    const [meta, screener, wl] = await Promise.all([
      jget("data/meta.json"), jget("data/screener.json"), jget("data/watchlist.json"),
    ]);
    D.meta = meta; D.screener = screener; D.watchDefault = wl.default || [];
    D.bySym = new Map(screener.map((x) => [x.symbol, x]));
    try { D.status = await jget("data/status.json"); } catch (e) { D.status = null; }
    return D;
  }

  /* ---------- 本次未更新 橫幅（排程抓取失敗時最醒目） ---------- */
  function statusBanner() {
    const st = D.status;
    if (!st || st.ok !== false) return "";
    const hk = st.data_cutoff_hk || (D.meta && D.meta.data_cutoff_hk) || "—";
    const us = st.data_cutoff_us || (D.meta && D.meta.data_cutoff_us) || "—";
    return '<div class="stale-banner" role="alert">' +
      "<b>⚠ 本次未更新</b>" +
      "<span>" + (st.message || "本次抓取失敗，頁面顯示的是上一次成功快照。") + "</span>" +
      "<span>顯示資料截止：港股 <b>" + hk + "</b>／美股 <b>" + us + "</b>（非本次快照）。</span>" +
      "</div>";
  }
  async function loadLongs() { if (!D.longs) D.longs = await jget("data/long_candidates.json"); return D.longs; }
  async function loadShorts() { if (!D.shorts) D.shorts = await jget("data/short_candidates.json"); return D.shorts; }

  /* ---------- 監察名單（localStorage） ---------- */
  function getWatch() {
    try {
      const v = JSON.parse(localStorage.getItem(WKEY));
      if (Array.isArray(v)) return v;
    } catch (e) {}
    return D.watchDefault.map((s) => ({ symbol: s, tag: "" }));
  }
  function setWatch(a) { localStorage.setItem(WKEY, JSON.stringify(a)); }

  /* ---------- 格式化 ---------- */
  const nf = (v, d) => (v === null || v === undefined || isNaN(v)) ? "—"
    : Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  function pctHTML(v) {
    if (v === null || v === undefined || isNaN(v)) return '<span class="muted">—</span>';
    const s = (v >= 0 ? "+" : "") + Number(v).toFixed(2) + "%";
    return '<span class="' + (v >= 0 ? "up" : "down") + '">' + s + "</span>";
  }
  function bigMoney(v, cur) {
    if (!v || isNaN(v)) return "—";
    const a = Math.abs(v);
    if (cur === "HKD" || cur === "CNY") {
      if (a >= 1e12) return (v / 1e12).toFixed(2) + "萬億";
      if (a >= 1e8) return (v / 1e8).toFixed(2) + "億";
      if (a >= 1e4) return (v / 1e4).toFixed(1) + "萬";
      return nf(v, 0);
    }
    if (a >= 1e12) return (v / 1e12).toFixed(2) + "T";
    if (a >= 1e9) return (v / 1e9).toFixed(2) + "B";
    if (a >= 1e6) return (v / 1e6).toFixed(1) + "M";
    if (a >= 1e3) return (v / 1e3).toFixed(1) + "K";
    return nf(v, 0);
  }
  const maxState = (s) => s === "確認" ? "ok" : s === "觀察" ? "warn" : "mute";
  function statePill(s) { return '<span class="pill ' + maxState(s) + '">' + s + "</span>"; }

  /* ---------- 版頭 / 掃描資訊 ---------- */
  const PAGES = [
    ["index.html", "總覽"], ["watchlist.html", "監察名單"],
    ["long.html", "長線候選"], ["short.html", "短線候選"],
  ];
  function renderHeader() {
    const el = document.getElementById("app-header");
    if (!el) return;
    const here = (location.pathname.split("/").pop() || "index.html");
    const tabs = PAGES.map(([h, t]) =>
      '<a href="' + h + '"' + (here === h ? ' class="active"' : "") + ">" + t + "</a>").join("");
    const m = D.meta || {};
    const sc = m.scan || {};
    const liq = sc.liquidity || {};
    el.innerHTML =
      '<div class="topbar"><div class="topbar-in">' +
      '<div class="brand">港股＋美股分析<small>每日收市後更新・延遲／收市後資料</small></div>' +
      '<nav class="tabs">' + tabs + "</nav></div></div>" +
      '<div class="scanbar"><div class="scanbar-in">' +
      "<span>資料截止 港股 <b>" + (m.data_cutoff_hk || m.data_cutoff || "—") + "</b>／美股 <b>" +
      (m.data_cutoff_us || m.data_cutoff || "—") + "</b>（HKT 收市後）</span>" +
      "<span>快照產生 <b>" + (m.generated_at_hkt || "—") + "</b></span>" +
      "<span>本次實際掃描 <b>" + (sc.scanned || 0) + "</b> 檔（港股 <b>" + (sc.universe_hk || 0) +
      "</b> ＋ 美股 <b>" + (sc.universe_us || 0) + "</b> 池，經流動性過濾）</span>" +
      '<span class="tag">範圍：' + (sc.scope_hk || "") + "；" + (sc.scope_us || "") + "</span>" +
      '<span class="tag">流動性門檻：港股≥' + (liq.hk_min_turnover ? (liq.hk_min_turnover / 1e6) + "M" : "") +
      "港元／美股≥" + (liq.us_min_turnover ? (liq.us_min_turnover / 1e6) + "M" : "") + "美元（" + (liq.window_days || 20) + "日均額）</span>" +
      '<span class="tag">' + (m.delay_note || "") + "</span>" +
      "</div></div>";
  }

  function disclaimer() {
    const m = D.meta || {};
    const sc = m.scan || {};
    const bak = sc.backup_used ? "本次港股最新日線以 AkShare（東方財富）補齊 " + sc.backup_used + " 檔。" : "";
    return '<div class="disclaimer">本網站為每日收市後產生的靜態快照，<b>非即時報價</b>；資料來自 ' +
      (m.source_primary || "") + "（備援：" + (m.source_backup || []).join("、") + "）。" + bak +
      "價格：" + (m.price_adjustment || "") + "。所有分數為規則化篩選結果，非投資建議；" +
      "本頁只涵蓋上述實際掃描範圍，不代表全市場。</div>";
  }

  function footer() {
    return '<div class="foot">資料來源與限制：' + (D.meta ? D.meta.source_primary : "") +
      "（非官方端點、無 SLA，可能限流或短暫未更新）。" +
      "下一次更新於各市場收市後執行。<br>本工具僅供研究參考，不構成任何投資建議。</div>";
  }

  /* ---------- 市場總覽 ---------- */
  function marketCards() {
    const ms = (D.meta.market_overview || []);
    return ms.map((m) =>
      '<div class="card"><h3>' + m.name + ' <span class="sect-badge">' + m.market + "</span></h3>" +
      '<div class="metric">' + nf(m.close, 2) + "</div>" +
      '<div class="small">日變動 ' + pctHTML(m.change_pct) + "・RSI " + nf(m.rsi, 1) +
      "・" + (m.above_ma200 ? "在 200 日線上" : "在 200 日線下") + "</div>" +
      '<div class="sect-badge">截至 ' + m.as_of + "</div></div>"
    ).join("");
  }

  /* ---------- 卡片 ---------- */
  function compBar(label, v) {
    const cls = v >= 70 ? "g" : v >= 45 ? "" : "w";
    return '<div class="comp"><span class="lbl">' + label + '</span><span class="bar ' + cls +
      '"><i style="width:' + Math.max(0, Math.min(100, v)) + '%"></i></span><span class="val">' + nf(v, 0) + "</span></div>";
  }
  function why(r, kind) {
    const items = (kind === "met" ? (r.reasons || []) : (r.fails || []));
    if (!items.length) return "";
    const lis = items.map((t) => '<li class="' + (kind === "met" ? "" : "no") + '">' + t + "</li>").join("");
    return '<ul class="reasons">' + lis + "</ul>";
  }
  function stockCard(x, which) {
    const r = which === "long" ? x.long : x.short;
    const c = r.components;
    const comps = which === "long"
      ? [["基本面", c.fundamental], ["股息", c.dividend], ["趨勢", c.trend]]
      : [["型態", c.pattern], ["動能", c.momentum], ["量能", c.volume]];
    return '<div class="stock-card">' +
      '<div class="hd"><div><div class="nm"><a href="stock.html?symbol=' + encodeURIComponent(x.symbol) + '">' +
      (x.name || x.symbol) + "</a></div>" +
      '<div class="sym">' + x.symbol + ' <span class="pill ' + (x.market === "HK" ? "hk" : "us") + '">' +
      x.market + "</span> " + statePill(r.state) + " " + (x.sector || "") + "</div></div>" +
      '<div><div class="score-big">' + nf(r.score, 1) + '</div><div class="sect-badge">等級 ' + r.grade + "</div></div></div>" +
      '<div class="small">收市 ' + nf(x.close, 2) + " " + (x.currency || "") + "・日變動 " + pctHTML(x.change_pct) +
      "・20日均額 " + bigMoney(x.turnover_ma20, x.currency) + "</div>" +
      '<div style="display:grid;gap:4px">' + comps.map((p) => compBar(p[0], p[1])).join("") + "</div>" +
      '<details class="why"><summary>入選原因（' + (r.reasons || []).length + "）</summary>" + why(r, "met") + "</details>" +
      '<details class="why"><summary>未符合條件（' + (r.fails || []).length + "）</summary>" + why(r, "no") + "</details>" +
      "</div>";
  }

  /* ---------- 篩選工具列 ---------- */
  function filterBar(id, sectors, extra) {
    const opts = sectors.map((s) => '<option value="' + s + '">' + s + "</option>").join("");
    return '<div class="toolbar" id="' + id + '">' +
      '<label>市場 <select class="f-mkt"><option value="">全部</option><option value="HK">港股</option><option value="US">美股</option></select></label>' +
      '<label>最低分 <input type="range" class="f-score" min="0" max="100" value="0" step="5"><b class="f-score-v">0</b></label>' +
      '<label>行業 <select class="f-sector"><option value="">全部</option>' + opts + "</select></label>" +
      (extra || "") +
      '<label>排序 <select class="f-sort"><option value="score">分數</option><option value="turnover">成交額</option><option value="change">日變動</option></select></label>' +
      '<span class="muted small f-count"></span></div>';
  }
  function wireFilter(id, render) {
    const bar = document.getElementById(id);
    if (!bar) return;
    const fire = () => {
      const mkt = bar.querySelector(".f-mkt").value;
      const sec = bar.querySelector(".f-sector").value;
      const min = +bar.querySelector(".f-score").value;
      const sort = bar.querySelector(".f-sort").value;
      bar.querySelector(".f-score-v").textContent = min;
      render({ mkt, sec, min, sort });
    };
    bar.addEventListener("input", fire);
    bar.addEventListener("change", fire);
    fire();
  }
  function applyFilter(list, f) {
    let a = list.filter((x) => (!f.mkt || x.market === f.mkt) && (!f.sec || x.sector === f.sec) &&
      ((x.long ? x.long.score : x.short.score) >= f.min));
    const key = (x) => f.sort === "turnover" ? (x.turnover_ma20 || 0)
      : f.sort === "change" ? (x.change_pct || -99) : (x.long ? x.long.score : x.short.score);
    a.sort((p, q) => key(q) - key(p));
    return a;
  }
  function sectorsOf(list) {
    return Array.from(new Set(list.map((x) => x.sector).filter(Boolean))).sort();
  }

  /* ---------- 各頁面 ---------- */
  function pageDashboard() {
    const m = D.meta;
    const cc = m.candidate_counts || {};
    const main = document.getElementById("page");
    main.innerHTML =
      "<h1>總覽</h1><p class='sub'>每日收市後快照的一次性檢視：市場概況、候選訊號數量、監察名單狀態。</p>" +
      '<div class="grid g-4">' + marketCards() + "</div>" +
      '<h2>候選訊號</h2>' +
      '<div class="grid g-4">' +
      '<div class="card"><h3>長線候選（確認）</h3><div class="metric">' + (cc.long_confirmed || 0) +
      '</div><div class="small">另有觀察 ' + (cc.long_watch || 0) + ' 檔</div><a class="small" href="long.html">查看長線候選 →</a></div>' +
      '<div class="card"><h3>短線候選（確認）</h3><div class="metric">' + (cc.short_confirmed || 0) +
      '</div><div class="small">另有觀察 ' + (cc.short_watch || 0) + ' 檔</div><a class="small" href="short.html">查看短線候選 →</a></div>' +
      '<div class="card"><h3>實際掃描</h3><div class="metric">' + (m.scan.scanned || 0) +
      '</div><div class="small">港股 ' + (m.scan.universe_hk || 0) + " ＋ 美股 " + (m.scan.universe_us || 0) + " 檔池</div></div>" +
      '<div class="card"><h3>資料截止</h3><div class="metric" style="font-size:15px">港股 ' +
      (m.data_cutoff_hk || "—") + "／美股 " + (m.data_cutoff_us || "—") +
      '</div><div class="small">' + (m.generated_at_hkt || "") + "</div></div>" +
      "</div>" +
      '<h2>監察名單重點</h2>' +
      '<div class="table-wrap"><table><thead><tr><th>股票</th><th>市場</th><th>收市</th><th>日變動</th>' +
      '<th>長線（分/狀態）</th><th>短線（分/狀態）</th><th>資料截止</th></tr></thead><tbody id="wl-body"></tbody></table></div>' +
      disclaimer() + footer();

    const watch = getWatch();
    const rows = watch.map((w) => D.bySym.get(w.symbol)).filter(Boolean).map((x) =>
      "<tr><td><a href='stock.html?symbol=" + encodeURIComponent(x.symbol) + "'>" + (x.name || x.symbol) +
      '</a><div class="sect-badge">' + x.symbol + "</div></td>" +
      '<td><span class="pill ' + (x.market === "HK" ? "hk" : "us") + '">' + x.market + "</span></td>" +
      "<td>" + nf(x.close, 2) + "</td><td>" + pctHTML(x.change_pct) + "</td>" +
      "<td>" + nf(x.long.score, 1) + " " + statePill(x.long.state) + "</td>" +
      "<td>" + nf(x.short.score, 1) + " " + statePill(x.short.state) + "</td>" +
      '<td class="muted">' + x.as_of + "</td></tr>").join("");
    document.getElementById("wl-body").innerHTML = rows ||
      '<tr><td colspan="7" class="muted">監察名單為空或未包含在掃描範圍。</td></tr>';
  }

  function pageWatchlist() {
    const main = document.getElementById("page");
    main.innerHTML =
      "<h1>我的監察名單</h1><p class='sub'>可加入／移除、設定分類標籤；設定儲存在此瀏覽器（localStorage），不需後端。</p>" +
      '<div class="toolbar"><input type="text" id="add-sym" placeholder="輸入代號，如 0700.HK / AAPL" style="min-width:220px">' +
      '<input type="text" id="add-tag" placeholder="分類標籤（選填）" style="min-width:140px">' +
      '<button class="primary" id="add-btn">加入</button>' +
      '<button class="ghost" id="reset-btn">重設為預設</button>' +
      '<span id="add-msg" class="small muted"></span></div>' +
      '<div class="table-wrap"><table><thead><tr><th>股票</th><th>市場</th><th>分類</th><th>收市</th>' +
      '<th>日變動</th><th>長線</th><th>短線</th><th>20日均額</th><th></th></tr></thead><tbody id="wl-body"></tbody></table></div>' +
      '<p class="small muted">提示：新加入的代號若不在本次掃描範圍（' + (D.meta.scan.scanned) +
      " 檔）內，將顯示「不在掃描範圍」，需待下一次收市後快照納入。</p>" + footer();

    function draw() {
      const watch = getWatch();
      const body = document.getElementById("wl-body");
      body.innerHTML = watch.map((w, i) => {
        const x = D.bySym.get(w.symbol);
        if (!x) return "<tr><td><b>" + w.symbol + '</b><div class="sect-badge">不在本次掃描範圍</div></td>' +
          '<td colspan="6"></td><td>—</td><td><button class="ghost rm" data-i="' + i + '">移除</button></td></tr>';
        return "<tr><td><a href='stock.html?symbol=" + encodeURIComponent(x.symbol) + "'>" + (x.name || x.symbol) +
          '</a><div class="sect-badge">' + x.symbol + "</div></td>" +
          '<td><span class="pill ' + (x.market === "HK" ? "hk" : "us") + '">' + x.market + "</span></td>" +
          '<td><input type="text" class="tag-in" data-i="' + i + '" value="' + (w.tag || "") + '" placeholder="—" style="width:96px"></td>' +
          "<td>" + nf(x.close, 2) + "</td><td>" + pctHTML(x.change_pct) + "</td>" +
          "<td>" + nf(x.long.score, 1) + " " + statePill(x.long.state) + "</td>" +
          "<td>" + nf(x.short.score, 1) + " " + statePill(x.short.state) + "</td>" +
          "<td>" + bigMoney(x.turnover_ma20, x.currency) + "</td>" +
          '<td><button class="ghost rm" data-i="' + i + '">移除</button></td></tr>';
      }).join("") || '<tr><td colspan="9" class="muted">尚未加入任何股票。</td></tr>';

      body.querySelectorAll("button.rm").forEach((b) => b.onclick = () => {
        const a = getWatch(); a.splice(+b.dataset.i, 1); setWatch(a); draw();
      });
      body.querySelectorAll("input.tag-in").forEach((inp) => inp.onchange = () => {
        const a = getWatch(); a[+inp.dataset.i].tag = inp.value; setWatch(a);
      });
    }
    document.getElementById("add-btn").onclick = () => {
      const v = document.getElementById("add-sym").value.trim().toUpperCase();
      const tag = document.getElementById("add-tag").value.trim();
      if (!v) return;
      const a = getWatch();
      if (a.some((w) => w.symbol === v)) { document.getElementById("add-msg").textContent = "已在名單中。"; return; }
      a.push({ symbol: v, tag: tag }); setWatch(a);
      document.getElementById("add-sym").value = ""; document.getElementById("add-msg").textContent = "已加入 " + v + "。";
      draw();
    };
    document.getElementById("reset-btn").onclick = () => {
      setWatch(D.watchDefault.map((s) => ({ symbol: s, tag: "" }))); draw();
    };
    draw();
  }

  async function pageLong() {
    const data = await loadLongs();
    const main = document.getElementById("page");
    main.innerHTML =
      "<h1>長線候選（權重 70%）</h1>" +
      "<p class='sub'>依「基本面＋股息＋趨勢」三項獨立給分再合成；只列趨勢確認且達標者。與短線評分完全分開。</p>" +
      filterBar("fb", sectorsOf(data.confirmed.concat(data.watch)), "") +
      '<h2>確認候選 <span class="muted small" id="c-count"></span></h2><div class="grid g-3" id="c-list"></div>' +
      '<h2>觀察名單（條件接近未確認）</h2><div class="grid g-3" id="w-list"></div>' +
      disclaimer() + footer();
    function render(f) {
      const conf = applyFilter(data.confirmed, f);
      document.getElementById("c-list").innerHTML = conf.map((x) => stockCard(x, "long")).join("") ||
        '<div class="empty">沒有符合目前篩選的確認候選。</div>';
      document.getElementById("w-list").innerHTML = applyFilter(data.watch, f).slice(0, 60).map((x) => stockCard(x, "long")).join("") ||
        '<div class="empty">沒有觀察名單。</div>';
      document.getElementById("c-count").textContent = "顯示 " + conf.length + " / 共 " +
        data.confirmed.length + " 檔符合（全池 " + D.meta.scan.scanned + " 檔）";
      document.querySelector("#fb .f-count").textContent = "確認候選 " + data.confirmed.length +
        "・觀察 " + data.watch.length + " 檔";
    }
    wireFilter("fb", render);
  }

  async function pageShort() {
    const data = await loadShorts();
    const main = document.getElementById("page");
    main.innerHTML =
      "<h1>短線候選（權重 30%）</h1>" +
      "<p class='sub'>依「型態突破＋動能＋量能」獨立給分；確認需收盤突破＋放量＋動能條件同時成立（寧遲勿錯）。與長線評分完全分開。</p>" +
      filterBar("fb", sectorsOf(data.confirmed.concat(data.watch)), "") +
      '<h2>確認候選 <span class="muted small" id="c-count"></span></h2><div class="grid g-3" id="c-list"></div>' +
      '<h2>觀察名單（突破／動能接近但未確認）</h2><div class="grid g-3" id="w-list"></div>' +
      disclaimer() + footer();
    function render(f) {
      const conf = applyFilter(data.confirmed, f);
      document.getElementById("c-list").innerHTML = conf.map((x) => stockCard(x, "short")).join("") ||
        '<div class="empty">沒有符合目前篩選的確認候選（收市突破＋放量條件嚴格，常有空清單）。</div>';
      document.getElementById("w-list").innerHTML = applyFilter(data.watch, f).slice(0, 60).map((x) => stockCard(x, "short")).join("") ||
        '<div class="empty">沒有觀察名單。</div>';
      document.getElementById("c-count").textContent = "顯示 " + conf.length + " / 共 " +
        data.confirmed.length + " 檔符合（全池 " + D.meta.scan.scanned + " 檔）";
      document.querySelector("#fb .f-count").textContent = "確認候選 " + data.confirmed.length +
        "・觀察 " + data.watch.length + " 檔";
    }
    wireFilter("fb", render);
  }

  function pageStock() {
    const sym = new URLSearchParams(location.search).get("symbol") || "";
    const x = D.bySym.get(sym);
    const main = document.getElementById("page");
    if (!x) {
      main.innerHTML = "<h1>個股詳情</h1><p class='sub'>找不到 " + (sym || "（未指定代號）") +
        "。可能不在本次掃描範圍（" + D.meta.scan.scanned + " 檔）或代號有誤。</p>" +
        '<p><a href="index.html">← 回總覽</a></p>' + footer();
      return;
    }
    const cur = x.currency || "";
    main.innerHTML =
      "<h1>" + (x.name || x.symbol) + " <span class='pill " + (x.market === "HK" ? "hk" : "us") + "'>" +
      x.market + "</span></h1>" +
      "<p class='sub'>" + x.symbol + "・" + (x.sector || "—") + (x.industry ? " / " + x.industry : "") +
      "・通訊" + (cur === "HKD" ? "港元" : cur === "USD" ? "美元" : cur) +
      "・資料截止 " + x.as_of + "（HKT 收市後快照，非即時）</p>" +
      '<div class="grid g-4">' +
      '<div class="card"><h3>收市價</h3><div class="metric">' + nf(x.close, 2) + '</div><div class="small">日變動 ' + pctHTML(x.change_pct) + "</div></div>" +
      '<div class="card"><h3>長線評分</h3><div class="metric">' + nf(x.long.score, 1) + '</div><div class="small">' + statePill(x.long.state) + " 等級 " + x.long.grade + "</div></div>" +
      '<div class="card"><h3>短線評分</h3><div class="metric">' + nf(x.short.score, 1) + '</div><div class="small">' + statePill(x.short.state) + " 等級 " + x.short.grade + "</div></div>" +
      '<div class="card"><h3>20 日均額</h3><div class="metric">' + bigMoney(x.turnover_ma20, cur) + '</div><div class="small">市值 ' + bigMoney(x.market_cap, cur) + "</div></div>" +
      "</div>" +
      '<h2>歷史走勢與技術指標</h2>' +
      '<div class="chart-card"><div class="chart-tools" id="ct">' +
      '<div class="grp" id="range"><button data-r="1" >1年</button><button data-r="3">3年</button><button data-r="5">5年</button><button data-r="10">10年</button><button data-r="0" class="on">全部</button></div>' +
      '<span class="lab">主圖</span><div class="grp"><button data-ind="ma20" class="on">MA20</button><button data-ind="ma50" class="on">MA50</button><button data-ind="ma200" class="on">MA200</button><button data-ind="boll">布林</button><button data-ind="vol" class="on">成交量</button></div>' +
      '<span class="lab">副圖</span><div class="grp"><button data-ind="rsi">RSI</button><button data-ind="macd">MACD</button><button data-ind="atr">ATR</button></div>' +
      "</div>" +
      '<div class="legend" id="legend"></div>' +
      '<div id="main-chart"></div><div id="subcharts"></div>' +
      '<div class="legend">' + (x.history ? "" : "") + '價格：' + "拆分已調整、除息未回補" +
      "・延遲／收市後・來源 Yahoo Finance（yfinance）。</div></div>" +
      '<h2>長線評分（權重 70%）</h2>' + scorePanel(x.long, [["基本面", "fundamental"], ["股息", "dividend"], ["趨勢", "trend"]]) +
      '<h2>短線評分（權重 30%）</h2>' + scorePanel(x.short, [["型態", "pattern"], ["動能", "momentum"], ["量能", "volume"]]) +
      '<h2>基本面與股息摘要</h2>' + fundTable(x, cur) +
      disclaimer() + footer();

    const q = new URLSearchParams(location.search);
    const ind = { ma20: 1, ma50: 1, ma200: 1, boll: 0, vol: 1, rsi: 0, macd: 0, atr: 0 };
    (q.get("ind") || "").split(",").forEach((k) => { if (k in ind) ind[k] = 1; });
    const rng = q.get("range");
    const initRange = rng === "1" ? 1 : rng === "3" ? 3 : rng === "5" ? 5 : rng === "10" ? 10 : 0;
    window.StockChart.create(document.getElementById("main-chart"),
      document.getElementById("subcharts"), x,
      { range: initRange, ind: ind });
  }

  function scorePanel(r, comps) {
    return '<div class="card"><div class="grid g-2"><div>' +
      comps.map((c) => compBar(c[0], r.components[c[1]])).join("") +
      '<div class="sect-badge" style="margin-top:6px">權重：' +
      comps.map((c) => c[0] + " " + Math.round((r.weights[c[1]] || 0) * 100) + "%").join("・") + "</div></div>" +
      '<div><div class="small muted">入選原因</div>' + (why(r, "met") || '<div class="small muted">—</div>') +
      '<div class="small muted" style="margin-top:6px">未符合條件</div>' + (why(r, "no") || '<div class="small muted">—</div>') +
      "</div></div></div>";
  }
  function fundTable(x, cur) {
    const rows = [
      ["市盈率 PE", x.pe], ["市帳率 PB", x.pb], ["ROE %", x.roe], ["股息率 %", x.dividend_yield],
      ["MA20", x.ma20], ["MA50", x.ma50], ["MA200", x.ma200],
      ["距 MA200 %", x.dist_ma200_pct], ["RSI", x.rsi], ["MACD 柱", x.macd_hist],
      ["ATR", x.atr], ["量比（對20日均量）", x.vol_ratio],
    ];
    return '<div class="table-wrap"><table><tbody>' +
      rows.map((r) => "<tr><th>" + r[0] + "</th><td>" + (r[1] === null || r[1] === undefined ? "—" : nf(r[1], 2)) + "</td></tr>").join("") +
      "</tbody></table></div>";
  }

  /* ---------- 啟動 ---------- */
  async function boot() {
    const page = document.body.dataset.page || "index";
    try {
      await loadCore();
    } catch (e) {
      document.getElementById("page").innerHTML =
        '<div class="empty">載入資料快照失敗：' + e.message +
        "<br>請確認已執行資料管線並以靜態伺服器開啟（非 file://）。</div>";
      return;
    }
    renderHeader();
    const hdr = document.getElementById("app-header");
    if (hdr && hdr.insertAdjacentHTML) hdr.insertAdjacentHTML("afterend", statusBanner());
    try {
      if (page === "index") pageDashboard();
      else if (page === "watchlist") pageWatchlist();
      else if (page === "long") await pageLong();
      else if (page === "short") await pageShort();
      else if (page === "stock") pageStock();
    } catch (e) {
      document.getElementById("page").innerHTML = '<div class="empty">頁面錯誤：' + e.message + "</div>";
    }
  }
  window.addEventListener("DOMContentLoaded", boot);
})();
