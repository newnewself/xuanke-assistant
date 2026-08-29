from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class CourseClass(Base):
    """一个教学班（选课课号），拼课/查询的最小单元。"""

    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    xk_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    course_no: Mapped[str] = mapped_column(String(32), index=True)
    course_name: Mapped[str] = mapped_column(String(128), index=True)
    credit: Mapped[float] = mapped_column(Float)
    nature: Mapped[str] = mapped_column(String(32))          # 课程性质：必修/选修/公选
    course_category: Mapped[str] = mapped_column(String(32), default="")   # 课程类别（来自课程基本信息）
    course_attribution: Mapped[str] = mapped_column(String(64), default="")  # 课程归属
    college: Mapped[str] = mapped_column(String(64), index=True)  # 开课学院
    campus: Mapped[str] = mapped_column(String(32), index=True)   # 校区
    teachers: Mapped[str] = mapped_column(String(256), default="")  # 顿号连接
    staff_no: Mapped[str] = mapped_column(String(256), default="")   # 教工号，与 teachers 顺序对应
    gender: Mapped[str] = mapped_column(String(64), default="")
    teacher_titles: Mapped[str] = mapped_column(String(256), default="")
    teacher_edu: Mapped[str] = mapped_column(String(256), default="")
    teacher_college: Mapped[str] = mapped_column(String(256), default="")
    teacher_segments: Mapped[str] = mapped_column(Text, default="")  # 教师分段：徐冠雷(1-8周)、方毅立(9-16周)
    rooms: Mapped[str] = mapped_column(String(512), default="")     # 上课地点
    room_no: Mapped[str] = mapped_column(String(256), default="")   # 场地编号
    room_type: Mapped[str] = mapped_column(String(256), default="") # 场地类别名称
    room_weeks: Mapped[str] = mapped_column(String(256), default="") # 场地上课起始周
    room_periods: Mapped[str] = mapped_column(String(256), default="") # 场地上课节次
    building: Mapped[str] = mapped_column(String(256), default="")  # 教学楼
    floor: Mapped[str] = mapped_column(String(64), default="")      # 楼层号
    time_text: Mapped[str] = mapped_column(Text, default="")        # 上课时间原文
    sessions_json: Mapped[str] = mapped_column(Text, default="[]")  # 结构化时段
    week_hours: Mapped[str] = mapped_column(String(64), default="")  # 周学时（源为"理论(2.0)-实习(8.0)"等文本，存原文）
    total_hours: Mapped[float] = mapped_column(Float, default=0)
    plan_size: Mapped[float] = mapped_column(Float, default=0)      # 教学班人数(容量口径)
    enrolled: Mapped[float] = mapped_column(Float, default=0)       # 选课人数
    seats: Mapped[float] = mapped_column(Float, default=0)          # 教室座位数
    remaining: Mapped[float] = mapped_column(Float, default=0)      # 教学班人数-选课人数，可为负
    major_group: Mapped[str] = mapped_column(Text, default="")      # 专业组成
    class_group: Mapped[str] = mapped_column(Text, default="")      # 教学班组成
    year: Mapped[str] = mapped_column(String(16), default="")
    term: Mapped[str] = mapped_column(String(16), default="")


class Panel(Base):
    """AI 推送到右侧的表格卡片，持久化以便历史消息重新打开。"""

    __tablename__ = "panels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256))
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ChatMessage(Base):
    """对话消息：按 session_id 分组为多段独立会话。"""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    session_id: Mapped[str] = mapped_column(String(36), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class MetaKV(Base):
    """导入元信息：学年/学期/时间/来源/班级数。"""

    __tablename__ = "meta_kv"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
