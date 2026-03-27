import io
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from pdf2image import convert_from_bytes

MIN_TEXT_CHARS = 80  # Mínimo de caracteres para considerar OCR válido

class OCRBaseEngine:
    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Pré-processa imagens para melhorar a taxa de acerto do OCR em fotos de celular:
        - Converte para escala de cinza
        - Aplica nitidez (Sharpness) para compensar foco suave
        - Aumenta o contraste
        - Binariza com threshold adaptativo
        """
        img = image.convert('L')
        # Nitidez: melhora bordas de letras fotografadas
        img = img.filter(ImageFilter.SHARPEN)
        img = img.filter(ImageFilter.SHARPEN)
        # Contraste
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.5)
        # Binarização
        img = img.point(lambda p: 255 if p > 140 else 0)
        return img

    def extract_from_image_bytes(self, image_bytes: bytes) -> str:
        """
        Extrai texto de uma imagem (JPEG/PNG).
        """
        image = Image.open(io.BytesIO(image_bytes))
        image = self.preprocess_image(image)
        text = pytesseract.image_to_string(image, lang='por')
        if len(text.strip()) < MIN_TEXT_CHARS:
            # Tenta sem binarização (pode ajudar em fotos com fundo muito escuro)
            image_raw = Image.open(io.BytesIO(image_bytes)).convert('L')
            enhancer = ImageEnhance.Contrast(image_raw)
            image_raw = enhancer.enhance(1.5)
            text_alt = pytesseract.image_to_string(image_raw, lang='por')
            if len(text_alt.strip()) > len(text.strip()):
                text = text_alt
        return text

    def extract_from_pdf_bytes(self, pdf_bytes: bytes) -> str:
        """
        Converte PDF escaneado em imagens e roda o OCR em cada página.
        Nota: pdf2image precisa do 'poppler' instalado no SO.
        """
        try:
            images = convert_from_bytes(pdf_bytes)
            full_text = ""
            for img in images:
                processed_img = self.preprocess_image(img)
                text = pytesseract.image_to_string(processed_img, lang='por')
                full_text += text + "\n"
            return full_text
        except Exception as e:
            return f"Erro no OCR (verifique se poppler está instalado): {str(e)}"
