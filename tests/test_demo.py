"""Modul demo (AVIATOR_DEMO=1): date simulate, fără rețea, marcat clar pentru model."""
import json

import httpx
import pytest
from mcp.client.client import Client

from aviator_mcp.client import AviatorClient
from aviator_mcp.server import build_server


@pytest.fixture
def demo_env(monkeypatch):
    monkeypatch.setenv("AVIATOR_DEMO", "1")
    monkeypatch.delenv("AVIATOR_API_TOKEN", raising=False)
    monkeypatch.delenv("AVIATOR_DEFAULT_ORG", raising=False)
    monkeypatch.delenv("AVIATOR_DEFAULT_REPO", raising=False)


def test_from_env_demo_nu_cere_token(demo_env):
    c = AviatorClient.from_env()
    assert c.demo is True and c.token


def test_from_env_normal_nu_e_demo(monkeypatch):
    monkeypatch.delenv("AVIATOR_DEMO", raising=False)
    assert AviatorClient.from_env().demo is False


async def test_demo_fara_retea_si_cu_stare(demo_env, monkeypatch):
    async def no_network(*a, **k):
        raise AssertionError("demo mode must not use the network")
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", no_network)
    server = build_server()
    async with Client(server) as c:
        r = await c.call_tool("get_queue_stats", {"repo": "acme/api"})
        assert not r.is_error and json.loads(r.content[0].text)["depth"]["queued"] == 9
        await c.call_tool("queue_pr", {"repo": "acme/api", "number": 1250})
        r = await c.call_tool("get_queue_stats", {"repo": "acme/api"})
        assert json.loads(r.content[0].text)["depth"]["queued"] == 10  # starea persistă în proces


async def test_demo_marcat_in_instructiuni(demo_env):
    server = build_server()
    assert "DEMO MODE" in server.instructions


def test_instructiuni_normale_fara_demo(monkeypatch):
    monkeypatch.delenv("AVIATOR_DEMO", raising=False)
    assert "DEMO MODE" not in build_server(AviatorClient(token="t")).instructions
