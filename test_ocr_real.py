import requests
import time
import sys
import os

# Aceita o caminho da imagem como argumento via linha de comando
if len(sys.argv) < 2:
    print("Uso: python test_ocr_real.py <caminho_para_imagem>")
    print("Exemplo: python test_ocr_real.py C:\\Users\\drdhs\\Downloads\\tomografia.jpg")
    sys.exit(1)

IMAGE_PATH = sys.argv[1]
API_URL = "https://otto-ocr-api.onrender.com"

if not os.path.exists(IMAGE_PATH):
    print(f"ERRO: Arquivo nao encontrado em: {IMAGE_PATH}")
    sys.exit(1)

filename = os.path.basename(IMAGE_PATH)
ext = filename.split('.')[-1].lower()
mime_type = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

print("=" * 55)
print("   OTTO OCR — Teste E2E com Laudo Real no Render")
print("=" * 55)
print(f"Imagem: {filename}")
print(f"Tamanho: {os.path.getsize(IMAGE_PATH) // 1024} KB")
print()

# 1. Upload
print("1. Enviando imagem para a API no Render...")
try:
    with open(IMAGE_PATH, "rb") as f:
        files = {"file": (filename, f, mime_type)}
        response = requests.post(f"{API_URL}/ocr/upload", files=files)
    
    if response.status_code != 200:
        print(f"Erro no upload! Status: {response.status_code}")
        print(f"Body: {response.text[:300]}")
        sys.exit(1)
    
    data = response.json()
    job_id = data.get("job_id")
    print(f"   Ticket gerado: {job_id}")

    # 2. Polling
    print("\n2. Aguardando processamento (OCR + LGPD + GPT)...")
    for attempt in range(20):
        res = requests.get(f"{API_URL}/ocr/{job_id}/result").json()
        status = res.get("status")
        msg = res.get("message", "")
        print(f"   [{attempt+1:02d}] {status} | {msg}")
        
        if status == "completed":
            r = res.get("result", {})
            print("\n" + "=" * 55)
            print("RESULTADO EXTRADO PELO OTTO OCR")
            print("=" * 55)

            print(f"\nMotor OCR Utilizado: {'Tesseract' if r.get('was_raster_engine_used') else 'PDF Nativo'}")
            print(f"Texto total extraído: {r.get('raw_text_length', 0)} caracteres")

            print("\n--- TEXTO HIGIENIZADO (LGPD) ---")
            print("Nomes, CPF, RG e Convênio devem estar mascarados:")
            print(r.get("safe_text_snippet", ""))

            print("\n--- ENTIDADES EXTRAÍDAS (NLP) ---")
            print(r.get("entities_found", {}))

            print("\n--- INTERPRETAÇÃO CLÍNICA (GPT) ---")
            import json
            ci = r.get("clinical_interpretation", {})
            if "error" in ci:
                print("GPT offline (sem OPENAI_API_KEY no Render). Configure-a no Painel do Render!")
            else:
                print(json.dumps(ci, indent=2, ensure_ascii=False))
            break

        elif status == "failed":
            print(f"\nERRO NO SERVIDOR: {res.get('message')}")
            break
        
        time.sleep(4)
    else:
        print("Timeout: o servidor demorou mais de 80 segundos.")

except Exception as e:
    print(f"\nExcecao ao contactar API: {e}")
