import sqlite3
import json

conn = sqlite3.connect('otto_ocr_backup.db')
conn.row_factory = sqlite3.Row

print('=' * 60)
print('JOBS')
print('=' * 60)
for j in conn.execute('SELECT job_id, filename, exam_type, status, patient_token, created_at FROM jobs ORDER BY created_at DESC').fetchall():
    print('  [' + str(j['status']) + '] ' + str(j['exam_type']) + ' | ' + str(j['patient_token']) + ' | ' + str(j['created_at']))

print()
print('=' * 60)
print('VALIDACOES')
print('=' * 60)
for v in conn.execute('SELECT job_id, exam_type, is_correct, corrections, validated_at FROM validations ORDER BY validated_at DESC').fetchall():
    status = 'CORRETO' if v['is_correct'] else 'CORRIGIDO'
    print('  [' + status + '] ' + str(v['exam_type']) + ' | ' + str(v['validated_at']))
    if v['corrections']:
        print('  >> ' + str(v['corrections']))

print()
print('=' * 60)
print('LEXICAL FEEDBACK (' + str(conn.execute('SELECT COUNT(*) FROM lexical_feedback').fetchone()[0]) + ' entradas)')
print('=' * 60)
for f in conn.execute('SELECT exam_type, original_text, corrected_text, created_at FROM lexical_feedback ORDER BY created_at DESC').fetchall():
    print('  Tipo: ' + str(f['exam_type']) + ' | ' + str(f['created_at']))
    print('  ORIGINAL : ' + str(f['original_text'])[:120])
    print('  CORRIGIDO: ' + str(f['corrected_text'])[:120])
    print()

conn.close()
