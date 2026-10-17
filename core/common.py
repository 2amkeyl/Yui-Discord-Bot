import contextvars
import json
import os
import random
import time
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import discord


# Thư mục gốc của project (chứa main.py) — dùng cho mọi đường dẫn file dữ liệu
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Giờ Việt Nam (UTC+7), dùng chung cho mọi cog / store
VN_TZ = timezone(timedelta(hours=7))

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

def err_embed(text: str, guild: Optional[discord.Guild] = None) -> discord.Embed:
    """Embed báo lỗi (màu đỏ) dùng chung cho mọi cog."""
    return make_embed(text, color=ERROR_COLOR, guild=guild)

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

# Đọc / ghi file JSON dùng chung cho các store trong stores/.
# Ghi vào file .tmp rồi os.replace nên nếu bot bị kill giữa chừng (Termux...) file cũ vẫn còn nguyên.

def read_json(path: str, default: Any = None, *, label: Optional[str] = None) -> Any:
    """Đọc JSON; file chưa có thì trả `default`, file hỏng thì log cảnh báo rồi trả `default`."""
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, ValueError) as e:
        log(f"Không đọc được {label or os.path.basename(path)}, dùng dữ liệu mặc định: {e}", "warn")
        if isinstance(e, ValueError):  # JSON hỏng/không giải mã được: giữ lại bản hỏng để cứu, kẻo lần lưu sau ghi đè mất
            try:
                os.replace(path, path + ".corrupt")
            except OSError:
                pass
        return default

def write_json_atomic(path: str, data: Any, *, mode: int = 0o666, **dump_kwargs) -> None:
    """Ghi JSON an toàn (ghi .tmp -> fsync -> os.replace). Ném OSError nếu ghi thất bại."""
    tmp = path + ".tmp"
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, **dump_kwargs)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:  # kể cả TypeError do dữ liệu không serialize được: dọn .tmp, file cũ giữ nguyên
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise

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
