"""路径与全局配置。"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "courses.db"
CONFIG_PATH = BASE_DIR / "config.local.json"
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

for _d in (DATA_DIR, UPLOAD_DIR):
    _d.mkdir(parents=True, exist_ok=True)
