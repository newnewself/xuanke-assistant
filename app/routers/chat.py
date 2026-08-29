"""对话：SSE 流式 + 多会话历史持久化 + 面板取回。"""
import json
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select

from ..agent import stream_chat
from ..db import SessionLocal
from ..models import ChatMessage, Panel
from .courses import get_many_impl

router = APIRouter(prefix="/api")

# 每个会话传给模型的最大历史条数（也是前端提示"新开会话"的阈值）
HISTORY_LIMIT = 40


class ChatIn(BaseModel):
    content: str
    busy_slots: list[str] = []   # "w:p" 或 "w:p:2,6,8,10"
    session_id: str = ""


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
def chat(body: ChatIn):
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(400, "消息不能为空")
    session_id = (body.session_id or "").strip() or uuid.uuid4().hex

    with SessionLocal() as db:
        rows = db.scalars(select(ChatMessage)
                          .where(ChatMessage.session_id == session_id)
                          .order_by(ChatMessage.id.desc())
                          .limit(HISTORY_LIMIT)).all()
        history = [{"role": r.role, "content": r.content}
                   for r in reversed(rows) if r.role in ("user", "assistant") and r.content]
        db.add(ChatMessage(role="user", content=content, session_id=session_id))
        db.commit()

    def gen():
        yield _sse("session", {"session_id": session_id})
        with SessionLocal() as db:
            panel_ids, tools = [], []
            final_text = ""
            for ev in stream_chat(content, body.busy_slots, history):
                if ev["event"] == "panel":
                    panel_ids.append(ev["data"]["id"])
                elif ev["event"] == "done":
                    # error 事件可能先于 done 到达，空 text 不覆盖已记录的错误信息
                    if ev["data"].get("text"):
                        final_text = ev["data"]["text"]
                    tools = ev["data"].get("tools", []) or tools
                elif ev["event"] == "error":
                    final_text = f"⚠️ {ev['data'].get('message', '出错')}"
                yield _sse(ev["event"], ev["data"])
            if final_text:
                db.add(ChatMessage(role="assistant", content=final_text,
                                   session_id=session_id,
                                   meta_json=json.dumps({"tools": tools, "panel_ids": panel_ids},
                                                        ensure_ascii=False)))
                db.commit()

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/sessions")
def sessions():
    """所有会话列表：按最近消息倒序，title 取该会话第一条用户消息。"""
    with SessionLocal() as db:
        msgs = db.scalars(select(ChatMessage).order_by(ChatMessage.id)).all()
    order: list[str] = []
    by: dict[str, dict] = {}
    for m in msgs:
        if m.session_id not in by:
            by[m.session_id] = {"session_id": m.session_id, "title": "",
                                "count": 0, "last_time": str(m.created_at)}
            order.append(m.session_id)
        info = by[m.session_id]
        info["count"] += 1
        info["last_time"] = str(m.created_at)
        if not info["title"] and m.role == "user":
            info["title"] = m.content[:30]
    return [by[k] for k in reversed(order)]


@router.get("/history")
def history(session_id: str = ""):
    with SessionLocal() as db:
        rows = db.scalars(select(ChatMessage)
                          .where(ChatMessage.session_id == session_id)
                          .order_by(ChatMessage.id).limit(500)).all()
        total = db.scalar(select(func.count()).select_from(ChatMessage)
                          .where(ChatMessage.session_id == session_id)) or 0
    # truncated=True：会话消息数已达上限，更早的内容不再传给模型，前端据此提示新开会话
    return {"truncated": total >= HISTORY_LIMIT, "limit": HISTORY_LIMIT,
            "messages": [{"id": r.id, "role": r.role, "content": r.content,
                          "meta": json.loads(r.meta_json or "{}"), "created_at": str(r.created_at)}
                         for r in rows]}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    with SessionLocal() as db:
        db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
        db.commit()
    return {"ok": True}


@router.get("/panels/{panel_id}")
def get_panel(panel_id: int):
    with SessionLocal() as db:
        panel = db.get(Panel, panel_id)
    if panel is None:
        raise HTTPException(404, "面板不存在")
    payload = json.loads(panel.payload_json)
    # 行数据按课号现取：旧面板自动补齐新增字段，余量等也保持入库最新值（保持原顺序）
    ids = [r.get("xk_id") for r in (payload.get("rows") or []) if r.get("xk_id")]
    if ids:
        fresh = {r["xk_id"]: r for r in get_many_impl(ids)}
        payload["rows"] = [fresh[x] for x in ids if x in fresh]
        payload["total"] = len(payload["rows"])
    return payload | {"id": panel.id}
