"""
Org-specific DLP policy: the deterministic "terminology" layer + config loader.

An organisation's notion of "confidential" splits into two parts that are NOT a
document-retrieval (RAG) problem:

  * terminology -- specific sensitive proper nouns (codenames, acquisition
    targets, internal hostnames). Handled here as a fast, deterministic
    watchlist match (call it "Tier 1.5"): exact, case-insensitive, whole-term.
  * policy      -- category rules ("pricing is confidential") that can't be
    enumerated as a word list. Handled by Tier 2 (Gemma) with the policy
    `statement` injected into its prompt (see tier2.build_system_prompt).

Both are sourced from `policy.yaml`, a one-time offline org-onboarding artifact.

Public API:
    load_policy(path=None) -> Policy
    match_watchlist(text, watchlist) -> list[dict]   # [{type,value,start,end}]
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_DEFAULT_POLICY_PATH = Path(__file__).with_name("policy.yaml")


@dataclass
class Policy:
    """Loaded org policy. ``watchlist`` items are ``{"term", "type"}`` dicts."""

    statement: str = ""
    watchlist: list[dict] = field(default_factory=list)


def load_policy(path: str | Path | None = None) -> Policy:
    """
    Load ``policy.yaml`` into a :class:`Policy`.

    Defaults to the ``policy.yaml`` next to this module. A missing file yields an
    empty policy so the detection stack runs fine with no org config at all.
    """
    p = Path(path) if path is not None else _DEFAULT_POLICY_PATH
    if not p.exists():
        return Policy()
    data = yaml.safe_load(p.read_text()) or {}
    watchlist = [w for w in data.get("watchlist", []) if w.get("term")]
    return Policy(statement=data.get("statement", "") or "", watchlist=watchlist)


def match_watchlist(text: str, watchlist: list[dict]) -> list[dict]:
    """
    Find org watchlist terms in ``text`` (case-insensitive, whole-term).

    Returns ``{"type", "value", "start", "end"}`` dicts sorted by start offset,
    mirroring ``tier1.detect``'s shape so downstream redaction is uniform.
    ``value`` preserves the source text's original casing.
    """
    hits: list[dict] = []
    for entry in watchlist:
        term = entry.get("term", "")
        if not term:
            continue
        # \b handles alnum boundaries; the lookarounds stop a term ending in a
        # non-word char (e.g. a hostname's ".internal") from matching mid-token.
        pattern = re.compile(
            r"(?<![\w.-])" + re.escape(term) + r"(?![\w.-])",
            re.IGNORECASE,
        )
        for m in pattern.finditer(text):
            hits.append(
                {
                    "type": entry.get("type", "ORG_SENSITIVE"),
                    "value": m.group(0),
                    "start": m.start(),
                    "end": m.end(),
                }
            )
    hits.sort(key=lambda h: h["start"])
    return hits
