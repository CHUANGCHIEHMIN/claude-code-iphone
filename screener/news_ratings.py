"""Condition C without the paid API: pull investment-bank ratings out of news headlines.

Searches Google News (RSS) for the stock name together with the four target brokers over the
last ~3 months, then extracts broker / rating / target price / date from each headline. Only
headlines that name the stock, one of the four brokers, and a rating or target price are kept,
and every rating links back to its article so it can be checked.
"""
from __future__ import annotations

import email.utils
import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date

from .net import fetch_text
from .rules import canonical_broker

log = logging.getLogger(__name__)

RSS = "https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
BROKER_TERMS = ["摩根士丹利", "大摩", "高盛", "摩根大通", "小摩", "美銀", "美林", "Morgan Stanley",
                "Goldman", "JPMorgan", "J.P. Morgan", "摩根大通證券", "BofA", "美國銀行"]
_BROKER_RE = re.compile("|".join(re.escape(t) for t in sorted(BROKER_TERMS, key=len, reverse=True)), re.I)

POS = ["優於大盤", "首評買進", "買進", "加碼", "增持", "買入", "喊進", "喊買", "Overweight", "Outperform", "Buy"]
NEU = ["中立", "中性", "持有", "Equal-weight", "Equal Weight", "Neutral", "Hold"]
NEG = ["劣於大盤", "減碼", "減持", "賣出", "Underweight", "Underperform", "Sell"]
_RATING_RE = re.compile("|".join(re.escape(t) for t in sorted(POS + NEU + NEG, key=len, reverse=True)), re.I)
_FINAL_RE = re.compile(r"(?:調升|上調|調高|調降|下調|調低|升|降|改|調整)(?:評等|投資評等)?(?:至|為|到)\s*(" + _RATING_RE.pattern + ")", re.I)
_NUM = r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
_TP_FINAL = re.compile(r"(?:至|到|上看|喊|為|調升|調高|上調|升|調降|下修|降)\s*" + _NUM + r"\s*元")
_TP_AFTER = re.compile(r"^目標價[^0-9！？!?，,。；;]{0,6}?" + _NUM + r"\s*元")
_TP_BEFORE = re.compile(_NUM + r"\s*元(?:的)?目標價")
_CLAUSE_END = re.compile(r"[！？!?，。；;｜|]")


def short_name(name: str) -> str:
    return re.sub(r"[*＊]|-KY|-創", "", name).strip()


def query_url(name: str) -> str:
    brokers = " OR ".join(f'"{t}"' if " " in t else t for t in ("摩根士丹利", "大摩", "高盛", "摩根大通", "小摩", "美銀"))
    q = f'"{short_name(name)}" ({brokers}) when:90d'
    return RSS.format(q=urllib.parse.quote(q))


def parse_rss(xml_text: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        src = (it.findtext("source") or "").strip()
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3].strip()
        pub = it.findtext("pubDate")
        try:
            d = email.utils.parsedate_to_datetime(pub).date() if pub else None
        except (TypeError, ValueError):
            d = None
        items.append({"title": title, "url": (it.findtext("link") or "").strip(), "source": src, "date": d})
    return items


def _find_name(title: str, sn: str, longer: list[str]) -> int:
    """Position of `sn` in `title`, ignoring hits that are really a longer stock name (長榮 vs 長榮航)."""
    start = 0
    while (pos := title.find(sn, start)) >= 0:
        if not any(title.startswith(other, pos) for other in longer):
            return pos
        start = pos + 1
    return -1


def extract(title: str, name: str, all_names: tuple[str, ...] = ()) -> dict | None:
    """Return {broker, rating, target_price} if the headline rates `name`, else None."""
    sn = short_name(name)
    longer = [n for n in map(short_name, all_names) if n != sn and n.startswith(sn)]
    pos = _find_name(title, sn, longer)
    if pos < 0:
        return None
    # a headline that also names other listed stocks (lists, comparisons) can't be pinned on this one
    own = {sn, *longer}
    for other in map(short_name, all_names):
        if len(other) >= 2 and other not in own and not sn.startswith(other) and other in title:
            return None
    brokers = [(m.start(), canonical_broker(m.group(0))) for m in _BROKER_RE.finditer(title)]
    brokers = [(p, b) for p, b in brokers if b]
    if not brokers:
        return None
    broker = min(brokers, key=lambda pb: abs(pb[0] - pos))[1]
    m = _FINAL_RE.search(title)
    rating = m.group(1) if m else None
    if rating is None:
        m = _RATING_RE.search(title)
        rating = m.group(0) if m else None
    tp = None
    i = title.find("目標價")
    if i >= 0:
        seg = title[i: i + 24]
        cut = _CLAUSE_END.search(seg)
        seg = seg[: cut.start()] if cut else seg
        m = _TP_FINAL.search(seg) or _TP_AFTER.search(seg) or _TP_BEFORE.search(title)
        if m:
            tp = float(m.group(1).replace(",", ""))
    if rating is None and tp is None:
        return None
    return {"broker": broker, "rating": rating, "target_price": tp}


def ratings_for(code: str, name: str, asof: date, all_names: tuple[str, ...] = ()) -> list[dict]:
    """Latest headline-derived rating per broker (raises on network failure)."""
    xml_text = fetch_text(query_url(name))
    best: dict[str, dict] = {}
    for it in parse_rss(xml_text):
        if not it["date"] or it["date"] > asof:
            continue
        x = extract(it["title"], name, all_names)
        if not x:
            continue
        r = {**x, "date": it["date"].isoformat(), "source": it["source"] or "新聞", "url": it["url"],
             "title": it["title"], "via": "新聞標題"}
        cur = best.get(x["broker"])
        if cur is None or r["date"] > cur["date"]:
            best[x["broker"]] = r
    return sorted(best.values(), key=lambda r: r["date"], reverse=True)
