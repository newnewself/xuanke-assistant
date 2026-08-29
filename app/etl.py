"""ETL：教务系统导出的《按条件查询课程.xlsx》 → SQLite 课程库（原子替换）。

隐私红线：教师联系电话列在转换过程中被显式丢弃，任何落库表都不含该字段。
"""
import json
import os
import re
from datetime import datetime

import pandas as pd
from sqlalchemy import text

from .config import DATA_DIR, DB_PATH
from .db import Base, engine
from .categories import load_custom_categories, match_custom_category
from . import engine as eng
from . import models  # noqa: F401  # 必须 import 以注册 ORM 表结构，create_all 才会建全表

# 原始表的列 → 标准字段名（原始列名即中文名）
RAW_COLS = {
    "学年": "year", "学期": "term", "星期几": "weekday", "上课节次": "period_text",
    "起始周": "week_text", "课程号": "course_no", "课程名称": "course_name",
    "教工号": "staff_no", "姓名": "teacher", "性别": "gender", "职称名称": "title",
    "最高学历": "edu", "教师所属学院": "teacher_college", "场地编号": "room_no",
    "场地名称": "room", "场地类别名称": "room_type", "场地上课起始周": "room_weeks",
    "场地上课节次": "room_periods", "上课地点": "room2", "校区": "campus",
    "教学班人数": "plan_size", "教学班组成": "class_group", "选课课号": "xk_id",
    "学分": "credit", "总学时": "total_hours", "开课学院": "college",
    "选课人数": "enrolled", "周学时": "week_hours", "上课时间": "time_text",
    "课程性质": "nature", "座位数": "seats", "教学楼": "building", "楼层号": "floor",
    "专业组成": "major_group",
}
# 教师联系电话 → 有意不入库（隐私）


def load_raw(path) -> pd.DataFrame:
    df = pd.read_excel(path, header=3)
    df = df.dropna(how="all").rename(columns={c: RAW_COLS[c] for c in df.columns if c in RAW_COLS})
    if "xk_id" not in df.columns:
        raise ValueError("不是《按条件查询课程》格式的文件：缺少“选课课号”列")
    return df


def _clean_campus(v) -> str:
    s = str(v or "").strip().replace("\ufffd", "")
    if s in ("沙", "下沙"):
        return "下沙"
    return s


def _join_distinct(values, sep="、") -> str:
    out = list(dict.fromkeys(str(v).strip() for v in values if pd.notna(v) and str(v).strip()))
    return sep.join(out)


