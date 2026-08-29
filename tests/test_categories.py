"""自定义课程类别：名单加载 + ETL/匹配的类别覆盖（名单为空 = 只注册不关联）。"""
import pandas as pd

from app import categories, etl


def test_load_defaults_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(categories, "PATH", tmp_path / "不存在.json")
    cats = categories.load_custom_categories()
    assert list(cats) == ["体育课"]
    assert all(v == [] for v in cats.values())


def test_load_reads_file_and_keeps_defaults(tmp_path, monkeypatch):
    f = tmp_path / "custom_categories.json"
    f.write_text('{"体育课": ["MPE052", "游泳"], "坏条目": "不是列表"}', encoding="utf-8")
    monkeypatch.setattr(categories, "PATH", f)
    cats = categories.load_custom_categories()
    assert cats["体育课"] == ["MPE052", "游泳"]
    assert "坏条目" not in cats                # 非法条目（非列表）忽略


def test_match_by_course_no_and_name_keyword():
    cats = {"体育课": ["MPE052", "游泳"], "形策": []}
    assert categories.match_custom_category("MPE052", "初级体育舞蹈", cats) == "体育课"
    assert categories.match_custom_category("XXX111", "游泳与救生", cats) == "体育课"
    assert categories.match_custom_category("XXX111", "形势与政策(1)", cats) == ""
    assert categories.match_custom_category("XXX111", "高等数学", cats) == ""


def make_raw(course_no: str, course_name: str) -> pd.DataFrame:
    return pd.DataFrame([{
        "xk_id": "X-1", "course_no": course_no, "course_name": course_name,
        "teacher": "张三", "title": "讲师", "edu": "硕士", "teacher_college": "体育学院",
        "time_text": "星期一第1-2节{1-16周}",
    }])


def test_transform_override_wins_over_source_info():
    raw = make_raw("MPE052", "初级体育舞蹈")
    info = {"MPE052": ("普通共同课", "")}
    clean = etl.transform(raw, info, custom_categories={"体育课": ["MPE052"]})
    assert clean.loc[0, "course_category"] == "体育课"


def test_transform_keeps_source_when_no_hit():
    raw = make_raw("HJC001", "环境工程原理")
    info = {"HJC001": ("专业核心课", "")}
    clean = etl.transform(raw, info, custom_categories={"体育课": ["MPE052"]})
    assert clean.loc[0, "course_category"] == "专业核心课"


def test_transform_name_keyword_hit():
    raw = make_raw("PRE016", "体育与健康(1)(预科)")
    clean = etl.transform(raw, {}, custom_categories={"体育课": ["体育"]})
    assert clean.loc[0, "course_category"] == "体育课"


def test_transform_empty_lists_change_nothing():
    raw = make_raw("MPE052", "初级体育舞蹈")
    clean = etl.transform(raw, {}, custom_categories={"体育课": []})
    assert clean.loc[0, "course_category"] == ""
