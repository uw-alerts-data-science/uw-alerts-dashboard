import os
import sys

from scraper.logging_config import setup_logging

logger = setup_logging("scraper")
REQUIRED_ENV_VARS = ["ANTHROPIC_API_KEY", "GOOGLE_MAPS_API_KEY", "DATABASE_URL"]


def load_config() -> dict:
    config, missing = {}, []
    for var in REQUIRED_ENV_VARS:
        value = os.environ.get(var)
        if value:
            config[var] = value
        else:
            missing.append(var)
    if missing:
        for var in missing:
            logger.error("missing_env_var", extra={"var": var})
        sys.exit(1)
    return config
