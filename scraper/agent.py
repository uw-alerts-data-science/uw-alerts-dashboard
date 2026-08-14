import sys

from scraper.config import load_config
from scraper.live_discovery import run_live_discovery


def run_agent(config: dict) -> int:
    return run_live_discovery(config)


if __name__ == "__main__":
    sys.exit(run_agent(load_config()))
