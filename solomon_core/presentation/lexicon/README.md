# Solomon Lexicon Subsystem

**Location:** `solomon_core/presentation/lexicon/`  
**Status:** Phase 42 — Controlled Construction (NON-AUTHORITATIVE, SASE-SEALED)

---

## Purpose

The Lexicon subsystem is a **sealed, non-authoritative presentation sub-machine**
responsible solely for controlling **how Solomon communicates**, never **what Solomon decides**.

It operates entirely within the **Solomon Authority Safety Envelope (SASE)** and exists to:

- Normalize tone and framing
- Preserve epistemic honesty
- Prevent accidental authority through language
- Improve clarity, structure, and professional presentation

Lexicon is **presentation-only** and **deterministic**.

---

## Authority Posture (NON-NEGOTIABLE)

The Lexicon subsystem:

- ❌ Does **not** decide
- ❌ Does **not** recommend
- ❌ Does **not** prioritize or rank
- ❌ Does **not** evaluate quality or importance
- ❌ Does **not** infer intent or meaning
- ❌ Does **not** influence execution, planning, or autonomy
- ❌ Does **not** modify system state or memory

It may **only** apply deterministic, presentation-only transformations
to finalized response payloads.

Any deviation constitutes a **SASE violation**.

---

## Governing Doctrine (AUTHORITATIVE)

All Lexicon behavior and structure MUST conform to the following locked documents:

- `docs/SASE_LAWS.md`
- `Solomon_Phase_41_Charter.docx`
- Lexicon v2 Design Document
- `docs/ideology/Epistemic_Output_Typing.md`
- `docs/ideology/Meta_Observation_Doctrine.md`

These documents override all local interpretation.

---

## Subsystem Boundaries

### Allowed Inputs (READ-ONLY)
- Finalized response payloads
- Explicit epistemic signals (evidence state, scope flags, task type)

### Allowed Outputs
- Presentation-only modifications to `user_output`
- Optional presentation metadata for auditability

### Forbidden Interactions
- Planner, cognition, autonomy, or execution layers
- Memory, databases, or persistence layers
- Tool invocation or side effects
- Signal or event emission
- Cross-layer imports

---

## Phase 42 Construction Scope

Phase 42 authorizes **controlled realization** of the Lexicon subsystem
under the following constraints:

- Contracts, policy, and guards are **locked**
- Implementation must be:
  - Deterministic
  - Stateless
  - Rule-driven
  - Fully auditable
- Guards must **fail closed**
- No experimental, provisional, or hidden logic

Lexicon **may be integrated only via explicit orchestrator invocation**.

---

## Implementation Order (AUTHORITATIVE)

1. Interface contracts (`contracts.py`) — **LOCKED**
2. Policy declarations (`policy.py`) — **LOCKED**
3. Guardrails & invariants (`guards.py`) — **LOCKED**
4. Deterministic presentation implementation (Phase 42 scope)
5. Orchestrator-controlled integration

No step may be skipped or reordered.

---

## Canonical Statement

> **The Lexicon subsystem controls expression, not intent.**  
> **It is sealed, deterministic, and non-authoritative.**  
> **Authority remains singular and untouched.**

---

**Phase 42 Status:** ACTIVE — CONTROLLED CONSTRUCTION
