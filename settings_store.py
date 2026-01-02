import json
import os
from typing import Dict


SETTINGS_DIR = os.path.expanduser("~/.epub_bilingual_translator")
SETTINGS_PATH = os.path.join(SETTINGS_DIR, "settings.json")


def load_settings() -> Dict:
    if not os.path.exists(SETTINGS_PATH):
        return {}
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        # 读取失败时返回空配置，避免启动中断
        return {}


def save_settings(settings: Dict) -> None:
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
