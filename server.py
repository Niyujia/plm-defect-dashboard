"""
PLM 缺陷看板后端服务
提供静态文件服务 + /api/refresh SSE 实时刷新接口
"""
import os, sys, json, time, io, re, sqlite3, traceback
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import pandas as pd
import requests
from collections import defaultdict

# ── 配置 ──────────────────────────────────────────
PLM_BASE = 'https://plm.xgd.com'
PERSONNEL_REPORT_ID = '1221266680132403200'
DEFECT_REPORT_ID = '1089684809031438336'
SESSION_DB = os.path.expanduser('~/.nexgo-plm/nexgo-plm.db')
WEB_ROOT = os.path.dirname(os.path.abspath(__file__))

_COLOR_PALETTE = [
    '#D9E1F2', '#FCE4D6', '#E8DAEF', '#FFF2CC', '#EAD1DC', '#CFE2F3',
    '#D5E8D4', '#FFE6CC', '#E2EFDA', '#F4CCCC', '#FDE9D9', '#EEEEEE',
    '#FFF7E6', '#D4EFDF', '#D5F5E3', '#D6EAF8', '#F9E79F', '#D2B4DE',
    '#A9DFBF', '#FADBD8', '#D4E6F1', '#F5CBA7', '#AED6F1', '#F9E6B2',
    '#D7BDE2', '#A3E4D7', '#F5B7B1', '#85C1E9', '#F8C471', '#C39BD3',
    '#F0B27A', '#82E0AA', '#F1948A', '#85C1E9', '#BB8FCE', '#73C6B6',
    '#F7DC6F', '#D7BDE2', '#A9CCE3', '#EDBB99', '#A3E4D7', '#F5B041',
    '#7FB3D8', '#D2B4DE', '#F1948A', '#A9DFBF', '#F8C471', '#85C1E9',
    '#E8DAEF', '#76D7C4', '#F5CBA7', '#C39BD3', '#82E0AA', '#F9E79F',
    '#AED6F1', '#D7BDE2', '#F0B27A', '#A3E4D7', '#F1948A', '#85C1E9',
    '#F5B041', '#7FB3D8', '#D2B4DE', '#F8C471', '#A9DFBF', '#E8DAEF',
    '#76D7C4', '#F5CBA7', '#C39BD3', '#82E0AA', '#F9E79F', '#AED6F1',
    '#D7BDE2', '#F0B27A', '#A3E4D7', '#F1948A', '#85C1E9', '#F5B041',
    '#7FB3D8', '#D2B4DE', '#F8C471', '#A9DFBF', '#E8DAEF', '#76D7C4',
    '#F5CBA7', '#C39BD3', '#82E0AA', '#F9E79F', '#AED6F1', '#D7BDE2',
    '#F0B27A', '#A3E4D7', '#F1948A', '#85C1E9', '#F5B041', '#7FB3D8',
]

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

def get_token():
    try:
        conn = sqlite3.connect(SESSION_DB)
        cur = conn.cursor()
        cur.execute('SELECT access_token FROM auth_session WHERE id=1')
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        log(f'读取Token失败: {e}')
        return None

def plm_post(report_id, token, page_no=1, page_size=10000):
    return requests.post(f'{PLM_BASE}/jmreport/show', json={
        'id': report_id, 'apiUrl': '',
        'params': json.dumps({'pageNo': page_no, 'pageSize': page_size})
    }, headers={
        'Content-Type': 'application/json;charset=UTF-8',
        'X-Access-Token': token, 'token': token
    }, timeout=120)

def fetch_personnel(token):
    """从PLM获取人员分组数据"""
    resp = plm_post(PERSONNEL_REPORT_ID, token)
    resp.raise_for_status()
    data = resp.json()
    user_list = data['result']['dataList']['PLMUserAndDeptDetail']['list']
    p2g = {}
    for u in user_list:
        name = str(u.get('username', '')).strip()
        dept = str(u.get('userdept', '')).strip()
        forbid = str(u.get('isforbid', ''))
        if name and name != 'nan' and dept and dept != 'nan' and forbid == '正常使用':
            p2g[name] = dept
    log(f'人员分组: {len(p2g)}人')
    return p2g

