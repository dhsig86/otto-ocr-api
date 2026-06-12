# OTTO OCR — CLAUDE.md

> Contexto operacional para agentes LLM. Atualizado: 2026-06-03.

---

## O que é este módulo

Microserviço de OCR e interpretação clínica de laudos médicos ORL. Pipeline completo:

1. **Extração** — Texto nativo de PDF (`PyPDF2`) ou rasterizado via `pytesseract` com 4 estratégias em cascata
2. **LGPD** — Separação header/body, remoção de PII (CPF, RG, nome, CRM, convênio, data nascimento), tokenização anônima de paciente
3. **Classificação** — Identificação automática do tipo de exame por scoring regex (9 tipos, incluindo subtipos de TC)
4. **NLP heurístico** — Extração de entidades específicas (limiares dB de audiometria, latências de BERA)
5. **Interpretação GPT** — Análise clínica via GPT-4o-mini com Structured Outputs, enriquecida por knowledge base lexical (termos discriminativos + diagnósticos compostos)

**Regra 9 do OTTO:** OCR é SEMPRE opcional. Nunca obrigatório. Nunca pode quebrar o output.

---

## Deploy

| Camada | Plataforma | URL |
|--------|-----------|-----|
| Backend (API + OCR) | Heroku (Docker) | `https://otto-ocr-api-*.herokuapp.com` |

Deploy via `heroku.yml` → Docker build. Sem frontend dedicado — servido pelo próprio FastAPI (`static/index.html` ou `ocr_review.html`).

---

## Build & Test Commands

```bash
# Instalar dependências Python
pip install -r requirements.txt

# Dependências de sistema (Tesseract + Poppler — necessários para OCR e pdf2image)
# macOS:   brew install tesseract tesseract-lang poppler
# Debian:  apt-get install tesseract-ocr tesseract-ocr-por poppler-utils
# Windows: choco install tesseract poppler

# Rodar servidor local
uvicorn main:app --reload --port 8005

# Rodar testes automatizados (Pytest)
python -m pytest tests/

# Rodar testes manuais locais adicionais
python test_ocr_api.py
python test_ocr_real.py
python test_batch_laudos.py
python test_ocr_header.py
```

Não há linter ou typecheck configurado (projeto Python puro sem mypy).

---

## Estrutura de Pastas

```
OTTO OCR/
├── main.py                          ← FastAPI app: CORS, middleware CSP, rotas, pipeline assíncrono
├── core/
│   ├── security.py                  ← LGPD: strip_pii_from_text(), extract_and_strip_header(),
│   │                                   generate_patient_token(), extract_exam_date()
│   └── database.py                  ← SQLite: init_db(), CRUD de jobs + validations + lexical_feedback
├── services/
│   ├── extractor.py                 ← PdfExtractor: PyPDF2, detecta PDF nativo vs raster
│   ├── ocr_engine.py                ← OCRBaseEngine: 4 estratégias Tesseract em cascata
│   ├── exam_classifier.py           ← ExamClassifier: scoring regex para 9 tipos de exame
│   ├── nlp_parser.py                ← NLPParser: heurísticas de audiometria e BERA
│   └── gpt_bridge.py                ← GPTSummarizer: prompts especializados por exame + Structured Outputs
├── middleware/
│   └── require_auth.py              ← verify_firebase_token(): FastAPI Dependency
├── knowledge/
│   ├── lexical_kb.json              ← Base de termos discriminativos por tipo de exame
│   └── orl_lexicon_supplement.json  ← Suplemento lexical ORL expandido
├── seed/                            ← Seed do SQLite para preservar dados entre deploys
├── static/                          ← Frontend estático (index.html mobile-first)
├── ocr_review.html                  ← Frontend legado (considerar remoção)
├── docs/                            ← GitHub Pages frontend (CNAME: ocr.drdariohart.com)
├── Dockerfile                       ← python:3.11-slim + tesseract-ocr + poppler-utils
├── heroku.yml                       ← build.docker.web: Dockerfile
├── vercel.json                      ← CSP: frame-ancestors restrito a origens do ecossistema
├── requirements.txt                 ← 10 dependências (pinadas com ranges)
├── atualizar_kb.py                  ← Script utilitário para atualizar lexical_kb.json
├── exportar_dataset_treinamento.py  ← Exporta dados validados para MLOps
├── preparar_seed.py                 ← Gera seed limpo do banco
├── ver_banco.py                     ← Utilitário para inspecionar SQLite
├── update_estado.py                 ← Utilitário de migração de estados
├── test_ocr_api.py                  ← Testes de API
├── test_ocr_real.py                 ← Testes com laudos reais
├── test_batch_laudos.py             ← Testes em batch
└── test_ocr_header.py              ← Teste de extração de cabeçalho
```

