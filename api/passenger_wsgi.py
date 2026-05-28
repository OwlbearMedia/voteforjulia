import importlib.util
import os
import sys

project_home = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.dirname(project_home)
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

app_path = os.path.join(project_home, "app.py")
spec = importlib.util.spec_from_file_location("voteforjulia_app", app_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load Flask app from {app_path}")

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
application = module.app
