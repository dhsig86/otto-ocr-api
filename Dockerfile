# Usa uma imagem oficial leve do Python (Debian)
FROM python:3.11-slim

# Variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Instala as dependências do sistema operacional cruciais para o módulo
# Tesseract (Open Source OCR engine)
# tesseract-ocr-por (Pacote de linguagem Português)
# poppler-utils (Motor de PDF requerido para transformar páginas em imagens rasterizadas)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-por \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Configura o diretório da nossa aplicação
WORKDIR /app

# Instala as bibliotecas de Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copia os serviços, API e core para o container
COPY . /app/

# A porta padrão que o provedor em nuvem procurará
EXPOSE 8000

# Script de boot da aplicação lidando com porta dinâmica do Heroku
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
