import os
import json
from pathlib import Path
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

# Carrega a knowledge base de léxico clínico
_KB_PATH = Path(__file__).parent.parent / "knowledge" / "lexical_kb.json"

def _load_kb() -> dict:
    if _KB_PATH.exists():
        with open(_KB_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}

_LEXICAL_KB = _load_kb()


class GPTAnalysisResult(BaseModel):
    summary: str = Field(description="Resumo clínico de 3 a 5 linhas do laudo.")
    findings: list[str] = Field(description="Achados relevantes (máximo 8). INCLUA variantes anatômicas e obstruções de via de drenagem.")
    diagnostics: list[str] = Field(description="Diagnósticos diferenciais ou condutas sugeridas (sem recomendações definitivas).")


# Prompts base especializados por tipo de exame
_BASE_PROMPTS = {
    "audiometria": """
        Você é especialista em audiologia clínica. Analise o laudo de audiometria a seguir.
        Identifique: tipo e grau de perda auditiva (condutiva/neurossensorial/mista), orelhas afetadas,
        frequências comprometidas e correlações clínicas (zumbido, vertigem, hipoacusia progressiva).
        Não dê recomendações médicas definitivas.
    """,
    "bera": """
        Você é especialista em eletrofisiologia auditiva. Analise o BERA (Potencial Evocado Auditivo
        de Tronco Encefálico) a seguir. Identifique latências absolutas e interpico das ondas I, III e V,
        compare com valores normais de referência e comente sobre suspeita de neuropatia auditiva ou
        alterações de tronco. Não dê recomendações médicas definitivas.
    """,
    "videolaringoscopia": """
        Você é especialista em laringologia. Analise o laudo de videolaringoscopia ou nasofibrolaringoscopia
        a seguir. Identifique achados nas estruturas laríngeas (pregas vocais, aritenóides, epiglote),
        presença de nódulos, pólipos, edema, paralisia vocal ou sinais de refluxo.
        Comente as implicações para disfagia e disfonia. Não dê recomendações médicas definitivas.
    """,
    "endoscopia_nasal": """
        Você é especialista em rinologia. Analise o laudo de videoendoscopia nasal a seguir.
        Identifique achados nos meatos nasais, cornetos, septo, fossas nasais e coanas.
        Comente sobre sinusite, polipose, desvio de septo e implicações para obstrução nasal.
        Indique se o quadro sugere tratamento clínico ou cirúrgico (septoplastia, FESS).
        Não dê recomendações médicas definitivas.
    """,
    "tomografia": """
        Você é especialista em otorrinolaringologia com foco em imagens de cabeça e pescoço.
        Analise o laudo de tomografia a seguir. Identifique TODOS os achados, incluindo variantes
        anatômicas (curvatura paradoxal de corneto, concha bolhosa, esporão septal), obstruções
        de vias de drenagem (infundíbulo etmoidal, complexo ostiomeatal) e natureza dos achados
        (espessamento mucoso, velamento, nível líquido, lesões expansivas).
        Se houver espessamento crônico COM nível líquido, classifique como 'sinusite crônica agudizada'.
        Não dê recomendações médicas definitivas.
    """,
    "generico": """
        Você é especialista em otorrinolaringologia. Analise o laudo a seguir,
        identificando o tipo de exame, os achados relevantes e as implicações clínicas.
        Não dê recomendações médicas definitivas.
    """,
}


def _build_lexical_block(exam_type: str) -> str:
    """Constrói o bloco de vocabulário clínico para injetar no prompt."""
    kb = _LEXICAL_KB.get(exam_type, {})
    termos_altos = [t for t in kb.get("achados_discriminativos", []) if t.get("peso") == "ALTO"]
    if not termos_altos:
        return ""

    linhas = ["VOCABULÁRIO CLÍNICO PRIORITÁRIO (não ignore estes termos se presentes no laudo):"]
    for t in termos_altos:
        variantes = " / ".join(t.get("variantes", []))
        linhas.append(f'  - "{t["termo"]}" (também: {variantes}): {t["significado"]}')

    diags = kb.get("diagnosticos_compostos", [])
    if diags:
        linhas.append("\nDIAGNÓSTICOS COMPOSTOS (aplicar quando a combinação de achados estiver presente):")
        for d in diags:
            linhas.append(f'  - {d["condicao"]} → {d["diagnostico"]}')

    return "\n".join(linhas)


def _build_prompt(text: str, exam_type: str) -> str:
    base = _BASE_PROMPTS.get(exam_type, _BASE_PROMPTS["generico"]).strip()
    lexical_block = _build_lexical_block(exam_type)

    sections = [base]
    if lexical_block:
        sections.append(lexical_block)
    sections.append(f'Texto extraído do laudo (dados de identificação removidos — conformidade LGPD):\n"""\n{text}\n"""')

    return "\n\n".join(sections)


class GPTSummarizer:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None

    async def summarize(self, text: str, exam_type: str = "generico") -> dict:
        if not self.api_key or not self.client:
            return {
                "summary": "Resumo mockado: API Key da OpenAI não configurada no ambiente.",
                "findings": ["Configure OPENAI_API_KEY no painel do Render."],
                "diagnostics": ["Integração GPT pendente de chave de API."]
            }

        prompt = _build_prompt(text, exam_type)

        try:
            response = await self.client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Você é um assistente médico clínico especializado em Otorrinolaringologia. Seja preciso e completo nos achados — não omita variantes anatômicas ou obstruções de drenagem."},
                    {"role": "user", "content": prompt}
                ],
                response_format=GPTAnalysisResult,
            )
            return response.choices[0].message.parsed.model_dump()
        except Exception as e:
            return {"error": str(e), "summary": "Erro de integração GPT."}
