from unittest.mock import Mock, patch

from core.login_v9 import render_login_v9


def test_login_header_is_rendered_as_unindented_html():
    form = Mock()
    form.__enter__ = Mock(return_value=form)
    form.__exit__ = Mock(return_value=False)

    with (
        patch("core.login_v9.st.markdown") as markdown,
        patch("core.login_v9.st.form", return_value=form),
        patch("core.login_v9.st.selectbox", return_value="Allan"),
        patch("core.login_v9.st.text_input", return_value=""),
        patch("core.login_v9.st.form_submit_button", return_value=False),
        patch("core.login_v9.st.caption"),
    ):
        render_login_v9(manager=None)

    html = markdown.call_args.args[0]
    assert html.startswith("<style>")
    assert '\n<div class="v9-login">' in html
    assert markdown.call_args.kwargs["unsafe_allow_html"] is True
