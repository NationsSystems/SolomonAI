# solomon_core/skills/semantic/docintel_reconcile_bid_contract.py
# -------------------------------------------------------------------
# Phase 23.3 — Bid ↔ Contract Reconciliation Micro-Skill (v1.1)
#
# Purpose:
#   • Reconcile structured Excel bid data against contract text
#   • Detect financial overages vs contract limits
#   • Provide deterministic placeholders for scope/obligation mismatches
#   • Produce a strict, machine-readable reconciliation block
#
# This is the FINAL structural bridge required for Jeremy's demo path.
#
# Inputs (arguments):
#   {
#       "contract_text": <plain text of contract>   (required)
#       "bid_structured": <output from skill_import_xlsx> (required)
#   }
#
# Output:
#   {
#       ok: True,
#       structured: {
#           contract_currency_values: [...],
#           contract_max_value,
#           bid_sheet_totals: { sheet: total },
#           bid_grand_total,
#           overage_amount,
#           status: "within_limit" | "over_contract" | "unknown",
#           risks: [...],
#           scope_mismatches: [],
#           obligations_checked: False,
#           evidence: {}
#       },
#       user_output: <plain English summary>
#   }
# -------------------------------------------------------------------

import re
from solomon_core.logger import get_logger

logger = get_logger("skill_docintel_reconcile_bid_contract")


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _extract_currency_values(text: str):
    """
    Extract currency-like values from contract text.
    Examples: $12,500.00, $15750, 15,750.00
    """
    if not text:
        return []

    matches = re.findall(r"\$?\b[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?\b", text)

    cleaned = []
    for m in matches:
        try:
            val = float(m.replace("$", "").replace(",", ""))
            cleaned.append(val)
        except Exception:
            pass

    return cleaned


def _sum_bid_totals(bid_structured: dict):
    totals = bid_structured.get("totals", {}) if isinstance(bid_structured, dict) else {}
    safe_totals = {}

    for k, v in totals.items():
        try:
            safe_totals[k] = float(v)
        except Exception:
            safe_totals[k] = 0.0

    return safe_totals, sum(safe_totals.values())


# ---------------------------------------------------------------
# ✅ Phase-23.3 Reconciliation Entry Point
# ---------------------------------------------------------------

def execute(arguments: dict):

    contract_text = arguments.get("contract_text")
    bid_structured = arguments.get("bid_structured")

    if not isinstance(contract_text, str) or not contract_text.strip():
        return {
            "ok": False,
            "result": "Missing contract text for reconciliation",
            "user_output": "No contract text was supplied for reconciliation."
        }

    if not isinstance(bid_structured, dict) or "totals" not in bid_structured:
        return {
            "ok": False,
            "result": "Missing or invalid structured bid data",
            "user_output": "No valid structured bid data was supplied."
        }

    # -----------------------------------------------------------
    # Extract financials
    # -----------------------------------------------------------

    contract_values = _extract_currency_values(contract_text)
    contract_max = max(contract_values) if contract_values else None

    sheet_totals, bid_grand_total = _sum_bid_totals(bid_structured)

    # -----------------------------------------------------------
    # Reconciliation Logic (v1.1 Financial Core)
    # -----------------------------------------------------------

    if contract_max is None:
        status = "unknown"
        overage = None
        risks = ["No explicit contract price cap detected"]
    else:
        if bid_grand_total > contract_max:
            status = "over_contract"
            overage = round(bid_grand_total - contract_max, 2)
            risks = [f"Bid exceeds contract cap by ${overage}"]
        else:
            status = "within_limit"
            overage = 0.0
            risks = []

    structured = {
        "contract_currency_values": contract_values,
        "contract_max_value": contract_max,
        "bid_sheet_totals": sheet_totals,
        "bid_grand_total": round(bid_grand_total, 2),
        "overage_amount": overage,
        "status": status,
        "risks": risks,

        # ✅ Phase-23.3 placeholders for next upgrade layer
        "scope_mismatches": [],
        "obligations_checked": False,
        "evidence": {},
    }

    # -----------------------------------------------------------
    # User-facing summary
    # -----------------------------------------------------------

    if status == "over_contract":
        summary = f"Bid exceeds contract limit by ${overage}."
    elif status == "within_limit":
        summary = "Bid is within the contract price limit."
    else:
        summary = "Contract limit could not be determined from the document."

    return {
        "ok": True,
        "structured": structured,
        "user_output": summary,
    }
