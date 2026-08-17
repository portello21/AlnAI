from __future__ import annotations

import base64
from datetime import datetime, timezone
import tempfile
import time

import httpx

from core.config import Config
from core.media_budget import finish_media, reserve_media
from core.supabase_optional import create_privileged_client


IMAGE_MODEL = "gemini-2.5-flash-image"


def generate_image(*, user_id: str, profile: str, prompt: str, aspect_ratio: str = "1:1") -> dict:
    if not Config.ALLOW_PAID_PROVIDERS or not Config.GEMINI_API:
        return {"success": False, "reason": "media_not_configured"}
    reservation = reserve_media(user_id=user_id, profile=profile, media_type="image", prompt=prompt, provider="google", model=IMAGE_MODEL)
    if not reservation.get("success"):
        return reservation
    reservation_id = reservation["id"]
    try:
        response = httpx.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/images/generations",
            headers={"Authorization": f"Bearer {Config.GEMINI_API}", "Content-Type": "application/json"},
            json={"model": IMAGE_MODEL, "prompt": prompt.strip()[:4000], "n": 1, "response_format": "b64_json", "size": {"1:1": "1024x1024", "16:9": "1344x768", "9:16": "768x1344"}.get(aspect_ratio, "1024x1024")},
            timeout=120.0,
        )
        response.raise_for_status()
        payload = response.json()
        encoded = str(((payload.get("data") or [{}])[0]).get("b64_json") or "")
        image = base64.b64decode(encoded, validate=True)
        if not image or len(image) > 15 * 1024 * 1024:
            raise ValueError("invalid_image")
        path = f"{profile.casefold()}/{user_id}/images/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{reservation_id}.png"
        client = create_privileged_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)
        if client is None:
            raise RuntimeError("storage_unavailable")
        client.storage.from_("rog-media").upload(path, image, {"content-type": "image/png", "upsert": "false"})
        finish_media(reservation_id, success=True, actual_cost_usd=0.02, storage_path=path)
        signed = client.storage.from_("rog-media").create_signed_url(path, 900) or {}
        return {"success": True, "url": signed.get("signedURL") or signed.get("signedUrl"), "cost_usd": 0.02, "reservation_id": reservation_id}
    except Exception as exc:
        finish_media(reservation_id, success=False, error_type=type(exc).__name__)
        return {"success": False, "reason": "generation_failed"}


def generate_video(*, user_id: str, profile: str, prompt: str) -> dict:
    if not Config.ALLOW_PAID_PROVIDERS or not Config.GEMINI_API:
        return {"success": False, "reason": "media_not_configured"}
    model = Config.GEMINI_VIDEO_MODEL
    reservation = reserve_media(user_id=user_id, profile=profile, media_type="video", prompt=prompt, provider="google", model=model)
    if not reservation.get("success"):
        return reservation
    reservation_id = reservation["id"]
    try:
        from google import genai
        client = genai.Client(api_key=Config.GEMINI_API)
        operation = client.models.generate_videos(model=model, prompt=prompt.strip()[:4000])
        deadline = time.monotonic() + 540
        while not operation.done and time.monotonic() < deadline:
            time.sleep(10)
            operation = client.operations.get(operation)
        if not operation.done or not operation.response.generated_videos:
            raise TimeoutError("video_generation_timeout")
        generated = operation.response.generated_videos[0]
        client.files.download(file=generated.video)
        with tempfile.NamedTemporaryFile(suffix=".mp4") as temporary:
            generated.video.save(temporary.name)
            temporary.seek(0)
            video = temporary.read()
        if not video or len(video) > 50 * 1024 * 1024:
            raise ValueError("invalid_video")
        path = f"{profile.casefold()}/{user_id}/videos/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{reservation_id}.mp4"
        storage = create_privileged_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)
        if storage is None:
            raise RuntimeError("storage_unavailable")
        storage.storage.from_("rog-media").upload(path, video, {"content-type": "video/mp4", "upsert": "false"})
        finish_media(reservation_id, success=True, actual_cost_usd=0.40, storage_path=path)
        signed = storage.storage.from_("rog-media").create_signed_url(path, 900) or {}
        return {"success": True, "url": signed.get("signedURL") or signed.get("signedUrl"), "cost_usd": 0.40, "reservation_id": reservation_id}
    except Exception as exc:
        finish_media(reservation_id, success=False, error_type=type(exc).__name__)
        return {"success": False, "reason": "generation_failed"}
