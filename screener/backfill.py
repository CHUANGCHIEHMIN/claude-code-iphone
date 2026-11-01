"""Download past trading days into the history store (for performance tracking and backtests).

python -m screener.backfill --years 3            # 近 3 年，已存在的日期自動略過
python -m screener.backfill --start 2024-01-01 --end 2024-12-31 --max-minutes 300

Order: 加權指數月表（交易日曆）→ 每個交易日的上市／上櫃行情與三大法人（由新到舊）→ 月營收。
About 4 requests per trading day; with the polite rate limit that is ~6 seconds per day.
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import date, timedelta

from . import history, pipeline, sources

log = logging.getLogger(__name__)


def months(start: date, end: date) -> list[date]:
    out, d = [], date(start.year, start.month, 1)
    while d <= end:
        out.append(d)
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return out


def _twice(fn, d: date) -> dict:
    """TPEx sometimes cuts its ~2MB responses short (IncompleteRead) or answers empty; try once more."""
    try:
        got = fn(d)
    except Exception as e:  # noqa: BLE001
        log.warning("%s %s failed once: %r", fn.__name__, d, e)
        got = {}
    return got or fn(d)


def fetch_day(d: date) -> tuple[dict, dict, dict, dict]:
    tw_q = sources.twse_quotes(d)
    tp_q = _twice(sources.tpex_quotes, d)
    tw_f = sources.twse_insti(d)
    tp_f = _twice(sources.tpex_insti, d)
    return tw_q, tp_q, tw_f, tp_f


def run(start: date, end: date, store: history.Store, max_minutes: float = 300) -> dict:
    t0 = time.monotonic()
    budget = lambda: time.monotonic() - t0 < max_minutes * 60  # noqa: E731
    have = store.taiex()
    today = pipeline.today_tpe()
    for m in months(start, end):
        ym = m.strftime("%Y-%m")
        current = (m.year, m.month) == (today.year, today.month)
        if not current and sum(1 for d in have if d.startswith(ym)) >= 15:
            continue
        try:
            got = sources.taiex_month(m)
        except Exception as e:  # noqa: BLE001
            log.warning("TAIEX %s failed: %r", ym, e)
            continue
        store.save_taiex(got)
        log.info("TAIEX %s: %d days", ym, len(got))
    cal = sorted(date.fromisoformat(d) for d in store.taiex() if start.isoformat() <= d <= end.isoformat())
    todo = [d for d in reversed(cal) if not store.has(d)]
    log.info("%d trading days in range, %d to download", len(cal), len(todo))
    saved, failed = 0, []
    todo = todo + todo  # second pass retries the days that failed in the first
    for d in todo:
        if store.has(d):
            continue
        if not budget():
            log.warning("time budget reached; the remaining days are downloaded by the next run")
            break
        try:
            snap = fetch_day(d)
        except Exception as e:  # noqa: BLE001
            log.warning("%s failed: %r", d, e)
            failed.append(d.isoformat())
            continue
        if store.save(d, *snap):
            saved += 1
            log.info("saved %s (%d/%d)", d, saved, len(todo) // 2)
        else:
            failed.append(d.isoformat())
            log.warning("%s incomplete (TWSE %d / TPEx %d quotes, flows %d / %d)", d, *map(len, snap))
    rev_saved = 0
    have_rev = set(store.revenue_months())
    first = date(start.year, start.month, 1) - timedelta(days=120)
    for m in months(first, end):
        ym = m.strftime("%Y-%m")
        published = date(m.year + (m.month == 12), m.month % 12 + 1, 11)
        if ym in have_rev or published > today or not budget():
            continue
        try:
            rev = sources.mops_revenue(m.year, m.month)
        except Exception as e:  # noqa: BLE001
            log.warning("revenue %s failed: %r", ym, e)
            continue
        store.save_revenue(ym, rev)
        rev_saved += 1
    out = {"days_in_range": len(cal), "saved": saved,
           "failed": sorted({d for d in failed if not store.has(date.fromisoformat(d))}),
           "remaining": len([d for d in cal if not store.has(d)]), "revenue_saved": rev_saved}
    log.info("backfill done: %s", out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="回補歷史行情與三大法人資料")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--years", type=float, default=3)
    ap.add_argument("--max-minutes", type=float, default=300)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    end = date.fromisoformat(args.end) if args.end else pipeline.today_tpe()
    start = date.fromisoformat(args.start) if args.start else end - timedelta(days=int(365 * args.years))
    run(start, end, history.Store(), args.max_minutes)


if __name__ == "__main__":
    main()
