from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import io
import asyncio

from services.extractor import PdfExtractor
from services.ocr_engine import OCRBaseEngine
from services.nlp_parser import NLPParser
from services.gpt_bridge import GPTSummarizer
from core.security import strip_pii_from_text

app = FastAPI(
    title="OTTO OCR Service",
    description="Microserviço opcional para extração e interpretação de exames OTTO (Regra 9).",
    version="1.0.0"
)

# Configurando CORS para permitir requisições do seu Frontend em Vite/React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Trocar pelo domínio do OTTO Triagem/PROCOD em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs = {}
extractor = PdfExtractor()
ocr_engine = OCRBaseEngine()
nlp_parser = NLPParser()
gpt_bridge = GPTSummarizer()

class ValidationResult(BaseModel):
    is_correct: bool
    corrections: str | None = None

async def process_job(job_id: str, file_bytes: bytes, filename: str):
    try:
        jobs[job_id]["status"] = "processing"
        
        text = ""
        is_raster = False
        
        if filename.lower().endswith(".pdf"):
            text, is_raster = extractor.process(file_bytes, filename)
            if is_raster:
                jobs[job_id]["message"] = "PDF escaneado detectado. Iniciando motor OCR..."
                text = ocr_engine.extract_from_pdf_bytes(file_bytes)
        else:
            is_raster = True
            jobs[job_id]["message"] = "Imagem detectada. Iniciando motor OCR..."
            text = ocr_engine.extract_from_image_bytes(file_bytes)
            
        jobs[job_id]["message"] = "Aplicando camada de anonimização (LGPD)..."
        safe_text = strip_pii_from_text(text)
        
        jobs[job_id]["message"] = "Analisando com NLP/Regex estruturado..."
        exam_type = filename.split(".")[0].lower()
        extracted_entities = nlp_parser.enrich_with_heuristics(safe_text, exam_type)
        
        jobs[job_id]["message"] = "Enviando texto seguro para resumo no GPT..."
        gpt_analysis = await gpt_bridge.summarize(safe_text, exam_type)
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = {
            "was_raster_engine_used": is_raster,
            "raw_text_length": len(text),
            "safe_text_snippet": safe_text[:200] + "...", 
            "entities_found": extracted_entities,
            "clinical_interpretation": gpt_analysis
        }
        jobs[job_id]["message"] = "Processamento finalizado e interpretado sem quebrar output."
        
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["message"] = f"Erro assíncrono no processamento: {str(e)}"

@app.post("/ocr/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Recebe arquivo (PDF ou imagem) e aciona processamento assíncrono."""
    job_id = str(uuid.uuid4())
    file_bytes = await file.read()
    
    jobs[job_id] = {
        "status": "queued",
        "result": None,
        "filename": file.filename,
        "message": "Protocolo gerado. O exame iniciou o processamento na nuvem."
    }
    
    background_tasks.add_task(process_job, job_id, file_bytes, file.filename)

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Protocolo gerado. O exame entrou na fila."
    }

@app.get("/ocr/{job_id}/result")
async def get_ocr_result(job_id: str):
    """Poller do frontend para buscar quando a análise finaliza."""
    if job_id not in jobs:
        return {"error": "Not Found", "message": "Job inválido."}
    return jobs[job_id]

@app.post("/ocr/{job_id}/validate")
async def validate_ocr_result(job_id: str, payload: ValidationResult):
    """Rota de feedback médico."""
    if job_id not in jobs:
        return {"error": "Not Found"}
    jobs[job_id]["validation_status"] = "validated"
    jobs[job_id]["corrections"] = payload.corrections
    return {"status": "success"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "OTTO OCR microservice"}
