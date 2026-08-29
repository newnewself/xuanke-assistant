"""时间解析与冲突判定的边界用例——这些函数的正确性决定系统可信度。"""
import pytest

from app import engine as eng


def test_parse_periods_ranges():
    assert eng.parse_periods("1-2节") == [1, 2]
    assert eng.parse_periods("1-4节,6-9节") == [1, 2, 3, 4, 6, 7, 8, 9]
    assert eng.parse_periods("10节") == [10]
    assert eng.parse_periods("１-２节") == [1, 2]  # 全角数字也能处理


def test_parse_weeks_variants():
    assert eng.parse_weeks("1-16周") == ([[1, 16]], None)
    assert eng.parse_weeks("1-9周,11-15周(单)") == ([[1, 9], [11, 15]], "单")
    assert eng.parse_weeks("10-16周(双)") == ([[10, 16]], "双")
    assert eng.parse_weeks("5周") == ([[5, 5]], None)
    assert eng.parse_weeks("") == ([[1, 25]], None)


def test_parse_time_text_multi_segment():
    text = "星期一第1-2节{1-16周};星期二第1-2节{1-16周}"
    s = eng.parse_time_text(text)
    assert [x["weekday"] for x in s] == [1, 2]
    assert s[0]["periods"] == [1, 2]
    assert s[0]["weeks"] == [[1, 16]]


def test_parse_time_text_parity_inside_braces():
    s = eng.parse_time_text("星期三第3-4节{1-9周,11-15周(单)}")
    assert s[0]["parity"] == "单"
    assert s[0]["weeks"] == [[1, 9], [11, 15]]


def test_parse_time_text_garbage_is_empty():
    assert eng.parse_time_text("") == []
    assert eng.parse_time_text("待定") == []
    assert eng.parse_time_text(None) == []


def test_parse_fallback():
    s = eng.parse_fallback(1, "1-2节", "1-6周")
    assert s == [{"weekday": 1, "periods": [1, 2], "weeks": [[1, 6]], "parity": None}]
    assert eng.parse_fallback(None, "1-2节", "1周") == []
    assert eng.parse_fallback(9, "1节", "1周") == []


def test_session_conflict_three_dimensions():
    a = {"weekday": 1, "periods": [1, 2], "weeks": [[1, 16]], "parity": None}
    # 同星期同节次同周次 → 冲突
    assert eng.session_conflict(a, {**a})
    # 不同星期 → 不冲突
    assert not eng.session_conflict(a, {**a, "weekday": 2})
    # 节次错开 → 不冲突
    assert not eng.session_conflict(a, {**a, "periods": [3, 4]})
    # 周次错开 → 不冲突
    assert not eng.session_conflict(a, {**a, "weeks": [[17, 20]]})
    # 一个单周一个双周 → 不冲突
    assert not eng.session_conflict({**a, "parity": "单"}, {**a, "parity": "双"})
    # 单周 vs 未标记 → 冲突（未标记视为全周次）
    assert eng.session_conflict({**a, "parity": "单"}, {**a})


def test_busy_conflict_weeks():
    FULL = frozenset(range(1, 17))
    s = [{"weekday": 4, "periods": [7, 8], "weeks": [[2, 3], [6, 8], [10, 10]], "parity": None}]
    # 全学期标记（旧格式二元组）→ 冲突
    assert eng.busy_conflict(s, {(4, 7)})
    assert not eng.busy_conflict(s, {(4, 9)})
    assert not eng.busy_conflict(s, {(2, 7)})
    # 散周标记：与实际上课周有交集 → 冲突
    assert eng.busy_conflict(s, {(4, 7, frozenset({2, 6, 8, 10}))})
    assert eng.busy_conflict(s, {(4, 7, frozenset({10}))})
    assert not eng.busy_conflict(s, {(4, 7, frozenset({4, 5}))})
    assert not eng.busy_conflict(s, {(4, 7, frozenset({11, 12, 16}))})
    # 单双周展开：单周课的 meeting weeks 为奇数周
    s2 = [{"weekday": 3, "periods": [3], "weeks": [[1, 16]], "parity": "单"}]
    assert eng.busy_conflict(s2, {(3, 3, frozenset({3}))})
    assert not eng.busy_conflict(s2, {(3, 3, frozenset({2}))})


def test_parse_busy_slots():
    FULL = frozenset(range(1, 17))
    bs = eng.parse_busy_slots("1:1;4:7:2,6,8,10")
    assert (1, 1, FULL) in bs
    assert (4, 7, frozenset({2, 6, 8, 10})) in bs
    # 旧逗号格式（无周次段）兼容
    assert eng.parse_busy_slots("1:1,1:2") == {(1, 1, FULL), (1, 2, FULL)}
    assert eng.parse_busy_slots("") == set()
    assert eng.parse_busy_slots("x:y;3") == set()
    # 区间与散周混写、非法段跳过
    bs2 = eng.parse_busy_slots("2:1:1-8,10;9:9:abc")
    assert (2, 1, frozenset({1, 2, 3, 4, 5, 6, 7, 8, 10})) in bs2


def test_busy_slot_label():
    FULL = frozenset(range(1, 17))
    assert eng.busy_slot_label((3, 4)) == "周三第4节"
    assert eng.busy_slot_label((3, 4, frozenset({2, 6, 8, 10}))) == "周三第4节{2,6,8,10周}"
    assert eng.busy_slot_label((3, 4, frozenset({1, 2, 3}))) == "周三第4节{1-3周}"
    assert eng.busy_slot_label((3, 4, FULL)) == "周三第4节"


def test_sessions_brief():
    s = [{"weekday": 1, "periods": [1, 2], "weeks": [[1, 16]], "parity": None},
         {"weekday": 6, "periods": [10], "weeks": [[5, 5]], "parity": "双"}]
    assert eng.sessions_brief(s) == "周一1-2节{1-16周};周六10节{5周(双)}"
