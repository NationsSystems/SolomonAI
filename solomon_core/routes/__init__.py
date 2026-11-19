# ------------------------------------------------------------------
# FILE: __init__.py
# DIRECTORY: solomon_core/routes/
# ------------------------------------------------------------------
# Dynamic Blueprint Loader for Solomon
#
# PURPOSE
#   Discover and register Flask blueprints while ensuring admin-prefixed
#   routes are registered after normal application routes.
#
# LOGGING CONTRACT
#   Startup output must remain ASCII-safe so redirected Windows stdout,
#   service managers, and production log collectors cannot fail on encoding.
# ------------------------------------------------------------------

import importlib
import pkgutil

from flask import Blueprint, Flask


def _resolve_module_blueprint(
    module,
    mod_name,
):
    """
    Resolve the Flask Blueprint exported by a *_bp.py route module.

    Preferred convention is an exact variable match:
      people_bp.py -> people_bp

    A controlled fallback is allowed because older route modules may expose
    a single Blueprint under a non-matching variable name. This keeps route
    discovery resilient without allowing ambiguous automatic registration.
    """

    if hasattr(
        module,
        mod_name,
    ):
        blueprint = getattr(
            module,
            mod_name,
        )

        if isinstance(
            blueprint,
            Blueprint,
        ):
            return blueprint

    exported_names = getattr(
        module,
        "__all__",
        [],
    )

    for exported_name in exported_names:
        blueprint = getattr(
            module,
            exported_name,
            None,
        )

        if isinstance(
            blueprint,
            Blueprint,
        ):
            return blueprint

    discovered_blueprints = []

    for attribute_name in dir(module):
        if attribute_name.startswith("_"):
            continue

        blueprint = getattr(
            module,
            attribute_name,
            None,
        )

        if isinstance(
            blueprint,
            Blueprint,
        ):
            discovered_blueprints.append(
                blueprint
            )

    if len(discovered_blueprints) == 1:
        return discovered_blueprints[0]

    return None


def _register_blueprint(
    app,
    blueprint,
    discovered_name,
    discovered,
):
    """
    Register a blueprint once and keep startup logs deterministic.
    """

    if blueprint.name in app.blueprints:
        discovered.append(
            f"{discovered_name} (already registered)"
        )
        return

    app.register_blueprint(
        blueprint
    )
    discovered.append(
        discovered_name
    )


def _discover_and_register(
    app,
    package_name,
    package_path,
    discovered,
    deferred_admin,
):
    """
    Scan one package for *_bp.py modules and register their blueprints.

    Admin-prefixed routes are deferred until all normal routes have been
    registered.
    """

    for _, mod_name, is_pkg in pkgutil.iter_modules(
        package_path
    ):
        if (
            is_pkg
            or not mod_name.endswith("_bp")
        ):
            continue

        full_mod_name = (
            f"{package_name}.{mod_name}"
        )
        module = importlib.import_module(
            full_mod_name
        )
        blueprint = _resolve_module_blueprint(
            module,
            mod_name,
        )

        if not blueprint:
            print(
                "[routes][WARNING] "
                f"Skipped {mod_name}: "
                "no usable Flask Blueprint found."
            )
            continue

        prefix = getattr(
            blueprint,
            "url_prefix",
            None,
        ) or ""

        if prefix.startswith("/admin"):
            deferred_admin.append(
                blueprint
            )
            discovered.append(
                f"{blueprint.name} (deferred)"
            )
            continue

        _register_blueprint(
            app,
            blueprint,
            blueprint.name,
            discovered,
        )

    return discovered


def register_all_blueprints(
    app: Flask,
    package_name: str = __name__,
    package_path=None,
):
    """
    Import and register Solomon route blueprints.

    Registration order:
      1. Primary route-package blueprints
      2. Blueprint modules inside route subpackages
      3. Manually registered hflo_review_api
      4. Manually registered task_api
      5. Deferred admin-prefixed blueprints
    """

    if package_path is None:
        package = importlib.import_module(
            package_name
        )
        package_path = package.__path__

    discovered = []
    deferred_admin = []

    _discover_and_register(
        app,
        package_name,
        package_path,
        discovered,
        deferred_admin,
    )

    for _, sub_name, is_pkg in pkgutil.iter_modules(
        package_path
    ):
        if not is_pkg:
            continue

        subpackage_name = (
            f"{package_name}.{sub_name}"
        )
        subpackage = importlib.import_module(
            subpackage_name
        )

        if hasattr(
            subpackage,
            "__path__",
        ):
            _discover_and_register(
                app,
                subpackage_name,
                subpackage.__path__,
                discovered,
                deferred_admin,
            )

    try:
        from solomon_core.routes.hflo_review_api import (
            hflo_review_api,
        )

        _register_blueprint(
            app,
            hflo_review_api,
            "hflo_review_api",
            discovered,
        )
    except Exception as exc:
        print(
            "[routes][ERROR] "
            "Failed to load hflo_review_api: "
            f"{exc}"
        )

    try:
        from solomon_core.routes.task_api import (
            task_api,
        )

        _register_blueprint(
            app,
            task_api,
            "task_api",
            discovered,
        )
    except Exception as exc:
        print(
            "[routes][ERROR] "
            "Failed to load task_api: "
            f"{exc}"
        )

    for blueprint in deferred_admin:
        if blueprint.name in app.blueprints:
            discovered.append(
                f"{blueprint.name} (already registered)"
            )
            continue

        app.register_blueprint(
            blueprint
        )

    if deferred_admin:
        deferred_names = ", ".join(
            blueprint.name
            for blueprint in deferred_admin
        )
        print(
            "[routes][LOCKED] "
            "Admin blueprints registered last: "
            f"{deferred_names}"
        )

    registered_names = (
        ", ".join(discovered)
        or "None"
    )
    print(
        "[routes][OK] "
        "Registered blueprints: "
        f"{registered_names}"
    )

    return discovered