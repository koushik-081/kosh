from functools import lru_cache

import httpx

from app.config import get_settings


@lru_cache
def setup_tracing() -> bool:
    """Send every LLM call and agent step to Phoenix, if it is running. Returns True if tracing is on.

    Checks once at startup instead of failing on every request when Phoenix is not started.
    """
    url = get_settings().phoenix_url
    try:
        httpx.get(url, timeout=1)
    except httpx.HTTPError:
        print(f"Tracing off: Phoenix is not running at {url}")
        return False
    from phoenix.otel import register  # imported here so Kosh still starts without Phoenix

    register(project_name="kosh", endpoint=f"{url}/v1/traces", auto_instrument=True, verbose=False)
    return True