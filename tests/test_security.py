from core.security import (
    extract_exam_date,
    generate_patient_token,
    extract_patient_data,
    extract_and_strip_header,
    strip_pii_from_text
)

def test_extract_exam_date():
    header = "Paciente: Joao\nData do Exame: 15/03/2026\nExame: Audiometria"
    date = extract_exam_date(header)
    assert date == "2026-03-15"

    header_iso = "Paciente: Maria\nRealizado em: 2026-04-20"
    date_iso = extract_exam_date(header_iso)
    assert date_iso == "2026-04-20"

def test_generate_patient_token():
    header = "Paciente: Joao da Silva\nNascimento: 15/03/1990"
    token1 = generate_patient_token(header)
    token2 = generate_patient_token(header)
    assert token1.startswith("pt-")
    assert token1 == token2  # Determinístico para o mesmo cabeçalho

    token_empty = generate_patient_token("")
    assert token_empty.startswith("pt-")
    assert len(token_empty) > 6

def test_extract_patient_data():
    header = "Paciente: Joao da Silva\nNascimento: 15/03/1990\nIdade: 54 anos\nSexo: Masculino\nCargo: Serralheiro"
    data = extract_patient_data(header)
    assert data["nome"] == "Joao da Silva"
    assert data["data_nascimento"] == "1990-03-15"
    assert data["idade"] == "54 anos"
    assert data["sexo"] == "Masculino"
    assert data["cargo_funcao"] == "Serralheiro"

def test_extract_and_strip_header():
    raw_text = (
        "Nome: Maria Oliveira\n"
        "Convênio: Unimed\n"
        "Indicação Clínica: Rouquidão persistente há 2 semanas.\n"
        "Achados: Laringe normal, pregas vocais móveis."
    )
    body, header = extract_and_strip_header(raw_text)
    assert "Indicação Clínica" in body
    assert "Maria Oliveira" in header

def test_strip_pii_from_text():
    raw = "Paciente: Joao da Silva\nCPF: 123.456.789-00\nRG: 12.345.678-9\ncrm 12345-SP"
    stripped = strip_pii_from_text(raw)
    assert "[CPF OMITIDO]" in stripped
    assert "[RG OMITIDO]" in stripped
    assert "[MÉDICO OMITIDO]" in stripped
    assert "Joao da Silva" not in stripped