def build_groups(p2g):
    """构建GROUPS结构（同上位函数）"""
    group_members = defaultdict(list)
    for person, group in p2g.items():
        if person not in group_members[group]:
            group_members[group].append(person)
    android_prefixes = ['安卓', 'Android']
    android_list, other_list = [], []
    for gname, members in sorted(group_members.items(), key=lambda x: -len(x[1])):
        if any(gname.startswith(p) for p in android_prefixes):
            android_list.append((gname, members))
        else:
            other_list.append((gname, members))
    groups = android_list + other_list
    colors = {}
    for i, (gname, _) in enumerate(groups):
        colors[gname] = _COLOR_PALETTE[i % len(_COLOR_PALETTE)]
    return groups, [g for g, _ in android_list], colors

def fetch_defect_data(token):
    """从PLM获取全部产品缺陷报表数据（分页）"""
    all_items = []
    page = 1
    total = None
    while True:
        resp = plm_post(DEFECT_REPORT_ID, token, page_no=page)
        resp.raise_for_status()
        data = resp.json()
        table = data['result']['dataList']['BUG']
        items = table.get('list', [])
        if total is None:
            total = table.get('count', 0)
            log(f'缺陷报表总数: {total}条')
        all_items.extend(items)
        log(f'  第{page}页: {len(items)}条')
        if len(all_items) >= total or len(items) == 0:
            break
        page += 1
    log(f'缺陷数据获取完成: {len(all_items)}条')
    return all_items

# PLM字段 → 看板DataFrame列名 映射
COLUMN_MAP = {
    'issuenumber': '问题编号',
    'issuename': '问题名称',
    'lifecyclestate': '问题状态',
    'severityvalue': '严重程度',
    'developowner': '流程未执行人',
    'modelvalue': '机型',
    'testfrequencyvalue': '测试轮数',
    'solphasevalue': '计划解决阶段',
    'createtime': '创建时间',
}

def items_to_df(items):
    """将PLM API返回的缺陷数据转换为DataFrame（列名与Excel一致）"""
    rows = []
    for item in items:
        row = {}
        for api_col, df_col in COLUMN_MAP.items():
            row[df_col] = item.get(api_col, '')
        row['开发负责人'] = item.get('developowner', '')
        rows.append(row)
    return pd.DataFrame(rows)

# ── KPI 计算函数（与 generate_dashboard.py 保持一致） ──

def calc_overview(df):
    total_df = df[~df['问题状态'].isin(['测试审核不通过关闭', '已取消'])]
    total = len(total_df)
    closed_review = len(total_df[total_df['问题状态'].isin(['已关闭', '评审关闭', '已解决'])])
    to_verify = len(total_df[total_df['问题状态'] == '已修复待验证'])
    unrepaired = total - closed_review - to_verify
    fix_rate = round((closed_review + to_verify) / total * 100, 1) if total > 0 else 0
    close_rate = round(closed_review / total * 100, 1) if total > 0 else 0
    return {'total': int(total), 'unrepaired': int(unrepaired),
            'closed_review': int(closed_review), 'to_verify': int(to_verify),
            'fix_rate': fix_rate, 'close_rate': close_rate}

def normalize_round(val):
    if pd.isna(val) or str(val).strip() in ('', '-', '/', '无', 'V', ' '):
        return None
    s = str(val).strip()
    m = re.search(r'(?:HV|SV|RV|DVT)?[ -]*(V?\d+\.\d+)', s, re.IGNORECASE)
    if m:
        v = m.group(1)
        return v if v.startswith('V') else 'V' + v
    m = re.search(r'V?(\d+\.\d+)', s)
    if m:
        return 'V' + m.group(1)
    m = re.search(r'^TR(\d+)$', s, re.IGNORECASE)
    if m:
        return 'TR' + m.group(1)
    for kw in ['PVT', 'EVT', 'DVT', 'LMT']:
        if kw in s.upper():
            return kw
    return None

def get_group_for_person(person_str, p2g):
    if pd.isna(person_str):
        return '未分配'
    for p in str(person_str).split(','):
        p = p.strip()
        if p in p2g:
            return p2g[p]
    return '未分配'

