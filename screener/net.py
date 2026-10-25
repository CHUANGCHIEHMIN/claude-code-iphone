"""HTTP helpers: polite rate limiting, retries, JSON / text decoding."""
from __future__ import annotations

import http.client
import json
import logging
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

log = logging.getLogger(__name__)

UA = "Mozilla/5.0 (X11; Linux x86_64) tw-chip-screener/1.0"
# TWSE asks clients to stay under ~3 requests / 5 seconds per IP.
MIN_INTERVAL = {"www.twse.com.tw": 2.2, "www.tpex.org.tw": 1.5, "news.google.com": 1.5}
_last_hit: dict[str, float] = {}


def _throttle(host: str) -> None:
    gap = MIN_INTERVAL.get(host, 0.5)
    wait = _last_hit.get(host, 0) + gap - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()


def fetch_bytes(url: str, retries: int = 3, timeout: int = 40) -> bytes:
    host = urlparse(url).hostname or ""
    err: Exception | None = None
    for attempt in range(retries):
        _throttle(host)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:  # incl. IncompleteRead, resets
            err = e
            log.warning("fetch failed (%s/%s) %s: %r", attempt + 1, retries, url, e)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}: {err!r}")


def fetch_json(url: str, **kw) -> dict | list:
    raw = fetch_bytes(url, **kw)
    txt = raw.decode("utf-8-sig", "replace").strip()
    if not txt or txt[0] not in "[{":
        raise RuntimeError(f"not JSON from {url}: {txt[:120]!r}")
    return json.loads(txt)


def fetch_text(url: str, **kw) -> str:
    raw = fetch_bytes(url, **kw)
    head = raw[:2000].lower()
    if b"big5" in head or b"ms950" in head or b"cp950" in head:
        return raw.decode("cp950", "replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp950", "replace")
