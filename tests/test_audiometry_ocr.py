import pytest
from services.nlp_parser import NLPParser
from services.exam_classifier import ExamClassifier

def test_parse_audiometria_parecer_completo():
    parser = NLPParser()
    sample_text = """
    PACIENTE: JOAO DA SILVA
    EXAME: AUDIOMETRIA TONAL E VOCAL
    PARECER AUDIOLÓGICO:
    Paciente apresenta perda auditiva neurossensorial bilateral de grau moderado a severo nas frequências de 3kHz, 4kHz e 6kHz.
    Limiares tonais: 50 dB a 500Hz, 70 dB a 4000Hz.
    SRT: 55 dB. IPRF: 88%.
    Sugiro realização de BERA e Immitanciometria para complementação diagnóstica.
    """
    result = parser.parse_audiometria(sample_text)
    
    assert result["tipo_perda"] == "neurossensorial"
    assert result["lateralidade"] == "bilateral"
    assert result["grau_perda"] == "moderado a severo"
    assert result["srt_db"] == 55
    assert result["iprf_pct"] == 88
    assert "BERA/PEATE" in result["sugestoes_complementares"]
    assert "Immitanciometria/Timpanometria" in result["sugestoes_complementares"]

def test_parse_audiometria_normoacusia():
    parser = NLPParser()
    sample_text = """
    EXAME: AUDIOMETRIA TONAL
    PARECER AUDIOLÓGICO:
    Limiares auditivos dentro dos padrões da normalidade em ambas as orelhas (normoacusia).
    SRT: 15 dB. IPRF: 100%.
    """
    result = parser.parse_audiometria(sample_text)
    
    assert result["tipo_perda"] == "normal"
    assert result["lateralidade"] == "bilateral"
    assert result["srt_db"] == 15
    assert result["iprf_pct"] == 100

def test_exam_classifier_audiometria():
    classifier = ExamClassifier()
    sample_text = "Audiograma tonal liminar e vocal. SRT 40 dB, IPRF 92%. Perda auditiva condutiva em orelha direita."
    
    exam_type = classifier.classify(sample_text)
    assert exam_type == "audiometria"
