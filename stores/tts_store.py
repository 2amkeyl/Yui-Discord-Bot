import os

from core.common import log, read_json, write_json_atomic, ROOT_DIR

# Ngôn ngữ giọng đọc riêng của từng người dùng (user_id -> mã ngôn ngữ).
TTS_STORE_PATH = os.path.join(ROOT_DIR, "tts_settings.json")


def load_user_langs() -> dict[str, str]:
    data = read_json(TTS_STORE_PATH, {})
    try:
        return {str(uid): str(lang) for uid, lang in data.get("user_langs", {}).items()}
    except AttributeError as e:
        log(f"tts_settings.json sai định dạng, dùng cài đặt rỗng: {e}", "warn")
        return {}


def save_user_langs(user_langs: dict[str, str]):
    try:
        write_json_atomic(TTS_STORE_PATH, {"user_langs": user_langs})
    except OSError as e:
        log(f"Không lưu được tts_settings.json: {e}", "warn")
