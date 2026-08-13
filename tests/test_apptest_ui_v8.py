from streamlit.testing.v1 import AppTest


SCRIPT = r'''
import streamlit as st
from core.ui_v8 import inject_design_system, render_agent_header, render_brand, render_profile, render_welcome

inject_design_system()
with st.sidebar:
    render_brand()
    render_profile("Natan")
render_agent_header("tech")
render_welcome("tech", "Natan")
st.chat_input("Mensagem para o ROG AI…", key="smoke_chat")
'''


def test_v8_ui_renders_without_streamlit_exception():
    at = AppTest.from_string(SCRIPT, default_timeout=5).run()
    assert not at.exception
    assert len(at.chat_input) == 1
    assert at.chat_input[0].placeholder == "Mensagem para o ROG AI…"


def test_v8_ui_mobile_safe_elements_exist_in_rendered_smoke():
    at = AppTest.from_string(SCRIPT, default_timeout=5).run()
    assert not at.exception
    assert len(at.markdown) >= 3
