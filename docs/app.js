"use strict";
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
const C_LABEL = { positive: ["有正面評等", "ok"], negative_only: ["僅負面評等", "bad"], neutral: ["僅中立評等", "plain"], no_coverage: ["無覆蓋／查無公開報導", "plain"], not_checked: ["未查證", "warn"] };

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

function tagsFor(s) {
  const t = [];
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
        <div class="metric"><div class="k">投行</div><div class="v small">${esc(C_LABEL[s.C.status]?.[0])}</div></div>
      </div>
    </div>`).join("");
  $("#summary").innerHTML = `
    <div class="kpis">
      <div class="kpi"><div class="label">今日入選</div><div class="value num">${sm.count}<small>檔</small></div></div>
      <div class="kpi"><div class="label">三大法人5日合計</div><div class="value num ${signCls(total)}">${yi(total, 0)}</div></div>
      <div class="kpi"><div class="label">外資5日</div><div class="value num ${signCls(foreign)}">${yi(foreign, 0)}</div></div>
      <div class="kpi"><div class="label">投信5日</div><div class="value num ${signCls(trust)}">${yi(trust, 0)}</div></div>
    </div>
    <p class="card small">${esc(sm.market_line)}</p>
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
    </div>
    <dl class="basis">
      <dt>永續依據</dt><dd>${esc(s.A.basis)} ${(s.A.evidence || []).map((e) => link(e.url, "來源")).join(" ")}</dd>
      <dt>未來性依據</dt><dd>${esc(s.B.basis)}</dd>
      <dt>投行評等（近3個月）</dt><dd>${ratingsHTML(s.C)}</dd>
      ${news ? `<dt>近一週新聞</dt><dd><ul class="news-list">${news}</ul></dd>` : ""}
    </dl>
  </article>`;
}

function picksTable(picks) {
  const rows = picks.map((s) => `<tr>
    <td class="sticky"><b>${esc(s.code)}</b> ${esc(s.name)}</td><td>${esc(s.industry)}</td>
    <td class="r num">${num(s.close)}</td><td class="r num ${signCls(s.chg5)}">${pct(s.chg5)}</td>
    <td class="r num ${signCls(s.net_amt)}">${yi(s.net_amt, 2)}</td><td class="r num ${signCls(s.foreign_amt)}">${yi(s.foreign_amt, 2)}</td><td class="r num ${signCls(s.trust_amt)}">${yi(s.trust_amt, 2)}</td>
    <td class="r num">${pct(s.net_ratio, 1, false)}${s.dominant ? ' <span class="tag accent">主導</span>' : ""}</td>
    <td class="r num">${num(s.vol_ratio)}${s.volume_up ? ' <span class="tag warn">量增</span>' : ""}</td>
    <td class="wrap">${esc(s.A.basis)}</td><td class="wrap">${esc(s.B.basis)}</td><td class="wrap small">${ratingsHTML(s.C, true)}</td>
    <td class="r num">${num(s.pe, 1)}</td><td class="r num ${signCls(s.qfii_chg5)}">${s.qfii_chg5 == null ? DASH : s.qfii_chg5.toFixed(2) + "pp"}</td>
    <td class="r num ${signCls(s.margin_chg5)}">${s.margin_chg5 == null ? DASH : s.margin_chg5.toLocaleString("zh-TW")}</td></tr>`).join("");
  return `<div class="table-wrap"><table><thead><tr>
    <th class="sticky">股票</th><th>產業</th><th class="r">收盤</th><th class="r">5日漲跌</th><th class="r">法人5日買超</th><th class="r">外資</th><th class="r">投信</th>
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
    <td class="r num">${num(s.vol_ratio)}</td>
    <td>${mark(s.A.pass)}</td><td>${mark(s.B.pass)}</td><td class="small">${esc(C_LABEL[s.C.status]?.[0] || s.C.status)}</td>
    <td>${s.selected ? '<span class="tag ok">入選</span>' : ""}</td><td class="wrap small">${esc((s.reasons || []).join("、") || DASH)}</td></tr>`).join("");
  return `<div class="table-wrap"><table><thead><tr><th class="r">#</th><th class="sticky">股票</th><th class="r">法人5日買超</th><th class="r">買超/成交值</th><th class="r">量增比</th>
    <th>A永續</th><th>B未來性</th><th>C投行</th><th>結果</th><th>未入選原因</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function renderPool(rep) {
  $("#pool").innerHTML = `
    <h2>候選池前 20 名對照表（依 5 日買超金額）</h2>
    <p class="small muted">✓ 符合　✗ 不符合　? 無法查證。入選規則：A 永續與 B 未來性皆符合，且 C 投行評等不是「只有負面評等」。</p>
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
  const tech = (rep.tech_news || []).map((n) => `<li>${link(n.url, n.title)}<div class="small">${esc(n.summary)}</div><div class="meta">${esc(n.source)}・${esc(n.date)}</div></li>`).join("");
  $("#news").innerHTML = `
    <h2>入選個股相關新聞（近一週）</h2>${per || '<div class="card empty">— 未取得</div>'}
    <h2>當日國內外重要科技新聞</h2>${tech ? `<div class="card"><ul class="news-list">${tech}</ul></div>` : '<div class="card empty">— 未取得</div>'}`;
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
      <li>量增比＝近 5 日均量 ÷ 近 20 日均量，≥1.2 標「量增」，入選股依此排序。</li></ol></div>
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

function selectTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  document.querySelectorAll(".panel").forEach((p) => { p.hidden = p.id !== name; });
  store.set("tab", name);
  window.scrollTo({ top: 0 });
}

async function load(day) {
  const rep = await getJSON(`data/reports/${day}.json`);
  $("#sub").textContent = `資料日 ${rep.asof}・區間 ${rep.window[0].slice(5)}～${rep.window.at(-1).slice(5)}・入選 ${rep.summary.count} 檔`;
  renderSummary(rep); renderPicks(rep); renderPool(rep); renderNews(rep); renderNotes(rep, `reports/${day}.md`);
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
