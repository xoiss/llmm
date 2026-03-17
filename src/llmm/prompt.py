from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

import jinja2
import tomlkit

from llmm.config import Config

_IMAGE_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

SUPPORTED_TEXT_EXTENSIONS: frozenset[str] = frozenset({".txt", ".md"})
SUPPORTED_IMAGE_EXTENSIONS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg"})


@dataclass
class ImageData:
    """Wraps binary image data and exposes a data URI for use in multimodal requests."""

    _mime: str
    _data: bytes

    def __init__(self, path: Path) -> None:
        self._mime = _IMAGE_MIME[path.suffix.lower()]
        self._data = path.read_bytes()

    @property
    def uri(self) -> str:
        """Return a ready-to-use data URI: ``data:<mime>;base64,<b64>``."""
        b64 = base64.b64encode(self._data).decode("ascii")
        return f"data:{self._mime};base64,{b64}"


@dataclass
class ParsedPrompt:
    system: str | None
    user_template: str | None
    user_role: str
    assistant_role: str
    task: str | None
    config_overrides: dict  # optional keys: "provider_api", "llm_params"


def parse_prompt(path: Path) -> ParsedPrompt:
    """Read and parse a prompt.toml file."""
    data = tomlkit.loads(path.read_text(encoding="utf-8"))

    prompt = data.get("prompt", {})
    system: str | None = prompt.get("system") or None
    user_template: str | None = prompt.get("user") or None

    role_names = data.get("role_names", {})
    user_role = str(role_names.get("user", "user"))
    assistant_role = str(role_names.get("assistant", "assistant"))

    chat = data.get("chat", {})
    task: str | None = chat.get("task") or None

    config_overrides: dict = {}
    if "provider_api" in data:
        config_overrides["provider_api"] = dict(data["provider_api"])
    if "llm_params" in data:
        config_overrides["llm_params"] = dict(data["llm_params"])

    return ParsedPrompt(
        system=system,
        user_template=user_template,
        user_role=user_role,
        assistant_role=assistant_role,
        task=task,
        config_overrides=config_overrides,
    )


def apply_overrides(config: Config, overrides: dict) -> Config:
    """Return a new Config with prompt-file section overrides applied on top of *config*.

    Prompt-file values take the highest precedence (above the global config file and
    environment variables).
    """
    import copy

    cfg = copy.copy(config)

    provider_api = overrides.get("provider_api", {})
    if "base_url" in provider_api:
        cfg.base_url = str(provider_api["base_url"])
    if "auth_token" in provider_api:
        cfg.auth_token = str(provider_api["auth_token"])
    if "auth_type" in provider_api:
        cfg.auth_type = str(provider_api["auth_type"])

    llm_params = overrides.get("llm_params", {})
    if "dialect" in llm_params:
        cfg.dialect = str(llm_params["dialect"])
    if "model" in llm_params:
        cfg.model = str(llm_params["model"])
    if "temperature" in llm_params:
        cfg.temperature = float(llm_params["temperature"])
    if "max_completion_tokens" in llm_params:
        cfg.max_completion_tokens = int(llm_params["max_completion_tokens"])

    return cfg


def render(
    user_template: str | None,
    text: str | None = None,
    image: ImageData | None = None,
) -> str | list[dict]:
    """Render the user message content from a template and document input.

    Args:
        user_template: Jinja2 template string with an optional ``{{ document }}``
            placeholder, or None.
        text: Plain-text document content (mutually exclusive with *image*).
        image: Binary image input (mutually exclusive with *text*).

    Returns:
        A plain string for text input; a multimodal content array for image input.
    """
    if image is not None:
        if user_template is not None:
            # Render with an empty document to remove {{ document }}, then trim
            remaining = jinja2.Template(user_template).render(document="").strip()
        else:
            remaining = ""

        parts: list[dict] = []
        if remaining:
            parts.append({"type": "text", "text": remaining})
        parts.append({"type": "image_url", "image_url": {"url": image.uri}})
        return parts

    # Text or stdin input
    if user_template is None:
        return text or ""
    return jinja2.Template(user_template).render(document=text or "")
