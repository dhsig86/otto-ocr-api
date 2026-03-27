import re

def strip_pii_from_text(raw_text: str) -> str:
    """
    Remove ou ofusca informações sensíveis (Nome, CPF, Convênio).
    Utilizado como buffer ANTES de repassar o texto ao GPT.
    """
    if not isinstance(raw_text, str):
        return ""
        
    # Mascarar CPF (ex: 123.456.789-00 ou 12345678900)
    cpf_pattern = r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'
    text = re.sub(cpf_pattern, '[CPF OMITIDO]', raw_text)
    
    # Mascarar possíveis nomes após "Paciente:" ou "Nome:"
    name_pattern = r'(?i)(paciente|nome)[:\s]+([A-Za-zÀ-ÖØ-öø-ÿ\s]+)(?=\n|$)'
    text = re.sub(name_pattern, r'\1: [NOME OMITIDO]', text)

    # Mascarar possíveis RGs
    rg_pattern = r'(?i)(rg|registro geral)[:\s]+([0-9xX.-]+)(?=\n|$)'
    text = re.sub(rg_pattern, r'\1: [RG OMITIDO]', text)
    
    # Mascarar datas de nascimento
    dob_pattern = r'(?i)(data de nascimento|nascimento|d.n.)[:\s]+(\d{2}/\d{2}/\d{4})'
    text = re.sub(dob_pattern, r'\1: [DATA OMITIDA]', text)
    
    # Mascarar convênio
    convenio_pattern = r'(?i)(conv[eê]nio|plano)[:\s]+([A-Za-zÀ-ÖØ-öø-ÿ\s]+)(?=\n|$)'
    text = re.sub(convenio_pattern, r'\1: [CONVÊNIO OMITIDO]', text)

    return text
