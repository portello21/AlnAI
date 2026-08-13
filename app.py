from __future__ import annotations

import streamlit as st

from core.app_shell_v8 import run
from core.config import Config


st.set_page_config(
    page_title="ROG AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

Config.validate()
run()
