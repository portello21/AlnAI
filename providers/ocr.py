import os
from PIL import Image
import pytesseract

# Define o caminho padrão do executável no Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text_tesseract(image_path_or_bytes) -> str:
    try:
        if isinstance(image_path_or_bytes, bytes):
            import io
            image = Image.open(io.BytesIO(image_path_or_bytes))
        else:
            image = Image.open(image_path_or_bytes)
            
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(image, lang='por+eng', config=custom_config)
        return text.strip()
    except Exception as e:
        return f"Erro no OCR local (Tesseract): {str(e)}"