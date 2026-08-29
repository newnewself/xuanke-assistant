"""LLM 接口配置：存本地 config.local.json（.gitignore，不进仓库）。"""
import json
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..agent import load_config
from ..config import CONFIG_PATH

router = APIRouter(prefix="/api/config")

# 未配置时给用户的默认接入点（OpenAI 兼容网关），仅需再填 API Key
DEFAULT_BASE_URL = "https://opencode.ai/zen/go/v1"
DEFAULT_MODEL = "glm-5.3-flash"


class ConfigIn(BaseModel):
    api_key: str = ""
    # base_url / model 不由界面下发：留空时沿用已存值，新机器回落到内置默认（防君子，不对外展示网关地址）
    base_url: str = ""
    model: str = ""


@router.get("")
def get_config():
    cfg = load_config()
    key = cfg.get("api_key") or ""
    return {"configured": bool(cfg.get("base_url") and key and cfg.get("model")),
            "model": cfg.get("model") or DEFAULT_MODEL,
            "api_key_masked": (key[:4] + "****" + key[-4:]) if len(key) > 8 else ("已填写" if key else "")}


@router.put("")
def put_config(body: ConfigIn):
    old = load_config()
    cfg = {
        "base_url": body.base_url.strip() or old.get("base_url", "") or DEFAULT_BASE_URL,
        "model": body.model.strip() or old.get("model", "") or DEFAULT_MODEL,
        "api_key": body.api_key.strip() or old.get("api_key", ""),
    }
    if not cfg["api_key"]:
        raise HTTPException(400, "API Key 不能为空")
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


@router.post("/test")
def test_config():
    cfg = load_config()
    if not (cfg.get("base_url") and cfg.get("api_key") and cfg.get("model")):
        raise HTTPException(400, "请先保存完整配置")
    try:
        from openai import OpenAI
        client = OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"], timeout=30)
        client.chat.completions.create(
            model=cfg["model"],
            messages=[{"role": "user", "content": "hi"}], max_tokens=1)
        return {"ok": True, "message": "连接成功"}
    except Exception as e:
        msg = str(e)
        msg = re.sub(r"(sk-[A-Za-z0-9]{6})[A-Za-z0-9]+", r"\1****", msg)
        return {"ok": False, "message": msg[:300]}
