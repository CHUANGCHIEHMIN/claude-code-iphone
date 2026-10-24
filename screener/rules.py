"""Screening rules: common-stock filter, conditions A/B/C, selection."""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"

BROKERS = {
    "J.P. Morgan": ("jp morgan", "j.p. morgan", "jpmorgan", "摩根大通", "小摩"),
    "BofA": ("bank of america", "bofa", "美銀", "美國銀行", "merrill", "美林"),
    "Morgan Stanley": ("morgan stanley", "摩根士丹利", "大摩"),
    "Goldman Sachs": ("goldman", "高盛"),
}
POSITIVE = ("buy", "overweight", "outperform", "買進", "加碼", "優於大盤", "增持", "買入", "conviction")
NEGATIVE = ("sell", "underweight", "underperform", "賣出", "減碼", "劣於大盤", "減持")

COMMON_CODE = re.compile(r"^[1-9]\d{3}$")


def is_common_stock(code: str, name: str) -> bool:
    """普通股：4碼、非00開頭(ETF)、非91xx(存託憑證)、名稱不含DR；權證/特別股/ETN 皆非4碼純數字。"""
    code = code.strip()
    if not COMMON_CODE.match(code):
        return False
    if code.startswith("91"):
        return False
    if "DR" in name.upper() or "ETF" in name.upper() or "ETN" in name.upper():
        return False
    return True


def load_themes() -> dict[str, list[str]]:
    return json.loads((CONFIG / "themes.json").read_text("utf-8"))["themes"]


def load_sustainability() -> dict[str, dict]:
    return json.loads((CONFIG / "sustainability.json").read_text("utf-8"))["lists"]


def themes_for(code: str, themes: dict[str, list[str]]) -> list[str]:
    return [t for t, codes in themes.items() if code in codes]


def canonical_broker(s: str) -> str | None:
    low = (s or "").lower()
    for canon, keys in BROKERS.items():
        if any(k in low for k in keys):
            return canon
    return None


def rating_polarity(rating: str) -> str:
    low = (rating or "").lower()
    # "underweight"/"underperform" contain "weight"/"perform" – check negatives first
    if any(k in low for k in NEGATIVE):
        return "negative"
    if any(k in low for k in POSITIVE):
        return "positive"
    return "neutral"


def classify_ratings(ratings: list[dict], asof: date, window_days: int = 92) -> dict:
    """Keep only the 4 target brokers within ~3 months; summarise polarity."""
    kept = []
    for r in ratings or []:
        broker = canonical_broker(r.get("broker", ""))
        if not broker:
            continue
        d = _parse_date(r.get("date"))
        if d is None or d > asof + timedelta(days=1) or (asof - d).days > window_days:
            continue
        kept.append({**r, "broker": broker, "polarity": rating_polarity(r.get("rating", ""))})
    pos = [r for r in kept if r["polarity"] == "positive"]
    neg = [r for r in kept if r["polarity"] == "negative"]
    if pos:
        status = "positive"
    elif neg:
        status = "negative_only"
    elif kept:
        status = "neutral"
    else:
        status = "no_coverage"
    return {"status": status, "ratings": kept}


def _parse_date(s) -> date | None:
    if not s:
        return None
    m = re.search(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", str(s))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def revenue_all_positive(rev: list[dict]) -> bool | None:
    """rev: 最近3個月 [{'month': '2026-09', 'yoy': 12.3}, ...]."""
    if not rev or len(rev) < 3 or any(r.get("yoy") is None for r in rev[:3]):
        return None
    return all(r["yoy"] > 0 for r in rev[:3])


def decide(stock: dict) -> tuple[bool, list[str]]:
    """入選規則：A 與 B 皆符合，且 C 不是「只有負面評等」。回傳 (是否入選, 未入選原因)."""
    reasons = []
    if stock["A"]["pass"] is not True:
        reasons.append("A永續未符合" if stock["A"]["pass"] is False else "A永續未能查證")
    if stock["B"]["pass"] is not True:
        reasons.append("B未來性未符合" if stock["B"]["pass"] is False else "B未來性資料不足")
    if stock["C"]["status"] == "negative_only":
        reasons.append("C僅有負面投行評等")
    return (not reasons), reasons
