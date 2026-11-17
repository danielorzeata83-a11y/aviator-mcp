"""Serverul MCP: listare tool-uri, scheme, adnotări și rutarea apelurilor (prin client MCP în memorie)."""
import json

import httpx
import pytest
import respx
from mcp.client.client import Client

from aviator_mcp.client import AviatorClient
from aviator_mcp.server import build_server

BASE = "https://api.aviator.co"
READ = {"list_repositories", "get_queue_stats", "list_queued_prs", "get_pr_status",
        "get_bot_pr", "get_bisection_status", "get_config", "get_analytics"}
WRITE = {"queue_pr", "dequeue_pr", "refresh_or_sync_pr", "set_queue_paused", "backport_pr", "update_config"}


@pytest.fixture
def server(monkeypatch):
    monkeypatch.delenv("AVIATOR_DEFAULT_ORG", raising=False)
    monkeypatch.delenv("AVIATOR_DEFAULT_REPO", raising=False)
    return build_server(AviatorClient(token="tok", base_url=BASE, sleep=lambda s: None))


async def call(server, name, **args):
    async with Client(server) as c:
        r = await c.call_tool(name, args)
    text = r.content[0].text
    return r.is_error, (text if r.is_error else json.loads(text))


# --- listare / scheme ------------------------------------------------------
async def test_14_tooluri_cu_adnotari_corecte(server):
    async with Client(server) as c:
        tools = {t.name: t for t in (await c.list_tools()).tools}
    assert set(tools) == READ | WRITE
    for n in READ:
        assert tools[n].annotations.read_only_hint is True, n
    for n in WRITE:
        a = tools[n].annotations
        assert a.read_only_hint is False and a.destructive_hint is True, n
    for t in tools.values():
        assert t.input_schema["type"] == "object"
        assert t.description and len(t.description) < 600, t.name


# --- rutare + construcția cererilor ----------------------------------------
@respx.mock
async def test_queue_pr_skip_line(server):
    route = respx.post(f"{BASE}/api/v1/pull_request").mock(return_value=httpx.Response(200, json={"pull_request": {"number": 9}}))
    err, out = await call(server, "queue_pr", repo="acme/api", number=9, skip_line=True, skip_line_reason="prod outage")
    assert not err and out["pull_request"]["number"] == 9
    body = json.loads(route.calls.last.request.content)
    assert body["action"] == "queue"
    assert body["pull_request"]["skip_line"] is True
    assert body["pull_request"]["repository"] == {"org": "acme", "name": "api"}


@respx.mock
async def test_dequeue_si_sync(server):
    route = respx.post(f"{BASE}/api/v1/pull_request").mock(return_value=httpx.Response(200, json={}))
    await call(server, "dequeue_pr", org="acme", repo="api", number=3)
    assert json.loads(route.calls.last.request.content)["action"] == "dequeue"
    await call(server, "refresh_or_sync_pr", org="acme", repo="api", number=3, action="sync")
    assert json.loads(route.calls.last.request.content)["action"] == "sync"


async def test_refresh_or_sync_respinge_alte_actiuni(server):
    err, msg = await call(server, "refresh_or_sync_pr", org="acme", repo="api", number=3, action="queue")
    assert err


async def test_get_pr_status_number_si_branch_respins_fara_http(server):
    with respx.mock(assert_all_called=False) as m:
        route = m.get(f"{BASE}/api/v1/pull_request")
        err, msg = await call(server, "get_pr_status", org="acme", repo="api", number=1, branch="x")
        assert err and "exactly one" in msg and route.call_count == 0


@respx.mock
async def test_get_pr_status_dupa_branch(server):
    route = respx.get(f"{BASE}/api/v1/pull_request").mock(return_value=httpx.Response(200, json={"number": 5, "status": "queued"}))
    err, out = await call(server, "get_pr_status", org="acme", repo="api", branch="feat/x")
    assert out["status"] == "queued"
    p = route.calls.last.request.url.params
    assert p["branch"] == "feat/x" and "number" not in p


@respx.mock
async def test_set_queue_paused_repo_vs_branches(server):
    r_repo = respx.post(f"{BASE}/api/v1/repo").mock(return_value=httpx.Response(200, json={}))
    r_br = respx.post(f"{BASE}/api/v1/branches").mock(return_value=httpx.Response(200, json={}))
    await call(server, "set_queue_paused", org="acme", repo="api", paused=True)
    assert json.loads(r_repo.calls.last.request.content) == {"org": "acme", "name": "api", "paused": True}
    await call(server, "set_queue_paused", org="acme", repo="api", paused=True, branch_pattern="release-*",
               paused_message="freeze")
    assert json.loads(r_br.calls.last.request.content) == {
        "repository": {"org": "acme", "name": "api"}, "pattern": "release-*", "paused": True, "paused_message": "freeze"}
    assert r_repo.call_count == 1


