import io
from PyPDF2 import PdfReader

class PdfExtractor:
    def process(self, file_bytes: bytes, filename: str) -> tuple[str, bool]:
        """
        Analisa se o PDF é raster (imagem) ou text-based e realiza extração primária.
        Retorna (texto_extraido, is_raster)
        """
        if not filename.lower().endswith(".pdf"):
            return ("", True)
        
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            
            # Se o PDF tem menos de 50 caracteres (excluindo espaços), provavelmente é scan
            if len(text.strip()) < 50:
                return ("", True)
                
            return (text, False)
        except Exception as e:
            # Em caso de erro (corrompido ou criptografado), assumimos raster para tentar o OCR
            return ("", True)
