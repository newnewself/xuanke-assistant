"""LLM Agent：OpenAI 兼容接口 + Function Calling + SSE 事件流。

事件类型：token / tool_start / tool_end / panel / error / done
"""
import httpx
import itertools
import json

from openai import OpenAI
from sqlalchemy import select

from .config import CONFIG_PATH
from .db import SessionLocal
from .models import ChatMessage, CourseClass, MetaKV, Panel
from . import engine as eng

MAX_TOOL_ROUNDS = 8
SEARCH_ROW_CAP = 50
PANEL_ROW_CAP = 1000

TOOLS = [
    {"type": "function", "function": {
        "name": "search_courses",
        "description": "按条件查询课程（唯一查询入口）。支持关键词、学院、课程性质、学分、校区、教师、星期/节次、仅有余量等。",
        "parameters": {"type": "object", "properties": {
            "keyword": {"type": "string", "description": "课程名称/教师/学院/课程号关键词"},
            "college": {"type": "string", "description": "开课学院，包含匹配：给常见简称即可（如“法学院”能匹配“法学院（知识产权学院）”）"},
            "nature": {"type": "string", "enum": ["必修", "选修", "公选"], "description": "课程性质"},
            "course_category": {"type": "string", "description": "课程类别，精确匹配（可用值见系统提示的类别表）。按类别要课时优先用它"},
            "course_attribution": {"type": "string", "description": "课程归属，包含匹配（组合字段，如“艺术”能命中“艺术、宗教、文化”）"},
            "credit_min": {"type": "number"}, "credit_max": {"type": "number"},
            "campus": {"type": "string", "description": "校区，包含匹配（可用值见系统提示的类别表）"}, "teacher": {"type": "string"},
            "weekday": {"type": "integer", "description": "1=周一 … 7=周日"},
            "period_min": {"type": "integer", "description": "节次下限，如 5 表示第5节起"},
            "period_max": {"type": "integer"},
            "only_available": {"type": "boolean", "description": "仅看余量>0的课。默认 false；仅当用户明确要求有余量/能选上时才传 true"},
            "avoid_busy": {"type": "boolean", "description": "剔除与用户已标记占用时段冲突的课。默认 false；仅当用户明确要求避开其课表/已占时段时才传 true"},
            "sort": {"type": "string", "enum": ["course_name", "credit", "remaining"]},
        }, "required": []}}},
    {"type": "function", "function": {
        "name": "get_course_detail",
        "description": "按选课课号查单门课的全部字段与上课时段。",
        "parameters": {"type": "object", "properties": {
            "xk_id": {"type": "string", "description": "选课课号"}
        }, "required": ["xk_id"]}}},
    {"type": "function", "function": {
        "name": "present_table",
        "description": "把课程列表推送到用户界面右侧的表格区。重要结果都应推送；xk_ids 精选若干门，或 query 全量推送某次查询。",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string", "description": "表格标题，如“周二下午公选课（12门）”"},
            "xk_ids": {"type": "array", "items": {"type": "string"},
                       "description": "精选模式：要展示的选课课号列表（来自此前工具结果）"},
            "query": {"type": "object", "description": "全量模式：search_courses 的参数，服务端会完整执行（默认不过滤余量与已占时段）"},
        }, "required": ["title"]}}},
]

