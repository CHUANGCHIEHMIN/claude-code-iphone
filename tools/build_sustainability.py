"""Write config/sustainability.json from the JSON printed by tools/fetch_esg_lists.py.

Usage: python tools/build_sustainability.py esg_lists.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_esg_lists_meta import CG_PDF_URL, CG_AS_OF, MONEYDJ_URL  # noqa: E402

data = json.loads(Path(sys.argv[1]).resolve().read_text("utf-8"))
cg = data["cg"]
for sec in ("一、上市公司", "二、上櫃公司"):
    for tier in ("前5%", "6%至20%"):
        v = cg[sec][tier]
        if not v["ok"]:
            sys.exit(f"{sec} {tier}: parsed {len(v['codes'])} codes but PDF says {v['expected']}")

top5 = sorted(set(cg["一、上市公司"]["前5%"]["codes"]) | set(cg["二、上櫃公司"]["前5%"]["codes"]))
top20 = sorted(set(cg["一、上市公司"]["6%至20%"]["codes"]) | set(cg["二、上櫃公司"]["6%至20%"]["codes"]))
etf = data["moneydj_00850"]
tsi = sorted({h["code"] for h in etf["holdings"]})
if len(tsi) < 80:
    sys.exit(f"00850 holdings look incomplete: {len(tsi)}")

out = {
    "_說明": ("永續性（條件A）名單，符合任一即通過。由 tools/fetch_esg_lists.py 下載官方資料、"
             "tools/build_sustainability.py 產生；也可手動增修。臺灣永續指數即 FTSE4Good TIP Taiwan ESG Index"
             "（臺灣指數公司與富時羅素合編），每年6月、12月定期審核，審核後請重新更新。"
             "公司治理評鑑第十二屆為最後一屆，2027年起改為ESG評鑑。MSCI ESG 評級無公開整份名單，需網路研究或手動填入。"),
    "lists": {
        "公司治理評鑑前5%": {
            "source": CG_PDF_URL, "as_of": CG_AS_OF,
            "note": f"上市 {len(cg['一、上市公司']['前5%']['codes'])} 家＋上櫃 {len(cg['二、上櫃公司']['前5%']['codes'])} 家",
            "codes": top5,
        },
        "公司治理評鑑6%~20%": {
            "source": CG_PDF_URL, "as_of": CG_AS_OF,
            "note": f"上市 {len(cg['一、上市公司']['6%至20%']['codes'])} 家＋上櫃 {len(cg['二、上櫃公司']['6%至20%']['codes'])} 家",
            "codes": top20,
        },
        "臺灣永續指數（FTSE4Good TIP Taiwan ESG）成分股": {
            "source": MONEYDJ_URL, "as_of": f"00850持股 {etf['date']}",
            "note": ("臺灣指數公司未公開成分股清單，以追蹤此指數之元大臺灣ESG永續ETF(00850)全部持股代替；"
                     "2026/06/22 定審後指數成分股為113檔，ETF持股可能略少。"),
            "codes": tsi,
        },
        "MSCI ESG評級A以上": {"source": "", "as_of": "", "note": "無公開整份名單", "codes": []},
    },
}
(Path(__file__).resolve().parent.parent / "config" / "sustainability.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", "utf-8")
print(f"前5%: {len(top5)}  6%~20%: {len(top20)}  臺灣永續指數: {len(tsi)}  union: {len(set(top5) | set(top20) | set(tsi))}")
