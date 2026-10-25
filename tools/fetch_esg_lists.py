"""Download official sustainability / governance lists and print them as JSON (run in GitHub Actions).

Sources:
  - 證交所公司治理中心：114年(第十二屆)公司治理評鑑結果 PDF（前5%、6%~20%）
  - 臺灣指數公司：臺灣永續指數 (FTSE4Good TIP Taiwan ESG) 指數頁
  - MoneyDJ：元大臺灣ESG永續ETF(00850，追蹤臺灣永續指數) 全部持股，作為交叉核對
"""
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
CG_PDF = ("https://cgc.twse.com.tw/static/20260430/8a828e179dd8817f019ddd4b86530000_"
          "114年(第十二屆)公司治理評鑑系統評鑑結果暨評鑑程序說明.pdf")


def get(url) -> bytes:
    parts = urllib.parse.urlsplit(url)
    url = urllib.parse.urlunsplit(parts._replace(path=urllib.parse.quote(parts.path)))
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def cg_pdf():
    from pypdf import PdfReader

    raw = get(CG_PDF)
    reader = PdfReader(io.BytesIO(raw))
    print(f"PDF pages={len(reader.pages)} bytes={len(raw)}", file=sys.stderr)
    pages = [p.extract_text() or "" for p in reader.pages]
    for i, t in enumerate(pages):
        print(f"\n----- page {i + 1} -----", file=sys.stderr)
        print(t[:6000], file=sys.stderr)
    return pages


def taiwanindex():
    html = get("https://taiwanindex.com.tw/indexes/F4GTTE").decode("utf-8", "replace")
    print("taiwanindex bytes", len(html), file=sys.stderr)
    for href in sorted(set(re.findall(r'href=["\']([^"\']+)["\']', html))):
        if re.search(r"download|constituent|成分|xls|csv|pdf|F4GTTE", href, re.I):
            print("  link:", href, file=sys.stderr)
    text = re.sub(r"\s+", " ", re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", html, flags=re.S))
    i = text.find("成分股")
    print("  text around 成分股:", text[max(0, i - 300): i + 3000] if i >= 0 else text[:3000], file=sys.stderr)
    for m in re.finditer(r'"(/api/[^"]+|https?://[^"]+api[^"]+)"', html):
        print("  api-ish:", m.group(1), file=sys.stderr)
    return html


def moneydj_00850():
    html = get("https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00850.TW").decode("utf-8", "replace")
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    date = re.search(r"資料日期：(\d{4}/\d{2}/\d{2})", text)
    rows = re.findall(r"([^\s()（）]+)\((\d{4})\.TW\)\s+([\d.]+)", text)
    return {"date": date.group(1) if date else None, "holdings": [{"name": n, "code": c, "weight": float(w)} for n, c, w in rows]}


out = {}
try:
    out["moneydj_00850"] = moneydj_00850()
except Exception as e:  # noqa: BLE001
    out["moneydj_00850"] = {"error": repr(e)}
time.sleep(1)
try:
    taiwanindex()
except Exception as e:  # noqa: BLE001
    print("taiwanindex error", repr(e), file=sys.stderr)
time.sleep(1)
try:
    pages = cg_pdf()
    out["cg_pdf_pages"] = len(pages)
except Exception as e:  # noqa: BLE001
    out["cg_pdf_error"] = repr(e)
print("\n=====JSON=====")
print(json.dumps(out, ensure_ascii=False))
