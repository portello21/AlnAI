from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8-sig")
SHELL = (ROOT / "core" / "app_shell_v8.py").read_text(encoding="utf-8-sig")


def test_chat_uses_streamlit_native_submission_pipeline():
    assert "st.chat_input(" in SHELL
    assert "accept_file=\"multiple\"" in SHELL
    assert 'accept_audio=audio_ready' in SHELL
    assert 'find_spec("whisper")' in SHELL
    assert "process_submission(" in SHELL


def test_chat_has_attachment_limits():
    assert "MAX_FILE_BYTES = 20 * 1024 * 1024" in SHELL
    assert "for uploaded in files[:10]" in SHELL


def test_python_uses_agent_runtime():
    assert "from core.agent_runtime import AGENTS as RUNTIME_AGENTS, execute_agent" in SHELL
    assert "execute_agent(" in SHELL


def test_invalid_components_v2_generic_callback_is_absent():
    assert "on_change=lambda: None" not in APP + SHELL


def test_quick_actions_use_the_real_submission_pipeline():
    assert "QUICK_ACTIONS" in SHELL
    assert "process_submission(profile, agent_id, conversations, prompt)" in SHELL
