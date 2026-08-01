import importlib.util
import logging
import os
import sys
import types

logger = logging.getLogger(__name__)


def _start_new_relic() -> object | None:
    """Initialise the APM agent, returning its WSGI wrapper (or None).

    Must run before app.py is imported below: the agent instruments Flask,
    smtplib and googleapiclient through import hooks, so anything already
    imported is never traced.

    Every failure here is swallowed. This module is the entry point for the
    whole API, so an exception — a missing package, an unreadable log path, a
    rejected licence key — would take every form on the site down to gain
    monitoring. Degrading to an un-instrumented app is always the better trade.
    Configuration comes from the environment (NEW_RELIC_LICENSE_KEY,
    NEW_RELIC_APP_NAME), set per app in cPanel, so no key lives in the repo.
    """
    if not os.environ.get("NEW_RELIC_LICENSE_KEY", "").strip():
        return None

    try:
        import newrelic.agent

        newrelic.agent.initialize()
        return newrelic.agent.WSGIApplicationWrapper
    except Exception:
        logger.exception("New Relic agent failed to start; continuing without it")
        return None


_new_relic_wrapper = _start_new_relic()

project_home = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.dirname(project_home)
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

# In some deployments (for example "api_test"), modules still import via
# the "api" package name. Create a package alias that points at the current
# deployment directory so imports resolve to local code, not sibling folders.
if os.path.basename(project_home) != "api":
    package_name = "api"
    package = types.ModuleType(package_name)
    package.__file__ = os.path.join(project_home, "__init__.py")
    package.__path__ = [project_home]
    sys.modules[package_name] = package

app_path = os.path.join(project_home, "app.py")
spec = importlib.util.spec_from_file_location("voteforjulia_app", app_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load Flask app from {app_path}")

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
application = module.app

if _new_relic_wrapper is not None:
    application = _new_relic_wrapper(application)
