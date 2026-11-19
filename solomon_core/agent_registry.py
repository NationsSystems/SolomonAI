# solomon_core/agent_registry.py
# ---------------------------------------------------------------
# Phase 27 — Agent Capability Registry (Read-Only)
#
# PURPOSE:
#   • Load and expose declarative agent capability metadata
#   • Enforce read-only access to agent definitions
#   • Provide a single integration point for future gating logic
#
# GUARANTEES:
#   • No routing
#   • No decision making
#   • No inference
#   • No regex
#   • No keyword lists
#   • No side effects
#   • Safe to import anywhere
#
# DATA SOURCE:
#   agent_capabilities.json (external, declarative)
#
# NOTES:
#   • Supports stable alias resolution for presentation-friendly names
#     (e.g., "SolomonAI Estimating Agent") without introducing logic/routing.
# ---------------------------------------------------------------

import json
import os
from typing import Dict, List, Optional

# ---------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------

_AGENT_CAPABILITIES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "agent_capabilities.json",
)

_loaded = False
_load_error: Optional[Exception] = None
_registry: Dict[str, Dict] = {}

# ---------------------------------------------------------------
# Canonical Agent IDs + Aliases (Deterministic)
# ---------------------------------------------------------------
# Canonical registry IDs are the keys inside agent_capabilities.json.
# Aliases are presentation or code-friendly names that resolve to a canonical ID.
ESTIMATING_AGENT_ID = "estimating"  # Canonical ID in JSON today

_AGENT_ALIASES = {
    # Preferred external phrasing
    "solomonai estimating agent": ESTIMATING_AGENT_ID,

    # Internal naming options (allowed)
    "estimatingagent": ESTIMATING_AGENT_ID,
    "estimating_agent": ESTIMATING_AGENT_ID,
}


def _normalize_agent_key(value: str) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().lower().split())


def resolve_agent_id(agent_id_or_alias: str) -> Optional[str]:
    """
    Resolve an agent ID or alias to a canonical agent ID.

    Deterministic mapping only. No heuristics. No inference.
    """
    if not agent_id_or_alias:
        return None

    key = _normalize_agent_key(agent_id_or_alias)
    if not key:
        return None

    # Direct hit
    if agent_exists(key):
        return key

    # Alias hit
    return _AGENT_ALIASES.get(key)


# ---------------------------------------------------------------
# Internal loader (fail-closed)
# ---------------------------------------------------------------

def _load_registry():
    global _loaded, _load_error, _registry

    if _loaded:
        return

    try:
        if not os.path.isfile(_AGENT_CAPABILITIES_FILE):
            raise FileNotFoundError(
                f"Agent capability file not found: {_AGENT_CAPABILITIES_FILE}"
            )

        with open(_AGENT_CAPABILITIES_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)

        agents = payload.get("agents")
        if not isinstance(agents, dict):
            raise ValueError("Invalid agent_capabilities.json format: missing 'agents'")

        _registry = agents
        _loaded = True
        _load_error = None  # clear any prior failure

    except Exception as e:
        _load_error = e
        _registry = {}
        _loaded = False


# ---------------------------------------------------------------
# Public Read-Only API
# ---------------------------------------------------------------

def registry_available() -> bool:
    """Return True if the agent registry loaded successfully."""
    _load_registry()
    return _loaded


def registry_error() -> Optional[Exception]:
    """Return the registry load error, if any."""
    _load_registry()
    return _load_error


def list_agents() -> List[str]:
    """Return a list of registered agent identifiers."""
    _load_registry()
    return sorted(_registry.keys())


def agent_exists(agent_id: str) -> bool:
    """Return True if the agent ID exists."""
    if not agent_id:
        return False
    _load_registry()
    return agent_id in _registry


def get_agent(agent_id: str) -> Optional[Dict]:
    """
    Return a COPY of the raw agent definition.

    IMPORTANT:
    • Returned data must be treated as read-only by callers
    • No normalization or inference occurs here
    """
    if not agent_id:
        return None

    _load_registry()
    agent = _registry.get(agent_id)
    if not isinstance(agent, dict):
        return None

    # Shallow copy prevents accidental mutation of in-memory registry
    return dict(agent)


def get_agent_by_name(agent_id_or_alias: str) -> Optional[Dict]:
    """
    Convenience: resolve alias -> canonical id -> return agent.

    Deterministic mapping only.
    """
    canon = resolve_agent_id(agent_id_or_alias)
    if not canon:
        return None
    return get_agent(canon)


def get_agent_domains(agent_id: str) -> List[str]:
    """Return the domains an agent is allowed to operate in."""
    agent = get_agent(agent_id)
    if not agent:
        return []
    domains = agent.get("domains", [])
    return list(domains) if isinstance(domains, list) else []


def get_allowed_actions(agent_id: str) -> List[str]:
    """Return actions explicitly allowed for this agent."""
    agent = get_agent(agent_id)
    if not agent:
        return []
    actions = agent.get("allowed_actions", [])
    return list(actions) if isinstance(actions, list) else []


def get_forbidden_actions(agent_id: str) -> List[str]:
    """Return actions explicitly forbidden for this agent."""
    agent = get_agent(agent_id)
    if not agent:
        return []
    actions = agent.get("forbidden_actions", [])
    return list(actions) if isinstance(actions, list) else []


# ---------------------------------------------------------------
# Dev-Only Guardrail
# ---------------------------------------------------------------

def _assert_no_mutators():
    """
    Ensure this module exposes no write paths.
    Not executed automatically.
    """
    forbidden = {"set", "add", "update", "delete", "register", "modify"}
    for name in globals():
        for f in forbidden:
            if f in name.lower():
                raise RuntimeError(
                    f"Forbidden mutator detected in agent registry: {name}"
                )


__all__ = [
    "ESTIMATING_AGENT_ID",
    "resolve_agent_id",
    "get_agent_by_name",
    "registry_available",
    "registry_error",
    "list_agents",
    "agent_exists",
    "get_agent",
    "get_agent_domains",
    "get_allowed_actions",
    "get_forbidden_actions",
]
