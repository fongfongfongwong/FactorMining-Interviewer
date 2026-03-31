"""Launcher that patches os.getcwd for sandboxed environments, then runs Streamlit."""
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Patch os.getcwd to always return the project directory
# This fixes PermissionError in sandboxed environments where the initial cwd is inaccessible
_original_getcwd = os.getcwd
def _patched_getcwd():
    try:
        return _original_getcwd()
    except (PermissionError, OSError):
        return PROJECT_DIR

os.getcwd = _patched_getcwd

# Also patch pathlib.Path.cwd
import pathlib
_original_cwd = pathlib.Path.cwd
@classmethod
def _patched_cwd(cls):
    try:
        return _original_cwd()
    except (PermissionError, OSError):
        return cls(PROJECT_DIR)

pathlib.Path.cwd = _patched_cwd

# Change to project directory
os.chdir(PROJECT_DIR)

# Now run streamlit
port = os.environ.get("PORT", "8502")
sys.argv = ["streamlit", "run", os.path.join(PROJECT_DIR, "app.py"),
            "--server.headless", "true", "--server.port", port]

from streamlit.web.cli import main
main(prog_name="streamlit")
