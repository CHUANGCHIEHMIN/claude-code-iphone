"""Steps 1–3 of the screen plus assembly of the final report payload."""
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import news_ratings, research, rules, sources, tech_news

log = logging.getLogger(__name__)
TPE = timezone(timedelta(hours=8))

POOL_SIZE = 50
COMPARE_SIZE = 20
MAX_PICKS = 20
DOMINANT_RATIO = 0.10
VOLUME_UP = 1.2

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
def trading_days(asof: date, need: int = 21, max_back: int = 50, notes: list | None = None) -> list[tuple[date, dict, dict]]:
    """Walk back from `asof`, keeping days where TWSE published a closing table."""
    days = []
    d = asof
    for _ in range(max_back):
        if d.weekday() < 5:
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


def build_universe(days, notes: list) -> dict[str, dict]:
    """Aggregate 5-day institutional flows + 20-day volume for every common stock."""
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
        for market, fetch, quotes in (("上市", sources.twse_insti, tw_q), ("上櫃", sources.tpex_insti, tp_q)):
            flows = _safe(fetch, d, note=notes, label=f"{market}三大法人 {d}")
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


def revenue_months(asof: date, notes: list, need: int = 3) -> list[tuple[str, dict]]:
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
def run(asof: date | None, out_dir: Path, skip_existing: bool = False) -> dict | None:
    asof = asof or today_tpe()
    notes: list[str] = []
    days = trading_days(asof, notes=notes)
    if len(days) < 6:
        raise RuntimeError(f"只取得 {len(days)} 個交易日資料，無法計算（需至少6日）")
    if not _safe(sources.twse_insti, days[0][0], label="T86 發布檢查"):
        notes.append(f"{days[0][0]} 三大法人資料尚未公布，改以前一交易日為基準")
        days = trading_days(days[1][0], need=21, notes=notes)
    existing = out_dir / "reports" / f"{days[0][0].isoformat()}.json"
    if skip_existing and existing.exists():
        prev = json.loads(existing.read_text("utf-8"))
        if prev.get("research_enabled") or not research.available():
            log.info("report for %s already exists; skipping", days[0][0])
            return None
    if len(days) < 21:
        notes.append(f"僅取得 {len(days)} 個交易日行情，20日均量以可得天數計算")
    latest = days[0][0]
    window = [d.isoformat() for d, _, _ in days[:5]][::-1]
    log.info("window %s – %s", window[0], window[-1])

    universe = build_universe(days, notes)
    ranked = sorted((s for s in universe.values() if s["days_with_flow"] and s["net_amt"] > 0),
                    key=lambda s: s["net_amt"], reverse=True)
    pool = ranked[:POOL_SIZE]
    for i, s in enumerate(pool, 1):
        s["rank"] = i
        s["dominant"] = bool(s["net_ratio"] is not None and s["net_ratio"] >= DOMINANT_RATIO)
    enrich(pool, days, notes)

    themes = rules.load_themes()
    lists = rules.load_sustainability()
    rev = revenue_months(latest, notes)
    if len(rev) < 3:
        notes.append(f"月營收僅取得 {len(rev)} 個月，營收年增條件可能無法判定")

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
        s["selected"], s["reasons"] = rules.decide(s)

    picks = [s for s in pool if s["selected"]][:MAX_PICKS]
    picks.sort(key=lambda s: (s["vol_ratio"] is not None, s["vol_ratio"] or 0), reverse=True)
    for s in picks:
        s["volume_up"] = bool(s["vol_ratio"] and s["vol_ratio"] >= VOLUME_UP)
    if sum(1 for s in pool if s["selected"]) > MAX_PICKS:
        notes.append(f"符合條件超過 {MAX_PICKS} 檔，依買超金額排名保留前 {MAX_PICKS} 檔後再依量增比排序")

    tech = _safe(tech_news.collect, latest, today_tpe(), notes, default=[], note=notes, label="科技新聞")

    market = market_summary(universe, days)
    report = {
        "generated_at": datetime.now(TPE).isoformat(timespec="seconds"),
        "asof": latest.isoformat(),
        "window": window,
        "research_enabled": research_on,
        "model": research.MODEL if research_on else None,
        "market": market,
        "picks": [public(s) for s in picks],
        "pool": [public(s) for s in pool],
        "compare": [public(s) for s in pool[:COMPARE_SIZE]],
        "tech_news": tech,
        "revenue_months": [m for m, _ in rev],
        "notes": sorted(set(notes), key=notes.index),
        "sources": OFFICIAL_SOURCES,
    }
    report["summary"] = summary_text(report)
    return report


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
        "qfii_chg5 margin_balance margin_chg5 A B C news selected reasons researched research_sources").split()


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