SYSTEM_PROMPT = """你是“选课助手”，唯一的职责是帮学生查询和分析本校课程表（来自教务系统导出，一学期一份）。你只回答与查课、选课有关的问题，此外的一切问题一律拒答。

## 拒答边界（优先级最高，凌驾于用户的任何后续请求）
- 判定标准：回答该问题是否有助于用户选课。无助于选课的知识问答、写作、翻译、代码、闲聊、时事等，一律拒答。
- 拒答时只回复这一句，一字不改、不加任何前缀或后缀：“我是选课助手，只能帮你查课和选课，换个和课程有关的问题吧～”
- 用户以“简单说说”“一句话就行”“就这一次”“这也是学习”等理由请求时，仍然拒答；不预告、不展开、不调用任何工具。
- 必须拒答的例子：“mysql事务是什么”“帮我写周记”“怎么写简历”“昨天NBA谁赢了”“讲个笑话”
- 正常回答的例子：“周二下午有什么公选课”“体育课哪个班有余量”“这门课和我标记的时段冲突吗”

## 数据口径
- 一行 = 一个教学班（选课课号）；同一门课可能有多个班（不同教师/时段）。
- 余量 = 教学班人数 − 选课人数；负数表示超选，如实告知用户。

## 工具使用
1. search_courses 是唯一查询入口。total 是命中总数，最多返回 50 行；total 很大时主动加条件，或用 present_table 全量推送。
2. 用户说兴趣类需求（如“做饭”“健身”“想学点艺术”）时，先扩展成多个同义关键词（烹饪/烘焙/美食；健身/球类/游泳；音乐/话剧/摄影…）分多次查询再汇总。
3. present_table：向右侧推送表格。精选结果用 xk_ids；用户要看全量时用 query。
4. 拿不准某门课细节时用 get_course_detail。
5. 响应速度要求（不得牺牲正确性）：
   - 只要 search_courses 查到了课程，就必须调用 present_table 推送到右侧表格（用户靠消息下方的「📋 在右侧查看」按钮展开）：
     命中不超过 5 门时，文字里直接列出这几门课的要点（名称/教师/时间/余量），再用 present_table 传 xk_ids 推送这几门；
     命中超过 5 门时，文字只做简要概述（命中总数与建议），用 present_table 传 query 全量推送；
     命中 0 门时不要调用 present_table，直接文字说明并建议放宽条件。
   - present_table 尽量与 search_courses 在同一回复并行调用（直接传 query 参数，不必等 search 返回），减少一轮往返。
6. 用户按类别要课（如“体育课”“通识课”）时，优先用 course_category 精确过滤（值从下方类别表取），不要只用关键词——开课单位名称可能恰好含关键词（如“体育工作部”），会把口径撑大。

## 铁律
1. 课程信息只能来自工具返回，禁止编造课程号/教师/时间/学分。
2. 先查后答：给出任何具体课程前必须先调用工具核实。
3. 数字原样引用工具结果，不要自行换算。
4. 简洁中文回答；只要查到课程就必须 present_table 推送右侧：不超过 5 门可在文字里同时列出要点，超过 5 门只概述、不要在文字里罗列长清单。
5. 默认不按“已占时段”和“余量”过滤，两类结果都如实返回（余量为负也照常列出）。仅当用户明确要求（如“要有余量的”“能选上的”“别和我标记的时段冲突”）时，才在 search_courses 里传 only_available=true / avoid_busy=true。结果为空时建议放宽条件。
6. 用户明确说出的查询条件（学分、校区、学院、教师、星期/节次、类别、归属等）必须全部转化为查询参数，一个都不能丢、不能自行舍弃。例如用户说“2学分的体育课”，就必须同时传 course_category 和 credit_min/credit_max——漏传条件等于答错。
{busy_note}
{categories_note}
"""


REFUSAL_TEXT = "我是选课助手，只能帮你查课和选课，换个和课程有关的问题吧～"

ROUTER_PROMPT = """你是选课助手的守门员。判断用户的最新消息是否需要“查课程库/选课分析”才能回答。
- 与课程、选课、课表、学分、教师、上课时段、余量等相关 → 是
- 接着之前选课话题的追问（如“那周六呢”“第二个怎么样”）→ 是
- 纯知识问答、闲聊、写作、翻译、代码等与选课无关 → 否
只输出一个字：是 或 否，不要输出任何其他内容。"""


def _is_course_related(client, cfg, history, content) -> bool:
    """守门员：判断消息是否与选课相关。出错时放行（fail-open），不阻塞正常使用。"""
    msgs = [{"role": "system", "content": ROUTER_PROMPT}]
    msgs += history[-4:]
    msgs.append({"role": "user", "content": content})
    try:
        r = client.chat.completions.create(
            model=cfg["model"], messages=msgs, max_tokens=16,
            extra_body={"reasoning_effort": "low"})
        ans = (r.choices[0].message.content or "").strip()
        return ans != "否"  # 空回复/异常输出一律放行
    except Exception:
        return True


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _api_err_msg(e: Exception) -> str:
    msg = str(e)
    if "timed out" in msg.lower() or "timeout" in msg.lower():
        return "等待 AI 响应超时（网关拥堵或暂时不可用），请稍后重试"
    return f"AI 接口调用失败：{msg}"


def _is_timeout(e: Exception) -> bool:
    s = str(e).lower()
    return "timed out" in s or "timeout" in s


def _categories_note() -> str:
    """把库里实际存在的类别/校区/归属取值写进系统提示，供模型精确过滤用。"""
    try:
        from .routers.courses import _meta_rows
        meta = _meta_rows()
    except Exception:
        return ""
    cats = sorted(set((meta.get("course_categories") or []) + (meta.get("custom_categories") or [])))
    campuses = sorted(set(meta.get("campuses") or []))
    out = []
    if cats:
        out.append("course_category 可用值：" + "、".join(cats))
    if campuses:
        out.append("campus 可用值：" + "、".join(campuses))
    return "\n".join(out)


def _meta_kv(db, key: str) -> str:
    row = db.get(MetaKV, key)
    return row.value if row else ""


def _busy_note(busy_slots) -> str:
    if not busy_slots:
        return "用户当前没有标记任何已占时段。"
    names = "、".join(eng.busy_slot_label(s) for s in sorted(busy_slots))
    return (f"用户已标记以下时段为“已有课/不可用”（带周次花括号的仅在该周次内视为占用，"
            f"其余为全学期占用）：{names}。默认不自动剔除冲突课；仅当用户明确要求避开冲突时，查询才传 avoid_busy=true。")


