# -*- coding: utf-8 -*-
"""
每日自动更新：检查当天报表是否已导出、看板是否过期
若需要则自动执行 Skill C(export_plm.py) + Skill K(generate_dashboard.py)
由 Windows 计划任务每天定时调用（pythonw 无窗口运行）
"""
import os
import subprocess
from datetime import datetime

PY = r'C:/Users/niyujia/.workbuddy/binaries/python/envs/default/Scripts/python.exe'
EXPORT = r'C:/Users/niyujia/.workbuddy/skills/Skill C 自动导出缺陷列表/scripts/export_plm.py'
GEN = r'C:/Users/niyujia/.workbuddy/skills/un10-three-tab-dashboard/scripts/generate_dashboard.py'
DEFECT_DIR = r'F:/UN10/PVT/缺陷'
WEB_DIR = r'C:/Users/niyujia/plm-dashboard-web'
LOG_FILE = os.path.join(WEB_DIR, 'daily_update.log')


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def main():
    today = datetime.now().strftime('%Y%m%d')
    log('=== 每日自动更新开始 ===')

    # 1) 检查今天是否已有报表，没有则执行 Skill C 导出
    has_today = False
    try:
        for f in os.listdir(DEFECT_DIR):
            if ('产品问题报表' in f and today in f and f.endswith('.xlsx')
                    and not f.startswith('~')):
                has_today = True
                break
    except Exception as e:
        log(f'扫描目录失败: {e}')

    if not has_today:
        log('今日无报表，执行 Skill C 导出...')
        try:
            r = subprocess.run([PY, EXPORT], capture_output=True, text=True,
                               timeout=600, cwd=os.path.dirname(EXPORT))
            log(f'Skill C 完成 exit={r.returncode}: {(r.stdout or "")[-200:]}')
        except Exception as e:
            log(f'Skill C 异常: {e}')
    else:
        log('今日已有报表，跳过导出')

    # 2) 看板是否比最新报表旧，是则执行 Skill K 生成
    try:
        latest_mt = 0
        for f in os.listdir(DEFECT_DIR):
            if ('产品问题报表' in f and f.endswith('.xlsx') and not f.startswith('~')):
                mt = os.path.getmtime(os.path.join(DEFECT_DIR, f))
                latest_mt = max(latest_mt, mt)
        idx = os.path.join(WEB_DIR, 'index.html')
        idx_mt = os.path.getmtime(idx) if os.path.exists(idx) else 0
        if idx_mt < latest_mt:
            log('看板过期，执行 Skill K 生成...')
            try:
                r = subprocess.run([PY, GEN], capture_output=True, text=True,
                                   timeout=600, cwd=os.path.dirname(GEN))
                log(f'Skill K 完成 exit={r.returncode}: {(r.stdout or "")[-200:]}')
            except Exception as e:
                log(f'Skill K 异常: {e}')
        else:
            log('看板已最新，跳过生成')
    except Exception as e:
        log(f'看板检查异常: {e}')

    log('=== 每日自动更新完成 ===')


if __name__ == '__main__':
    main()
