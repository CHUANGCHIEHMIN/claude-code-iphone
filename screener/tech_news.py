"""Daily domestic / international tech news without the paid API.

Pulls headlines from Google News RSS (Traditional Chinese edition for domestic media, US English
edition for international media), groups headlines from different outlets that report the same
story, and keeps only stories carried by at least MIN_SOURCES distinct outlets — each with every
source link so it can be checked. Non-Chinese headlines are machine-translated to Traditional
Chinese through the free Google Translate endpoint, with mainland terms mapped to Taiwan usage.
"""
from __future__ import annotations

import email.utils
import html
import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

from .net import fetch_json, fetch_text

log = logging.getLogger(__name__)
TPE = timezone(timedelta(hours=8))

PER_REGION = 10
MIN_SOURCES = 2
MAX_LINKS = 6

EDITIONS = {
    "國內": "hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "國外": "hl=en-US&gl=US&ceid=US:en",
}
TOPIC = "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?{ed}"
SEARCH = "https://news.google.com/rss/search?q={q}&{ed}"
QUERIES = {
    "國內": ["(AI OR 人工智慧 OR 半導體 OR 晶片 OR 先進封裝 OR 矽光子 OR 量子)",
             "(機器人 OR 低軌衛星 OR 儲能 OR 資安 OR 新藥 OR 電動車 OR 太空)",
             "(輝達 OR 台積電 OR 蘋果 OR Google OR 微軟 OR OpenAI)"],
    "國外": ["(AI OR semiconductor OR chip OR quantum OR robotics)",
             "(satellite OR space OR battery OR biotech OR cybersecurity OR breakthrough)",
             "(Nvidia OR Apple OR Google OR Microsoft OR OpenAI OR TSMC)"],
}
TRANSLATE = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=zh-TW&dt=t&q={q}"

# 股價、盤勢類標題不是科技新聞
_MARKET = re.compile(r"漲停|跌停|盤中|收盤|股價|目標價|除息|ETF|台股|美股|個股|法人|外資|台指期|夜盤|期指|ADR|標普|"
                     r"大漲|大跌|暴漲|暴跌|狂殺|重挫|崩跌|財報|"
                     r"\bstocks?\b|\bshares?\b|price target|Nasdaq|Dow\b|S&P|\bETF|earnings", re.I)
# 掛著科技公司名、但與科技無關的社會新聞（天災、工安、活動）
_OFFTOPIC = re.compile(r"颱風|地震|運動會|尾牙|工安|身亡|喪命|罹難|\d+死|遺孀|命案|車禍|\bkilled\b|\bdies\b", re.I)
# 標題尾巴的媒體欄目名（「- 綜合」「| 財經焦點」「| 金融要聞| 產經」「- 台股 - 新聞」）
_SECTION_TAIL = re.compile(r"\s*[|｜\-–—]\s*[\u4e00-\u9fff ]{1,6}\s*$")
# 機器翻譯常見的大陸用語 → 台灣用語
TW_TERMS = [("英偉達", "輝達"), ("芯片", "晶片"), ("人工智能", "人工智慧"), ("智能手機", "智慧型手機"),
            ("軟件", "軟體"), ("硬件", "硬體"), ("網絡", "網路"), ("互聯網", "網際網路"), ("數據中心", "資料中心"),
            ("服務器", "伺服器"), ("內存", "記憶體"), ("存儲", "儲存"), ("光刻", "微影"), ("硅", "矽"),
            ("量子計算", "量子運算"), ("初創", "新創"), ("視頻", "影片"), ("信息", "資訊"), ("谷歌", "Google"),
            ("臉書", "Facebook"), ("台積公司", "台積電"), ("鴻海精密", "鴻海")]
_CJK = re.compile(r"[一-鿿]")
_LINK = re.compile(r'<a href="([^"]+)"[^>]*>(.*?)</a>(?:\s|&nbsp;|\xa0)*<font[^>]*>(.*?)</font>', re.S)
_STOP = set("the a an and or of to in on for with from by at as is are be its it this that new after over "
            "into says say said will can how why what more than about amid".split())


def _q(q: str, asof: date) -> str:
    return f"{q} after:{(asof - timedelta(days=1)).isoformat()} before:{(asof + timedelta(days=1)).isoformat()}"


def feed_urls(region: str, asof: date, today: date | None = None) -> list[str]:
    ed = EDITIONS[region]
    urls = [SEARCH.format(q=urllib.parse.quote(_q(q, asof)), ed=ed) for q in QUERIES[region]]
    if today is None or abs((today - asof).days) <= 1:  # topic feed only has current headlines
        urls.insert(0, TOPIC.format(ed=ed))
    return urls


def _clean_title(title: str, src: str) -> str:
    title = html.unescape(title).strip()
    if src and title.endswith(" - " + src):
        title = title[: -len(src) - 3].strip()
    while (m := _SECTION_TAIL.search(title)) and m.start() > 0:
        title = title[: m.start()].rstrip()
    return title


