"use strict";
let STRATEGY = null;
const $ = (s, el = document) => el.querySelector(s);
const DASH = "—";
const esc = (s) => String(s ?? DASH).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : null);
const link = (u, text) => (safeUrl(u) ? `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(text)}</a>` : esc(text));
const yi = (v, d = 1) => (v == null ? DASH : `${v >= 0 ? "+" : ""}${(v / 1e8).toLocaleString("zh-TW", { minimumFractionDigits: d, maximumFractionDigits: d })} 億`);
const pct = (v, d = 1, signed = true) => (v == null ? DASH : `${signed && v >= 0 ? "+" : ""}${(v * 100).toFixed(d)}%`);
const num = (v, d = 2) => (v == null ? DASH : v.toLocaleString("zh-TW", { minimumFractionDigits: d, maximumFractionDigits: d }));
const signCls = (v) => (v == null || v === 0 ? "" : v > 0 ? "up" : "down");
const mark = (v) => (v === true ? '<span class="yes">✓</span>' : v === false ? '<span class="no">✗</span>' : '<span class="unk">?</span>');
const C_LABEL = { positive: ["有正面評等", "ok"], negative_only: ["僅負面評等", "bad"], neutral: ["僅中立／未載明評等", "plain"], no_coverage: ["無覆蓋／查無公開報導", "plain"], not_checked: ["未查證", "warn"] };

const store = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } } };

