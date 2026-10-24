"""Fetchers for official TWSE / TPEx / MOPS data. Each returns plain dicts keyed by stock code."""
from __future__ import annotations

import logging
import re
from datetime import date
from functools import lru_cache

from .net import fetch_json, fetch_text
from .tables import col, extract_tables, find_table, norm, num

log = logging.getLogger(__name__)

TWSE = "https://www.twse.com.tw/rwd/zh"
TPEX = "https://www.tpex.org.tw/www/zh-tw"


def ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def slash(d: date) -> str:
    return d.strftime("%Y/%m/%d")


def _tpex_date_ok(js, d: date) -> bool:
    """TPEx silently falls back to the latest available day; make sure it answered for `d`."""
    got = str(js.get("date", "")) if isinstance(js, dict) else ""
    return got.replace("/", "") in ("", ymd(d))


# ---------------------------------------------------------------- daily quotes
def twse_quotes(d: date) -> dict[str, dict]:
    js = fetch_json(f"{TWSE}/afterTrading/MI_INDEX?date={ymd(d)}&type=ALLBUT0999&response=json")
    t = find_table(extract_tables(js), "證券代號", "收盤價")
    if not t:
        return {}
    f = t.fields
    ic, iname = col(f, "證券代號"), col(f, "證券名稱")
    ivol, ival, iclose = col(f, "成交股數"), col(f, "成交金額"), col(f, "收盤價")
    isign, idiff, ipe = col(f, "漲跌(+/-)"), col(f, "漲跌價差"), col(f, "本益比")
    out = {}
    for r in t.data:
        code = norm(r[ic])
        diff = num(r[idiff]) if idiff is not None else None
        if diff is not None and isign is not None and "-" in norm(r[isign]):
            diff = -diff
        out[code] = {
            "name": norm(r[iname]), "close": num(r[iclose]), "volume": num(r[ivol]) or 0.0,
            "value": num(r[ival]) or 0.0, "diff": diff,
            "pe": num(r[ipe]) if ipe is not None else None,
        }
    return out


def tpex_quotes(d: date) -> dict[str, dict]:
    js = fetch_json(f"{TPEX}/afterTrading/dailyQuotes?date={slash(d)}&type=EW&response=json")
    if not _tpex_date_ok(js, d):
        return {}
    t = find_table(extract_tables(js), "代號", "收盤", "成交股數")
    if not t:
        return {}
    f = t.fields
    ic, iname, iclose, idiff = col(f, "代號"), col(f, "名稱"), col(f, "收盤"), col(f, "漲跌")
    ivol, ival = col(f, "成交股數"), col(f, "成交金額")
    out = {}
    for r in t.data:
        out[norm(r[ic])] = {
            "name": norm(r[iname]), "close": num(r[iclose]), "volume": num(r[ivol]) or 0.0,
            "value": num(r[ival]) or 0.0, "diff": num(r[idiff]), "pe": None,
        }
    return out


# ------------------------------------------------------ institutional investors
@lru_cache(maxsize=32)
def twse_insti(d: date) -> dict[str, dict]:
    js = fetch_json(f"{TWSE}/fund/T86?date={ymd(d)}&selectType=ALLBUT0999&response=json")
    t = find_table(extract_tables(js), "證券代號", "三大法人")
    if not t:
        return {}
    f = t.fields
    ic, iname = col(f, "證券代號"), col(f, "證券名稱")
    ifor = col(f, "外陸資買賣超")
    ifdealer = col(f, "外資自營商買賣超")
    itrust = col(f, "投信買賣超")
    idealer = col(f, "自營商買賣超股數", exclude=("外資", "自行", "避險"))
    itotal = col(f, "三大法人買賣超")
    out = {}
    for r in t.data:
        foreign = num(r[ifor]) or 0.0
        out[norm(r[ic])] = {
            "name": norm(r[iname]),
            "foreign": foreign,                       # 外資及陸資（不含外資自營商）
            "foreign_dealer": num(r[ifdealer]) or 0.0 if ifdealer is not None else 0.0,
            "trust": num(r[itrust]) or 0.0,
            "dealer": num(r[idealer]) or 0.0 if idealer is not None else 0.0,
            "total": num(r[itotal]) or 0.0,
        }
    return out


# TPEx 三大法人 table repeats 買進/賣出/買賣超 headers; the group order is fixed:
# 外資及陸資(不含外資自營商) | 外資自營商 | 外資及陸資合計 | 投信 | 自營商(自行) | 自營商(避險) | 自營商合計 | 三大法人合計
TPEX_INSTI_IDX = {"foreign": 4, "foreign_dealer": 7, "foreign_all": 10, "trust": 13, "dealer": 22, "total": 23}


@lru_cache(maxsize=32)
def tpex_insti(d: date) -> dict[str, dict]:
    js = fetch_json(f"{TPEX}/insti/dailyTrade?type=Daily&sect=EW&date={slash(d)}&response=json")
    if not _tpex_date_ok(js, d):
        return {}
    t = find_table(extract_tables(js), "代號", "三大法人")
    if not t or len(t.fields) < 24:
        return {}
    X = TPEX_INSTI_IDX
    out, bad = {}, 0
    for r in t.data:
        v = {k: num(r[i]) or 0.0 for k, i in X.items()}
        if abs(v["foreign"] + v["foreign_dealer"] - v["foreign_all"]) > 1 or \
                abs(v["foreign_all"] + v["trust"] + v["dealer"] - v["total"]) > 1:
            bad += 1
        out[norm(r[0])] = {"name": norm(r[1]), **v}
    if bad:
        log.warning("TPEx 三大法人欄位檢核不一致 %d/%d 筆 (%s)", bad, len(out), d)
    return out


