# scraper/tests/test_config.py
import pytest
from unittest.mock import patch


# --- load_config: direct (no Azure) ---


def test_load_config_direct_returns_all_vars(monkeypatch):
    monkeypatch.setenv("USE_AZURE", "false")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "maps-test")
    monkeypatch.setenv("DATABASE_URL", "postgres://localhost/test")
    from scraper.config import load_config

    cfg = load_config()
    assert cfg["ANTHROPIC_API_KEY"] == "sk-test"
    assert cfg["USE_AZURE"] is False


def test_load_config_missing_one_var_exits_1(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("USE_AZURE", "false")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "maps-test")
    monkeypatch.setenv("DATABASE_URL", "postgres://localhost/test")
    from scraper.config import load_config

    with pytest.raises(SystemExit) as exc:
        load_config()
    assert exc.value.code == 1


def test_load_config_all_missing_exits_1(monkeypatch):
    for var in [
        "ANTHROPIC_API_KEY",
        "GOOGLE_MAPS_API_KEY",
        "DATABASE_URL",
        "USE_AZURE",
    ]:
        monkeypatch.delenv(var, raising=False)
    from scraper.config import load_config

    with pytest.raises(SystemExit) as exc:
        load_config()
    assert exc.value.code == 1


# --- load_config: Azure ---


def test_load_config_azure_returns_azure_vars(monkeypatch):
    monkeypatch.setenv("USE_AZURE", "true")
    monkeypatch.setenv("AZURE_ANTHROPIC_BASE_URL", "https://my-azure.example.com")
    monkeypatch.setenv("AZURE_ANTHROPIC_API_KEY", "azure-key")
    monkeypatch.setenv("AZURE_ANTHROPIC_DEPLOYMENT", "claude-sonnet-4-5")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "maps-test")
    monkeypatch.setenv("DATABASE_URL", "postgres://localhost/test")
    from scraper.config import load_config

    cfg = load_config()
    assert cfg["USE_AZURE"] is True
    assert cfg["AZURE_ANTHROPIC_BASE_URL"] == "https://my-azure.example.com"
    assert cfg["AZURE_ANTHROPIC_DEPLOYMENT"] == "claude-sonnet-4-5"
    assert "ANTHROPIC_API_KEY" not in cfg


def test_load_config_azure_missing_azure_var_exits_1(monkeypatch):
    monkeypatch.setenv("USE_AZURE", "true")
    monkeypatch.delenv("AZURE_ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.setenv("AZURE_ANTHROPIC_API_KEY", "azure-key")
    monkeypatch.setenv("AZURE_ANTHROPIC_DEPLOYMENT", "claude-sonnet-4-5")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "maps-test")
    monkeypatch.setenv("DATABASE_URL", "postgres://localhost/test")
    from scraper.config import load_config

    with pytest.raises(SystemExit) as exc:
        load_config()
    assert exc.value.code == 1


# --- get_anthropic_client ---


def test_get_anthropic_client_direct(monkeypatch):
    config = {"USE_AZURE": False, "ANTHROPIC_API_KEY": "sk-direct"}
    with patch("scraper.config.anthropic.Anthropic") as mock_cls:
        from scraper.config import get_anthropic_client

        get_anthropic_client(config)
        mock_cls.assert_called_once_with(api_key="sk-direct")


def test_get_anthropic_client_azure(monkeypatch):
    config = {
        "USE_AZURE": True,
        "AZURE_ANTHROPIC_BASE_URL": "https://my-azure.example.com",
        "AZURE_ANTHROPIC_API_KEY": "azure-key",
        "AZURE_ANTHROPIC_DEPLOYMENT": "claude-sonnet-4-5",
    }
    with patch("scraper.config.anthropic.Anthropic") as mock_cls:
        from scraper.config import get_anthropic_client

        get_anthropic_client(config)
        mock_cls.assert_called_once_with(
            base_url="https://my-azure.example.com",
            api_key="azure-key",
        )


# --- get_model_name ---


def test_get_model_name_direct_default():
    from scraper.config import get_model_name

    assert get_model_name({"USE_AZURE": False}) == "claude-haiku-4-5-20251001"


def test_get_model_name_direct_from_env():
    from scraper.config import get_model_name

    cfg = {"USE_AZURE": False, "ANTHROPIC_HAIKU_MODEL": "claude-haiku-4-5"}
    assert get_model_name(cfg) == "claude-haiku-4-5"


def test_get_model_name_azure():
    from scraper.config import get_model_name

    cfg = {"USE_AZURE": True, "AZURE_ANTHROPIC_DEPLOYMENT": "claude-sonnet-4-5"}
    assert get_model_name(cfg) == "claude-sonnet-4-5"
