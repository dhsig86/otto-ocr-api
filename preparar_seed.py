"""
preparar_seed.py — Gera o arquivo seed/otto_ocr_seed.db para incluir no deploy.

O seed preserva SOMENTE as correções lexicais aprovadas (sem dados clínicos de pacientes).
As tabelas `jobs` e `validations` são exportadas SEM o campo result_json (dados clínicos).

Uso:
  1. Baixe o banco:  curl.exe -H "X-Admin-Token: otto-ocr-admin" https://otto-ocr-api.onrender.com/ocr/db/export --output otto_ocr_backup.db
  2. Gere o seed:    python preparar_seed.py otto_ocr_backup.db
  3. Commit o seed:  git add seed/otto_ocr_seed.db && git commit -m "Seed: atualizando com validacoes aprovadas"
  4. Deploy:         git push github master → Manual Deploy no Render
"""
import sqlite3
import shutil
import sys
from pathlib import Path

SOURCE = sys.argv[1] if len(sys.argv) > 1 else "otto_ocr_backup.db"
SEED_DIR = Path("seed")
SEED_PATH = SEED_DIR / "otto_ocr_seed.db"

if not Path(SOURCE).exists():
    print("Arquivo fonte nao encontrado:", SOURCE)
    sys.exit(1)

SEED_DIR.mkdir(exist_ok=True)

# Copiar o banco fonte
shutil.copy2(SOURCE, SEED_PATH)

# Limpar dados sensíveis do seed:
# - result_json (contém texto clínico interpretado)
# - filename (pode expor nomes de arquivos)
conn = sqlite3.connect(str(SEED_PATH))
try:
    # Zera apenas as colunas sensíveis, mantém estrutura e metadados anonimizados
    conn.execute("UPDATE jobs SET result_json = NULL, filename = '[redacted]'")
    conn.execute("UPDATE lexical_feedback SET original_text = '[redacted]' WHERE LENGTH(original_text) > 100")
    conn.commit()

    # Resumo
    jobs_n = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    val_n = conn.execute("SELECT COUNT(*) FROM validations").fetchone()[0]
    fb_n = conn.execute("SELECT COUNT(*) FROM lexical_feedback").fetchone()[0]
    corr_n = conn.execute("SELECT COUNT(*) FROM validations WHERE is_correct=0").fetchone()[0]

    print("Seed gerado com sucesso:", str(SEED_PATH))
    print("  Jobs              :", jobs_n, "(result_json removido para LGPD)")
    print("  Validacoes totais :", val_n)
    print("  Com correcao      :", corr_n)
    print("  Feedback lexical  :", fb_n)
    print()
    print("Proximo passo:")
    print("  git add seed/otto_ocr_seed.db")
    print("  git commit -m 'Seed: validacoes aprovadas pre-deploy'")
    print("  git push github master")
    print("  → Manual Deploy no Render")

finally:
    conn.close()
