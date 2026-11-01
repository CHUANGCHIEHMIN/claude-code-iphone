"""Simulated portfolio that follows the report's entry signals and the exit rules every trading day.

State lives in docs/data/portfolio.json. `prev` keeps the state from before the latest day so a rerun
of the same day starts from the same point instead of double-counting.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from . import signals
from .engine import REASON, Engine, new_state, stats


def load(path: Path) -> dict | None:
    return json.loads(path.read_text("utf-8")) if path.exists() else None


def update(path: Path, p: dict, days: list[tuple[str, dict]], series: dict[str, dict],
           candidates: list[dict], max_new: int, latest: str, taiex: dict[str, float],
           notes: list) -> dict:
    """days: [(iso, {code: quote})] oldest first, ending at `latest`."""
    doc = load(path) or {}
    st = doc.get("state")
    if st and st.get("last_day") and st["last_day"] > latest:
        notes.append(f"模擬持股已更新至 {st['last_day']}，本次（{latest}）不重算")
        return summary(st, p, taiex, latest)
    if st and st.get("last_day") == latest and doc.get("prev"):
        st = copy.deepcopy(doc["prev"])
    if not st:
        st = new_state(p["portfolio"]["capital"])
        st["started"] = latest
    eng = Engine(p, st)
    pending = [(d, q) for d, q in days if st.get("last_day") is None or d > st["last_day"]]
    if st.get("last_day") is None:
        pending = pending[-1:]
    prev = copy.deepcopy(eng.s)
    for d, quotes in pending:
        if d == latest:
            prev = copy.deepcopy(eng.s)
        eng.on_open(d, quotes)
        feats = {}
        for code in eng.s["positions"]:
            s = series.get(code)
            if s and d in s["dates"]:
                feats[code] = signals.features(signals.upto(s, s["dates"].index(d) + 1), p)
        eng.on_close(d, quotes, feats)
    if eng.s.get("last_day") == latest:
        eng.plan(latest, candidates, max_new)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"state": eng.s, "prev": prev}, ensure_ascii=False, indent=1), "utf-8")
    return summary(eng.s, p, taiex, latest)


def summary(st: dict, p: dict, taiex: dict[str, float], latest: str) -> dict:
    pos = []
    for code, x in sorted(st["positions"].items(), key=lambda kv: kv[1]["entry_date"]):
        pos.append({"code": code, "name": x["name"], "industry": x.get("industry"), "shares": x["shares"],
                    "entry_date": x["entry_date"], "entry": x["entry"], "last": x["last"],
                    "ret": round(x["last"] / x["entry"] - 1, 4), "stop": x["stop"], "days": x["days"],
                    "exit_order": REASON.get(st["exit_orders"].get(code)) if code in st["exit_orders"] else None})
    orders = [{**o, "est_stop": round(max(o["ref_close"] - p["exit"]["atr_mult"] * o["atr"],
                                          o["ref_close"] * (1 - p["exit"]["max_stop_pct"])), 2)
               if o.get("atr") else round(o["ref_close"] * (1 - p["exit"]["max_stop_pct"]), 2)}
              for o in st["orders"]]
    return {
        "asof": latest, "started": st.get("started"), "capital": st["capital"],
        "cash": round(st["cash"]), "equity": round(st["cash"] + sum(x["shares"] * x["last"]
                                                                    for x in st["positions"].values())),
        "positions": pos, "orders": orders,
        "exits": [x for x in pos if x["exit_order"]],
        "trades": st["trades"][-30:][::-1],
        "stats": stats(st["trades"], st["equity"], st["capital"], taiex),
        "equity_curve": st["equity"][-250:],
    }
