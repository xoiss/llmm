from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import tomlkit


@dataclass
class Config:
    base_url: str | None = None
    auth_token: str | None = None
    auth_type: str = "Bearer"
    ssl_verify: bool = True
    dialect: str = "OpenAI Chat Completions"
    model: str | None = None
    temperature: float | None = None
    max_completion_tokens: int | None = None


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from environment variables and optional config file.

    Precedence (highest to lowest):
      1. Config file values
      2. Environment variables
      3. Built-in defaults
    """
    ssl_verify_env = os.environ.get("LLMM_PROVIDER_API_SSL_VERIFY", "true").lower()
    cfg = Config(
        base_url=os.environ.get("LLMM_PROVIDER_API_BASE_URL"),
        auth_token=os.environ.get("LLMM_PROVIDER_API_AUTH_TOKEN"),
        auth_type=os.environ.get("LLMM_PROVIDER_API_AUTH_TYPE", "Bearer"),
        ssl_verify=ssl_verify_env not in ("false", "0", "no"),
    )

    if config_path is None:
        config_path = Path.home() / ".llmm" / "config.toml"

    if config_path.exists():
        data = tomlkit.loads(config_path.read_text(encoding="utf-8"))

        provider_api = data.get("provider_api", {})
        if "base_url" in provider_api:
            cfg.base_url = str(provider_api["base_url"])
        if "auth_token" in provider_api:
            cfg.auth_token = str(provider_api["auth_token"])
        if "auth_type" in provider_api:
            cfg.auth_type = str(provider_api["auth_type"])
        if "ssl_verify" in provider_api:
            cfg.ssl_verify = bool(provider_api["ssl_verify"])

        llm_params = data.get("llm_params", {})
        if "dialect" in llm_params:
            cfg.dialect = str(llm_params["dialect"])
        if "model" in llm_params:
            cfg.model = str(llm_params["model"])
        if "temperature" in llm_params:
            cfg.temperature = float(llm_params["temperature"])
        if "max_completion_tokens" in llm_params:
            cfg.max_completion_tokens = int(llm_params["max_completion_tokens"])

    return cfg
