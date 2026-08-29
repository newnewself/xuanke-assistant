"""确定性引擎：上课时间解析、时段冲突、课程查询。纯逻辑，不依赖 FastAPI。"""
import json
import re
from functools import lru_cache

# ---------- 上课时间解析 ----------

WEEKDAY_MAP = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}
WEEKDAY_NAMES = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}

# 每个时段段：星期X第N-M节{周次}
_SEGMENT_RE = re.compile(
    r"星期\s*([一二三四五六日天])\s*第?\s*([0-9，,\-－]+)\s*节(?:\s*\{([^}]*)\})?"
)
_PARITY_RE = re.compile(r"[(（]\s*(单|双)\s*[)）]")
_RANGE_RE = re.compile(r"(\d+)\s*[-－]\s*(\d+)")
_NUM_RE = re.compile(r"\d+")


def _normalize(text: str) -> str:
    return text.replace("，", ",").replace("－", "-").replace("–", "-").strip()


def parse_periods(text: str) -> list[int]:
    """"1-2节" → [1,2]；"1-4节,6-9节" → [1,2,3,4,6,7,8,9]；"10节" → [10]"""
    text = _normalize(text)
    periods: set[int] = set()
    for a, b in _RANGE_RE.findall(text):
        periods.update(range(int(a), int(b) + 1))
    if not periods:
        periods.update(int(n) for n in _NUM_RE.findall(text))
    return sorted(p for p in periods if 0 < p <= 15)


def parse_weeks(text: str | None) -> tuple[list[list[int]], str | None]:
    """"1-9周,11-15周(单)" → ([[1,9],[11,15]], "单")；空 → ([[1,25]], None)"""
    if not text or not _normalize(text):
        return [[1, 25]], None
    text = _normalize(text)
    parity_m = _PARITY_RE.search(text)
    parity = parity_m.group(1) if parity_m else None
    weeks: list[list[int]] = []
    # 先按逗号拆段，每段形如 1-16周 / 5-8周 / 10周
    for part in text.split(","):
        part = part.strip()
        m = re.search(r"(\d+)\s*[-－]\s*(\d+)\s*周", part)
        if m:
            weeks.append([int(m.group(1)), int(m.group(2))])
            continue
        m = re.search(r"(\d+)\s*周", part)
        if m:
            weeks.append([int(m.group(1)), int(m.group(1))])
    if not weeks:
        return [[1, 25]], parity
    return weeks, parity


def parse_time_text(text: str | None) -> list[dict]:
    """把"星期一第1-2节{1-16周};星期二第3-4节{1-8周(双)}"解析成结构化 session 列表。

    session = {"weekday": 1-7, "periods": [..], "weeks": [[s,e],..], "parity": None|"单"|"双"}
    单双周标记可能出现在花括号内或段尾括号里，两种位置都识别。
    """
    if not text:
        return []
    sessions: list[dict] = []
    for seg in _normalize(str(text)).split(";"):
        seg = seg.strip()
        if not seg:
            continue
        m = _SEGMENT_RE.search(seg)
        if not m:
            continue
        weekday = WEEKDAY_MAP.get(m.group(1))
        if weekday is None:
            continue
        periods = parse_periods(m.group(2))
        if not periods:
            continue
        parity = None
        parity_m = _PARITY_RE.search(seg)  # 括号可能在花括号内外
        if parity_m:
            parity = parity_m.group(1)
        weeks, p2 = parse_weeks(m.group(3))
        parity = parity or p2
        sessions.append(
            {"weekday": weekday, "periods": periods, "weeks": weeks, "parity": parity}
        )
    return _dedupe_sessions(sessions)


def parse_fallback(weekday, period_text, week_text) -> list[dict]:
    """上课时间为空时，用行级 星期几/上课节次/起始周 三列兜底。"""
    try:
        weekday = int(float(weekday))
    except (TypeError, ValueError):
        return []
    if not 1 <= weekday <= 7:
        return []
    periods = parse_periods(str(period_text or ""))
    if not periods:
        return []
    weeks, parity = parse_weeks(str(week_text or ""))
    return [{"weekday": weekday, "periods": periods, "weeks": weeks, "parity": parity}]


