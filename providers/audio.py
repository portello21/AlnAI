from __future__ import annotations

import logging
import os
import tempfile
from functools import lru_cache

LOGGER = logging.getLogger("rog.audio")


@lru_cache(maxsize=1)
def _model():
    """Load Whisper lazily so login/UI startup does not pay the model cost."""
    import whisper
    return whisper.load_model("base")


def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    if not audio_bytes:
        return ""

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        result = _model().transcribe(tmp_path, language="pt")
        return str(result.get("text", "") or "").strip()
    except Exception as exc:
        LOGGER.warning("audio transcription failed: %s", type(exc).__name__)
        return ""
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