async function getJSON(path) {
  const r = await fetch(path, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return r.json();
}

function ratingsHTML(c, compact = false) {
  if (!c.ratings || !c.ratings.length) return `<span class="tag ${C_LABEL[c.status]?.[1] || "plain"}">${esc(C_LABEL[c.status]?.[0] || c.status)}</span>`;
  return c.ratings.map((r) => {
    const tp = typeof r.target_price === "number" ? `TP ${r.target_price.toLocaleString("zh-TW")}` : "TP —";
    const cls = r.polarity === "positive" ? "ok" : r.polarity === "negative" ? "bad" : "plain";
    const body = `${esc(r.broker)}｜${esc(r.rating)}｜${tp}｜${esc(r.date)}`;
    return compact ? `<div>${link(r.url, body)}</div>` : `<div><span class="tag ${cls}">${esc(r.broker)} ${esc(r.rating)}</span> <span class="small num">${tp}・${esc(r.date)}</span> ${safeUrl(r.url) ? link(r.url, r.source || "來源") : ""}</div>`;
  }).join("");
}

const SIGNAL_CLS = { "可進場": "ok", "觀察": "plain", "過熱": "warn", "排除": "bad" };
const signalTag = (s) => (s.signal ? `<span class="tag ${SIGNAL_CLS[s.signal] || "plain"}">${esc(s.signal)}</span>` : "");
const stopOf = (s, st) => {
  const t = s.tech || {}, x = st?.exit;
  if (!t.close || !x) return null;
  const byAtr = t.atr ? t.close - x.atr_mult * t.atr : -Infinity;
  return Math.max(byAtr, t.close * (1 - x.max_stop_pct));
};

function tagsFor(s) {
  const t = [signalTag(s)];
  if (s.order) t.push('<span class="tag accent">模擬買進</span>');
  if (s.new_entry) t.push('<span class="tag accent">新進榜</span>');
  if (s.attention) t.push('<span class="tag warn">注意股</span>');
  if (s.disposal) t.push('<span class="tag bad">處置股</span>');
  if (s.volume_up) t.push('<span class="tag warn">量增</span>');
  if (s.dominant) t.push('<span class="tag accent">法人主導</span>');
  (s.B.themes || []).slice(0, 3).forEach((x) => t.push(`<span class="tag plain">${esc(x)}</span>`));
  return t.join("");
}

function renderSummary(rep) {
  const m = rep.market, sm = rep.summary;
  const total = m["上市"].net + m["上櫃"].net, foreign = m["上市"].foreign + m["上櫃"].foreign, trust = m["上市"].trust + m["上櫃"].trust;
  const top = rep.picks.slice(0, 3).map((s, i) => `
    <div class="card">
      <div class="stock-head">
        <div><span class="rank">${i + 1}</span><span class="code">${esc(s.code)}</span><span class="name">${esc(s.name)}</span>
          <div class="small muted">${esc(s.industry)}・${esc(s.market)}</div></div>
        <div class="price"><b class="num">${num(s.close)}</b><div class="small num ${signCls(s.chg5)}">5日 ${pct(s.chg5)}</div></div>
      </div>
      <div style="margin-top:8px">${tagsFor(s)}</div>
      <div class="metrics">
        <div class="metric"><div class="k">量增比</div><div class="v num">${num(s.vol_ratio)}</div></div>
        <div class="metric"><div class="k">5日法人買超</div><div class="v num ${signCls(s.net_amt)}">${yi(s.net_amt)}</div></div>
        <div class="metric"><div class="k">買超／成交值</div><div class="v num">${pct(s.net_ratio, 1, false)}</div></div>
        <div class="metric"><div class="k">綜合分數</div><div class="v num">${num(s.score, 0)}</div></div>
      </div>
      ${s.signal_reasons ? `<div class="small muted">進場訊號：${esc(s.signal)}・${esc((s.signal_reasons || []).join("、"))}</div>` : ""}
    </div>`).join("");
  $("#summary").innerHTML = `
    <div class="kpis">
      <div class="kpi"><div class="label">今日入選</div><div class="value num">${sm.count}<small>檔</small></div></div>
      <div class="kpi"><div class="label">三大法人5日合計</div><div class="value num ${signCls(total)}">${yi(total, 0)}</div></div>
      <div class="kpi"><div class="label">外資5日</div><div class="value num ${signCls(foreign)}">${yi(foreign, 0)}</div></div>
      <div class="kpi"><div class="label">投信5日</div><div class="value num ${signCls(trust)}">${yi(trust, 0)}</div></div>
    </div>
    <p class="card small">${esc(sm.market_line)}</p>
    ${regimeCard(m.regime)}
    ${portfolioBrief(rep.portfolio)}
    <h2>前 3 名重點</h2>
    ${top || '<div class="card empty">今日無個股同時符合所有條件。</div>'}
    ${rep.research_enabled ? "" : '<div class="card small"><span class="tag warn">注意</span> 本次未啟用網路研究（未設定 API 金鑰），永續性、投行評等與新聞未查證，因此可能沒有個股入選。詳見「說明」。</div>'}`;
}

function pickCard(s, i) {
  const news = (s.news || []).map((n) => `<li>${link(n.url, n.title || n.summary)}<div class="small">${esc(n.summary)}</div><div class="meta">${esc(n.source)}・${esc(n.date)}</div></li>`).join("");
  return `
  <article class="card">
    <div class="stock-head">
      <div><span class="rank">${i + 1}</span><span class="code">${esc(s.code)}</span><span class="name">${esc(s.name)}</span>
        <div class="small muted">${esc(s.industry)}・${esc(s.market)}・候選池第 ${s.rank} 名</div></div>
      <div class="price"><b class="num">${num(s.close)}</b><div class="small num ${signCls(s.chg5)}">5日 ${pct(s.chg5)}</div></div>
    </div>
    <div style="margin-top:8px">${tagsFor(s)}</div>
    <div class="metrics">
      <div class="metric"><div class="k">量增比（5日/20日均量）</div><div class="v num">${num(s.vol_ratio)}</div></div>
      <div class="metric"><div class="k">5日三大法人買超</div><div class="v num ${signCls(s.net_amt)}">${yi(s.net_amt, 2)}</div></div>
      <div class="metric"><div class="k">外資／投信</div><div class="v num small"><span class="${signCls(s.foreign_amt)}">${yi(s.foreign_amt, 2)}</span>／<span class="${signCls(s.trust_amt)}">${yi(s.trust_amt, 2)}</span></div></div>
      <div class="metric"><div class="k">買超占成交值</div><div class="v num">${pct(s.net_ratio, 1, false)}</div></div>
      <div class="metric"><div class="k">本益比</div><div class="v num">${num(s.pe, 1)}</div></div>
      <div class="metric"><div class="k">外資持股（5日變化）</div><div class="v num">${num(s.qfii_ratio)}% <span class="small ${signCls(s.qfii_chg5)}">(${s.qfii_chg5 == null ? DASH : (s.qfii_chg5 >= 0 ? "+" : "") + s.qfii_chg5.toFixed(2) + "pp"})</span></div></div>
      <div class="metric"><div class="k">融資5日增減</div><div class="v num ${signCls(s.margin_chg5)}">${s.margin_chg5 == null ? DASH : (s.margin_chg5 >= 0 ? "+" : "") + s.margin_chg5.toLocaleString("zh-TW") + " 張"}</div></div>
      <div class="metric"><div class="k">5日成交值</div><div class="v num">${yi(s.value5, 1).replace("+", "")}</div></div>
      <div class="metric"><div class="k">綜合分數（0–100）</div><div class="v num">${num(s.score, 0)}</div></div>
      <div class="metric"><div class="k">5日法人買超天數／投信連買</div><div class="v num">${s.buy_days ?? DASH} 天／${s.trust_streak ?? DASH} 天</div></div>
      <div class="metric"><div class="k">20日均線（乖離）</div><div class="v num">${num(s.tech?.ma)} <span class="small">(${pct(s.tech?.bias)})</span></div></div>
      <div class="metric"><div class="k">參考停損（隔日開盤進場）</div><div class="v num">${num(stopOf(s, STRATEGY))}</div></div>
    </div>
    <dl class="basis">
      <dt>進場訊號</dt><dd>${signalTag(s)} ${esc((s.signal_reasons || []).join("、") || DASH)}</dd>
      <dt>永續依據</dt><dd>${esc(s.A.basis)} ${(s.A.evidence || []).map((e) => link(e.url, "來源")).join(" ")}</dd>
      <dt>未來性依據</dt><dd>${esc(s.B.basis)}</dd>
      <dt>投行評等（近3個月）</dt><dd>${ratingsHTML(s.C)}</dd>
      ${news ? `<dt>近一週新聞</dt><dd><ul class="news-list">${news}</ul></dd>` : ""}
    </dl>
  </article>`;
}

function picksTable(picks) {
  const rows = picks.map((s) => `<tr>
    <td class="sticky"><b>${esc(s.code)}</b> ${esc(s.name)}</td><td>${signalTag(s)}</td><td class="r num">${num(s.score, 0)}</td><td>${esc(s.industry)}</td>
    <td class="r num">${num(s.close)}</td><td class="r num ${signCls(s.chg5)}">${pct(s.chg5)}</td>
    <td class="r num ${signCls(s.net_amt)}">${yi(s.net_amt, 2)}</td><td class="r num ${signCls(s.foreign_amt)}">${yi(s.foreign_amt, 2)}</td><td class="r num ${signCls(s.trust_amt)}">${yi(s.trust_amt, 2)}</td>
    <td class="r num">${pct(s.net_ratio, 1, false)}${s.dominant ? ' <span class="tag accent">主導</span>' : ""}</td>
    <td class="r num">${num(s.vol_ratio)}${s.volume_up ? ' <span class="tag warn">量增</span>' : ""}</td>
    <td class="wrap">${esc(s.A.basis)}</td><td class="wrap">${esc(s.B.basis)}</td><td class="wrap small">${ratingsHTML(s.C, true)}</td>
    <td class="r num">${num(s.pe, 1)}</td><td class="r num ${signCls(s.qfii_chg5)}">${s.qfii_chg5 == null ? DASH : s.qfii_chg5.toFixed(2) + "pp"}</td>
    <td class="r num ${signCls(s.margin_chg5)}">${s.margin_chg5 == null ? DASH : s.margin_chg5.toLocaleString("zh-TW")}</td></tr>`).join("");
  return `<div class="table-wrap"><table><thead><tr>
    <th class="sticky">股票</th><th>訊號</th><th class="r">分數</th><th>產業</th><th class="r">收盤</th><th class="r">5日漲跌</th><th class="r">法人5日買超</th><th class="r">外資</th><th class="r">投信</th>
    <th class="r">買超/成交值</th><th class="r">量增比</th><th>永續依據</th><th>未來性依據</th><th>投行評等</th><th class="r">本益比</th><th class="r">外資持股5日</th><th class="r">融資5日(張)</th>
    </tr></thead><tbody>${rows}</tbody></table></div>`;
}

function renderPicks(rep) {
  const view = store.get("picksView") || "cards";
  const body = !rep.picks.length ? '<div class="card empty">今日無個股同時符合所有條件。請參考「候選池」了解各檔未入選原因。</div>'
    : view === "table" ? picksTable(rep.picks) : rep.picks.map(pickCard).join("");
  $("#picks").innerHTML = `
    <h2>精選表（依量增比排序，${rep.picks.length} 檔）</h2>
    <div class="toggle"><button data-view="cards" class="${view === "cards" ? "on" : ""}">卡片</button><button data-view="table" class="${view === "table" ? "on" : ""}">表格</button></div>
    ${body}`;
  $("#picks").querySelectorAll(".toggle button").forEach((b) => b.addEventListener("click", () => { store.set("picksView", b.dataset.view); renderPicks(rep); }));
}

function poolTable(list) {
  const rows = list.map((s) => `<tr class="${s.selected ? "sel" : ""}">
    <td class="r num">${s.rank}</td><td class="sticky"><b>${esc(s.code)}</b> ${esc(s.name)}</td>
    <td class="r num ${signCls(s.net_amt)}">${yi(s.net_amt, 2)}</td><td class="r num">${pct(s.net_ratio, 1, false)}${s.dominant ? ' <span class="tag accent">主導</span>' : ""}</td>
    <td class="r num">${num(s.vol_ratio)}</td><td class="r num">${num(s.score, 0)}</td><td>${signalTag(s)}</td>
    <td>${mark(s.A.pass)}</td><td>${mark(s.B.pass)}</td><td class="small">${esc(C_LABEL[s.C.status]?.[0] || s.C.status)}</td>
    <td>${s.selected ? '<span class="tag ok">入選</span>' : ""}</td><td class="wrap small">${esc((s.reasons || []).join("、") || DASH)}</td></tr>`).join("");
  return `<div class="table-wrap"><table><thead><tr><th class="r">#</th><th class="sticky">股票</th><th class="r">法人5日買超</th><th class="r">買超/成交值</th><th class="r">量增比</th><th class="r">分數</th><th>訊號</th>
    <th>A永續</th><th>B未來性</th><th>C投行</th><th>結果</th><th>未入選原因</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function renderPool(rep) {
  $("#pool").innerHTML = `
    <h2>候選池前 20 名對照表（依 5 日買超金額）</h2>
    <p class="small muted">✓ 符合　✗ 不符合　? 無法查證。入選規則：A 永續與 B 未來性皆符合，C 投行評等不是「只有負面評等」，且非處置股。分數與訊號只供參考，不影響入選。</p>
    ${poolTable(rep.compare)}
    <details><summary>顯示完整候選池 ${rep.pool.length} 檔</summary>${poolTable(rep.pool)}</details>
    <h2>判定依據明細（前 20 名）</h2>
    ${rep.compare.map((s) => `<div class="card small"><b>${esc(s.code)} ${esc(s.name)}</b>
      <div><span class="muted">A：</span>${esc(s.A.basis)}</div><div><span class="muted">B：</span>${esc(s.B.basis)}</div>
      <div><span class="muted">C：</span>${ratingsHTML(s.C, true)}</div></div>`).join("")}`;
}

function renderNews(rep) {
  const per = rep.picks.filter((s) => (s.news || []).length).map((s) => `<div class="card"><b>${esc(s.code)} ${esc(s.name)}</b>
    <ul class="news-list" style="margin-top:8px">${s.news.map((n) => `<li>${link(n.url, n.title || n.summary)}<div class="small">${esc(n.summary)}</div><div class="meta">${esc(n.source)}・${esc(n.date)}</div></li>`).join("")}</ul></div>`).join("");
  const techItem = (n) => {
    const srcs = (n.sources || []).length ? n.sources : [n];
    return `<li>${link(n.url, n.title)}${n.title_orig ? ` <span class="tag plain">機器翻譯</span><div class="small muted">原文：${esc(n.title_orig)}</div>` : ""}
      <div class="small">${n.source_count ? `<span class="tag ok">${esc(n.source_count)} 家媒體報導</span>` : ""}${srcs.map((a) => link(a.url, a.source || "來源")).join("、")}</div>
      <div class="meta">${esc(n.date)}</div></li>`;
  };
  const regions = [...new Set((rep.tech_news || []).map((n) => n.region || "國內外"))];
  const tech = regions.map((r) => `<div class="card"><b>${esc(r)}媒體</b><ul class="news-list" style="margin-top:8px">${rep.tech_news.filter((n) => (n.region || "國內外") === r).map(techItem).join("")}</ul></div>`).join("");
  $("#news").innerHTML = `
    <h2>入選個股相關新聞（近一週）</h2>${per || '<div class="card empty">— 未取得</div>'}
    <h2>當日國內外重要科技新聞</h2>
    <p class="small muted">同一事件需至少 2 家不同媒體報導才收錄，依報導家數排序；外文標題為機器翻譯，請點連結核對原文。</p>
    ${tech || '<div class="card empty">— 未取得</div>'}`;
}

function renderNotes(rep, mdPath) {
  const extra = new Map();
  rep.pool.forEach((s) => [...(s.A.evidence || []), ...(s.C.ratings || []), ...(s.news || [])].forEach((e) => { if (safeUrl(e.url) && !extra.has(e.url)) extra.set(e.url, e.title || e.source || s.name); }));
  (rep.tech_news || []).forEach((n) => { if (safeUrl(n.url) && !extra.has(n.url)) extra.set(n.url, n.title); });
  $("#notes").innerHTML = `
    <h2>方法</h2>
    <div class="card small"><ol style="margin:0;padding-left:20px">
      <li>範圍：上市＋上櫃普通股（排除 ETF、ETN、權證、特別股、存託憑證）。近 5 個交易日（${esc(rep.window[0])}～${esc(rep.window.at(-1))}）三大法人買賣超股數 × 當日收盤價逐日加總，取前 50 名為候選池；買超金額占同期成交值 ≥10% 標「法人主導」。</li>
      <li>條件 A 永續、B 未來性（成長產業或近 3 月營收年增皆正）、C 投行評等（J.P. Morgan、BofA、Morgan Stanley、Goldman Sachs 近 3 個月）。A、B 皆符合且 C 非僅負面者入選，最多 20 檔。</li>
      <li>量增比＝近 5 日均量 ÷ 近 20 日均量，≥1.2 標「量增」，入選股依此排序。</li>
      <li>綜合分數（0–100）：候選池內「買超占成交值、投信買超占成交值、5 日買超天數、量增比」四項的百分位平均；C 有正面評等 +5、僅負面 −5。只用於排序參考與模擬持股的優先順序。</li>
      <li>進場訊號（隔日開盤適用）：處置股＝排除；5 日漲幅 >15%、高於 20 日均線 >15%、融資 5 日增加 >10% 或注意股＝過熱；收盤站上上彎的 20 日均線，且突破前 20 日高點並量增＝可進場；其餘＝觀察。參數在 config/strategy.json。</li>
      <li>大盤濾網：加權指數低於 60 日均線時為弱勢，模擬持股暫停新進場（強勢時每天最多 3 檔）。</li></ol></div>
    <h2>資料限制說明</h2>
    <div class="card small"><ul class="notes" style="margin:0;padding-left:20px">
      ${(rep.notes || []).map((n) => `<li>${esc(n)}</li>`).join("")}
      <li>買超金額為「股數 × 收盤價」估算，非實際成交均價。「外資」含外資自營商。</li>
      <li>投行評等取自公開新聞報導：自動擷取 Google 新聞標題中寫明券商、評等或目標價者，可能遺漏或誤判，請點連結核對。</li>
      <li>月營收採用：${esc((rep.revenue_months || []).join("、") || DASH)}。</li>
      ${rep.research_enabled ? `<li>網路研究模型：${esc(rep.model)}</li>` : ""}
    </ul></div>
    <p class="small">${link(mdPath, "下載 Markdown 版完整報告")}・產出時間 ${esc(rep.generated_at)}</p>
    <h2>Sources</h2>
    <div class="card small"><ul style="margin:0;padding-left:20px">
      ${rep.sources.map((s) => `<li>${link(s.url, s.name)}</li>`).join("")}
      ${[...extra].map(([u, t]) => `<li>${link(u, t)}</li>`).join("")}
    </ul></div>`;
}

function regimeCard(r) {
  if (!r) return "";
  const cls = r.state === "強勢" ? "ok" : r.state === "弱勢" ? "bad" : "plain";
  return `<div class="card small"><span class="tag ${cls}">大盤${esc(r.state)}</span>
    加權指數 <b class="num">${num(r.taiex, 0)}</b>・60 日均線 <span class="num">${num(r.ma, 0)}</span>（${esc(r.date)}）。
    ${r.max_entries ? `模擬持股每天最多新增 <b>${esc(r.max_entries)}</b> 檔。` : "模擬持股<b>暫停新進場</b>，已持有的照出場規則處理。"}
    ${r.crash ? `<div><span class="tag ok">大跌買點</span> ${esc(r.crash.date)} 收盤距 20 日高點 <b class="num">${num(r.crash.drawdown * 100, 1)}%</b>，不要求突破訊號，改買入選清單綜合分數最高的股票${r.crash.days_left ? `（還有 ${esc(r.crash.days_left)} 個交易日）` : "（今天是最後一天）"}。</div>` : ""}</div>`;
}

function orderList(pf) {
  const buys = (pf.orders || []).map((o) => `<li><b>${esc(o.code)} ${esc(o.name)}</b> <span class="small muted">${esc(o.industry)}</span>
    <div class="small num">參考收盤 ${num(o.ref_close)}・預估停損 ${num(o.est_stop)}（實際以開盤價計算）</div></li>`).join("");
  const sells = (pf.exits || []).map((x) => `<li><b>${esc(x.code)} ${esc(x.name)}</b> <span class="tag bad">${esc(x.exit_order)}</span>
    <div class="small num">成本 ${num(x.entry)}・收盤 ${num(x.last)}・<span class="${signCls(x.ret)}">${pct(x.ret)}</span></div></li>`).join("");
  return `<div class="card"><b>明日開盤買進</b><ul class="news-list" style="margin-top:8px">${buys || '<li class="small muted">無</li>'}</ul></div>
    <div class="card"><b>明日開盤賣出</b><ul class="news-list" style="margin-top:8px">${sells || '<li class="small muted">無</li>'}</ul></div>`;
}

function portfolioBrief(pf) {
  if (!pf) return "";
  const ret = pf.equity / pf.capital - 1;
  return `<h2>模擬持股</h2>
    <div class="kpis">
      <div class="kpi"><div class="label">帳戶淨值</div><div class="value num">${(pf.equity / 1e4).toLocaleString("zh-TW", { maximumFractionDigits: 1 })}<small>萬</small></div></div>
      <div class="kpi"><div class="label">累計報酬</div><div class="value num ${signCls(ret)}">${pct(ret)}</div></div>
      <div class="kpi"><div class="label">持有</div><div class="value num">${pf.positions.length}<small>檔</small></div></div>
      <div class="kpi"><div class="label">已實現勝率（${pf.stats?.trades ?? 0} 筆）</div><div class="value num">${pf.stats?.win_rate == null ? DASH : pct(pf.stats.win_rate, 0, false)}</div></div>
    </div>
    ${orderList(pf)}`;
}

function renderPortfolio(pf) {
  if (!pf) { $("#portfolio").innerHTML = '<div class="card empty">此日期的報告尚未啟用模擬持股。</div>'; return; }
  const st = pf.stats || {};
  const pos = pf.positions.map((x) => `<tr><td class="sticky"><b>${esc(x.code)}</b> ${esc(x.name)}</td><td class="r num">${x.shares.toLocaleString("zh-TW")}</td>
    <td>${esc(x.entry_date)}</td><td class="r num">${num(x.entry)}</td><td class="r num">${num(x.last)}</td><td class="r num ${signCls(x.ret)}">${pct(x.ret)}</td>
    <td class="r num">${num(x.stop)}</td><td class="r num">${x.days}</td><td>${x.exit_order ? `<span class="tag bad">明日賣出：${esc(x.exit_order)}</span>` : '<span class="tag plain">續抱</span>'}</td></tr>`).join("");
  const trades = pf.trades.map((t) => `<tr><td class="sticky"><b>${esc(t.code)}</b> ${esc(t.name)}</td><td>${esc(t.entry_date)}</td><td>${esc(t.exit_date)}</td>
    <td class="r num">${num(t.entry)}</td><td class="r num">${num(t.exit)}</td><td class="r num ${signCls(t.ret)}">${pct(t.ret)}</td><td class="r num ${signCls(t.pnl)}">${t.pnl.toLocaleString("zh-TW")}</td>
    <td class="r num">${t.days}</td><td>${esc(t.reason)}</td></tr>`).join("");
  const x = STRATEGY?.exit, pfp = STRATEGY?.portfolio;
  $("#portfolio").innerHTML = `
    <h2>模擬持股（${esc(pf.started || "")} 起，初始資金 ${(pf.capital / 1e4).toLocaleString("zh-TW")} 萬）</h2>
    <p class="small muted">每天依「可進場」訊號（依綜合分數排序）在隔日開盤買進，並依停損（獲利後上移到成本）、法人連賣、時間停損自動出場。已扣手續費與證交稅。</p>
    ${portfolioBrief(pf).replace("<h2>模擬持股</h2>", "")}
    <h2>目前持股</h2>
    ${pos ? `<div class="table-wrap"><table><thead><tr><th class="sticky">股票</th><th class="r">股數</th><th>進場日</th><th class="r">成本</th><th class="r">收盤</th><th class="r">報酬</th><th class="r">停損</th><th class="r">持有日</th><th>狀態</th></tr></thead><tbody>${pos}</tbody></table></div>` : '<div class="card empty">目前沒有持股</div>'}
    ${pf.equity_curve?.length > 1 ? `<h2>淨值走勢</h2><div class="card">${lineChart([{ name: "模擬帳戶", points: pf.equity_curve.map(([d, v]) => [d, v / pf.capital]) }])}</div>` : ""}
    <h2>績效統計（已實現）</h2>
    <div class="card small">交易 ${st.trades ?? 0} 筆・勝率 ${st.win_rate == null ? DASH : pct(st.win_rate, 0, false)}・平均 ${pct(st.avg_ret)}・平均獲利 ${pct(st.avg_win)}・平均虧損 ${pct(st.avg_loss)}・賺賠比 ${st.payoff ?? DASH}・最大回撤 ${pct(st.max_drawdown)}・同期加權指數 ${pct(st.bench_return)}</div>
    <h2>最近平倉</h2>
    ${trades ? `<div class="table-wrap"><table><thead><tr><th class="sticky">股票</th><th>進場</th><th>出場</th><th class="r">買價</th><th class="r">賣價</th><th class="r">報酬</th><th class="r">損益(元)</th><th class="r">天數</th><th>原因</th></tr></thead><tbody>${trades}</tbody></table></div>` : '<div class="card empty">尚無平倉紀錄</div>'}
    ${x && pfp ? `<h2>規則</h2><div class="card small"><ul style="margin:0;padding-left:20px">
      <li>停損：進場價 − ${x.atr_mult}×ATR(${x.atr_n})，最多 −${(x.max_stop_pct * 100).toFixed(0)}%；盤中觸及即出場。</li>
      ${x.breakeven_after != null ? `<li>保本：收盤曾獲利 ${(x.breakeven_after * 100).toFixed(0)}% 以上後，停損上移到成本。</li>` : ""}
      ${x.trail_after != null ? `<li>移動停利：曾獲利 ${(x.trail_after * 100).toFixed(0)}% 以上後，收盤跌破 ${x.trail_ma} 日均線，隔日開盤出場。</li>` : ""}
      <li>法人轉賣：外資＋投信連 ${x.inst_sell_days} 日賣超，隔日開盤出場。</li>
      <li>時間停損：持有 ${x.time_stop_days} 日仍未獲利 ${(x.time_stop_min_gain * 100).toFixed(0)}%，隔日開盤出場。</li>
      <li>部位：每筆最多虧損總資產 ${(pfp.risk_per_trade * 100).toFixed(0)}%，最多 ${pfp.max_positions} 檔，同產業最多 ${pfp.max_per_industry} 檔；隔日開盤跳空 >${(STRATEGY.entry.max_gap_up * 100).toFixed(0)}% 或接近漲停不追價。</li>
    </ul></div>` : ""}`;
}

// Line chart: values are ratios to a common base (1 = start). Series 0 = accent, series 1 = muted dashed (benchmark).
function lineChart(series) {
  const W = Math.max(280, Math.min(1000, ($("#main")?.clientWidth || 640) - 66)), H = W < 500 ? 200 : 260, L = 40, R = 104, T = 12, B = 26;
  const all = series.flatMap((s) => s.points.map((p) => p[1]));
  let lo = Math.min(...all, 1), hi = Math.max(...all, 1);
  const pad = (hi - lo) * 0.08 || 0.02; lo -= pad; hi += pad;
  const dates = series[0].points.map((p) => p[0]);
  const n = dates.length;
  const x = (i) => L + (n > 1 ? (i * (W - L - R)) / (n - 1) : 0);
  const y = (v) => T + ((hi - v) * (H - T - B)) / (hi - lo);
  const idx = new Map(dates.map((d, i) => [d, i]));
  const ticks = [lo + pad, 1, hi - pad].filter((v, i, a) => a.findIndex((w) => Math.abs(w - v) < (hi - lo) / 10) === i);
  const cls = ["c0", "c1"];
  const paths = series.map((s, k) => {
    const pts = s.points.filter((p) => idx.has(p[0])).map((p) => `${x(idx.get(p[0])).toFixed(1)},${y(p[1]).toFixed(1)}`);
    const last = s.points.at(-1);
    return `<polyline class="ln ${cls[k]}" points="${pts.join(" ")}"/>
      <text class="lbl" x="${W - R + 6}" y="${y(last[1]) + 4}">${esc(s.name)} ${pct(last[1] - 1, 1)}</text>`;
  }).join("");
  const data = encodeURIComponent(JSON.stringify(series.map((s) => s.points)));
  return `<div class="chart" data-series="${data}" data-names="${esc(series.map((s) => s.name).join("|"))}">
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(series.map((s) => s.name).join("與"))}走勢（起點＝100%）">
      ${ticks.map((v) => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text class="ax" x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${pct(v - 1, 0)}</text>`).join("")}
      <text class="ax" x="${L}" y="${H - 6}">${esc(dates[0])}</text><text class="ax" x="${W - R}" y="${H - 6}" text-anchor="end">${esc(dates.at(-1))}</text>
      ${paths}
      <line class="cross" x1="0" x2="0" y1="${T}" y2="${H - B}" style="display:none"/>
      <rect class="hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}"/>
    </svg>
    ${series.length > 1 ? `<div class="legend small">${series.map((s, k) => `<span><i class="sw ${cls[k]}"></i>${esc(s.name)}</span>`).join("")}</div>` : ""}
    <div class="tip small" hidden></div></div>`;
}

function bindCharts(root) {
  root.querySelectorAll(".chart").forEach((el) => {
    const pts = JSON.parse(decodeURIComponent(el.dataset.series)), names = el.dataset.names.split("|");
    const svg = el.querySelector("svg"), hit = el.querySelector(".hit"), cross = el.querySelector(".cross"), tip = el.querySelector(".tip");
    const n = pts[0].length;
    const move = (ev) => {
      const r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
      const sx = ((ev.clientX - r.left) / r.width) * vb.width;
      const x0 = +hit.getAttribute("x"), w = +hit.getAttribute("width");
      const i = Math.max(0, Math.min(n - 1, Math.round(((sx - x0) / w) * (n - 1))));
      const px = x0 + (n > 1 ? (i * w) / (n - 1) : 0);
      cross.setAttribute("x1", px); cross.setAttribute("x2", px); cross.style.display = "";
      const d = pts[0][i][0];
      tip.innerHTML = `<b>${esc(d)}</b>` + pts.map((s, k) => { const p = s.find((q) => q[0] === d); return p ? `<div>${esc(names[k])}：${pct(p[1] - 1)}</div>` : ""; }).join("");
      tip.hidden = false;
      tip.style.left = `${Math.min(r.width - 150, Math.max(0, (px / vb.width) * r.width - 70))}px`;
    };
    hit.addEventListener("pointermove", move);
    hit.addEventListener("pointerdown", move);
    hit.addEventListener("pointerleave", () => { tip.hidden = true; cross.style.display = "none"; });
  });
}

function statRow(name, a, extra = "") {
  if (!a) return `<tr><td class="sticky namecol">${esc(name)}</td><td class="r" colspan="5">${DASH}</td>${extra}</tr>`;
  return `<tr><td class="sticky namecol">${esc(name)}</td><td class="r num">${a.n}</td><td class="r num ${signCls(a.avg)}">${pct(a.avg, 2)}</td>
    <td class="r num">${pct(a.win_rate, 0, false)}</td><td class="r num ${signCls(a.excess)}">${pct(a.excess, 2)}</td><td class="r num">${pct(a.beat_rate, 0, false)}</td>${extra}</tr>`;
}

async function renderPerf() {
  const [perf, bt] = await Promise.all([getJSON("data/performance.json").catch(() => null), getJSON("data/backtest.json").catch(() => null)]);
  const h = Number(store.get("perfH") || 5);
  const toggle = `<div class="toggle" id="perfH">${[...new Set([...(perf?.horizons || []), ...(bt?.horizons || [])])].sort((a, b) => a - b).map((k) => `<button data-h="${k}" class="${k === h ? "on" : ""}">持有 ${k} 日</button>`).join("")}</div>`;
  const head = `<thead><tr><th class="sticky">分組</th><th class="r">樣本</th><th class="r">平均報酬</th><th class="r">勝率</th><th class="r">超額報酬</th><th class="r">贏大盤比率</th></tr></thead>`;
  const live = perf?.groups?.length ? `<div class="table-wrap"><table>${head}<tbody>${perf.groups.map((g) => statRow(g.name, g[`h${h}`])).join("")}</tbody></table></div>
      <details><summary>依報告日期</summary><div class="table-wrap"><table>${head.replace("分組", "報告日")}<tbody>${perf.by_day.map((g) => statRow(g.date, g[`h${h}`])).join("")}</tbody></table></div></details>`
    : '<div class="card empty">尚無足夠的後續股價可計算。</div>';
  let back = '<div class="card empty">尚未執行回測。請到 GitHub Actions 執行「backtest」工作流程（第一次約 1～2 小時）。</div>';
  if (bt) {
    const vh = (v, seg) => v[seg]?.[`h${h}`];
    const vrows = bt.variants.map((v) => `<tr><td class="sticky namecol"><b>${esc(v.name)}</b><div class="small muted">${esc(v.desc)}</div></td><td class="r num">${v.picks_per_day ?? DASH}</td>
      <td class="r num ${signCls(vh(v, "all")?.avg)}">${pct(vh(v, "all")?.avg, 2)}</td><td class="r num">${pct(vh(v, "all")?.win_rate, 0, false)}</td>
      <td class="r num ${signCls(vh(v, "train")?.excess)}">${pct(vh(v, "train")?.excess, 2)}</td><td class="r num ${signCls(vh(v, "test")?.excess)}">${pct(vh(v, "test")?.excess, 2)}</td>
      <td class="r num">${pct(vh(v, "test")?.win_rate, 0, false)}</td></tr>`).join("");
    const srows = bt.strategies.map((s) => { const a = s.all, te = s.test || {}; return `<tr><td class="sticky"><b>${esc(s.name)}</b></td><td class="r num">${a.trades}</td>
      <td class="r num">${pct(a.win_rate, 0, false)}</td><td class="r num ${signCls(a.avg_ret)}">${pct(a.avg_ret, 2)}</td><td class="r num">${a.payoff ?? DASH}</td>
      <td class="r num ${signCls(a.total_return)}">${pct(a.total_return)}</td><td class="r num ${signCls(a.cagr)}">${pct(a.cagr)}</td><td class="r num down">${pct(a.max_drawdown)}</td>
      <td class="r num ${signCls(te.total_return)}">${pct(te.total_return)}</td><td class="small">${esc(Object.entries(s.exit_reasons || {}).map(([k, n]) => `${k} ${n}`).join("、") || DASH)}</td></tr>`; }).join("");
    const full = bt.strategies[0];
    const t0 = bt.taiex_curve?.[0]?.[1];
    const chart = full?.equity_curve?.length > 1 && t0 ? lineChart([
      { name: "策略", points: full.equity_curve.map(([d, v]) => [d, v / (STRATEGY?.portfolio?.capital || full.equity_curve[0][1])]) },
      { name: "加權指數", points: bt.taiex_curve.map(([d, v]) => [d, v / t0]) },
    ]) : "";
    back = `<p class="small muted">${esc(bt.period[0])} ～ ${esc(bt.period[1])}，共 ${bt.days} 個交易日；${esc(bt.split)} 之前為調參期、之後為驗證期。同期加權指數 ${pct(bt.bench_return)}。產出於 ${esc(bt.generated_at)}。</p>
      <h2>選股規則比較（持有 ${h} 日）</h2>
      <div class="table-wrap"><table><thead><tr><th class="sticky">規則</th><th class="r">每日檔數</th><th class="r">平均報酬</th><th class="r">勝率</th><th class="r">調參期超額</th><th class="r">驗證期超額</th><th class="r">驗證期勝率</th></tr></thead><tbody>${vrows}</tbody></table></div>
      <h2>策略模擬（進場訊號＋出場規則＋部位控管）</h2>
      <div class="table-wrap"><table><thead><tr><th class="sticky">出場方式</th><th class="r">交易數</th><th class="r">勝率</th><th class="r">平均報酬</th><th class="r">賺賠比</th><th class="r">總報酬</th><th class="r">年化</th><th class="r">最大回撤</th><th class="r">驗證期總報酬</th><th>出場原因</th></tr></thead><tbody>${srows}</tbody></table></div>
      ${chart ? `<div class="card">${chart}</div>` : ""}
      <h2>回測限制</h2><div class="card small"><ul style="margin:0;padding-left:20px">${bt.caveats.map((c) => `<li>${esc(c)}</li>`).join("")}</ul></div>
      <p class="small">${link("reports/backtest.md", "下載 Markdown 版回測報告")}</p>`;
  }
  $("#perf").innerHTML = `
    ${toggle}
    <h2>實際入選股後續表現</h2>
    <p class="small muted">每份報告的入選股，以報告隔日開盤價買進、持有 N 個交易日後收盤的報酬（已扣手續費與證交稅）；超額報酬＝減去同期加權指數漲跌。樣本少時僅供參考。</p>
    ${live}
    <h2>歷史回測</h2>
    ${back}`;
  $("#perf").querySelectorAll("#perfH button").forEach((b) => b.addEventListener("click", () => { store.set("perfH", b.dataset.h); renderPerf(); }));
  bindCharts($("#perf"));
}

function selectTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  document.querySelectorAll(".panel").forEach((p) => { p.hidden = p.id !== name; });
  store.set("tab", name);
  window.scrollTo({ top: 0 });
}

async function load(day) {
  const rep = await getJSON(`data/reports/${day}.json`);
  $("#sub").textContent = `資料日 ${rep.asof}・區間 ${rep.window[0].slice(5)}～${rep.window.at(-1).slice(5)}・入選 ${rep.summary.count} 檔`;
  STRATEGY = rep.strategy || null;
  renderSummary(rep); renderPicks(rep); renderPool(rep); renderNews(rep); renderNotes(rep, `reports/${day}.md`);
  renderPortfolio(rep.portfolio); bindCharts($("#portfolio"));
  if (location.hash.slice(1) !== day) history.replaceState(null, "", `#${day}`);
}

async function init() {
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => selectTab(b.dataset.tab)));
  selectTab(store.get("tab") || "summary");
  let idx;
  try { idx = await getJSON("data/index.json"); } catch (e) {
    $("#sub").textContent = "尚無報告資料";
    $("#summary").innerHTML = `<div class="card empty">尚未產生任何報告。請在 GitHub Actions 執行「daily-report」工作流程。<br><span class="small">${esc(e.message)}</span></div>`;
    return;
  }
  renderPerf().catch((e) => { $("#perf").innerHTML = `<div class="card empty">載入失敗：${esc(e.message)}</div>`; });
  const sel = $("#date");
  sel.innerHTML = idx.reports.map((r) => `<option value="${esc(r.date)}">${esc(r.date)}（${r.count} 檔）</option>`).join("");
  const want = location.hash.slice(1);
  const day = idx.reports.some((r) => r.date === want) ? want : idx.latest;
  sel.value = day;
  sel.addEventListener("change", () => load(sel.value).catch(showErr));
  await load(day).catch(showErr);
}
function showErr(e) { $("#summary").innerHTML = `<div class="card empty">載入失敗：${esc(e.message)}</div>`; selectTab("summary"); }
init();
