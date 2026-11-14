"""Technical / chip features, entry signals and scores shared by the daily report and the backtest.

A *series* is a dict of equal-length lists, oldest first:
  dates, open, high, low, close, volume, value, foreign, trust, total   (flows may be None)
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ("dates", "open", "high", "low", "close", "volume", "value", "foreign", "trust", "total")

ENTER, WATCH, HOT, EXCLUDED = "可進場", "觀察", "過熱", "排除"


def load_strategy() -> dict:
    return json.loads((ROOT / "config" / "strategy.json").read_text("utf-8"))


def new_series() -> dict:
    return {k: [] for k in FIELDS}


def append(s: dict, d: str, q: dict, f: dict | None) -> None:
    s["dates"].append(d)
    for k in ("open", "high", "low", "close", "volume", "value"):
        s[k].append(q.get(k))
    if f is None:
        s["foreign"].append(None), s["trust"].append(None), s["total"].append(None)
    else:
        s["foreign"].append((f.get("foreign") or 0.0) + (f.get("foreign_dealer") or 0.0))
        s["trust"].append(f.get("trust") or 0.0)
        s["total"].append(f.get("total") or 0.0)


def upto(s: dict, n: int) -> dict:
    """First n bars (series as of an earlier day)."""
    return {k: v[:n] for k, v in s.items()}


def sma(xs: list, n: int, end: int | None = None) -> float | None:
    xs = xs[:end] if end is not None else xs
    w = [x for x in xs[-n:] if x is not None]
    return sum(w) / n if len(xs) >= n and len(w) == n else None


def atr(s: dict, n: int = 14) -> float | None:
    h, lo, c = s["high"], s["low"], s["close"]
    if len(c) < n + 1:
        return None
    trs = []
    for i in range(len(c) - n, len(c)):
        hi, low, pc = h[i] or c[i], lo[i] or c[i], c[i - 1]
        if hi is None or low is None or pc is None:
            return None
        trs.append(max(hi - low, abs(hi - pc), abs(low - pc)))
    return sum(trs) / n


def streak(xs: list, pred) -> int:
    k = 0
    for x in reversed(xs):
        if x is None or not pred(x):
            break
        k += 1
    return k


def features(s: dict, p: dict) -> dict:
    """Indicators as of the last bar of `s`."""
    e, x = p["entry"], p["exit"]
    c, v = s["close"], s["volume"]
    last = c[-1] if c else None
    ma = sma(c, e["ma"])
    ma_prev = sma(c, e["ma"], end=len(c) - e["slope_days"]) if len(c) > e["slope_days"] else None
    ma_pull = sma(c, e["pullback_ma"])
    ma_trail = sma(c, x["trail_ma"])
    n = e["breakout_days"]
    prior_highs = [h if h is not None else cc for h, cc in zip(s["high"][-n - 1:-1], c[-n - 1:-1])]
    hi_prev = max(prior_highs) if len(prior_highs) == n and None not in prior_highs else None
    v5, v20 = sma(v, 5), sma(v, 20)
    inst = [None if f is None or t is None else f + t for f, t in zip(s["foreign"], s["trust"])]
    flows5 = [t for t in s["total"][-5:] if t is not None]
    return {
        "close": last,
        "ma": ma, "ma_up": bool(ma and ma_prev and ma > ma_prev),
        "ma_pull": ma_pull, "ma_trail": ma_trail,
        "high_prev": hi_prev,
        "breakout": bool(last and hi_prev and last > hi_prev),
        "vol_ratio": (v5 / v20) if v5 and v20 else None,
        "chg5": (last / c[-6] - 1) if len(c) >= 6 and last and c[-6] else None,
        "bias": (last / ma - 1) if last and ma else None,
        "atr": atr(s, x["atr_n"]),
        "buy_days": sum(1 for t in flows5 if t > 0),
        "trust_streak": streak(s["trust"], lambda t: t > 0),
        "inst_sell_streak": streak(inst, lambda t: t < 0),
    }


def entry_signal(f: dict, p: dict, *, disposal: bool = False, attention: bool = False,
                 margin_pct: float | None = None) -> tuple[str, list[str]]:
    """Status for the next trading day's open, with the reasons behind it."""
    e, o = p["entry"], p["overheat"]
    if disposal:
        return EXCLUDED, ["處置股"]
    hot = []
    if f["chg5"] is not None and f["chg5"] > o["chg5_max"]:
        hot.append(f"5日漲幅 {f['chg5'] * 100:.1f}% 超過 {o['chg5_max'] * 100:.0f}%")
    if f["bias"] is not None and f["bias"] > o["bias20_max"]:
        hot.append(f"高於{e['ma']}日均線 {f['bias'] * 100:.1f}%")
    if margin_pct is not None and margin_pct > o["margin_chg5_pct_max"]:
        hot.append(f"融資5日增加 {margin_pct * 100:.1f}%")
    if attention and o.get("attention_is_overheat", True):
        hot.append("注意股")
    if hot:
        return HOT, hot
    if f["ma"] is None or f["close"] is None:
        return WATCH, ["歷史股價不足，無法判斷趨勢"]
    if f["close"] <= f["ma"]:
        return WATCH, [f"收盤未站上{e['ma']}日均線"]
    if not f["ma_up"]:
        return WATCH, [f"{e['ma']}日均線未上彎"]
    if f["breakout"] and (f["vol_ratio"] or 0) >= e["vol_ratio_min"]:
        return ENTER, [f"突破前{e['breakout_days']}日高點且量增"]
    if not e.get("pullback_entry"):
        return WATCH, [f"趨勢向上，等待量增突破前{e['breakout_days']}日高點"]
    if f["ma_pull"] and 0 <= f["close"] / f["ma_pull"] - 1 <= e["pullback_pct"]:
        return ENTER, [f"拉回至{e['pullback_ma']}日均線 {e['pullback_pct'] * 100:.0f}% 內"]
    return WATCH, ["趨勢向上，等待突破（量增）或拉回"]


