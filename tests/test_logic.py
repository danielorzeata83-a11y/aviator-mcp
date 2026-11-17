"""Logică pură: validare input, construirea corpului, trunchiere."""
import pytest

from aviator_mcp import logic as L
from aviator_mcp.logic import InputError


# --- org / repo ------------------------------------------------------------
def test_resolve_repo_explicit():
    assert L.resolve_repo("acme", "api") == ("acme", "api")


def test_resolve_repo_forma_org_slash_repo():
    assert L.resolve_repo(None, "acme/api") == ("acme", "api")
    assert L.resolve_repo("acme", "acme/api") == ("acme", "api")


def test_resolve_repo_din_env(monkeypatch):
    monkeypatch.setenv("AVIATOR_DEFAULT_ORG", "acme")
    monkeypatch.setenv("AVIATOR_DEFAULT_REPO", "web")
    assert L.resolve_repo(None, None) == ("acme", "web")


def test_resolve_repo_lipsa_sau_invalid(monkeypatch):
    monkeypatch.delenv("AVIATOR_DEFAULT_ORG", raising=False)
    monkeypatch.delenv("AVIATOR_DEFAULT_REPO", raising=False)
    with pytest.raises(InputError, match="org"):
        L.resolve_repo(None, "api")
    with pytest.raises(InputError, match="repo"):
        L.resolve_repo("acme", None)
    with pytest.raises(InputError):
        L.resolve_repo("ac me", "api")
    with pytest.raises(InputError):
        L.resolve_repo("other", "acme/api")  # conflict org


# --- PR / date -------------------------------------------------------------
@pytest.mark.parametrize("n", [0, -3])
def test_pr_number_pozitiv(n):
    with pytest.raises(InputError, match="positive"):
        L.check_pr_number(n)


def test_pr_number_ok():
    assert L.check_pr_number(1234) == 1234


def test_date_format():
    assert L.check_date("2026-11-01") == "2026-11-01"
    assert L.check_date(None) is None
    with pytest.raises(InputError, match="YYYY-MM-DD"):
        L.check_date("01/11/2026")
    with pytest.raises(InputError):
        L.check_date("2026-13-01")


def test_interval_start_dupa_end():
    with pytest.raises(InputError, match="start"):
        L.check_range("2026-11-10", "2026-11-01")
    assert L.check_range("2026-11-01", "2026-11-10") == ("2026-11-01", "2026-11-10")


def test_exact_unul_dintre_number_si_branch():
    assert L.pr_lookup(12, None) == {"number": 12}
    assert L.pr_lookup(None, "feat/x") == {"branch": "feat/x"}
    with pytest.raises(InputError, match="exactly one"):
        L.pr_lookup(None, None)
    with pytest.raises(InputError, match="exactly one"):
        L.pr_lookup(12, "feat/x")


# --- corpul POST /pull_request --------------------------------------------
def test_pr_body_queue_minimal_trimite_affected_targets_gol():
    """Live: Aviator respinge queue fără affected_targets („Missing affected_targets”), deși docs îl dau opțional."""
    assert L.pr_body("queue", "acme", "api", 1234) == {
        "action": "queue",
        "pull_request": {"number": 1234, "repository": {"org": "acme", "name": "api"}, "affected_targets": []},
    }


def test_pr_body_dequeue_fara_affected_targets():
    assert "affected_targets" not in L.pr_body("dequeue", "acme", "api", 1)["pull_request"]


def test_pr_body_skip_line_cu_motiv_si_optiuni():
    b = L.pr_body("queue", "acme", "api", 7, skip_line=True, skip_line_reason="prod outage",
                  affected_targets=["a"], merge_commit_title="T", merge_commit_body="B")
    pr = b["pull_request"]
    assert pr["skip_line"] is True and pr["skip_line_reason"] == "prod outage"
    assert pr["affected_targets"] == ["a"]
    assert pr["merge_commit_message"] == {"title": "T", "body": "B"}


def test_pr_body_motiv_fara_skip_line_respins():
    with pytest.raises(InputError, match="skip_line"):
        L.pr_body("queue", "acme", "api", 7, skip_line_reason="x")


def test_pr_body_optiuni_de_queue_interzise_la_alte_actiuni():
    with pytest.raises(InputError, match="queue"):
        L.pr_body("dequeue", "acme", "api", 7, skip_line=True)


