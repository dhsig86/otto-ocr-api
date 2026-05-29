from fastapi import FastAPI, File, UploadFile, BackgroundTasks, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
import os
from pydantic import BaseModel
import uuid
from pathlib import Path

from middleware.require_auth import verify_firebase_token
from pathlib import Path

# ADMIN_TOKEN: env var obrigatória para /ocr/db/export
# Se não configurada, a rota retorna 503 (em vez de gerar random que muda a cada restart)

BASE_DIR = Path(__file__).parent

from services.extractor import PdfExtractor
from services.ocr_engine import OCRBaseEngine
from services.nlp_parser import NLPParser
from services.gpt_bridge import GPTSummarizer
from services.exam_classifier import ExamClassifier
from core.security import strip_pii_from_text, extract_and_strip_header, generate_patient_token, extract_exam_date, extract_patient_data
from core.database import init_db, create_job, update_job, get_job, save_validation, get_lexical_stats, update_validation_status

# Inicializa o banco de dados SQLite na primeira execução
init_db()

app = FastAPI(
    title="OTTO OCR Service",
    description="Microserviço opcional de extração e interpretação de exames OTTO (Regra 9).",
    version="3.1.0"
)

# Política de retenção: limpa uploads com mais de 7 dias (LGPD)
UPLOAD_RETENTION_DAYS = int(os.environ.get("UPLOAD_RETENTION_DAYS", "7"))

@app.on_event("startup")
async def cleanup_old_uploads():
    """Remove arquivos de upload com mais de UPLOAD_RETENTION_DAYS dias."""
    import time
    upload_dir = BASE_DIR / "uploads"
    if not upload_dir.exists():
        return
    cutoff = time.time() - (UPLOAD_RETENTION_DAYS * 86400)
    removed = 0
    for f in upload_dir.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass
    if removed:
        print(f"[LGPD] Removidos {removed} uploads com mais de {UPLOAD_RETENTION_DAYS} dias.")

