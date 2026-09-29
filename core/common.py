import contextvars
import os
import random
import time
import asyncio
from datetime import datetime
from typing import Optional

import discord

# ==============================================================================
# ── CẤU HÌNH CƠ BẢN ───────────────────────────────────────────────────────────
# ==============================================================================

# Thư mục gốc của project (chứa main.py) — dùng cho mọi đường dẫn file dữ liệu
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HEART = "<a:klg23:1535400172199350332>"
EMBED_COLOR = 0xffb6c1
ERROR_COLOR = 0xff6961
FOOTER_TEXT = "Yui Hirasawa • Câu lạc bộ Nhạc Nhẹ"

RANDOM_GIFS = [
    "https://i.pinimg.com/originals/af/31/8d/af318d284a3eef8d521b0b7880898c57.gif",
    "https://i.pinimg.com/originals/78/df/3e/78df3e40841a6273341e2e4eaab80141.gif",
    "https://giffiles.alphacoders.com/349/34952.gif",
    "https://i.redd.it/l8m23lay25m71.gif",
    "https://i.pinimg.com/originals/b6/a0/71/b6a0714d5f20cd27457f152f59c155e6.gif",
    "https://i.pinimg.com/originals/79/8c/86/798c86f0f349317216aeb17fea188f87.gif",
]

current_footer_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("current_footer_ctx", default=FOOTER_TEXT)

def set_footer_guild(guild: Optional[discord.Guild]):
    current_footer_ctx.set(f"Yui Hirasawa • {guild.name}" if guild else FOOTER_TEXT)

def make_embed(description: str, *, title: str = None, color: int = EMBED_COLOR, gif: bool = False, guild: Optional[discord.Guild] = None) -> discord.Embed:
    embed = discord.Embed(description=description, color=color)
    if title:
        embed.title = title

    footer_text = f"Yui Hirasawa • {guild.name}" if guild else current_footer_ctx.get()
    embed.set_footer(text=footer_text)

    if gif and RANDOM_GIFS:
        embed.set_image(url=random.choice(RANDOM_GIFS))

    return embed

class Colors:
    RESET  = "\033[0m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    DIM    = "\033[2m"

DEBUG = True

def log(msg: str, level: str = "info"):
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = {"info": f"{Colors.CYAN}[INFO]{Colors.RESET}", "ok": f"{Colors.GREEN}[  OK]{Colors.RESET}", "warn": f"{Colors.YELLOW}[WARN]{Colors.RESET}", "error": f"{Colors.RED}[ ERR]{Colors.RESET}", "debug": f"{Colors.DIM}[DBG ]{Colors.RESET}"}.get(level, f"[{level.upper()}]")
    if level == "debug" and not DEBUG: return
    print(f"{Colors.DIM}{ts}{Colors.RESET} {prefix} {msg}")

# ==============================================================================
# ── HẠ TẦNG: RATE LIMITER & GỬI TIN NHẮN AN TOÀN ──────────────────────────────
# ==============================================================================
# Tránh bị Discord rate-limit khi bot gửi nhiều tin nhắn liên tục (ví dụ chào
# loạt người vào voice cùng lúc).

class GlobalRateLimiter:
    def __init__(self, max_per_second: float = 35):
        self.max_per_second = max_per_second
        self._lock: Optional[asyncio.Lock] = None  # khởi tạo lười, chỉ tạo khi đã có event loop đang chạy
        self._tokens = max_per_second
        self._last_refill = time.monotonic()

    async def acquire(self):
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self.max_per_second, self._tokens + elapsed * self.max_per_second)
            self._last_refill = now
            if self._tokens < 1:
                wait = (1 - self._tokens) / self.max_per_second
                await asyncio.sleep(wait)
                self._tokens = 0
                self._last_refill = time.monotonic()
            else:
                self._tokens -= 1

rate_limiter = GlobalRateLimiter()

async def safe_send(channel, content: str = None, *, embed: discord.Embed = None):
    await rate_limiter.acquire()
    try: await channel.send(content=content, embed=embed)
    except discord.HTTPException as e: log(f"Lỗi khi gửi tin nhắn vào kênh: {e}", "warn")
