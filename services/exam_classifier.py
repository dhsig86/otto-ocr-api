import re

# Tipos de exame suportados, em ordem de especificidade
# IMPORTANTE: subtipos (tomografia_mastoide, tomografia_pescoco) ANTES de tomografia genérica
EXAM_PATTERNS = {
    "audiometria": [
        r"audiometria",
        r"audiograma",
        r"limiar\s+(tonal|vocal)",
        r"\b(?:0[.,]25|0[.,]5|1|2|3|4|6|8)\s?kHz",
        r"\bdB\s?(NA|nHL|SPL)",
        r"\bSRT\b",
        r"\bIPRF\b",
        r"\bIRF\b",
        r"discrimina[çc][ãa]o\s+(de\s+)?fala",
    ],
    "bera": [
        r"\bBERA\b",
        r"potencial\s+evocado\s+auditivo",
        r"onda\s+[IVX]{1,3}",
        r"lat[eê]ncia\s+(absoluta|interpico)",
        r"limiar\s+eletrofisiol[oó]gico",
        r"\bPEATE\b",
    ],
    "videolaringoscopia": [
        r"videolaringoscopia",
        r"nasofibrolaringoscopia",
        r"laringoscopia",
        r"prega[s]?\s+vocal",
        r"laringe",
        r"glote",
        r"paralisia\s+vocal",
        r"n[oó]dulo\s+vocal",
        r"edema\s+de\s+Reinke",
    ],
    "endoscopia_nasal": [
        r"videoendoscopia\s+nasal",
        r"endoscopia\s+nasal",
        r"nasofibrolaringoscopia",
        r"meato\s+(m[eé]dio|inferior|superior)",
        r"corneto",
        r"septo\s+nasal",
        r"polipose\s+nasal",
        r"adenoide|aden[oó]ide",
    ],
    # Subtipos de TC — antes do genérico "tomografia"
    "tomografia_mastoide": [
        r"tomografia\s+(de\s+)?mast[oó]ide",
        r"\bTC\s+(de\s+)?mast[oó]ide",
        r"ossos\s+temporais",
        r"orelha\s+m[eé]dia",
        r"c[eé]lulas?\s+masto[ií]dea",
        r"tegmen\s+tympani",
        r"cadeia\s+ossicular",
        r"colesteatoma",
        r"mast[oó]ide\s+eb[uú]rnea",
    ],
    "tomografia_pescoco": [
        r"tomografia\s+(de\s+)?pesco[çc]o",
        r"\bTC\s+(de\s+)?pesco[çc]o",
        r"espa[çc]o\s+parafar[ií]ngeo",
        r"linfonodomegalia\s+cervical",
        r"gl[aâ]ndula\s+par[oó]tida",
        r"gl[aâ]ndula\s+submandibular",
        r"cisto\s+branquial",
        r"ducto\s+tireoglosso",
        r"cadeia\s+ganglionar\s+cervical",
    ],
    "tomografia": [
        r"tomografia",
        r"\bTC\b",
        r"\bTCFC\b",
        r"seios\s+(da\s+)?face",
        r"mast[oó]ide",
        r"seio\s+(maxilar|etmoidal|esfenoidal|frontal)",
        r"espessamento\s+mucoso",
        r"complexo\s+ostiomeatal",
        r"c[eé]lula\s+de\s+(Haller|Onodi)",
    ],
    "polissonografia": [
        r"polissonografia",
        r"\biah\b",
        r"[ií]ndice\s+de\s+apneia",
        r"apneia.hipopneia",
        r"hipopneia",
        r"arquitetura\s+do\s+sono",
        r"sono\s+rem",
        r"oximetria",
        r"dessatura[çc][ãa]o",
    ],
}

EXAM_LABELS = {
    "audiometria": "Audiometria Tonal/Vocal",
    "bera": "BERA (Potencial Evocado Auditivo)",
    "videolaringoscopia": "Videolaringoscopia / Nasofibrolaringoscopia",
    "endoscopia_nasal": "Videoendoscopia Nasal",
    "tomografia_mastoide": "TC de Mastóide / Ossos Temporais",
    "tomografia_pescoco": "TC de Pescoço",
    "tomografia": "TC de Seios da Face",
    "polissonografia": "Polissonografia",
    "generico": "Exame Otorrinolaringológico (Não Identificado)",
}

class ExamClassifier:
    def classify(self, text: str) -> str:
        """
        Identifica o tipo de exame analisando o texto antes do NLP especializado.
        Retorna a chave do tipo (ex: 'audiometria') ou 'generico'.
        Subtipos de TC são verificados primeiro para maior especificidade.
        """
        text_lower = text.lower()
        scores = {exam: 0 for exam in EXAM_PATTERNS}

        for exam, patterns in EXAM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    scores[exam] += 1

        best_match = max(scores, key=scores.get)
        if scores[best_match] == 0:
            return "generico"
        return best_match

    def label(self, exam_type: str) -> str:
        return EXAM_LABELS.get(exam_type, EXAM_LABELS["generico"])
