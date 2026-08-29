"""ETL 聚合 + 搜索过滤（含忙碌时段剔除）的集成测试，跑在临时 SQLite 上。"""
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import etl
from app.db import Base
from app.models import CourseClass
from app.routers import courses


def make_raw() -> pd.DataFrame:
    """模拟教务导出：一门课两个时段两行；一门公选课含单双周；一门超选课。"""
    return pd.DataFrame([
        # 环境工程原理：两行（周一、周二），选课人数 48/77 余量正
        {"xk_id": "X-1", "course_no": "HJC001", "course_name": "环境工程原理", "credit": 4.0,
         "nature": "必修", "college": "环境学院", "campus": "下沙", "teacher": "江博琼",
         "title": "教授", "edu": "博士", "teacher_college": "环境学院",
         "time_text": "星期一第1-2节{1-16周};星期二第1-2节{1-16周}",
         "weekday": 1, "period_text": "1-2节", "week_text": "1-16周",
         "room2": "B104", "plan_size": 77.0, "enrolled": 48.0, "seats": 93.0,
         "week_hours": 4.0, "total_hours": 64.0, "major_group": "环境工程", "term": 1.0},
        {"xk_id": "X-1", "course_no": "HJC001", "course_name": "环境工程原理", "credit": 4.0,
         "nature": "必修", "college": "环境学院", "campus": "下沙", "teacher": "江博琼",
         "title": "教授", "edu": "博士", "teacher_college": "环境学院",
         "time_text": "星期一第1-2节{1-16周};星期二第1-2节{1-16周}",
         "weekday": 2, "period_text": "1-2节", "week_text": "1-16周",
         "room2": "B104", "plan_size": 77.0, "enrolled": 48.0, "seats": 93.0,
         "week_hours": 4.0, "total_hours": 64.0, "major_group": "环境工程", "term": 1.0},
        # 公选课：单双周
        {"xk_id": "X-2", "course_no": "MSC001", "course_name": "烘焙与美食", "credit": 2.0,
         "nature": "公选", "college": "旅游学院", "campus": "教工路", "teacher": "张三",
         "title": "副教授", "edu": "硕士", "teacher_college": "旅游学院",
         "time_text": "星期三第3-4节{1-9周,11-15周(单)}",
         "weekday": 3, "period_text": "3-4节", "week_text": "1-16周",
         "room2": "F101", "plan_size": 60.0, "enrolled": 59.0, "seats": 80.0,
         "week_hours": 2.0, "total_hours": 32.0, "major_group": "全校", "term": 1.0},
        # 超选课：remaining 为负
        {"xk_id": "X-3", "course_no": "ART002", "course_name": "摄影基础", "credit": 1.5,
         "nature": "公选", "college": "人文学院", "campus": "下沙", "teacher": "李四",
         "title": "讲师", "edu": "硕士", "teacher_college": "人文学院",
         "time_text": "星期四第6-7节{1-16周}",
         "weekday": 4, "period_text": "6-7节", "week_text": "1-16周",
         "room2": "A203", "plan_size": 40.0, "enrolled": 55.0, "seats": 40.0,
         "week_hours": 2.0, "total_hours": 24.0, "major_group": "全校", "term": 1.0},
    ])


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    clean = etl.transform(make_raw())
    db_path = tmp_path / "t.db"
    etl.write_db(clean, str(db_path))
    e = create_engine(f"sqlite:///{db_path}")
    SessionT = sessionmaker(bind=e, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(courses, "SessionLocal", SessionT)
    yield SessionT


def test_transform_aggregates_rows(tmp_db):
    with tmp_db() as s:
        rows = s.query(CourseClass).all()
    assert len(rows) == 3  # 两行 X-1 聚合为一个班
    x1 = next(r for r in rows if r.xk_id == "X-1")
    assert x1.credit == 4.0
    assert x1.remaining == 77.0 - 48.0
    import json
    sessions = json.loads(x1.sessions_json)
    assert {s["weekday"] for s in sessions} == {1, 2}


def test_transform_dedupes_rooms_within_cell():
    # 教务源数据单元格内用 ; 拼了重复地点：拆开去重，不同地点保留
    raw = make_raw().iloc[[0, 1]].copy()   # 只取 X-1 的两行
    raw["room2"] = ["A101;A101;B202", "A101"]
    clean = etl.transform(raw)
    assert clean.loc[0, "rooms"] == "A101、B202"


def test_search_keyword_and_nature(tmp_db):
    res = courses.search_courses_impl({"keyword": "烘焙"})
    assert res["total"] == 1 and res["rows"][0]["course_name"] == "烘焙与美食"
    res = courses.search_courses_impl({"nature": "公选"})
    assert res["total"] == 2


def test_search_credit_range(tmp_db):
    res = courses.search_courses_impl({"credit_min": 2, "credit_max": 4})
    assert res["total"] == 2


def test_search_only_available_keeps_negative_shown_elsewhere(tmp_db):
    res = courses.search_courses_impl({"only_available": True})
    assert res["total"] == 2  # 摄影基础 remaining=-15 被过滤
    res = courses.search_courses_impl({"keyword": "摄影"})
    assert res["rows"][0]["remaining"] == -15  # 不隐藏负数


def test_busy_slot_removal(tmp_db):
    # 周二第1节被占用 → 环境工程原理被剔除
    res = courses.search_courses_impl({}, busy_slots={(2, 1)})
    assert res["busy_removed"] == 1
    assert all(r["xk_id"] != "X-1" for r in res["rows"])
    # 不相关时段不剔除
    res = courses.search_courses_impl({}, busy_slots={(5, 8)})
    assert res["busy_removed"] == 0


def test_weekday_window(tmp_db):
    res = courses.search_courses_impl({"weekday": 3, "period_min": 3, "period_max": 4})
    assert res["total"] == 1 and res["rows"][0]["xk_id"] == "X-2"


def test_filter_ids_only_available_and_order(tmp_db):
    # 精选表过滤：余量 <=0 剔除，且保持传入课号顺序
    res = courses.filter_ids_impl(["X-3", "X-1", "X-2"], only_available=True)
    assert [r["xk_id"] for r in res["rows"]] == ["X-1", "X-2"]
    assert res["total"] == 2


def test_filter_ids_busy_and_no_filters(tmp_db):
    # 周一第1节被占用 → 环境工程原理(X-1)被剔除
    res = courses.filter_ids_impl(["X-1", "X-2"], busy_slots={(1, 1)})
    assert [r["xk_id"] for r in res["rows"]] == ["X-2"]
    # 无过滤条件 → 全部返回；不存在的课号被忽略
    res = courses.filter_ids_impl(["X-2", "NOPE", "X-3"])
    assert [r["xk_id"] for r in res["rows"]] == ["X-2", "X-3"]


def test_write_db_preserves_history(tmp_db, tmp_path):
    # 再次导入时旧库的 panels/chat_messages 应被迁移
    from sqlalchemy import text
    from datetime import datetime
    e = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    now = datetime.now().isoformat(sep=" ")
    with e.begin() as conn:
        conn.execute(text("INSERT INTO panels(title, payload_json, created_at) VALUES('t','{}',:c)"),
                     {"c": now})
        conn.execute(text("INSERT INTO chat_messages(role, content, meta_json, created_at, session_id) VALUES('user','hi','{}',:c,'oldsess')"),
                     {"c": now})
    e.dispose()  # Windows 下替换文件前必须释放句柄
    etl.write_db(etl.transform(make_raw()), str(tmp_path / "t.db"))
    with e.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM panels")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM chat_messages")).scalar() == 1


