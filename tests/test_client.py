"""Client HTTP: URL, parametri, autentificare, maparea erorilor, retry, paginare."""
import httpx
import pytest
import respx

from aviator_mcp.client import AviatorClient, AviatorError

BASE = "https://api.aviator.co"


def make(token="tok_123", **kw):
    return AviatorClient(token=token, base_url=BASE, sleep=lambda s: None, **kw)


# --- construcția cererii ---------------------------------------------------
@respx.mock
async def test_get_cu_parametri_si_autentificare():
    route = respx.get(f"{BASE}/api/v1/queue/stats").mock(return_value=httpx.Response(200, json={"depth": {}}))
    out = await make().get("/api/v1/queue/stats", params={"org": "acme", "repo": "api", "x": None})
    assert out == {"depth": {}}
    req = route.calls.last.request
    assert req.url.params["org"] == "acme" and req.url.params["repo"] == "api"
    assert "x" not in req.url.params  # None-urile nu se trimit
    assert req.headers["Authorization"] == "Bearer tok_123"
    assert req.headers["User-Agent"].startswith("aviator-mcp-unofficial/")


@respx.mock
async def test_post_json():
    route = respx.post(f"{BASE}/api/v1/repo").mock(return_value=httpx.Response(200, json={"paused": True}))
    await make().post("/api/v1/repo", json={"org": "a", "name": "b", "paused": True})
    assert route.calls.last.request.content == b'{"org":"a","name":"b","paused":true}'


@respx.mock
async def test_post_continut_brut_yaml():
    route = respx.post(f"{BASE}/api/v1/config").mock(return_value=httpx.Response(200, json={"success": True}))
    await make().post("/api/v1/config", params={"org": "a", "repo": "b"}, content="k: v\n",
                      content_type="text/plain")
    req = route.calls.last.request
    assert req.content == b"k: v\n" and req.headers["Content-Type"] == "text/plain"


@respx.mock
async def test_get_cu_corp_json():
    route = respx.get(f"{BASE}/api/v1/branches").mock(return_value=httpx.Response(200, json={"branches": []}))
    await make().get("/api/v1/branches", json={"repository": {"org": "a", "name": "b"}})
    assert route.calls.last.request.content == b'{"repository":{"org":"a","name":"b"}}'


async def test_fara_token_nu_face_cerere():
    with pytest.raises(AviatorError, match="AVIATOR_API_TOKEN"):
        await make(token="").get("/api/v1/repo")


def test_base_url_din_env(monkeypatch):
    monkeypatch.setenv("AVIATOR_API_URL", "https://aviator.internal.example/")
    monkeypatch.setenv("AVIATOR_API_TOKEN", "t")
    c = AviatorClient.from_env()
    assert c.base_url == "https://aviator.internal.example" and c.token == "t"


@respx.mock
async def test_raspuns_non_json_returnat_ca_text():
    respx.get(f"{BASE}/api/v1/config").mock(return_value=httpx.Response(200, text="merge_rules: {}\n"))
    assert await make().get("/api/v1/config") == "merge_rules: {}\n"


# --- maparea erorilor ------------------------------------------------------
@pytest.mark.parametrize("status,needle", [
    (401, "token"),
    (403, "permission"),
    (404, "not found"),
])
@respx.mock
async def test_erori_4xx_mesaje_actionabile(status, needle):
    respx.get(f"{BASE}/api/v1/pull_request").mock(return_value=httpx.Response(status, json={"error": "nope"}))
    with pytest.raises(AviatorError) as e:
        await make().get("/api/v1/pull_request")
    msg = str(e.value).lower()
    assert needle in msg and str(status) in msg and "nope" in msg


@respx.mock
async def test_400_lista_de_erori():
    respx.post(f"{BASE}/api/v1/config").mock(return_value=httpx.Response(400, json={"errors": ["a: bad", "b: bad"]}))
    with pytest.raises(AviatorError) as e:
        await make().post("/api/v1/config", content="x: 1", content_type="text/plain")
    assert "a: bad" in str(e.value) and "b: bad" in str(e.value) and "400" in str(e.value)


@respx.mock
async def test_429_reincearca_dupa_retry_after_apoi_reuseste():
    waits = []
    route = respx.get(f"{BASE}/api/v1/repo").mock(side_effect=[
        httpx.Response(429, headers={"Retry-After": "3"}), httpx.Response(200, json=[])])
    c = AviatorClient(token="t", base_url=BASE, sleep=waits.append)
    assert await c.get("/api/v1/repo") == []
    assert route.call_count == 2 and waits == [3.0]


