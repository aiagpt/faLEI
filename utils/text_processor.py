import re
import html
from typing import List

def dividir_texto_inteligente(texto: str, max_chars: int = 4500) -> List[str]:
    """
    Divide texto em chunks respeitando limites de artigos.
    
    Args:
        texto: Texto a ser dividido
        max_chars: Tamanho máximo de cada chunk
    
    Returns:
        Lista de chunks de texto
    """
    if len(texto) <= max_chars:
        return [texto]
    
    chunks = []
    # Dividir por artigos
    artigos = re.split(r'(Art\.\\s+\\d+)', texto)
    
    chunk_atual = ""
    for parte in artigos:
        # Se a parte sozinha já é maior que o limite, precisamos dividir ela também
        if len(parte) > max_chars:
            # Primeiro, salva o que já acumulou
            if chunk_atual.strip():
                chunks.append(chunk_atual.strip())
                chunk_atual = ""
            
            # Divide a parte grande por quebras de linha ou sentenças
            if '\n' in parte:
                subpartes = parte.split('\n')
            else:
                subpartes = re.split(r'(?<=[.!?])\s+', parte)
                
            sub_chunk = ""
            for sub in subpartes:
                # Se a sentença sozinha for maior que o limite, quebra por espaços
                if len(sub) > max_chars:
                    if sub_chunk:
                        chunks.append(sub_chunk.strip())
                        sub_chunk = ""
                    
                    # Dividir sentença gigante por espaços
                    palavras = sub.split(' ')
                    temp_sent = ""
                    for palavra in palavras:
                        if len(temp_sent) + len(palavra) + 1 <= max_chars:
                            temp_sent += (palavra + " ") if temp_sent else palavra
                        else:
                            chunks.append(temp_sent.strip())
                            temp_sent = palavra
                    if temp_sent:
                        sub_chunk = temp_sent # Continua
                
                elif len(sub_chunk) + len(sub) <= max_chars:
                    sub_chunk += sub if not sub_chunk else (" " + sub)
                else:
                    item_to_add = sub_chunk.strip()
                    if item_to_add:
                        chunks.append(item_to_add)
                    sub_chunk = sub
                    
            if sub_chunk.strip():
                chunk_atual = sub_chunk # Continua com o resto
        
        elif len(chunk_atual) + len(parte) <= max_chars:
            chunk_atual += parte
        else:
            if chunk_atual.strip():
                chunks.append(chunk_atual.strip())
            chunk_atual = parte
    
    if chunk_atual.strip():
        chunks.append(chunk_atual.strip())
    
    return chunks

def formatar_lei_ssml(texto_bruto: str) -> str:
    """
    Formata texto jurídico com pausas SSML.
    
    Args:
        texto_bruto: Texto sem formatação
    
    Returns:
        Texto formatado com tags SSML
    """
    # Escapar caracteres especiais para XML/SSML
    texto_safe = html.escape(texto_bruto)
    
    # Adicionar pausas estratégicas
    texto_ssml = texto_safe.replace("Art.", '<break time="600ms"/>Art.')
    texto_ssml = texto_ssml.replace("§", '<break time="400ms"/>§')
    texto_ssml = texto_ssml.replace(";", ';<break time="300ms"/>')
    texto_ssml = texto_ssml.replace(":", ':<break time="300ms"/>')
    texto_ssml = texto_ssml.replace(".", '.<break time="500ms"/>')
    
    return f"<speak>{texto_ssml}</speak>"
