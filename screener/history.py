"""Local store of daily market snapshots (quotes + institutional flows) for tracking and backtests.

Layout under data/history/ (outside docs/, so it is not published on the website):
  YYYY/YYYY-MM-DD.csv.gz   one file per trading day, common stocks only, written once
  taiex.csv                發行量加權股價指數 daily closes (also the trading-day calendar)
  revenue/YYYY-MM.json     月營收年增率 {code: yoy}
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import os
from datetime import date
from pathlib import Path

from . import rules

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "data" / "history"
COLS = ["code", "name", "market", "open", "high", "low", "close", "volume", "value",
        "foreign", "trust", "dealer", "total"]


def default_dir() -> Path:
    return Path(os.environ.get("SCREENER_HISTORY_DIR") or DEFAULT_DIR)


def _f(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return f"{v:g}" if isinstance(v, float) else str(v)


def _n(s: str) -> float | None:
    return float(s) if s not in ("", None) else None


class Store:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else default_dir()

    # ------------------------------------------------------------ day snapshots
    def path(self, d: date) -> Path:
        return self.root / str(d.year) / f"{d.isoformat()}.csv.gz"

    def has(self, d: date) -> bool:
        return self.path(d).exists()

    def days(self) -> list[date]:
        out = []
        if not self.root.exists():
            return out
        for p in self.root.glob("*/*.csv.gz"):
            try:
                out.append(date.fromisoformat(p.name[:10]))
            except ValueError:
                continue
        return sorted(out)

    def save(self, d: date, tw_q: dict, tp_q: dict, tw_f: dict, tp_f: dict, overwrite: bool = False) -> bool:
        """Write one trading day. Only complete days (both markets' quotes and flows) are stored."""
        if not (tw_q and tp_q and tw_f and tp_f):
            return False
        p = self.path(d)
        if p.exists() and not overwrite:
            return False
        rows = []
        for market, quotes, flows in (("上市", tw_q, tw_f), ("上櫃", tp_q, tp_f)):
            for code, q in quotes.items():
                if q.get("close") is None or not rules.is_common_stock(code, q.get("name", "")):
                    continue
                f = flows.get(code)
                fl = [None] * 4 if f is None else [
                    f.get("foreign", 0.0) + f.get("foreign_dealer", 0.0), f.get("trust", 0.0),
                    f.get("dealer", 0.0), f.get("total", 0.0)]
                rows.append([code, q.get("name", ""), market, q.get("open"), q.get("high"), q.get("low"),
                             q["close"], q.get("volume"), q.get("value"), *fl])
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(COLS)
        for r in sorted(rows):
            w.writerow([_f(x) for x in r])
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        with open(tmp, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(buf.getvalue().encode("utf-8"))
        tmp.replace(p)
        return True

    def rows(self, d: date) -> list[dict] | None:
        p = self.path(d)
        if not p.exists():
            return None
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            out = []
            for r in csv.DictReader(fh):
                for k in COLS[3:]:
                    r[k] = _n(r[k])
                out.append(r)
            return out

    def load(self, d: date) -> tuple[dict, dict, dict, dict] | None:
        """Return (twse_quotes, tpex_quotes, twse_flows, tpex_flows) shaped like `sources` output."""
        rows = self.rows(d)
        if rows is None:
            return None
        tw_q, tp_q, tw_f, tp_f = {}, {}, {}, {}
        for r in rows:
            q = {"name": r["name"], "open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"],
                 "volume": r["volume"] or 0.0, "value": r["value"] or 0.0, "diff": None, "pe": None}
            tq, tf = (tw_q, tw_f) if r["market"] == "上市" else (tp_q, tp_f)
            tq[r["code"]] = q
            if r["total"] is not None:
                tf[r["code"]] = {"name": r["name"], "foreign": r["foreign"] or 0.0, "foreign_dealer": 0.0,
                                 "trust": r["trust"] or 0.0, "dealer": r["dealer"] or 0.0, "total": r["total"]}
        return tw_q, tp_q, tw_f, tp_f

    # ------------------------------------------------------------------ TAIEX
    def taiex(self) -> dict[str, float]:
        p = self.root / "taiex.csv"
        if not p.exists():
            return {}
        out = {}
        for line in p.read_text("utf-8").splitlines()[1:]:
            d, _, v = line.partition(",")
            if d and v:
                out[d] = float(v)
        return out

    def save_taiex(self, closes: dict[str, float]) -> None:
        if not closes:
            return
        merged = {**self.taiex(), **closes}
        self.root.mkdir(parents=True, exist_ok=True)
        body = "date,close\n" + "".join(f"{d},{_f(v)}\n" for d, v in sorted(merged.items()))
        (self.root / "taiex.csv").write_text(body, "utf-8")

    # ---------------------------------------------------------------- revenue
    def revenue(self, ym: str) -> dict[str, float] | None:
        p = self.root / "revenue" / f"{ym}.json"
        return json.loads(p.read_text("utf-8")) if p.exists() else None

    def revenue_months(self) -> list[str]:
        d = self.root / "revenue"
        return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []

    def save_revenue(self, ym: str, rev: dict[str, dict]) -> None:
        data = {c: v["yoy"] for c, v in sorted(rev.items()) if v.get("yoy") is not None}
        if len(data) < 500:
            return
        p = self.root / "revenue" / f"{ym}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf-8")