def _num(v, default=0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return default if f != f else f  # f != f 即 NaN，落库会变成 NOT NULL 违规


def _str(v) -> str:
    if v is None or (isinstance(v, float) and v != v) or (v is pd.NaT):
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return str(v).strip()


def _term_str(v) -> str:
    s = _str(v)
    try:
        return str(int(float(s)))
    except (TypeError, ValueError):
        return s


def load_course_info(path) -> dict:
    """《课程基本信息》→ {课程代码: (课程类别, 课程归属)}。缺文件返回空表，字段留空。"""
    from pathlib import Path
    if not Path(path).exists():
        return {}
    info = pd.read_excel(path, header=3)
    info.columns = [str(c).strip() for c in info.columns]
    if "课程代码" not in info.columns:
        return {}
    info = info.dropna(subset=["课程代码"])
    out: dict[str, tuple[str, str]] = {}
    for _, r in info.iterrows():
        code = _str(r.get("课程代码"))
        if code.endswith(".0"):
            code = code[:-2]
        if not code or code in out:
            continue
        out[code] = (_str(r.get("课程类别")), _str(r.get("课程归属")))
    return out


def transform(raw: pd.DataFrame, course_info: dict | None = None,
              custom_categories: dict[str, list[str]] | None = None) -> pd.DataFrame:
    """5595 行（每时段一行）→ 一行一个教学班，sessions 解析为结构化 JSON。

    custom_categories：自定义类别名单（None = 从 data/custom_categories.json 读）；
    命中名单的课程 course_category 覆盖为自定义类别名，未命中保持教务原值。
    """
    records = []
    info = course_info or {}
    custom = load_custom_categories() if custom_categories is None else custom_categories
    for xk_id, g in raw.groupby("xk_id", sort=False):
        first = g.iloc[0]
        course_no = _str(first.get("course_no"))
        cat, attr = info.get(course_no, ("", ""))
        custom_cat = match_custom_category(course_no, _str(first.get("course_name")), custom)
        if custom_cat:
            cat = custom_cat
        sessions = []
        for t in g["time_text"].dropna():
            sessions.extend(eng.parse_time_text(str(t)))
        if not sessions:
            for _, r in g.iterrows():
                sessions.extend(eng.parse_fallback(r.get("weekday"), r.get("period_text"), r.get("week_text")))
        plan = _num(first.get("plan_size"))
        enrolled = _num(first.get("enrolled"))
        room_col = "room2" if "room2" in g.columns else "room"
        rooms = ""
        if room_col in g.columns:
            parts: list[str] = []
            for v in g[room_col]:
                if pd.isna(v) or not str(v).strip():
                    continue
                # 教务导出的单元格常已把各时段地点用 ;/, 拼好且重复出现，拆开再去重
                parts.extend(p.strip() for p in re.split(r"[;；,，、]", str(v)) if p.strip())
            rooms = "、".join(dict.fromkeys(parts))

        def merge(col: str, sep="、") -> str:
            return _join_distinct(g[col], sep=sep) if col in g.columns else ""

        def merge_code(col: str, sep="、") -> str:
            """编号类字段（场地编号/楼层号）：Excel 读成 2074.0 时还原为 2074，保住前导零语义。"""
            if col not in g.columns:
                return ""
            vals = [(_str(v)[:-2] if _str(v).endswith(".0") else _str(v)) for v in g[col]]
            return _join_distinct([v for v in vals if v], sep=sep)
        # 教师分段：同一班内不同行起始周不同（分段授课）时，保留“教师(周次)”对应关系
        week_vals = {_str(v) for v in g["week_text"]} if "week_text" in g.columns else set()
        week_vals.discard("")
        teacher_segments = ""
        if len(week_vals) > 1:
            segs: dict[str, list[str]] = {}
            order: list[str] = []
            for _, r in g.iterrows():
                t, w = _str(r.get("teacher")), _str(r.get("week_text"))
                if not w:
                    continue
                if not t:
                    t = "（未标注教师）"
                if t not in segs:
                    segs[t] = []
                    order.append(t)
                if w not in segs[t]:
                    segs[t].append(w)
            teacher_segments = "、".join(
                f"{t}({'+'.join(ws)})" for t, ws in ((t, segs[t]) for t in order))
        records.append({
            "xk_id": _str(xk_id) or str(xk_id),
            "course_no": _str(first.get("course_no")),
            "course_name": _str(first.get("course_name")),
            "credit": _num(first.get("credit")),
            "nature": _str(first.get("nature")),
            "course_category": cat,
            "course_attribution": attr,
            "college": _str(first.get("college")),
            "campus": _clean_campus(first.get("campus")),
            "teachers": _join_distinct(g["teacher"]),
            "staff_no": merge("staff_no"),
            "gender": merge("gender"),
            "teacher_titles": _join_distinct(g["title"]),
            "teacher_edu": _join_distinct(g["edu"]),
            "teacher_college": _join_distinct(g["teacher_college"]),
            "teacher_segments": teacher_segments,
            "rooms": rooms,
            "room_no": merge_code("room_no"),
            "room_type": merge("room_type"),
            "room_weeks": merge("room_weeks", sep="；"),
            "room_periods": merge("room_periods", sep="；"),
            "building": merge("building"),
            "floor": merge_code("floor"),
            "time_text": _join_distinct(g["time_text"], sep=";"),
            "sessions_json": json.dumps(eng._dedupe_sessions(sessions), ensure_ascii=False),
            "week_hours": _str(first.get("week_hours")),   # 源为"理论(2.0)-实习(8.0)"等文本，存原文
            "total_hours": _num(first.get("total_hours")),
            "plan_size": plan,
            "enrolled": enrolled,
            "seats": _num(first.get("seats")),
            "remaining": round(plan - enrolled, 2),   # 负数保留（超选）
            "major_group": _str(first.get("major_group")),
            "class_group": _str(first.get("class_group")),
            "year": _str(first.get("year")),
            "term": _term_str(first.get("term")),
        })
    return pd.DataFrame(records)


def write_db(clean: pd.DataFrame, db_path=os.fspath(DB_PATH)) -> dict:
    """写入临时库并原子替换，正在使用的旧库不受影响。"""
    tmp = str(db_path) + ".new"
    if os.path.exists(tmp):
        os.remove(tmp)
    from sqlalchemy import create_engine
    tmp_engine = create_engine(f"sqlite:///{tmp}")
    Base.metadata.create_all(tmp_engine)
    # 先由 create_all 建好含自增主键的表，再 append，保证 ORM 可查询
    clean.to_sql("classes", tmp_engine, if_exists="append", index=False)
    with tmp_engine.begin() as conn:
        for k, v in {
            "year": _str(clean["year"].iloc[0]) if len(clean) else "",
            "term": _term_str(clean["term"].iloc[0]) if len(clean) else "",
            "imported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "class_count": str(len(clean)),
        }.items():
            conn.execute(text(
                "INSERT OR REPLACE INTO meta_kv(key, value) VALUES (:k, :v)"), {"k": k, "v": v})
    tmp_engine.dispose()
    # panels / chat_messages 保留在旧库中，一并搬到新库
    if os.path.exists(db_path):
        from sqlalchemy import create_engine
        old_engine = create_engine(f"sqlite:///{db_path}")
        try:
            with old_engine.begin() as conn:
                panels = conn.execute(text(
                    "SELECT title, payload_json, created_at FROM panels")).fetchall()
                chats = conn.execute(text(
                    "SELECT role, content, meta_json, created_at, session_id FROM chat_messages")).fetchall()
        except Exception:
            panels, chats = [], []
        finally:
            old_engine.dispose()
        e2 = create_engine(f"sqlite:///{tmp}")
        with e2.begin() as conn:
            for p in panels:
                conn.execute(text("INSERT INTO panels(title, payload_json, created_at) VALUES(:t,:p,:c)"),
                             {"t": p[0], "p": p[1], "c": p[2]})
            for c in chats:
                conn.execute(text("INSERT INTO chat_messages(role, content, meta_json, created_at, session_id) VALUES(:r,:c,:m,:t,:s)"),
                             {"r": c[0], "c": c[1], "m": c[2], "t": c[3], "s": c[4] or ""})
        e2.dispose()
    if os.path.exists(db_path):
        # 目标库存在（服务可能正开着连接）：用 SQLite backup 原地覆盖，
        # 不做文件替换，避免 Windows 下句柄占用导致 PermissionError
        import sqlite3 as _sq3
        src = _sq3.connect(tmp)
        dst = _sq3.connect(db_path, timeout=20)
        src.backup(dst)
        dst.close()
        src.close()
        os.remove(tmp)
    else:
        os.replace(tmp, db_path)
    engine.dispose()
    return {"class_count": len(clean), "year": _str(clean["year"].iloc[0]) if len(clean) else "",
            "term": _term_str(clean["term"].iloc[0]) if len(clean) else ""}


def import_file(path) -> dict:
    raw = load_raw(path)
    clean = transform(raw, load_course_info(DATA_DIR / "课程基本信息.xlsx"))
    if clean.empty:
        raise ValueError("没有解析到任何课程数据")
    return write_db(clean)


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "../按条件查询课程.xlsx"
    stats = import_file(src)
    print("导入完成:", stats)
