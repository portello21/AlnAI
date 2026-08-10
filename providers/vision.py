import os
import io
import json
from PIL import Image
from providers.ocr import extract_text_tesseract

def analyze_image(image_bytes: bytes, prompt: str = "") -> dict:
    """
    Motor de extração local com heurísticas para faturas, recibos e documentos em CAD/BRL.
    """
    try:
        extracted_text = extract_text_tesseract(image_bytes)
        
        # Heurísticas de extração de entidades
        import re
        total_match = re.search(r'(?:total|cad|[\$])\s*([\d\.,]+)', extracted_text, re.IGNORECASE)
        total_val = float(total_match.group(1).replace(',', '.')) if total_match else 0.00
        
        currency = "CAD" if "cad" in extracted_text.lower() or "$" in extracted_text else "BRL"
        
        return {
            "document_type": "invoice_or_receipt",
            "language": "por+eng",
            "summary": "Extração estruturada realizada via Tesseract OCR.",
            "text": extracted_text,
            "entities": {
                "merchant": "Detectado via OCR",
                "date": None,
                "currency": currency,
                "total": total_val
            }
        }
    except Exception as e:
        return {
            "document_type": "error",
            "language": "unknown",
            "summary": f"Erro no processamento local: {str(e)}",
            "text": "",
            "entities": {}
        }