"""Root wrapper for Streamlit Cloud deployment.
Adds the backend directory to sys.path and runs the actual app.
"""
import sys
import os

# Get absolute path to the backend directory
_here = os.path.dirname(os.path.abspath(__file__))
_backend = os.path.join(_here, "backend")

# Add backend to path so 'app' package is importable
if _backend not in sys.path:
    sys.path.insert(0, _backend)

# Change working directory to backend so SQLite DB is created there
os.chdir(_backend)

# Now exec the actual app
with open(os.path.join(_backend, "streamlit_app.py"), encoding="utf-8") as f:
    code = f.read()

exec(compile(code, os.path.join(_backend, "streamlit_app.py"), "exec"))
