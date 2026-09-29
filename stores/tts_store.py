import json
import os

from core.common import log, ROOT_DIR

# Ngôn ngữ giọng đọc riêng của từng người dùng (user_id -> mã ngôn ngữ).
TTS_STORE_PATH = os.path.join(ROOT_DIR, "tts_settings.json")


def load_user_langs() -> dict[str, str]:
    if not os.path.exists(TTS_STORE_PATH):
        return {}
    try:
        with open(TTS_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {str(uid): str(lang) for uid, lang in data.get("user_langs", {}).items()}
    except (json.JSONDecodeError, OSError, AttributeError) as e:
        log(f"Không đọc được tts_settings.json, dùng cài đặt rỗng: {e}", "warn")
        return {}


def save_user_langs(user_langs: dict[str, str]):
    tmp_path = TTS_STORE_PATH + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({"user_langs": user_langs}, f, ensure_ascii=False)
        os.replace(tmp_path, TTS_STORE_PATH)  # ghi xong mới thay file cũ, lỡ tắt máy giữa chừng không mất dữ liệu
    except OSError as e:
        log(f"Không lưu được tts_settings.json: {e}", "warn")
