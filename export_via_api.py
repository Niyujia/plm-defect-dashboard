# -*- coding: utf-8 -*-
"""
Skill C 兜底导出：直接走 PLM API 拉全量缺陷数据并落盘为报表 Excel。

背景：PLM 的 jmreport 导出接口在数据量超过 10000 时会请求第 2 页
      （OFFSET 10000 LIMIT 10000），服务端返回
      "An I/O error occurred while sending to the backend." 导致导出失败。
      而 API 通路（jmreport/show）走的是另一套查询，total≈9974 一页即可取完。

用法：python export_via_api.py
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server import get_token, fetch_defect_data, items_to_df  # noqa: E402

DEFECT_DIR = r'F:\UN10\PVT\缺陷'
MIN_ROWS = 500


def main():
    token = get_token()
    if not token:
        print('[FAIL] PLM token 无效，无法走 API 兜底')
        return 1

    items = fetch_defect_data(token)
    if not items:
        print('[FAIL] API 返回空数据')
        return 1

    df = items_to_df(items)
    if len(df) < MIN_ROWS:
        print(f'[FAIL] 数据过少: {len(df)} 行（阈值 {MIN_ROWS}）')
        return 1

    today = datetime.now().strftime('%Y%m%d')
    seq = 1
    while True:
        dest = os.path.join(DEFECT_DIR, f'产品问题报表-{today}-{seq:02d}.xlsx')
        if not os.path.exists(dest):
            break
        seq += 1

    df.to_excel(dest, index=False)
    print(f'[OK] API 兜底导出成功: {os.path.basename(dest)}（{len(df)} 行 / {len(df.columns)} 列）')
    print(f'     列: {", ".join(df.columns)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())