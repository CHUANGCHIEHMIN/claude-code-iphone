"""CLI: python -m screener [--date YYYY-MM-DD] [--no-llm] [--out docs]"""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import date
from pathlib import Path

from . import pipeline, report

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser(description="三大法人籌碼 × 永續 × 未來性 選股報告")
    ap.add_argument("--date", help="基準日 YYYY-MM-DD（預設：台北今天；遇休市自動往前找）")
    ap.add_argument("--no-llm", action="store_true", help="不呼叫 Claude API（只跑官方數據步驟）")
    ap.add_argument("--out", default=str(ROOT / "docs"), help="網站輸出目錄（預設 docs/）")
    ap.add_argument("--reindex", action="store_true", help="只重建 data/index.json")
    ap.add_argument("--skip-existing", action="store_true", help="該交易日報告已存在時略過（排程用，避免休市日重複呼叫 API）")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.no_llm:
        os.environ["SCREENER_NO_LLM"] = "1"

    out = Path(args.out)
    if args.reindex:
        reindex(out)
        return
    asof = date.fromisoformat(args.date) if args.date else None
    rep = pipeline.run(asof, out / "data", skip_existing=args.skip_existing)
    if rep is not None:
        write(rep, out)


def write(rep: dict, out: Path) -> None:
    data = out / "data"
    (data / "reports").mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(parents=True, exist_ok=True)
    day = rep["asof"]
    (data / "reports" / f"{day}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), "utf-8")
    (out / "reports" / f"{day}.md").write_text(report.render(rep), "utf-8")
    reindex(out)
    logging.info("wrote report %s (%d picks)", day, rep["summary"]["count"])


def reindex(out: Path) -> None:
    """Rebuild data/index.json from the report files (so concurrent runs never need a merge)."""
    data = out / "data"
    rows = []
    for p in sorted((data / "reports").glob("*.json"), reverse=True):
        r = json.loads(p.read_text("utf-8"))
        rows.append({"date": r["asof"], "count": r["summary"]["count"], "generated_at": r["generated_at"],
                     "research": r["research_enabled"]})
    idx = {"latest": rows[0]["date"] if rows else None, "reports": rows}
    (data / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1), "utf-8")


if __name__ == "__main__":
    main()
