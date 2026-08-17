from types import SimpleNamespace

import core.media_budget as budget
import providers.gemini_media as media


def test_media_cost_estimates_respect_total_budget():
    assert budget.MEDIA_ESTIMATES == {"image": 0.02, "video": 0.40}
    assert budget.MEDIA_ESTIMATES["video"] * 12 + budget.MEDIA_ESTIMATES["image"] * 100 < 10


def test_image_generation_is_closed_when_paid_media_is_not_configured(monkeypatch):
    monkeypatch.setattr(media.Config, "ALLOW_PAID_PROVIDERS", False)
    monkeypatch.setattr(media.Config, "GEMINI_API", "")
    monkeypatch.setattr(media, "reserve_media", lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not reserve")))
    assert media.generate_image(user_id="user", profile="allan", prompt="safe image")["reason"] == "media_not_configured"


def test_budget_admin_requires_revalidated_admin(monkeypatch):
    import core.supabase_auth as auth
    monkeypatch.setattr(auth, "validate_access_token", lambda token: None)
    monkeypatch.setattr(budget, "_client", lambda: SimpleNamespace())
    assert not budget.admin_update_budget("invalid", enabled=True, daily_limit_usd=1, image_limit_usd=2, video_limit_usd=5)
