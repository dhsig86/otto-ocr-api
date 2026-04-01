import re

# Tipos de exame suportados, em ordem de especificidade
EXAM_PATTERNS = {
    "audiometria": [
        r"audiometria",
        r"audiograma",
        r"limiar\s+(tonal|vocal)",
        r"\b(?:0[\.,]25|0[\.,]5|1|2|3|4|6|8)\s?kHz",
        r"\bdB\s?(NA|nHL|SPL)",
    ],
    "bera": [
        r"\bBERA\b",
        r"potencial\s+evocado\s+auditivo",
        r"onda\s+[IVX]{1,3}",
        r"lat[eê]ncia\s+(absoluta|interpico)",
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
    "tomografia": [
        r"tomografia",
        r"\bTC\b",
        r"\bTCFC\b",
        r"seios\s+(da\s+)?face",
        r"mastu00f3ide|mastoide",
        r"seio\s+(maxilar|etmoidal|esfenoidal|frontal)",
        r"espessamento\s+mucoso",
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
    "tomografia": "Tomografia Computadorizada",
    "polissonografia": "Polissonografia",
    "generico": "Exame Otorrinolaringológico (Não Identificado)",
}

class ExamClassifier:
    def classify(self, text: str) -> str:
        """
        Identifica o tipo de exame analisando o texto antes do NLP especializado.
        Retorna a chave do tipo (ex: 'audiometria') ou 'generico'.
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
