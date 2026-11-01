"""Push the day's signals to Telegram (free). Skipped silently unless both secrets are set.

Secrets (GitHub → Settings → Secrets and variables → Actions):
  TELEGRAM_BOT_TOKEN   token from @BotFather
  TELEGRAM_CHAT_ID     your chat id (send the bot a message, then open
                       https://api.telegram.org/bot<TOKEN>/getUpdates to read it)
Optional variable SITE_URL: the GitHub Pages address, added as a link at the end.

python -m screener.notify [docs/data/reports/YYYY-MM-DD.json]
"""
from __future__ import annotations

import json
import logging
import os
import sys
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent


def message(rep: dict, site: str | None = None) -> str:
    reg = (rep.get("market") or {}).get("regime") or {}
    pf = rep.get("portfolio") or {}
    L = [f"📊 法人籌碼選股 {rep['asof']}"]
    if reg.get("taiex"):
        L.append(f"大盤：{reg['state']}（加權 {reg['taiex']:,.0f}／60日均 {reg['ma']:,.0f}）" if reg.get("ma")
                 else f"大盤：{reg['state']}")
    L.append(f"入選 {len(rep.get('picks') or [])} 檔")
    buys = pf.get("orders") or []
    if buys:
        L.append("\n🟢 明日開盤買進（模擬持股）")
        for o in buys:
            L.append(f"・{o['code']} {o['name']}　參考價 {o['ref_close']:,.2f}　停損約 {o['est_stop']:,.2f}")
    sells = pf.get("exits") or []
    if sells:
        L.append("\n🔴 明日開盤賣出")
        for x in sells:
            L.append(f"・{x['code']} {x['name']}　{x['exit_order']}（{x['ret'] * 100:+.1f}%）")
    enter = [s for s in rep.get("picks") or [] if s.get("signal") == "可進場" and not s.get("order")]
    if enter:
        L.append("\n其他可進場：" + "、".join(f"{s['code']}{s['name']}" for s in enter[:8]))
    if not buys and not sells:
        L.append("\n今日無新的買賣訊號")
    if pf.get("equity"):
        L.append(f"\n模擬帳戶 {pf['equity']:,.0f} 元（{(pf['equity'] / pf['capital'] - 1) * 100:+.1f}%），持有 {len(pf.get('positions') or [])} 檔")
    if site:
        L.append(site)
    L.append("※ 資料整理，非投資建議")
    return "\n".join(L)


def send(text: str, token: str, chat_id: str) -> None:
    body = json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        log.info("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set; skipping notification")
        return
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        idx = json.loads((ROOT / "docs" / "data" / "index.json").read_text("utf-8"))
        path = ROOT / "docs" / "data" / "reports" / f"{idx['latest']}.json"
    rep = json.loads(path.read_text("utf-8"))
    try:
        send(message(rep, os.environ.get("SITE_URL") or None), token, chat)
        log.info("notification sent for %s", rep["asof"])
    except Exception as e:  # noqa: BLE001  通知失敗不影響報告
        log.warning("notification failed: %r", e)


if __name__ == "__main__":
    main()
