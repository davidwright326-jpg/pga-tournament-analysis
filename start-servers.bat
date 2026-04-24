@echo off
REM Start PGA Tournament Analysis servers

echo Starting Streamlit app...
start "PGA Streamlit" cmd /k "cd /d %~dp0backend && python -m streamlit run streamlit_app.py --server.port 8501 --server.headless true"

echo Starting backend API server...
start "PGA Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --reload --port 8000"

echo Starting frontend server...
start "PGA Frontend" cmd /k "cd /d %~dp0frontend && node node_modules/next/dist/bin/next dev"

echo All servers starting!
echo Streamlit:  http://localhost:8501
echo Backend:    http://localhost:8000
echo Frontend:   http://localhost:3000
