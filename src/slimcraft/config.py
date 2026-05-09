import os
import logging

logger = logging.getLogger("slimcraft")

ENV_PATHS = [
    os.path.join(os.getcwd(), ".env"),
    os.path.join(os.path.expanduser("~"), ".slimcraft", ".env"),
]


def load_env():
    """Load .env files from CWD and ~/.slimcraft/ (no external deps)."""
    for path in ENV_PATHS:
        if os.path.exists(path):
            _parse_dotenv(path)
            logger.debug("Loaded config from %s", path)


def _parse_dotenv(path):
    """Minimal .env parser."""
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("'\"").strip()
            if key and key not in os.environ:
                os.environ[key] = val


def getenv(key, default=None):
    """Get a config value from environment variables."""
    return os.environ.get(key, default)
