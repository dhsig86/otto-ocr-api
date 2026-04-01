import sys

file_path = r'C:\Users\drdhs\.gemini\antigravity\brain\098929d2-1c7a-48cc-9284-9515de8d7c76\estado_atual_otto_ocr.md.resolved'

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    content = content.replace(
        '> **Versão:** 3.1.0 (Sprint 4 + Hotfix OCR Cascade)  \n> **Data:** 2026-03-27  \n> **Status:** Operacional em produção',
        '> **Versão:** 3.1.1 (Sprint 5 + Hotfix Header Failsafe & LGPD Hash)  \n> **Data:** 2026-03-27  \n> **Status:** Operacional em produção'
    )

    content = content.replace(
        '│  3. OCR (3 estratégias em cascata)          │\n│  4. LGPD: strip PII + patient_token SHA256  │\n│  5. ExamClassifier (regex por modalidade)   │',
        '│  3. OCR (3 estratégias em cascata)          │\n│  4. LGPD: strip PII + pseudonym hash        │\n│     * Failsafe anti-drop de cabeçalho       │\n│  5. ExamClassifier (regex por modalidade)   │'
    )

    content = content.replace(
        '| Remoção de PII | [extract_and_strip_header()](file:///C:/Users/drdhs/OneDrive/Documentos/OTTO%20OCR/core/security.py#20-53) remove cabeçalho com nome, data, médico |\n| Anonimização | `patient_token = sha256(header_raw)[:12]` — rastreável sem identificar |',
        '| Remoção de PII | `extract_and_strip_header()` remove o cabeçalho, possuindo um failsafe para não apagar o laudo todo |\n| Pseudonimização | Nomes identificados via RegEx são substituídos por um hash criptográfico curto (`[Paciente_1A2B3D]`) |\n| Anonimização | `patient_token = sha256(header_raw)[:12]` — rastreável sem identificar |'
    )

    content = content.replace(
        '| Sprint 5 | ⏳ | OCR em cascata (3 estratégias), integração OTTO Triagem (`ocr_context`) |',
        '| Sprint 5 | ✅ | OCR em cascata, integração OTTO Triagem (`ocr_context`), Failsafe LGPD e Hash Pseudonimizada (v3.1.1) |'
    )

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print('Arquivo atualizado com sucesso!')
except Exception as e:
    print('Erro:', e)