---

## API — Endpoints

### `GET /ping`
Diagnóstico de saúde — retorna versão e caminhos de arquivos estáticos.

### `POST /ocr/upload` 🔒 Firebase Auth
Inicia extração assíncrona de laudo médico.

```
Content-Type: multipart/form-data
Authorization: Bearer <firebase_id_token>

campo: file (PDF ou imagem JPG/PNG)

Response:
{
  "job_id": "uuid",
  "status": "queued"
}
```

### `GET /ocr/{job_id}/result`
Polling do resultado do processamento. Público (sem auth).

```json
{
  "job_id": "...",
  "patient_token": "pt-abc123def456",
  "exam_type": "audiometria",
  "status": "completed",
  "message": "Processamento finalizado.",
  "result": {
    "patient_token": "pt-abc123def456",
    "exam_date": "2024-01-06",
    "exam_type": "audiometria",
    "exam_label": "Audiometria Tonal/Vocal",
    "was_raster_engine_used": false,
    "raw_text_length": 1250,
    "safe_text_snippet": "...",
    "entities_found": { "decibeis_encontrados": ["25", "30", "40"] },
    "clinical_interpretation": {
      "is_valid_exam": true,
      "summary": "...",
      "findings": ["..."],
      "normal_standards": "...",
      "diagnostics": ["..."],
      "succinct_insight": "..."
    }
  }
}
```

Status possíveis: `queued` → `processing` → `completed` | `low_confidence` | `failed`

### `POST /ocr/{job_id}/validate` 🔒 Firebase Auth
Feedback médico para retroalimentação lexical.

```json
{
  "is_correct": false,
  "corrections": "O diagnóstico correto é perda mista bilateral"
}
```

### `GET /ocr/stats`
Estatísticas de validações para monitoramento do enriquecimento lexical. Público.

### `GET /ocr/db/export` 🔒 Admin Token
Exporta banco SQLite para backup. Header `X-Admin-Token` obrigatório.

### `GET /health`
Health check padrão.

---

## Pipeline assíncrono — `process_job()`

```
Upload →
  Etapa 1: Extração de texto
    ├─ PDF nativo → PyPDF2 → texto
    └─ PDF raster ou imagem → OCRBaseEngine (4 estratégias em cascata)
  
  Etapa 2: LGPD
    ├─ extract_and_strip_header() → separa header (PII) do body (clínico)
    ├─ extract_exam_date() → data do exame (metadado, não PII)
    ├─ generate_patient_token() → hash SHA-256 do header → "pt-xxxxxx"
    └─ strip_pii_from_text() → CPF, RG, nome, CRM, convênio removidos
  
  Guarda de Confiança: body < 80 caracteres → status "low_confidence" → PARA
  
  Etapa 3: Classificação → ExamClassifier.classify() → scoring regex
  
  Etapa 4: NLP → NLPParser.enrich_with_heuristics() → entidades por tipo
  
  Etapa 5: GPT → GPTSummarizer.summarize()
    ├─ Prompt base especializado (9 tipos)
    ├─ + Vocabulário lexical_kb.json (termos discriminativos peso ALTO)
    ├─ + Diagnósticos compostos (ex: espessamento + nível líquido → agudizada)
    └─ → GPTAnalysisResult (Structured Outputs / Pydantic)
```

---

## Motor OCR — 4 Estratégias em Cascata

| # | Estratégia | Descrição | Melhor para |
|---|-----------|-----------|-------------|
| 1 | `_strategy_original` | Imagem RGB original, DPI 200 | Screenshots e docs digitais |
| 2 | `_strategy_enhanced` | Grayscale + contraste 1.8 + sharpen | PDFs escaneados |
| 3 | `_strategy_binarize` | Binarização agressiva + contraste 2.5 | Fotos de celular |
| 4 | `_strategy_sparse` | PSM 11 (sparse text) | Tabelas/audiogramas |

Seleção: roda as 4 e retorna a com mais caracteres (`max(results, key=len)`).

---

## Tipos de Exame Suportados

