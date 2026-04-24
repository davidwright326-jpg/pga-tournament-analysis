"""Root wrapper for Streamlit Cloud deployment.
Adds the backend directory to sys.path and runs the actual app.
"""
import sys
import os

# Add backend to path so 'app' package is importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

# Change working directory to backend so SQLite DB is created there
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

# Now exec the actual app
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", "streamlit_app.py"), encoding="utf-8") as f:
    code = f.read()

# The backend app does sys.path.insert(0, os.path.dirname(__file__))
# which is fine — it'll just add the backend dir again (harmless)
exec(compile(code, "backend/streamlit_app.py", "exec"))
