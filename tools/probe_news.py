"""Live check of headline-derived broker ratings for a few large caps (run in GitHub Actions)."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from screener import news_ratings  # noqa: E402

for code, name in [("2330", "台積電"), ("2317", "鴻海"), ("3231", "緯創"), ("2382", "廣達"), ("2454", "聯發科"),
                   ("3443", "創意"), ("2603", "長榮"), ("2412", "中華電"), ("2912", "統一超"), ("2377", "微星")]:
    xml = news_ratings.fetch_text(news_ratings.query_url(name))
    items = news_ratings.parse_rss(xml)
    print(f"\n== {code} {name}: {len(items)} headlines")
    for it in items[:6]:
        print("   ", it["date"], it["source"], "|", it["title"][:80])
    for r in news_ratings.ratings_for(code, name, date(2026, 10, 25), ("長榮航", "長榮鋼", "中華電", "統一超")):
        print("  =>", r["broker"], r["rating"], r["target_price"], r["date"], r["source"], "|", r["title"][:70])
