import os
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

class GPTAnalysisResult(BaseModel):
    summary: str = Field(description="Resumo clínico de 3 a 5 linhas do laudo.")
    findings: list[str] = Field(description="Achados relevantes (máximo 5).")
    diagnostics: list[str] = Field(description="Diagnósticos diferenciais ou condutas sugeridas (sem recomendações definitivas).")

# Prompts especializados por tipo de exame
EXAM_PROMPTS = {
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
        Analise o laudo de tomografia a seguir. Identifique as estruturas afetadas
        (seios paranasais, mastoide, orelha média, região cervical), natureza dos achados
        (espessamento mucoso, velamento, lesões expansivas, calcificações) e correlacione
        com indicações cirúrgicas. Não dê recomendações médicas definitivas.
    """,
    "generico": """
        Você é especialista em otorrinolaringologia. Analise o laudo a seguir,
        identificando o tipo de exame, os achados relevantes e as implicações clínicas.
        Não dê recomendações médicas definitivas.
    """,
}

class GPTSummarizer:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None

    async def summarize(self, text: str, exam_type: str = "generico") -> dict:
        prompt_context = EXAM_PROMPTS.get(exam_type, EXAM_PROMPTS["generico"])

        if not self.api_key or not self.client:
            return {
                "summary": "Resumo mockado: API Key da OpenAI não configurada no ambiente.",
                "findings": ["Configure OPENAI_API_KEY no painel do Render/Heroku."],
                "diagnostics": ["Integração GPT pendente de chave de API."]
            }

        prompt = f"""
        {prompt_context}

        Texto extraído do laudo (dados de identificação removidos para conformidade com a LGPD):
        \"\"\"
        {text}
        \"\"\"
        """

        try:
            response = await self.client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Você é um assistente médico clínico especializado em Otorrinolaringologia."},
                    {"role": "user", "content": prompt}
                ],
                response_format=GPTAnalysisResult,
            )
            return response.choices[0].message.parsed.model_dump()
        except Exception as e:
            return {"error": str(e), "summary": "Erro de integração GPT."}
