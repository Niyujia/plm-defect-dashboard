@echo off
REM PLM缺陷看板 - 内网HTTP服务器启动脚本
REM 启动后可通过 http://10.199.183.123:8080 访问

echo Starting PLM Dashboard Server...
echo URL: http://10.199.183.123:8080
echo Press Ctrl+C to stop

"C:\Users\niyujia\.workbuddy\binaries\python\envs\default\Scripts\python.exe" -m http.server 8080 --directory "C:\Users\niyujia\plm-dashboard-web" --bind 0.0.0.0