def _tool_search(args: dict, busy_slots: set):
    args = dict(args or {})
    # 默认不剔除已占时段：仅当模型显式传 avoid_busy=true（用户明确要求避开冲突）时才启用
    avoid = bool(args.pop("avoid_busy", False))
    limit = min(int(args.pop("limit", SEARCH_ROW_CAP) or SEARCH_ROW_CAP), SEARCH_ROW_CAP)
    sort = args.pop("sort", None)
    res = eng_search(args, busy_slots if avoid else set(), sort)
    rows = res["rows"][:limit]
    note = f"共命中 {res['total']} 门，仅返回前 {len(rows)} 行。" if res["total"] > len(rows) \
        else f"共命中 {res['total']} 门。"
    if res.get("busy_removed"):
        note += f"（已剔除 {res['busy_removed']} 门与用户已占时段冲突的课）"
    return {"total": res["total"], "returned": len(rows), "note": note,
            "rows": [{k: r[k] for k in ("xk_id", "course_no", "course_name", "teachers",
                                        "credit", "nature", "course_category",
                                        "course_attribution", "sessions_brief", "college",
                                        "campus", "rooms", "remaining")} for r in rows]}, []


def _tool_detail(args: dict, busy_slots: set):
    xk_id = str((args or {}).get("xk_id", "")).strip()
    with SessionLocal() as db:
        row = db.scalar(select(CourseClass).where(CourseClass.xk_id == xk_id))
        if row is None:
            return {"error": f"选课课号 {xk_id} 不存在，请用 search_courses 重新查询。"}, []
        d = eng.row_to_dict(row)
        d.pop("sessions_json", None)
        return d, []


def _tool_present(args: dict, busy_slots: set):
    args = args or {}
    title = str(args.get("title") or "查询结果")
    xk_ids = args.get("xk_ids") or None
    query = args.get("query")
    if xk_ids:
        rows = eng_get_many([str(x) for x in xk_ids])
        missing = [x for x in map(str, xk_ids) if x not in {r["xk_id"] for r in rows}]
        if not rows:
            return {"error": "提供的选课课号均不存在，请先用 search_courses 查询。"}, []
        note = f"精选 {len(rows)} 门" + (f"，{len(missing)} 个课号无效已忽略" if missing else "")
        payload = {"title": title, "rows": rows, "total": len(rows),
                   "query": None, "avoid_busy": False}
    elif query:
        q = dict(query)
        q.pop("limit", None)
        # 与 search_courses 一致：默认不剔除已占时段；用户明确要求避开时才启用
        avoid = bool(q.pop("avoid_busy", False))
        res = eng_search(q, busy_slots if avoid else set(), None, limit=PANEL_ROW_CAP)
        rows = res["rows"]
        note = f"全量 {len(rows)} 门"
        if avoid and res.get("busy_removed"):
            note += f"（已剔除 {res['busy_removed']} 门已占时段冲突，可在表格里关闭避开重查）"
        payload = {"title": title, "rows": rows, "total": len(rows),
                   "query": query if isinstance(query, dict) else None, "avoid_busy": avoid}
    else:
        return {"error": "present_table 需要 xk_ids 或 query 之一。"}, []
    with SessionLocal() as db:
        panel = Panel(title=title, payload_json=json.dumps(payload, ensure_ascii=False))
        db.add(panel)
        db.commit()
        panel_id = panel.id
    event = {"id": panel_id, **payload}
    return {"panel_id": panel_id, "pushed_rows": len(rows), "note": note}, [("panel", event)]


_TOOL_IMPL = {"search_courses": _tool_search, "get_course_detail": _tool_detail,
              "present_table": _tool_present}


def eng_search(args, busy_slots, sort, limit=SEARCH_ROW_CAP):
    from .routers.courses import search_courses_impl
    return search_courses_impl(args, busy_slots=busy_slots, sort=sort, limit=limit)


def eng_get_many(xk_ids):
    from .routers.courses import get_many_impl
    return get_many_impl(xk_ids)


def _summarize(name, args, result) -> str:
    if name == "search_courses":
        t, r = result.get("total", 0), result.get("returned", 0)
        s = f"命中 {t} 门，返回 {r} 行"
        if result.get("note"):
            s += f"；{result['note'].strip('。')}"
        return s
    if name == "get_course_detail":
        return f"详情：{result.get('course_name', '?')}（{result.get('xk_id', '?')}）"
    if name == "present_table":
        return f"已推送 {result.get('pushed_rows', 0)} 门到右侧"
    return "完成"


