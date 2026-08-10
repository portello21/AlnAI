import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Optional

from providers.ocr import extract_text_tesseract


TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".log",
    ".py",
    ".ps1",
    ".yaml",
    ".yml",
    ".toml",
}

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}


def calculate_file_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def decode_text_bytes(file_bytes: bytes) -> str:
    encodings = (
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1",
    )

    for encoding in encodings:
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    return file_bytes.decode(
        "utf-8",
        errors="replace",
    )


def extract_csv_text(file_bytes: bytes) -> str:
    raw = decode_text_bytes(file_bytes)

    try:
        reader = csv.reader(io.StringIO(raw))
        rows = []

        for row in reader:
            rows.append(" | ".join(str(cell) for cell in row))

        return "\n".join(rows).strip()

    except Exception:
        return raw.strip()


def extract_json_text(file_bytes: bytes) -> str:
    raw = decode_text_bytes(file_bytes)

    try:
        data = json.loads(raw)

        return json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )

    except Exception:
        return raw.strip()


def extract_document_text(
    file_bytes: bytes,
    filename: str,
    mime_type: Optional[str] = None,
) -> dict:

    filename = filename or "arquivo"
    extension = Path(filename).suffix.lower()
    mime_type = (mime_type or "").lower()

    result = {
        "filename": filename,
        "extension": extension,
        "mime_type": mime_type,
        "file_hash": calculate_file_sha256(file_bytes),
        "text": "",
        "method": None,
        "success": False,
        "error": None,
    }

    try:
        if extension in TEXT_EXTENSIONS:
            result["text"] = decode_text_bytes(file_bytes).strip()
            result["method"] = "text"

        elif extension == ".csv":
            result["text"] = extract_csv_text(file_bytes)
            result["method"] = "csv"

        elif extension == ".json":
            result["text"] = extract_json_text(file_bytes)
            result["method"] = "json"

        elif extension in IMAGE_EXTENSIONS or mime_type.startswith("image/"):
            ocr_text = extract_text_tesseract(file_bytes)

            if ocr_text.lower().startswith("erro no ocr"):
                raise RuntimeError(ocr_text)

            result["text"] = ocr_text.strip()
            result["method"] = "tesseract"

        elif extension == ".pdf":
            result["error"] = (
                "PDF detectado. Extracao PDF sera habilitada "
                "na proxima etapa."
            )
            return result

        elif extension == ".docx":
            result["error"] = (
                "DOCX detectado. Extracao DOCX sera habilitada "
                "na proxima etapa."
            )
            return result

        else:
            result["error"] = (
                f"Formato ainda nao suportado: "
                f"{extension or mime_type or 'desconhecido'}"
            )
            return result

        if not result["text"]:
            result["error"] = "Nenhum texto foi extraido."
            return result

        result["success"] = True
        return result

    except Exception as exc:
        result["error"] = str(exc)
        return result