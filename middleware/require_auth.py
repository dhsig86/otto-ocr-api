"""
middleware/require_auth.py — OTTO OCR
Firebase Auth dependency para FastAPI.

Protege endpoints de análise clínica contra acesso não autenticado.
Endpoints públicos (polling de resultado, stats) permanecem abertos.

Env vars:
  FIREBASE_CREDENTIALS_JSON  — JSON completo da service account (prioridade, Render/Heroku)
  GOOGLE_APPLICATION_CREDENTIALS — caminho para arquivo .json (local)
"""

import os
import json
from fastapi import HTTPException, Header
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials

# Inicializa Firebase Admin uma única vez (padrão do ecossistema OTTO)
if not firebase_admin._apps:
    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if cred_json:
        try:
            cred_dict = json.loads(cred_json)
            firebase_admin.initialize_app(credentials.Certificate(cred_dict))
        except Exception as e:
            print(f"[OCR-AUTH] AVISO: falha ao inicializar Firebase via FIREBASE_CREDENTIALS_JSON: {e}")
    else:
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path and os.path.exists(cred_path):
            firebase_admin.initialize_app(credentials.Certificate(cred_path))
        else:
            print("[OCR-AUTH] AVISO: credenciais Firebase nao encontradas. Endpoints protegidos retornarao 503.")


async def verify_firebase_token(authorization: str = Header(default=None)) -> str:
    """
    FastAPI Dependency — valida Bearer token Firebase e retorna uid do medico.
    Retorna 401 se token ausente/invalido, 503 se Firebase nao inicializado.
    """
    if not firebase_admin._apps:
        raise HTTPException(
            status_code=503,
            detail="Servico de autenticacao nao configurado. Adicione FIREBASE_CREDENTIALS_JSON no ambiente."
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token Bearer ausente ou malformado.")

    token = authorization.split("Bearer ", 1)[1].strip()

    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded["uid"]
    except firebase_auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token Firebase expirado. Faca login novamente.")
    except firebase_auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Token Firebase invalido.")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Falha na autenticacao: {str(e)}")
