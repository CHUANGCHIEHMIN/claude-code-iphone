"""Steps 1–3 of the screen plus assembly of the final report payload."""
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import history, news_ratings, performance, portfolio, research, rules, signals, sources, tech_news

log = logging.getLogger(__name__)
TPE = timezone(timedelta(hours=8))

POOL_SIZE = 50
COMPARE_SIZE = 20
MAX_PICKS = 20
DOMINANT_RATIO = 0.10
VOLUME_UP = 1.2
NEED_DAYS = 26  # 20日均線＋5日斜率、20日高點、ATR(14) 所需的交易日數

OFFICIAL_SOURCES = [
    {"name": "臺灣證券交易所 三大法人買賣超日報 (T86)", "url": "https://www.twse.com.tw/zh/trading/foreign/t86.html"},
    {"name": "臺灣證券交易所 每日收盤行情 (MI_INDEX)", "url": "https://www.twse.com.tw/zh/trading/historical/mi-index.html"},
    {"name": "臺灣證券交易所 外資及陸資投資持股統計 (MI_QFIIS)", "url": "https://www.twse.com.tw/zh/trading/foreign/mi-qfiis.html"},
    {"name": "臺灣證券交易所 融資融券彙總 (MI_MARGN)", "url": "https://www.twse.com.tw/zh/trading/margin/mi-margn.html"},
    {"name": "臺灣證券交易所 個股本益比、殖利率及股價淨值比 (BWIBBU_d)", "url": "https://www.twse.com.tw/zh/trading/historical/bwibbu-day.html"},
    {"name": "櫃買中心 三大法人買賣明細資訊", "url": "https://www.tpex.org.tw/zh-tw/mainboard/trading/major-institutional/detail/day.html"},
    {"name": "櫃買中心 上櫃股票行情", "url": "https://www.tpex.org.tw/zh-tw/mainboard/trading/info/mi-pricing.html"},
    {"name": "櫃買中心 僑外資及陸資持股比例", "url": "https://www.tpex.org.tw/zh-tw/mainboard/trading/major-institutional/qfii/rank.html"},
    {"name": "櫃買中心 融資融券餘額", "url": "https://www.tpex.org.tw/zh-tw/mainboard/trading/margin-trading/transactions.html"},
    {"name": "櫃買中心 個股本益比、殖利率、股價淨值比", "url": "https://www.tpex.org.tw/zh-tw/mainboard/trading/info/pe-ratio.html"},
    {"name": "公開資訊觀測站 每月營業收入彙總表", "url": "https://mopsov.twse.com.tw/mops/web/t21sc04_ifrs"},
    {"name": "Google 新聞搜尋（投行評等新聞標題）", "url": "https://news.google.com/?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
    {"name": "Google 新聞 RSS（國內外科技新聞，同一事件需 2 家以上媒體報導）", "url": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
    {"name": "Google 翻譯（外文新聞標題機器翻譯）", "url": "https://translate.google.com/"},
    {"name": "證交所公司治理中心 第十二屆公司治理評鑑結果", "url": "https://cgc.twse.com.tw/evaluationCorp/listCh"},
    {"name": "MoneyDJ 元大臺灣ESG永續ETF(00850) 全部持股", "url": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00850.TW"},
    {"name": "證交所 OpenAPI 上市公司每月營業收入彙總表（產業別）", "url": "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"},
    {"name": "臺灣證券交易所 市場成交資訊（發行量加權股價指數，FMTQIK）", "url": "https://www.twse.com.tw/zh/trading/historical/fmtqik.html"},
    {"name": "臺灣證券交易所 處置有價證券／注意有價證券", "url": "https://www.twse.com.tw/zh/announcement/punish.html"},
    {"name": "櫃買中心 OpenAPI 處置有價證券／注意股票資訊", "url": "https://www.tpex.org.tw/openapi/"},
    {"name": "櫃買中心 OpenAPI 上櫃公司每月營業收入彙總表（產業別）", "url": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"},
]


def today_tpe() -> date:
    return datetime.now(TPE).date()


def _safe(fn, *a, default=None, note: list | None = None, label: str = ""):
    try:
        return fn(*a)
    except Exception as e:  # noqa: BLE001
        log.warning("%s failed: %r", label or fn.__name__, e)
        if note is not None:
            note.append(f"{label or fn.__name__} 取得失敗：{e}")
        return {} if default is None else default


# ------------------------------------------------------------------ step 0/1
def trading_days(asof: date, need: int = NEED_DAYS, max_back: int = 60, notes: list | None = None,
                 store: history.Store | None = None, stored_flows: dict | None = None) -> list[tuple[date, dict, dict]]:
    """Walk back from `asof`, keeping days where TWSE published a closing table (stored days are reused)."""
    days = []
    d = asof
    for _ in range(max_back):
        if d.weekday() < 5:
            snap = store.load(d) if store else None
            if snap:
                tw, tp, tw_f, tp_f = snap
                days.append((d, tw, tp))
                if stored_flows is not None:
                    stored_flows[d] = (tw_f, tp_f)
                if len(days) >= need:
                    break
                d -= timedelta(days=1)
                continue
            tw = _safe(sources.twse_quotes, d, label=f"TWSE 收盤行情 {d}")
            if tw:
                tp = _safe(sources.tpex_quotes, d, label=f"TPEx 收盤行情 {d}")
                if not tp:  # TWSE traded that day, so an empty TPEx table means the download failed
                    tp = _safe(sources.tpex_quotes, d, label=f"TPEx 收盤行情 {d}（重試）")
                if not tp and notes is not None:
                    notes.append(f"{d} 上櫃收盤行情取得失敗，上櫃個股該日成交量與買超金額缺漏")
                days.append((d, tw, tp))
                log.info("trading day %s: TWSE %d / TPEx %d quotes", d, len(tw), len(tp))
                if len(days) >= need:
                    break
        d -= timedelta(days=1)
    return days


def build_universe(days, notes: list, stored_flows: dict | None = None,
                   flows_out: dict | None = None) -> dict[str, dict]:
    """Aggregate 5-day institutional flows + 20-day volume for every common stock."""
    stored_flows = stored_flows or {}
    last5 = days[:5]
    stocks: dict[str, dict] = {}
    for idx, (d, tw_q, tp_q) in enumerate(days[:20]):
        for market, quotes in (("上市", tw_q), ("上櫃", tp_q)):
            for code, q in quotes.items():
                if not rules.is_common_stock(code, q["name"]):
                    continue
                s = stocks.setdefault(code, {
                    "code": code, "name": q["name"], "market": market,
                    "vol20": [], "vol5": [], "value5": 0.0, "net_amt": 0.0, "foreign_amt": 0.0,
                    "trust_amt": 0.0, "dealer_amt": 0.0, "foreign_sh": 0.0, "trust_sh": 0.0,
                    "net_sh": 0.0, "days_with_flow": 0, "closes": {},
                })
                s["vol20"].append(q["volume"])
                s["closes"][d.isoformat()] = q["close"]
                if idx < 5:
                    s["vol5"].append(q["volume"])
                    s["value5"] += q["value"]
                    if idx == 0:
                        s["close"] = q["close"]
                        s["pe_quote"] = q.get("pe")
    for d, tw_q, tp_q in last5:
        got = []
        for k, (market, fetch, quotes) in enumerate((("上市", sources.twse_insti, tw_q), ("上櫃", sources.tpex_insti, tp_q))):
            flows = stored_flows[d][k] if d in stored_flows else _safe(fetch, d, note=notes, label=f"{market}三大法人 {d}")
            got.append(flows)
            if not flows:
                notes.append(f"{d} {market}三大法人資料為空")
            for code, f in flows.items():
                s = stocks.get(code)
                q = quotes.get(code)
                if not s or not q or q["close"] is None:
                    continue
                px = q["close"]
                foreign = f["foreign"] + f.get("foreign_dealer", 0.0)
                s["net_amt"] += f["total"] * px
                s["foreign_amt"] += foreign * px
                s["trust_amt"] += f["trust"] * px
                s["dealer_amt"] += f["dealer"] * px
                s["foreign_sh"] += foreign
                s["trust_sh"] += f["trust"]
                s["net_sh"] += f["total"]
                s["days_with_flow"] += 1
        if flows_out is not None:
            flows_out[d] = tuple(got)
    prev_close_day = days[5][0].isoformat() if len(days) > 5 else None
    for s in stocks.values():
        v5, v20 = s.pop("vol5"), s.pop("vol20")
        s["avg_vol5"] = sum(v5) / len(v5) if v5 else None
        s["avg_vol20"] = sum(v20) / len(v20) if len(v20) >= 15 else None
        s["vol_ratio"] = (s["avg_vol5"] / s["avg_vol20"]) if s["avg_vol5"] and s["avg_vol20"] else None
        s["net_ratio"] = (s["net_amt"] / s["value5"]) if s["value5"] else None
        prev = s["closes"].get(prev_close_day) if prev_close_day else None
        s["chg5"] = (s["close"] / prev - 1) if s.get("close") and prev else None
        s.pop("closes")
    return stocks


# ------------------------------------------------------------ enrichment data
def enrich(pool: list[dict], days, notes: list) -> None:
    latest = days[0][0]
    before = days[5][0] if len(days) > 5 else None  # 5 個交易日前
    first = days[4][0] if len(days) > 4 else None   # 視窗第一天

    q_now = {**_safe(sources.twse_qfii, latest, note=notes, label="上市外資持股"),
             **_safe(sources.tpex_qfii, latest, note=notes, label="上櫃外資持股")}
    q_then = {}
    if before:
        q_then = {**_safe(sources.twse_qfii, before, note=notes, label="上市外資持股(5日前)"),
                  **_safe(sources.tpex_qfii, before, note=notes, label="上櫃外資持股(5日前)")}
    m_now = {**_safe(sources.twse_margin, latest, note=notes, label="上市融資"),
             **_safe(sources.tpex_margin, latest, note=notes, label="上櫃融資")}
    m_first = {}
    if first:
        m_first = {**_safe(sources.twse_margin, first, note=notes, label="上市融資(視窗首日)"),
                   **_safe(sources.tpex_margin, first, note=notes, label="上櫃融資(視窗首日)")}
    if not m_now:
        notes.append(f"{latest} 融資餘額尚未公布或取得失敗，融資5日增減顯示「—」")
    if not q_now:
        notes.append(f"{latest} 外資持股比率尚未公布或取得失敗，外資持股5日變化顯示「—」")
    pe = {**_safe(sources.twse_pe, latest, note=notes, label="上市本益比"),
          **_safe(sources.tpex_pe, latest, note=notes, label="上櫃本益比")}
    ind = _safe(sources.industries, note=notes, label="產業別")

    for s in pool:
        c = s["code"]
        s["industry"] = ind.get(c) or "—"
        s["pe"] = pe.get(c) or s.get("pe_quote") or None
        a, b = q_now.get(c), q_then.get(c)
        s["qfii_ratio"] = a
        s["qfii_chg5"] = (a - b) if a is not None and b is not None else None
        mn, mf = m_now.get(c), m_first.get(c)
        s["margin_balance"] = mn["balance"] if mn else None
        s["margin_chg5"] = (mn["balance"] - mf["prev"]) if mn and mf and mn["balance"] is not None \
            and mf["prev"] is not None else None


def revenue_months(asof: date, notes: list, need: int = 3,
                   store: history.Store | None = None) -> list[tuple[str, dict]]:
    out = []
    y, m = asof.year, asof.month
    if asof.day <= 10:  # 上月營收須於每月10日前公布，10日前上月資料尚不完整
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    for _ in range(need + 2):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        rev = _safe(sources.mops_revenue, y, m, note=notes, label=f"月營收 {y}-{m:02d}")
        if len(rev) > 500:
            out.append((f"{y}-{m:02d}", rev))
            if store:
                _safe(store.save_revenue, f"{y}-{m:02d}", rev, label="月營收存檔")
        elif not out:
            continue  # 當月尚未公布完畢，往前一個月
        if len(out) >= need:
            break
    return out


# ---------------------------------------------------------------- conditions
def condition_a(s: dict, lists: dict, res: dict | None) -> dict:
    hits = [(name, v) for name, v in lists.items() if s["code"] in (v.get("codes") or [])]
    if hits:
        basis = "、".join(name + (f"（{v['as_of']}）" if v.get("as_of") else "") for name, v in hits)
        evidence = [{"title": name, "url": v["source"], "date": v.get("as_of", "")}
                    for name, v in hits if str(v.get("source", "")).startswith("http")]
        return {"pass": True, "basis": basis, "evidence": evidence}
    if res and res.get("sustainability"):
        r = res["sustainability"]
        ev = [e for e in (r.get("evidence") or []) if e.get("url")]
        passed = r.get("pass")
        if passed is True and not ev:
            passed = None  # 無來源不採信
        return {"pass": passed, "basis": r.get("basis") or "—", "evidence": ev}
    return {"pass": None, "basis": "未查證（無手動清單、未啟用網路研究）", "evidence": []}


def condition_b(s: dict, themes: dict, rev: list[tuple[str, dict]], res: dict | None) -> dict:
    tags = rules.themes_for(s["code"], themes)
    basis = []
    if tags:
        basis.append("主題對照表：" + "、".join(tags))
    if res and res.get("future", {}).get("pass") and res["future"].get("themes"):
        extra = [t for t in res["future"]["themes"] if t not in tags]
        if extra:
            tags += extra
            basis.append("網路研究：" + "、".join(extra) + (f"（{res['future'].get('basis')}）" if res["future"].get("basis") else ""))
    yoy = [{"month": mth, "yoy": data.get(s["code"], {}).get("yoy")} for mth, data in rev]
    rev_ok = rules.revenue_all_positive(yoy)
    if rev_ok:
        basis.append("近3月營收年增皆正（" + "、".join(f"{r['month'][5:]}月 {r['yoy']:+.1f}%" for r in yoy) + "）")
    if tags or rev_ok is True:
        passed = True
    elif rev_ok is False or (res and res.get("future", {}).get("pass") is False):
        passed = False
    else:
        passed = None  # 無主題且營收資料不足
    return {"pass": passed, "themes": tags, "revenue_yoy": yoy, "revenue_all_positive": rev_ok,
            "basis": "；".join(basis) or "非成長主題且近3月營收年增未全為正"}


# ------------------------------------------------------------------- research
def _cache_path(cache_dir: Path, code: str, asof: date) -> Path:
    return cache_dir / f"{asof.isoformat()}_{code}.json"


def run_research(targets: list[dict], asof: date, cache_dir: Path) -> dict[str, dict]:
    if not research.available():
        return {}
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = {}

    def one(s):
        p = _cache_path(cache_dir, s["code"], asof)
        if p.exists():
            return s["code"], json.loads(p.read_text("utf-8"))
        r = research.research_stock(s["code"], s["name"], s["market"], s.get("industry", ""), asof)
        if "error" not in r:
            p.write_text(json.dumps(r, ensure_ascii=False, indent=1), "utf-8")
        return s["code"], r

    with ThreadPoolExecutor(max_workers=int(os.environ.get("SCREENER_WORKERS", "4"))) as ex:
        for code, r in ex.map(one, targets):
            out[code] = r
    return out


def run_news_ratings(pool: list[dict], asof: date, cache_dir: Path, all_names: tuple[str, ...],
                     notes: list) -> dict[str, list[dict] | None]:
    """Condition C from news headlines for every pool stock (free; independent of the API key)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    out, failed = {}, 0
    for s in pool:
        p = cache_dir / f"{asof.isoformat()}_{s['code']}.json"
        if p.exists():
            out[s["code"]] = json.loads(p.read_text("utf-8"))
            continue
        try:
            r = news_ratings.ratings_for(s["code"], s["name"], asof, all_names)
        except Exception as e:  # noqa: BLE001
            log.warning("news ratings failed %s: %r", s["code"], e)
            out[s["code"]] = None
            failed += 1
            continue
        p.write_text(json.dumps(r, ensure_ascii=False, indent=1), "utf-8")
        out[s["code"]] = r
    if failed:
        notes.append(f"投行評等新聞搜尋有 {failed} 檔失敗，這些個股的條件C標示為未查證")
    return out


def _merge_ratings(a: list[dict], b: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in a + b:
        key = (rules.canonical_broker(r.get("broker", "")), str(r.get("date", ""))[:10])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


# ---------------------------------------------------------------------- main
def ensure_taiex(store: history.Store, latest: date, notes: list, months: int = 5) -> dict[str, float]:
    """加權指數收盤（FMTQIK 月表）：當月每次重抓，過去月份已存過就不再抓。"""
    have = store.taiex()
    y, m = latest.year, latest.month
    for k in range(months):
        first = date(y, m, 1)
        ym = first.strftime("%Y-%m")
        if k == 0 or sum(1 for d in have if d.startswith(ym)) < 15:
            got = _safe(sources.taiex_month, first, note=notes, label=f"加權指數 {ym}")
            if got:
                store.save_taiex(got)
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return store.taiex()


def build_series(codes: set[str], days, flows: dict) -> dict[str, dict]:
    out = {}
    for d, tw_q, tp_q in reversed(days):
        tw_f, tp_f = flows.get(d, ({}, {}))
        for code in codes:
            q = tw_q.get(code) or tp_q.get(code)
            if not q or q.get("close") is None:
                continue
            f = (tw_f or {}).get(code) or (tp_f or {}).get(code) if d in flows else None
            if d in flows and f is None:
                f = {"foreign": 0.0, "trust": 0.0, "total": 0.0}  # 當日無法人進出
            signals.append(out.setdefault(code, signals.new_series()), d.isoformat(), q, f)
    return out


def previous_report(out_dir: Path, latest: date) -> dict | None:
    prev = sorted(p for p in (out_dir / "reports").glob("*.json") if p.stem < latest.isoformat())
    return json.loads(prev[-1].read_text("utf-8")) if prev else None


def run(asof: date | None, out_dir: Path, skip_existing: bool = False,
        history_dir: Path | None = None) -> dict | None:
    asof = asof or today_tpe()
    notes: list[str] = []
    store = history.Store(history_dir)
    stored_flows: dict = {}
    days = trading_days(asof, notes=notes, store=store, stored_flows=stored_flows)
    if len(days) < 6:
        raise RuntimeError(f"只取得 {len(days)} 個交易日資料，無法計算（需至少6日）")
    if days[0][0] not in stored_flows and not _safe(sources.twse_insti, days[0][0], label="T86 發布檢查"):
        notes.append(f"{days[0][0]} 三大法人資料尚未公布，改以前一交易日為基準")
        stored_flows = {}
        days = trading_days(days[1][0], notes=notes, store=store, stored_flows=stored_flows)
    existing = out_dir / "reports" / f"{days[0][0].isoformat()}.json"
    if skip_existing and existing.exists():
        prev = json.loads(existing.read_text("utf-8"))
        if prev.get("research_enabled") or not research.available():
            log.info("report for %s already exists; skipping", days[0][0])
            return None
    if len(days) < NEED_DAYS:
        notes.append(f"僅取得 {len(days)} 個交易日行情，均線等技術指標以可得天數計算")
    latest = days[0][0]
    window = [d.isoformat() for d, _, _ in days[:5]][::-1]
    log.info("window %s – %s", window[0], window[-1])
    strategy = signals.load_strategy()

    flows: dict = dict(stored_flows)
    universe = build_universe(days, notes, stored_flows, flows)
    for d, tw_q, tp_q in days[:5]:
        if d in flows:
            _safe(store.save, d, tw_q, tp_q, *flows[d], label=f"每日快照 {d}")
    ranked = sorted((s for s in universe.values() if s["days_with_flow"] and s["net_amt"] > 0),
                    key=lambda s: s["net_amt"], reverse=True)
    pool = ranked[:POOL_SIZE]
    for i, s in enumerate(pool, 1):
        s["rank"] = i
        s["dominant"] = bool(s["net_ratio"] is not None and s["net_ratio"] >= DOMINANT_RATIO)
    enrich(pool, days, notes)

    themes = rules.load_themes()
    lists = rules.load_sustainability()
    rev = revenue_months(latest, notes, store=store)
    if len(rev) < 3:
        notes.append(f"月營收僅取得 {len(rev)} 個月，營收年增條件可能無法判定")

    # 處置股／注意股（官方只提供近期名單，回補舊日期報告時不套用）
    recent = (today_tpe() - latest).days <= 7
    disposal = _safe(sources.disposal, latest + timedelta(days=1), note=notes, label="處置股名單") if recent else {}
    attention = _safe(sources.attention, latest, default=set(), note=notes, label="注意股名單") if recent else set()
    if not recent:
        notes.append("處置股、注意股名單僅提供近期資料，本次（非近期日期）未套用")

    # 先以對照表/營收判定 B，決定哪些需要網路研究（控制 API 成本）
    for s in pool:
        s["B"] = condition_b(s, themes, rev, None)
    max_research = int(os.environ.get("SCREENER_MAX_RESEARCH", "30"))
    targets = [s for s in pool if s["rank"] <= COMPARE_SIZE or s["B"]["pass"] is not False][:max_research]
    research_on = research.available()
    res = run_research(targets, latest, out_dir / "cache" / "research") if research_on else {}
    if not research_on:
        notes.append("未設定 ANTHROPIC_API_KEY：永續性僅依名單判定、個股新聞未取得；投行評等改由新聞標題擷取")

    all_names = tuple(sorted({u["name"] for u in universe.values()}))
    news_c = run_news_ratings(pool, latest, out_dir / "cache" / "news_ratings", all_names, notes)

    # 技術面、籌碼連續性、進場訊號（用近 NEED_DAYS 日行情）
    pf_path = out_dir / "portfolio.json"
    pf_doc = portfolio.load(pf_path) or {}
    held = set((pf_doc.get("state") or {}).get("positions", {})) | \
        {o["code"] for o in (pf_doc.get("state") or {}).get("orders", [])}
    series = build_series({s["code"] for s in pool} | held, days, flows)
    prev_rep = previous_report(out_dir, latest)
    prev_picks = {s["code"] for s in (prev_rep or {}).get("picks", [])}

    for s in pool:
        r = res.get(s["code"])
        s["researched"] = r is not None and "error" not in r
        if r and "error" in r:
            notes.append(f"{s['code']} {s['name']} 網路研究失敗：{r['error']}")
            r = None
        s["A"] = condition_a(s, lists, r)
        s["B"] = condition_b(s, themes, rev, r)
        nc = news_c.get(s["code"])
        c = rules.classify_ratings(_merge_ratings((r or {}).get("ratings") or [], nc or []), latest)
        if not s["researched"] and nc is None:
            c["status"] = "not_checked"
        s["C"] = c
        s["news"] = [n for n in ((r or {}).get("news") or []) if n.get("url")][:2]
        s["research_sources"] = (r or {}).get("searched", [])
        s["disposal"] = disposal.get(s["code"])
        s["attention"] = s["code"] in attention
        f = signals.features(series[s["code"]], strategy) if s["code"] in series else None
        s["tech"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in (f or {}).items()}
        s["buy_days"] = f["buy_days"] if f else None
        s["trust_streak"] = f["trust_streak"] if f else None
        s["trust_ratio"] = (s["trust_amt"] / s["value5"]) if s["value5"] else None
        base = (s["margin_balance"] - s["margin_chg5"]) if s.get("margin_balance") is not None \
            and s.get("margin_chg5") is not None else None
        s["margin_pct5"] = (s["margin_chg5"] / base) if base else None
        if f:
            s["signal"], s["signal_reasons"] = signals.entry_signal(
                f, strategy, disposal=bool(s["disposal"]), attention=s["attention"], margin_pct=s["margin_pct5"])
        else:
            s["signal"], s["signal_reasons"] = signals.WATCH, ["歷史股價不足"]
        s["selected"], s["reasons"] = rules.decide(s)

    for s, sc in zip(pool, signals.percentile_scores(pool, signals.SCORE_KEYS)):
        bonus = {"positive": 5, "negative_only": -5}.get(s["C"]["status"], 0)
        s["score"] = max(0.0, min(100.0, sc + bonus))

    picks = [s for s in pool if s["selected"]][:MAX_PICKS]
    picks.sort(key=lambda s: (s["vol_ratio"] is not None, s["vol_ratio"] or 0), reverse=True)
    for s in picks:
        s["volume_up"] = bool(s["vol_ratio"] and s["vol_ratio"] >= VOLUME_UP)
        s["new_entry"] = bool(prev_rep) and s["code"] not in prev_picks
    if sum(1 for s in pool if s["selected"]) > MAX_PICKS:
        notes.append(f"符合條件超過 {MAX_PICKS} 檔，依買超金額排名保留前 {MAX_PICKS} 檔後再依量增比排序")

    # 大盤濾網、模擬持股
    taiex = ensure_taiex(store, latest, notes)
    reg = signals.regime(taiex, latest.isoformat(), strategy)
    if reg["state"] == "未知":
        notes.append("加權指數歷史不足，大盤濾網暫不套用")
    cands = sorted((s for s in picks if s["signal"] == signals.ENTER), key=lambda s: s["score"], reverse=True)
    cand_rows = [{"code": s["code"], "name": s["name"], "industry": s.get("industry"), "close": s["close"],
                  "atr": (s["tech"] or {}).get("atr")} for s in cands]
    quotes_by_day = [(d.isoformat(), {**tp_q, **tw_q}) for d, tw_q, tp_q in reversed(days)]
    pf = _safe(portfolio.update, pf_path, strategy, quotes_by_day, series, cand_rows, reg["max_entries"],
               latest.isoformat(), taiex, notes, note=notes, label="模擬持股")
    ordered = {o["code"] for o in (pf or {}).get("orders", [])}
    for s in picks:
        s["order"] = s["code"] in ordered

    tech = _safe(tech_news.collect, latest, today_tpe(), notes, default=[], note=notes, label="科技新聞")

    market = market_summary(universe, days)
    market["regime"] = reg
    report = {
        "generated_at": datetime.now(TPE).isoformat(timespec="seconds"),
        "asof": latest.isoformat(),
        "window": window,
        "research_enabled": research_on,
        "model": research.MODEL if research_on else None,
        "market": market,
        "strategy": {k: v for k, v in strategy.items() if k != "backtest"},
        "picks": [public(s) for s in picks],
        "pool": [public(s) for s in pool],
        "compare": [public(s) for s in pool[:COMPARE_SIZE]],
        "portfolio": pf or None,
        "tech_news": tech,
        "revenue_months": [m for m, _ in rev],
        "notes": sorted(set(notes), key=notes.index),
        "sources": OFFICIAL_SOURCES,
    }
    report["summary"] = summary_text(report)
    write_performance(out_dir, store, days, taiex, strategy, report, notes)
    return report


def write_performance(out_dir: Path, store: history.Store, days, taiex: dict, strategy: dict,
                      report: dict, notes: list) -> None:
    """Score every past report's picks (including today's, written by the caller) against later prices."""
    prices: dict[str, dict[str, tuple]] = {}
    first = min([p.stem for p in (out_dir / "reports").glob("*.json")] + [report["asof"]])
    for d in store.days():
        if d.isoformat() < first:
            continue
        rows = store.rows(d) or []
        prices[d.isoformat()] = {r["code"]: (r["open"], r["close"]) for r in rows}
    for d, tw_q, tp_q in days:
        day = prices.setdefault(d.isoformat(), {})
        for q in (tw_q, tp_q):
            for code, x in q.items():
                day.setdefault(code, (x.get("open"), x.get("close")))
    c = strategy["costs"]
    cost = c["fee"] * c["fee_discount"] * 2 + c["tax"]
    try:
        perf = performance.compute(out_dir / "reports", prices, taiex, cost, extra=report)
    except Exception as e:  # noqa: BLE001
        log.warning("performance failed: %r", e)
        notes.append(f"績效追蹤計算失敗：{e}")
        return
    (out_dir / "performance.json").write_text(json.dumps(perf, ensure_ascii=False, indent=1), "utf-8")


def market_summary(universe: dict, days) -> dict:
    tot = {"上市": [0.0, 0.0, 0.0], "上櫃": [0.0, 0.0, 0.0]}
    for s in universe.values():
        t = tot[s["market"]]
        t[0] += s["net_amt"]
        t[1] += s["foreign_amt"]
        t[2] += s["trust_amt"]
    return {k: {"net": v[0], "foreign": v[1], "trust": v[2]} for k, v in tot.items()}


KEYS = ("code name market industry rank close chg5 net_amt foreign_amt trust_amt dealer_amt foreign_sh "
        "trust_sh net_sh value5 net_ratio dominant avg_vol5 avg_vol20 vol_ratio volume_up pe qfii_ratio "
        "qfii_chg5 margin_balance margin_chg5 margin_pct5 A B C news selected reasons researched research_sources "
        "buy_days trust_streak trust_ratio score tech signal signal_reasons disposal attention new_entry order").split()


def public(s: dict) -> dict:
    return {k: s.get(k) for k in KEYS}


def _yi(v: float) -> str:
    return f"{v / 1e8:+,.1f} 億"


def summary_text(rep: dict) -> dict:
    picks = rep["picks"]
    mk = rep["market"]
    total = mk["上市"]["net"] + mk["上櫃"]["net"]
    foreign = mk["上市"]["foreign"] + mk["上櫃"]["foreign"]
    trust = mk["上市"]["trust"] + mk["上櫃"]["trust"]
    direction = "買超" if total >= 0 else "賣超"
    line = (f"近5日（{rep['window'][0]}～{rep['window'][-1]}）三大法人合計{direction}約 {abs(total) / 1e8:,.0f} 億元"
            f"（外資 {_yi(foreign)}、投信 {_yi(trust)}；上市 {_yi(mk['上市']['net'])}、上櫃 {_yi(mk['上櫃']['net'])}，依個股買賣超×收盤價估算）。")
    top3 = []
    for s in picks[:3]:
        bits = [f"{s['code']} {s['name']}", f"量增比 {s['vol_ratio']:.2f}" if s["vol_ratio"] else "量增比 —",
                f"5日法人買超 {_yi(s['net_amt'])}"]
        if s["dominant"]:
            bits.append("法人主導")
        if s["B"]["themes"]:
            bits.append("、".join(s["B"]["themes"][:2]))
        top3.append("｜".join(bits))
    return {"count": len(picks), "top3": top3, "market_line": line}
