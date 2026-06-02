import importlib.util
import os
import sys
import types

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