def _dedupe_sessions(sessions: list[dict]) -> list[dict]:
    seen, out = set(), []
    for s in sessions:
        key = json.dumps(s, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def sessions_brief(sessions: list[dict]) -> str:
    """给 LLM / 前端看的人话时段描述：周一1-2节{1-16周(单)}"""
    parts = []
    for s in sessions:
        p = s["periods"]
        ptxt = f"{p[0]}-{p[-1]}节" if len(p) > 1 else f"{p[0]}节"
        wtxt = "+".join(
            f"{a}-{b}周" if a != b else f"{a}周" for a, b in s["weeks"]
        )
        if s.get("parity"):
            wtxt += f"({s['parity']})"
        parts.append(f"{WEEKDAY_NAMES[s['weekday']]}{ptxt}{{{wtxt}}}")
    return ";".join(parts)


# ---------- 冲突 / 过滤 ----------


def _weeks_overlap(a: list[list[int]], b: list[list[int]]) -> bool:
    for s1, e1 in a:
        for s2, e2 in b:
            if s1 <= e2 and s2 <= e1:
                return True
    return False


def session_conflict(sa: dict, sb: dict) -> bool:
    """两个 session 是否冲突：同星期 ∧ 节次相交 ∧ 周次相交 ∧ 单双周相容。"""
    if sa["weekday"] != sb["weekday"]:
        return False
    if not set(sa["periods"]) & set(sb["periods"]):
        return False
    pa, pb = sa.get("parity"), sb.get("parity")
    if pa and pb and pa != pb:
        return False
    if pa and not pb and pb is not None:
        return False
    return _weeks_overlap(sa["weeks"], sb["weeks"])


SEMESTER_WEEKS = 16
FULL_BUSY_WEEKS = frozenset(range(1, SEMESTER_WEEKS + 1))


def parse_weeks_spec(text: str | None) -> frozenset[int]:
    """\"1-16\" / \"2,6,8,10\" / \"1-8,10\" / None → 周次集合（钳制 1-16）。"""
    if text is None or not str(text).strip():
        return frozenset(FULL_BUSY_WEEKS)
    weeks: set[int] = set()
    for part in _normalize(str(text)).split(","):
        part = part.strip().replace("周", "")
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*[-－~]\s*(\d+)", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                a, b = b, a
            weeks.update(range(a, b + 1))
            continue
        if re.fullmatch(r"\d+", part):
            weeks.add(int(part))
            continue
        raise ValueError(f"bad week spec: {part}")
    return frozenset(w for w in weeks if 1 <= w <= SEMESTER_WEEKS)


def compact_weeks(weeks) -> str:
    """周次集合 → 紧凑文本：{2,6,8,10} → "2,6,8,10"；{1,2,3} → "1-3"。"""
    out, start, prev = [], None, None
    for w in sorted(weeks):
        if start is None:
            start = prev = w
        elif w == prev + 1:
            prev = w
        else:
            out.append(f"{start}-{prev}" if start != prev else str(start))
            start = prev = w
    if start is not None:
        out.append(f"{start}-{prev}" if start != prev else str(start))
    return ",".join(out)


def parse_busy_slots(text: str) -> set[tuple]:
    """解析 busy slot 串："1:1;3:6;4:7:2,6,8,10"（w:p[:周次spec]，缺省=全学期）。

    顶层分隔符为 ";"（周次段内含逗号）；兼容旧格式纯逗号分隔（无周次段）。
    返回 {(weekday, period, frozenset 周次)}。
    """
    text = (text or "").strip()
    if not text:
        return set()
    busy: set[tuple] = set()
    for part in (text.split(";") if ";" in text else text.split(",")):
        try:
            pieces = part.strip().split(":")
            w, p = int(pieces[0]), int(pieces[1])
            busy.add((w, p, parse_weeks_spec(pieces[2] if len(pieces) >= 3 else None)))
        except (ValueError, IndexError):
            continue
    return busy


def _session_meeting_weeks(s: dict) -> set[int]:
    """课程 session 的实际上课周集合：周次区间展开 + 单双周过滤。"""
    weeks: set[int] = set()
    for a, b in s["weeks"]:
        weeks.update(range(max(1, a), min(25, b) + 1))
    parity = s.get("parity")
    if parity == "单":
        return {w for w in weeks if w % 2 == 1}
    if parity == "双":
        return {w for w in weeks if w % 2 == 0}
    return weeks


def busy_conflict(sessions: list[dict], busy_slots: set[tuple]) -> bool:
    """课程时段是否命中用户标记的已占时段。

    busy slot = (weekday, period)（全学期占用，兼容旧格式，宁严勿漏）
    或 (weekday, period, frozenset 周次)：标记周次与该节次实际上课周
    （周次区间展开 + 单双周过滤）有交集才算冲突。
    """
    for s in sessions:
        meet = None
        for slot in busy_slots:
            if slot[0] != s["weekday"] or slot[1] not in s["periods"]:
                continue
            weeks = slot[2] if len(slot) >= 3 else None
            if not weeks or weeks == FULL_BUSY_WEEKS:
                return True
            if meet is None:
                meet = _session_meeting_weeks(s)
            if weeks & meet:
                return True
    return False


def busy_slot_label(slot: tuple) -> str:
    """(3,4,{2,6,8,10}) → "周三第4节{2,6,8,10周}"；全学期占用 → "周三第4节"。"""
    label = f"{WEEKDAY_NAMES.get(slot[0], slot[0])}第{slot[1]}节"
    if len(slot) >= 3 and slot[2] and slot[2] != FULL_BUSY_WEEKS:
        label += "{" + compact_weeks(slot[2]) + "周}"
    return label


def hits_window(sessions: list[dict], weekday: int, pmin: int, pmax: int) -> bool:
    """课程是否落在 星期几 + 节次区间 内。"""
    for s in sessions:
        if s["weekday"] != weekday:
            continue
        if any(pmin <= p <= pmax for p in s["periods"]):
            return True
    return False


# ---------- 查询 ----------

MAIN_FIELDS = [
    "xk_id", "course_no", "course_name", "teachers", "credit", "nature",
    "time_text", "sessions_brief", "college", "campus", "rooms",
    "remaining", "plan_size", "enrolled", "seats", "teacher_segments",
    "course_category", "course_attribution",
]
ALL_FIELDS = MAIN_FIELDS + [
    "week_hours", "total_hours", "teacher_titles", "teacher_edu",
    "teacher_college", "staff_no", "gender",
    "room_no", "room_type", "room_weeks", "room_periods", "building", "floor",
    "major_group", "class_group", "year", "term", "sessions_json",
]
# 表格/查询接口返回的字段：除 sessions_json（重且仅详情需要）外的全部字段，
# 保证列设置"全选"后每一列都有数据
TABLE_FIELDS = [f for f in ALL_FIELDS if f != "sessions_json"]

SORT_KEYS = {
    "course_name": lambda r: getattr(r, "course_name", "") or "",
    "credit": lambda r: getattr(r, "credit", 0) or 0,
    "remaining": lambda r: getattr(r, "remaining", 0)
        if getattr(r, "remaining", None) is not None else -1e9,
}


def row_to_dict(row, fields=None) -> dict:
    fields = fields or ALL_FIELDS
    d = {}
    for f in fields:
        if f == "sessions_brief":
            d[f] = sessions_brief(json.loads(row.sessions_json or "[]"))
        elif f == "sessions_json":
            d[f] = json.loads(row.sessions_json or "[]")
        else:
            v = getattr(row, f, None)
            d[f] = round(v, 2) if isinstance(v, float) else v
    return d
