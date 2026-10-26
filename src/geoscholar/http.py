"""HTTP GET with polite retries for rate limits and temporary server errors."""
import logging
import time

import requests

from geoscholar import config

log = logging.getLogger(__name__)
RETRY_STATUS = {429, 500, 502, 503, 504}


def polite_get(url, params=None, timeout=60, retries=5, base_delay=10.0):
    """GET url; on 429 / 5xx wait and try again, doubling the wait each time.

    If the server sends a Retry-After header (seconds), that wait is used instead.
    Waits with the defaults: 10, 20, 40, 80, 160 s (about 5 minutes in total).
    """
    for attempt in range(retries + 1):
        resp = requests.get(url, params=params, timeout=timeout,
                            headers={"User-Agent": config.USER_AGENT})
        if resp.status_code not in RETRY_STATUS or attempt == retries:
            resp.raise_for_status()
            return resp
        retry_after = resp.headers.get("Retry-After", "")
        wait = float(retry_after) if retry_after.isdigit() else base_delay * 2 ** attempt
        log.warning("HTTP %d from %s, waiting %.0f s (retry %d/%d)",
                    resp.status_code, url.split("?")[0], wait, attempt + 1, retries)
        time.sleep(wait)