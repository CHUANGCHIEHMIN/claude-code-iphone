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


TIER = re.compile(r"【評鑑結果列為\s*(.+?)，計\s*(\d+)\s*家(.*?)】")
SECTION = re.compile(r"^\s*([一二三四五六七八九十]+)、(.+?)\s*$")
CODE = re.compile(r"(?<![\d.])(\d{4})(?![\d.])\s+\S")


def cg_pdf():
    """Parse the evaluation PDF into {section: {tier: {"expected": n, "codes": [...]}}}."""
    from pypdf import PdfReader

    raw = get(CG_PDF)
    reader = PdfReader(io.BytesIO(raw))
    pages = [p.extract_text() or "" for p in reader.pages]
    result, section, tier = {}, "（未分節）", None
    for pno, text in enumerate(pages, 1):
        for line in text.splitlines():
            m = SECTION.match(line)
            if m and len(m.group(2)) < 40 and "家" not in m.group(2):
                section = f"{m.group(1)}、{m.group(2)}"
                tier = None
                continue
            m = TIER.search(line)
            if m:
                tier = m.group(1).replace(" ", "")
                result.setdefault(section, {})[tier] = {"expected": int(m.group(2)), "scope": m.group(3).strip(),
                                                        "page": pno, "codes": []}
                continue
            if tier and "代號" not in line:
                result[section][tier]["codes"] += CODE.findall(line)
    for sec, tiers in result.items():
        for t, v in tiers.items():
            v["codes"] = sorted(set(v["codes"]))
            v["ok"] = len(v["codes"]) == v["expected"]
            print(f"[{sec}] {t}: expected {v['expected']} parsed {len(v['codes'])} p{v['page']} {v['scope']}",
                  file=sys.stderr)
    # print pages before the first tier for context (method notes / headings)
    for pno in range(1, len(pages) + 1):
        if "前5%" in pages[pno - 1] or "前 5%" in pages[pno - 1]:
            print(f"\n----- page {pno} (mentions 前5%) -----\n{pages[pno - 1][:1500]}", file=sys.stderr)
    return result


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


def taiwanindex_files():
    """Download the 臺灣永續指數 files linked from its official page and pull out stock codes."""
    out = {}
    for fid in (198, 483):
        url = f"https://backend.taiwanindex.com.tw/api/downloadFile/IndexFiles/{fid}/tw"
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                raw, cd, ct = r.read(), r.headers.get("Content-Disposition", ""), r.headers.get("Content-Type", "")
        except Exception as e:  # noqa: BLE001
            out[fid] = {"error": repr(e)}
            continue
        name = urllib.parse.unquote(cd)
        text = ""
        if raw[:4] == b"%PDF":
            from pypdf import PdfReader
            text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(raw)).pages)
        elif raw[:2] == b"PK":
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            rows = []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    rows.append(" | ".join("" if v is None else str(v) for v in row))
            text = "\n".join(rows)
        else:
            text = raw.decode("utf-8", "replace")
        print(f"\n----- taiwanindex file {fid}: {name} {ct} {len(raw)} bytes -----\n{text[:2500]}", file=sys.stderr)
        codes = sorted(set(re.findall(r"(?<![\d.])(\d{4})(?![\d.%])", text)))
        out[fid] = {"name": name, "bytes": len(raw), "codes": codes}
    return out


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
    out["taiwanindex_files"] = taiwanindex_files()
except Exception as e:  # noqa: BLE001
    out["taiwanindex_error"] = repr(e)
try:
    out["cg"] = cg_pdf()
except Exception as e:  # noqa: BLE001
    out["cg_error"] = repr(e)
print("\n=====JSON=====")
print(json.dumps(out, ensure_ascii=False))