def test_search_weekdays_and_periods_multiselect(tmp_db):
    """查询卡新增的周几/节次多选：任选集合内任一命中；组合时段须同时满足两维。"""
    # 多选周几：周一或周四 → X-1（周一1-2）与 X-3（周四6-7）
    res = courses.search_courses_impl({"weekdays": "1,4"})
    assert {r["xk_id"] for r in res["rows"]} == {"X-1", "X-3"}
    # 多选节次：第3、6节 → X-2（周三3-4）与 X-3（周四6-7），星期不限
    res = courses.search_courses_impl({"periods": "3,6"})
    assert {r["xk_id"] for r in res["rows"]} == {"X-2", "X-3"}
    # 组合：周二 × 第1或6节 → 只有 X-1（周二1-2）
    res = courses.search_courses_impl({"weekdays": "2", "periods": "1,6"})
    assert {r["xk_id"] for r in res["rows"]} == {"X-1"}
    # 组合无交集：周一第6节没有任何课
    res = courses.search_courses_impl({"weekdays": "1", "periods": "6"})
    assert res["total"] == 0
    # 中文逗号容错、非法项忽略
    res = courses.search_courses_impl({"weekdays": "1，4,x"})
    assert {r["xk_id"] for r in res["rows"]} == {"X-1", "X-3"}
    # 两维都不传 = 不限
    assert courses.search_courses_impl({})["total"] == 3
