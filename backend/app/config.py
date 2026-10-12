"""Application configuration loaded from backend/.env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH, override=True)

MINIMAX_BASE_URL: str = os.environ.get(
    "ANTHROPIC_BASE_URL", "https://api.minimax.cn/anthropic"
)

_api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
if not _api_key or _api_key == "<我的key>":
    raise RuntimeError("ANTHROPIC_API_KEY 未配置")
MINIMAX_API_KEY: str = _api_key

MINIMAX_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "MiniMax-M3")

WORKSPACE_DIR: Path = Path(__file__).resolve().parent.parent / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    print("MINIMAX_BASE_URL :", MINIMAX_BASE_URL)
    print("MINIMAX_MODEL    :", MINIMAX_MODEL)
    print("WORKSPACE_DIR    :", WORKSPACE_DIR)
    masked = MINIMAX_API_KEY[:8] + "..." if len(MINIMAX_API_KEY) >= 8 else MINIMAX_API_KEY
    print(f"MINIMAX_API_KEY  : {masked} (len={len(MINIMAX_API_KEY)})")
