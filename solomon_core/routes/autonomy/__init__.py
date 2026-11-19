# solomon_core/routes/autonomy/__init__.py
# ---------------------------------------------------------------
# Namespace package for autonomy-related blueprints (UI + API)
# ---------------------------------------------------------------

from .autonomy_status_bp import autonomy_status_bp
from .autonomy_ui_bp import autonomy_ui_bp

__all__ = ["autonomy_status_bp", "autonomy_ui_bp"]
