from __future__ import annotations

import streamlit as st

import core.app_shell_v8 as app_shell
from core.config import Config
from core.login_v9 import render_login_v9
from core.session_restore_v9 import restore_session_from_request


st.set_page_config(
    page_title="ROG AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

Config.validate()
restore_session_from_request()

# V9 login fixes a race where the cookie-writing component was immediately
# destroyed by st.rerun(), causing authenticated users to be logged out on F5.
app_shell.render_login = render_login_v9
app_shell.run()
