import re
from core.security import extract_and_strip_header, strip_pii_from_text

text = """EXAME DE ENDOSCOPIA NASAL
Exame realizado com fibra rígida 30°
Anestesia e vasoconstritor tópicos: sim

Nome: Julia Montari Fonseca Marques              Data: 06/01/2021

NARIZ
Septo nasal: Septo Centrado. Desvio alto não obstrutiva.

Meatos Nasais:
Inferiores: Obstruídos por mucosa redundante.
"""

body_safe, header_raw = extract_and_strip_header(text)
print("--- BODY SAFE ---")
print(body_safe)
print("--- HEADER RAW ---")
print(header_raw)
print("--- PII STRIPPED ---")
print(strip_pii_from_text(text))
