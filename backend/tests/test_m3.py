"""Smoke test: call MiniMax-M3 directly via the anthropic SDK."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import MINIMAX_BASE_URL, MINIMAX_API_KEY, MINIMAX_MODEL
from anthropic import Anthropic

client = Anthropic(base_url=MINIMAX_BASE_URL, api_key=MINIMAX_API_KEY)

resp = client.messages.create(
    model=MINIMAX_MODEL,
    max_tokens=64,
    messages=[{"role": "user", "content": "你好，只回复两个字：正常"}],
)

print("text:", resp.content[0].text)
print("usage:", resp.usage)
