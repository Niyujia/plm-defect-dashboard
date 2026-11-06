@echo off
rem PLM dashboard service - silent start
rem NOTE: must use venv pythonw (versions\3.13.12 lacks pandas/openpyxl) - fixed 2026-11-06
start "" /b "C:\Users\niyujia\.workbuddy\binaries\python\envs\default\Scripts\pythonw.exe" "C:\Users\niyujia\plm-dashboard-web\server.py" 8080
echo PLM dashboard service started in background: http://localhost:8080
