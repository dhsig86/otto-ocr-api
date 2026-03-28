"""
atualizar_kb.py — Script local para gerar patches da Knowledge Base a partir das validações médicas.

Uso: python atualizar_kb.py [banco.db]

Le as entradas de lexical_feedback no banco SQLite e sugere termos para adicionar à KB.
"""
import sqlite3
import json
import sys
from pathlib import Path
from collections import Counter

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "otto_ocr_backup.db"
KB_PATH = Path("knowledge/lexical_kb.json")

if not Path(DB_PATH).exists():
    print("Banco nao encontrado:", DB_PATH)
    sys.exit(1)

# Carregar KB atual
kb = {}
if KB_PATH.exists():
    with open(KB_PATH, encoding="utf-8") as f:
        kb = json.load(f)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print("=" * 60)
print("OTTO OCR — Gerador de Patches da Knowledge Base")
print("=" * 60)

# Estatísticas gerais
stats = conn.execute("""
    SELECT
        (SELECT COUNT(*) FROM jobs WHERE status='completed') as jobs_ok,
        (SELECT COUNT(*) FROM validations) as total_val,
        (SELECT COUNT(*) FROM validations WHERE is_correct=0) as corrigidos,
        (SELECT COUNT(*) FROM lexical_feedback) as feedback
""").fetchone()

print("\nEstatísticas do banco:")
print("  Jobs concluídos   :", stats['jobs_ok'])
print("  Total validacoes  :", stats['total_val'])
print("  Com correcao      :", stats['corrigidos'])
print("  Entradas de lexico:", stats['feedback'])

# Validacoes com correcao
print("\n" + "=" * 60)
print("CORRECOES MEDICAS REGISTRADAS")
print("=" * 60)
correcoes = conn.execute("""
    SELECT v.exam_type, v.corrections, v.validated_at, j.filename
    FROM validations v
    LEFT JOIN jobs j ON j.job_id = v.job_id
    WHERE v.is_correct = 0
    ORDER BY v.validated_at DESC
""").fetchall()

for c in correcoes:
    print("\n  Exame   :", c['exam_type'])
    print("  Arquivo :", c['filename'])
    print("  Data    :", c['validated_at'])
    print("  Correção:", c['corrections'])

# Feedback lexical
print("\n" + "=" * 60)
print("FEEDBACK LEXICAL (para enriquecimento da KB)")
print("=" * 60)
feedbacks = conn.execute("""
    SELECT exam_type, original_text, corrected_text, created_at
    FROM lexical_feedback ORDER BY created_at DESC
""").fetchall()

patch_suggestions = []
for fb in feedbacks:
    print("\n  Tipo     :", fb['exam_type'])
    print("  Data     :", fb['created_at'])
    print("  Original :", fb['original_text'][:120])
    print("  Corrigido:", fb['corrected_text'][:120])

    # Sugere termos potencialmente novos
    termos_kb = [t['termo'] for t in kb.get(fb['exam_type'], {}).get('achados_discriminativos', [])]
    correction = fb['corrected_text'].lower()
    for kw in ["infundíbulo", "corneto", "bolhosa", "paradoxal", "esporão", "obliteração"]:
        if kw in correction and not any(kw in t for t in termos_kb):
            patch_suggestions.append((fb['exam_type'], kw))

if patch_suggestions:
    print("\n" + "=" * 60)
    print("SUGESTÕES DE PATCH (termos mencionados nas correções)")
    print("mas NÃO encontrados na KB atual:")
    print("=" * 60)
    for exam, termo in set(patch_suggestions):
        print("  [" + exam + "] Considerar adicionar: '" + termo + "'")
    print("\nEdite knowledge/lexical_kb.json para incorporar esses termos.")
else:
    print("\nA KB já cobre todos os termos identificados nas correcoes.")

conn.close()
print("\nConcluido.")
