import os

from core.common import log, read_json, write_json_atomic, ROOT_DIR

NOTIFY_STORE_PATH = os.path.join(ROOT_DIR, "notify_settings.json")

def load_disabled_guilds() -> set:
    data = read_json(NOTIFY_STORE_PATH, {})
    try:
        return {int(g) for g in data.get("disabled_guilds", [])}
    except (AttributeError, TypeError, ValueError) as e:
        log(f"notify_settings.json sai định dạng, dùng danh sách rỗng: {e}", "warn")
        return set()

def save_disabled_guilds(guild_ids: set):
    try:
        write_json_atomic(NOTIFY_STORE_PATH, {"disabled_guilds": list(guild_ids)})
    except OSError as e:
        log(f"Không lưu được notify_settings.json: {e}", "warn")
