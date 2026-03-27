import io
import pytesseract
from PIL import Image, ImageEnhance
from pdf2image import convert_from_bytes

class OCRBaseEngine:
    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Aplica escala de cinza, aumento de contraste e binarização simples
        para melhorar a precisão do OCR em laudos.
        """
        img = image.convert('L')
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        img = img.point(lambda p: 255 if p > 128 else 0)
        return img

    def extract_from_image_bytes(self, image_bytes: bytes) -> str:
        """
        Extrai texto de uma imagem (JPEG/PNG).
        """
        image = Image.open(io.BytesIO(image_bytes))
        image = self.preprocess_image(image)
        # lang='por' requer o pacote tesseract-ocr-por instalado
        text = pytesseract.image_to_string(image, lang='por')
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
