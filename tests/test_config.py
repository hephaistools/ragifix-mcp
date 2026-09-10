"""Tests des modèles de configuration de ragifix-mcp."""

from __future__ import annotations

import pytest

from ragifix_mcp.config import (
    AppConfig,
    ConfigError,
    LoggingConfig,
    McpSourceConfig,
    RagifixConfig,
    ServerConfig,
    load_config,
)


# -- ServerConfig --------------------------------------------------------------

def test_server_config_defaults():
    cfg = ServerConfig(auth_token_env="X")
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8422
    assert cfg.instructions == ""


def test_server_auth_token_missing_raises(monkeypatch):
    monkeypatch.delenv("RAGIFIX_MCP_TOKEN", raising=False)
    cfg = ServerConfig(auth_token_env="RAGIFIX_MCP_TOKEN")
    with pytest.raises(ConfigError):
        _ = cfg.auth_token


def test_server_auth_token_present(monkeypatch):
    monkeypatch.setenv("RAGIFIX_MCP_TOKEN", "secret")
    cfg = ServerConfig(auth_token_env="RAGIFIX_MCP_TOKEN")
    assert cfg.auth_token == "secret"


# -- RagifixConfig ---------------------------------------------------------------

def test_ragifix_config_defaults():
    cfg = RagifixConfig(api_token_env="X")
    assert cfg.base_url == "http://127.0.0.1:8421"
    assert cfg.timeout_seconds == 60.0


def test_ragifix_api_token_missing_raises(monkeypatch):
    monkeypatch.delenv("RAGIFIX_API_TOKEN", raising=False)
    cfg = RagifixConfig(api_token_env="RAGIFIX_API_TOKEN")
    with pytest.raises(ConfigError):
        _ = cfg.api_token


def test_ragifix_api_token_present(monkeypatch):
    monkeypatch.setenv("RAGIFIX_API_TOKEN", "secret")
    cfg = RagifixConfig(api_token_env="RAGIFIX_API_TOKEN")
    assert cfg.api_token == "secret"


# -- LoggingConfig / McpSourceConfig ---------------------------------------------

def test_logging_config_default():
    assert LoggingConfig().level == "INFO"


def test_logging_config_invalid_level_raises():
    with pytest.raises(ValueError):
        LoggingConfig(level="TRACE")


def test_mcp_source_config_requires_name_and_description():
    with pytest.raises(ValueError):
        McpSourceConfig.model_validate({"name": "s1"})


def test_mcp_source_config_valid():
    src = McpSourceConfig(name="s1", description="d")
    assert src.name == "s1"


# -- AppConfig ------------------------------------------------------------------

def test_app_config_valid(minimal_config_dict):
    cfg = AppConfig.model_validate(minimal_config_dict)
    assert cfg.server.auth_token_env == "RAGIFIX_MCP_TOKEN"
    assert cfg.ragifix.api_token_env == "RAGIFIX_API_TOKEN"
    assert cfg.mcp_sources == []
    assert cfg.logging.level == "INFO"


def test_app_config_with_mcp_sources(minimal_config_dict):
    minimal_config_dict["mcp_sources"] = [{"name": "s1", "description": "d"}]
    cfg = AppConfig.model_validate(minimal_config_dict)
    assert len(cfg.mcp_sources) == 1
    assert cfg.mcp_sources[0].name == "s1"


def test_app_config_requires_server_and_ragifix():
    with pytest.raises(ValueError):
        AppConfig.model_validate({})


# -- load_config ------------------------------------------------------------------

def test_load_config_missing(tmp_path):
    with pytest.raises(ConfigError):
        load_config(str(tmp_path / "inexistant.yaml"))


def test_load_config_empty(tmp_path):
    f = tmp_path / "empty.yaml"
    f.write_text("", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(str(f))


def test_load_config_invalid(tmp_path):
    f = tmp_path / "invalid.yaml"
    f.write_text("server:\n  auth_token_env: X\n", encoding="utf-8")  # ragifix manquant
    with pytest.raises(ConfigError):
        load_config(str(f))


def test_load_config_valid(write_config, minimal_config_dict):
    path = write_config(minimal_config_dict)
    cfg = load_config(path)
    assert isinstance(cfg, AppConfig)
    assert cfg.server.auth_token_env == "RAGIFIX_MCP_TOKEN"