def build_details_list(df, p2g):
    items = []
    for _, row in df.iterrows():
        items.append({
            'id': str(row.get('问题编号', '')),
            'name': str(row.get('问题名称', ''))[:80],
            'person': str(row.get('流程未执行人', '')),
            'model': str(row.get('机型', '')),
            'status': str(row.get('问题状态', '')),
            'severity': str(row.get('严重程度', '')),
            'group': get_group_for_person(row.get('流程未执行人', ''), p2g),
            'round': normalize_round(row.get('测试轮数')),
            'rawRound': str(row.get('测试轮数', '')).strip(),
            'resolvePhase': str(row.get('计划解决阶段', '')),
        })
    return items

def calc_group_stats(df, groups, android_groups):
    result = []
    for gname, members in groups:
        mask = df['流程未执行人'].apply(
            lambda x: any(m in str(x).split(',') for m in members))
        result.append({'group': gname, 'count': int(mask.sum())})
    android = sorted([r for r in result if r['group'] in android_groups],
                     key=lambda x: android_groups.index(x['group']))
    others = sorted([r for r in result if r['group'] not in android_groups],
                    key=lambda x: -x['count'])
    return android + others

def get_models(df):
    return sorted(df['机型'].dropna().unique().tolist())

PHASE_MAP = {
    'V0.1': 'EVT', 'V1.0': 'EVT', 'TR1': 'EVT', 'TR2': 'EVT',
    'V0.2': 'DVT', 'V0.3': 'DVT', 'V0.4': 'DVT', 'TR3': 'DVT', 'DVT': 'DVT',
    'V0.5': 'PVT', 'V0.6': 'PVT', 'TR4': 'PVT', 'PVT': 'PVT',
}
PHASE_ORDER = ['EVT', 'DVT', 'PVT', 'LMT']
PHASE_LABELS = {'EVT': 'EVT阶段', 'DVT': 'DVT阶段', 'PVT': 'PVT阶段', 'LMT': 'LMT阶段'}

def calc_phase_stats(items):
    counts = {}
    for d in items:
        n = d.get('round')
        if not n:
            continue
        phase = PHASE_MAP.get(n, 'LMT')
        if phase not in counts:
            counts[phase] = {'total': 0, '严重': 0, '一般': 0, '优化建议': 0}
        counts[phase]['total'] += 1
        sev = d.get('severity', '')
        if '致命' in sev or '严重' in sev:
            counts[phase]['严重'] += 1
        elif '建议' in sev:
            counts[phase]['优化建议'] += 1
        else:
            counts[phase]['一般'] += 1
    return [{'phase': p, 'label': PHASE_LABELS[p],
             'total': counts.get(p, {}).get('total', 0),
             'severe': counts.get(p, {}).get('严重', 0),
             'normal': counts.get(p, {}).get('一般', 0),
             'suggestion': counts.get(p, {}).get('优化建议', 0)}
            for p in PHASE_ORDER]

TR_PHASES = ['TR1', 'TR2', 'TR3', 'TR4', '结项']
TR_TARGETS = {'TR2': 80, 'TR3': 90, 'TR4': 93, '结项': 95}
TR_DISPLAY = ['TR1', 'TR2', 'TR3', 'TR4', '结项']

def calc_tr_closure(items):
    tr1_total = sum(1 for d in items if d.get('round') == 'TR1')
    results = []
    for tr_name in TR_DISPLAY:
        if tr_name == 'TR1':
            results.append({'node': 'TR1', 'total': int(tr1_total), 'closed': 0, 'rate': 0, 'target': 0, 'phases': 'TR1(测试轮次)'})
            continue
        if tr_name == '结项':
            include_phases = ['结项', 'TR1', 'TR2', 'TR3', 'TR4']
        else:
            idx = TR_PHASES.index(tr_name)
            include_phases = TR_PHASES[:idx + 1]
        subset = [d for d in items if d.get('resolvePhase') in include_phases]
        total = max(0, len(subset) - tr1_total)
        closed = len([d for d in subset
                      if d.get('status') in ('已关闭', '评审关闭')
                      and d.get('round') != 'TR1'])
        rate = round(closed / total * 100, 1) if total > 0 else 0
        results.append({
            'node': tr_name, 'total': int(total), 'closed': int(closed),
            'rate': rate, 'target': TR_TARGETS.get(tr_name, 0),
            'phases': '+'.join(include_phases),
        })
    return results

