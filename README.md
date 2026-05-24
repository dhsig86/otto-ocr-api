# OTTO OCR — Microserviço de OCR e Interpretação de Laudos ORL

> Módulo do ecossistema **AOTTO** para extração, anonimização e interpretação assistida por IA de laudos médicos otorrinolaringológicos.

---

## 🎯 Proposta Clínica

No consultório de ORL, o médico frequentemente recebe laudos de exames em formato impresso, PDF escaneado ou foto de celular. Interpretar e transcrever manualmente esses laudos consome tempo e está sujeito a erros de transcrição.

O **OTTO OCR** automatiza esse processo:

1. **Extrai o texto** do laudo (PDF nativo ou imagem escaneada)
2. **Remove dados pessoais** do paciente (LGPD compliance)
3. **Identifica o tipo de exame** automaticamente
4. **Interpreta clinicamente** os achados usando GPT-4o-mini com vocabulário especializado em ORL
5. **Gera um resumo estruturado** pronto para prontuário

> ⚠️ **Regra 9 do OTTO:** O OCR é sempre opcional. Nunca obrigatório para o fluxo clínico. Nunca pode quebrar o output de outros módulos.

---

## 🔬 Tipos de Exame Suportados

| Exame | O que o OCR extrai e interpreta |
|-------|--------------------------------|
| **Audiometria** | Limiares tonais por frequência, tipo e grau de perda auditiva (condutiva/neurossensorial/mista), gap osteoacústico |
| **BERA** | Latências absolutas e interpico das ondas I, III e V; suspeita de neuropatia auditiva |
| **Videolaringoscopia** | Achados em pregas vocais, aritenóides, epiglote; nódulos, pólipos, edema, paralisia vocal |
| **Videoendoscopia Nasal** | Meatos, cornetos, septo, fossas nasais, coanas; sinusite, polipose, adenoide |
| **Tomografia (TC/TCFC)** | Variantes anatômicas (curvatura paradoxal, concha bolhosa, esporão septal), obstruções de drenagem, espessamento mucoso |
| **Polissonografia** | IAH, eficiência do sono, arquitetura (N1-N3, REM), oximetria, ronco, classificação de apneia |
| **Exame Genérico** | Qualquer laudo ORL não reconhecido — análise geral de achados |

---

## 🧠 Inteligência Clínica

### Base de Conhecimento Lexical

O OTTO OCR possui uma base de vocabulário clínico curado (`lexical_kb.json`) que é injetada nos prompts de IA. Isso garante que a interpretação não omita:

- **Termos discriminativos de peso ALTO** — ex: "infundíbulo etmoidal obliterado", "curvatura paradoxal do corneto", "gap osteoacústico > 15 dB"
- **Diagnósticos compostos** — ex: espessamento mucoso + nível líquido → **sinusite crônica agudizada** (não apenas "sinusite crônica")

### Feedback Médico

Após cada interpretação, o médico pode validar ou corrigir o resultado. As correções são armazenadas e alimentam o enriquecimento contínuo do vocabulário clínico.

---

## 📋 Recursos Principais

- **Pipeline de 5 etapas:** Extração → LGPD → Classificação → NLP → GPT-4o-mini
- **4 estratégias de OCR em cascata:** otimizadas para screenshots, PDFs escaneados, fotos de celular e tabelas/audiogramas
- **Anonimização LGPD:** CPF, RG, nome, CRM, convênio e data de nascimento são removidos automaticamente antes de qualquer processamento
- **Token de paciente:** hash determinístico que permite rastreabilidade sem armazenar dados pessoais
- **Interpretação estruturada:** resumo clínico, achados, elementos normais, diagnósticos diferenciais e insight para prontuário
- **Guarda de confiança:** se o OCR extraiu menos de 80 caracteres, o sistema sinaliza baixa confiança em vez de alucinações
- **Validação médica:** feedback do médico persiste em banco de dados para retroalimentação do sistema

---

## 🖥️ Instalação e Desenvolvimento Local

### Pré-requisitos

- Python 3.11+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) instalado no sistema
- [Poppler](https://poppler.freedesktop.org/) instalado (necessário para `pdf2image`)

```bash
# macOS
brew install tesseract tesseract-lang poppler

# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-por poppler-utils

# Windows
choco install tesseract poppler
```

### Rodar localmente

```bash
cd "OTTO OCR"

# Criar e ativar virtualenv
python -m venv venv
# Linux/macOS: source venv/bin/activate
# Windows: venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
# Criar .env com:
#   OPENAI_API_KEY=sk-...
#   FIREBASE_CREDENTIALS_JSON={"type":"service_account",...}

# Iniciar servidor
uvicorn main:app --reload --port 8005
```

O servidor estará disponível em `http://localhost:8005`.

### Testar

```bash
python test_ocr_api.py       # Testes de API
python test_ocr_real.py       # Testes com laudos reais
python test_batch_laudos.py   # Testes em batch
```

---

## 🚀 Deploy em Produção

O OTTO OCR utiliza Docker deploy no Heroku:

```bash
# Push para branch main → autodeploy via heroku.yml
cd "OTTO OCR"
git push origin main
```

### Variáveis de ambiente (Heroku Dashboard)

| Variável | Descrição |
|----------|-----------|
| `OPENAI_API_KEY` | Chave API OpenAI |
| `FIREBASE_CREDENTIALS_JSON` | JSON do service account Firebase |
| `ADMIN_TOKEN` | Token para exportação do banco de dados |

O `Dockerfile` já inclui instalação de `tesseract-ocr`, `tesseract-ocr-por` e `poppler-utils`.

---

## 🔗 Integração com o Ecossistema

| Módulo | Como usa o OCR |
|--------|---------------|
| **OTTOPROCOD** | Leitura de carteirinhas de plano de saúde (`OcrScanner.jsx`) |
| **OTTO PWA** | Pode embutir via iframe a interface de revisão |
| **Qualquer módulo autenticado** | Chamada direta via `POST /ocr/upload` com Bearer token Firebase |

---

## ⚕️ Conformidade

- **LGPD:** Dados pessoais removidos antes de qualquer processamento ou armazenamento
- **CFM:** Interpretações são sugestivas — "Não dê recomendações médicas definitivas" está no prompt de todas as análises
- **Auditabilidade:** patient_token + job_id permitem rastreio sem exposição de PII

---

*Desenvolvido por Dr. Dario Hart Signorini — dr.dhsig@gmail.com*
