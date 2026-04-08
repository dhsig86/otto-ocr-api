import re
import uuid
import hashlib

# Padrões de data aceitos nos laudos (DD/MM/AAAA, DD-MM-AAAA, AAAA-MM-DD)
_DATE_PATTERNS = [
    # "Data: 06/01/2021" | "Data do Exame: 06/01/2021" | "Emissão: ..." com possíveis caracteres lixo do OCR
    r'(?:data[\w\s]*?|emiss[aã]o)[\s:]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
    # "Realizado em: 06/01/2021"
    r'(?:realizado\s+em|executado\s+em|data\s+de\s+realiza[cç][aã]o)[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
    # Data solta no cabeçalho: "06/01/2021" ou "2021-01-06"
    r'\b(\d{4}[-\/]\d{2}[-\/]\d{2})\b',
    r'\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})\b',
]

def extract_exam_date(header_raw: str, body_text: str = "") -> str:
    """
    Extrai a data de execução do exame a partir do cabeçalho bruto ou do corpo do texto.
    Chamada ANTES do descarte LGPD — data de exame é metadado clínico, não dado pessoal.
    Retorna string ISO 'AAAA-MM-DD' ou string original se não conseguir normalizar.
    Retorna "" se nenhuma data for encontrada.
    """
    search_text = header_raw + "\n" + body_text[:800]

    for pattern in _DATE_PATTERNS:
        m = re.search(pattern, search_text, re.IGNORECASE)
        if m:
            raw_date = m.group(1).strip()
            # Normalizar para AAAA-MM-DD
            return _normalize_date(raw_date)

    return ""

def _normalize_date(raw: str) -> str:
    """Tenta converter a data capturada para AAAA-MM-DD."""
    sep_match = re.match(r'(\d{1,4})([\/\-\.])(\d{1,2})\2(\d{2,4})', raw)
    if not sep_match:
        return raw  # retorna como veio
    a, _, b, c = sep_match.group(1), sep_match.group(2), sep_match.group(3), sep_match.group(4)
    # AAAA-MM-DD
    if len(a) == 4:
        return f"{a}-{b.zfill(2)}-{c.zfill(2)}"
    # DD/MM/AAAA → AAAA-MM-DD
    year = c if len(c) == 4 else f"20{c}"
    return f"{year}-{b.zfill(2)}-{a.zfill(2)}"


def generate_patient_token(raw_header_text: str = "") -> str:
    """
    Gera um token anônimo e auditável para o paciente.
    
    - O token é único por sessão (UUID v4).
    - Pode opcionalmente ser derivado de um hash do cabeçalho bruto (nome + data)
      para gerar sempre o mesmo token para o mesmo paciente, sem armazenar o nome.
    - Nunca retorna dados pessoais.
    """
    if raw_header_text and len(raw_header_text) > 3:
        # Hash determinístico a partir do texto do cabeçalho (sem armaznar o dado bruto)
        h = hashlib.sha256(raw_header_text.encode("utf-8")).hexdigest()[:12]
        return f"pt-{h}"
    return f"pt-{uuid.uuid4().hex[:12]}"

def extract_and_strip_header(raw_text: str) -> tuple[str, str]:
    """
    Extrai e remove o bloco de cabeçalho (dados do paciente) do texto do laudo.
    Retorna (texto_seguro, cabeçalho_bruto).
    """
    # Padrões que sinalizam o início de informações clínicas reais
    content_markers = [
        r"^indicação\s+clínica", r"^queixa\s+principal", r"^achados",
        r"^exame:", r"^tipo\s+de\s+exame", r"^laudo", r"^resultado",
        r"^tomografia", r"^audiometria", r"^videolaringoscopia",
        r"^potencial\s+evocado", r"^videoendoscopia", r"^tc\b", r"^tcfc\b",
        r"^polissonografia", r"^psg\b",
    ]
    
    lines = raw_text.splitlines()
    header_lines = []
    body_lines = []
    header_done = False
    
    for line in lines:
        if not header_done:
            is_body = any(re.search(m, line.strip(), re.IGNORECASE) for m in content_markers)
            if is_body:
                header_done = True
                body_lines.append(line)
            else:
                header_lines.append(line)
        else:
            body_lines.append(line)
    
    header_raw = "\n".join(header_lines)
    body_safe = "\n".join(body_lines)
    
    # Fallback caso não seja encontrado nenhum marcador claro de conteúdo no laudo.
    # Sem isso, todo o texto vira 'header_lines' e o 'body' fica vazio, causando 0 caracteres extraídos.
    if not header_done and len(lines) > 0:
        body_safe = raw_text
        header_raw = "\n".join(lines[:5])
    
    return body_safe, header_raw


def strip_pii_from_text(raw_text: str) -> str:
    """
    Remove/ofusca informações sensíveis (Nome, CPF, RG, Convênio, Data de Nasc.) integralmente.
    """
    if not isinstance(raw_text, str):
        return ""

    # CPF (ex: 123.456.789-00 ou 12345678900)
    text = re.sub(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b', '[CPF OMITIDO]', raw_text)
    # Nomes após "Paciente:", "Paciente...:", "Nome:"
    # Trocamos [NOME OMITIDO] por um hash curto para manter o contexto textual (criptografia leve)
    def _anonymize_name(match):
        prefix = match.group(1)
        name = match.group(2).strip()
        if name:
            import hashlib
            h = hashlib.sha256(name.encode('utf-8')).hexdigest()[:6].upper()
            return f"{prefix} [Paciente_{h}]"
        return f"{prefix} [NOME PROTEGIDO]"

    text = re.sub(
        r'(?i)(paciente\.{0,3}:|nome)[:\s]+([A-Za-zÀ-ÖØ-öø-ÿ \']+?)(?=\s{3,}|\t|data:|idade:|nasc|rg:|cpf:|sexo:|\n|$|\r)', 
        _anonymize_name, 
        text
    )
    # RG
    text = re.sub(r'(?i)(rg|registro\s+geral)[:\s]+([0-9xX.\-\s]+)(?=\n|$|\r)', r'\1: [RG OMITIDO]', text)
    # Data de nascimento
    text = re.sub(r'(?i)(nascimento|d\.n\.|data\s+nasc\.?)[:\s]+(\d{2}[/\-]\d{2}[/\-]\d{4})', r'\1: [DATA OMITIDA]', text)
    # Convênio / Matrícula
    text = re.sub(r'(?i)(conv[eê]nio|plan[oa]|matr[ií]cula)[:\s]+([A-Za-zÀ-ÖØ-öø-ÿ\s\d]+)(?=\n|$|\r)', r'\1: [OMITIDO]', text)
    # N° pedido / solicitante / médico
    text = re.sub(r'(?i)(n[°º]?\s*(pedido|ordem|requisição))[:\s]+[\w\s]+\n', r'\1: [OMITIDO]\n', text)
    # CRM (ex: CRM 12345-SP)
    text = re.sub(r'(?i)(crm\s+\d+[-\s]?[a-z]{0,2})', '[MÉDICO OMITIDO]', text)

    return text
