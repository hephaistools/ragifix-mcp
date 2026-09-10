"""Tests du point d'entrée CLI et de l'assemblage de l'application.

Seulement les chemins légers : validation des arguments, erreur de
configuration, avertissement d'accès distant, et démarrage réussi avec
`uvicorn.run` patché (pour éviter de lancer un vrai serveur).
"""

from __future__ import annotations

import logging

import pytest
import uvicorn

from ragifix_mcp.main import build_app, create_app, main


def test_main_missing_config_arg_exits(monkeypatch):
    monkeypatch.setattr("sys.argv", ["ragifix-mcp"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_main_invalid_config_exits(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sys.argv",
        ["ragifix-mcp", "--config", str(tmp_path / "inexistant.yaml")],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


def test_build_app_wraps_with_bearer_auth(minimal_config_dict, mcp_token_env, ragifix_token_env):
    from ragifix_mcp.auth import BearerAuthASGIMiddleware
    from ragifix_mcp.config import AppConfig

    config = AppConfig.model_validate(minimal_config_dict)
    app = build_app(config)
    assert isinstance(app, BearerAuthASGIMiddleware)


def test_create_app_warns_on_non_local_host(
    write_config, minimal_config_dict, mcp_token_env, ragifix_token_env, caplog
):
    minimal_config_dict["server"]["host"] = "0.0.0.0"
    path = write_config(minimal_config_dict)

    with caplog.at_level(logging.WARNING):
        create_app(str(path))

    assert any("accès non strictement" in record.message for record in caplog.records)


def test_create_app_no_warning_on_local_host(
    write_config, minimal_config_dict, mcp_token_env, ragifix_token_env, caplog
):
    path = write_config(minimal_config_dict)

    with caplog.at_level(logging.WARNING):
        create_app(str(path))

    assert not any("accès non strictement" in record.message for record in caplog.records)


def test_create_app_logs_mcp_sources_info(
    write_config, minimal_config_dict, mcp_token_env, ragifix_token_env, caplog
):
    minimal_config_dict["mcp_sources"] = [{"name": "s1", "description": "d"}]
    path = write_config(minimal_config_dict)

    with caplog.at_level(logging.INFO):
        create_app(str(path))

    assert any("Sources MCP locales configurées" in record.message for record in caplog.records)


def test_main_success_calls_uvicorn_run(
    monkeypatch, write_config, minimal_config_dict, mcp_token_env, ragifix_token_env
):
    path = write_config(minimal_config_dict)
    monkeypatch.setattr("sys.argv", ["ragifix-mcp", "--config", str(path)])

    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: calls.append(kwargs))

    main()

    assert len(calls) == 1
    assert calls[0]["host"] == "127.0.0.1"
    assert calls[0]["port"] == 8422
