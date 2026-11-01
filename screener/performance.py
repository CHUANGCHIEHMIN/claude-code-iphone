"""Track what happened to every past pick: returns 1/5/10/20 trading days later, vs 加權指數.

Entry = open of the trading day after the report (the report comes out at 21:00, so the report-day
close cannot be traded). Exit = close h trading days after entry (day 1 = entry day). Returns are net of
round-trip costs. Benchmark = 加權指數 close on the report day → close on the same exit day.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from statistics import median

HORIZONS = (1, 5, 10, 20)


def _agg(rows: list[dict], h: int) -> dict | None:
    rs = [r[f"r{h}"] for r in rows if r.get(f"r{h}") is not None]
    if not rs:
        return None
    ex = [r[f"x{h}"] for r in rows if r.get(f"x{h}") is not None]
    wins = [x for x in rs if x > 0]
    losses = [x for x in rs if x <= 0]
    return {"n": len(rs), "win_rate": round(len(wins) / len(rs), 4), "avg": round(sum(rs) / len(rs), 4),
            "median": round(median(rs), 4),
            "avg_win": round(sum(wins) / len(wins), 4) if wins else None,
            "avg_loss": round(sum(losses) / len(losses), 4) if losses else None,
            "excess": round(sum(ex) / len(ex), 4) if ex else None,
            "beat_rate": round(sum(1 for x in ex if x > 0) / len(ex), 4) if ex else None}


GROUPS = [
    ("全部入選股", lambda r: True),
    ("量增（≥1.2）", lambda r: r.get("volume_up") is True),
    ("非量增", lambda r: r.get("volume_up") is False),
    ("法人主導（買超占成交值≥10%）", lambda r: r.get("dominant") is True),
    ("新進榜", lambda r: r.get("new_entry") is True),
    ("訊號：可進場", lambda r: r.get("signal") == "可進場"),
    ("訊號：觀察", lambda r: r.get("signal") == "觀察"),
    ("訊號：過熱", lambda r: r.get("signal") == "過熱"),
    ("綜合分數前半", lambda r: r.get("score_half") == "high"),
    ("綜合分數後半", lambda r: r.get("score_half") == "low"),
]


def compute(reports_dir: Path, prices: dict[str, dict[str, tuple]], taiex: dict[str, float],
            cost: float, extra: dict | None = None) -> dict:
    """prices: {iso day: {code: (open, close)}}; taiex keys define the trading calendar.
    `extra` is a report not yet written to disk (today's); it replaces a file with the same date."""
    cal = sorted(set(taiex) | set(prices))
    pos = {d: i for i, d in enumerate(cal)}
    reps = {}
    for p in sorted(reports_dir.glob("*.json")):
        rep = json.loads(p.read_text("utf-8"))
        reps[rep["asof"]] = rep
    if extra:
        reps[extra["asof"]] = extra
    rows = []
    for d, rep in sorted(reps.items()):
        if d not in pos:
            continue
        i = pos[d]
        picks = rep.get("picks") or []
        scores = sorted((s.get("score") for s in picks if s.get("score") is not None), reverse=True)
        cut = scores[(len(scores) - 1) // 2] if scores else None
        for s in picks:
            row = {"date": d, "code": s["code"], "name": s["name"], "volume_up": s.get("volume_up"),
                   "dominant": s.get("dominant"), "new_entry": s.get("new_entry"), "signal": s.get("signal"),
                   "score": s.get("score"),
                   "score_half": None if s.get("score") is None or cut is None
                   else ("high" if s["score"] >= cut else "low")}
            entry_day = cal[i + 1] if i + 1 < len(cal) else None
            bar = prices.get(entry_day, {}).get(s["code"]) if entry_day else None
            entry = bar[0] if bar and bar[0] else None
            row["entry_date"], row["entry"] = entry_day, entry
            for h in HORIZONS:
                j = i + h
                if entry is None or j >= len(cal):
                    continue
                b = prices.get(cal[j], {}).get(s["code"])
                if not b or not b[1]:
                    continue
                row[f"r{h}"] = round(b[1] / entry * (1 - cost) - 1, 4)
                t0, t1 = taiex.get(d), taiex.get(cal[j])
                if t0 and t1:
                    row[f"x{h}"] = round(row[f"r{h}"] - (t1 / t0 - 1), 4)
            rows.append(row)
    groups = []
    for name, pred in GROUPS:
        sel = [r for r in rows if pred(r)]
        if not sel:
            continue
        groups.append({"name": name, **{f"h{h}": _agg(sel, h) for h in HORIZONS}})
    by_day = []
    for d in sorted({r["date"] for r in rows}, reverse=True):
        sel = [r for r in rows if r["date"] == d]
        by_day.append({"date": d, "n": len(sel), **{f"h{h}": _agg(sel, h) for h in HORIZONS}})
    return {"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "horizons": list(HORIZONS), "cost": cost, "groups": groups, "by_day": by_day,
            "rows": sorted(rows, key=lambda r: (r["date"], r["code"]), reverse=True)}
