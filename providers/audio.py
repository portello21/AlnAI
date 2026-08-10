import os
import whisper
import tempfile

# Carrega o modelo base localmente (otimizado para velocidade e precisão)
model = whisper.load_model("base")

def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    """
    Transcreve áudio gravado via navegador usando Whisper local.
    """
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
            
        result = model.transcribe(tmp_path, language="pt")
        os.unlink(tmp_path)
        return result.get("text", "").strip()
    except Exception as e:
        return f"Erro na transcrição de áudio: {str(e)}"