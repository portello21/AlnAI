from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "frontend" / "chat_input" / "src" / "ChatInput.tsx").read_text(encoding="utf-8-sig")
APP = (ROOT / "app.py").read_text(encoding="utf-8-sig")


def test_chat_emits_supported_events():
    assert 'type: "send" | "audio"' in CHAT
    assert "Streamlit.setComponentValue(event)" in CHAT
    assert 'type: "send"' in CHAT
    assert 'type: "audio"' in CHAT


def test_chat_has_attachment_limits():
    assert "MAX_FILE_SIZE = 20 * 1024 * 1024" in CHAT
    assert "MAX_FILES = 10" in CHAT


def test_chat_has_keyboard_send_and_composition_guard():
    assert 'event.key === "Enter"' in CHAT
    assert "!event.shiftKey" in CHAT
    assert "!event.nativeEvent.isComposing" in CHAT


def test_python_uses_agent_runtime():
    assert "from core.agent_runtime import execute_agent" in APP
    assert "execute_agent(" in APP


def test_invalid_components_v2_generic_callback_is_absent():
    assert "on_change=lambda: None" not in APP
