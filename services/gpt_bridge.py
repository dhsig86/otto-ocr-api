import os
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

class GPTAnalysisResult(BaseModel):
    summary: str = Field(description="Resumo de 3 a 5 linhas do laudo.")
    findings: list[str] = Field(description="Lista dos achados de maior relevância (máximo 5).")
    diagnostics: list[str] = Field(description="Sugestões de diagnósticos diferenciais ou condutas (sem recomendações médicas definitivas).")

class GPTSummarizer:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "dummy")
        self.client = AsyncOpenAI(api_key=self.api_key)

    async def summarize(self, text: str, exam_type: str = "Exame de Otorrinolaringologia Genérico") -> dict:
        """
        Chama a API da OpenAI estruturada para garantir a formatação da resposta.
        """
        if self.api_key == "dummy" or not self.api_key:
            return {
                "summary": "Resumo mockado. API Key do OpenAI não configurada no ambiente (.env).",
                "findings": ["Achado 1 (Mockado)", "Achado 2 (Mockado)"],
                "diagnostics": ["Sugestão diagnóstica mockada (Mockado)"]
            }

        prompt = f"""
        Você é um assistente especialista em Otorrinolaringologia.
        Aja como um transcritor clínico e gerador de relatórios.
        
        ATENÇÃO: Não faça recomendações médicas definitivas.
        Tipo de exame: {exam_type}

        Texto extraído (garantido sem PII - compliance com LGPD):
        \"\"\"
        {text}
        \"\"\"
        """
        
        try:
            response = await self.client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Você atua como auxiliar de triagem em otorrino."},
                    {"role": "user", "content": prompt}
                ],
                response_format=GPTAnalysisResult,
            )
            return response.choices[0].message.parsed.model_dump()
        except Exception as e:
            return {"error": str(e), "summary": "Erro de integração GPT."}
