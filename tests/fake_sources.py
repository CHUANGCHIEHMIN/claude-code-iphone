"""Fake TWSE/TPEx/MOPS responses shaped exactly like the live payloads (captured via tools/probe.py)."""
from __future__ import annotations

import re
from datetime import date, timedelta

HOLIDAYS = {date(2026, 10, 9), date(2026, 10, 23)}
TWSE_STOCKS = {  # code: (name, base price, base volume)
    "2330": ("台積電", 1500.0, 30_000_000), "2317": ("鴻海", 230.0, 60_000_000),
    "1101": ("台泥", 28.0, 20_000_000), "2308": ("台達電", 900.0, 8_000_000),
    "0050": ("元大台灣50", 60.0, 50_000_000), "9105": ("泰金寶-DR", 5.0, 1_000_000),
    "2881A": ("富邦特", 60.0, 100_000),
}
TPEX_STOCKS = {"3363": ("上詮", 300.0, 9_000_000), "6488": ("環球晶", 450.0, 3_000_000),
               "00679B": ("元大美債20年", 26.0, 30_000_000)}


def is_trading(d: date) -> bool:
    return d.weekday() < 5 and d not in HOLIDAYS


def _seq(d: date) -> int:
    return (d - date(2026, 9, 1)).days


def price(code, base, d):
    return round(base * (1 + 0.002 * _seq(d)), 2)


def volume(code, base, d):
    # recent days get more volume for 3363 to create a 量增 signal
    boost = 2.0 if code == "3363" and _seq(d) > 45 else 1.0
    return int(base * boost)


def flow(code, d):
    """daily net shares: 外資(不含), 外資自營商, 投信, 自營商."""
    k = {"2330": (3_000_000, 0, 200_000, 100_000), "2317": (-500_000, 0, 1_000_000, 50_000),
         "1101": (2_000_000, 0, 500_000, 0), "2308": (400_000, 1_000, 100_000, -20_000),
         "3363": (800_000, 0, 600_000, 30_000), "6488": (-100_000, 0, 50_000, 0),
         "0050": (9_000_000, 0, 0, 0), "9105": (10_000, 0, 0, 0), "2881A": (1_000, 0, 0, 0),
         "00679B": (500_000, 0, 0, 0)}[code]
    return k


def _comma(n):
    return f"{n:,}"