async def test_get_branch_status_nu_exista(server):
    """Verificat live: API-ul Aviator nu permite citirea statusului pe branch-uri
    (GET respins; POST cere obligatoriu `paused`, deci ar modifica starea)."""
    async with Client(server) as c:
        names = {t.name for t in (await c.list_tools()).tools}
    assert "get_branch_status" not in names


@respx.mock
async def test_list_queued_prs_compact_si_limitat(server):
    prs = [{"number": i, "title": f"t{i}", "author": "a", "base_branch": "main", "status": "queued",
            "queued_at": "x", "skip_line": False, "bot_pull_request": {"huge": "x" * 500}} for i in range(30)]
    respx.get(f"{BASE}/api/v1/pull_request/queued").mock(return_value=httpx.Response(200, json={"pull_requests": prs}))
    err, out = await call(server, "list_queued_prs", org="acme", repo="api", limit=5)
    assert out["count"] == 5 and out["total"] == 30 and out["truncated"] is True
    assert "bot_pull_request" not in out["items"][0] and out["items"][0]["number"] == 0


@respx.mock
async def test_list_repositories_paginat(server):
    respx.get(f"{BASE}/api/v1/repo").mock(side_effect=[
        httpx.Response(200, json=[{"org": "a", "name": str(i), "paused": False, "active": True} for i in range(10)]),
        httpx.Response(200, json=[{"org": "a", "name": "x", "paused": True, "active": True}])])
    err, out = await call(server, "list_repositories")
    assert out["count"] == 11 and out["has_more"] is False


@respx.mock
async def test_get_config_trunchiat_si_istoric(server):
    respx.get(f"{BASE}/api/v1/config").mock(return_value=httpx.Response(200, text="a: 1\n" * 3000))
    hist = respx.get(f"{BASE}/api/v1/config/history").mock(
        return_value=httpx.Response(200, json={"history": [{"diff": "-a\n+b", "applied_at": "t"}]}))
    err, out = await call(server, "get_config", org="acme", repo="api", include_history=True, max_chars=200)
    assert out["config"]["truncated"] is True and len(out["config"]["text"]) == 200
    assert out["history"]["items"][0]["diff"] == "-a\n+b"
    assert hist.call_count == 1


@respx.mock
async def test_get_config_fara_istoric_nu_cere_istoric(server):
    respx.get(f"{BASE}/api/v1/config").mock(return_value=httpx.Response(200, text="a: 1\n"))
    err, out = await call(server, "get_config", org="acme", repo="api")
    assert "history" not in out and out["config"]["text"] == "a: 1\n"


async def test_update_config_yaml_invalid_fara_http(server):
    with respx.mock(assert_all_called=False) as m:
        route = m.post(f"{BASE}/api/v1/config")
        err, msg = await call(server, "update_config", org="acme", repo="api", yaml_config="a: [1")
        assert err and "YAML" in msg and route.call_count == 0


@respx.mock
async def test_update_config_trimite_yaml_brut(server):
    route = respx.post(f"{BASE}/api/v1/config").mock(return_value=httpx.Response(200, json={"success": True}))
    err, out = await call(server, "update_config", org="acme", repo="api", yaml_config="merge_rules:\n  a: 1\n")
    assert out == {"success": True}
    assert route.calls.last.request.content == b"merge_rules:\n  a: 1\n"


@respx.mock
async def test_get_analytics_repo_format_si_rezumat(server):
    route = respx.get(f"{BASE}/api/v1/analytics").mock(return_value=httpx.Response(200, json={
        "mergequeue_usage": [{"date": "d", "total": 4, "merged_by_bot": 3}]}))
    err, out = await call(server, "get_analytics", org="acme", repo="api", start="2026-11-01", end="2026-11-07")
    p = route.calls.last.request.url.params
    assert p["repo"] == "acme/api" and p["start"] == "2026-11-01"
    assert out["summary"]["prs_merged_total"] == 4 and "daily" in out


async def test_get_analytics_data_invalida(server):
    err, msg = await call(server, "get_analytics", org="acme", repo="api", start="11/01/2026")
    assert err and "YYYY-MM-DD" in msg