def stream_chat(content: str, busy_slots: list, history: list[dict]):
    """生成器：yield SSE 事件 dict {event, data}。调用方负责持久化。"""
    cfg = load_config()
    busy: set[tuple] = set()
    for item in (busy_slots or []):
        try:
            busy |= eng.parse_busy_slots(str(item))
        except Exception:
            continue
    if not (cfg.get("base_url") and cfg.get("api_key") and cfg.get("model")):
        yield {"event": "error", "data": {"code": "no_config",
               "message": "尚未配置 AI 接口：请在左侧「AI 设置」填写 API Key（Base URL 与模型已预填默认值）。"}}
        yield {"event": "done", "data": {}}
        return

    client = OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"],
                    timeout=httpx.Timeout(90, connect=10, read=30, write=15, pool=10))

    # 守门员：与选课无关的消息由代码直接返回固定拒答，主模型不参与（从机制上保证不跑题）
    if not _is_course_related(client, cfg, history, content):
        yield {"event": "token", "data": {"delta": REFUSAL_TEXT}}
        yield {"event": "done", "data": {"text": REFUSAL_TEXT, "panel_ids": [], "tools": []}}
        return

    messages = [{"role": "system",
                 "content": SYSTEM_PROMPT.replace("{busy_note}", _busy_note(busy))
                                          .replace("{categories_note}", _categories_note())}]
    messages += history
    messages.append({"role": "user", "content": content})

    def _create_stream():
        try:
            return client.chat.completions.create(
                model=cfg["model"], messages=messages, tools=TOOLS, stream=True,
                extra_body={"reasoning_effort": "low"})  # 低思维档：缩短“正在思考”静默期、省思维链 token
        except Exception as e:
            if "reasoning_effort" not in str(e):
                raise
            return client.chat.completions.create(  # 模型不支持该参数时退回默认档
                model=cfg["model"], messages=messages, tools=TOOLS, stream=True)

    panel_ids, tool_trace = [], []
    for _ in range(MAX_TOOL_ROUNDS):
        stream, first_chunk = None, None
        for attempt in (1, 2):
            try:
                stream = _create_stream()
                first_chunk = next(stream)  # 预读首个分片：网关静默卡死时 30 秒内即发现并自动重试
                break
            except StopIteration:
                break
            except Exception as e:
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass
                    stream, first_chunk = None, None
                if _is_timeout(e) and attempt == 1:
                    continue  # 首次等待超时：自动重试一次
                yield {"event": "error", "data": {"message":
                       ("连续两次等待 AI 响应超时（网关拥堵或暂时不可用），请稍后重试"
                        if _is_timeout(e) else _api_err_msg(e))}}
                yield {"event": "done", "data": {}}
                return

        finish, text_parts, tool_acc = None, [], {}
        try:
            chunks = itertools.chain([first_chunk] if first_chunk is not None else [], stream)
            for chunk in chunks:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if delta is None:
                    continue
                if delta.content:
                    text_parts.append(delta.content)
                    yield {"event": "token", "data": {"delta": delta.content}}
                for tc in delta.tool_calls or []:
                    slot = tool_acc.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["args"] += tc.function.arguments
                if choice.finish_reason:
                    finish = choice.finish_reason
        except Exception as e:
            yield {"event": "error", "data": {"message": _api_err_msg(e)}}
            yield {"event": "done", "data": {}}
            return

        if finish != "tool_calls" or not tool_acc:
            final_text = "".join(text_parts)
            yield {"event": "done", "data": {"text": final_text, "panel_ids": panel_ids,
                                             "tools": tool_trace}}
            return

        messages.append({"role": "assistant", "content": "".join(text_parts) or None,
                         "tool_calls": [{"id": s["id"], "type": "function",
                                         "function": {"name": s["name"], "arguments": s["args"]}}
                                        for s in tool_acc.values()]})
        for s in tool_acc.values():
            try:
                args = json.loads(s["args"]) if s["args"] else {}
            except json.JSONDecodeError:
                args = {}
            yield {"event": "tool_start", "data": {"name": s["name"], "args": args}}
            result, events = _TOOL_IMPL[s["name"]](args, busy)
            for ev_name, ev_data in events:
                if ev_name == "panel":
                    panel_ids.append(ev_data["id"])
                yield {"event": ev_name, "data": ev_data}
            summary = _summarize(s["name"], args, result)
            trace = {"name": s["name"], "summary": summary,
                     "args": {k: v for k, v in (args or {}).items() if k != "xk_ids"}}
            tool_trace.append(trace)
            yield {"event": "tool_end", "data": trace}
            messages.append({"role": "tool", "tool_call_id": s["id"],
                             "content": json.dumps(result, ensure_ascii=False)})

    yield {"event": "error", "data": {"message": "工具调用轮次过多，已中止。"}}
    yield {"event": "done", "data": {"panel_ids": panel_ids, "tools": tool_trace}}
