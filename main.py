from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

from services.extractor import PdfExtractor
from services.ocr_engine import OCRBaseEngine
from services.nlp_parser import NLPParser
from services.gpt_bridge import GPTSummarizer
from services.exam_classifier import ExamClassifier
from core.security import strip_pii_from_text, extract_and_strip_header, generate_patient_token

app = FastAPI(
    title="OTTO OCR Service",
    description="Microserviço opcional de extração e interpretação de exames OTTO (Regra 9).",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs = {}
extractor = PdfExtractor()
ocr_engine = OCRBaseEngine()
nlp_parser = NLPParser()
gpt_bridge = GPTSummarizer()
classifier = ExamClassifier()

class ValidationResult(BaseModel):
    is_correct: bool
    corrections: str | None = None

async def process_job(job_id: str, file_bytes: bytes, filename: str):
    try:
        jobs[job_id]["status"] = "processing"
        text = ""
        is_raster = False

        # — Etapa 1: Extração de Texto —
        if filename.lower().endswith(".pdf"):
            text, is_raster = extractor.process(file_bytes, filename)
            if is_raster:
                jobs[job_id]["message"] = "PDF escaneado detectado. Iniciando motor OCR..."
                text = ocr_engine.extract_from_pdf_bytes(file_bytes)
        else:
            is_raster = True
            jobs[job_id]["message"] = "Imagem detectada. Iniciando motor OCR..."
            text = ocr_engine.extract_from_image_bytes(file_bytes)

        # — Etapa 2: LGPD — Extrai cabeçalho (PII) e gera token anônimo auditável —
        jobs[job_id]["message"] = "Aplicando protocolo LGPD: extraindo cabeçalho e gerando token anônimo..."
        safe_body, header_raw = extract_and_strip_header(text)
        patient_token = generate_patient_token(header_raw)
        safe_body = strip_pii_from_text(safe_body)

        # — Etapa 3: Classificação do Tipo de Exame (ANTES de NLP e GPT) —
        jobs[job_id]["message"] = "Identificando tipo de exame..."
        exam_type = classifier.classify(safe_body)
        exam_label = classifier.label(exam_type)
        jobs[job_id]["exam_type"] = exam_type
        jobs[job_id]["message"] = f"Exame identificado: {exam_label}"

        # — Etapa 4: NLP Rule-Based específico por tipo —
        entities = nlp_parser.enrich_with_heuristics(safe_body, exam_type)

        # — Etapa 5: Interpretação GPT com prompt especializado —
        jobs[job_id]["message"] = f"Enviando para análise clínica GPT ({exam_label})..."
        gpt_analysis = await gpt_bridge.summarize(safe_body, exam_type)

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["message"] = "Processamento finalizado."
        jobs[job_id]["result"] = {
            "patient_token": patient_token,    # ID anônimo para integrar ao OTTO Triagem
            "exam_type": exam_type,
            "exam_label": exam_label,
            "was_raster_engine_used": is_raster,
            "raw_text_length": len(text),
            "safe_text_snippet": safe_body[:300] + "...",
            "entities_found": entities,
            "clinical_interpretation": gpt_analysis
        }

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["message"] = f"Erro no processamento: {str(e)}"

@app.post("/ocr/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Inicia extração assíncrona de laudo médico (PDF ou imagem)."""
    job_id = str(uuid.uuid4())
    file_bytes = await file.read()

    jobs[job_id] = {
        "status": "queued",
        "result": None,
        "filename": file.filename,
        "message": "Protocolo gerado. Processamento iniciado."
    }

    background_tasks.add_task(process_job, job_id, file_bytes, file.filename)
    return {"job_id": job_id, "status": "queued"}

@app.get("/ocr/{job_id}/result")
async def get_ocr_result(job_id: str):
    """Consulta resultado do processamento."""
    if job_id not in jobs:
        return {"error": "Not Found"}
    return jobs[job_id]

@app.post("/ocr/{job_id}/validate")
async def validate_ocr_result(job_id: str, payload: ValidationResult):
    """Feedback médico para retroalimentação e auditoria."""
    if job_id not in jobs:
        return {"error": "Not Found"}
    jobs[job_id]["validation_status"] = "validated"
    jobs[job_id]["corrections"] = payload.corrections
    return {"status": "success"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "OTTO OCR microservice", "version": "2.0.0"}
