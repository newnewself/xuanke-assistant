"""课程查询 API。搜索核心实现放这里，agent 工具复用同一份逻辑。"""
import json

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import false, or_, select

from ..db import SessionLocal, get_db
from ..models import CourseClass, MetaKV
from ..categories import load_custom_categories
from .. import engine as eng

router = APIRouter(prefix="/api")


def search_courses_impl(args: dict, busy_slots: set | None = None,
                        sort: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    """limit=0 表示不截断，返回全部符合条件的结果。"""
    busy_slots = busy_slots or set()
    args = {k: v for k, v in (args or {}).items() if v not in (None, "")}
    with SessionLocal() as db:
        q = select(CourseClass)
        kw = args.get("keyword")
        if kw:
            like = f"%{kw}%"
            q = q.where(or_(CourseClass.course_name.like(like),
                            CourseClass.teachers.like(like),
                            CourseClass.college.like(like),
                            CourseClass.course_no.like(like)))
        if args.get("course_name"):
            q = q.where(CourseClass.course_name.like(f"%{args['course_name']}%"))
        if args.get("course_no"):
            q = q.where(CourseClass.course_no.like(f"%{args['course_no']}%"))
        # 学院/校区/归属用包含匹配：模型或用户给常见叫法（如“法学院”“下沙校区”）也能命中，
        # 下拉框选完整取值时行为与精确匹配一致（取值间互不为子串）
        if args.get("college"):
            q = q.where(CourseClass.college.like(f"%{args['college']}%"))
        if args.get("nature"):
            q = q.where(CourseClass.nature == args["nature"])
        if args.get("course_category"):
            q = q.where(CourseClass.course_category == args["course_category"])
        if args.get("course_attribution"):
            q = q.where(CourseClass.course_attribution.like(f"%{args['course_attribution']}%"))
        if args.get("campus"):
            # 双向包含：让“下沙校区”也能命中库值“下沙”（校区取值极少，先取全量再匹配）
            v = args["campus"]
            all_campus = [c for c in db.scalars(select(CourseClass.campus).distinct()) if c]
            hits = [c for c in all_campus if v in c or c in v]
            q = q.where(or_(*[CourseClass.campus == c for c in hits]) if hits else false())
        if args.get("teacher"):
            q = q.where(CourseClass.teachers.like(f"%{args['teacher']}%"))
        if args.get("credit_min") is not None:
            q = q.where(CourseClass.credit >= float(args["credit_min"]))
        if args.get("credit_max") is not None:
            q = q.where(CourseClass.credit <= float(args["credit_max"]))
        if args.get("only_available"):
            q = q.where(CourseClass.remaining > 0)

        rows = db.scalars(q).all()

    # Python 侧精筛：时段窗口 + 忙碌时段剔除（会话结构无法高效走 SQL，量级无压力）
    weekday = args.get("weekday")
    pmin = args.get("period_min") or 1
    pmax = args.get("period_max") or 15
    out, busy_removed = [], 0
    for r in rows:
        sessions = json.loads(r.sessions_json or "[]")
        if weekday and not eng.hits_window(sessions, int(weekday), int(pmin), int(pmax)):
            continue
        if busy_slots and eng.busy_conflict(sessions, busy_slots):
            busy_removed += 1
            continue
        out.append(r)

    total = len(out)
    key = eng.SORT_KEYS.get(sort or "course_name", eng.SORT_KEYS["course_name"])
    reverse = sort in ("remaining", "credit")
    out.sort(key=key, reverse=reverse)
    window = out[offset:] if limit == 0 else out[offset: offset + limit]
    return {"total": total, "busy_removed": busy_removed,
            "rows": [eng.row_to_dict(r, eng.TABLE_FIELDS) for r in window]}


def get_many_impl(xk_ids: list[str]) -> list[dict]:
    if not xk_ids:
        return []
    with SessionLocal() as db:
        rows = db.scalars(select(CourseClass).where(CourseClass.xk_id.in_(xk_ids))).all()
    return [eng.row_to_dict(r, eng.TABLE_FIELDS) for r in rows]


def filter_ids_impl(xk_ids: list[str], only_available: bool = False,
                    busy_slots: set | None = None) -> dict:
    """精选表格（无查询参数）的本地过滤：保持传入顺序，按余量/已占时段剔除。"""
    ids = [str(x) for x in (xk_ids or [])]
    busy = busy_slots or set()
    with SessionLocal() as db:
        rows = db.scalars(select(CourseClass).where(CourseClass.xk_id.in_(ids))).all() if ids else []
    by_id = {r.xk_id: r for r in rows}
    out = []
    for x in ids:
        r = by_id.get(x)
        if r is None:
            continue
        if only_available and r.remaining <= 0:
            continue
        if busy and eng.busy_conflict(json.loads(r.sessions_json or "[]"), busy):
            continue
        out.append(eng.row_to_dict(r, eng.TABLE_FIELDS))
    return {"rows": out, "total": len(out)}


def _meta_rows() -> dict:
    with SessionLocal() as db:
        kvs = {k.key: k.value for k in db.scalars(select(MetaKV)).all()}
        count = len(db.scalars(select(CourseClass.id)).all())
        colleges = sorted({r for r in db.scalars(select(CourseClass.college)).all() if r})
        campuses = sorted({r for r in db.scalars(select(CourseClass.campus)).all() if r})
        natures = sorted({r for r in db.scalars(select(CourseClass.nature)).all() if r})
        categories = sorted({r for r in db.scalars(select(CourseClass.course_category)).all() if r})
        attributions = sorted({r for r in db.scalars(select(CourseClass.course_attribution)).all() if r})
    return {"class_count": count, **kvs, "colleges": colleges,
            "campuses": campuses, "natures": natures,
            "course_categories": categories, "course_attributions": attributions,
            "custom_categories": list(load_custom_categories().keys())}


@router.get("/meta")
def meta():
    return _meta_rows()


@router.get("/courses")
def courses(
    keyword: str = "", college: str = "", nature: str = "", campus: str = "",
    course_name: str = "", course_no: str = "", course_category: str = "", course_attribution: str = "",
    teacher: str = "", credit_min: float | None = None, credit_max: float | None = None,
    weekday: int | None = None, period_min: int = 1, period_max: int = 15,
    only_available: bool = False, avoid_busy: bool = False,
    busy_slots: str = "",          # 格式 "1:1;3:6;4:7:2,6,8,10"（w:p[:周次]，; 分隔）
    sort: str = "course_name", limit: int = Query(50, ge=0, le=5000), offset: int = 0,
):
    busy = eng.parse_busy_slots(busy_slots)
    return search_courses_impl(
        {"keyword": keyword, "college": college, "nature": nature, "campus": campus,
         "course_name": course_name, "course_no": course_no, "course_category": course_category,
         "course_attribution": course_attribution,
         "teacher": teacher, "credit_min": credit_min, "credit_max": credit_max,
         "weekday": weekday, "period_min": period_min, "period_max": period_max,
         "only_available": only_available},
        busy_slots=busy if avoid_busy else set(), sort=sort, limit=limit, offset=offset)


@router.get("/courses/detail/{xk_id}")
def course_detail(xk_id: str):
    from ..agent import _tool_detail
    result, _ = _tool_detail({"xk_id": xk_id}, set())
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/courses/filter")
def filter_courses(body: dict):
    """AI 精选表格的工具栏过滤：xk_ids + 有余量 / 排除冲突。"""
    return filter_ids_impl(body.get("xk_ids") or [],
                           bool(body.get("only_available")),
                           eng.parse_busy_slots(body.get("busy_slots") or ""))
