import json
import os

from core.common import log, ROOT_DIR

# Lưu ý: chạy trên Termux thì file này nằm trong bộ nhớ máy nên vẫn còn
# nguyên sau khi restart bot hay khởi động lại điện thoại — chỉ mất nếu
# gỡ app Termux hoặc xoá dữ liệu app.
NOTIFY_STORE_PATH = os.path.join(ROOT_DIR, "notify_settings.json")

def load_disabled_guilds() -> set:
    if not os.path.exists(NOTIFY_STORE_PATH):
        return set()
    try:
        with open(NOTIFY_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {int(g) for g in data.get("disabled_guilds", [])}
    except (json.JSONDecodeError, OSError, ValueError) as e:
        log(f"Không đọc được notify_settings.json, dùng danh sách rỗng: {e}", "warn")
        return set()

def save_disabled_guilds(guild_ids: set):
    try:
        with open(NOTIFY_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump({"disabled_guilds": list(guild_ids)}, f)
    except OSError as e:
        log(f"Không lưu được notify_settings.json: {e}", "warn")
