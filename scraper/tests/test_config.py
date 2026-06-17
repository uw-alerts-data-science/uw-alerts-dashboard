# scraper/tests/test_config.py
import pytest


def test_load_config_returns_all_vars(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "maps-test")
    monkeypatch.setenv("DATABASE_URL", "postgres://localhost/test")
    from scraper.config import load_config
    cfg = load_config()
    assert cfg["ANTHROPIC_API_KEY"] == "sk-test"
    assert cfg["GOOGLE_MAPS_API_KEY"] == "maps-test"
    assert cfg["DATABASE_URL"] == "postgres://localhost/test"


def test_load_config_missing_one_var_exits_1(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "maps-test")
    monkeypatch.setenv("DATABASE_URL", "postgres://localhost/test")
    from scraper.config import load_config
    with pytest.raises(SystemExit) as exc:
        load_config()
    assert exc.value.code == 1


def test_load_config_all_missing_exits_1(monkeypatch):
    for var in ["ANTHROPIC_API_KEY", "GOOGLE_MAPS_API_KEY", "DATABASE_URL"]:
        monkeypatch.delenv(var, raising=False)
    from scraper.config import load_config
    with pytest.raises(SystemExit) as exc:
        load_config()
    assert exc.value.code == 1