# ------------------------------------------------------------ foreign holdings
def twse_qfii(d: date) -> dict[str, float]:
    js = fetch_json(f"{TWSE}/fund/MI_QFIIS?date={ymd(d)}&selectType=ALLBUT0999&response=json")
    t = find_table(extract_tables(js), "證券代號", "持股比率")
    if not t:
        return {}
    ic = col(t.fields, "證券代號")
    ir = col(t.fields, "全體外資", "持股比率") or col(t.fields, "持股比率", exclude=("尚可", "上限"))
    return {norm(r[ic]): num(r[ir]) for r in t.data if num(r[ir]) is not None}


def tpex_qfii(d: date) -> dict[str, float]:
    js = fetch_json(f"{TPEX}/insti/qfii?date={slash(d)}&response=json")
    if not _tpex_date_ok(js, d):
        return {}
    t = find_table(extract_tables(js), "代號", "持股比率")
    if not t:
        return {}
    ic = col(t.fields, "代號")
    ir = col(t.fields, "持股比率", exclude=("尚可",))
    return {norm(r[ic]): num(r[ir]) for r in t.data if num(r[ir]) is not None}


# ------------------------------------------------------------- margin balances
def twse_margin(d: date) -> dict[str, dict]:
    js = fetch_json(f"{TWSE}/marginTrading/MI_MARGN?date={ymd(d)}&selectType=ALL&response=json")
    for t in extract_tables(js):
        f = t.fields
        ic = col(f, "代號")
        if ic is None or col(f, "今日餘額") is None:
            continue
        # 融資 block comes first: 買進, 賣出, 現金償還, 前日餘額, 今日餘額, 次一營業日限額, then 融券 block
        iprev, ibal = col(f, "前日餘額"), col(f, "今日餘額")
        return {norm(r[ic]): {"prev": num(r[iprev]), "balance": num(r[ibal])} for r in t.data}
    return {}


def tpex_margin(d: date) -> dict[str, dict]:
    js = fetch_json(f"{TPEX}/margin/balance?date={slash(d)}&response=json")
    if not _tpex_date_ok(js, d):
        return {}
    t = find_table(extract_tables(js), "代號", "資餘額")
    if not t:
        return {}
    f = t.fields
    ic, iprev, ibal = col(f, "代號"), col(f, "前資餘額"), col(f, "資餘額", exclude=("前",))
    return {norm(r[ic]): {"prev": num(r[iprev]), "balance": num(r[ibal])} for r in t.data}


# -------------------------------------------------------------------- P/E ratio
def twse_pe(d: date) -> dict[str, float]:
    js = fetch_json(f"{TWSE}/afterTrading/BWIBBU_d?date={ymd(d)}&selectType=ALL&response=json")
    t = find_table(extract_tables(js), "證券代號", "本益比")
    if not t:
        return {}
    ic, ipe = col(t.fields, "證券代號"), col(t.fields, "本益比")
    return {norm(r[ic]): num(r[ipe]) for r in t.data if num(r[ipe])}


def tpex_pe(d: date) -> dict[str, float]:
    js = fetch_json(f"{TPEX}/afterTrading/peQryDate?date={slash(d)}&response=json")
    if not _tpex_date_ok(js, d):
        return {}
    t = find_table(extract_tables(js), "代號", "本益比")
    if not t:
        return {}
    ic, ipe = col(t.fields, "代號"), col(t.fields, "本益比")
    return {norm(r[ic]): num(r[ipe]) for r in t.data if num(r[ipe])}


# --------------------------------------------------------- company basic data
def industries() -> dict[str, str]:
    """code -> 產業別名稱 (from the monthly-revenue open data, which carries readable names)."""
    out: dict[str, str] = {}
    for url, kc, ki in (
        ("https://openapi.twse.com.tw/v1/opendata/t187ap05_L", "公司代號", "產業別"),
        ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O", "公司代號", "產業別"),
    ):
        try:
            for r in fetch_json(url):
                out[str(r.get(kc, "")).strip()] = str(r.get(ki, "")).strip()
        except Exception as e:  # noqa: BLE001
            log.warning("industry list failed %s: %r", url, e)
    return out


# ------------------------------------------------------------ monthly revenue
_ROW = re.compile(r"<tr[^>]*>\s*<td[^>]*>\s*(\d{4})\s*</td>\s*<td[^>]*>([^<]*)</td>(.*?)</tr>", re.S | re.I)
_TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)


def mops_revenue(year: int, month: int) -> dict[str, dict]:
    """MOPS 月營收彙總表 (上市 sii + 上櫃 otc, 國內 _0 + 國外 _1). code -> {revenue, yoy}."""
    out: dict[str, dict] = {}
    roc = year - 1911
    for mkt in ("sii", "otc"):
        for kind in (0, 1):
            url = f"https://mopsov.twse.com.tw/nas/t21/{mkt}/t21sc03_{roc}_{month}_{kind}.html"
            try:
                html = fetch_text(url)
            except Exception as e:  # noqa: BLE001
                log.warning("MOPS revenue failed %s: %r", url, e)
                continue
            for code, _name, rest in _ROW.findall(html):
                tds = [norm(x) for x in _TD.findall(rest)]
                if len(tds) >= 5:
                    out[code] = {"revenue": num(tds[0]), "yoy": num(tds[4])}
    return out
