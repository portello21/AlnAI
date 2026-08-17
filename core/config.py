from __future__ import annotations

import os
from pathlib import Path
import streamlit as st


def _setting(name: str, default: str = "") -> str:
    """Read secrets first, then environment, without making either mandatory."""
    try:
        value = st.secrets.get(name, None)
    except Exception:
        value = None
    if value is None:
        value = os.getenv(name, default)
    return str(value or default).strip()


def _bool_setting(name: str, default: bool = False) -> bool:
    raw = _setting(name, "true" if default else "false").casefold()
    return raw in {"1", "true", "yes", "on"}


def _float_setting(name: str, default: float) -> float:
    try:
        return max(1.0, float(_setting(name, str(default))))
    except (TypeError, ValueError):
        return default


class Config:
    """Runtime configuration with optional integrations and an explicit cost guard."""

    DEEPSEEK_API = _setting("DEEPSEEK_API_KEY")
    NVIDIA_API = _setting("NVIDIA_API_KEY")
    OPENAI_API = _setting("OPENAI_API_KEY")
    ANTHROPIC_API = _setting("ANTHROPIC_API_KEY")
    SUPABASE_URL = _setting("SUPABASE_URL")
    SUPABASE_KEY = _setting("SUPABASE_KEY")
    TELEGRAM_TOKEN = _setting("TELEGRAM_BOT_TOKEN")

    PROVIDER_MODE = _setting("ROG_PROVIDER_MODE", "auto").casefold()
    ALLOW_PAID_PROVIDERS = _bool_setting("ROG_ALLOW_PAID", False)

    # NVIDIA NIM is the preferred hosted provider for the family deployment.
    # The model below is the endpoint validated by the project owner. It can be
    # overridden in Streamlit secrets without changing source code.
    NVIDIA_BASE_URL = _setting("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    NVIDIA_MODEL = _setting(
        "NVIDIA_MODEL",
        "nvidia/nemotron-3-nano-30b-a3b",
    )
    NVIDIA_TIMEOUT_SECONDS = _float_setting("NVIDIA_TIMEOUT_SECONDS", 20.0)

    # Streamlit Community Cloud currently checks projects out below /mount/src
    # and exposes STREAMLIT_SHARING_MODE. ROG_CLOUD_MODE is an explicit escape
    # hatch for other hosts and local testing.
    _cloud_override = _setting("ROG_CLOUD_MODE", "auto").casefold()
    IS_CLOUD = (
        _cloud_override in {"1", "true", "yes", "on"}
        if _cloud_override != "auto"
        else bool(os.getenv("STREAMLIT_SHARING_MODE") or str(Path.cwd()).startswith("/mount/src/"))
    )
    SUPABASE_SYNC_MODE = _setting("SUPABASE_SYNC_MODE", "background").casefold()

    @classmethod
    def status(cls) -> dict[str, bool]:
        return {
            "deepseek": bool(cls.DEEPSEEK_API),
            "nvidia": bool(cls.NVIDIA_API and cls.NVIDIA_MODEL),
            "openai": bool(cls.OPENAI_API and cls.ALLOW_PAID_PROVIDERS),
            "anthropic": bool(cls.ANTHROPIC_API and cls.ALLOW_PAID_PROVIDERS),
            "supabase": bool(cls.SUPABASE_URL and cls.SUPABASE_KEY),
            "telegram": bool(cls.TELEGRAM_TOKEN),
        }

    @classmethod
    def validate(cls) -> dict[str, bool]:
        """Return availability instead of crashing on optional integrations."""
        return cls.status()
