import json
import os
from core.common import log, ROOT_DIR

GACHA_STORE_PATH = os.path.join(ROOT_DIR, "gacha_settings.json")
_LEGACY_PATH = os.path.join(ROOT_DIR, "watch_settings.json")

# Tương thích ngược: đổi tên file dữ liệu cũ (watch_settings.json) nếu có
if os.path.exists(_LEGACY_PATH) and not os.path.exists(GACHA_STORE_PATH):
    try:
        os.replace(_LEGACY_PATH, GACHA_STORE_PATH)
    except OSError:
        pass

def get_default_user_state() -> dict:
    return {
        "pity_counter": 0,
        "last_index": None,
        "total_rolls": 0,
        "tier_counts": {"0": 0, "1": 0, "2": 0, "3": 0},
        "actress_counts": {},
        "history": [],
        "daily_rolls": 0,
        "last_reset_date": ""
    }

def load_all_states() -> dict:
    if not os.path.exists(GACHA_STORE_PATH):
        return {}
    try:
        with open(GACHA_STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, ValueError) as e:
        log(f"Không đọc được gacha_settings.json: {e}", "warn")
        return {}

def save_all_states(states: dict):
    try:
        with open(GACHA_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(states, f, ensure_ascii=False)
    except OSError as e:
        log(f"Không lưu được gacha_settings.json: {e}", "warn")

def get_user_state(states: dict, user_id: int) -> dict:
    uid_str = str(user_id)
    if uid_str not in states:
        states[uid_str] = get_default_user_state()
    else:
        # Tương thích ngược: Thêm key mới nếu user cũ chưa có
        s = states[uid_str]
        if "history" not in s: s["history"] = []
        if "daily_rolls" not in s: s["daily_rolls"] = 0
        if "last_reset_date" not in s: s["last_reset_date"] = ""
    return states[uid_str]
