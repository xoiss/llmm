from __future__ import annotations

from typing import Union

import requests

from llmm.config import Config
from llmm.dialog import Message


class LLMError(Exception):
    """Base exception for LLM client errors."""


class LLMHTTPError(LLMError):
    """Raised when the HTTP request fails or returns an error status code."""


class LLMAPIError(LLMError):
    """Raised when the API response is malformed or unexpected."""


def complete(
    messages: list[Union[Message, dict]],
    config: Config,
    system_prompt: str | None = None,
) -> str:
    """Send a synchronous chat completion request and return the response text.

    Implements the OpenAI Chat Completions dialect only (v1).
    Dialect-specific logic is isolated here so other dialects can be added later.

    Args:
        messages: Conversation turns. Each element is either a Message dataclass
            (plain-text content) or a raw dict supporting multimodal content arrays.
        config: Effective configuration with provider URL, auth credentials, and
            model parameters.
        system_prompt: Optional system message prepended before user/assistant turns.

    Returns:
        The assistant's response text.

    Raises:
        LLMError: Provider URL or auth token is missing from config.
        LLMHTTPError: HTTP request failed or the server returned a non-2xx status.
        LLMAPIError: The API response could not be parsed.
    """
    if not config.base_url:
        raise LLMError(
            "LLM provider base URL is not configured. "
            "Set LLMM_PROVIDER_API_BASE_URL or add base_url to the config file."
        )
    if not config.auth_token:
        raise LLMError(
            "LLM provider auth token is not configured. "
            "Set LLMM_PROVIDER_API_AUTH_TOKEN or add auth_token to the config file."
        )

    api_messages: list[dict] = []
    if system_prompt:
        api_messages.append({"role": "system", "content": system_prompt})
    for msg in messages:
        if isinstance(msg, Message):
            api_messages.append({"role": msg.role, "content": msg.content})
        else:
            api_messages.append(msg)

    body: dict = {
        "model": config.model,
        "messages": api_messages,
    }
    if config.temperature is not None:
        body["temperature"] = config.temperature
    if config.max_completion_tokens is not None:
        body["max_completion_tokens"] = config.max_completion_tokens

    url = config.base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"{config.auth_type} {config.auth_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=body, headers=headers, timeout=120, verify=config.ssl_verify)
    except requests.RequestException as exc:
        raise LLMHTTPError(f"HTTP request failed: {exc}") from exc

    if not response.ok:
        raise LLMHTTPError(f"HTTP {response.status_code}: {response.text}")

    try:
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMAPIError(
            f"Unexpected API response format: {exc}\nResponse body: {response.text}"
        ) from exc
