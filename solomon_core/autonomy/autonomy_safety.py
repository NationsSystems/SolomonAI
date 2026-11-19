# autonomy_safety.py — Phase 16 Step 1
# -------------------------------------------------------------
# SYSTEM SAFETY CHECKS
#
# Purpose:
#   Encapsulate all CPU, disk, and general resource checks
#   used by autonomy mode selection.
#
# Notes:
#   • Pure safety logic only
#   • No database access
#   • No autonomy decision logic
#   • Used by strict_autonomy_controller + mode selector
# -------------------------------------------------------------

import psutil
from config import settings


# -------------------------------------------------------------
# Pull thresholds from config
# -------------------------------------------------------------
CPU_HALT_THRESHOLD = settings.AUTONOMY_SETTINGS["CPU_HALT_THRESHOLD"]
DISK_HALT_THRESHOLD = settings.AUTONOMY_SETTINGS["DISK_HALT_THRESHOLD"]


# -------------------------------------------------------------
# SYSTEM RESOURCE CHECK
# -------------------------------------------------------------
def system_safe_to_run():
    """
    Returns:
        (ok: bool, reason: str | None)

    Evaluates CPU and disk usage thresholds.
    Called by autonomy mode selector before any strategic/operational decision.
    """

    cpu = psutil.cpu_percent(interval=0.1)
    disk = psutil.disk_usage("/").percent

    if cpu > CPU_HALT_THRESHOLD:
        return False, f"CPU usage too high ({cpu}%)"

    if disk > DISK_HALT_THRESHOLD:
        return False, f"Disk usage too high ({disk}%)"

    return True, None
