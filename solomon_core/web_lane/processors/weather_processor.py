# ------------------------------------------------------------------
# FILE: solomon_core/web_lane/processors/weather_processor.py
# ------------------------------------------------------------------
# WEATHER PROCESSOR
#
# Purpose:
#   Organize weather bullet points into deterministic sections
#   matching the Web Lane presentation gold standard.
#
# Design constraints:
#   • Deterministic
#   • No keyword inference
#   • No semantic guessing
#   • Pure positional organization
#
# Output contract:
#   {
#       "summary": "...",
#       "sections": [
#           {"title": "...", "items": [...]}
#       ]
#   }
# ------------------------------------------------------------------


def process_weather(summary: str, points: list[str]):

    if not isinstance(points, list):
        points = []

    clean_points = []

    for p in points:

        if not isinstance(p, str):
            continue

        s = p.strip()

        if not s:
            continue

        clean_points.append(s)

    # ------------------------------------------------------------------
    # Deterministic partition
    # ------------------------------------------------------------------
    # 0-1 → current conditions
    # 2-3 → today's forecast
    # 4-6 → extended outlook
    # ------------------------------------------------------------------

    current_items = clean_points[:2]
    today_items = clean_points[2:4]
    outlook_items = clean_points[4:7]

    # ------------------------------------------------------------------
    # Narrative summary (ONLY the summary)
    # ------------------------------------------------------------------

    narrative_summary = ""

    if summary and isinstance(summary, str):
        narrative_summary = summary.strip()

    # ------------------------------------------------------------------
    # Section construction
    # ------------------------------------------------------------------

    sections = []

    if current_items:
        sections.append(
            {
                "title": "Current conditions",
                "items": current_items,
            }
        )

    if today_items:
        sections.append(
            {
                "title": "Today's forecast",
                "items": today_items,
            }
        )

    if outlook_items:
        sections.append(
            {
                "title": "Extended outlook",
                "items": outlook_items,
            }
        )

    return {
        "summary": narrative_summary,
        "sections": sections
    }