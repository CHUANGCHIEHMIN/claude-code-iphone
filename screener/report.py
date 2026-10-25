"""Render the report payload as Markdown (the web UI renders the JSON directly)."""
from __future__ import annotations

DASH = "—"


def yi(v) -> str:
    return DASH if v is None else f"{v / 1e8:+,.2f}億"


def pct(v, digits=1, signed=True) -> str:
    if v is None:
        return DASH
    return f"{v * 100:+.{digits}f}%" if signed else f"{v * 100:.{digits}f}%"


def fnum(v, fmt="{:,.2f}") -> str:
    return DASH if v is None else fmt.format(v)


def mark(v) -> str:
    return {True: "✅", False: "❌", None: "❔"}[v]


C_LABEL = {"positive": "✅ 有正面評等", "negative_only": "❌ 僅負面評等", "neutral": "➖ 僅中立評等",
           "no_coverage": "➖ 無覆蓋／查無公開報導", "not_checked": "❔ 未查證"}


def ratings_text(c: dict) -> str:
    if not c["ratings"]:
        return {"not_checked": "未查證"}.get(c["status"], "無覆蓋／查無公開報導")
    parts = []
    for r in c["ratings"]:
        tp = f"TP {r['target_price']:,.0f}" if isinstance(r.get("target_price"), (int, float)) else "TP —"
        link = f"[{r.get('source') or '來源'}]({url(r.get('url'))})" if url(r.get("url")) else ""
        parts.append(f"{r['broker']}／{r.get('rating') or DASH}／{tp}／{r.get('date') or DASH} {link}")
    return "<br>".join(parts)


def url(u) -> str:
    u = str(u or "")
    return u.replace(" ", "%20").replace(")", "%29") if u.startswith(("http://", "https://")) else ""


def esc(s) -> str:
    return str(s if s is not None else DASH).replace("|", "／").replace("\n", " ")


def render(rep: dict) -> str:
    L = []
    w = rep["window"]
    L.append(f"# 三大法人籌碼選股報告 {rep['asof']}")
    L.append(f"_資料區間：{w[0]} ～ {w[-1]}（近5個交易日）；產出時間：{rep['generated_at']}_\n")

    sm = rep["summary"]
    L.append("## 1. 摘要")
    L.append(f"- **今日入選：{sm['count']} 檔**")
    if sm["top3"]:
        L.append("- **前3名重點：**")
        L += [f"  {i}. {t}" for i, t in enumerate(sm["top3"], 1)]
    L.append(f"- **市場法人動向：** {sm['market_line']}\n")

    L.append("## 2. 精選表（依量增比排序）")
    if not rep["picks"]:
        L.append("今日無個股同時符合所有條件。\n")
    else:
        L.append("| 代號 | 名稱 | 產業 | 收盤 | 5日漲跌 | 5日法人買超 | 外資 | 投信 | 買超/成交值 | 量增比 | 永續依據 | 未來性依據 | 投行評等 | 本益比 | 外資持股5日變化 | 融資5日增減(張) |")
        L.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|---:|---:|")
        for s in rep["picks"]:
            ratio = pct(s["net_ratio"], signed=False) + (" **法人主導**" if s["dominant"] else "")
            vr = fnum(s["vol_ratio"]) + (" **量增**" if s.get("volume_up") else "")
            L.append("| " + " | ".join(esc(x) for x in [
                s["code"], s["name"], s["industry"], fnum(s["close"]), pct(s["chg5"]),
                yi(s["net_amt"]), yi(s["foreign_amt"]), yi(s["trust_amt"]), ratio, vr,
                s["A"]["basis"], s["B"]["basis"], ratings_text(s["C"]), fnum(s["pe"], "{:.1f}"),
                fnum(s["qfii_chg5"], "{:+.2f}pp"), fnum(s["margin_chg5"], "{:+,.0f}"),
            ]) + " |")
        L.append("")

    L.append("## 3. 候選池前20名對照表（依5日買超金額）")
    L.append("| 排名 | 代號 | 名稱 | 5日法人買超 | 買超/成交值 | A永續 | B未來性 | C投行 | 結果 | 未入選原因 |")
    L.append("|---:|---|---|---:|---:|:-:|:-:|---|:-:|---|")
    for s in rep["compare"]:
        L.append("| " + " | ".join(esc(x) for x in [
            s["rank"], s["code"], s["name"], yi(s["net_amt"]),
            pct(s["net_ratio"], signed=False) + (" 法人主導" if s["dominant"] else ""),
            mark(s["A"]["pass"]), mark(s["B"]["pass"]), C_LABEL.get(s["C"]["status"], s["C"]["status"]),
            "✅ 入選" if s["selected"] else "—", "、".join(s["reasons"]) or DASH,
        ]) + " |")
    L.append("")

    L.append("## 4. 科技新聞")
    L.append("### (a) 入選個股相關新聞（近一週）")
    any_news = False
    for s in rep["picks"]:
        if s["news"]:
            any_news = True
            L.append(f"- **{s['code']} {s['name']}**")
            for n in s["news"]:
                L.append(f"  - {esc(n.get('summary') or n.get('title'))}（{esc(n.get('source'))}，{esc(n.get('date'))}）[連結]({url(n['url'])})")
    if not any_news:
        L.append("- —（未取得）")
    L.append("\n### (b) 當日國內外重要科技新聞")
    if rep["tech_news"]:
        for i, n in enumerate(rep["tech_news"], 1):
            L.append(f"{i}. **{esc(n.get('title'))}** — {esc(n.get('summary'))}（{esc(n.get('source'))}）[連結]({url(n['url'])})")
    else:
        L.append("- —（未取得）")
    L.append("")

    L.append("## 5. 資料限制說明")
    L += [f"- {n}" for n in rep["notes"]] or ["- 無"]
    L.append("- 買超金額以每日三大法人買賣超股數 × 當日收盤價逐日加總估算，非實際成交均價。")
    L.append("- 「外資」為外資及陸資（含外資自營商）；外資持股5日變化為最新交易日與5個交易日前持股比率之差（百分點）。")
    L.append("- 投行評等取自公開新聞報導（自動擷取 Google 新聞標題中寫明券商、評等或目標價者），券商報告本身不公開，可能遺漏或誤判，請點連結核對。")
    L.append("- 本報告為資料整理，不構成投資建議。\n")

    L.append("## Sources")
    for s in rep["sources"]:
        L.append(f"- [{s['name']}]({s['url']})")
    seen = set()
    for s in rep["pool"]:
        for e in (s["A"].get("evidence") or []) + (s["C"].get("ratings") or []) + (s.get("news") or []):
            u = url(e.get("url"))
            if u and u not in seen:
                seen.add(u)
                L.append(f"- [{esc(e.get('title') or e.get('source') or s['name'])}]({u})")
    for n in rep["tech_news"]:
        u = url(n.get("url"))
        if u and u not in seen:
            seen.add(u)
            L.append(f"- [{esc(n.get('title'))}]({u})")
    return "\n".join(L) + "\n"
