import json
from datetime import date

import pytest

from screener import net, news_ratings, pipeline, report, research, rules, sources
from tests import fake_sources as fk


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(sources, "fetch_json", fk.fake_fetch_json)
    monkeypatch.setattr(sources, "fetch_text", fk.fake_fetch_text)
    monkeypatch.setattr(news_ratings, "fetch_text", fk.fake_rss)
    monkeypatch.setattr(net, "MIN_INTERVAL", {})
    monkeypatch.setenv("SCREENER_NO_LLM", "1")
    monkeypatch.setattr(rules, "load_sustainability",
                        lambda: {"臺灣永續指數成分股": {"codes": ["2330", "3363", "2308"]}})


def test_common_stock_filter():
    assert rules.is_common_stock("2330", "台積電")
    assert not rules.is_common_stock("0050", "元大台灣50")
    assert not rules.is_common_stock("9105", "泰金寶-DR")
    assert not rules.is_common_stock("2881A", "富邦特")
    assert not rules.is_common_stock("00679B", "元大美債20年")
    assert not rules.is_common_stock("030001", "權證")


def test_rating_classification():
    r = rules.classify_ratings([
        {"broker": "大摩 Morgan Stanley", "rating": "Overweight", "date": "2026-10-01"},
        {"broker": "高盛", "rating": "Underperform（劣於大盤）", "date": "2026-09-15"},
        {"broker": "野村", "rating": "Buy", "date": "2026-10-01"},          # 非指定券商
        {"broker": "J.P. Morgan", "rating": "Overweight", "date": "2026-05-01"},  # 超過3個月
    ], date(2026, 10, 22))
    assert r["status"] == "positive"
    assert [x["broker"] for x in r["ratings"]] == ["Morgan Stanley", "Goldman Sachs"]
    assert r["ratings"][1]["polarity"] == "negative"
    neg = rules.classify_ratings([{"broker": "BofA", "rating": "Underweight", "date": "2026-10-20"}], date(2026, 10, 22))
    assert neg["status"] == "negative_only"