@respx.mock
async def test_429_persistent_mesaj_rate_limit_si_asteptare_plafonata():
    waits = []
    respx.get(f"{BASE}/api/v1/repo").mock(return_value=httpx.Response(429, headers={"Retry-After": "999"}))
    c = AviatorClient(token="t", base_url=BASE, sleep=waits.append)
    with pytest.raises(AviatorError, match="(?i)rate limit"):
        await c.get("/api/v1/repo")
    assert waits == [10.0]


@respx.mock
async def test_5xx_reincearca_o_data():
    route = respx.get(f"{BASE}/api/v1/repo").mock(side_effect=[httpx.Response(502), httpx.Response(200, json=[1])])
    assert await make().get("/api/v1/repo") == [1]
    assert route.call_count == 2


@respx.mock
async def test_5xx_persistent():
    respx.get(f"{BASE}/api/v1/repo").mock(return_value=httpx.Response(500, text="boom"))
    with pytest.raises(AviatorError, match="500"):
        await make().get("/api/v1/repo")


@respx.mock
async def test_post_nu_se_reincearca_la_5xx():
    """Scrierile nu sunt idempotente: o eroare 5xx nu se repetă automat."""
    route = respx.post(f"{BASE}/api/v1/pull_request").mock(return_value=httpx.Response(503))
    with pytest.raises(AviatorError, match="(?i)may or may not"):
        await make().post("/api/v1/pull_request", json={})
    assert route.call_count == 1


@respx.mock
async def test_eroare_de_retea():
    respx.get(f"{BASE}/api/v1/repo").mock(side_effect=httpx.ConnectError("dns"))
    with pytest.raises(AviatorError, match="(?i)could not reach"):
        await make().get("/api/v1/repo")


# --- paginare --------------------------------------------------------------
def pages(*sizes):
    n = 0
    out = []
    for s in sizes:
        out.append(httpx.Response(200, json=[{"i": n + k} for k in range(s)]))
        n += s
    return out


@respx.mock
async def test_paginare_ultima_pagina_partiala():
    route = respx.get(f"{BASE}/api/v1/repo").mock(side_effect=pages(10, 10, 3))
    items, more = await make().paginate("/api/v1/repo", limit=100)
    assert len(items) == 23 and more is False
    assert [c.request.url.params["page"] for c in route.calls] == ["1", "2", "3"]


@respx.mock
async def test_paginare_pagina_goala():
    respx.get(f"{BASE}/api/v1/repo").mock(side_effect=pages(10, 0))
    items, more = await make().paginate("/api/v1/repo", limit=100)
    assert len(items) == 10 and more is False


@respx.mock
async def test_paginare_fara_rezultate():
    respx.get(f"{BASE}/api/v1/repo").mock(side_effect=pages(0))
    assert await make().paginate("/api/v1/repo", limit=5) == ([], False)


@respx.mock
async def test_paginare_limita_opreste_si_raporteaza_has_more():
    route = respx.get(f"{BASE}/api/v1/repo").mock(side_effect=pages(10, 10, 10))
    items, more = await make().paginate("/api/v1/repo", limit=15)
    assert [x["i"] for x in items] == list(range(15)) and more is True
    assert route.call_count == 2


@respx.mock
async def test_paginare_cu_cheie_si_parametri():
    route = respx.get(f"{BASE}/api/v1/config/history").mock(side_effect=[
        httpx.Response(200, json={"history": [{"a": 1}]})])
    items, more = await make().paginate("/api/v1/config/history", params={"org": "a"}, key="history", limit=5)
    assert items == [{"a": 1}] and more is False
    assert route.calls.last.request.url.params["org"] == "a"


@respx.mock
async def test_mesaj_api_null_nu_apare_ca_none():
    """Live: Aviator a răspuns 404 cu {"error": null} → nu afișăm „Aviator said: None”."""
    respx.get(f"{BASE}/api/v1/pull_request").mock(return_value=httpx.Response(404, json={"error": None, "message": None}))
    with pytest.raises(AviatorError) as e:
        await make().get("/api/v1/pull_request")
    assert "None" not in str(e.value) and "Aviator said" not in str(e.value)