def percentile_scores(rows: list[dict], keys: tuple[str, ...]) -> list[float]:
    """Average percentile rank (0–100) of each row across `keys`; missing values count as the lowest."""
    n = len(rows)
    if n == 0:
        return []
    total = [0.0] * n
    for k in keys:
        vals = [r.get(k) if r.get(k) is not None else float("-inf") for r in rows]
        for i, v in enumerate(vals):
            below = sum(1 for w in vals if w < v)
            ties = sum(1 for w in vals if w == v) - 1
            total[i] += (below + ties / 2) / (n - 1) if n > 1 else 1.0
    return [round(100 * t / len(keys), 1) for t in total]


SCORE_KEYS = ("net_ratio", "trust_ratio", "buy_days", "vol_ratio")


def crash(closes: list[float], days: list[str], p: dict) -> dict | None:
    """大跌買點：最近 crash_window 個交易日內，曾有一天收盤距 crash_lookback 日高點跌幅 ≥ crash_drawdown."""
    m = p["market"]
    dd_min, look, win = m.get("crash_drawdown"), m.get("crash_lookback", 20), m.get("crash_window", 5)
    if not dd_min or not closes:
        return None
    for j in range(len(closes) - 1, max(-1, len(closes) - 1 - win), -1):
        hi = max(closes[max(0, j - look): j + 1])
        dd = closes[j] / hi - 1
        if dd <= -dd_min:
            return {"date": days[j], "drawdown": round(dd, 4), "days_left": win - (len(closes) - 1 - j) - 1,
                    "max_entries": m.get("crash_max_entries", m["strong_max_entries"])}
    return None


def regime(taiex: dict[str, float], asof: str, p: dict) -> dict:
    """大盤濾網：加權指數 vs N 日均線；大跌後幾天另列「大跌買點」."""
    days = sorted(d for d in taiex if d <= asof)
    n = p["market"]["ma"]
    closes = [taiex[d] for d in days]
    ma = sma(closes, n)
    last = closes[-1] if closes else None
    cr = crash(closes, days, p)
    if ma is None or last is None:
        out = {"state": "未知", "taiex": last, "ma": ma, "date": days[-1] if days else None,
               "max_entries": p["market"]["strong_max_entries"]}
    else:
        weak = last < ma
        out = {"state": "弱勢" if weak else "強勢", "taiex": last, "ma": ma, "date": days[-1],
               "max_entries": p["market"]["weak_max_entries" if weak else "strong_max_entries"]}
    out["crash"] = cr
    if cr:
        out["max_entries"] = cr["max_entries"]
    return out


def entry_candidates(stocks: list[dict], reg: dict) -> list[dict]:
    """模擬持股的進場候選（依綜合分數排序）：平常只取「可進場」；大跌買點期間取清單中所有未過熱、未排除的股票."""
    if reg.get("crash"):
        ok = [s for s in stocks if s["signal"] not in (HOT, EXCLUDED)]
    else:
        ok = [s for s in stocks if s["signal"] == ENTER]
    return sorted(ok, key=lambda s: s["score"], reverse=True)
