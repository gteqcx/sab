"""Shared utilities: privacy filter + SHA-256 deduplication."""
import re
import hashlib
import json
import time
from pathlib import Path

DEDUP_PATH = Path.home() / ".claude/memory-mcp/.dedup_cache.json"
DEDUP_WINDOW = 300  # 5 minutes

_SECRET_PATTERNS = [
    (r'sk-[a-zA-Z0-9]{8,}',              '[OPENAI_KEY]'),
    (r'sk-or-v1-[a-zA-Z0-9\-]{8,}',     '[OPENROUTER_KEY]'),
    (r'tvly-[a-zA-Z0-9_\-]{8,}',        '[TAVILY_KEY]'),
    (r'AIza[a-zA-Z0-9_\-]{10,}',        '[GOOGLE_KEY]'),
    (r'AQ\.[a-zA-Z0-9_\-]{8,}',         '[GEMINI_KEY]'),
    (r'ghp_[a-zA-Z0-9]{10,}',           '[GITHUB_TOKEN]'),
    (r'ghs_[a-zA-Z0-9]{10,}',           '[GITHUB_TOKEN]'),
    (r'xoxb-[a-zA-Z0-9\-]{50,}',        '[SLACK_TOKEN]'),
    (r'Bearer\s+[a-zA-Z0-9._\-]{20,}',  'Bearer [REDACTED]'),
    (r'(?i)(password|passwd|secret|api[_\-]?key|access[_\-]?token)\s*[=:]\s*["\']?[\w\-\.]{8,}',
     r'\1=[REDACTED]'),
]


def filter_secrets(text: str) -> str:
    for pattern, replacement in _SECRET_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


def is_duplicate(content: str) -> bool:
    """Return True if identical content was uploaded within DEDUP_WINDOW seconds."""
    h = hashlib.sha256(content.strip().encode()).hexdigest()
    now = time.time()

    cache: dict = {}
    if DEDUP_PATH.exists():
        try:
            cache = json.loads(DEDUP_PATH.read_text())
        except Exception:
            cache = {}

    cache = {k: v for k, v in cache.items() if now - v < DEDUP_WINDOW}

    if h in cache:
        DEDUP_PATH.write_text(json.dumps(cache))
        return True

    cache[h] = now
    DEDUP_PATH.write_text(json.dumps(cache))
    return False
