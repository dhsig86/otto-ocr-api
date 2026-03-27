import requests
import time
import json
from PIL import Image, ImageDraw, ImageFont
import io

API_URL = "https://otto-ocr-api.onrender.com"

LAUDOS = [
    {
        "id": "laudo_1_pasteur",
        "tipo_esperado": "tomografia",
        "texto": """HOSPITAL PASTEUR    totalcare diagnosticos
Nome: Carlos Teste da Silva
ID Paciente: HPT-109053
Data do Exame: 11/24/2025
Data de Nascimento: 5/17/1965
Medico Solicitante: EVELYN MIRANDA ARAUJO

TOMOGRAFIA COMPUTADORIZADA DOS SEIOS DA FACE

Técnica:
Foram obtidas imagens sem contraste.

Análise:
Exame anterior de 10/07/2023.
Osteossintese metálica na parede anterior do seio maxilar esquerdo / rebordo orbitário, inalterada.
Extensas irregularidades nos ossos nasais, notadamente no esquerdo.
Também se observam irregularidades na porção anterossuperior óssea do septo nasal.
Marcada proximidade das asas do nariz com o septo nasal sugerindo a possibilidade de insuficiência de cartilagens alares, e eventualmente podendo estar associada a sinéquias.
Septo nasal apresenta desvio angular para a direita com esporão ósseo ipsilateral no terço médio. O esporão comprime o corneto inferior direito.
Recessos olfatórios livres.
Fossas olfatórias sem assimetrias significativas, com profundidade estimada em cerca de 7mm à direita e 8mm à esquerda no plano dos canais etmoidais anteriores.
Vias de drenagem livres.
Discreto espessamento mucoso nas cavidades frontais e em algumas células etmoidais anteriores.
Restante das cavidades paranasais normoaeradas.

Impressão:
Sinais sugestivos de sequelas de fratura envolvendo a zona k do nariz e do septo nasal, com possível insuficiência de válvulas nasais / cartilagens alares e sinéquias.
Desvio do septo nasal.
Osteossíntese metálica no rebordo orbitário esquerdo.

Liberado por: Dra. Anna Patricia de Freitas Linhares Riello - CRM 5254574-9 RJ"""
    },
    {
        "id": "laudo_2_proecho",
        "tipo_esperado": "tomografia",
        "texto": """ProEcho DIAGNOSTICOS
Nome: Jonildes Moura Teste Palmer
Data de Nasc: 22/04/1959
Medico: DARIO HART SIGNORINI - CRM 980722
Data da Ficha: 21/05/2025

TOMOGRAFIA COMPUTADORIZADA DA FACE

ASPECTOS TÉCNICOS:
Aquisição helicoidal multislice, com reconstruções multiplanares, sem o meio de contraste venoso.

ASPECTOS OBSERVADOS:
Espessamento mucoso do seio esfenoidal e dos seios maxilares, principalmente das suas regiões inferiores.
Velamento de quase todas as células etmoidais devido espessamento mucoso.
Obliteração das vias de drenagem inclusive dos recess frontoetmoidais.
Cavidades paranasais com paredes ósseas íntegras.
Seios frontais normotransparentes.
Meatos nasais médios e inferiores livres.
Meato nasal superior obliterado por secreção/espessamento mucoso.
Coluna aérea da rinofaringe com amplitude preservada.
Septo nasal centrado.

Liberado por: CRM-RJ:1036858 - PHELLIPE PROENCE PEREIRA DE QUEIROZ"""
    }
]

def criar_imagem_laudo(texto: str) -> bytes:
    """Gera uma imagem PNG com o texto do laudo em fonte legível para o OCR."""
    linhas = texto.strip().splitlines()
    w, h = 900, max(600, len(linhas) * 24 + 60)
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    y = 20
    for linha in linhas:
        d.text((20, y), linha, fill=(0, 0, 0))
        y += 22
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

def testar_laudo(laudo: dict) -> dict:
    nome = laudo["id"]
    print(f"\n{'='*55}")
    print(f"TESTANDO: {nome.upper()}")
    print(f"  Tipo esperado: {laudo['tipo_esperado']}")
    print("="*55)

    img_bytes = criar_imagem_laudo(laudo["texto"])

    # Upload
    files = {"file": (f"{nome}.png", img_bytes, "image/png")}
    r = requests.post(f"{API_URL}/ocr/upload", files=files)
    if r.status_code != 200:
        return {"erro": f"Upload falhou: {r.status_code} {r.text[:100]}"}

    job_id = r.json().get("job_id")
    print(f"  Ticket: {job_id}")

    # Polling
    for i in range(25):
        res = requests.get(f"{API_URL}/ocr/{job_id}/result").json()
        status = res.get("status")
        msg = res.get("message", "")
        print(f"  [{i+1:02d}] {status} | {msg}")
        if status == "completed":
            return res.get("result", {})
        elif status == "failed":
            return {"erro": res.get("message")}
        time.sleep(4)
    return {"erro": "Timeout"}

resultados = {}

for laudo in LAUDOS:
    resultado = testar_laudo(laudo)
    resultados[laudo["id"]] = {
        "tipo_esperado": laudo["tipo_esperado"],
        "resultado": resultado
    }

# Salva os resultados em JSON
with open("resultados_ocr.json", "w", encoding="utf-8") as f:
    json.dump(resultados, f, ensure_ascii=False, indent=2)

print("\n\n" + "="*55)
print("RESUMO EXECUTIVO DOS TESTES OCR")
print("="*55)

for lid, data in resultados.items():
    r = data["resultado"]
    if "erro" in r:
        print(f"\n[{lid}] ❌ ERRO: {r['erro']}")
        continue

    print(f"\n[{lid}]")
    print(f"  patient_token : {r.get('patient_token', 'N/A')}")
    print(f"  exam_type     : {r.get('exam_type', 'N/A')}  (esperado: {data['tipo_esperado']})")
    print(f"  exam_label    : {r.get('exam_label', 'N/A')}")
    print(f"  motor OCR     : {'Tesseract' if r.get('was_raster_engine_used') else 'PDF Nativo'}")
    print(f"  chars extraídos: {r.get('raw_text_length', 0)}")
    print(f"  NLP entities  : {r.get('entities_found', {})}")

    ci = r.get("clinical_interpretation", {})
    if "error" in ci:
        print(f"  GPT           : Mockado (sem API Key) - {ci.get('summary','')[:80]}")
    else:
        print(f"\n  --- GPT SUMMARY ---")
        print(f"  {ci.get('summary','')}")
        print(f"\n  --- FINDINGS ---")
        for f_item in ci.get("findings", []):
            print(f"    • {f_item}")
        print(f"\n  --- DIAGNOSTICS ---")
        for d_item in ci.get("diagnostics", []):
            print(f"    • {d_item}")

print("\n\nResultados completos salvos em: resultados_ocr.json")
