"""Probe where official sustainability / governance lists can be downloaded (run in GitHub Actions)."""
import json
import re
import sys
import time
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
KEY = re.compile(r"治理|評鑑|永續|ESG|FTSE4Good|Sustainab|governance", re.I)


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        raw = r.read()
        ctype = r.headers.get("Content-Type", "")
    for enc in ("utf-8", "cp950"):
        try:
            return raw.decode(enc), ctype, len(raw)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace"), ctype, len(raw)


def links(html, base=""):
    out = []
    for href, text in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.S | re.I):
        t = re.sub(r"<[^>]+>|\s+", " ", text).strip()
        if KEY.search(t) or KEY.search(href) or href.lower().endswith((".pdf", ".xls", ".xlsx", ".csv")):
            out.append((t[:80], href))
    return out


def show(name, url, mode="links"):
    print(f"\n===== {name}\n{url}")
    try:
        txt, ctype, n = get(url)
    except Exception as e:  # noqa: BLE001
        print("ERROR", repr(e))
        return None
    print("ctype", ctype, "bytes", n)
    if mode == "swagger":
        js = json.loads(txt)
        for path, ops in js.get("paths", {}).items():
            for op in ops.values():
                s = f"{op.get('summary', '')} {op.get('description', '')} {' '.join(op.get('tags', []))}"
                if KEY.search(s) or KEY.search(path):
                    print("  ", path, "|", s.strip()[:150])
    elif mode == "links":
        for t, h in links(txt)[:80]:
            print("  ", t, "->", h)
    elif mode == "raw":
        print(txt[:3000])
    elif mode == "codes":
        rows = re.findall(r"(?<![\d.])([1-9]\d{3})(?![\d.,%])", re.sub(r"<[^>]+>", " ", txt))
        print("  4-digit tokens:", len(rows), sorted(set(rows))[:400])
        print(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", txt))[:4000])
    time.sleep(1.5)
    return txt


show("twse openapi swagger", "https://openapi.twse.com.tw/v1/swagger.json", "swagger")
show("tpex openapi swagger", "https://www.tpex.org.tw/openapi/swagger.json", "swagger")
show("cgc home", "https://cgc.twse.com.tw/")
show("cgc eval", "https://cgc.twse.com.tw/evaluationCorp/listCh")
show("taiwanindex home", "https://taiwanindex.com.tw/")
show("taiwanindex index list", "https://taiwanindex.com.tw/indexes")
show("moneydj 00850 holdings", "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00850.TW", "codes")
show("yuanta 00850", "https://www.yuantaetfs.com/product/detail/00850/ratio", "raw")
for extra in sys.argv[1:]:
    show("extra", extra, "codes")