# CORS: Adicionado dominio explicitamente para resolver Strict-Origin policy na request FormData
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # ── Domínios customizados ──────────────────────────────────────────
        "https://ocr.drdariohart.com",
        "https://otto.drdariohart.com",
        "https://procod.drdariohart.com",
        "https://atlas.drdariohart.com",
        "https://cases.drdariohart.com",
        # ── Vercel deployments ────────────────────────────────────────────
        "https://ottopwa.vercel.app",
        "https://otto-pwa.vercel.app",          # legacy
        "https://ottos-plum.vercel.app",
        "https://otto-calc-hub.vercel.app",
        "https://otto-imune.vercel.app",
        "https://otto-voice-one.vercel.app",
        "https://bottok-orcin.vercel.app",
        "https://test-pg-bice.vercel.app",
        "https://otto-ocr-web.vercel.app",
        # ── Firebase Hosting ──────────────────────────────────────────────
        "https://otto-ecosystem.web.app",
        "https://otto-ecosystem.firebaseapp.com",
        # ── Heroku / Netlify ──────────────────────────────────────────────
        "https://otto-ai-triagem-1fc48c3c292e.herokuapp.com",
        "https://otto-whisper.netlify.app",
        "https://dhsig86.github.io",
        # ── Desenvolvimento local ─────────────────────────────────────────
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    # Permite iframe embed para o OTTO PWA
    if "X-Frame-Options" in response.headers:
        del response.headers["X-Frame-Options"]
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self' https://otto.drdariohart.com https://ottopwa.vercel.app https://ottos-plum.vercel.app"
    return response

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
        import asyncio
        if filename.lower().endswith(".pdf"):
            text, is_raster = await asyncio.to_thread(extractor.process, file_bytes, filename)
            if is_raster:
                update_job(job_id, status="processing", message="PDF escaneado detectado. Iniciando motor OCR...")
                text = await asyncio.to_thread(ocr_engine.extract_from_pdf_bytes, file_bytes)
        else:
            is_raster = True
            update_job(job_id, status="processing", message="Imagem detectada. Iniciando motor OCR...")
            text = await asyncio.to_thread(ocr_engine.extract_from_image_bytes, file_bytes)

        # Etapa 2: LGPD — extrair data ANTES de descartar o cabeçalho
        update_job(job_id, status="processing", message="Aplicando protocolo LGPD...")
        safe_body, header_raw = await asyncio.to_thread(extract_and_strip_header, text)
        exam_date = await asyncio.to_thread(extract_exam_date, header_raw, safe_body)  # data é metadado clínico, não PII
        patient_token = await asyncio.to_thread(generate_patient_token, header_raw)
        patient_data = await asyncio.to_thread(extract_patient_data, header_raw)
        safe_body = await asyncio.to_thread(strip_pii_from_text, safe_body)

        # Guarda de Confiança
        MIN_CHARS = 80
        if len(safe_body.strip()) < MIN_CHARS:
            msg = (
                f"OCR extraiu apenas {len(safe_body.strip())} caracteres — insuficiente para análise segura. "
                "Por favor, envie o laudo em melhor qualidade (PDF nativo, scan de alta resolução ou foto com boa iluminação)."
            )
            result = {
                "patient_token": patient_token,
                "patient_data": patient_data,
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
        exam_type = await asyncio.to_thread(classifier.classify, safe_body)
        exam_label = await asyncio.to_thread(classifier.label, exam_type)
        update_job(job_id, status="processing", message=f"Exame identificado: {exam_label}",
                   patient_token=patient_token, exam_type=exam_type)

        # Etapa 4: NLP
        entities = await asyncio.to_thread(nlp_parser.enrich_with_heuristics, safe_body, exam_type)

        # Etapa 5: GPT
        update_job(job_id, status="processing", message=f"Enviando para análise clínica GPT ({exam_label})...")
        gpt_analysis = await gpt_bridge.summarize(safe_body, exam_type)

        if not gpt_analysis.get("is_valid_exam", True):
            msg = (
                "A inteligência clínica de fallback detectou texto ilegível (ruído de OCR) ou que a imagem corresponde a um gráfico/tabela ininteligível. "
                "Por favor, certifique-se de enviar a folha textual do laudo com resultados, em boa qualidade e iluminação."
            )
            update_job(job_id, status="low_confidence", message=msg,
                       result=None, patient_token=patient_token, exam_type=exam_type)
            return

        result = {
            "patient_token": patient_token,
            "patient_data": patient_data,
            "exam_date": exam_date,
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

@app.post("/ocr/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    uid: str = Depends(verify_firebase_token),  # ACT-29: requer médico autenticado
):
    """Inicia extração assíncrona de laudo médico (PDF ou imagem). Requer Bearer token Firebase."""
    job_id = str(uuid.uuid4())
    file_bytes = await file.read()
    
    # Armazena localmente o arquivo cru para futura esteira de MLOps
    upload_dir = BASE_DIR / "uploads"
    upload_dir.mkdir(exist_ok=True)
    file_path = upload_dir / f"{job_id}_{file.filename}"
    file_path.write_bytes(file_bytes)
    
    create_job(job_id, file.filename, file_path=str(file_path))
    update_job(job_id, status="queued", message="Protocolo gerado. Processamento iniciado.")
    background_tasks.add_task(process_job, job_id, file_bytes, file.filename)
    return {"job_id": job_id, "status": "queued"}

@app.get("/ocr/{job_id}/result")
async def get_ocr_result(job_id: str):
    """Consulta resultado do processamento."""
    job = get_job(job_id)
    if not job:
        return {"error": "Not Found"}
    return job

@app.post("/ocr/{job_id}/validate")
async def validate_ocr_result(
    job_id: str,
    payload: ValidationResult,
    uid: str = Depends(verify_firebase_token),  # ACT-29: feedback só de médico autenticado
):
    """Feedback médico persistido no banco de dados para retroalimentação lexical. Requer Bearer token Firebase."""
    job = get_job(job_id)
    if not job:
        return {"error": "Not Found"}
    save_validation(job_id, payload.is_correct, payload.corrections)
    update_validation_status(job_id, payload.is_correct)
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
    admin_token = os.environ.get("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN não configurado no servidor")
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
    return {"status": "ok", "service": "OTTO OCR microservice", "version": "3.1.0"}
