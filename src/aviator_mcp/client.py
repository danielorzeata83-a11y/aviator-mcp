"""Thin async HTTP client for the Aviator REST API with LLM-friendly errors."""
from __future__ import annotations

import asyncio
import os
from typing import Any, Callable

import httpx

from . import __version__

DEFAULT_BASE = "https://api.aviator.co"
MAX_WAIT = 10.0  # seconds; cap for Retry-After


class AviatorError(Exception):
    """An API failure, phrased so the model knows what to do next."""


def _api_message(r: httpx.Response) -> str:
    try:
        data = r.json()
    except ValueError:
        return r.text.strip()[:300]
    if isinstance(data, dict):
        if isinstance(data.get("errors"), list):
            return "; ".join(map(str, data["errors"]))
        msg = data.get("message") or data.get("error")
        if msg:
            return str(msg)[:300]
        return "" if {"message", "error"} & set(data) else str(data)[:300]
    return str(data)[:300]


def _error_for(r: httpx.Response, write: bool) -> AviatorError:
    s, api = r.status_code, _api_message(r)
    detail = f" Aviator said: {api}" if api else ""
    if s == 401:
        hint = "Authentication failed: the API token is invalid or expired. Create a token at app.aviator.co (Settings → API token) and set AVIATOR_API_TOKEN."
    elif s == 403:
        hint = "Forbidden: the token lacks permission for this action, or the repo is not configured in Aviator. Skip-line and skip-validation need extra authorization."
    elif s == 404:
        hint = "Not found: check the org/repo spelling, that the repo is enabled in Aviator, and the PR number."
    elif s in (400, 422):
        hint = "Invalid request. Fix the listed problems and retry."
    elif s == 429:
        hint = "Rate limit reached on the Aviator API. Wait a minute before retrying; do not loop."
    elif s >= 500:
        hint = "Aviator server error; try again later."
        if write:
            hint += " The write may or may not have been applied: check the current state (e.g. get_pr_status) before retrying."
    else:
        hint = "Unexpected response."
    return AviatorError(f"HTTP {s}. {hint}{detail}")


class AviatorClient:
    def __init__(self, token: str, base_url: str = DEFAULT_BASE, *, timeout: float = 30.0,
                 sleep: Callable[[float], Any] | None = None, transport: httpx.AsyncBaseTransport | None = None,
                 demo: bool = False):
        self.token = token
        self.demo = demo
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._sleep = sleep
        self._transport = transport

    @classmethod
    def from_env(cls) -> "AviatorClient":
        if os.getenv("AVIATOR_DEMO") == "1":
            from . import demo  # simulated data, no network, no token
            return cls(token="demo", transport=httpx.MockTransport(demo.handler_for(demo.fresh())), demo=True)
        return cls(token=os.getenv("AVIATOR_API_TOKEN", ""), base_url=os.getenv("AVIATOR_API_URL", DEFAULT_BASE))

    async def _wait(self, seconds: float) -> None:
        if self._sleep is None:
            await asyncio.sleep(seconds)
        else:
            res = self._sleep(seconds)
            if asyncio.iscoroutine(res):
                await res

    async def request(self, method: str, path: str, *, params: dict | None = None, json: Any = None,
                      content: str | None = None, content_type: str | None = None) -> Any:
        if not self.token:
            raise AviatorError("AVIATOR_API_TOKEN is not set. Ask the user for an Aviator API token "
                               "(app.aviator.co → Settings → API token) and configure it in the MCP server env.")
        write = method != "GET"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json",
                   "User-Agent": f"aviator-mcp-unofficial/{__version__}"}
        if content_type:
            headers["Content-Type"] = content_type
        params = {k: v for k, v in (params or {}).items() if v is not None}
        attempts = 1 if write else 2
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self._timeout, transport=self._transport) as http:
            for attempt in range(1, attempts + 2):
                try:
                    r = await http.request(method, path, params=params, json=json, content=content, headers=headers)
                except httpx.TransportError as e:
                    if attempt < attempts:
                        continue
                    raise AviatorError(f"Could not reach Aviator at {self.base_url} ({type(e).__name__}). "
                                       "Check network access and AVIATOR_API_URL.") from None
                if r.status_code == 429 and attempt == 1:
                    try:
                        wait = float(r.headers.get("Retry-After", "2"))
                    except ValueError:
                        wait = 2.0
                    await self._wait(min(wait, MAX_WAIT))
                    continue
                if r.status_code >= 500 and attempt < attempts:
                    continue
                if r.status_code >= 400:
                    raise _error_for(r, write)
                try:
                    return r.json()
                except ValueError:
                    return r.text
        raise AviatorError("Request failed after retries.")  # pragma: no cover

    async def get(self, path: str, **kw) -> Any:
        return await self.request("GET", path, **kw)

    async def post(self, path: str, **kw) -> Any:
        return await self.request("POST", path, **kw)

    async def paginate(self, path: str, *, params: dict | None = None, key: str | None = None,
                       limit: int = 50, page_size: int = 10, max_pages: int = 20) -> tuple[list, bool]:
        """Fetch page=1.. until a short/empty page or `limit` items. Returns (items, has_more)."""
        items: list = []
        for page in range(1, max_pages + 1):
            data = await self.get(path, params={**(params or {}), "page": page})
            batch = (data.get(key) if isinstance(data, dict) else data) or []
            items.extend(batch)
            if len(items) >= limit:
                return items[:limit], len(items) > limit or len(batch) >= page_size
            if len(batch) < page_size:
                return items, False
        return items, True