def test_pr_body_actiune_invalida():
    with pytest.raises(InputError):
        L.pr_body("merge", "acme", "api", 7)


def test_pr_body_omite_valori_none():
    b = L.pr_body("sync", "acme", "api", 7, affected_targets=None)
    assert "affected_targets" not in b["pull_request"]


# --- YAML config -----------------------------------------------------------
def test_yaml_valid():
    assert L.check_yaml("merge_rules:\n  labels:\n    trigger: mergequeue\n").startswith("merge_rules")


@pytest.mark.parametrize("bad", ["", "   ", "a: [1, 2", "- just\n- a list\n"])
def test_yaml_invalid_respins_local(bad):
    with pytest.raises(InputError):
        L.check_yaml(bad)


# --- trunchiere ------------------------------------------------------------
def test_truncate_text_sub_limita():
    assert L.truncate_text("abc", 10) == {"text": "abc", "truncated": False, "total_chars": 3}


def test_truncate_text_peste_limita():
    r = L.truncate_text("x" * 50, 20)
    assert r["text"] == "x" * 20 and r["truncated"] is True and r["total_chars"] == 50


def test_cap_list():
    assert L.cap_list([1, 2, 3], 2) == {"items": [1, 2], "count": 2, "total": 3, "truncated": True}
    assert L.cap_list([], 5) == {"items": [], "count": 0, "total": 0, "truncated": False}


# --- rezumat analytics -----------------------------------------------------
def test_rezumat_analytics():
    data = {
        "time_in_queue": [{"date": "d1", "avg": 100, "p90": 300}, {"date": "d2", "avg": 200, "p90": 500}],
        "mergequeue_usage": [{"date": "d1", "total": 10, "merged_by_bot": 8}, {"date": "d2", "total": 5, "merged_by_bot": 5}],
        "blocked_reason": [{"date": "d1", "ci_failure": 2, "merge_conflict": 1, "manual_dequeue": 0},
                           {"date": "d2", "ci_failure": 1, "merge_conflict": 0, "manual_dequeue": 3}],
    }
    s = L.summarize_analytics(data)
    assert s == {
        "days": 2,
        "time_in_queue_avg_minutes": 150.0,
        "time_in_queue_p90_max_minutes": 500,
        "prs_merged_total": 15,
        "prs_merged_by_aviator": 13,
        "blocked_totals": {"ci_failure": 3, "merge_conflict": 1, "manual_dequeue": 3},
    }


def test_rezumat_analytics_gol_sau_partial():
    assert L.summarize_analytics({}) == {"days": 0}
    assert L.summarize_analytics({"mergequeue_usage": []}) == {"days": 0}


# --- compactarea schemei (etapa 6) -----------------------------------------
def test_compact_schema_scoate_title_si_anyof_null():
    s = {"type": "object", "title": "fArguments", "required": ["n"], "properties": {
        "n": {"type": "integer", "title": "N", "exclusiveMinimum": 0},
        "org": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None, "title": "Org", "description": "GitHub org."},
        "tags": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": None, "title": "Tags"},
        "flag": {"type": "boolean", "default": False, "title": "Flag"},
        "mode": {"enum": ["refresh", "sync"], "type": "string", "title": "Mode"}}}
    assert L.compact_schema(s) == {"type": "object", "required": ["n"], "properties": {
        "n": {"type": "integer", "exclusiveMinimum": 0},
        "org": {"type": "string", "description": "GitHub org."},
        "tags": {"items": {"type": "string"}, "type": "array"},
        "flag": {"type": "boolean", "default": False},
        "mode": {"enum": ["refresh", "sync"], "type": "string"}}}


def test_compact_schema_nu_modifica_inputul():
    s = {"title": "x", "properties": {"a": {"title": "A", "type": "string"}}}
    L.compact_schema(s)
    assert s["title"] == "x"


def test_merge_commit_doar_titlu_completeaza_body_cu_titlul():
    """Live: Aviator respinge merge_commit_message cu doar `title` („Invalid pull_request object”); cu title+body acceptă."""
    b = L.pr_body("queue", "acme", "api", 7, merge_commit_title="T")
    assert b["pull_request"]["merge_commit_message"] == {"title": "T", "body": "T"}


def test_merge_commit_doar_body_cere_titlu():
    with pytest.raises(InputError, match="merge_commit_title"):
        L.pr_body("queue", "acme", "api", 7, merge_commit_body="B")
