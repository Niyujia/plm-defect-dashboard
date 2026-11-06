# -*- coding: utf-8 -*-
"""
每日自动更新（2026-11-06 重写，API 优先版）
  0) nexgo-plm login 刷新 PLM token（API 通路与 TR3 导出共用，有效期约2小时）
  1) 今日报表缺失/无效时导出：优先走 API（export_via_api.py，责任人=combinename
     新口径、pageSize=20000 绕开深分页故障），失败再兜底 Skill C 页面导出
  2) TR3 复审报表导出（Tab4 数据源，失败不影响主流程）
  3) 看板比最新报表旧时执行 Skill K 生成（自动同步 plm-dashboard-web/index.html）

由 Windows 计划任务「PLM缺陷每日自动更新-上午/下午」每天 09:00 / 15:00 调用
（pythonw 无窗口运行；任务已启用 StartWhenAvailable 补跑错过的触发）
"""
import os
import subprocess
from datetime import datetime

PY = r'C:/Users/niyujia/.workbuddy/binaries/python/envs/default/Scripts/python.exe'
PLM_LOGIN = r'C:/Users/niyujia/.workbuddy/binaries/node/versions/22.22.2/nexgo-plm.cmd'
WEB_DIR = r'C:/Users/niyujia/plm-dashboard-web'
API_EXPORT = os.path.join(WEB_DIR, 'export_via_api.py')
EXPORT = r'C:/Users/niyujia/.workbuddy/skills/Skill C 自动导出缺陷列表/scripts/export_plm.py'
GEN = r'C:/Users/niyujia/.workbuddy/skills/un10-three-tab-dashboard/scripts/generate_dashboard.py'
TR3 = r'C:/Users/niyujia/.workbuddy/skills/un10-three-tab-dashboard/scripts/export_tr3.py'
DEFECT_DIR = r'F:/UN10/PVT/缺陷'
LOG_FILE = os.path.join(WEB_DIR, 'daily_update.log')

MIN_VALID_SIZE = 100_000  # 有效 xlsx 最小体积（伪报表是 ~10KB 错误 JSON）


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def run(cmd, cwd=None, timeout=600):
    """执行子进程，返回 (returncode, 合并输出)。统一 UTF-8 解码，避免 GBK 崩溃。"""
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace',
                           timeout=timeout, cwd=cwd, env=env)
        return r.returncode, ((r.stdout or '') + (r.stderr or ''))
    except Exception as e:
        return -1, str(e)


def _is_valid_xlsx(path):
    try:
        with open(path, 'rb') as fh:
            magic = fh.read(2)
        return magic == b'PK' and os.path.getsize(path) > MIN_VALID_SIZE
    except Exception:
        return False


def today_reports_valid():
    """今日是否有有效（PK 头且体积达标）的产品问题报表"""
    today = datetime.now().strftime('%Y%m%d')
    try:
        for f in os.listdir(DEFECT_DIR):
            if ('产品问题报表' in f and today in f and f.endswith('.xlsx')
                    and not f.startswith('~')
                    and _is_valid_xlsx(os.path.join(DEFECT_DIR, f))):
                return True
    except Exception as e:
        log(f'扫描目录失败: {e}')
    return False


def main():
    log('=== 每日自动更新开始 ===')

    # 0) 刷新 PLM token（nexgo-plm 非交互登录，读取 ~/.plm-assistant.yaml）
    rc, out = run([PLM_LOGIN, 'login'], cwd=WEB_DIR, timeout=120)
    if rc == 0 and '登录成功' in out:
        log('PLM token 已刷新')
    else:
        log(f'[警告] token 刷新失败 rc={rc}: {out[-150:]}（将尝试沿用现有 token）')

    # 1) 今日报表缺失或为伪文件 → 导出（API 优先，Skill C 兜底）
    if not today_reports_valid():
        log('今日无有效报表，优先执行 API 导出（新责任人口径）...')
        rc, out = run([PY, API_EXPORT], cwd=WEB_DIR, timeout=300)
        if rc == 0:
            log(f'API 导出成功: {out[-160:]}')
        else:
            log(f'API 导出失败 rc={rc}，兜底执行 Skill C 页面导出...')
            rc2, out2 = run([PY, EXPORT], cwd=os.path.dirname(EXPORT), timeout=600)
            if rc2 == 0:
                log('Skill C 导出成功（旧列口径兜底）')
            else:
                log(f'[错误] 两条导出通路均失败，跳过看板生成: {out2[-200:]}')
                log('=== 每日自动更新结束（失败） ===')
                return
    else:
        log('今日已有有效报表，跳过导出')

    # 2) TR3 复审报表（Tab4 数据源，失败不影响主流程）
    rc, out = run([PY, TR3], cwd=os.path.dirname(TR3), timeout=300)
    if rc == 0:
        log('TR3 复审报表导出完成')
    else:
        log(f'TR3 导出跳过(不影响主流程): {out[-120:]}')

    # 3) 看板比最新报表旧 → Skill K 生成（自动同步 plm-dashboard-web/index.html）
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
            rc, out = run([PY, GEN], cwd=os.path.dirname(GEN), timeout=600)
            if rc == 0:
                log('Skill K 完成，看板已更新')
            else:
                log(f'[错误] Skill K 失败: {out[-200:]}')
        else:
            log('看板已最新，跳过生成')
    except Exception as e:
        log(f'看板检查异常: {e}')

    log('=== 每日自动更新完成 ===')


if __name__ == '__main__':
    main()
