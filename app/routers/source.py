"""资料来源：分享的课程表格文件（下载制——文件展示在本页，查看需下载到本地）。

文件由 `python -X utf8 -m app.source_gen <教务导出xlsx>` 生成到 data/ 下；
未生成时接口降级为 available=false，前端给出引导文案。
"""
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import DATA_DIR

router = APIRouter(prefix="/api/source")

XLSX_OUT = DATA_DIR / "资料来源_按条件查询上课情况.xlsx"
META_OUT = DATA_DIR / "source_meta.json"
NOTE = "数据通过“我的商大-信息查询-按条件查询上课情况”获取"


@router.get("")
def source_meta():
    if not XLSX_OUT.exists():
        return {"available": False}
    meta = {}
    if META_OUT.exists():
        try:
            meta = json.loads(META_OUT.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    return {"available": True, "note": NOTE,
            "updated_at": meta.get("updated_at", ""),
            "rows": meta.get("rows", 0), "cols": meta.get("cols", 0),
            "size_bytes": meta.get("size_bytes", XLSX_OUT.stat().st_size)}


@router.get("/download")
def download():
    if not XLSX_OUT.exists():
        raise HTTPException(404, "资料来源表尚未生成：请先运行 python -X utf8 -m app.source_gen")
    return FileResponse(XLSX_OUT, filename=XLSX_OUT.name,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
