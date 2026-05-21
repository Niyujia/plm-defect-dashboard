"""
UN10 互动式缺陷看板生成器 - 三栏设计
栏1: 缺陷总览 (KPI卡片)
栏2: 各组缺陷统计 (柱状图+组别列表)  
栏3: 修复率关闭率走势 (趋势图)
数据公式遵循 Skill A
"""
import pandas as pd
import os
import re
import json
from datetime import datetime

# ==================== Skill A 配置 ====================
TARGET_MODELS = ['UN10', 'UN10R', 'UN10P', 'UN10RS']
EXCLUDE_STATUS = ['测试审核不通过关闭', '已修复待验证', '已关闭', '评审关闭']

GROUPS = [
    ('安卓组唐朝',   ['龚棕塘', '路江飞', '刘泽祥', '彭浩', '黄彬', '唐朝', '梁幸蒋', '邓峻']),
    ('安卓组霍耀光', ['霍耀光', '郑腾交', '王程炯', '陈玉杰', '邓延军', '林政和', '胡耀波', '吴镜清']),
    ('安卓组刘锐峰', ['刘锐峰', '朱倩雯', '刘俊华', '沈磊', '司奇']),
    ('硬件组向阳',   ['林裕敏', '向阳', '李德权', '王冠', '夏亮', '陈文琪', '陈双明', '梁宏达', '董鑫', '冯泉', '张玮发', '赵章宁', '李俊昌']),
    ('效能组崔龙龙', ['崔龙龙', '郑俊杰', '彭湃', '熊勇']),
    ('单片机黄文潘', ['黄文潘', '任海鹏', '林腾威', '王霖']),
    ('SE胡文',       ['胡文']),
    ('NPI黄恒沵',    ['黄恒沵']),
    ('通讯组黄林欢', ['黄林欢', '严立言', '郑思捷', '肖金华']),
    ('卡组张辉权',   ['张辉权', '唐建斌', '梁毅雄', '罗绘东']),
    ('结构组赵林立', ['夏小平', '赵林立']),
    ('PQA戚飘红',    ['戚飘红', '俞正帅']),
    ('应用丘志鹏',   ['华聪', '丘志鹏']),
    ('测试部汪肖肖',   ['汪肖肖']),
    ('测试部硬件测试',  ['王蓉', '李锐杰', '孟德宇', '沈志伟', '邱诗照']),
    ('测试部软件测试',  ['梁坚', '覃锦庆', '张宏伟', '唐兰', '钟金兰', '汤海燕', '赵丽敏', '贺婷', '马晓微', '熊鸣', '张理晴']),
]

ANDROID_GROUPS = ['安卓组唐朝', '安卓组霍耀光', '安卓组刘锐峰']

GROUP_COLORS = {
    '安卓组唐朝': '#D9E1F2', '安卓组霍耀光': '#FCE4D6', '安卓组刘锐峰': '#E8DAEF',
    '硬件组向阳': '#FFF2CC', '效能组崔龙龙': '#EAD1DC', '单片机黄文潘': '#CFE2F3',
    'SE胡文': '#D5E8D4', 'NPI黄恒沵': '#FFE6CC', '通讯组黄林欢': '#E2EFDA',
    '卡组张辉权': '#F4CCCC', '结构组赵林立': '#FDE9D9', 'PQA戚飘红': '#EEEEEE',
    '应用丘志鹏': '#FFF7E6', '测试部汪肖肖': '#D6EAF8', '测试部硬件测试': '#D4EFDF',
    '测试部软件测试': '#D5F5E3',
}

DEFECT_DIR = r'F:/UN10/PVT/缺陷'


def _match_person(df, person):
    exact = df['流程未执行人'] == person
    contains = df['流程未执行人'].str.contains(r'(?:^|,)' + person + r'(?:,|$)', na=False)
    return df[exact | contains]


def get_group_for_person(person_str):
    if pd.isna(person_str):
        return '未分配'
    for gname, members in GROUPS:
        for m in members:
            if m in str(person_str).split(','):
                return gname
    return '未分配'


def file_sort_key(fname):
    """从文件名提取日期+序号用于排序"""
    m = re.search(r'(\d{8})[-]?(\d{2})?', fname)
    if m:
        return m.group(1) + (m.group(2) if m.group(2) else '99')
    return '0000000099'


def load_latest_file():
    files = [f for f in os.listdir(DEFECT_DIR)
             if f.startswith('产品问题报表') and f.endswith('.xlsx')
             and '梳理表' not in f and '统计' not in f and '关闭率' not in f
             and '清单' not in f and '类型' not in f and '严重' not in f and not f.startswith('~')]
    files.sort(key=file_sort_key, reverse=True)
    latest = os.path.join(DEFECT_DIR, files[0])
    print(f'[INFO] 最新文件: {latest}')
    return latest


def load_file(filepath):
    df = pd.read_excel(filepath, sheet_name=0)
    # 不再按 TARGET_MODELS 过滤，保留全部机型
    return df


def calc_overview(df):
    # 缺陷总数剔除"测试审核不通过关闭"
    total_df = df[df['问题状态'] != '测试审核不通过关闭']
    total = len(total_df)
    unrepaired_statuses = ['开启', '修复中', '已分配', '正在审阅', '测试审核']
    unrepaired = len(total_df[total_df['问题状态'].isin(unrepaired_statuses)])
    # 已关闭+评审关闭
    closed_review = len(total_df[total_df['问题状态'].isin(['已关闭', '评审关闭'])])
    # 已修复待验证
    to_verify = len(total_df[total_df['问题状态'] == '已修复待验证'])
    # 修复率 = (已关闭 + 评审关闭 + 已修复待验证) / 总数
    fixed = closed_review + to_verify
    fix_rate = round(fixed / total * 100, 1) if total > 0 else 0
    # 关闭率 = (已关闭 + 评审关闭) / 总数
    close_rate = round(closed_review / total * 100, 1) if total > 0 else 0
    return {
        'total': int(total), 'unrepaired': int(unrepaired),
        'closed_review': int(closed_review), 'to_verify': int(to_verify),
        'fix_rate': fix_rate, 'close_rate': close_rate
    }


def build_details_list(df):
    items = []
    for _, row in df.iterrows():
        items.append({
            'id': str(row.get('问题编号', '')),
            'name': str(row.get('问题名称', ''))[:80],
            'person': str(row.get('流程未执行人', '')),
            'model': str(row.get('机型', '')),
            'status': str(row.get('问题状态', '')),
            'severity': str(row.get('严重程度', '')),
            'group': get_group_for_person(row.get('流程未执行人', '')),
            'round': normalize_round(row.get('测试轮数')),
            'resolvePhase': str(row.get('计划解决阶段', '')),
        })
    return items


def calc_group_stats(df):
    """按Skill A公式计算各组成员缺陷数量"""
    result = []
    for gname, members in GROUPS:
        member_masks = [_match_person(df, m) for m in members]
        d = pd.concat(member_masks).drop_duplicates()
        result.append({'group': gname, 'count': int(len(d))})
    android = sorted([r for r in result if r['group'] in ANDROID_GROUPS],
                     key=lambda x: ANDROID_GROUPS.index(x['group']))
    others = sorted([r for r in result if r['group'] not in ANDROID_GROUPS],
                    key=lambda x: -x['count'])
    return android + others