def parse_feed(xml_text: str) -> list[list[dict]]:
    """Each RSS item → a group of articles: the item itself plus the related coverage Google lists."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    groups = []
    for it in root.iter("item"):
        src = (it.findtext("source") or "").strip()
        pub = it.findtext("pubDate")
        try:
            dt = email.utils.parsedate_to_datetime(pub).astimezone(TPE) if pub else None
        except (TypeError, ValueError):
            dt = None
        d = dt.date() if dt else None
        head = {"title": _clean_title(it.findtext("title") or "", src), "url": (it.findtext("link") or "").strip(),
                "source": src, "date": d}
        group = [head]
        for u, t, s in _LINK.findall(it.findtext("description") or ""):
            s = html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
            t = _clean_title(re.sub(r"<[^>]+>", "", t), s)
            if u != head["url"]:
                group.append({"title": t, "url": html.unescape(u), "source": s, "date": d})
        groups.append(group)
    return groups


def tokens(title: str) -> set[str]:
    t = title.lower()
    words = {w for w in re.findall(r"[a-z0-9][a-z0-9.\-]*[a-z0-9]|[a-z0-9]", t) if w not in _STOP and len(w) > 1}
    cjk = re.sub(r"[^一-鿿]+", " ", t).split()
    bigrams = {seg[i: i + 2] for seg in cjk for i in range(len(seg) - 1)}
    return words | bigrams


def similar(a: set[str], b: set[str]) -> bool:
    shared = len(a & b)
    return shared >= 6 or (shared >= 4 and shared / max(1, min(len(a), len(b))) >= 0.4)


def cluster(groups: list[list[dict]]) -> list[list[dict]]:
    """Merge RSS groups that report the same story (a shared link, or any two similar headlines)."""
    parent = list(range(len(groups)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    toks = [[tokens(a["title"]) for a in g] for g in groups]
    urls = [{a["url"] for a in g} for g in groups]
    for i in range(len(groups)):
        for j in range(i):
            if find(i) == find(j):
                continue
            if urls[i] & urls[j] or any(similar(x, y) for x in toks[i] for y in toks[j]):
                parent[find(i)] = find(j)
    merged: dict[int, list[dict]] = {}
    for i, g in enumerate(groups):
        merged.setdefault(find(i), []).extend(g)
    return list(merged.values())


def _source_key(s: str) -> str:
    return re.sub(r"[\s.\-_]+|新聞網$|新聞$|\.com$", "", s.lower())


def is_tech(title: str) -> bool:
    return bool(title) and not _MARKET.search(title) and not _OFFTOPIC.search(title)


def relevant(lead: dict, articles: list[dict]) -> bool:
    """The lead headline is tech news, and at most half the outlets frame it as market / off-topic news."""
    off = sum(1 for a in articles if not is_tech(a["title"]))
    return is_tech(lead["title"]) and off * 2 <= len(articles)


def to_tw(text: str) -> str:
    for a, b in TW_TERMS:
        text = text.replace(a, b)
    return text


def translate(text: str) -> str:
    data = fetch_json(TRANSLATE.format(q=urllib.parse.quote(text)))
    out = "".join(seg[0] for seg in (data[0] or []) if seg and seg[0])
    return to_tw(out.strip()) or text


def stories(groups: list[list[dict]], asof: date) -> list[dict]:
    """Verified stories (≥ MIN_SOURCES distinct outlets), most widely reported first."""
    out = []
    for g in cluster(groups):
        g = [a for a in g if a["url"] and (a["date"] is None or asof - timedelta(days=1) <= a["date"] <= asof + timedelta(days=1))]
        lead = next((a for a in g if a["date"]), None)
        if lead is None or not relevant(lead, g):
            continue
        seen: dict[str, dict] = {}
        for a in [lead, *g]:
            k = _source_key(a["source"] or "")
            if k and k not in seen:
                seen[k] = a
        if len(seen) < MIN_SOURCES:
            continue
        links = list(seen.values())
        out.append({"lead": lead, "links": links[:MAX_LINKS], "count": len(seen)})
    out.sort(key=lambda s: (s["count"], s["lead"]["date"]), reverse=True)
    return out


def collect(asof: date, today: date | None = None, notes: list | None = None) -> list[dict]:
    """Up to PER_REGION verified stories each from domestic and international media."""
    today = today or datetime.now(TPE).date()
    items: list[dict] = []
    for region in EDITIONS:
        groups: list[list[dict]] = []
        for u in feed_urls(region, asof, today):
            try:
                groups += parse_feed(fetch_text(u))
            except Exception as e:  # one failed feed should not drop the whole section
                log.warning("tech news feed failed %s: %r", u, e)
        picked = stories(groups, asof)[:PER_REGION]
        if notes is not None and len(picked) < PER_REGION:
            notes.append(f"{region}科技新聞僅 {len(picked)} 則經 {MIN_SOURCES} 家以上媒體報導，未滿 {PER_REGION} 則不補足")
        for s in picked:
            lead = s["lead"]
            title, orig = to_tw(lead["title"]), None
            if len(_CJK.findall(lead["title"])) < len(lead["title"]) * 0.3:
                orig = lead["title"]
                try:
                    title = translate(orig)
                except Exception as e:
                    log.warning("translate failed %r: %r", orig, e)
                    title = orig
            names = "、".join(a["source"] for a in s["links"])
            items.append({
                "region": region,
                "title": title,
                "title_orig": orig,
                "translated": orig is not None and title != orig,
                "summary": f"{s['count']} 家媒體報導：{names}" + ("等" if s["count"] > len(s["links"]) else ""),
                "source": lead["source"],
                "url": lead["url"],
                "date": lead["date"].isoformat(),
                "source_count": s["count"],
                "sources": [{"source": a["source"], "title": a["title"], "url": a["url"]} for a in s["links"]],
            })
    return items
