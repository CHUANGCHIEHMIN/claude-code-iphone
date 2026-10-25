"""Web research via the Claude API (web search tool) for conditions A / B / C and per-stock news.

Only runs when ANTHROPIC_API_KEY (or another Anthropic credential) is configured.
Every fact returned must carry a source URL; the pipeline treats missing data as「—」.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date

log = logging.getLogger(__name__)

MODEL = os.environ.get("SCREENER_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("SCREENER_EFFORT", "medium")
WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search", "max_uses": 8}

SYSTEM = """你是台股研究助理，替一個自動化選股報告查證公開資訊。規則：
- 只能使用本次 web_search 查到的內容，不可憑記憶填寫數字、日期或評等；查不到就填 null 或空陣列。
- 每一筆事實都要附上實際查到的網址（url）與日期。
- 摘要用你自己的話改寫成一句繁體中文，不要大段引用原文。
- 最後只輸出一個 JSON 物件（可放在 ```json 區塊內），不要輸出其他文字。"""

STOCK_PROMPT = """查證台股 {code} {name}（{market}，產業：{industry}）的下列資訊，基準日 {asof}：

1. 永續性（符合任一即可）：最新一屆證交所公司治理評鑑排名前20%（上市前20%或上櫃前20%）；臺灣永續指數、富時台灣ESG（FTSE4Good TIP Taiwan ESG）等永續指數成分股；MSCI ESG 評級 A 以上（A/AA/AAA）。
2. 未來性：是否屬於 AI伺服器／AI晶片、先進製程與先進封裝、矽光子／CPO、散熱、電力與重電／儲能、機器人／自動化、低軌衛星、資安、生技新藥 等成長產業，依公司主要營收或產品判斷。
3. 投行評等：{since} 至 {asof} 之間，J.P. Morgan（摩根大通）、Bank of America Global Research（美銀）、Morgan Stanley（摩根士丹利）、Goldman Sachs（高盛）對此股的評等與目標價（新台幣）。來源限公開新聞報導，例如鉅亨網、經濟日報、工商時報、MoneyDJ、Reuters。正面與負面（減碼／賣出／劣於大盤）都要列出；中立也列出。
4. 近一週（{week_ago} 至 {asof}）與此公司相關的新聞 1–2 則。

輸出 JSON 結構：
{{
  "sustainability": {{"pass": true|false|null, "basis": "符合的項目，如『臺灣永續指數成分股』，無則說明", "evidence": [{{"title": "", "url": "", "date": "YYYY-MM-DD"}}]}},
  "future": {{"pass": true|false, "themes": ["上列主題名稱"], "basis": "一句說明"}},
  "ratings": [{{"broker": "Morgan Stanley", "rating": "Overweight", "target_price": 1234.0, "date": "YYYY-MM-DD", "source": "鉅亨網", "url": ""}}],
  "news": [{{"title": "", "summary": "一句改寫摘要", "source": "", "url": "", "date": "YYYY-MM-DD"}}]
}}"""

def available() -> bool:
    if os.environ.get("SCREENER_NO_LLM"):
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _client():
    import anthropic  # imported lazily so the data pipeline works without the SDK

    return anthropic.Anthropic(max_retries=4, timeout=600)


def _parse_json(text: str) -> dict | None:
    m = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidates = m[::-1] + [text[text.find("{"): text.rfind("}") + 1]] if "{" in text else m[::-1]
    for c in candidates:
        try:
            return json.loads(c)
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _ask(prompt: str) -> tuple[dict | None, list[dict]]:
    """Run one research turn with web search; return (parsed JSON, searched URLs)."""
    import anthropic

    client = _client()
    messages = [{"role": "user", "content": prompt}]
    urls: list[dict] = []
    text = ""
    for _ in range(5):  # pause_turn continuations
        try:
            resp = client.beta.messages.create(
                model=MODEL,
                max_tokens=16000,
                system=SYSTEM,
                tools=[WEB_SEARCH],
                output_config={"effort": EFFORT},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=messages,
            )
        except anthropic.RateLimitError as e:
            log.warning("rate limited: %s", e)
            raise
        except anthropic.APIStatusError as e:
            log.error("Claude API error %s: %s", e.status_code, e.message)
            return None, urls
        except anthropic.APIConnectionError as e:
            log.error("Claude API connection error: %s", e)
            return None, urls
        for b in resp.content:
            if b.type == "web_search_tool_result" and isinstance(b.content, list):
                urls += [{"title": r.title, "url": r.url} for r in b.content if getattr(r, "url", None)]
            elif b.type == "text":
                text += b.text
        if resp.stop_reason == "refusal":
            log.warning("request refused: %s", getattr(resp, "stop_details", None))
            return None, urls
        if resp.stop_reason == "pause_turn":
            messages = [messages[0], {"role": "assistant", "content": resp.content}]
            continue
        break
    return _parse_json(text), urls


def research_stock(code: str, name: str, market: str, industry: str, asof: date) -> dict:
    from datetime import timedelta

    prompt = STOCK_PROMPT.format(
        code=code, name=name, market=market, industry=industry or "—",
        asof=asof.isoformat(), since=(asof - timedelta(days=92)).isoformat(),
        week_ago=(asof - timedelta(days=7)).isoformat(),
    )
    data, urls = _ask(prompt)
    if data is None:
        return {"error": "研究步驟未取得有效回應", "searched": urls}
    data["searched"] = urls[:20]
    return data