def build_group_details(df, group_name):
    """获取指定组（Skill A筛选后）的缺陷列表"""
    members = None
    for gname, mlist in GROUPS:
        if gname == group_name:
            members = mlist
            break
    if not members:
        return []
    member_masks = [_match_person(df, m) for m in members]
    filtered = pd.concat(member_masks).drop_duplicates()
    return build_details_list(filtered)


def collect_trend_data():
    files = [f for f in os.listdir(DEFECT_DIR)
             if f.startswith('产品问题报表') and f.endswith('.xlsx')
             and '梳理表' not in f and '统计' not in f and '关闭率' not in f
             and '清单' not in f and '类型' not in f and '严重' not in f and not f.startswith('~')]
    date_files = {}
    for f in files:
        m = re.search(r'(\d{8})', f)
        if m:
            d = m.group(1)
            if d not in date_files or file_sort_key(f) > file_sort_key(date_files[d]):
                date_files[d] = f
    trend = []
    for date_str in sorted(date_files.keys()):
        fp = os.path.join(DEFECT_DIR, date_files[date_str])
        try:
            df_raw = pd.read_excel(fp, sheet_name=0)
            df = df_raw[df_raw['问题状态'] != '测试审核不通过关闭'].copy()
            if len(df) == 0:
                continue
            all_total = len(df)
            all_closed = len(df[df['问题状态'].isin(['已关闭', '评审关闭'])])
            all_to_verify = len(df[df['问题状态'] == '已修复待验证'])
            all_fix = round((all_closed + all_to_verify) / all_total * 100, 1)
            all_close = round(all_closed / all_total * 100, 1)
            # 按机型聚合
            model_data = {}
            for model_name, grp in df.groupby('机型'):
                m_total = len(grp)
                m_closed = len(grp[grp['问题状态'].isin(['已关闭', '评审关闭'])])
                m_to_verify = len(grp[grp['问题状态'] == '已修复待验证'])
                model_data[str(model_name)] = {
                    't': int(m_total), 'c': int(m_closed), 'v': int(m_to_verify)
                }
            dt = datetime.strptime(date_str, '%Y%m%d')
            trend.append({
                'date': date_str, 'label': dt.strftime('%m/%d'),
                'all_total': int(all_total), 'all_fix': all_fix, 'all_close': all_close,
                'md': model_data,
            })
        except Exception as e:
            print(f'[WARN] 跳过 {date_files[date_str]}: {e}')
    return trend


def normalize_round(val):
    """归一化测试轮次：HV0.1/SV0.1/RV0.1 → V0.1"""
    if pd.isna(val) or str(val).strip() in ('', '-', '/', '无', 'V', ' '):
        return None
    s = str(val).strip()
    # 直接匹配 V0.x/V1.x/V2.x... 或 0.x/1.x
    import re
    m = re.search(r'(?:HV|SV|RV|DVT)?[ -]*(V?\d+\.\d+)', s, re.IGNORECASE)
    if m:
        v = m.group(1)
        if not v.startswith('V'):
            v = 'V' + v
        return v
    # 纯数字版本
    m = re.search(r'V?(\d+\.\d+)', s)
    if m:
        return 'V' + m.group(1)
    # TR0-4 / TR0 / TR1
    m = re.search(r'^TR(\d+)$', s, re.IGNORECASE)
    if m:
        return 'TR' + m.group(1)
    # 其他阶段名
    phase_keywords = ['PVT', 'EVT', 'DVT', 'LMT']
    for kw in phase_keywords:
        if kw in s.upper():
            return kw
    return None


def calc_round_stats(df):
    """计算各测试轮次的缺陷数量（归一化后的轮次）"""
    counts = {}
    for _, row in df.iterrows():
        val = row.get('测试轮数')
        if pd.isna(val):
            continue
        normalized = normalize_round(val)
        if normalized:
            counts[normalized] = counts.get(normalized, 0) + 1
    # 按版本号排序
    def sort_key(k):
        import re
        m = re.search(r'(\d+)\.(\d+)', k)
        if m:
            return (int(m.group(1)), int(m.group(2)))
        # TR0, TR1, TR2... 按数字顺序
        m_tr = re.search(r'^TR(\d+)$', k)
        if m_tr:
            return (98, int(m_tr.group(1)))
        # PVT/EVT/DVT/LMT 放最后
        phase_order = {'EVT': 0, 'DVT': 1, 'PVT': 2, 'LMT': 3}
        return (99, phase_order.get(k, 99))
    sorted_items = sorted(counts.items(), key=lambda x: sort_key(x[0]))
    return [{'round': k, 'count': v} for k, v in sorted_items]


TR_PHASES = ['TR1', 'TR2', 'TR3', 'TR4', '结项']
TR_TARGETS = {'TR2': 80, 'TR3': 90, 'TR4': 93, '结项': 95}
TR_DISPLAY = ['TR2', 'TR3', 'TR4', '结项']


def calc_tr_closure(df):
    """
    计算 TR 节点关闭率。
    TR2 = TR1+TR2 缺陷的关闭率
    TR3 = TR1+TR2+TR3 缺陷的关闭率
    TR4 = TR1+TR2+TR3+TR4 缺陷的关闭率
    结项 = 结项+TR1+TR2+TR3+TR4 缺陷的关闭率
    """
    # 先剔除测试审核不通过关闭，再计算
    df_clean = df[df['问题状态'] != '测试审核不通过关闭']
    results = []
    for tr_name in TR_DISPLAY:
        # 确定需要包含的阶段
        if tr_name == '结项':
            include_phases = ['结项', 'TR1', 'TR2', 'TR3', 'TR4']
        else:
            idx = TR_PHASES.index(tr_name)
            include_phases = TR_PHASES[:idx + 1]  # TR1 ~ TRn
        # 筛选数据
        subset = df_clean[df_clean['计划解决阶段'].isin(include_phases)]
        total = len(subset)
        closed = len(subset[subset['问题状态'].isin(['已关闭', '评审关闭'])])
        rate = round(closed / total * 100, 1) if total > 0 else 0
        target = TR_TARGETS.get(tr_name, 0)
        results.append({
            'node': tr_name,
            'total': int(total),
            'closed': int(closed),
            'rate': rate,
            'target': target,
            'phases': '+'.join(include_phases),
        })
    return results


