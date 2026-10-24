"""Probe official TWSE / TPEx / MOPS endpoints and print their response shapes.

Used to verify parser assumptions from a network that can reach the sites
(e.g. GitHub Actions). Usage: python tools/probe.py [YYYYMMDD]
"""
import json
import sys
import time
import urllib.request

D = sys.argv[1] if len(sys.argv) > 1 else "20261022"
ONLY = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
Y, M, DD = D[:4], D[4:6], D[6:]
ROC = f"{int(Y) - 1911}/{M}/{DD}"
SLASH = f"{Y}/{M}/{DD}"
UA = {"User-Agent": "Mozilla/5.0 (tw-chip-screener probe)"}

URLS = [
    ("twse_t86", f"https://www.twse.com.tw/rwd/zh/fund/T86?date={D}&selectType=ALLBUT0999&response=json"),
    ("twse_mi_index", f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={D}&type=ALLBUT0999&response=json"),
    ("twse_qfiis", f"https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?date={D}&selectType=ALLBUT0999&response=json"),
    ("twse_margin", f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={D}&selectType=ALL&response=json"),
    ("twse_bwibbu", f"https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={D}&selectType=ALL&response=json"),
    ("twse_bfi82u", f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?type=day&dayDate={D}&response=json"),
    ("twse_basic", "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"),
    ("twse_rev", "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"),
    ("tpex_3insti_new", f"https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={SLASH}&response=json"),
    ("tpex_3insti_old", f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json&se=EW&t=D&d={ROC}"),
    ("tpex_quotes_new", f"https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?date={SLASH}&type=EW&response=json"),
    ("tpex_quotes_old", f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&o=json&se=EW&d={ROC}"),
    ("tpex_pe_new", f"https://www.tpex.org.tw/www/zh-tw/afterTrading/peQryDate?date={SLASH}&response=json"),
    ("tpex_pe_old", f"https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php?l=zh-tw&o=json&d={ROC}"),
    ("tpex_margin_new", f"https://www.tpex.org.tw/www/zh-tw/margin/balance?date={SLASH}&response=json"),
    ("tpex_margin_old", f"https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&o=json&d={ROC}"),
    ("tpex_qfii_new", f"https://www.tpex.org.tw/www/zh-tw/insti/qfii?date={SLASH}&response=json"),
    ("tpex_qfii_new2", f"https://www.tpex.org.tw/www/zh-tw/insti/qfiiStats?date={SLASH}&response=json"),
    ("tpex_qfii_old", f"https://www.tpex.org.tw/web/stock/3insti/qfii/qfii_result.php?l=zh-tw&o=json&d={ROC}"),
    ("tpex_basic", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"),
    ("tpex_rev", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"),
    ("tpex_qfii_openapi", "https://www.tpex.org.tw/openapi/v1/tpex_3insti_qfii"),
    ("mops_rev_sii", f"https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_{int(Y) - 1911}_9_0.html"),
    ("mops_rev_otc", f"https://mopsov.twse.com.tw/nas/t21/otc/t21sc03_{int(Y) - 1911}_9_0.html"),
]


def short(v, n=400):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return s[:n]


for name, url in URLS:
    if ONLY and name not in ONLY:
        continue
    print(f"\n===== {name}\n{url}")
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            print("status", r.status, "ctype", r.headers.get("Content-Type"), "bytes", len(raw))
    except Exception as e:  # noqa: BLE001
        print("ERROR", repr(e))
        time.sleep(2)
        continue
    if name.startswith("mops"):
        for enc in ("utf-8", "cp950"):
            try:
                txt = raw.decode(enc)
                print("decoded as", enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            txt = raw.decode("cp950", "replace")
        i = txt.find("2330")
        print(txt[:300])
        print("...around 2330:", txt[max(0, i - 600): i + 600] if i >= 0 else "not found")
        i = txt.find("公司代號")
        print("...header:", txt[max(0, i - 200): i + 1500] if i >= 0 else "no header")
        time.sleep(2)
        continue
    try:
        js = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        print("NOT JSON", repr(e), raw[:300])
        time.sleep(2)
        continue
    if isinstance(js, list):
        print("list len", len(js))
        print("first:", short(js[:2], 1500))
    else:
        print("keys", list(js.keys()))
        for k in ("stat", "date", "title", "reportDate", "iTotalRecords", "fields", "params"):
            if k in js:
                print(k, "=", short(js[k], 1500))
        if "data" in js:
            print("data len", len(js["data"]), "first", short(js["data"][:2], 1500))
        if "aaData" in js:
            print("aaData len", len(js["aaData"]), "first", short(js["aaData"][:2], 1500))
        for i, t in enumerate(js.get("tables", []) or []):
            if not isinstance(t, dict):
                continue
            print(f"table[{i}] title={t.get('title')!r} keys={list(t.keys())} rows={len(t.get('data') or [])}")
            print("  fields", short(t.get("fields"), 1500))
            if t.get("groups"):
                print("  groups", short(t.get("groups"), 800))
            print("  first", short((t.get("data") or [])[:3], 2400))
            print("  other", {k: short(v, 300) for k, v in t.items() if k not in ("data", "fields", "title")})
        for k, v in js.items():
            if k.startswith(("data", "fields", "groups")) and k not in ("data", "fields"):
                print(k, short(v, 600))
    time.sleep(2.5)