| Tipo | Label | Classificador |
|------|-------|---------------|
| `audiometria` | Audiometria Tonal/Vocal | kHz, dB, audiograma |
| `bera` | BERA (Potencial Evocado Auditivo) | onda I/III/V, latência |
| `videolaringoscopia` | Videolaringoscopia / Nasofibrolaringoscopia | prega vocal, laringe |
| `endoscopia_nasal` | Videoendoscopia Nasal | meato, corneto, septo |
| `tomografia_mastoide` | TC de Mastóide / Ossos Temporais | cadeia ossicular, colesteatoma |
| `tomografia_pescoco` | TC de Pescoço | parofaríngeo, parótida, cisto branquial |
| `tomografia` | TC de Seios da Face | seio maxilar/etmoidal, complexo ostiomeatal |
| `polissonografia` | Polissonografia | IAH, apneia, sono REM |
| `generico` | Exame Otorrinolaringológico (Não Identificado) | fallback |

> Subtipos de TC (`tomografia_mastoide`, `tomografia_pescoco`) são avaliados **antes** do `tomografia` genérico para maior especificidade.

---

## Banco de Dados — SQLite

Path: `./otto_ocr.db` (configurável via `SQLITE_DB_PATH` env var).

### Tabelas

| Tabela | Colunas principais | Propósito |
|--------|-------------------|-----------|
| `jobs` | job_id, patient_token, filename, exam_type, status, message, result_json, file_path, validation_status | Rastreio de OCR jobs |
| `validations` | job_id, patient_token, exam_type, is_correct, corrections | Feedback médico |
| `lexical_feedback` | exam_type, original_text, corrected_text, source_job_id | Enriquecimento do léxico |

Mecanismo de seed: se o banco não existe no deploy, copia de `seed/otto_ocr_seed.db` para preservar validações médicas entre deploys.

---

## Knowledge Base Lexical

2 arquivos de vocabulário clínico injetados nos prompts GPT:
- **`lexical_kb.json`** — Termos discriminativos por tipo de exame
- **`orl_lexicon_supplement.json`** — Suplemento lexical ORL expandido

Estrutura por tipo de exame:
- `achados_discriminativos[]` — termos com peso (ALTO/MÉDIO/BAIXO), variantes e significado clínico
- `diagnosticos_compostos[]` — regras compostas (ex: espessamento + nível líquido → sinusite crônica agudizada)

Exames com KB rica: tomografia (11 termos, 3 compostos), polissonografia (11 termos), audiometria (4 termos), videolaringoscopia (3 termos).

---

## Segurança & Auth

### Firebase Auth
- **Dependency:** `middleware/require_auth.py → verify_firebase_token()`
- **Auth dual:** Firebase Bearer token OU `X-Internal-Key` (server-to-server entre triagem → OCR)
- **Env vars:** `FIREBASE_CREDENTIALS_JSON` (prioridade, JSON inline) ou `GOOGLE_APPLICATION_CREDENTIALS` (path)
- **Endpoints protegidos:** `POST /ocr/upload`, `POST /ocr/{job_id}/validate`
- **Endpoints públicos:** `GET /ocr/{job_id}/result`, `GET /ocr/stats`, `GET /ping`, `GET /health`
- **Endpoint admin:** `GET /ocr/db/export` — protegido por `X-Admin-Token` header (env var `ADMIN_TOKEN`, retorna 503 se não configurado)
- `uid` extraído SEMPRE do token Firebase verificado, NUNCA do request body ✅

### CORS
Allowlist explícita com ~20 origens — NÃO usa `*`. Configurado em `main.py`:
- Domínios customizados: `otto.drdariohart.com`, `ocr.drdariohart.com`, `procod.drdariohart.com`, `atlas.drdariohart.com`, `cases.drdariohart.com`
- Vercel: `ottopwa.vercel.app`, `otto-pwa.vercel.app`, `ottos-plum.vercel.app`, `otto-calc-hub.vercel.app`, `otto-imune.vercel.app`, `otto-voice-one.vercel.app`, `bottok-orcin.vercel.app`, `test-pg-bice.vercel.app`, `otto-ocr-web.vercel.app`
- Firebase Hosting: `otto-ecosystem.web.app`, `otto-ecosystem.firebaseapp.com`
- Heroku/Netlify/GitHub: `otto-ai-triagem-*.herokuapp.com`, `otto-whisper.netlify.app`, `dhsig86.github.io`
- Localhost: `3000`, `5173`, `8000` (+ variantes `127.0.0.1`)

