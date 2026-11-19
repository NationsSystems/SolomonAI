"""
solomon_core.planner package — Phase 21 (Model A)

This package consolidates:
- Strict planner (Phase 21)
- Strategic planner (Phase 18/19)
"""

# Strict planner (Phase 21)
from .planner_backend import *      # noqa: F401,F403
from .planner_interface import *    # noqa: F401,F403
from .planner_action_router import *  # noqa: F401,F403
from .plan_validator import *       # noqa: F401,F403

# Strategic planner (Phase 18/19)
try:
    from .strategic_planner import *       # noqa: F401,F403
    from .strategic_memory import *        # noqa: F401,F403
    from .plan_scoring_engine import *     # noqa: F401,F403
    from .plan_simulation_engine import *  # noqa: F401,F403
except ImportError:
    # If any of these are missing, the rest of the package should still import cleanly.
    pass
