# -*- coding: utf-8 -*-
"""
PLM 看板服务守护脚本：检查 8080 端口，若服务未运行则自动拉起。
由 Windows 计划任务每 5 分钟调用一次（pythonw 无窗口）。
"""
import socket
import subprocess
import sys
import os

PORT = 8080
# ⚠️ 必须用 venv 里的 pythonw：基础解释器(versions\3.13.12)不含 pandas/requests 等依赖，
#    用它启动会直接 ModuleNotFoundError 退出（2026-11-06 踩过）
PYTHONW = r'C:\Users\niyujia\.workbuddy\binaries\python\envs\default\Scripts\pythonw.exe'
SERVER = r'C:\Users\niyujia\plm-dashboard-web\server.py'
WORKDIR = r'C:\Users\niyujia\plm-dashboard-web'
LOG = os.path.join(WORKDIR, 'server_guard.log')


def _log(msg):
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')
    except Exception:
        pass


def port_open(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect(('127.0.0.1', port))
        s.close()
        return True
    except Exception:
        try:
            s.close()
        except Exception:
            pass
        return False


def main():
    if port_open(PORT):
        sys.exit(0)  # 服务正常，无需处理
    # 服务未运行 → 拉起
    # 关键：必须带 DETACHED_PROCESS(0x8)，否则从计划任务运行时，
    # 任务结束会连带终止整个子进程树，导致"日志显示已拉起但服务实际没起来"
    try:
        subprocess.Popen(
            [PYTHONW, SERVER, str(PORT)],
            cwd=WORKDIR,
            creationflags=0x00000008 | 0x08000000,  # DETACHED_PROCESS | CREATE_NO_WINDOW
            close_fds=True,
        )
        _log(f'[guard] 服务未运行，已自动拉起（detached）')
    except Exception as e:
        _log(f'[guard] 拉起失败: {e}')


if __name__ == '__main__':
    main()