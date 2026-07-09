"""Tests for the org policy layer: watchlist matcher + policy.yaml loader."""
import policy


# --- Watchlist matcher (Tier 1.5): deterministic org-specific term detection ---

_WATCHLIST = [
    {"term": "Project Falcon", "type": "PROJECT_CODENAME"},
    {"term": "Acme Corp", "type": "ACQUISITION"},
]


def test_match_finds_term_with_exact_span():
    text = "The Project Falcon launch slips to Q3."
    hits = policy.match_watchlist(text, _WATCHLIST)
    assert len(hits) == 1
    hit = hits[0]
    assert hit["type"] == "PROJECT_CODENAME"
    assert hit["value"] == "Project Falcon"
    # Offsets slice back to the exact matched text.
    assert text[hit["start"]:hit["end"]] == "Project Falcon"


def test_match_is_case_insensitive_but_preserves_original_casing():
    text = "heads up: project falcon is confidential"
    hits = policy.match_watchlist(text, _WATCHLIST)
    assert len(hits) == 1
    # Matched case-insensitively, but value reflects the source text.
    assert hits[0]["value"] == "project falcon"
    assert hits[0]["type"] == "PROJECT_CODENAME"


def test_match_respects_word_boundaries():
    # "Acme Corp" must not match inside "Acme Corporation".
    text = "We love Acme Corporations everywhere."
    assert policy.match_watchlist(text, _WATCHLIST) == []


def test_match_finds_multiple_distinct_terms():
    text = "Project Falcon and the Acme Corp deal are both secret."
    types = {h["type"] for h in policy.match_watchlist(text, _WATCHLIST)}
    assert types == {"PROJECT_CODENAME", "ACQUISITION"}


def test_match_empty_watchlist_returns_nothing():
    assert policy.match_watchlist("Project Falcon", []) == []


# --- policy.yaml loader ---------------------------------------------------


def test_load_default_policy_has_statement_and_watchlist():
    p = policy.load_policy()
    assert p.statement.strip(), "demo policy statement should be non-empty"
    terms = {w["term"] for w in p.watchlist}
    assert "Project Falcon" in terms
    # Every watchlist entry carries a type.
    assert all(w.get("type") for w in p.watchlist)


def test_load_missing_policy_returns_empty_policy():
    p = policy.load_policy("/nonexistent/path/policy.yaml")
    assert p.statement == ""
    assert p.watchlist == []
