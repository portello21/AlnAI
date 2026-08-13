from __future__ import annotations

import streamlit as st


class Config:
    """Runtime configuration. Optional services must never prevent the UI from starting."""

    DEEPSEEK_API = st.secrets.get("DEEPSEEK_API_KEY", "")
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
    TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN", "")

    @classmethod
    def status(cls) -> dict[str, bool]:
        return {
            "deepseek": bool(cls.DEEPSEEK_API),
            "supabase": bool(cls.SUPABASE_URL and cls.SUPABASE_KEY),
            "telegram": bool(cls.TELEGRAM_TOKEN),
        }

    @classmethod
    def validate(cls) -> dict[str, bool]:
        """Return availability instead of crashing on optional integrations.

        Model/provider failures are handled by the runtime router; persistence can
        fall back to SQLite. Authentication passwords are validated separately.
        """
        return cls.status()
