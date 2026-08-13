from __future__ import annotations

import streamlit as st

from core.app_shell_v8 import run
from core.config import Config
from core.session_restore_v9 import restore_session_from_request


st.set_page_config(
    page_title="ROG AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

Config.validate()
restore_session_from_request()
run()