def fake_fetch_json(url: str):
    m = re.search(r"date=(\d{8})", url) or re.search(r"date=(\d{4})/(\d{2})/(\d{2})", url)
    d = None
    if m:
        s = "".join(m.groups()) if len(m.groups()) > 1 else m.group(1)
        d = date(int(s[:4]), int(s[4:6]), int(s[6:]))
    if "openapi" in url:
        rows = [{"公司代號": c, "產業別": ind} for c, ind in
                [("2330", "半導體業"), ("2317", "其他電子業"), ("1101", "水泥工業"), ("2308", "電子零組件業"),
                 ("3363", "通信網路業"), ("6488", "半導體業")]]
        return rows
    if d and not is_trading(d):
        if "tpex" in url:
            return {"date": d.strftime("%Y%m%d"), "stat": "ok", "tables": [{"fields": ["代號"], "data": []}]}
        return {"stat": "很抱歉，沒有符合條件的資料!"}
    if "MI_INDEX" in url:
        fields = ["證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額", "開盤價", "最高價", "最低價", "收盤價",
                  "漲跌(+/-)", "漲跌價差", "最後揭示買價", "最後揭示買量", "最後揭示賣價", "最後揭示賣量", "本益比"]
        data = []
        for c, (n, p, v) in TWSE_STOCKS.items():
            px, vol = price(c, p, d), volume(c, v, d)
            data.append([c, n, _comma(vol), "1", _comma(int(vol * px)), "", "", "", f"{px:.2f}",
                         "<p style= color:red>+</p>", "1.00", "", "", "", "", "20.50"])
        return {"stat": "OK", "date": d.strftime("%Y%m%d"),
                "tables": [{"title": "價格指數", "fields": ["指數", "收盤指數"], "data": [["x", "1"]]},
                           {"title": "每日收盤行情", "fields": fields, "data": data}, {}]}
    if "T86" in url:
        fields = ["證券代號", "證券名稱", "外陸資買進股數(不含外資自營商)", "外陸資賣出股數(不含外資自營商)",
                  "外陸資買賣超股數(不含外資自營商)", "外資自營商買進股數", "外資自營商賣出股數", "外資自營商買賣超股數",
                  "投信買進股數", "投信賣出股數", "投信買賣超股數", "自營商買賣超股數", "自營商買進股數(自行買賣)",
                  "自營商賣出股數(自行買賣)", "自營商買賣超股數(自行買賣)", "自營商買進股數(避險)",
                  "自營商賣出股數(避險)", "自營商買賣超股數(避險)", "三大法人買賣超股數"]
        data = []
        for c, (n, _, _) in TWSE_STOCKS.items():
            f, fd, t, dl = flow(c, d)
            data.append([c, n + "    ", "0", "0", _comma(f), "0", "0", _comma(fd), "0", "0", _comma(t), _comma(dl),
                         "0", "0", "0", "0", "0", "0", _comma(f + fd + t + dl)])
        return {"stat": "OK", "date": d.strftime("%Y%m%d"), "fields": fields, "data": data}
    if "MI_QFIIS" in url:
        fields = ["證券代號", "證券名稱", "國際證券編碼", "發行股數", "外資及陸資尚可投資股數", "全體外資及陸資持有股數",
                  "外資及陸資尚可投資比率", "全體外資及陸資持股比率", "外資及陸資共用法令投資上限比率"]
        data = [[c, n, "", "", "", "", 50.0, round(40 + 0.01 * _seq(d), 2), "100.00"] for c, (n, _, _) in TWSE_STOCKS.items()]
        return {"stat": "OK", "fields": fields, "data": data}
    if "MI_MARGN" in url:
        fields = ["代號", "名稱", "買進", "賣出", "現金償還", "前日餘額", "今日餘額", "次一營業日限額",
                  "買進", "賣出", "現券償還", "前日餘額", "今日餘額", "次一營業日限額", "資券互抵", "註記"]
        data = [[c, n, "0", "0", "0", _comma(10_000 + 10 * _seq(d) - 10), _comma(10_000 + 10 * _seq(d)), "0",
                 "0", "0", "0", "5", "5", "0", "0", ""] for c, (n, _, _) in TWSE_STOCKS.items()]
        return {"stat": "OK", "tables": [{"title": "信用交易統計", "fields": ["項目", "買進", "前日餘額", "今日餘額"],
                                          "data": [["融資", "1", "1", "1"]]},
                                         {"title": "融資融券彙總", "fields": fields, "data": data}]}
    if "BWIBBU" in url:
        fields = ["證券代號", "證券名稱", "收盤價", "殖利率(%)", "股利年度", "本益比", "股價淨值比", "財報年/季"]
        return {"stat": "OK", "fields": fields, "data": [["2330", "台積電", "1", "1", 114, "25.10", "1", ""],
                                                          ["1101", "台泥", "1", "1", 114, "-", "1", ""]]}
    ds = d.strftime("%Y%m%d") if d else ""
    if "insti/dailyTrade" in url:
        data = []
        for c, (n, _, _) in TPEX_STOCKS.items():
            f, fd, t, dl = flow(c, d)
            row = [c, n] + ["0", "0", _comma(f), "0", "0", _comma(fd), "0", "0", _comma(f + fd), "0", "0", _comma(t),
                            "0", "0", "0", "0", "0", _comma(dl), "0", "0", _comma(dl), _comma(f + fd + t + dl)]
            data.append(row)
        fields = ["代號", "名稱"] + ["買進股數", "賣出股數", "買賣超股數"] * 7 + ["三大法人買賣超股數合計"]
        return {"date": ds, "stat": "ok", "tables": [{"title": "三大法人買賣明細資訊", "fields": fields, "data": data}, {}]}
    if "dailyQuotes" in url:
        fields = ["代號", "名稱", "收盤", "漲跌", "開盤", "最高", "最低", "均價", "成交股數", "成交金額(元)", "成交筆數"]
        data = []
        for c, (n, p, v) in TPEX_STOCKS.items():
            px, vol = price(c, p, d), volume(c, v, d)
            data.append([c, n, f"{px:.2f}", "+0.50 ", "", "", "", "", _comma(vol), _comma(int(vol * px)), "1"])
        return {"date": ds, "stat": "ok", "tables": [{"title": "上櫃股票行情", "fields": fields, "data": data}]}
    if "insti/qfii" in url:
        fields = ["排行", "代號", "名稱", "發行股數(A)", "僑外資及陸資尚可投資股數B=A*F-C", "僑外資及陸資持有股數(C)",
                  "僑外資及陸資尚可投資比率(D=B/A)", "僑外資及陸資持股比率(E=C/A)", "法令投資上限比率(F)", "備註"]
        data = [["1", c, n, "", "", "", "50%", f"{20 + 0.02 * _seq(d):.2f}%", "100%", ""] for c, (n, _, _) in TPEX_STOCKS.items()]
        return {"date": ds, "stat": "ok", "tables": [{"fields": fields, "data": data}]}
    if "margin/balance" in url:
        fields = ["代號", "名稱", "前資餘額(張)", "資買", "資賣", "現償", "資餘額", "資屬證金"]
        data = [[c, n, _comma(5000 - 5 * _seq(d) + 5), "0", "0", "0", _comma(5000 - 5 * _seq(d)), "0"]
                for c, (n, _, _) in TPEX_STOCKS.items()]
        return {"date": ds, "stat": "ok", "tables": [{"fields": fields, "data": data}]}
    if "peQryDate" in url:
        fields = ["股票代號", "公司名稱", "本益比", "每股股利"]
        return {"date": ds, "stat": "ok", "tables": [{"fields": fields, "data": [["3363", "上詮    ", "45.20", "1"]]}]}
    raise AssertionError(f"unexpected url {url}")


def fake_fetch_text(url: str) -> str:
    m = re.search(r"t21sc03_(\d+)_(\d+)_(\d)", url)
    roc, month, kind = map(int, m.groups())
    if kind == 1 or month >= 10:
        return "<html></html>"
    rows = []
    # 2330 / 3363 always positive YoY; 1101 negative in month 8; 2317 positive
    yoy = {"2330": 30.5, "2317": 12.0, "1101": -3.0 if month == 8 else 5.0, "2308": 18.0, "3363": 40.0,
           "6488": -10.0}
    for i in range(520):  # filler so the month counts as "published"
        yoy.setdefault(f"{7000 + i}", 1.0)
    for c, y in yoy.items():
        rows.append(f"<tr align=right><td align=center>{c}</td><td align=left>名稱</td><td nowrap>  1,000</td>"
                    f"<td nowrap>900</td><td nowrap>800</td><td nowrap>1.0</td><Td nowrap>  {y:.2f}</td>"
                    f"<td nowrap>9,000</td><td nowrap>8,000</td><td nowrap>12.5</td><td align=center>-</td></tr>")
    return "<html><table>" + "".join(rows) + "</table></html>"
