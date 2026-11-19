# -------------------------------------------------------------------
# FILE: webui/command_console_registry.py
# DIRECTORY: webui/
# -------------------------------------------------------------------
# Backend-owned command console department registry.
# The browser renders this truth; it does not define it.
# -------------------------------------------------------------------

from copy import deepcopy


def _function(icon, title, status, text):
    return {
        "icon": icon,
        "title": title,
        "status": status,
        "text": text,
    }


_DEFAULT_DEPARTMENT = {
    "icon": "dashboard",
    "status": "PLANNED",
    "purpose": "This construction console area is part of the planned operating map.",
    "functions": [
        _function(
            "view_module",
            "Function Map",
            "PLANNED",
            "This area will receive defined console functions as the product expands.",
        ),
        _function(
            "rule",
            "Department Checks",
            "PLANNED",
            "Checks will help identify missing information, risks, and required follow-up.",
        ),
        _function(
            "assignment",
            "Department Records",
            "PLANNED",
            "Records will preserve the work, findings, decisions, and handoff context.",
        ),
        _function(
            "psychology",
            "SolomonAI Guidance",
            "PLANNED",
            "SolomonAI will guide users inside this department when the area is activated.",
        ),
    ],
}


CONSTRUCTION_DEPARTMENTS = {
    "preconstruction": {
        "icon": "assignment",
        "status": "LIVE",
        "purpose": (
            "Preconstruction review, bid decisions, proposal review, scope risk, "
            "missing information, clarification tracking, and handoff preparation."
        ),
        "functions": [
            _function(
                "assignment",
                "Bid & Scope Review",
                "LIVE",
                "Reviews bid, proposal, scope, exclusion, qualification, commercial, risk, and handoff language.",
            ),
            _function(
                "folder_open",
                "Saved Review Records",
                "IN DEVELOPMENT",
                "Stores completed review records, prior findings, and generated review outputs.",
            ),
            _function(
                "compare_arrows",
                "Bid Comparison / Leveling",
                "IN DEVELOPMENT",
                "Compares proposals by price, scope, exclusions, missing information, qualifications, and risk.",
            ),
            _function(
                "help_center",
                "Clarification Tracker",
                "PLANNED",
                "Tracks open questions, bidder responses, unresolved items, and decision blockers.",
            ),
            _function(
                "outbox",
                "Handoff Packet",
                "PLANNED",
                "Prepares reviewed bid information for award, project management, or operations handoff.",
            ),
            _function(
                "description",
                "Document & Addenda Review",
                "PLANNED",
                "Tracks bid documents, addenda, proposal files, missing document issues, and review readiness.",
            ),
        ],
    },
    "preconstruction_review": {
        "icon": "assignment",
        "status": "LIVE",
        "purpose": (
            "Live Bid & Scope Review workflow for bid, proposal, scope, risk, "
            "commercial language, and handoff review."
        ),
        "functions": [
            _function(
                "assignment",
                "Bid & Scope Review",
                "LIVE",
                "Reviews bid, proposal, scope, exclusion, qualification, commercial, risk, and handoff language.",
            ),
            _function(
                "upload_file",
                "Upload Review Material",
                "LIVE",
                "Accepts bid, proposal, scope, exclusion, assumption, alternate, or responsibility language.",
            ),
            _function(
                "fact_check",
                "Solomon Findings",
                "LIVE",
                "Produces review findings that support risk review, clarification, and handoff decisions.",
            ),
            _function(
                "folder_open",
                "Saved Review Records",
                "IN DEVELOPMENT",
                "Preserves completed review outputs and prior findings for later review.",
            ),
        ],
    },
    "management": {
        "icon": "business_center",
        "status": "PLANNED",
        "purpose": (
            "Project operations after award, including handoff intake, project controls, "
            "open issues, decisions, work orders, closeout readiness, and operating visibility."
        ),
        "functions": [
            _function(
                "move_to_inbox",
                "Project Handoff Intake",
                "PLANNED",
                "Receives reviewed bid records, known exclusions, risks, assumptions, and open items from Precon.",
            ),
            _function(
                "report_problem",
                "Open Issues Log",
                "PLANNED",
                "Tracks project issues that need ownership, follow-up, escalation, or resolution.",
            ),
            _function(
                "warning",
                "Project Risk Register",
                "PLANNED",
                "Preserves known project risks carried forward from reviews, decisions, field activity, or project events.",
            ),
            _function(
                "fact_check",
                "Decision Log",
                "PLANNED",
                "Records important project decisions, supporting evidence, responsible parties, and follow-up requirements.",
            ),
            _function(
                "work",
                "Work Orders",
                "PLANNED",
                "Tracks assigned work, responsible parties, status, completion notes, and related records.",
            ),
            _function(
                "summarize",
                "Project Summaries",
                "PLANNED",
                "Creates operating summaries for project status, open issues, risks, and recent activity.",
            ),
        ],
    },
    "field": {
        "icon": "engineering",
        "status": "PLANNED",
        "purpose": (
            "Jobsite activity, field reports, daily records, site conditions, "
            "manpower notes, work progress, and field issue tracking."
        ),
        "functions": [
            _function(
                "assignment",
                "Field Reports",
                "PLANNED",
                "Captures field activity, jobsite conditions, work performed, issues observed, and status updates.",
            ),
            _function(
                "event_note",
                "Daily Logs",
                "PLANNED",
                "Records daily jobsite notes, manpower, weather, deliveries, delays, and work progress.",
            ),
            _function(
                "location_on",
                "Site Issue Log",
                "PLANNED",
                "Tracks jobsite issues, locations, responsible parties, status, and resolution.",
            ),
            _function(
                "groups",
                "Crew / Manpower Notes",
                "PLANNED",
                "Records crews, labor activity, manpower changes, and field responsibility.",
            ),
            _function(
                "photo_camera",
                "Field Photos",
                "PLANNED",
                "Attaches jobsite photos to records, issues, observations, completion notes, or supporting evidence.",
            ),
            _function(
                "timer_off",
                "Delay / Obstruction Notes",
                "PLANNED",
                "Tracks delays, access issues, weather impacts, work blockers, and obstruction notes.",
            ),
        ],
    },
    "quality": {
        "icon": "verified",
        "status": "PLANNED",
        "purpose": (
            "Quality control, inspections, deficiencies, corrective actions, "
            "punch items, installation review, and quality closeout."
        ),
        "functions": [
            _function(
                "checklist",
                "Quality Inspections",
                "PLANNED",
                "Records inspections, outcomes, pass/fail status, review notes, and follow-up requirements.",
            ),
            _function(
                "error_outline",
                "Deficiency Log",
                "PLANNED",
                "Tracks quality deficiencies, responsible parties, due dates, correction status, and supporting evidence.",
            ),
            _function(
                "build_circle",
                "Corrective Actions",
                "PLANNED",
                "Tracks corrective work required to close quality findings or resolve deficiencies.",
            ),
            _function(
                "check_box",
                "Punch Items",
                "PLANNED",
                "Manages punch list items, locations, responsible parties, completion status, and closeout readiness.",
            ),
            _function(
                "inventory_2",
                "Material / Install Review",
                "PLANNED",
                "Reviews materials, installation concerns, product issues, compliance notes, and approval concerns.",
            ),
            _function(
                "verified_user",
                "Quality Closeout",
                "PLANNED",
                "Preserves quality completion records before project handoff or closeout.",
            ),
        ],
    },
    "safety": {
        "icon": "health_and_safety",
        "status": "PLANNED",
        "purpose": (
            "Safety observations, incidents, hazard notes, corrective actions, "
            "toolbox talks, and compliance records."
        ),
        "functions": [
            _function(
                "visibility",
                "Safety Observations",
                "PLANNED",
                "Records jobsite safety observations, concerns, responsible parties, and follow-up items.",
            ),
            _function(
                "report_problem",
                "Incident Records",
                "PLANNED",
                "Captures incidents, near misses, involved parties, response notes, and review history.",
            ),
            _function(
                "campaign",
                "Toolbox Talks",
                "PLANNED",
                "Tracks safety meetings, topics, attendance, and communication records.",
            ),
            _function(
                "warning",
                "Hazard Notes",
                "PLANNED",
                "Records known hazards, locations, severity, mitigation steps, and responsibility.",
            ),
            _function(
                "assignment_turned_in",
                "Safety Corrective Actions",
                "PLANNED",
                "Tracks safety corrections, responsible parties, due dates, and completion status.",
            ),
            _function(
                "policy",
                "Compliance Records",
                "PLANNED",
                "Preserves required safety documentation, review notes, and compliance history.",
            ),
        ],
    },
    "communication": {
        "icon": "hub",
        "status": "PLANNED",
        "purpose": (
            "Coordination between trades, scopes, documents, RFIs, conflicts, "
            "responsibility boundaries, meeting minutes, and action items."
        ),
        "functions": [
            _function(
                "hub",
                "Coordination Issues",
                "PLANNED",
                "Tracks trade conflicts, responsibility gaps, document conflicts, and unresolved coordination items.",
            ),
            _function(
                "contact_support",
                "RFI Tracker",
                "PLANNED",
                "Tracks questions, responses, responsible parties, open dates, closed dates, and status.",
            ),
            _function(
                "compare",
                "Scope Conflict Log",
                "PLANNED",
                "Preserves conflicts between proposal language, drawings, specs, contracts, and responsibilities.",
            ),
            _function(
                "account_tree",
                "Trade Responsibility Map",
                "PLANNED",
                "Maps which trade, vendor, or party owns each scope item or unresolved responsibility.",
            ),
            _function(
                "notes",
                "Meeting Minutes",
                "PLANNED",
                "Records meeting topics, decisions, attendees, action items, open questions, and follow-up.",
            ),
            _function(
                "checklist_rtl",
                "Action Items",
                "PLANNED",
                "Tracks assigned coordination tasks, due dates, responsible parties, and completion status.",
            ),
        ],
    },
    "documents": {
        "icon": "folder_copy",
        "status": "PLANNED",
        "purpose": (
            "Shared construction document center for files, addenda, proposals, "
            "contracts, packets, revisions, closeout documents, and supporting records."
        ),
        "functions": [
            _function(
                "folder_copy",
                "Document Sets",
                "PLANNED",
                "Organizes drawings, specs, addenda, proposals, contracts, and project files.",
            ),
            _function(
                "inventory_2",
                "Document Packets",
                "PLANNED",
                "Groups related documents into bid packets, handoff packets, closeout packets, or review packets.",
            ),
            _function(
                "note_add",
                "Addenda",
                "PLANNED",
                "Tracks addenda received, acknowledged, reviewed, and connected to affected records.",
            ),
            _function(
                "request_quote",
                "Proposal Files",
                "IN DEVELOPMENT",
                "Stores subcontractor and vendor proposals connected to bid review records.",
            ),
            _function(
                "fact_check",
                "Closeout Documents",
                "PLANNED",
                "Tracks closeout files, missing closeout requirements, submitted documents, and completion status.",
            ),
            _function(
                "search",
                "Document Search",
                "PLANNED",
                "Searches project records, files, review outputs, document sets, and supporting evidence.",
            ),
        ],
    },
    "finance": {
        "icon": "payments",
        "status": "PLANNED",
        "purpose": (
            "Financial visibility, job cost review, AP/AR references, invoices, "
            "billing, change exposure, budget exceptions, and financial handoff notes."
        ),
        "functions": [
            _function(
                "monitoring",
                "Job Cost Review",
                "PLANNED",
                "Tracks cost concerns, budget exposure, financial review items, and project-level cost visibility.",
            ),
            _function(
                "receipt_long",
                "Vendor Invoices / AP",
                "PLANNED",
                "References vendor invoices, payment status, review notes, exceptions, and approval concerns.",
            ),
            _function(
                "request_quote",
                "Billing / AR",
                "PLANNED",
                "Tracks billing records, customer payment status, payment issues, and follow-up items.",
            ),
            _function(
                "price_change",
                "Change Cost Review",
                "PLANNED",
                "Reviews potential cost changes, exposure, supporting notes, and decision status.",
            ),
            _function(
                "difference",
                "Budget Exceptions",
                "PLANNED",
                "Tracks items that differ from budget, estimate, contract, approved scope, or prior assumptions.",
            ),
            _function(
                "outbox",
                "Financial Handoff Notes",
                "PLANNED",
                "Preserves finance-related notes for project management, accounting, or leadership review.",
            ),
        ],
    },
    "people": {
        "icon": "groups",
        "status": "PLANNED",
        "purpose": (
            "Personnel, roles, onboarding, training, assignments, "
            "responsibility mapping, and company participation."
        ),
        "functions": [
            _function(
                "badge",
                "Personnel Directory",
                "PLANNED",
                "Tracks people connected to the company, departments, projects, roles, and records.",
            ),
            _function(
                "assignment_ind",
                "Role Assignments",
                "PLANNED",
                "Assigns users or personnel to department roles, project roles, and workflow responsibilities.",
            ),
            _function(
                "groups",
                "Department Memberships",
                "PLANNED",
                "Connects personnel to Precon, Ops, Field, Quality, Safety, Finance, Admin, and other departments.",
            ),
            _function(
                "person_add",
                "Onboarding",
                "PLANNED",
                "Tracks onboarding steps, required setup, documents, access, training, and role readiness.",
            ),
            _function(
                "school",
                "Training / Knowledge Base",
                "PLANNED",
                "Stores training materials, process knowledge, role guidance, and required learning records.",
            ),
            _function(
                "person_pin",
                "Responsibility Notes",
                "PLANNED",
                "Records who owns reviews, decisions, issues, clarifications, handoffs, and follow-up work.",
            ),
        ],
    },
}


def get_command_department(module_id, module=None):
    clean_id = str(module_id or "home").strip().lower()
    definition = deepcopy(CONSTRUCTION_DEPARTMENTS.get(clean_id, _DEFAULT_DEPARTMENT))

    return {
        "id": clean_id,
        "label": (module or {}).get("label", "Construction Module"),
        "nav_label": (module or {}).get("nav_label", "Module"),
        "path": (module or {}).get("path", "#"),
        "module_status": (module or {}).get("status", "building"),
        "description": (module or {}).get("description", definition["purpose"]),
        "icon": definition["icon"],
        "status": definition["status"],
        "purpose": definition["purpose"],
        "functions": definition["functions"],
    }