def test_full_pipeline(tmp_path):
    rep = pipeline.run(date(2026, 10, 24), tmp_path)
    # 10/23 is a holiday in the fake calendar → latest trading day is 10/22
    assert rep["asof"] == "2026-10-22"
    assert rep["window"] == ["2026-10-16", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"]
    codes = [s["code"] for s in rep["pool"]]
    assert "6488" not in codes  # net seller excluded from 買超 pool
    assert "0050" not in codes and "9105" not in codes and "2881A" not in codes and "00679B" not in codes
    by = {s["code"]: s for s in rep["pool"]}

    # 5-day amount = Σ daily net shares × daily close
    days = [date.fromisoformat(x) for x in rep["window"]]
    exp = sum(sum(fk.flow("2330", d)) * fk.price("2330", 1500.0, d) for d in days)
    assert by["2330"]["net_amt"] == pytest.approx(exp)
    exp_f = sum((fk.flow("2330", d)[0] + fk.flow("2330", d)[1]) * fk.price("2330", 1500.0, d) for d in days)
    assert by["2330"]["foreign_amt"] == pytest.approx(exp_f)
    assert codes[0] == "2330"  # largest amount

    # 3363 volume doubled over recent days → ratio > 1.2
    assert by["3363"]["vol_ratio"] > 1.2
    assert by["2330"]["vol_ratio"] == pytest.approx(1.0)
    assert by["3363"]["pe"] == 45.2 and by["2330"]["pe"] == 25.1
    assert by["2330"]["qfii_chg5"] == pytest.approx(0.01 * 7, abs=1e-6)  # 10/15 → 10/22 = 7 calendar days
    assert by["2330"]["margin_chg5"] == pytest.approx(10 * (fk._seq(days[-1]) - fk._seq(days[0]) + 1))
    assert by["2330"]["industry"] == "半導體業"

    # conditions
    assert by["2330"]["B"]["pass"] is True and "先進製程與先進封裝" in by["2330"]["B"]["themes"]
    assert by["1101"]["B"]["pass"] is False   # 非成長主題且8月營收年減
    assert by["1101"]["A"]["pass"] is None
    assert by["2330"]["A"]["basis"] == "臺灣永續指數成分股"
    # condition C from headlines: newest Morgan Stanley headline wins, vague headline ignored
    c = by["2330"]["C"]
    assert c["status"] == "positive" and len(c["ratings"]) == 1
    assert c["ratings"][0]["target_price"] == 1800 and c["ratings"][0]["date"] == "2026-10-15"
    assert by["1101"]["C"]["status"] == "negative_only"
    assert by["2308"]["C"]["status"] == "no_coverage"
    picks = [s["code"] for s in rep["picks"]]
    assert set(picks) == {"2330", "3363", "2308"}
    assert picks[0] == "3363"  # sorted by volume ratio
    assert rep["picks"][0]["volume_up"] is True
    assert "1101" not in picks and "A永續未能查證" in by["1101"]["reasons"]

    md = report.render(rep)
    assert "## 2. 精選表" in md and "3363" in md and "## Sources" in md
    json.dumps(rep, ensure_ascii=False)


def test_research_json_parsing():
    assert research._parse_json('前言\n```json\n{"a": 1}\n```') == {"a": 1}
    assert research._parse_json('{"a": {"b": 2}}') == {"a": {"b": 2}}
    assert research._parse_json("no json") is None


def test_research_handles_pause_turn_and_collects_urls(monkeypatch):
    from types import SimpleNamespace as NS

    calls = []
    responses = [
        NS(stop_reason="pause_turn", content=[
            NS(type="web_search_tool_result", content=[NS(title="t1", url="https://a.example/1")])]),
        NS(stop_reason="end_turn", content=[
            NS(type="text", text='```json\n{"sustainability": {"pass": true}, "ratings": [], "news": []}\n```')]),
    ]

    class FakeMessages:
        def create(self, **kw):
            calls.append(kw)
            return responses[len(calls) - 1]

    monkeypatch.setattr(research, "_client", lambda: NS(beta=NS(messages=FakeMessages())))
    out = research.research_stock("2330", "台積電", "上市", "半導體業", date(2026, 10, 22))
    assert out["sustainability"]["pass"] is True
    assert out["searched"] == [{"title": "t1", "url": "https://a.example/1"}]
    assert len(calls) == 2 and calls[1]["messages"][1]["role"] == "assistant"
    assert calls[0]["tools"][0]["type"] == "web_search_20260209"
    assert calls[0]["fallbacks"] == "default"


def test_fetch_retries_incomplete_read(monkeypatch):
    import http.client

    calls = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            calls.append(1)
            if len(calls) == 1:
                raise http.client.IncompleteRead(b"partial")
            return b'{"ok": true}'

    monkeypatch.setattr(net.urllib.request, "urlopen", lambda req, timeout: Resp())
    monkeypatch.setattr(net.time, "sleep", lambda s: None)
    assert net.fetch_json("https://www.tpex.org.tw/x") == {"ok": True}
    assert len(calls) == 2


def test_missing_tpex_day_is_noted(monkeypatch, tmp_path):
    real = fk.fake_fetch_json

    def flaky(url):
        if "dailyQuotes" in url and "2026/10/16" in url:
            raise RuntimeError("fetch failed")
        return real(url)

    monkeypatch.setattr(sources, "fetch_json", flaky)
    rep = pipeline.run(date(2026, 10, 24), tmp_path)
    assert any("2026-10-16 上櫃收盤行情取得失敗" in n for n in rep["notes"])


def test_headline_extraction():
    names = ("長榮", "長榮航", "鴻海", "廣達", "台積電", "緯創", "英業達", "緯穎")
    assert news_ratings.extract("小摩將鴻海評等從中立調升至加碼，目標價上看300元", "鴻海", names) == \
        {"broker": "J.P. Morgan", "rating": "加碼", "target_price": 300.0}
    assert news_ratings.extract("美銀降評廣達至劣於大盤 目標價從350元下修至280元", "廣達", names)["rating"] == "劣於大盤"
    assert news_ratings.extract("高盛喊進長榮航 目標價60元", "長榮", names) is None      # 長榮航 is a different stock
    assert news_ratings.extract("高盛喊進長榮 目標價260元", "長榮", names)["target_price"] == 260.0
    assert news_ratings.extract("大摩看好台積電、聯發科", "台積電", names) is None     # no rating / target price
    assert news_ratings.extract("外資喊進鴻海", "鴻海", names) is None                 # not one of the 4 brokers
    # list headlines naming several stocks are not attributed to any of them
    assert news_ratings.extract("目標價1次看》鴻海、廣達、英業達、緯創 高盛完整評：這家強力買、1檔喊賣出", "廣達", names) is None
    assert news_ratings.extract("18家台廠高盛喊「買進」 鴻海、緯穎、緯創入列", "鴻海", names) is None
    # target price written before 目標價; the share price after it is ignored
    assert news_ratings.extract("高盛列「首選」喊400元目標價！鴻海254元還能漲近6成？", "鴻海", names)["target_price"] == 400.0
    assert news_ratings.extract("美銀喊「台積電估值太便宜」 目標價升至3,260元", "台積電", names)["target_price"] == 3260.0
    assert news_ratings.extract("高盛調升台積電目標價至 3300 元 凸顯全球半導體龍頭價值", "台積電", names)["target_price"] == 3300.0
    assert news_ratings.extract("緯創 AI 伺服器出貨翻倍，美銀喊目標價 265 元", "緯創", names)["target_price"] == 265.0
    assert news_ratings.extract("最新宣布！台積電(2330)受惠AI基建爆發，小摩給予優於大盤評級", "台積電", names)["rating"] == "優於大盤"
