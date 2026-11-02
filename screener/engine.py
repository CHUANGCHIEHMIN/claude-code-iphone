"""Day-by-day trading simulation shared by the backtest and the daily simulated portfolio.

Timeline for one trading day:
  on_open(day, bars)      execute yesterday's orders at today's open (exits first, then entries)
  on_close(day, bars, f)  intraday stop-loss (raised to cost once a close is breakeven_after above it),
                          then close-based exit signals → tomorrow's exit orders; mark equity
  plan(day, candidates)   today's entry signals → tomorrow's entry orders (position limits, industry cap)

bars: {code: {"open", "high", "low", "close"}}; f: {code: features dict from signals.features}
"""
from __future__ import annotations

import math

ALL_EXITS = ("stop", "trail", "inst", "time")
REASON = {"stop": "停損", "breakeven": "保本停損", "trail": "移動停利（跌破均線）", "inst": "法人連續賣超",
          "time": "時間停損", "hold": "持有期滿"}


def new_state(capital: float) -> dict:
    return {"capital": capital, "cash": capital, "positions": {}, "orders": [], "exit_orders": {},
            "trades": [], "equity": [], "last_day": None}


class Engine:
    def __init__(self, params: dict, state: dict | None = None, exits: tuple[str, ...] = ALL_EXITS,
                 fixed_hold: int | None = None):
        self.p = params
        self.s = state or new_state(params["portfolio"]["capital"])
        self.exits = set(exits)
        self.fixed_hold = fixed_hold
        c = params["costs"]
        self.buy_rate = c["fee"] * c["fee_discount"]
        self.sell_rate = c["fee"] * c["fee_discount"] + c["tax"]

    # ----------------------------------------------------------------- helpers
    def equity(self) -> float:
        return self.s["cash"] + sum(pos["shares"] * pos["last"] for pos in self.s["positions"].values())

    def _sell(self, day: str, code: str, price: float, reason: str) -> None:
        pos = self.s["positions"].pop(code)
        value = pos["shares"] * price
        self.s["cash"] += value * (1 - self.sell_rate)
        cost = pos["shares"] * pos["entry"] * (1 + self.buy_rate)
        net = value * (1 - self.sell_rate)
        self.s["trades"].append({
            "code": code, "name": pos["name"], "industry": pos.get("industry"),
            "entry_date": pos["entry_date"], "entry": pos["entry"], "exit_date": day, "exit": round(price, 2),
            "shares": pos["shares"], "days": pos["days"], "pnl": round(net - cost),
            "ret": round(net / cost - 1, 4), "reason": REASON.get(reason, reason),
        })
        self.s["exit_orders"].pop(code, None)

    # --------------------------------------------------------------- the day
    def on_open(self, day: str, bars: dict) -> None:
        for code, reason in list(self.s["exit_orders"].items()):
            b = bars.get(code)
            if code in self.s["positions"] and b and b.get("open"):
                self._sell(day, code, b["open"], reason)
        e, x, pf = self.p["entry"], self.p["exit"], self.p["portfolio"]
        orders, self.s["orders"] = self.s["orders"], []
        eq = self.equity()
        for o in orders:
            b = bars.get(o["code"])
            if not b or not b.get("open") or o["code"] in self.s["positions"]:
                continue
            px, ref = b["open"], o["ref_close"]
            if ref and (px / ref - 1 > e["max_gap_up"] or px >= ref * 1.095):
                continue  # 跳空過大或接近漲停：放棄，不追價
            stop = px - x["atr_mult"] * o["atr"] if o.get("atr") else px * (1 - x["max_stop_pct"])
            stop = max(stop, px * (1 - x["max_stop_pct"]))
            risk = px - stop
            if risk <= 0:
                continue
            shares = min(eq * pf["risk_per_trade"] / risk, eq / pf["max_positions"] / px,
                         self.s["cash"] / (px * (1 + self.buy_rate)))
            shares = math.floor(shares)
            if shares < 1:
                continue
            self.s["cash"] -= shares * px * (1 + self.buy_rate)
            self.s["positions"][o["code"]] = {
                "name": o["name"], "industry": o.get("industry"), "shares": shares, "entry": round(px, 2),
                "entry_date": day, "stop": round(stop, 2), "peak": px, "last": px, "days": 0,
            }

    def on_close(self, day: str, bars: dict, feats: dict) -> None:
        x = self.p["exit"]
        for code, pos in list(self.s["positions"].items()):
            b = bars.get(code)
            if not b or b.get("close") is None:
                continue
            pos["days"] += 1
            low, op = b.get("low") or b["close"], b.get("open") or b["close"]
            if "stop" in self.exits and low <= pos["stop"]:
                self._sell(day, code, min(op, pos["stop"]), "breakeven" if pos["stop"] >= pos["entry"] else "stop")
                continue
            pos["last"] = b["close"]
            pos["peak"] = max(pos["peak"], b["close"])
            be = x.get("breakeven_after")
            if "stop" in self.exits and be is not None and pos["peak"] / pos["entry"] - 1 >= be:
                pos["stop"] = max(pos["stop"], pos["entry"])  # 保本：之後最多回到成本出場
            if code in self.s["exit_orders"]:
                continue
            f = feats.get(code) or {}
            gain = b["close"] / pos["entry"] - 1
            if self.fixed_hold and pos["days"] >= self.fixed_hold:
                self.s["exit_orders"][code] = "hold"
            elif "trail" in self.exits and x.get("trail_after") is not None \
                    and pos["peak"] / pos["entry"] - 1 >= x["trail_after"] \
                    and f.get("ma_trail") and b["close"] < f["ma_trail"]:
                self.s["exit_orders"][code] = "trail"
            elif "inst" in self.exits and f.get("inst_sell_streak", 0) >= x["inst_sell_days"]:
                self.s["exit_orders"][code] = "inst"
            elif "time" in self.exits and pos["days"] >= x["time_stop_days"] and gain < x["time_stop_min_gain"]:
                self.s["exit_orders"][code] = "time"
        self.s["equity"].append([day, round(self.equity())])
        self.s["last_day"] = day

    def plan(self, day: str, candidates: list[dict], max_new: int) -> list[dict]:
        """candidates: [{code, name, industry, close, atr, ...}] in priority order."""
        pf = self.p["portfolio"]
        held = set(self.s["positions"]) | {o["code"] for o in self.s["orders"]}
        staying = [c for c in self.s["positions"] if c not in self.s["exit_orders"]]
        room = pf["max_positions"] - len(staying) - len(self.s["orders"])
        by_ind: dict[str, int] = {}
        for c in staying:
            ind = self.s["positions"][c].get("industry") or "—"
            by_ind[ind] = by_ind.get(ind, 0) + 1
        for o in self.s["orders"]:
            by_ind[o.get("industry") or "—"] = by_ind.get(o.get("industry") or "—", 0) + 1
        new = []
        for c in candidates:
            if len(new) >= min(room, max_new):
                break
            ind = c.get("industry") or "—"
            if c["code"] in held or by_ind.get(ind, 0) >= pf["max_per_industry"]:
                continue
            o = {"code": c["code"], "name": c["name"], "industry": c.get("industry"), "signal_date": day,
                 "ref_close": c["close"], "atr": c.get("atr")}
            new.append(o)
            held.add(c["code"])
            by_ind[ind] = by_ind.get(ind, 0) + 1
        self.s["orders"].extend(new)
        return new


