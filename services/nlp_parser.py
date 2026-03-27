import re

class NLPParser:
    def parse_audiometria(self, text: str) -> dict:
        """
        Extrai limiares de audiometria (0.25 a 8 kHz) usando regex rudimentar 
        como prova de conceito.
        """
        db_values = re.findall(r'(\d{1,3})\s?(?:dB|db|Db)', text)
        return {"decibeis_encontrados": db_values}

    def parse_bera(self, text: str) -> dict:
        """
        Extrai latências absolutas das ondas I, III e V
        """
        ondas = {}
        for onda in ['I', 'III', 'V']:
            match = re.search(rf'Onda\s+{onda}[:\s]+([\d.]+)\s?ms', text, re.IGNORECASE)
            if match:
                ondas[onda] = match.group(1)
        return {"latencias_ms": ondas}
        
    def enrich_with_heuristics(self, text: str, exam_type: str) -> dict:
        result = {}
        if exam_type and "audiometria" in exam_type.lower():
            result.update(self.parse_audiometria(text))
        elif exam_type and "bera" in exam_type.lower():
            result.update(self.parse_bera(text))
        
        return result