@respx.mock
async def test_backport_si_bisection_si_bot_pr(server):
    b = respx.post(f"{BASE}/api/v1/pull_request/backport").mock(return_value=httpx.Response(200, json={"message": "ok"}))
    await call(server, "backport_pr", org="acme", repo="api", number=12, target_branch="release-1")
    assert json.loads(b.calls.last.request.content) == {
        "target_branch": "release-1", "source_pull": {"number": 12, "repository": {"org": "acme", "name": "api"}}}
    bi = respx.get(f"{BASE}/api/v1/pull_request/bisection").mock(return_value=httpx.Response(200, json={"is_bisecting": False}))
    err, out = await call(server, "get_bisection_status", org="acme", repo="api", number=12)
    assert out == {"is_bisecting": False} and bi.calls.last.request.url.params["number"] == "12"
    respx.get(f"{BASE}/api/v1/bot_pull_request").mock(return_value=httpx.Response(200, json={
        "number": 201, "pull_requests": [{"number": 1, "title": "t", "status": "queued", "x": "drop"}]}))
    err, out = await call(server, "get_bot_pr", org="acme", repo="api", number=201)
    assert out["pull_requests"][0] == {"number": 1, "title": "t", "status": "queued"}


@respx.mock
async def test_get_queue_stats(server):
    respx.get(f"{BASE}/api/v1/queue/stats").mock(return_value=httpx.Response(200, json={"depth": {"queued": 3}}))
    err, out = await call(server, "get_queue_stats", org="acme", repo="api")
    assert out == {"depth": {"queued": 3}}


# --- erori ajung la LLM cu mesaj util ---------------------------------------
@respx.mock
async def test_eroare_api_devine_mesaj_tool(server):
    respx.post(f"{BASE}/api/v1/pull_request").mock(return_value=httpx.Response(404, json={"message": "pull_request not found"}))
    err, msg = await call(server, "queue_pr", org="acme", repo="api", number=9999)
    assert err and "pull_request not found" in msg and "404" in msg


async def test_fara_token(monkeypatch):
    s = build_server(AviatorClient(token="", base_url=BASE))
    err, msg = await call(s, "get_queue_stats", org="acme", repo="api")
    assert err and "AVIATOR_API_TOKEN" in msg


async def test_repo_lipsa(server):
    err, msg = await call(server, "get_queue_stats", repo="api")
    assert err and "org" in msg


async def test_paused_message_fara_pattern_respins(server):
    err, msg = await call(server, "set_queue_paused", org="acme", repo="api", paused=True, paused_message="x")
    assert err and "branch_pattern" in msg


async def test_scheme_compacte_fara_title_si_null(server):
    async with Client(server) as c:
        tools = (await c.list_tools()).tools
    import json as _j
    blob = _j.dumps([t.input_schema for t in tools])
    assert '"title"' not in blob and '"null"' not in blob


async def test_validarea_ramane_activa_dupa_compactare(server):
    err, msg = await call(server, "queue_pr", repo="acme/api", number="abc")
    assert err


@respx.mock
async def test_get_pr_status_raspuns_compact(server):
    respx.get(f"{BASE}/api/v1/pull_request").mock(return_value=httpx.Response(200, json={
        "number": 5, "status": "queued", "title": "t", "repository": {"org": "a", "name": "b"},
        "bot_pull_request": {"number": 201, "github_url": "u", "head_commit_sha": "x" * 40, "codemix_pre_batch_sha": "y"}}))
    err, out = await call(server, "get_pr_status", org="acme", repo="api", number=5)
    assert out == {"number": 5, "status": "queued", "title": "t", "bot_pull_request": {"number": 201, "github_url": "u"}}


@respx.mock
async def test_set_queue_paused_raspuns_uniform(server):
    respx.post(f"{BASE}/api/v1/repo").mock(return_value=httpx.Response(200, json={"org": "acme", "name": "api", "paused": True, "active": True}))
    respx.post(f"{BASE}/api/v1/branches").mock(return_value=httpx.Response(200, json={"pattern": "release-*", "paused": True}))
    err, a = await call(server, "set_queue_paused", org="acme", repo="api", paused=True)
    err, b = await call(server, "set_queue_paused", org="acme", repo="api", paused=True, branch_pattern="release-*")
    assert a == {"repo": "acme/api", "scope": "whole repo", "paused": True}
    assert b["scope"] == "base branches matching 'release-*'" and b["paused"] is True and b["repo"] == "acme/api"
