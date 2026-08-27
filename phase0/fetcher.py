"""Polite HTTP with an on-disk cache.

Every response is cached by URL hash. Reparsing after a parser fix costs
nothing and refetches nothing — which over the life of this project is the
single biggest reduction in request volume.
"""

import hashlib
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests

import config

_last_request_at = {}
_robots_cache = {}


def _cache_path(url):
    h = hashlib.sha256(url.encode()).hexdigest()[:24]
    return Path(config.HTML_CACHE_DIR) / f"{h}.html"


def robots_status(url):
    """Report what robots.txt says. Reports — does not enforce.

    Deliberate: what you do with this is your call, not the script's, and
    it should be a decision you make once, knowingly, rather than a default
    you inherit. See spec section 9.
    """
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    if base not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(f"{base}/robots.txt")
        try:
            rp.read()
            _robots_cache[base] = rp
        except Exception as e:
            print(f"  [robots] could not read {base}/robots.txt: {e}")
            _robots_cache[base] = None

    rp = _robots_cache[base]
    if rp is None:
        return "unknown"
    return "allowed" if rp.can_fetch(config.USER_AGENT, url) else "disallowed"


def _throttle(host):
    last = _last_request_at.get(host, 0)
    wait = config.REQUEST_DELAY_S - (time.time() - last)
    if wait > 0:
        time.sleep(wait)
    _last_request_at[host] = time.time()


def get(url, use_cache=True):
    """Return (html, status_code, from_cache).

    status_code is None when served from cache.
    """
    cp = _cache_path(url)
    if use_cache and cp.exists():
        return cp.read_text(encoding="utf-8"), None, True

    host = urlparse(url).netloc
    headers = {
        "User-Agent": config.USER_AGENT,
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    }

    last_err = None
    for attempt in range(config.MAX_RETRIES + 1):
        _throttle(host)
        try:
            r = requests.get(
                url, headers=headers, timeout=config.TIMEOUT_S,
                allow_redirects=True,
            )
            # Record removal semantics — this is spec section 5b signal 4.
            if r.status_code in (404, 410):
                return None, r.status_code, False
            r.raise_for_status()
            cp.parent.mkdir(parents=True, exist_ok=True)
            cp.write_text(r.text, encoding="utf-8")
            return r.text, r.status_code, False
        except Exception as e:
            last_err = e
            if attempt < config.MAX_RETRIES:
                time.sleep(5 * (attempt + 1))

    print(f"  [fetch] giving up on {url}: {last_err}")
    return None, None, False
