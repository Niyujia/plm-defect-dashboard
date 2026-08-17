@echo off
rem PLM看板后端服务 - 静默启动（无窗口）
start "" /b "C:\Users\niyujia\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe" "C:\Users\niyujia\plm-dashboard-web\server.py" 8080
echo PLM看板后端服务已启动（后台静默运行）: http://localhost:8080
