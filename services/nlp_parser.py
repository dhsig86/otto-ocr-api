import re

class NLPParser:
    def parse_audiometria(self, text: str) -> dict:
        """
        Extrai dados audiométricos: limiares (dB), SRT, IPRF, tipo de perda.
        """
        db_values = re.findall(r'(\d{1,3})\s?(?:dB|db|Db)', text)
        
        # Extrair tipo de perda
        loss_type = None
        text_lower = text.lower()
        if re.search(r'perda\s+(auditiva\s+)?mista|hipoacusia\s+mista', text_lower):
            loss_type = "mista"
        elif re.search(r'perda\s+(auditiva\s+)?condutiva|hipoacusia\s+condutiva', text_lower):
            loss_type = "condutiva"
        elif re.search(r'perda\s+(auditiva\s+)?(?:sensorioneural|neurossensorial|sensório-neural)', text_lower):
            loss_type = "neurossensorial"
        elif re.search(r'audi[çc][ãa]o\s+normal|limiares\s+normais', text_lower):
            loss_type = "normal"
        
        # Extrair SRT
        srt = None
        srt_match = re.search(r'SRT[:\s]+(\d{1,3})\s?dB', text, re.IGNORECASE)
        if srt_match:
            srt = int(srt_match.group(1))
        
        # Extrair IPRF/IRF
        iprf = None
        iprf_match = re.search(r'(?:IPRF|IRF)[:\s]+(\d{1,3})\s?%', text, re.IGNORECASE)
        if iprf_match:
            iprf = int(iprf_match.group(1))
        
        result = {"decibeis_encontrados": db_values}
        if loss_type:
            result["tipo_perda"] = loss_type
        if srt is not None:
            result["srt_db"] = srt
        if iprf is not None:
            result["iprf_pct"] = iprf
        return result

    def parse_bera(self, text: str) -> dict:
        """
        Extrai latências absolutas das ondas I, III e V e limiar eletrofisiológico.
        """
        ondas = {}
        for onda in ['I', 'III', 'V']:
            match = re.search(rf'Onda\s+{onda}[:\s]+([\d.]+)\s?ms', text, re.IGNORECASE)
            if match:
                ondas[onda] = match.group(1)
        
        # Limiar eletrofisiológico
        limiar = None
        limiar_match = re.search(r'limiar\s+(?:eletrofisiol[oó]gico)?[:\s]+(\d{1,3})\s?dB', text, re.IGNORECASE)
        if limiar_match:
            limiar = int(limiar_match.group(1))
        
        result = {"latencias_ms": ondas}
        if limiar is not None:
            result["limiar_eletrofisiologico_db"] = limiar
        return result

    def parse_tomografia(self, text: str) -> dict:
        """
        Extrai achados relevantes de TC de seios da face.
        """
        text_lower = text.lower()
        achados = []
        
        # Seios afetados
        seios = []
        for seio in ["maxilar", "etmoidal", "esfenoidal", "frontal"]:
            if seio in text_lower:
                seios.append(seio)
        
        # Lateralidade
        lateralidade = None
        if re.search(r'bilateral|bilateralmente', text_lower):
            lateralidade = "bilateral"
        elif re.search(r'\bdireito\b|\bdireita\b|à direita', text_lower):
            lateralidade = "direito"
        elif re.search(r'\besquerdo\b|\besquerda\b|à esquerda', text_lower):
            lateralidade = "esquerdo"
        
        # Achados-chave
        patterns = [
            (r'velamento\s+(total|parcial|completo)', "velamento"),
            (r'espessamento\s+(mucoso|da mucosa|mucoperiósteo)', "espessamento_mucoso"),
            (r'n[ií]vel\s+(l[ií]quido|hidro[- ]?a[eé]reo)', "nivel_liquido"),
            (r'desvio\s+(do\s+)?septo|septo\s+(nasal\s+)?desviado', "desvio_septal"),
            (r'concha\s+bolhosa|corneto\s+bolhoso', "concha_bolhosa"),
            (r'cisto\s+de\s+reten[çc][ãa]o', "cisto_retencao"),
            (r'p[oó]lipo', "polipo"),
            (r'obliteração\s+d[oe]s?\s+[oó]stio', "obliteracao_ostio"),
            (r'célula\s+de\s+Haller', "celula_haller"),
            (r'célula\s+de\s+Onodi', "celula_onodi"),
        ]
        for pattern, label in patterns:
            if re.search(pattern, text_lower):
                achados.append(label)
        
        result = {}
        if seios:
            result["seios_afetados"] = seios
        if lateralidade:
            result["lateralidade"] = lateralidade
        if achados:
            result["achados"] = achados
        return result

    def parse_tomografia_mastoide(self, text: str) -> dict:
        """
        Extrai achados relevantes de TC de mastóide/ossos temporais.
        """
        text_lower = text.lower()
        achados = []
        
        patterns = [
            (r'velamento\s+(de\s+)?c[eé]lulas?\s+masto[ií]dea', "velamento_mastoideo"),
            (r'colesteatoma|massa\s+de\s+partes\s+moles', "colesteatoma"),
            (r'eros[ãa]o\s+(ossicular|do\s+tegmen|da\s+bigorna|do\s+martelo)', "erosao_ossicular"),
            (r'mast[oó]ide\s+eb[uú]rnea|mastoide\s+esclero', "mastoide_eburnea"),
            (r'deiscência\s+do\s+(canal\s+de\s+)?[Ff]al[oó]pio|nervo\s+facial\s+exposto', "deiscencia_facial"),
            (r'f[ií]stula\s+(do\s+)?canal\s+semicircular', "fistula_labirintica"),
            (r'perfura[çc][ãa]o\s+timp[aâ]nica|membrana\s+timpânica\s+retra[ií]da', "alteracao_timpanica"),
            (r'otite\s+média\s+cr[oô]nica|OMC', "omc"),
        ]
        for pattern, label in patterns:
            if re.search(pattern, text_lower):
                achados.append(label)
        
        # Lateralidade
        lateralidade = None
        if re.search(r'bilateral|bilateralmente', text_lower):
            lateralidade = "bilateral"
        elif re.search(r'\bdireito\b|\bdireita\b|orelha direita|OD\b', text_lower):
            lateralidade = "direito"
        elif re.search(r'\besquerdo\b|\besquerda\b|orelha esquerda|OE\b', text_lower):
            lateralidade = "esquerdo"
        
        result = {}
        if achados:
            result["achados"] = achados
        if lateralidade:
            result["lateralidade"] = lateralidade
        return result

    def parse_tomografia_pescoco(self, text: str) -> dict:
        """
        Extrai achados relevantes de TC de pescoço.
        """
        text_lower = text.lower()
        achados = []
        
        patterns = [
            (r'linfonodomegalia|linfonodo\s+aumentado|adenopatia', "linfonodomegalia"),
            (r'necrose\s+central|centro\s+necr[oó]tico', "necrose_central"),
            (r'n[oó]dulo\s+(na\s+)?tire[oó]ide|massa\s+(na\s+)?tire[oó]ide', "nodulo_tireoide"),
            (r'massa\s+(na\s+)?par[oó]tida|tumor\s+de\s+par[oó]tida', "massa_parotida"),
            (r'cisto\s+branquial|cisto\s+de\s+fenda\s+branquial', "cisto_branquial"),
            (r'cisto\s+(do\s+)?ducto\s+tireoglosso', "cisto_tireoglosso"),
            (r'espa[çc]o\s+parafar[ií]ngeo', "invasao_parafaringeo"),
        ]
        for pattern, label in patterns:
            if re.search(pattern, text_lower):
                achados.append(label)
        
        # Níveis cervicais
        niveis = re.findall(r'n[ií]vel\s+([IViv]{1,4}[abAB]?)', text)
        
        result = {}
        if achados:
            result["achados"] = achados
        if niveis:
            result["niveis_cervicais"] = [n.upper() for n in niveis]
        return result

    def enrich_with_heuristics(self, text: str, exam_type: str) -> dict:
        result = {}
        if not exam_type:
            return result
            
        exam_lower = exam_type.lower()
        if "audiometria" in exam_lower:
            result.update(self.parse_audiometria(text))
        elif "bera" in exam_lower:
            result.update(self.parse_bera(text))
        elif exam_lower == "tomografia_mastoide":
            result.update(self.parse_tomografia_mastoide(text))
        elif exam_lower == "tomografia_pescoco":
            result.update(self.parse_tomografia_pescoco(text))
        elif "tomografia" in exam_lower:
            result.update(self.parse_tomografia(text))
        
        return result
