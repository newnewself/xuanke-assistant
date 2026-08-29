"""生成「资料来源」分享文件：教务导出原始表 + 课程类别/课程归属/余量 三列。

产出（data/ 下，均被 .gitignore 排除）：
- 资料来源_按条件查询上课情况.xlsx  供下载的完整表格文件
- source_meta.json                 文件元信息（行/列数等，供页面展示）

用法：python -X utf8 -m app.source_gen <教务导出的xlsx> [--updated 2026/8/28]
隐私：导出若含教师联系电话列，生成时显式丢弃，与入库红线一致。
"""
import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from .config import DATA_DIR
from .categories import load_custom_categories, match_custom_category
from .etl import load_course_info

XLSX_OUT = DATA_DIR / "资料来源_按条件查询上课情况.xlsx"
META_OUT = DATA_DIR / "source_meta.json"


def _norm_code(s: str) -> str:
    s = str(s).strip()
    return s[:-2] if s.endswith(".0") else s


def generate(src_path: str | Path, updated_at: str, out_dir: Path = DATA_DIR) -> dict:
    df = pd.read_excel(src_path, header=3)
    df = df.dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]
    # 丢弃无名首列（pandas 命名为 Unnamed: N）与电话列（若有）
    df = df.loc[:, [c for c in df.columns
                    if c and not c.startswith("Unnamed") and c != "教师联系电话"]]
    if "选课课号" not in df.columns:
        raise ValueError("不是《按条件查询课程》格式的文件：缺少“选课课号”列")

    info = load_course_info(out_dir / "课程基本信息.xlsx")
    codes = df["课程号"].map(_norm_code)
    # 自定义类别（data/custom_categories.json）命中则覆盖，与 ETL 口径一致；名单为空时无影响
    custom = load_custom_categories()
    hits = [match_custom_category(c, n, custom)
            for c, n in zip(codes, df["课程名称"].astype(str))]
    df["课程类别"] = [h or info.get(c, ("", ""))[0] for h, c in zip(hits, codes)]
    df["课程归属"] = codes.map(lambda c: info.get(c, ("", ""))[1])
    df["余量"] = (pd.to_numeric(df["教学班人数"], errors="coerce")
                  - pd.to_numeric(df["选课人数"], errors="coerce")).round(2)

    # 整数值的数值列去掉 .0（学分 2.0 → 2），预览和下载都更干净
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_float_dtype(s) and s.dropna().mod(1).eq(0).all():
            df[col] = s.astype("Int64")

    xlsx_out = out_dir / XLSX_OUT.name
    meta_out = out_dir / META_OUT.name
    df.to_excel(xlsx_out, index=False)

    meta_out.write_text(
        json.dumps({"updated_at": updated_at, "rows": len(df), "cols": len(df.columns),
                    "size_bytes": xlsx_out.stat().st_size},
                   ensure_ascii=False),
        encoding="utf-8")
    return {"rows": len(df), "cols": len(df.columns), "xlsx": str(xlsx_out), "meta": str(meta_out)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="生成资料来源分享表")
    ap.add_argument("xlsx", help="教务系统导出的《按条件查询上课情况.xlsx》路径")
    ap.add_argument("--updated", default=date.today().strftime("%Y/%m/%d"), help="展示用的更新日期")
    args = ap.parse_args()
    r = generate(args.xlsx, args.updated)
    print(f"已生成：{r['xlsx']}\n        {r['meta']}\n"
          f"共 {r['rows']} 行 × {r['cols']} 列（含课程类别/课程归属/余量），更新于 {args.updated}")
