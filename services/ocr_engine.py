import io
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pdf2image import convert_from_bytes

MIN_TEXT_CHARS = 80   # Mínimo de caracteres para considerar OCR válido
_TESS_CONFIG = '--psm 3 --oem 1'


class OCRBaseEngine:

    @staticmethod
    def _auto_orient(img: Image.Image) -> Image.Image:
        """Corrige rotação EXIF de fotos de celular e faz upscale se muito pequena."""
        # 1. Auto-rotation via EXIF (celulares gravam orientação nos metadados)
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        # 2. Upscale se resolução baixa (<1500px no maior eixo) — melhora OCR
        max_dim = max(img.size)
        if max_dim < 1500:
            scale = 1500 / max_dim
            new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
            img = img.resize(new_size, Image.LANCZOS)
        return img

    def _ocr(self, img: Image.Image, dpi: str = "150") -> str:
        """Roda Tesseract com hint de DPI, retorna string."""
        config = f"{_TESS_CONFIG} --dpi {dpi}"
        return pytesseract.image_to_string(img, lang="por", config=config)

    def _strategy_original(self, raw: bytes) -> str:
        """Estratégia 1: imagem original sem processamento + DPI 200.
        Melhor para screenshots e documentos digitais de boa qualidade."""
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        img = self._auto_orient(img)
        return self._ocr(img, dpi="200")

    def _strategy_enhanced(self, raw: bytes) -> str:
        """Estratégia 2: escala de cinza + contraste suave.
        Bom para PDFs escaneados e documentos com pouco contraste."""
        img = Image.open(io.BytesIO(raw))
        img = self._auto_orient(img).convert("L")
        img = ImageEnhance.Contrast(img).enhance(1.8)
        img = img.filter(ImageFilter.SHARPEN)
        return self._ocr(img, dpi="200")

    def _strategy_binarize(self, raw: bytes) -> str:
        """Estratégia 3: binarização agressiva + super-nitidez.
        Melhor para fotos de celular com fundo texturizado ou baixa iluminação."""
        img = Image.open(io.BytesIO(raw))
        img = self._auto_orient(img).convert("L")
        img = img.filter(ImageFilter.SHARPEN)
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Contrast(img).enhance(2.5)
        img = img.point(lambda p: 255 if p > 128 else 0)
        return self._ocr(img, dpi="150")

    def _strategy_sparse(self, raw: bytes) -> str:
        """Estratégia 4: PSM 11 (Sparse text).
        Melhor para resgatar texto limpo em formulários com tabelas ou grades densas (ex: audiometrias),
        onde o Tesseract tentaria ler as colunas da grade e gerar alucinações."""
        img = Image.open(io.BytesIO(raw))
        img = self._auto_orient(img).convert("L")
        img = ImageEnhance.Contrast(img).enhance(1.8)
        config = "--psm 11 --oem 1 --dpi 150"
        return pytesseract.image_to_string(img, lang="por", config=config)

    def extract_from_image_bytes(self, image_bytes: bytes) -> str:
        """
        Extrai texto de imagem (JPEG/PNG) com 4 estratégias em cascata.
        Retorna o resultado com mais caracteres.
        """
        results = []
        for strategy in (self._strategy_original, self._strategy_enhanced, self._strategy_binarize, self._strategy_sparse):
            try:
                text = strategy(image_bytes)
                results.append(text.strip())
            except Exception:
                results.append("")

        # Escolhe o resultado com mais conteúdo
        best = max(results, key=len)
        return best

    def extract_from_pdf_bytes(self, pdf_bytes: bytes) -> str:
        """
        Converte PDF escaneado em imagens e roda OCR com estratégia enhanced.
        """
        try:
            images = convert_from_bytes(pdf_bytes, dpi=200)
            full_text = ""
            for img in images:
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                full_text += self.extract_from_image_bytes(buf.getvalue()) + "\n"
            return full_text
        except Exception as e:
            return f"Erro no OCR (verifique se poppler está instalado): {str(e)}"
