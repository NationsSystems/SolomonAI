# solomon_core/domain_registry.py
# ---------------------------------------------------------------
# Phase 27 — Domain Registry Integration (Read-Only Boundary)
#
# PURPOSE:
#   • Provide a single, safe integration point between solomon_core
#     and solomon_domains.
#   • Expose domain identifiers in a read-only fashion.
#   • Prevent domain logic leakage into core execution.
#
# GUARANTEES:
#   • No routing logic
#   • No keyword lists
#   • No regex
#   • No LLM calls
#   • No side effects
#   • Safe to import anywhere
# ---------------------------------------------------------------

from typing import List, Optional

# NOTE:
# Import is intentionally shallow.
# solomon_domains must NEVER import solomon_core.
try:
    from solomon_domains import registry as _domain_registry
except Exception as e:
    _domain_registry = None
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None


# ---------------------------------------------------------------
# Public API (Read-Only)
# ---------------------------------------------------------------

def registry_available() -> bool:
    """Return True if the domain registry loaded successfully."""
    return _domain_registry is not None


def registry_error() -> Optional[Exception]:
    """Return the import error if the registry failed to load."""
    return _IMPORT_ERROR


def list_domains() -> List[str]:
    """
    Return a list of registered domain identifiers.

    Side-effect free.
    """
    if not _domain_registry:
        return []

    domains = getattr(_domain_registry, "ALL_DOMAINS", None)
    if isinstance(domains, set):
        return sorted(domains)

    return []


def domain_exists(domain_id: str) -> bool:
    """
    Return True if the domain ID exists in the registry.
    """
    if not _domain_registry or not domain_id:
        return False

    validator = getattr(_domain_registry, "is_valid_domain", None)
    if callable(validator):
        return bool(validator(domain_id))

    return False


# ---------------------------------------------------------------
# Internal Contract Assertion (Dev-Only)
# ---------------------------------------------------------------

def _assert_read_only():
    """
    Sanity check to ensure registry does not expose mutators.
    This is intentionally NOT executed automatically.
    """
    if not _domain_registry:
        return

    forbidden = {"register", "add", "update", "delete", "mutate"}
    for name in dir(_domain_registry):
        lname = name.lower()
        for f in forbidden:
            if f in lname:
                raise RuntimeError(
                    f"Forbidden mutator detected in domain registry: {name}"
                )


__all__ = [
    "registry_available",
    "registry_error",
    "list_domains",
    "domain_exists",
]