# ==================== HTML 生成 ====================
def generate_html(overview, group_stats, all_details, skill_a_details, models, trend_data, round_data, tr_data):
    # 序列化所有 JSON
    js_data = {
        'MODELS': models,
        'OVERVIEW': overview,
        'GROUP_STATS': group_stats,
        'ALL_DETAILS': all_details,
        'SKILL_A_DETAILS': skill_a_details,
        'TREND': trend_data,
        'ROUNDS': round_data,
        'TR_DATA': tr_data,
        'GROUP_NAMES': ['全部组别'] + [g['group'] for g in group_stats],
        'GROUP_COLORS': GROUP_COLORS,
        'GROUPS': [{'name': g[0], 'members': g[1]} for g in GROUPS],
    }
    json_str = json.dumps(js_data, ensure_ascii=False)

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PLM缺陷看板</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
<script>
// 取消 datalabels 全局注册，仅在轮次图需要时启用
if (typeof ChartDataLabels !== 'undefined') Chart.unregister(ChartDataLabels);
const PLM_EXPORT_URL = 'https://plm.xgd.com/jmreport/view/1089684809031438336?pageSize=100&claims=QmVhcmVyOmV5SmhiR2NpT2lKSVV6VXhNaUo5LmV5SnpkV0lpT2lKdWFYbDFhbWxoSWl3aVkzSmxZWFJsWkNJNk1UYzNPVE15TmpVeE5qQTFOQ3dpWlhod0lqb3hOemM1TXpZNU56RTJmUS4tMU16UDJya1lYTDhUeW02Y3JzWVFMejBydzlIVHp4Z0lLWHRUMkxZOXItckk5WHpxYlVtYnNIb0RQZ2FWNk5IekZ3dGxkRTBWV1VZRWJhclg2WURUZw==';
</script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif; background:#f0f2f5; color:#333; min-height:100vh; }}
.header {{ background:linear-gradient(135deg,#1a237e 0%,#283593 100%); color:white; padding:14px 24px; display:flex; align-items:center; gap:16px; flex-wrap:wrap; box-shadow:0 2px 8px rgba(0,0,0,.15); position:sticky; top:0; z-index:100; }}
.header h1 {{ font-size:18px; white-space:nowrap; display:flex; align-items:center; gap:8px; }}
.model-area {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
.model-label {{ font-size:13px; opacity:.8; }}
.model-dropdown {{ position:relative; display:inline-block; }}
.model-dropdown-btn {{ padding:5px 14px; border:none; border-radius:6px; font-size:13px; background:rgba(255,255,255,.15); color:white; cursor:pointer; outline:none; display:flex; align-items:center; gap:6px; }}
.model-dropdown-btn:hover {{ background:rgba(255,255,255,.25); }}
.model-menu {{ display:none; position:absolute; top:100%; left:0; margin-top:4px; background:white; border-radius:8px; box-shadow:0 4px 20px rgba(0,0,0,.25); padding:8px; z-index:200; min-width:240px; max-height:380px; overflow-y:auto; }}
.model-menu.show {{ display:block; }}
.model-menu label {{ display:flex; align-items:center; gap:8px; padding:6px 10px; cursor:pointer; font-size:13px; border-radius:4px; color:#333; }}
.model-menu label:hover {{ background:#e8eaf6; }}
.model-menu input[type=checkbox] {{ width:14px; height:14px; accent-color:#1a237e; }}
.model-tags {{ display:flex; gap:4px; flex-wrap:wrap; }}
.model-tag {{ display:inline-flex; align-items:center; gap:3px; padding:2px 10px; border-radius:12px; font-size:12px; background:rgba(255,255,255,.2); color:white; cursor:pointer; }}
.model-tag:hover {{ background:rgba(255,255,255,.35); }}
.model-actions {{ display:flex; gap:6px; margin-top:6px; padding-top:6px; border-top:1px solid #eee; }}
.model-actions button {{ flex:1; padding:4px; border:1px solid #ddd; border-radius:4px; background:white; font-size:12px; cursor:pointer; }}
.model-actions button:hover {{ background:#f5f5f5; }}
.header-time {{ margin-left:auto; font-size:11px; opacity:.6; }}
.header-right {{ display:flex; align-items:center; gap:8px; margin-left:auto; }}
.refresh-btn {{ padding:6px 14px; border:none; border-radius:6px; font-size:12px; background:rgba(255,255,255,.2); color:white; cursor:pointer; white-space:nowrap; }}
.refresh-btn:hover {{ background:rgba(255,255,255,.35); }}
.refresh-btn:disabled {{ opacity:.4; cursor:not-allowed; }}
.progress-wrap {{ width:80px; height:6px; background:rgba(255,255,255,.2); border-radius:3px; overflow:hidden; }}
.progress-bar {{ height:100%; width:0%; background:#4caf50; border-radius:3px; transition:width .3s; }}

.tabs {{ display:flex; background:white; border-bottom:1px solid #e0e0e0; padding:0 24px; position:sticky; top:56px; z-index:50; }}
.tab-btn {{ padding:12px 22px; cursor:pointer; border:none; background:none; font-size:14px; color:#666; border-bottom:3px solid transparent; transition:all .2s; white-space:nowrap; font-weight:500; }}
.tab-btn:hover {{ color:#1a237e; background:#f5f5ff; }}
.tab-btn.active {{ color:#1a237e; border-bottom-color:#1a237e; font-weight:600; }}
.content {{ padding:20px 24px; }}
.tab-panel {{ display:none; }}
.tab-panel.active {{ display:block; }}

.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:14px; margin-bottom:20px; }}
.kpi-card {{ background:white; border-radius:12px; padding:18px 16px; box-shadow:0 2px 8px rgba(0,0,0,.07); text-align:center; transition:transform .2s,box-shadow .2s; }}
.kpi-card:hover {{ transform:translateY(-2px); box-shadow:0 4px 16px rgba(0,0,0,.12); }}
.kpi-val {{ font-size:30px; font-weight:700; margin:6px 0 2px; }}
.kpi-lbl {{ font-size:12px; color:#888; }}
.kpi-sub {{ font-size:11px; color:#bbb; margin-top:2px; }}
.kpi-total .kpi-val {{ color:#1a237e; }}
.kpi-unfixed .kpi-val {{ color:#e53935; }}
.kpi-fixed .kpi-val {{ color:#43a047; }}
.kpi-b .kpi-val {{ color:#e65100; }}

.stats-row {{ display:flex; gap:20px; min-height:460px; }}
.chart-col {{ flex:1; background:white; border-radius:12px; padding:16px; box-shadow:0 2px 8px rgba(0,0,0,.07); }}
.chart-col h3 {{ font-size:14px; margin-bottom:10px; color:#333; }}
.chart-col .chart-wrap {{ position:relative; height:400px; }}
.list-col {{ flex:1; background:white; border-radius:12px; padding:16px; box-shadow:0 2px 8px rgba(0,0,0,.07); display:flex; flex-direction:column; }}
.list-col h3 {{ font-size:14px; margin-bottom:10px; color:#333; }}
.list-col .lc {{ margin-bottom:10px; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
.list-col .lc select {{ padding:5px 10px; border:1px solid #ccc; border-radius:6px; font-size:13px; outline:none; min-width:160px; }}
.list-col .lc .cnt {{ font-size:12px; color:#888; }}
.list-scroll {{ flex:1; overflow-y:auto; max-height:380px; }}
.list-col table {{ width:100%; border-collapse:collapse; font-size:12px; }}
.list-col th {{ background:#f5f5f5; padding:7px 5px; text-align:left; position:sticky; top:0; font-weight:600; color:#555; }}
.list-col td {{ padding:5px; border-bottom:1px solid #f0f0f0; }}
.list-col tr:hover {{ background:#fafaff; }}
.tag {{ display:inline-block; padding:1px 7px; border-radius:10px; font-size:10px; font-weight:500; }}
.tag-sA {{ background:#ffebee; color:#c62828; }}
.tag-sB {{ background:#fff3e0; color:#e65100; }}
.tag-sC {{ background:#e3f2fd; color:#1565c0; }}
.tag-sD {{ background:#e8f5e9; color:#2e7d32; }}
.tag-st-open {{ background:#fff3e0; color:#e65100; }}
.tag-st-fixed {{ background:#e8f5e9; color:#2e7d32; }}
.tag-st-closed {{ background:#e0e0e0; color:#555; }}

.trend-section {{ background:white; border-radius:12px; padding:20px; box-shadow:0 2px 8px rgba(0,0,0,.07); }}
.trend-section h3 {{ font-size:14px; margin-bottom:14px; color:#333; }}
.chart-container {{ position:relative; height:380px; }}

.trend-table {{ width:100%; margin-top:16px; border-collapse:collapse; font-size:12px; }}
.trend-table th {{ background:#f5f5f5; padding:6px 8px; text-align:center; position:sticky; top:0; font-weight:600; color:#555; }}
.trend-table td {{ padding:5px 8px; text-align:center; border-bottom:1px solid #f0f0f0; }}

@media (max-width:900px) {{ .stats-row {{ flex-direction:column; }} .kpi-grid {{ grid-template-columns:repeat(3,1fr); }} .header {{ flex-direction:column; align-items:flex-start; }} .header-time {{ margin-left:0; }} }}
@media (max-width:600px) {{ .kpi-grid {{ grid-template-columns:repeat(2,1fr); }} .tab-btn {{ padding:10px 12px; font-size:13px; }} }}
</style>
</head>
<body>

<div class="header">
  <h1>📊 PLM缺陷看板</h1>
  <div class="model-area">
    <span class="model-label">机型：</span>
    <div class="model-dropdown" id="modelDropdown">
      <button class="model-dropdown-btn" onclick="toggleModelMenu()">▼ 选择机型</button>
      <div class="model-menu" id="modelMenu"></div>
    </div>
    <div class="model-tags" id="modelTags"></div>
  </div>
  <div class="header-right">
    <div class="progress-wrap" id="progressWrap"><div class="progress-bar" id="progressBar"></div></div>
    <button class="refresh-btn" id="refreshBtn" onclick="handleRefresh()">🔄 刷新数据</button>
    <input type="file" id="fileInput" accept=".xlsx" style="display:none" onchange="handleFileUpload(event)">
    <div class="header-time" id="headerTime"></div>
  </div>
</div>

<div class="tabs">
  <button class="tab-btn active" data-tab="overview">📋 缺陷总览</button>
  <button class="tab-btn" data-tab="groups">👥 各组缺陷统计</button>
  <button class="tab-btn" data-tab="trend">📈 修复率关闭率走势</button>
  <button class="tab-btn" data-tab="rounds">🔁 各阶段及轮次</button>
  <button class="tab-btn" data-tab="tr">🎯 TR节点及关闭率</button>
  <button class="tab-btn" data-tab="severe">🔴 严重问题</button>
</div>

<div class="content">
  <div id="panel-overview" class="tab-panel active"><div class="kpi-grid" id="kpiGrid"></div></div>
  <div id="panel-groups" class="tab-panel">
    <div class="stats-row">
      <div class="chart-col"><h3>📊 各组缺陷数量分布 <small style="color:#999;font-weight:400;">（Skill A 公式）</small></h3><div class="chart-wrap"><canvas id="groupChart"></canvas></div></div>
      <div class="list-col">
        <h3>📋 缺陷明细</h3>
        <div class="lc">
          <select id="groupSelect" onchange="onGroupChange()"></select>
          <span class="cnt" id="listCount"></span>
        </div>
        <div class="list-scroll">
          <table><thead><tr><th>编号</th><th>描述</th><th>责任人</th><th>机型</th><th>状态</th><th>严重程度</th></tr></thead><tbody id="listBody"></tbody></table>
        </div>
      </div>
    </div>
  </div>
  <div id="panel-trend" class="tab-panel">
    <div class="trend-section">
      <h3>📈 修复率 &amp; 关闭率走势 <small style="color:#999;font-weight:400;">（全机型数据，按日统计）</small></h3>
      <div class="chart-container"><canvas id="trendChart"></canvas></div>
      <table class="trend-table"><thead><tr><th>日期</th><th>缺陷总数</th><th>修复率</th><th>关闭率</th></tr></thead><tbody id="trendTableBody"></tbody></table>
    </div>
  </div>
  <div id="panel-rounds" class="tab-panel">
    <div class="trend-section">
      <h3>🔁 各测试轮次缺陷数量分布 <small style="color:#999;font-weight:400;">（HV0.1/SV0.1已归一化为V0.1，随机型筛选变化）</small></h3>
      <div class="chart-container"><canvas id="roundChart"></canvas></div>
      <table class="trend-table" style="margin-top:14px;"><thead><tr><th>测试轮次</th><th>缺陷数量</th></tr></thead><tbody id="roundTableBody"></tbody></table>
    </div>
  </div>
  <div id="panel-tr" class="tab-panel">
    <div class="trend-section">
      <h3>🎯 TR节点关闭率对比 <small style="color:#999;font-weight:400;">（累计关闭率 vs 目标值，随机型筛选变化）</small></h3>
      <div class="chart-container" style="height:350px;"><canvas id="trChart"></canvas></div>
      <table class="trend-table" style="margin-top:14px;"><thead><tr><th>TR节点</th><th>包含阶段</th><th>缺陷总数</th><th>已关闭+评审关闭</th><th>关闭率</th><th>目标值</th><th>状态</th><th>差距</th></tr></thead><tbody id="trTableBody"></tbody></table>
    </div>
  </div>
  <div id="panel-severe" class="tab-panel">
    <div class="trend-section">
      <h3>🔴 严重问题列表 <small style="color:#999;font-weight:400;">（A：致命 / B：严重，随机型筛选变化）</small></h3>
      <div class="lc" style="margin-bottom:12px;">
        <select id="severeFilter" onchange="renderSevere()">
          <option value="all">全部</option>
          <option value="unfixed">未修复</option>
          <option value="to_verify">已修复待验证</option>
        </select>
        <span class="cnt" id="severeCount"></span>
      </div>
      <div class="list-scroll" style="max-height:500px;">
        <table><thead><tr><th>编号</th><th>问题描述</th><th>责任人</th><th>机型</th><th>严重程度</th><th>状态</th></tr></thead><tbody id="severeBody"></tbody></table>
      </div>
    </div>
  </div>
</div>

<script>
const DATA = {json_str};

let selModels = [];
let selGroup = '全部组别';
let groupChart = null, trendChart = null, roundChart = null, trChart = null;

// ===== Init =====
function init() {{
  initModelMenu();
  initGroupSelect();
  renderOverview();
  renderGroupChart();
  renderGroupList();
  renderTrend();
  renderRoundChart();
  renderTrChart();
  renderSevere();
  document.querySelectorAll('.tab-btn').forEach(b => b.addEventListener('click', function() {{
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(x => x.classList.remove('active'));
    this.classList.add('active');
    document.getElementById('panel-' + this.dataset.tab).classList.add('active');
    if (this.dataset.tab === 'groups' && groupChart) groupChart.resize();
    if (this.dataset.tab === 'trend' && trendChart) trendChart.resize();
    if (this.dataset.tab === 'rounds' && roundChart) roundChart.resize();
    if (this.dataset.tab === 'tr' && trChart) trChart.resize();
  }}));
  document.addEventListener('click', function(e) {{
    const dd = document.getElementById('modelDropdown');
    if (!dd.contains(e.target)) document.getElementById('modelMenu').classList.remove('show');
  }});
}}

function initModelMenu() {{
  const menu = document.getElementById('modelMenu');
  // 搜索框
  const searchInput = document.createElement('input');
  searchInput.type = 'text';
  searchInput.placeholder = '🔍 搜索机型...';
  searchInput.style.cssText = 'width:100%;padding:6px 8px;border:1px solid #ddd;border-radius:6px;font-size:13px;outline:none;margin-bottom:6px;box-sizing:border-box;';
  searchInput.oninput = function() {{
    const q = this.value.trim().toLowerCase();
    const items = menu.querySelectorAll('.model-item');
    let matchCount = 0;
    items.forEach(item => {{
      const name = item.dataset.name.toLowerCase();
      if(!q || name.includes(q)) {{
        item.style.display = '';
        if(q) {{ item.querySelector('input').checked = true; matchCount++; }}
      }} else {{
        item.style.display = 'none';
      }}
    }});
    if(q) {{
      // Auto-select searched models
      selModels = [];
      items.forEach(item => {{
        if(item.style.display !== 'none') {{
          selModels.push(item.dataset.name);
        }}
      }});
      const allCb = document.querySelector('#modelMenu > input[type=checkbox]');
      if(allCb) allCb.checked = selModels.length === DATA.MODELS.length;
      updateModelTags(); refreshAll();
    }}
  }};
  searchInput.onfocus = function() {{ this.select(); }};
  menu.appendChild(searchInput);
  // 全选勾选框
  const allLabel = document.createElement('label');
  allLabel.style.cssText = 'border-bottom:1px solid #eee;padding-bottom:8px;margin-bottom:4px;font-weight:600;display:flex;align-items:center;gap:8px;font-size:13px;';
  const allCb = document.createElement('input');
  allCb.type = 'checkbox'; allCb.checked = false;
  allCb.onchange = function() {{
    const checked = allCb.checked;
    menu.querySelectorAll('.model-item input[type=checkbox]').forEach(c => c.checked = checked);
    selModels = checked ? [...DATA.MODELS] : [];
    updateModelTags(); refreshAll();
  }};
  allLabel.appendChild(allCb); allLabel.appendChild(document.createTextNode(' 全选 (' + DATA.MODELS.length + ' 个机型)'));
  menu.appendChild(allLabel);
  // 各机型
  DATA.MODELS.forEach(m => {{
    const label = document.createElement('label');
    label.className = 'model-item';
    label.dataset.name = m;
    label.style.cssText = 'display:flex;align-items:center;gap:8px;padding:4px 8px;cursor:pointer;font-size:13px;border-radius:4px;color:#333;';
    label.onmouseenter = function() {{ this.style.background = '#e8eaf6'; }};
    label.onmouseleave = function() {{ this.style.background = ''; }};
    const cb = document.createElement('input');
    cb.type = 'checkbox'; cb.checked = false;
    cb.onchange = function() {{
      if (cb.checked) {{ if(!selModels.includes(m)) selModels.push(m); }}
      else {{ selModels = selModels.filter(x => x !== m); }}
      const allCb = document.querySelector('#modelMenu > input[type=checkbox]');
      if(allCb) allCb.checked = selModels.length === DATA.MODELS.length;
      updateModelTags(); refreshAll();
    }};
    label.appendChild(cb); label.appendChild(document.createTextNode(m));
    menu.appendChild(label);
  }});
  updateModelTags();
}}

function toggleModelMenu() {{ document.getElementById('modelMenu').classList.toggle('show'); }}

function updateModelTags() {{
  const tags = document.getElementById('modelTags');
  tags.innerHTML = '';
  selModels.forEach(m => {{
    const t = document.createElement('span'); t.className='model-tag';
    t.textContent = m + ' ✕';
    t.onclick = function() {{ selModels = selModels.filter(x => x !== m);
      document.querySelectorAll('#modelMenu input[type=checkbox]').forEach(c => {{ if(c.nextSibling && c.nextSibling.textContent && c.nextSibling.textContent.trim() === m) c.checked = false; }});
      const allCb = document.querySelector('#modelMenu input[type=checkbox]');
      if(allCb) allCb.checked = selModels.length === DATA.MODELS.length;
      updateModelTags(); refreshAll(); }};
    tags.appendChild(t);
  }});
}}

function initGroupSelect() {{
  const sel = document.getElementById('groupSelect'); sel.innerHTML = '';
  DATA.GROUP_NAMES.forEach(g => {{ const o = document.createElement('option'); o.value=g; o.textContent=g; sel.appendChild(o); }});
}}

function filterByModel(items) {{
  return items.filter(d => selModels.includes(d.model));
}}

// ===== Tab 1 =====
function renderOverview() {{
  const filtered = DATA.ALL_DETAILS.filter(d => d.status !== '测试审核不通过关闭').filter(d => selModels.includes(d.model));
  let total=filtered.length, unrepaired=0, closedReview=0, toVerify=0;
  const uStat=['开启','修复中','已分配','正在审阅','测试审核'];
  filtered.forEach(d => {{
    if(uStat.includes(d.status)) unrepaired++;
    if(d.status==='已关闭'||d.status==='评审关闭') closedReview++;
    if(d.status==='已修复待验证') toVerify++;
  }});
  const fixed = closedReview + toVerify;
  const fr = total>0?(fixed/total*100).toFixed(1):'0.0';
  const cr = total>0?(closedReview/total*100).toFixed(1):'0.0';
  document.getElementById('kpiGrid').innerHTML =
    `<div class="kpi-card kpi-total"><div class="kpi-lbl">缺陷总数</div><div class="kpi-val">${{total}}</div><div class="kpi-sub">已剔除测试审核不通过关闭</div></div>` +
    `<div class="kpi-card kpi-unfixed"><div class="kpi-lbl">未修复缺陷</div><div class="kpi-val">${{unrepaired}}</div><div class="kpi-sub">开启/修复中/已分配</div></div>` +
    `<div class="kpi-card kpi-fixed"><div class="kpi-lbl">已关闭+评审关闭</div><div class="kpi-val">${{closedReview}}</div><div class="kpi-sub">用于计算关闭率</div></div>` +
    `<div class="kpi-card kpi-fixed"><div class="kpi-lbl">已修复待验证</div><div class="kpi-val">${{toVerify}}</div><div class="kpi-sub">待验证修复</div></div>` +
    `<div class="kpi-card" style="border-left:3px solid #43a047;"><div class="kpi-lbl">缺陷修复率</div><div class="kpi-val">${{fr}}%</div><div class="kpi-sub">(已关闭+评审关闭+已修复待验证)/总数</div></div>` +
    `<div class="kpi-card" style="border-left:3px solid #1a237e;"><div class="kpi-lbl">缺陷关闭率</div><div class="kpi-val">${{cr}}%</div><div class="kpi-sub">(已关闭+评审关闭)/总数</div></div>`;
}}

// ===== Tab 2 =====
function getSkillADetails() {{
  // 从全量数据中按 Skill A 规则 + 选中机型筛选
  const skillAStatuses = ['测试审核不通过关闭', '已修复待验证', '已关闭', '评审关闭'];
  const skillAModels = ['UN10', 'UN10R', 'UN10P', 'UN10RS'];
  return DATA.ALL_DETAILS.filter(d =>
    selModels.includes(d.model) &&
    skillAModels.includes(d.model) &&
    !skillAStatuses.includes(d.status)
  );
}}

function renderGroupChart() {{
  const ctx = document.getElementById('groupChart').getContext('2d');
  const filtered = getSkillADetails();
  const allGroupNames = DATA.GROUP_NAMES.filter(g => g !== '全部组别');
  const counts = {{}};
  filtered.forEach(d => {{ counts[d.group] = (counts[d.group]||0)+1; }});
  const labels = allGroupNames;
  const values = labels.map(g => counts[g]||0);
  const colors = labels.map(g => DATA.GROUP_COLORS[g]||'#e0e0e0');
  if(groupChart) groupChart.destroy();
  groupChart = new Chart(ctx, {{
    type:'bar', data:{{ labels, datasets:[{{ label:'缺陷数量', data:values, backgroundColor:colors, borderColor:colors, borderWidth:1, borderRadius:4 }}] }},
    options:{{
      responsive:true, maintainAspectRatio:false, indexAxis:'y',
      plugins:{{
        legend:{{display:false}},
        tooltip:{{ backgroundColor:'rgba(0,0,0,.8)', padding:10, cornerRadius:6 }},
        datalabels:{{
          anchor:'end', align:'end', offset:2,
          font:{{weight:'bold',size:10}},
          color:'#444',
          formatter:function(v){{ return v>0?v:''; }}
        }}
      }},
      scales:{{
        x:{{ beginAtZero:true, ticks:{{stepSize:1,font:{{size:11}}}}, grid:{{color:'rgba(0,0,0,.06)'}} }},
        y:{{ ticks:{{font:{{size:11}}}}, grid:{{display:false}} }}
      }}
    }},
    plugins: [ChartDataLabels]
  }});
  // 更新下拉菜单显示各组的数量
  updateGroupSelectCounts(counts);
}}

function updateGroupSelectCounts(counts) {{
  const sel = document.getElementById('groupSelect');
  const total = getSkillADetails().length;
  if(sel.options.length > 0) {{
    sel.options[0].textContent = `全部组别 (${{total}} 条)`;
  }}
  for(let i=1; i<sel.options.length; i++) {{
    const g = sel.options[i].value;
    const c = counts[g]||0;
    sel.options[i].textContent = `${{g}} (${{c}} 条)`;
  }}
}}

function onGroupChange() {{
  selGroup = document.getElementById('groupSelect').value;
  renderGroupList();
}}

function renderGroupList() {{
  const filtered = getSkillADetails();
  let items = selGroup === '全部组别' ? filtered : filtered.filter(d => d.group === selGroup);
  document.getElementById('listCount').textContent = `共 ${{items.length}} 条`;
  document.getElementById('listBody').innerHTML = '';
  items.slice(0,200).forEach(d => {{
    const sc = d.severity&&d.severity.includes('A')?'tag-sA':d.severity&&d.severity.includes('B')?'tag-sB':d.severity&&d.severity.includes('C')?'tag-sC':d.severity&&d.severity.includes('D')?'tag-sD':'';
    const stc = d.status==='已关闭'?'tag-st-closed':['已修复待验证','已解决'].includes(d.status)?'tag-st-fixed':'tag-st-open';
    const tr = document.createElement('tr');
    tr.innerHTML = `<td><small>${{d.id}}</small></td><td><span title="${{d.name.replace(/"/g,'&quot;')}}">${{d.name.length>18?d.name.substring(0,18)+'...':d.name}}</span></td><td><small>${{d.person}}</small></td><td><small>${{d.model}}</small></td><td><span class="tag ${{stc}}">${{d.status}}</span></td><td><span class="tag ${{sc}}">${{d.severity||''}}</span></td>`;
    document.getElementById('listBody').appendChild(tr);
  }});
  if(items.length>200) {{
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="6" style="text-align:center;color:#999;">仅显示前 200 条，共 ${{items.length}} 条</td>`;
    document.getElementById('listBody').appendChild(tr);
  }}
}}

// ===== Tab 3 =====
function renderTrend() {{
  if(DATA.TREND.length===0) return;
  const ctx = document.getElementById('trendChart').getContext('2d');
  const labels = DATA.TREND.map(t => t.label);
  // 根据选中机型动态计算
  const useModelFilter = selModels.length > 0 && selModels.length < DATA.MODELS.length;
  const fixRates = DATA.TREND.map(t => {{
    if(!useModelFilter) return t.all_fix;
    let total=0, closed=0, toVerify=0;
    selModels.forEach(m => {{
      const md = t.md[m];
      if(md) {{ total+=md.t; closed+=md.c; toVerify+=md.v; }}
    }});
    return total>0 ? (closed+toVerify)/total*100 : 0;
  }});
  const closeRates = DATA.TREND.map(t => {{
    if(!useModelFilter) return t.all_close;
    let total=0, closed=0;
    selModels.forEach(m => {{
      const md = t.md[m];
      if(md) {{ total+=md.t; closed+=md.c; }}
    }});
    return total>0 ? closed/total*100 : 0;
  }});
  const totals = DATA.TREND.map(t => {{
    if(!useModelFilter) return t.all_total;
    let total=0;
    selModels.forEach(m => {{
      const md = t.md[m];
      if(md) total+=md.t;
    }});
    return total;
  }});
  if(trendChart) trendChart.destroy();
  trendChart = new Chart(ctx, {{
    type:'line',
    data:{{
      labels,
      datasets:[
        {{ label:'修复率 (%)', data:fixRates, borderColor:'#43a047', backgroundColor:'rgba(67,160,71,.1)', fill:true, tension:.3, pointRadius:4, pointHoverRadius:6, borderWidth:2 }},
        {{ label:'关闭率 (%)', data:closeRates, borderColor:'#1a237e', backgroundColor:'rgba(26,35,126,.1)', fill:true, tension:.3, pointRadius:4, pointHoverRadius:6, borderWidth:2 }},
        {{ label:'缺陷总数', data:totals, borderColor:'#f57f17', backgroundColor:'rgba(245,127,23,.1)', fill:true, tension:.3, pointRadius:3, pointHoverRadius:5, borderWidth:1.5, yAxisID:'y1' }}
      ]
    }},
    options:{{
      responsive:true, maintainAspectRatio:false,
      interaction:{{ mode:'index', intersect:false }},
      plugins:{{
        legend:{{ position:'top', labels:{{ font:{{size:12}}, padding:16 }} }},
        tooltip:{{ backgroundColor:'rgba(0,0,0,.8)', padding:12, cornerRadius:6, callbacks:{{ label:function(ctx){{ return ctx.dataset.label+': '+ctx.parsed.y.toFixed(1)+(ctx.dataset.label.includes('率')?'%':''); }} }} }}
      }},
      scales:{{
        y:{{ beginAtZero:true, max:100, position:'left', title:{{display:true,text:'百分比 (%)',font:{{size:11}}}}, ticks:{{font:{{size:11}},callback:v=>v+'%'}}, grid:{{color:'rgba(0,0,0,.06)'}} }},
        y1:{{ beginAtZero:true, position:'right', title:{{display:true,text:'缺陷数量',font:{{size:11}}}}, grid:{{display:false}}, ticks:{{font:{{size:11}}}} }},
        x:{{ ticks:{{font:{{size:11}},maxRotation:45}}, grid:{{display:false}} }}
      }}
    }}
  }});
  // 表格
  document.getElementById('trendTableBody').innerHTML = DATA.TREND.map((t,i) =>
    `<tr><td>${{t.label}}</td><td>${{totals[i]}}</td><td>${{fixRates[i].toFixed(1)}}%</td><td>${{closeRates[i].toFixed(1)}}%</td></tr>`
  ).join('');
}}

// ===== Tab 4 =====
function renderRoundChart() {{
  if(DATA.ROUNDS.length===0) return;
  const ctx = document.getElementById('roundChart').getContext('2d');
  // 筛选机型
  const filtered = DATA.ALL_DETAILS.filter(d => d.status !== '测试审核不通过关闭').filter(d => selModels.includes(d.model));
  const counts = {{}};
  filtered.forEach(d => {{
    let rnd = d.round;
    if(rnd) counts[rnd] = (counts[rnd]||0) + 1;
  }});
  // 过滤数值为0且无数据的轮次
  const allRounds = DATA.ROUNDS.map(r => r.round);
  const labels = allRounds.filter(l => counts[l] && counts[l] > 0);
  const values = labels.map(l => counts[l]||0);
  const colors = values.map(v => {{
    if(v>100) return '#e53935';
    if(v>50) return '#f57f17';
    if(v>20) return '#fdd835';
    return '#43a047';
  }});
  if(roundChart) roundChart.destroy();
  roundChart = new Chart(ctx, {{
    type:'bar',
    data:{{ labels, datasets:[{{
      label:'缺陷数量', data:values, backgroundColor:colors, borderColor:colors, borderWidth:1, borderRadius:4
    }}] }},
    options:{{
      responsive:true, maintainAspectRatio:false,
      plugins:{{
        legend:{{display:false}},
        tooltip:{{ backgroundColor:'rgba(0,0,0,.8)', padding:10, cornerRadius:6, callbacks:{{ label:function(ctx){{ return '数量: '+ctx.parsed.y; }} }} }},
        datalabels:{{ anchor:'end', align:'end', color:'#333', font:{{weight:'bold',size:11}}, formatter:function(v){{ return v>0?v:''; }} }}
      }},
      scales:{{
        x:{{ ticks:{{font:{{size:11}},maxRotation:45}}, grid:{{display:false}} }},
        y:{{ beginAtZero:true, ticks:{{stepSize:1,font:{{size:11}}}}, grid:{{color:'rgba(0,0,0,.06)'}} }}
      }}
    }},
    plugins: [ChartDataLabels]
  }});
  // 表格
  document.getElementById('roundTableBody').innerHTML = labels.map((l,i) =>
    `<tr><td>${{l}}</td><td>${{values[i]}}</td></tr>`
  ).join('');
}}

// ===== Tab 5 =====
function renderTrChart() {{
  if(DATA.TR_DATA.length===0) return;
  const ctx = document.getElementById('trChart').getContext('2d');
  // 从全量数据中动态计算
  const filtered = DATA.ALL_DETAILS.filter(d => d.status !== '测试审核不通过关闭').filter(d => selModels.includes(d.model));
  const trPhases = ['TR1','TR2','TR3','TR4','结项'];
  const trDisplay = ['TR2','TR3','TR4','结项'];
  const trTargets = {{'TR2':80,'TR3':90,'TR4':93,'结项':95}};
  const results = [];
  trDisplay.forEach(name => {{
    const includePhases = name === '结项' ? ['结项','TR1','TR2','TR3','TR4'] : trPhases.slice(0, trPhases.indexOf(name)+1);
    const subset = filtered.filter(d => includePhases.includes(d.resolvePhase));
    const total = subset.length;
    const closed = subset.filter(d => d.status==='已关闭'||d.status==='评审关闭').length;
    const rate = total>0 ? (closed/total*100).toFixed(1) : '0.0';
    results.push({{ node:name, total, closed, rate:parseFloat(rate), target:trTargets[name] }});
  }});
  const labels = results.map(r => r.node);
  const rates = results.map(r => r.rate);
  const targets = results.map(r => r.target);
  if(trChart) trChart.destroy();
  trChart = new Chart(ctx, {{
    type:'bar',
    data:{{
      labels,
      datasets:[
        {{ label:'实际关闭率', data:rates, backgroundColor:rates.map(v => v>=80?'rgba(67,160,71,0.7)':'rgba(229,57,53,0.7)'), barPercentage:0.45, categoryPercentage:0.6, borderRadius:4, order:2 }},
        {{ label:'目标值', data:targets, type:'line', borderColor:'#1a237e', borderWidth:2.5, borderDash:[6,3], pointBackgroundColor:'#1a237e', pointBorderColor:'white', pointBorderWidth:2, pointRadius:6, pointStyle:'circle', fill:false, tension:.15, order:1 }}
      ]
    }},
    options:{{
      responsive:true, maintainAspectRatio:false,
      plugins:{{
        legend:{{ position:'top', labels:{{ font:{{size:12}}, padding:16, usePointStyle:true }} }},
        tooltip:{{ backgroundColor:'rgba(0,0,0,.8)', padding:10, cornerRadius:6, callbacks:{{ label:function(ctx){{ return ctx.dataset.label+': '+ctx.parsed.y+'%'; }} }} }},
        datalabels:{{
          font:{{weight:'bold',size:11}},
          color:function(ctx){{ return ctx.datasetIndex===0?'#333':'#1a237e'; }},
          anchor:function(ctx){{ return ctx.datasetIndex===0?'end':'end'; }},
          align:function(ctx){{ return ctx.datasetIndex===0?'end':'end'; }},
          offset:2,
          formatter:function(v,ctx){{ return v>0?v+'%':''; }}
        }}
      }},
      scales:{{
        y:{{ beginAtZero:true, max:105, ticks:{{font:{{size:11}},callback:v=>v+'%'}}, grid:{{color:'rgba(0,0,0,.06)'}}, title:{{display:true,text:'关闭率 (%)',font:{{size:11}}}} }},
        x:{{ ticks:{{font:{{size:12}}}}, grid:{{display:false}} }}
      }}
    }},
    plugins: [ChartDataLabels]
  }});
  // 表格（优化显示）
  document.getElementById('trTableBody').innerHTML = results.map(r =>
    `<tr>
      <td><strong>${{r.node}}</strong></td>
      <td>${{r.node==='结项'?'结项+TR1~TR4':'TR1~'+r.node}}</td>
      <td>${{r.total}}</td>
      <td>${{r.closed}}</td>
      <td><span style="font-weight:700;color:${{r.rate>=r.target?'#43a047':'#e53935'}};">${{r.rate}}%</span></td>
      <td>${{r.target}}%</td>
      <td><span style="display:inline-block;padding:2px 10px;border-radius:10px;font-size:11px;font-weight:600;color:white;background:${{r.rate>=r.target?'#43a047':'#e53935'}};">${{r.rate>=r.target?'✅ 达标':'❌ 未达标'}}</span></td>
      <td style="color:${{r.rate>=r.target?'#43a047':'#999'}};font-size:11px;">${{r.rate>=r.target?'':'差 '+(r.target-r.rate).toFixed(1)+'%'}}</td>
    </tr>`
  ).join('');
}}

// ===== 数据刷新 =====
function handleRefresh() {{
  const btn = document.getElementById('refreshBtn');
  const bar = document.getElementById('progressBar');
  btn.disabled = true; btn.textContent = '⏳ 获取中...';
  bar.style.width = '10%';
  // 打开 PLM 页面让用户下载
  window.open(PLM_EXPORT_URL, '_blank');
  bar.style.width = '40%';
  // 延迟显示文件上传提示，等待用户下载后上传
  setTimeout(function() {{
    bar.style.width = '60%';
    document.getElementById('fileInput').click();
  }}, 1500);
}}

function handleFileUpload(event) {{
  const file = event.target.files[0];
  if (!file) return;
  const bar = document.getElementById('progressBar');
  const btn = document.getElementById('refreshBtn');
  bar.style.width = '70%';
  const reader = new FileReader();
  reader.onload = function(e) {{
    try {{
      bar.style.width = '80%';
      const data = new Uint8Array(e.target.result);
      const workbook = XLSX.read(data, {{type:'array'}});
      const sheet = workbook.Sheets[workbook.SheetNames[0]];
      const json = XLSX.utils.sheet_to_json(sheet);
      if (!json || json.length === 0) throw new Error('表格为空');
      bar.style.width = '90%';
      // 重建数据
      rebuildFromRaw(json);
      bar.style.width = '100%';
      btn.textContent = '✅ 刷新成功';
      setTimeout(function() {{
        btn.disabled = false; btn.textContent = '🔄 刷新数据';
        bar.style.width = '0%';
      }}, 2000);
    }} catch(err) {{
      console.error(err);
      bar.style.width = '0%';
      btn.disabled = false; btn.textContent = '❌ 失败，重试';
      alert('文件解析失败: ' + err.message);
    }}
  }};
  reader.readAsArrayBuffer(file);
  // 重置 input 以便再次选同一文件
  event.target.value = '';
}}

function rebuildFromRaw(raw) {{
  // 重新构建 ALL_DETAILS
  const newDetails = [];
  for (const row of raw) {{
    const model = String(row['机型'] || '');
    const status = String(row['问题状态'] || '');
    const person = String(row['流程未执行人'] || '');
    const resolvePhase = String(row['计划解决阶段'] || '');
    const roundRaw = String(row['测试轮数'] || '');
    newDetails.push({{
      id: String(row['问题编号'] || ''),
      name: String(row['问题名称'] || '').substring(0,80),
      person: person,
      model: model,
      status: status,
      severity: String(row['严重程度'] || ''),
      group: matchGroup(person),
      round: normalizeRound(roundRaw),
      resolvePhase: resolvePhase,
    }});
  }}
  // 更新全局数据
  DATA.ALL_DETAILS = newDetails;
  DATA.MODELS = [...new Set(newDetails.map(d => d.model).filter(Boolean))].sort();
  // 更新机型下拉
  selModels = [...DATA.MODELS];
  document.getElementById('modelMenu').innerHTML = '';
  document.querySelector('.model-tags').innerHTML = '';
  initModelMenu();
  // 重新渲染所有图表
  refreshAll();
}}

function matchGroup(personStr) {{
  for (const g of DATA.GROUPS) {{
    for (const m of g.members) {{
      if (personStr.includes(m)) return g.name;
    }}
  }}
  return '未分配';
}}

function normalizeRound(val) {{
  if (!val || ['','-','/','无','V',' '].includes(val.trim())) return null;
  const s = val.trim();
  let m = s.match(/(?:HV|SV|RV|DVT)?[ -]*(V[0-9]+[.][0-9]+)/i);
  if (m) return m[1].startsWith('V') ? m[1] : 'V' + m[1];
  m = s.match(/V?([0-9]+[.][0-9]+)/);
  if (m) return 'V' + m[1];
  m = s.match(/^TR([0-9]+)$/i);
  if (m) return 'TR' + m[1];
  const phases = ['PVT','EVT','DVT','LMT'];
  for (const p of phases) {{ if (s.toUpperCase().includes(p)) return p; }}
  return null;
}}

// ===== Tab 6 =====
function renderSevere() {{
  const filtered = DATA.ALL_DETAILS.filter(d => d.status !== '测试审核不通过关闭').filter(d => selModels.includes(d.model));
  // A致命/B严重
  const severe = filtered.filter(d => d.severity && (d.severity.includes('A') || d.severity.includes('B')));
  const filterVal = document.getElementById('severeFilter').value;
  let items;
  if (filterVal === 'unfixed') {{
    const unrepairedStatuses = ['开启', '修复中', '已分配', '正在审阅', '测试审核'];
    items = severe.filter(d => unrepairedStatuses.includes(d.status));
  }} else if (filterVal === 'to_verify') {{
    items = severe.filter(d => d.status === '已修复待验证');
  }} else {{
    items = severe;
  }}
  document.getElementById('severeCount').textContent = `共 ${{items.length}} 条`;
  document.getElementById('severeBody').innerHTML = '';
  items.slice(0, 500).forEach(d => {{
    const sc = d.severity.includes('A')?'tag-sA':'tag-sB';
    const stc = d.status==='已关闭'?'tag-st-closed':['已修复待验证','已解决'].includes(d.status)?'tag-st-fixed':'tag-st-open';
    const tr = document.createElement('tr');
    tr.innerHTML = `<td><small>${{d.id}}</small></td><td><span title="${{d.name.replace(/"/g,'&quot;')}}">${{d.name.length>25?d.name.substring(0,25)+'...':d.name}}</span></td><td><small>${{d.person}}</small></td><td><small>${{d.model}}</small></td><td><span class="tag ${{sc}}">${{d.severity}}</span></td><td><span class="tag ${{stc}}">${{d.status}}</span></td>`;
    document.getElementById('severeBody').appendChild(tr);
  }});
  if (items.length > 500) {{
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="6" style="text-align:center;color:#999;">仅显示前 500 条，共 ${{items.length}} 条</td>`;
    document.getElementById('severeBody').appendChild(tr);
  }}
}}

function refreshAll() {{ renderOverview(); renderGroupChart(); renderGroupList(); renderRoundChart(); renderTrChart(); renderSevere(); }}

document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>'''


# ==================== 主流程 ====================
def main():
    print('=' * 50)
    print('UN10 互动式缺陷看板生成器（三栏设计）')
    print('=' * 50)

    latest_file = load_latest_file()
    df = load_file(latest_file)
    print(f'[INFO] 全部数据: {len(df)} 行')

    overview = calc_overview(df)
    print(f'[INFO] 总览: {overview}')

    # 全部明细（用于总览栏）
    all_details = build_details_list(df)

    # Skill A 筛选后的数据（用于组统计栏 - 按 TARGET_MODELS 过滤 + 状态剔除）
    df_skill_a = df[df['机型'].isin(TARGET_MODELS)]
    df_skill_a = df_skill_a[~df_skill_a['问题状态'].isin(EXCLUDE_STATUS)]
    print(f'[INFO] Skill A筛选后: {len(df_skill_a)} 行')

    group_stats = calc_group_stats(df_skill_a)
    print(f'[INFO] 组统计: {len(group_stats)} 组')

    skill_a_details = build_details_list(df_skill_a)
    print(f'[INFO] Skill A详情: {len(skill_a_details)} 条')

    models = sorted(df['机型'].unique().tolist())
    print(f'[INFO] 机型: {models}')

    print('[INFO] 收集趋势数据...')
    trend = collect_trend_data()
    print(f'[INFO] 趋势数据: {len(trend)} 个时间点')

    print('[INFO] 计算轮次分布...')
    round_data = calc_round_stats(df)
    print(f'[INFO] 轮次数量: {len(round_data)}')

    print('[INFO] 计算TR节点关闭率...')
    tr_data = calc_tr_closure(df)
    for t in tr_data:
        print(f'  {t["node"]}: {t["rate"]}% (目标 {t["target"]}%)')
    print(f'[INFO] TR节点数: {len(tr_data)}')

    print('[INFO] 生成 HTML 看板...')
    html = generate_html(overview, group_stats, all_details, skill_a_details, models, trend, round_data, tr_data)

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    output_path = os.path.join(DEFECT_DIR, f'UN10_缺陷看板_三栏_{timestamp}.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'[OK] 看板已保存: {output_path}')
    return output_path


if __name__ == '__main__':
    main()