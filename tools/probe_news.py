"""Live check of headline-derived broker ratings for the current picks (run in GitHub Actions)."""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from screener import news_ratings  # noqa: E402
from screener.net import fetch_json  # noqa: E402

names = set()
for url, key in (("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", "公司簡稱"),
                 ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", "CompanyAbbreviation")):
    names |= {str(r.get(key, "")).strip() for r in fetch_json(url)}
names.discard("")
all_names = tuple(sorted(names))
print("universe names:", len(all_names))

rep = json.loads(Path("docs/data/reports/2026-10-22.json").read_text("utf-8"))
stocks = [(s["code"], s["name"]) for s in rep["pool"][:30]]
summary = {"positive": 0, "negative_only": 0, "neutral": 0, "no_coverage": 0}
from screener.rules import classify_ratings  # noqa: E402

for code, name in stocks:
    rs = news_ratings.ratings_for(code, name, date(2026, 10, 22), all_names)
    st = classify_ratings(rs, date(2026, 10, 22))["status"]
    summary[st] += 1
    print(f"\n== {code} {name}: {st}")
    for r in rs:
        print("  =>", r["broker"], r["rating"], r["target_price"], r["date"], r["source"], "|", r["title"][:80])
print("\nSUMMARY", summary)
