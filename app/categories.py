"""用户自定义课程类别：教务「课程类别」之外的常用补充标签。

名单存于 data/custom_categories.json，格式 {类别名: [课程号或课程名称关键词…]}。
名单为空 = 只注册类别、暂不关联任何课程。导入(ETL)与资料来源生成时，
名单内课程的 course_category 会被覆盖为对应类别名（自定义类别优先于教务原始类别）。
"""
import json

from .config import DATA_DIR

# 内置自定义类别（名字即用户口径）；文件缺失/损坏时以此兜底
DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "体育课": [],
}

PATH = DATA_DIR / "custom_categories.json"


def load_custom_categories() -> dict[str, list[str]]:
    """读 data/custom_categories.json；缺失或格式不对时回落到内置空名单。"""
    cats = {k: list(v) for k, v in DEFAULT_CATEGORIES.items()}
    try:
        raw = json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cats
    if not isinstance(raw, dict):
        return cats
    for name, entries in raw.items():
        name = str(name).strip()
        if not name or not isinstance(entries, list):
            continue
        cats[name] = [str(e).strip() for e in entries if str(e).strip()]
    return cats


def match_custom_category(course_no: str, course_name: str,
                          categories: dict[str, list[str]]) -> str:
    """名单条目与课程号相等、或为课程名称子串即命中；先定义的类别优先。"""
    for name, entries in categories.items():
        for e in entries:
            if e and (e == course_no or e in course_name):
                return name
    return ""