### CSP — frame-ancestors (corrigido ✅)
- **`main.py`:** `frame-ancestors 'self' https://otto.drdariohart.com https://ottopwa.vercel.app https://ottos-plum.vercel.app`
- **`vercel.json`:** Alinhado com as mesmas origens explícitas
- Conforme regra de segurança do ecossistema (sem `*`)

### LGPD
- Header do laudo (PII) é separado do body ANTES de qualquer processamento
- PII removida: CPF, RG, nome (hash anônimo), data nascimento, convênio, CRM
- `patient_token` é hash SHA-256 determinístico do header — mesmo paciente sempre gera mesmo token, sem armazenar nome
- Arquivo cru do upload é armazenado em `uploads/` para esteira MLOps (verificar se está em .gitignore ✅)

---

## Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|----------|------------|-----------|
| `OPENAI_API_KEY` | ✅ | Chave da API OpenAI para GPT-4o-mini |
| `FIREBASE_CREDENTIALS_JSON` | ✅ prod | JSON inline do service account Firebase |
| `GOOGLE_APPLICATION_CREDENTIALS` | alt. | Path para arquivo .json do service account |
| `ADMIN_TOKEN` | Não | Token para `GET /ocr/db/export` (retorna 503 se não configurado — sem default inseguro) |
| `SQLITE_DB_PATH` | Não | Path do banco SQLite (default: `./otto_ocr.db`) |

---

## Dependências principais

```
fastapi, uvicorn, python-multipart, pydantic
PyPDF2                      ← extração de texto de PDF nativo
pytesseract                 ← OCR via Tesseract
pdf2image                   ← conversão PDF→imagem (requer poppler)
Pillow                      ← manipulação de imagem (contraste, binarização)
openai                      ← GPT-4o-mini (AsyncOpenAI, Structured Outputs)
firebase-admin              ← autenticação Firebase
```

> Todas as dependências pinadas com ranges mínimo+máximo no `requirements.txt`.

**Dependências de sistema (Docker):** tesseract-ocr, tesseract-ocr-por, poppler-utils.

---

## Consumidores

- **OTTOPROCOD:** `OcrScanner.jsx` — lê carteirinha de plano de saúde via `VITE_OCR_BASE_URL`
- **OTTO PWA:** Pode embutir o frontend de revisão via iframe
- **Outros módulos:** Qualquer módulo autenticado pode chamar `POST /ocr/upload` com Bearer token

---

## GPT Structured Output — Schema

```python
class GPTAnalysisResult(BaseModel):
    is_valid_exam: bool     # False se texto ilegível (lixo de OCR)
    summary: str            # Resumo clínico de 3-5 linhas
    findings: list[str]     # Achados relevantes (máx 8)
    normal_standards: str   # Elementos dentro da normalidade (1 linha)
    diagnostics: list[str]  # Diagnósticos diferenciais sugeridos
    succinct_insight: str   # 1-2 frases para prontuário
```

---

## Git & Deploy

```bash
cd "OTTO OCR" && git push origin main
```

Heroku faz autodeploy via `heroku.yml` → Docker build no push em `main`.

---

## Pontos de Atenção para Curadoria

1. ~~**`frame-ancestors *`**~~ — ✅ Corrigido
2. ~~**`pdfminer.six` e `spacy` fantasmas**~~ — ✅ Removidas (nunca estiveram no requirements.txt real)
3. ~~**`ADMIN_TOKEN` default inseguro**~~ — ✅ Corrigido: retorna 503 se não configurado
4. ~~**Debris e .gitignore insuficiente**~~ — ✅ Resolvido: 8 debris removidos, .gitignore expandido
5. ~~**Dependências unpinned**~~ — ✅ Resolvido: todas pinadas com ranges
6. **Uploads persistidos** em `uploads/` — policy de retenção LGPD de 7 dias implementada via `@app.on_event("startup")`
7. **Testes Automatizados:** Suíte de testes configurada com Pytest na pasta `tests/` validando conformidade com a LGPD/remoção de PII e integridade das rotas do FastAPI.
8. **3 frontends coexistindo** — `static/index.html` (principal), `ocr_review.html` (legado), `docs/index.html` (GitHub Pages) — considerar consolidação
9. **Frontends HTML não enviam Bearer token** — upload pelo frontend estático falhará com 401 (backend correto, frontend incompleto)
