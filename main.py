from fastapi import FastAPI, File, UploadFile, BackgroundTasks, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
import os
from pydantic import BaseModel
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).parent

from services.extractor import PdfExtractor
from services.ocr_engine import OCRBaseEngine
from services.nlp_parser import NLPParser
from services.gpt_bridge import GPTSummarizer
from services.exam_classifier import ExamClassifier
from core.security import strip_pii_from_text, extract_and_strip_header, generate_patient_token
from core.database import init_db, create_job, update_job, get_job, save_validation, get_lexical_stats

# Inicializa o banco de dados SQLite na primeira execução
init_db()

app = FastAPI(
    title="OTTO OCR Service",
    description="Microserviço opcional de extração e interpretação de exames OTTO (Regra 9).",
    version="3.0.0"
)

# CORS: allow_credentials=True é INCOMPATÍVEL com allow_origins=["*"] pela spec CORS.
# Com credentials=False o wildcard funciona corretamente para upload de FormData.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# ─── Frontend: servido pela rota raiz ──────────────────────────────────────
_HTML_CANDIDATES = [
    BASE_DIR / "static" / "index.html",
    BASE_DIR / "ocr_review.html",
    BASE_DIR / "docs" / "index.html",
]

def _load_frontend() -> str:
    for p in _HTML_CANDIDATES:
        if p.exists():
            return p.read_text(encoding="utf-8")
    return "<h1>OTTO OCR</h1><p>Serviço operacional. Interface não encontrada.</p>"

@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def serve_frontend():
    return HTMLResponse(content=_load_frontend(), status_code=200)

@app.api_route("/ping", methods=["GET", "HEAD"], include_in_schema=False)
async def ping():
    files = {str(p.relative_to(BASE_DIR)): p.exists() for p in _HTML_CANDIDATES}
    return {"version": "3.0.0", "base_dir": str(BASE_DIR), "files": files}

# ─── Serviços ───────────────────────────────────────────────────────────────
extractor = PdfExtractor()
ocr_engine = OCRBaseEngine()
nlp_parser = NLPParser()
gpt_bridge = GPTSummarizer()
classifier = ExamClassifier()

class ValidationResult(BaseModel):
    is_correct: bool
    corrections: str | None = None

# ─── Pipeline assíncrono ────────────────────────────────────────────────────
async def process_job(job_id: str, file_bytes: bytes, filename: str):
    try:
        update_job(job_id, status="processing", message="Iniciando extração...")
        text = ""
        is_raster = False

        # Etapa 1: Extração de Texto
        if filename.lower().endswith(".pdf"):
            text, is_raster = extractor.process(file_bytes, filename)
            if is_raster:
                update_job(job_id, status="processing", message="PDF escaneado detectado. Iniciando motor OCR...")
                text = ocr_engine.extract_from_pdf_bytes(file_bytes)
        else:
            is_raster = True
            update_job(job_id, status="processing", message="Imagem detectada. Iniciando motor OCR...")
            text = ocr_engine.extract_from_image_bytes(file_bytes)

        # Etapa 2: LGPD
        update_job(job_id, status="processing", message="Aplicando protocolo LGPD...")
        safe_body, header_raw = extract_and_strip_header(text)
        patient_token = generate_patient_token(header_raw)
        safe_body = strip_pii_from_text(safe_body)

        # Guarda de Confiança
        MIN_CHARS = 80
        if len(safe_body.strip()) < MIN_CHARS:
            msg = (
                f"OCR extraiu apenas {len(safe_body.strip())} caracteres — insuficiente para análise segura. "
                "Por favor, envie o laudo em melhor qualidade (PDF nativo, scan de alta resolução ou foto com boa iluminação)."
            )
            result = {
                "patient_token": patient_token,
                "exam_type": "indefinido",
                "exam_label": "Não Identificado — Qualidade Insuficiente",
                "was_raster_engine_used": is_raster,
                "raw_text_length": len(text),
                "safe_text_snippet": safe_body[:300],
                "entities_found": {},
                "clinical_interpretation": None,
                "low_confidence": True
            }
            update_job(job_id, status="low_confidence", message=msg,
                       result=result, patient_token=patient_token, exam_type="indefinido")
            return

        # Etapa 3: Classificação
        exam_type = classifier.classify(safe_body)
        exam_label = classifier.label(exam_type)
        update_job(job_id, status="processing", message=f"Exame identificado: {exam_label}",
                   patient_token=patient_token, exam_type=exam_type)

        # Etapa 4: NLP
        entities = nlp_parser.enrich_with_heuristics(safe_body, exam_type)

        # Etapa 5: GPT
        update_job(job_id, status="processing", message=f"Enviando para análise clínica GPT ({exam_label})...")
        gpt_analysis = await gpt_bridge.summarize(safe_body, exam_type)

        result = {
            "patient_token": patient_token,
            "exam_type": exam_type,
            "exam_label": exam_label,
            "was_raster_engine_used": is_raster,
            "raw_text_length": len(text),
            "safe_text_snippet": safe_body[:300] + "...",
            "entities_found": entities,
            "clinical_interpretation": gpt_analysis
        }
        update_job(job_id, status="completed", message="Processamento finalizado.",
                   result=result, patient_token=patient_token, exam_type=exam_type)

    except Exception as e:
        update_job(job_id, status="failed", message=f"Erro no processamento: {str(e)}")

# ─── Rotas ───────────────────────────────────────────────────────────────────

# Rota corrigida: /api/upload (compatível com frontend OTTO PROCOD) + alias legado /ocr/upload
@app.post("/api/upload")
@app.post("/api/upload/")  # trailing-slash alias para evitar 307 redirect
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Inicia extração assíncrona de laudo médico (PDF ou imagem)."""
    job_id = str(uuid.uuid4())
    file_bytes = await file.read()
    create_job(job_id, file.filename)
    update_job(job_id, status="queued", message="Protocolo gerado. Processamento iniciado.")
    background_tasks.add_task(process_job, job_id, file_bytes, file.filename)
    return {"job_id": job_id, "status": "queued"}

@app.post("/ocr/upload")  # alias legado — mantido para não quebrar outros clientes
async def upload_document_legacy(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    return await upload_document(background_tasks, file)

@app.get("/ocr/{job_id}/result")
async def get_ocr_result(job_id: str):
    """Consulta resultado do processamento."""
    job = get_job(job_id)
    if not job:
        return {"error": "Not Found"}
    return job

@app.post("/ocr/{job_id}/validate")
async def validate_ocr_result(job_id: str, payload: ValidationResult):
    """Feedback médico persistido no banco de dados para retroalimentação lexical."""
    job = get_job(job_id)
    if not job:
        return {"error": "Not Found"}
    save_validation(job_id, payload.is_correct, payload.corrections)
    return {"status": "success", "persisted": True}

@app.get("/ocr/stats")
async def get_stats():
    """Estatísticas de validações para monitoramento do enriquecimento lexical."""
    return get_lexical_stats()

@app.get("/ocr/db/export")
async def export_database(x_admin_token: str = Header(default=None)):
    """
    Exporta o banco SQLite para download local antes de novos deploys.
    Protegido por token simples (header X-Admin-Token).
    """
    admin_token = os.environ.get("ADMIN_TOKEN", "otto-ocr-admin")
    if x_admin_token != admin_token:
        raise HTTPException(status_code=401, detail="Token inválido")
    from core.database import DB_PATH
    if not DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Banco de dados ainda não criado")
    return FileResponse(
        path=str(DB_PATH),
        media_type="application/octet-stream",
        filename="otto_ocr_backup.db"
    )

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "OTTO OCR microservice", "version": "3.0.0"}
