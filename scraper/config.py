import os
import sys

import anthropic

from scraper.logging_config import setup_logging

logger = setup_logging("scraper")

_BASE_VARS = ["GOOGLE_MAPS_API_KEY", "DATABASE_URL"]
_DIRECT_VARS = ["ANTHROPIC_API_KEY"]
_AZURE_VARS = [
    "AZURE_ANTHROPIC_BASE_URL",
    "AZURE_ANTHROPIC_API_KEY",
    "AZURE_ANTHROPIC_DEPLOYMENT",
]


def load_config() -> dict:
    use_azure = os.environ.get("USE_AZURE", "false").lower() == "true"
    required = _BASE_VARS + (_AZURE_VARS if use_azure else _DIRECT_VARS)

    config, missing = {"USE_AZURE": use_azure}, []
    for var in required:
        value = os.environ.get(var)
        if value:
            config[var] = value
        else:
            missing.append(var)

    for var in ["ANTHROPIC_HAIKU_MODEL", "ANTHROPIC_SONNET_MODEL"]:
        value = os.environ.get(var)
        if value:
            config[var] = value

    if missing:
        for var in missing:
            logger.error("missing_env_var", extra={"var": var})
        sys.exit(1)
    return config


def get_anthropic_client(config: dict) -> anthropic.Anthropic:
    if config.get("USE_AZURE"):
        return anthropic.Anthropic(
            base_url=config["AZURE_ANTHROPIC_BASE_URL"],
            api_key=config["AZURE_ANTHROPIC_API_KEY"],
        )
    return anthropic.Anthropic(api_key=config["ANTHROPIC_API_KEY"])


def get_model_name(config: dict) -> str:
    if config.get("USE_AZURE"):
        return config["AZURE_ANTHROPIC_DEPLOYMENT"]
    return config.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001")
