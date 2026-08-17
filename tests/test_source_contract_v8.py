from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8-sig")
SHELL = (ROOT / "core" / "app_shell_v8.py").read_text(encoding="utf-8-sig")
UI = (ROOT / "core" / "ui_v8.py").read_text(encoding="utf-8-sig")
ACTIVE = APP + "\n" + SHELL


def test_v8_design_system_exists():
    assert "FAMILY INTELLIGENCE" in UI
    assert "Natan" in UI
    assert "Tainan" in UI
    assert "rog-welcome" in UI


def test_no_fake_family_names_in_active_app():
    for forbidden in ("Irmão 1", "Irmão 2", "Irmao 1", "Irmao 2", "Brother 1", "Brother 2"):
        assert forbidden not in ACTIVE


def test_chat_has_runtime_pipeline_and_safe_fallback():
    assert "target=execute_agent" in SHELL
    assert "start_response_job(" in SHELL
    assert "falha temporária" in SHELL.lower()
    assert "busy" in SHELL


def test_profile_namespace_guards_are_wired():
    assert "allowed_namespaces(" in SHELL
    assert "write_namespace(" in SHELL


def test_no_invalid_component_callback_regression():
    assert "on_change=lambda: None" not in ACTIVE


def test_app_is_only_a_bootstrap_shell():
    assert "import core.app_shell_v8 as app_shell" in APP
    assert "app_shell.render_login = render_login_v9" in APP
    assert "app_shell.run()" in APP
    assert len(APP.splitlines()) < 40


def test_collapsed_sidebar_has_current_streamlit_reopen_control():
    assert 'data-testid="stSidebarCollapsed"' in UI
    assert 'initial_sidebar_state="auto"' in APP


def test_permanent_navigation_does_not_depend_on_sidebar():
    assert 'key="rog_top_nav"' in SHELL
    assert "render_navigation_bar(profile, agent_id, conversations, manager)" in SHELL
    for action in ("Assistente", "Memórias", "Documentos", "Sistema", "Nova conversa", "Trocar perfil", "Sair"):
        assert action in SHELL


def test_original_brand_assets_exist():
    assert (ROOT / "assets" / "rog-ai-mark.svg").is_file()
    assert (ROOT / "assets" / "rog-ai-core.webp").is_file()
    assert "rog-ai-core.webp" in UI


def test_fluid_chat_visual_contract():
    assert "Fluid chat shell" in UI
    assert 'avatar = ":material/person:"' in SHELL
    assert 'avatar=":material/auto_awesome:"' in SHELL
    assert "rog-inline-status" in UI
    assert 'meta = " · ".join' not in SHELL


def test_sidebar_uses_clean_text_labels():
    assert 'st.button(meta[1], key=f"v8_nav_{aid}"' in SHELL
    assert '("chat", "Conversa")' in SHELL
    assert 'initial_sidebar_state="auto"' in APP


def test_top_menu_uses_persistent_panel_instead_of_fixed_bar_popover():
    assert 'st.button(label, key="v8_top_menu_button"' in SHELL
    assert 'key="rog_top_menu_panel"' in SHELL
    assert 'with st.popover("Menu"' not in SHELL
    assert "st.session_state.v8_top_menu_open = False" in SHELL
