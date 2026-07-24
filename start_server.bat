@echo off
cd /d C:\Users\niyujia\plm-dashboard-web
PowerShell -Command "Start-Process -WindowStyle Hidden -FilePath 'C:\Users\niyujia\.workbuddy\binaries\python\versions\3.13.12\python.exe' -ArgumentList 'server.py','8080'"
echo PLM看板后端服务已启动: http://localhost:8080
