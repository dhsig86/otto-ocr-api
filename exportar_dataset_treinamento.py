"""
exportar_dataset_treinamento.py — Exporta imagens validadas com erro para retreinamento.

Filtra os jobs com validation_status='validated_with_errors', coleta as imagens 
salvas na pasta uploads/ e gera um .zip acompanhado da anotação médica.
"""
import sqlite3
import zipfile
import json
import os
from pathlib import Path

# Banco em ambiente de Produção ou Local
DB_ENV = os.getenv("SQLITE_DB_PATH")
DB_PATH = Path(DB_ENV) if DB_ENV else Path("otto_ocr_backup.db")

def main():
    if not DB_PATH.exists():
        print(f"Banco de dados {DB_PATH} não encontrado.")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    # Buscar validações com erros associadas a imagens salvas
    rows = conn.execute("""
        SELECT j.job_id, j.filename, j.file_path, v.corrections, v.exam_type
        FROM jobs j
        JOIN validations v ON j.job_id = v.job_id
        WHERE j.validation_status = 'validated_with_errors' AND j.file_path IS NOT NULL
    """).fetchall()

    if not rows:
        print("Nenhuma imagem com status 'validated_with_errors' foi encontrada na base de dados.")
        return

    out_zip = Path("dataset_retreinamento.zip")
    print(f"Encontradas {len(rows)} amostras de laudos que precisam de retreinamento de modelo.")
    
    metadata = []
    
    with zipfile.ZipFile(out_zip, 'w') as zf:
        for r in rows:
            fpath = Path(r['file_path'])
            if fpath.exists():
                # Zip a raw imagem
                zf.write(fpath, arcname=fpath.name)
                metadata.append({
                    "job_id": r['job_id'],
                    "filename": r['filename'],
                    "exam_type": r['exam_type'],
                    "corrections": r['corrections'],
                    "image_file": fpath.name
                })
            else:
                print(f"⚠️ Aviso: Arquivo original {fpath.name} não foi encontrado no disco local.")
                
        # Inclui o JSON de anotações médicas dentro do ZIP para a ferramenta de MLOps
        zf.writestr('metadata.json', json.dumps(metadata, indent=2, ensure_ascii=False))

    print(f"\\n✅ Exportação concluída com sucesso! Baixe o pacote para anotação em: {out_zip.absolute()}")

if __name__ == "__main__":
    main()
