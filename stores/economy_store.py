import os
import asyncio
from datetime import datetime
from typing import Optional

from core.common import ROOT_DIR, VN_TZ, read_json, write_json_atomic

DB_PATH = os.path.join(ROOT_DIR, "yui_db.json")

COIN_EMOJI = "<:klcow:1544278502654873630>"
NOITU_WIN_REWARD = 10000
DAILY_REWARD_MIN, DAILY_REWARD_MAX = 1000, 2000
GIVE_DAILY_LIMIT = 5_000_000
WORK_REWARD_MIN, WORK_REWARD_MAX = 200, 1000
WORK_COOLDOWN_SECONDS = 1800


def get_vn_today() -> str:
    return datetime.now(VN_TZ).strftime("%Y-%m-%d")


def parse_bet_amount(text: str, balance: int, max_cap: Optional[int] = None) -> Optional[int]:
    text = text.strip().lower().replace(" ", "")
    if text in ("all", "allin", "tatca"):
        return balance if max_cap is None else min(balance, max_cap)

    mult = 1
    if text.endswith("k"):
        mult, text = 1_000, text[:-1]
    elif text.endswith("m"):
        mult, text = 1_000_000, text[:-1]

    # Nếu có hậu tố k/m -> dấu . hoặc , còn lại chắc chắn là thập phân, giữ nguyên
    # Nếu KHÔNG có hậu tố -> coi , và . là phân cách hàng nghìn, xoá đi
    if mult == 1:
        text = text.replace(",", "").replace(".", "")

    try:
        value = int(float(text) * mult)
    except ValueError:
        return None
    return value if max_cap is None else min(value, max_cap)


class EconomyStore:
    """Ví Yui Coin dùng chung giữa economy_cog.py và minigame_cog.py."""

    def __init__(self):
        self.data: dict = read_json(DB_PATH, {}, label="yui_db.json")
        self._lock: Optional[asyncio.Lock] = None  # khởi tạo lười, tránh tạo Lock trước khi có event loop

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def ensure_user(self, uid: str) -> None:
        async with self.lock:
            if uid not in self.data:
                self.data[uid] = {"coins": 0, "wins": 0, "last_daily": "", "give_today": 0, "give_date": ""}

    async def save(self) -> None:
        async with self.lock:
            snapshot = dict(self.data)
        await asyncio.to_thread(write_json_atomic, DB_PATH, snapshot, indent=2)


economy = EconomyStore()
