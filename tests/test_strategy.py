import json
from datetime import date

import pytest

from screener import backfill, backtest, history, net, news_ratings, notify, performance, pipeline, portfolio, \
    rules, signals, sources, tech_news
from screener.engine import Engine
from tests import fake_sources as fk


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(sources, "fetch_json", fk.fake_fetch_json)
    monkeypatch.setattr(sources, "fetch_text", fk.fake_fetch_text)
    monkeypatch.setattr(news_ratings, "fetch_text", fk.fake_rss)
    monkeypatch.setattr(tech_news, "fetch_text", fk.fake_tech_rss)
    monkeypatch.setattr(tech_news, "fetch_json", fk.fake_translate)
    monkeypatch.setattr(net, "MIN_INTERVAL", {})
    monkeypatch.setenv("SCREENER_NO_LLM", "1")
    monkeypatch.setenv("SCREENER_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setattr(pipeline, "today_tpe", lambda: date(2026, 10, 23))
    monkeypatch.setattr(rules, "load_sustainability",
                        lambda: {"臺灣永續指數成分股": {"codes": ["2330", "3363", "2308"]}})
    sources.twse_insti.cache_clear()
    sources.tpex_insti.cache_clear()


def P():
    return signals.load_strategy()


def with_pullback(monkeypatch):
    """The fake market has flat volume, so only pullback entries fire there; turn them on for flow tests."""
    p = P()
    p["entry"]["pullback_entry"] = True
    monkeypatch.setattr(signals, "load_strategy", lambda: json.loads(json.dumps(p)))
    return p


def test_history_round_trip(tmp_path):
    st = history.Store(tmp_path / "h")
    d = date(2026, 10, 22)
    tw, tp, twf, tpf = backfill.fetch_day(d)
    assert tw["2330"]["open"] == pytest.approx(fk.price("2330", 1500.0, d) * 0.99, abs=0.01)
    assert st.save(d, tw, tp, twf, tpf) and not st.save(d, tw, tp, twf, tpf)  # written once
    tw2, tp2, twf2, tpf2 = st.load(d)
    assert set(tw2) == {"2330", "2317", "1101", "2308"}  # ETF / DR / 特別股 not stored
    assert set(tp2) == {"3363", "6488"}
    assert tw2["2330"]["close"] == tw["2330"]["close"]
    f = fk.flow("2330", d)
    assert twf2["2330"]["foreign"] == f[0] + f[1] and twf2["2330"]["total"] == sum(f)
    assert not st.save(date(2026, 10, 21), tw, {}, twf, tpf)  # incomplete day refused
    assert st.days() == [d]


def test_backfill_and_backtest(monkeypatch, tmp_path):
    st = history.Store(tmp_path / "h")
    out = backfill.run(date(2026, 9, 1), date(2026, 10, 22), st, 5)
    assert out["remaining"] == 0 and out["saved"] == len(st.days()) > 30
    assert "2026-10-22" in st.taiex() and "2026-10-23" not in st.taiex()  # holiday
    assert st.revenue("2026-08")["2330"] == 30.5
    p = with_pullback(monkeypatch)
    p["backtest"]["split"] = "2026-10-10"
    bt = backtest.run(st, date(2026, 10, 8), date(2026, 10, 22), p, rules.load_themes(),
                      {"l": {"codes": ["2330", "3363", "2308"]}})
    by = {v["key"]: v for v in bt["variants"]}
    assert set(by) == {k for k, _, _ in backtest.VARIANTS}
    base = by["base"]["all"]["h5"]
    assert base["n"] > 0 and base["avg"] > 0  # fake prices rise every day
    assert by["pool50"]["picks_per_day"] >= by["base"]["picks_per_day"]
    full = bt["strategies"][0]
    assert full["all"]["total_return"] > 0 and full["equity_curve"]
    md = backtest.render_md(bt)
    assert "## 2. 策略模擬" in md and "現行規則" in md


def test_entry_signals():
    p = P()
    s = signals.new_series()
    for i in range(30):  # steady uptrend, recent pullback to the 10-day average
        c = 100 + i
        signals.append(s, f"d{i:02d}", {"open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 1000,
                                        "value": c * 1000}, {"foreign": 10, "trust": 5, "total": 15})
    f = signals.features(s, p)
    assert f["ma_up"] and f["buy_days"] == 5 and f["trust_streak"] == 30
    assert f["atr"] == pytest.approx(2.0)
    st, why = signals.entry_signal(f, p)
    assert st == signals.WATCH  # trending but not a volume breakout nor near the 10-day average
    near = {**f, "close": f["ma_pull"] * 1.01}
    assert signals.entry_signal(near, p)[0] == signals.WATCH  # pullback entries are off by default
    p2 = {**p, "entry": {**p["entry"], "pullback_entry": True}}
    assert signals.entry_signal(near, p2)[0] == signals.ENTER
    assert signals.entry_signal(f, p, disposal=True)[0] == signals.EXCLUDED
    assert signals.entry_signal(f, p, attention=True) == (signals.HOT, ["注意股"])
    assert signals.entry_signal(f, p, margin_pct=0.2)[0] == signals.HOT
    f2 = {**f, "breakout": True, "vol_ratio": 1.5}
    assert signals.entry_signal(f2, p)[0] == signals.ENTER
    f3 = {**f, "chg5": 0.2}
    assert signals.entry_signal(f3, p)[0] == signals.HOT
    assert signals.percentile_scores([{"a": 1}, {"a": 3}, {"a": None}], ("a",)) == [50.0, 100.0, 0.0]


def test_engine_entry_stop_and_gap():
    p = P()
    eng = Engine(p)
    eng.plan("d0", [{"code": "A", "name": "甲", "industry": "x", "close": 100, "atr": 2},
                    {"code": "B", "name": "乙", "industry": "x", "close": 50, "atr": 1}], 3)
    assert len(eng.s["orders"]) == 2
    eng.on_open("d1", {"A": {"open": 101}, "B": {"open": 52}})  # B gaps up 4% → skipped
    assert set(eng.s["positions"]) == {"A"} and eng.s["orders"] == []
    pos = eng.s["positions"]["A"]
    assert pos["stop"] == pytest.approx(97.0)  # 101 − 2×2
    # risk 1% of 1,000,000 / 4 per share = 2,500 shares, capped by 1/8 of equity → 1,237 shares
    assert pos["shares"] == 1237
    eng.on_close("d1", {"A": {"open": 101, "high": 102, "low": 100, "close": 101.5}}, {})
    eng.on_close("d2", {"A": {"open": 99, "high": 99, "low": 96, "close": 96.5}}, {})
    assert "A" not in eng.s["positions"]
    t = eng.s["trades"][0]
    assert t["exit"] == 97.0 and t["reason"] == "停損" and t["ret"] < 0
    assert eng.s["cash"] < p["portfolio"]["capital"]


def test_engine_close_based_exits():
    p = P()
    assert p["exit"]["trail_after"] is None  # off by default; checked here with the old setting
    p["exit"]["trail_after"] = 0.10
    eng = Engine(p)
    eng.plan("d0", [{"code": "A", "name": "甲", "close": 100, "atr": 2}], 1)
    eng.on_open("d1", {"A": {"open": 100}})
    eng.on_close("d1", {"A": {"open": 100, "low": 99, "close": 112}}, {"A": {"ma_trail": 105}})
    assert eng.s["exit_orders"] == {}
    eng.on_close("d2", {"A": {"open": 110, "low": 104, "close": 104.5}}, {"A": {"ma_trail": 106}})
    assert eng.s["exit_orders"] == {"A": "trail"}
    eng.on_open("d3", {"A": {"open": 104}})
    assert eng.s["trades"][0]["reason"].startswith("移動停利") and eng.s["trades"][0]["exit"] == 104
    eng2 = Engine(p)
    eng2.plan("d0", [{"code": "A", "name": "甲", "close": 100, "atr": 2}], 1)
    eng2.on_open("d1", {"A": {"open": 100}})
    n = p["exit"]["inst_sell_days"]
    eng2.on_close("d1", {"A": {"open": 100, "low": 99, "close": 101}}, {"A": {"inst_sell_streak": n - 1}})
    assert eng2.s["exit_orders"] == {}
    eng2.on_close("d2", {"A": {"open": 100, "low": 99, "close": 101}}, {"A": {"inst_sell_streak": n}})
    assert eng2.s["exit_orders"] == {"A": "inst"}


def test_engine_breakeven_stop():
    p = P()
    eng = Engine(p)
    eng.plan("d0", [{"code": "A", "name": "甲", "close": 100, "atr": 2}], 1)
    eng.on_open("d1", {"A": {"open": 100}})
    eng.on_close("d1", {"A": {"open": 100, "low": 99, "close": 109}}, {})
    assert eng.s["positions"]["A"]["stop"] == 96.0  # +9%: still the ATR stop
    eng.on_close("d2", {"A": {"open": 109, "low": 108, "close": 111}}, {})
    assert eng.s["positions"]["A"]["stop"] == 100  # closed 10%+ above cost → stop moved to cost
    eng.on_close("d3", {"A": {"open": 104, "low": 99.5, "close": 101}}, {})
    t = eng.s["trades"][0]
    assert t["exit"] == 100 and t["reason"] == "保本停損" and "A" not in eng.s["positions"]


def test_weak_market_blocks_new_entries():
    p = P()
    taiex = {f"2026-{m:02d}-{d:02d}": 100.0 for m in (7, 8, 9) for d in range(1, 29)}
    taiex["2026-09-30"] = 90.0
    reg = signals.regime(taiex, "2026-09-30", p)
    assert reg["state"] == "弱勢" and reg["max_entries"] == 0
    eng = Engine(p)
    assert eng.plan("d0", [{"code": "A", "name": "甲", "close": 100, "atr": 2}], reg["max_entries"]) == []


def test_portfolio_rerun_is_idempotent(monkeypatch, tmp_path):
    with_pullback(monkeypatch)
    out = tmp_path / "data"
    for d in ("2026-10-19", "2026-10-20", "2026-10-21"):
        rep = pipeline.run(date.fromisoformat(d), out)
        (out / "reports").mkdir(parents=True, exist_ok=True)
        (out / "reports" / f"{d}.json").write_text(json.dumps(rep, ensure_ascii=False), "utf-8")
    first = json.loads((out / "portfolio.json").read_text("utf-8"))["state"]
    assert first["last_day"] == "2026-10-21" and first["positions"]  # orders from 10/19 filled on 10/20
    assert all(p["entry_date"] == "2026-10-20" for p in first["positions"].values())
    rep = pipeline.run(date(2026, 10, 21), out)
    again = json.loads((out / "portfolio.json").read_text("utf-8"))["state"]
    assert again["positions"] == first["positions"] and again["cash"] == first["cash"]
    assert len(again["equity"]) == len(first["equity"])
    assert rep["portfolio"]["equity"] > 0 and rep["market"]["regime"]["state"] == "強勢"
    perf = json.loads((out / "performance.json").read_text("utf-8"))
    rows = [r for r in perf["rows"] if r["date"] == "2026-10-19" and r["code"] == "2330"]
    assert rows and rows[0]["entry_date"] == "2026-10-20" and rows[0]["r1"] is not None
    assert perf["groups"][0]["name"] == "全部入選股"
    assert portfolio.load(out / "portfolio.json")["prev"]["last_day"] == "2026-10-20"


def test_disposal_attention_and_new_fields(tmp_path):
    rep = pipeline.run(date(2026, 10, 22), tmp_path)
    by = {s["code"]: s for s in rep["pool"]}
    assert by["1101"]["disposal"] and "處置股" in by["1101"]["reasons"]
    assert by["3363"]["attention"] and by["3363"]["signal"] == signals.HOT
    assert by["2330"]["score"] is not None and by["2330"]["buy_days"] == 5
    assert by["2330"]["tech"]["ma"] is not None
    msg = notify.message(rep, "https://example.github.io/x/")
    assert rep["asof"] in msg and "非投資建議" in msg


def test_performance_groups(tmp_path):
    d = tmp_path / "reports"
    d.mkdir()
    rep = {"asof": "2026-10-01", "picks": [{"code": "A", "name": "甲", "volume_up": True, "score": 80},
                                           {"code": "B", "name": "乙", "volume_up": False, "score": 20}]}
    (d / "2026-10-01.json").write_text(json.dumps(rep), "utf-8")
    prices = {"2026-10-01": {"A": (10, 10), "B": (10, 10)}, "2026-10-02": {"A": (10, 11), "B": (10, 9)}}
    taiex = {"2026-10-01": 100.0, "2026-10-02": 101.0}
    perf = performance.compute(d, prices, taiex, 0.0)
    g = {x["name"]: x for x in perf["groups"]}
    assert g["全部入選股"]["h1"]["n"] == 2 and g["全部入選股"]["h1"]["win_rate"] == 0.5
    assert g["量增（≥1.2）"]["h1"]["avg"] == pytest.approx(0.1)
    assert g["量增（≥1.2）"]["h1"]["excess"] == pytest.approx(0.09)
    assert g["綜合分數前半"]["h1"]["n"] == 1


def test_backfill_retries_cut_off_tpex_download(monkeypatch, tmp_path):
    calls = {"n": 0}
    real = fk.fake_fetch_json

    def flaky(url):
        if "dailyQuotes" in url and "2026/10/22" in url:
            calls["n"] += 1
            if calls["n"] <= 2:  # fails both tries in the first pass, then works in the second pass
                raise RuntimeError("fetch failed: IncompleteRead(712418 bytes read)")
        return real(url)

    monkeypatch.setattr(sources, "fetch_json", flaky)
    st = history.Store(tmp_path / "h")
    out = backfill.run(date(2026, 10, 20), date(2026, 10, 22), st, 5)
    assert out["failed"] == [] and out["remaining"] == 0 and st.has(date(2026, 10, 22))
