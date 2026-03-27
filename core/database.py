"""
Sprint 3: Persistência de Jobs e Validações Médicas com SQLite
=============================================================
Armazena jobs OCR e correções médicas de forma persistente para:
- Sobreviver a reinicializações do servidor Render
- Alimentar o enriquecimento léxico do OTTO OCR
- Auditoria LGPD (trilha de patient_tokens e validações)
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "otto_ocr.db"


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Cria as tabelas se não existirem."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id      TEXT PRIMARY KEY,
                patient_token TEXT,
                filename    TEXT,
                exam_type   TEXT,
                status      TEXT DEFAULT 'queued',
                message     TEXT,
                result_json TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS validations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id          TEXT NOT NULL,
                patient_token   TEXT,
                exam_type       TEXT,
                is_correct      INTEGER NOT NULL,  -- 1=correto, 0=incorreto
                corrections     TEXT,               -- texto livre da correção médica
                validated_at    TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            );

            CREATE TABLE IF NOT EXISTS lexical_feedback (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_type       TEXT,
                original_text   TEXT,  -- trecho extraído pelo OCR
                corrected_text  TEXT,  -- correção do médico
                source_job_id   TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );
        """)


# ─── Jobs ────────────────────────────────────────────────────────────────────

def create_job(job_id: str, filename: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO jobs (job_id, filename) VALUES (?, ?)",
            (job_id, filename)
        )

def update_job(job_id: str, status: str, message: str, result: dict = None,
               patient_token: str = None, exam_type: str = None) -> None:
    result_json = json.dumps(result, ensure_ascii=False) if result else None
    with get_connection() as conn:
        conn.execute("""
            UPDATE jobs SET
                status = ?,
                message = ?,
                result_json = COALESCE(?, result_json),
                patient_token = COALESCE(?, patient_token),
                exam_type = COALESCE(?, exam_type),
                updated_at = datetime('now')
            WHERE job_id = ?
        """, (status, message, result_json, patient_token, exam_type, job_id))

def get_job(job_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    if data.get("result_json"):
        data["result"] = json.loads(data.pop("result_json"))
    else:
        data["result"] = None
        data.pop("result_json", None)
    return data


# ─── Validações ───────────────────────────────────────────────────────────────

def save_validation(job_id: str, is_correct: bool, corrections: str = None) -> None:
    job = get_job(job_id)
    patient_token = job.get("patient_token") if job else None
    exam_type = job.get("exam_type") if job else None

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO validations (job_id, patient_token, exam_type, is_correct, corrections)
            VALUES (?, ?, ?, ?, ?)
        """, (job_id, patient_token, exam_type, int(is_correct), corrections))

        # Se tem correção, salva também no léxico
        if corrections and not is_correct and job and job.get("result"):
            safe_text = job["result"].get("safe_text_snippet", "")
            if safe_text and safe_text != "...":
                conn.execute("""
                    INSERT INTO lexical_feedback
                        (exam_type, original_text, corrected_text, source_job_id)
                    VALUES (?, ?, ?, ?)
                """, (exam_type, safe_text[:500], corrections[:500], job_id))

def get_lexical_stats() -> dict:
    """Retorna estatísticas do banco de validações para enriquecimento léxico."""
    with get_connection() as conn:
        total_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='completed'").fetchone()[0]
        total_validations = conn.execute("SELECT COUNT(*) FROM validations").fetchone()[0]
        corrections = conn.execute(
            "SELECT COUNT(*) FROM validations WHERE is_correct=0"
        ).fetchone()[0]
        by_exam = conn.execute("""
            SELECT exam_type, COUNT(*) as cnt
            FROM validations WHERE exam_type IS NOT NULL
            GROUP BY exam_type
        """).fetchall()
        feedback_count = conn.execute("SELECT COUNT(*) FROM lexical_feedback").fetchone()[0]

    return {
        "total_completed_jobs": total_jobs,
        "total_validations": total_validations,
        "corrections_submitted": corrections,
        "lexical_feedback_entries": feedback_count,
        "validations_by_exam": {r["exam_type"]: r["cnt"] for r in by_exam}
    }
