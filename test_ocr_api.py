import requests
import time
from PIL import Image, ImageDraw, ImageFont
import io

print("Iniciando Teste Integrado com a API da OTTO OCR no Heroku...")

# 1. Cria uma imagem simulando um laudo médico
# Multiplicando tamanho da imagem e fonte para ajudar o Tesseract (OCR) a enxergar melhor
img = Image.new('RGB', (800, 300), color = (255, 255, 255))
d = ImageDraw.Draw(img)

texto_medico = """
CLINICA OTTO - LAUDO DE EXAME
Paciente: Joao da Silva Sauro
CPF: 123.456.789-00
Convenio: Unimed
Data de Nascimento: 12/05/1980

Exame: Audiometria Tonal
Orelha Esquerda: Limiares normais.
Orelha Direita: Apresentou rebaixamento, limiar de 60 dB em 4000Hz.
"""

# Usando o default font.
d.text((20, 20), texto_medico, fill=(0, 0, 0))

buf = io.BytesIO()
img.save(buf, format='PNG')
buf.seek(0)
print("1. Imagem de laudo gerada artificialmente (contendo CPF e Nomes restritos pela LGPD).")

# 2. Faz o Upload
url_upload = "https://mysterious-castle-16344.herokuapp.com/ocr/upload"
print(f"2. Disparando POST para {url_upload}...")
try:
    files = {'file': ('audiometria_teste.png', buf, 'image/png')}
    response = requests.post(url_upload, files=files)
    if response.status_code != 200:
        print(f"Erro na nuvem! Status: {response.status_code} | Body: {response.text[:200]}")
        exit()
        
    data = response.json()
    job_id = data.get("job_id")
    print(f"   -> Sucesso! Recebemos o Ticket de Processamento: {job_id}")
    
    # 3. Polling
    url_result = f"https://mysterious-castle-16344.herokuapp.com/ocr/{job_id}/result"
    print("3. Aguardando o Servidor ler a imagem, limpar o texto e formatar os dados (Polling)...")
    
    attempts = 0
    while attempts < 15:
        res = requests.get(url_result).json()
        status = res.get("status")
        msg = res.get("message")
        print(f"   [Ticket: {job_id}] | Status: {status} | Info: {msg}")
        
        if status == "completed":
            print("\n" + "="*50)
            print("🚀 RESULTADO FINAL DEVOLVIDO PELA API 🚀")
            print("="*50)
            
            resultado = res.get("result", {})
            print(f"Motor Raster Utilizado: {resultado.get('was_raster_engine_used')}")
            
            print("\n--- 1. TEXTO HIGIENIZADO (LGPD Strip) ---")
            print("Note que CPF, Nomes e Convênios devem desaparecer:")
            print(resultado.get("safe_text_snippet"))
            
            print("\n--- 2. NLP RULE-BASED (Extração de Dados Parametrizados) ---")
            print("Nosso regex deve encontrar o valor de decibéis da audiometria (60 dB):")
            print(resultado.get("entities_found"))
            
            print("\n--- 3. INTERPRETAÇÃO CLÍNICA GPT ---")
            print("Se você ainda não colocou sua API Key no Heroku, isso trará dados Mokados de emergência:")
            import json
            print(json.dumps(resultado.get("clinical_interpretation"), indent=2, ensure_ascii=False))
            break
            
        elif status == "failed":
            print("Falha crônica da API.")
            break
            
        time.sleep(3)
        attempts += 1
        
except Exception as e:
    print(f"Erro ao contactar API: {e}")
