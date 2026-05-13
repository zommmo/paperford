# 默认配置，占位值，后续可按需替换
BASE_URL = "https://api.example.com/v1"
MODEL = "your-model-name"
TEMPERATURE = 0.7
BATCH_SIZE = 4
CONCURRENCY = 4
DEFAULT_TARGET_LANGUAGE = "Chinese"
TARGET_LANGUAGES = ["Chinese", "English", "Japanese", "Korean", "French", "German", "Spanish"]
MAX_BLOCK_TOKENS = 900

# 翻译提示与容错设置
PROMPT_VERSION = "v1"


def build_system_prompt(target_language: str = DEFAULT_TARGET_LANGUAGE) -> str:
    # system prompt 强制模型仅输出结构化 JSON，保证段落顺序可控。
    language = (target_language or DEFAULT_TARGET_LANGUAGE).strip()
    return (
        "You are a translation engine that only outputs JSON. "
        'Return a JSON array like [{"id":"...","translation":"..."}]. '
        "No explanations. Cover all input ids. "
        f"Translations must be {language}. "
        "Do not output Markdown or use ```json code fences. "
        "Output must start with [ and end with ], with no extra characters."
    )


SYSTEM_PROMPT = build_system_prompt(DEFAULT_TARGET_LANGUAGE)
DEFAULT_TIMEOUT = 60
MAX_RETRIES = 5

DB_PATH = "translations.sqlite3"