def build_dashboard_data(df, p2g):
    """从DataFrame构建完整的看板JSON数据"""
    groups, android_groups, colors = build_groups(p2g)
    overview = calc_overview(df)
    all_details = build_details_list(df, p2g)
    group_stats = calc_group_stats(df, groups, android_groups)
    models = get_models(df)
    phases = calc_phase_stats(all_details)
    tr_data = calc_tr_closure(all_details)
    return {
        'MODELS': models,
        'OVERVIEW': overview,
        'GROUP_STATS': group_stats,
        'ALL_DETAILS': all_details,
        'TREND': [],
        'PHASES': phases,
        'TR_DATA': tr_data,
        'GROUP_NAMES': ['全部组别'] + [g['group'] for g in group_stats],
        'GROUP_COLORS': colors,
        'GROUPS': [{'name': g[0], 'members': g[1]} for g in groups],
    }


# ── HTTP Server ──

class RefreshHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/refresh':
            self.handle_refresh()
        elif path == '/':
            self.serve_static('index.html')
        else:
            # 去除前导 / 后尝试查找文件
            fname = path.lstrip('/')
            self.serve_static(fname)

    def serve_static(self, filename):
        filepath = os.path.join(WEB_ROOT, filename)
        if not os.path.isfile(filepath):
            self.send_error(404)
            return
        ext = os.path.splitext(filename)[1].lower()
        mime = {
            '.html': 'text/html;charset=utf-8',
            '.js': 'application/javascript',
            '.css': 'text/css',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.svg': 'image/svg+xml',
        }.get(ext, 'application/octet-stream')
        with open(filepath, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(data)

    def sse_send(self, event, data_dict):
        """发送SSE事件"""
        payload = json.dumps(data_dict, ensure_ascii=False)
        self.wfile.write(f'event: {event}\ndata: {payload}\n\n'.encode('utf-8'))
        self.wfile.flush()

    def handle_refresh(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream;charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        try:
            # Step 1: 获取Token
            self.sse_send('progress', {'step': 1, 'msg': '正在连接PLM系统...', 'pct': 5})
            token = get_token()
            if not token:
                self.sse_send('error', {'msg': 'PLM登录已过期，请重新执行 nexgo-plm login'})
                return
            time.sleep(0.3)

            # Step 2: 获取人员分组
            self.sse_send('progress', {'step': 2, 'msg': '正在获取人员分组...', 'pct': 15})
            p2g = fetch_personnel(token)
            time.sleep(0.2)

            # Step 3: 获取缺陷报表
            self.sse_send('progress', {'step': 3, 'msg': '正在下载产品缺陷报表...', 'pct': 30})
            defect_items = fetch_defect_data(token)
            time.sleep(0.2)

            # Step 4: 解析数据
            self.sse_send('progress', {'step': 4, 'msg': '正在解析报表数据...', 'pct': 50})
            df = items_to_df(defect_items)
            log(f'解析完成: {len(df)}行, {len(df.columns)}列')
            time.sleep(0.2)

            # Step 5: 计算KPI
            self.sse_send('progress', {'step': 5, 'msg': '正在计算KPI指标...', 'pct': 70})
            data = build_dashboard_data(df, p2g)
            time.sleep(0.2)

            # Step 6: 完成
            self.sse_send('progress', {'step': 6, 'msg': '数据更新完成，正在刷新看板...', 'pct': 95})
            time.sleep(0.3)

            self.sse_send('complete', {'data': data, 'total_rows': len(df)})
            log('刷新完成')

        except Exception as e:
            log(f'刷新失败: {traceback.format_exc()}')
            self.sse_send('error', {'msg': f'刷新失败: {str(e)}'})

    def log_message(self, format, *args):
        log(f'HTTP {args[0]} {args[1]}')


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(('0.0.0.0', port), RefreshHandler)
    log(f'PLM看板后端服务启动: http://0.0.0.0:{port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        log('服务停止')

if __name__ == '__main__':
    main()