def stats(trades: list[dict], equity: list[list], capital: float, bench: dict[str, float] | None = None) -> dict:
    """Summary metrics for a simulation."""
    n = len(trades)
    wins = [t["ret"] for t in trades if t["ret"] > 0]
    losses = [t["ret"] for t in trades if t["ret"] <= 0]
    avg_w = sum(wins) / len(wins) if wins else None
    avg_l = sum(losses) / len(losses) if losses else None
    out = {
        "trades": n,
        "win_rate": round(len(wins) / n, 4) if n else None,
        "avg_ret": round(sum(t["ret"] for t in trades) / n, 4) if n else None,
        "avg_win": round(avg_w, 4) if avg_w is not None else None,
        "avg_loss": round(avg_l, 4) if avg_l is not None else None,
        "payoff": round(avg_w / -avg_l, 2) if avg_w and avg_l else None,
        "avg_days": round(sum(t["days"] for t in trades) / n, 1) if n else None,
    }
    if equity:
        vals = [v for _, v in equity]
        peak, mdd = vals[0], 0.0
        for v in vals:
            peak = max(peak, v)
            mdd = min(mdd, v / peak - 1)
        total = vals[-1] / capital - 1
        years = max(len(vals) / 245, 1 / 245)
        out.update({"total_return": round(total, 4), "cagr": round((1 + total) ** (1 / years) - 1, 4)
                    if total > -1 else None, "max_drawdown": round(mdd, 4),
                    "start": equity[0][0], "end": equity[-1][0]})
        if bench:
            b0, b1 = bench.get(equity[0][0]), bench.get(equity[-1][0])
            out["bench_return"] = round(b1 / b0 - 1, 4) if b0 and b1 else None
    return out
