# 默认配置，占位值，后续可按需替换
BASE_URL = "https://api.example.com/v1"
MODEL = "your-model-name"
TEMPERATURE = 0.7
BATCH_SIZE = 4
CONCURRENCY = 4

# 翻译提示与容错设置
PROMPT_VERSION = "v1"
# system prompt 强制模型仅输出结构化 JSON，保证段落顺序可控
SYSTEM_PROMPT = (
    "You are a translation engine that only outputs JSON. "
    'Return a JSON array like [{"id":"...","translation":"..."}]. '
    "No explanations. Cover all input ids. "
    "Translations must be Chinese."
)
DEFAULT_TIMEOUT = 60
MAX_RETRIES = 5

DB_PATH = "translations.sqlite3"
