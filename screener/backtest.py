"""Replay the screen over the history store and measure what would have happened.

python -m screener.backtest                    # 依 config/strategy.json 的 backtest 設定
python -m screener.backtest --start 2024-01-01 --end 2026-10-30

Two kinds of results:
  1. 事件研究：每天各種選股規則的名單，隔日開盤買進、持有 5/10/20 日的平均報酬（扣成本）與相對加權指數。
  2. 策略模擬：用進場訊號＋停損停利＋部位控管跑完整模擬帳戶（與網站「持股」頁相同引擎）。

Limitations (also written into the output): condition C (news) and 處置/注意股 cannot be replayed;
condition A uses today's lists (look-ahead); 融資 is not in the store.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median

from . import history, rules, signals, sources
from .engine import ALL_EXITS, Engine, stats

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
POOL, PICKS, MIN_VALUE5 = 50, 20, 5e8
KEEP = 90  # bars kept per stock

VARIANTS = [
    ("base", "現行規則", "候選池50檔 → A永續＋B未來性 → 依買超金額取前20"),
    ("pool50", "候選池全部50檔", "不套用 A、B，用來看 A、B 有沒有加分"),
    ("no_a", "只看B未來性", "不套用 A 永續（A 名單用的是現在的名單，有後見之明）"),
    ("ratio", "依買超占成交值排序", "A＋B 通過者依「買超÷成交值」取前20"),
    ("score", "依綜合分數排序", "A＋B 通過者依綜合分數（買超占比、投信占比、買超天數、量增比）取前20"),
    ("ratio_pool", "全市場買超占比候選池", "5日成交值≥5億者依買超占比取前50 → A＋B → 前20（減少大型股偏差）"),
    ("vol_up", "現行規則＋量增", "現行名單中量增比≥1.2"),
    ("trust3", "現行規則＋投信連買3日", "現行名單中投信連續買超≥3日"),
    ("not_hot", "現行規則＋排除過熱", "現行名單排除5日漲幅>15%或乖離>15%"),
    ("enter", "現行規則＋可進場訊號", "現行名單中當天出現可進場訊號者"),
]
EXIT_VARIANTS = [
    ("full", "完整出場規則", ALL_EXITS, None),
    ("stop_hold10", "停損＋固定持有10日", ("stop",), 10),
    ("hold10", "固定持有10日（無停損）", (), 10),
]


def _rev_available(d: date, months: list[str]) -> list[str]:
    """Revenue months published by `d` (month m is out by the 10th of m+1), newest first."""
    out = []
    for ym in sorted(months, reverse=True):
        y, m = int(ym[:4]), int(ym[5:])
        pub = date(y + (m == 12), m % 12 + 1, 11)
        if pub <= d:
            out.append(ym)
    return out


def _agg(rs: list[float], xs: list[float]) -> dict | None:
    if not rs:
        return None
    return {"n": len(rs), "win_rate": round(sum(1 for r in rs if r > 0) / len(rs), 4),
            "avg": round(sum(rs) / len(rs), 4), "median": round(median(rs), 4),
            "excess": round(sum(xs) / len(xs), 4) if xs else None,
            "beat_rate": round(sum(1 for x in xs if x > 0) / len(xs), 4) if xs else None}


def run(store: history.Store, start: date, end: date, p: dict, themes: dict, lists: dict,
        industries: dict[str, str] | None = None) -> dict:
    taiex = store.taiex()
    cal = [d for d in store.days() if d <= end]  # stored days are trading days by construction
    if len(cal) < 30:
        raise RuntimeError(f"歷史資料只有 {len(cal)} 個交易日，至少需要 30 日（請先執行 backfill）")
    split = date.fromisoformat(p["backtest"]["split"])
    horizons = p["backtest"]["horizons"]
    c = p["costs"]
    cost = c["fee"] * c["fee_discount"] * 2 + c["tax"]
    sust = {code for v in lists.values() for code in (v.get("codes") or [])}
    theme_codes = {code for codes in themes.values() for code in codes}
    rev_months = store.revenue_months()
    rev_cache: dict[str, dict] = {}

    series: dict[str, dict] = {}
    names: dict[str, tuple[str, str]] = {}
    events: list[dict] = []
    due: dict[int, list[tuple[dict, str, int]]] = {}
    engines = {k: Engine(p, exits=ex, fixed_hold=fh) for k, _, ex, fh in EXIT_VARIANTS}
    first_i = None
    tested_days = 0

    for i, d in enumerate(cal):
        rows = store.rows(d) or []
        iso = d.isoformat()
        bars = {}
        for r in rows:
            code = r["code"]
            names[code] = (r["name"], r["market"])
            s = series.setdefault(code, signals.new_series())
            f = None if r["total"] is None else {"foreign": r["foreign"], "trust": r["trust"], "total": r["total"]}
            signals.append(s, iso, r, f if f is not None else {"foreign": 0.0, "trust": 0.0, "total": 0.0})
            if len(s["dates"]) > KEEP + 40:
                for k in s:
                    del s[k][:40]
            bars[code] = r
        # resolve forward-return events that need today's prices
        for ev, kind, h in due.pop(i, []):
            b = bars.get(ev["code"])
            if kind == "entry":
                ev["entry"] = b["open"] if b and b.get("open") else None
            elif ev.get("entry") and b and b.get("close"):
                ev[f"r{h}"] = b["close"] / ev["entry"] * (1 - cost) - 1
                t0, t1 = taiex.get(ev["date"]), taiex.get(iso)
                if t0 and t1:
                    ev[f"x{h}"] = ev[f"r{h}"] - (t1 / t0 - 1)
        for eng in engines.values():
            eng.on_open(iso, bars)
            feats = {code: signals.features(series[code], p) for code in eng.s["positions"] if code in series}
            eng.on_close(iso, bars, feats)
        if d < start or i < 25:
            continue
        if first_i is None:
            first_i = i
        tested_days += 1
        last5 = {x.isoformat() for x in cal[max(0, i - 4): i + 1]}
        stocks = []
        for code, s in series.items():
            if not s["dates"] or s["dates"][-1] != iso:
                continue
            k = len(s["dates"])
            idx = [j for j in range(max(0, k - 5), k) if s["dates"][j] in last5]
            net = sum((s["total"][j] or 0) * s["close"][j] for j in idx)
            value5 = sum(s["value"][j] or 0 for j in idx)
            trust = sum((s["trust"][j] or 0) * s["close"][j] for j in idx)
            stocks.append({"code": code, "net_amt": net, "value5": value5,
                           "net_ratio": net / value5 if value5 else None,
                           "trust_ratio": trust / value5 if value5 else None})
        avail = _rev_available(d, rev_months)[:3]
        for ym in avail:
            if ym not in rev_cache:
                rev_cache[ym] = store.revenue(ym) or {}

        def enrich(st: dict) -> dict:
            code = st["code"]
            f = signals.features(series[code], p)
            yoy = [rev_cache.get(ym, {}).get(code) for ym in avail]
            rev_ok = len(yoy) == 3 and all(y is not None and y > 0 for y in yoy)
            st.update({"name": names[code][0], "industry": (industries or {}).get(code) or names[code][1], "f": f,
                       "vol_ratio": f["vol_ratio"], "buy_days": f["buy_days"], "trust_streak": f["trust_streak"],
                       "A": code in sust, "B": code in theme_codes or rev_ok})
            st["signal"], _ = signals.entry_signal(f, p)
            return st

        pool = [enrich(st) for st in sorted((x for x in stocks if x["net_amt"] > 0),
                                            key=lambda x: x["net_amt"], reverse=True)[:POOL]]
        for st, sc in zip(pool, signals.percentile_scores(pool, signals.SCORE_KEYS)):
            st["score"] = sc
        ab = [st for st in pool if st["A"] and st["B"]]
        base = ab[:PICKS]
        alt = [enrich(st) for st in sorted((x for x in stocks if x["net_amt"] > 0 and x["value5"] >= MIN_VALUE5
                                            and x["net_ratio"] is not None),
                                           key=lambda x: x["net_ratio"], reverse=True)[:POOL]]
        lists_today = {
            "base": base, "pool50": pool, "no_a": [st for st in pool if st["B"]][:PICKS],
            "ratio": sorted(ab, key=lambda st: st["net_ratio"] or 0, reverse=True)[:PICKS],
            "score": sorted(ab, key=lambda st: st["score"], reverse=True)[:PICKS],
            "ratio_pool": [st for st in alt if st["A"] and st["B"]][:PICKS],
            "vol_up": [st for st in base if (st["vol_ratio"] or 0) >= 1.2],
            "trust3": [st for st in base if st["trust_streak"] >= 3],
            "not_hot": [st for st in base if st["signal"] != signals.HOT],
            "enter": [st for st in base if st["signal"] == signals.ENTER],
        }
        for key, sel in lists_today.items():
            for st in sel:
                ev = {"v": key, "date": iso, "code": st["code"], "test": d >= split}
                events.append(ev)
                due.setdefault(i + 1, []).append((ev, "entry", 0))
                for h in horizons:
                    due.setdefault(i + h, []).append((ev, "exit", h))
        reg = signals.regime(taiex, iso, p)
        cands = sorted((st for st in base if st["signal"] == signals.ENTER), key=lambda st: st["score"], reverse=True)
        rows_c = [{"code": st["code"], "name": st["name"], "industry": st["industry"],
                   "close": st["f"]["close"], "atr": st["f"]["atr"]} for st in cands]
        for eng in engines.values():
            eng.plan(iso, rows_c, reg["max_entries"])

    if first_i is None:
        raise RuntimeError("回測區間內沒有足夠資料")
    period = (cal[first_i].isoformat(), cal[-1].isoformat())
    out_v = []
    for key, name, desc in VARIANTS:
        evs = [e for e in events if e["v"] == key]
        row = {"key": key, "name": name, "desc": desc,
               "picks_per_day": round(len(evs) / tested_days, 1) if tested_days else None}
        for seg, sel in (("all", evs), ("train", [e for e in evs if not e["test"]]),
                         ("test", [e for e in evs if e["test"]])):
            row[seg] = {f"h{h}": _agg([e[f"r{h}"] for e in sel if f"r{h}" in e],
                                      [e[f"x{h}"] for e in sel if f"x{h}" in e]) for h in horizons}
        out_v.append(row)
    out_s = []
    cap = p["portfolio"]["capital"]
    for key, name, _, _ in EXIT_VARIANTS:
        st = engines[key].s
        eq = [e for e in st["equity"] if e[0] >= period[0]]
        tr = st["trades"]
        seg = {"all": stats(tr, eq, cap, taiex)}
        tr_eq = [e for e in eq if e[0] < split.isoformat()]
        te_eq = [e for e in eq if e[0] >= split.isoformat()]
        if tr_eq:
            seg["train"] = stats([t for t in tr if t["entry_date"] < split.isoformat()], tr_eq, cap, taiex)
        if te_eq:
            base_cap = tr_eq[-1][1] if tr_eq else cap
            seg["test"] = stats([t for t in tr if t["entry_date"] >= split.isoformat()], te_eq, base_cap, taiex)
        reasons: dict[str, int] = {}
        for t in tr:
            reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
        out_s.append({"key": key, "name": name, **seg, "exit_reasons": reasons,
                      "equity_curve": eq[::5] + ([eq[-1]] if eq and (len(eq) - 1) % 5 else []),
                      "recent_trades": tr[-15:][::-1]})
    t0, t1 = taiex.get(period[0]), taiex.get(period[1])
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "period": period, "split": split.isoformat(), "days": tested_days, "horizons": horizons,
        "cost": cost, "bench_return": round(t1 / t0 - 1, 4) if t0 and t1 else None,
        "taiex_curve": [[d.isoformat(), taiex[d.isoformat()]] for d in cal[first_i::5] if d.isoformat() in taiex],
        "variants": out_v, "strategies": out_s,
        "caveats": [
            "條件C（投行評等新聞）與處置股、注意股無法回測，模擬時視為不影響；融資增減未存歷史，不在過熱判斷中。",
            "條件A使用目前的永續名單套用到過去，有後見之明偏差；「只看B未來性」一列可作對照。",
            "條件B的產業主題對照表也是目前版本；月營收以每月10日公布、11日起可用估算。",
            "進場價為報告隔日開盤價、出場為收盤價，已扣手續費與證交稅；未計滑價與零股流動性。",
            "事件研究每天都重新計算名單，相鄰日期的持有期重疊，樣本並非彼此獨立。",
            f"{split.isoformat()} 之前為調參期、之後為驗證期；兩段都優於大盤的規則才較可信。",
        ],
    }


def render_md(bt: dict) -> str:
    pct = lambda v: "—" if v is None else f"{v * 100:+.2f}%"  # noqa: E731
    rate = lambda v: "—" if v is None else f"{v * 100:.0f}%"  # noqa: E731
    L = [f"# 回測結果 {bt['period'][0]} ～ {bt['period'][1]}",
         f"_產出時間：{bt['generated_at']}；共 {bt['days']} 個交易日；加權指數同期 {pct(bt['bench_return'])}；"
         f"調參期／驗證期分界 {bt['split']}_\n", "## 1. 選股規則比較（事件研究）",
         "隔日開盤買進、持有 N 個交易日，扣成本後的平均報酬；超額＝減去同期加權指數漲跌。\n"]
    for h in bt["horizons"]:
        L.append(f"### 持有 {h} 日")
        L.append("| 規則 | 每日檔數 | 全期平均 | 全期勝率 | 全期超額 | 調參期超額 | 驗證期超額 | 驗證期勝率 |")
        L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for v in bt["variants"]:
            a, tr, te = (v[s].get(f"h{h}") or {} for s in ("all", "train", "test"))
            L.append(f"| {v['name']} | {v['picks_per_day'] or '—'} | {pct(a.get('avg'))} | {rate(a.get('win_rate'))} | "
                     f"{pct(a.get('excess'))} | {pct(tr.get('excess'))} | {pct(te.get('excess'))} | {rate(te.get('win_rate'))} |")
        L.append("")
    L.append("## 2. 策略模擬（進場訊號＋出場規則＋部位控管）")
    L.append("| 出場方式 | 交易數 | 勝率 | 平均報酬 | 賺賠比 | 總報酬 | 年化 | 最大回撤 | 驗證期總報酬 | 加權指數 |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for s in bt["strategies"]:
        a, te = s["all"], s.get("test") or {}
        L.append(f"| {s['name']} | {a['trades']} | {rate(a['win_rate'])} | {pct(a['avg_ret'])} | {a['payoff'] or '—'} | "
                 f"{pct(a.get('total_return'))} | {pct(a.get('cagr'))} | {pct(a.get('max_drawdown'))} | "
                 f"{pct(te.get('total_return'))} | {pct(a.get('bench_return'))} |")
    L.append("\n## 3. 限制")
    L += [f"- {c}" for c in bt["caveats"]]
    L.append("- 回測結果不代表未來績效，本報告不構成投資建議。")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="選股規則回測")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--out", default=str(ROOT / "docs"))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = signals.load_strategy()
    store = history.Store()
    days = store.days()
    if not days:
        raise SystemExit("history store is empty; run python -m screener.backfill first")
    end = date.fromisoformat(args.end) if args.end else days[-1]
    start = date.fromisoformat(args.start) if args.start else \
        max(days[0] + timedelta(days=45), end - timedelta(days=int(365 * p["backtest"]["years"])))
    try:
        ind = sources.industries()
    except Exception:  # noqa: BLE001
        ind = {}
    store.save_industries(ind)
    ind = ind if len(ind) >= 500 else store.industries()
    bt = run(store, start, end, p, rules.load_themes(), rules.load_sustainability(), ind)
    out = Path(args.out)
    (out / "data").mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(parents=True, exist_ok=True)
    (out / "data" / "backtest.json").write_text(json.dumps(bt, ensure_ascii=False, indent=1), "utf-8")
    (out / "reports" / "backtest.md").write_text(render_md(bt), "utf-8")
    log.info("backtest %s – %s written", *bt["period"])


if __name__ == "__main__":
    main()
