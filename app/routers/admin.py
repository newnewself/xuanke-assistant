"""数据导入：上传教务导出的《按条件查询课程.xlsx》重建课程库。"""
import time

from fastapi import APIRouter, HTTPException, UploadFile

from .. import etl
from ..config import UPLOAD_DIR

router = APIRouter(prefix="/api/admin")

ALLOWED = {".xlsx", ".xls"}


@router.post("/import")
async def import_data(file: UploadFile):
    if not file.filename or "." not in file.filename or \
            ("." + file.filename.rsplit(".", 1)[1].lower()) not in ALLOWED:
        raise HTTPException(400, "请上传 .xlsx / .xls 格式的课程表文件")
    suffix = "." + file.filename.rsplit(".", 1)[1].lower()
    path = UPLOAD_DIR / f"import_{int(time.time())}{suffix}"
    try:
        with open(path, "wb") as f:
            while chunk := await file.read(1 << 20):
                f.write(chunk)
        stats = etl.import_file(path)
        return {"ok": True, "stats": stats}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"导入失败：{e}")
    finally:
        path.unlink(missing_ok=True)
