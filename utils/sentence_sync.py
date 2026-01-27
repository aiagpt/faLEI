"""
Gerador de timestamps por FRASE - Simples, rápido e eficiente.
Destaca frases inteiras em vez de palavras individuais.
"""
import json
import re
from typing import List, Dict

def split_into_sentences(text: str) -> List[str]:
    """
    Divide texto em frases baseado em pontuação.
    """
    # Padrões de fim de frase
    sentence_endings = r'[.!?;]\s+'
    
    # Dividir em frases
    sentences = re.split(sentence_endings, text)
    
    # Limpar e filtrar vazias
    sentences = [s.strip() for s in sentences if s.strip()]
    
    return sentences

def get_mp3_duration(audio_path: str) -> float:
    """
    Obtém duração do MP3 sem precisar de ffmpeg.
    Usa mutagen para ler metadados.
    """
    try:
        from mutagen.mp3 import MP3
        audio = MP3(audio_path)
        return audio.info.length
    except:
        # Fallback: estimar por tamanho do arquivo
        # MP3 típico: ~128kbps = 16KB/s
        import os
        file_size = os.path.getsize(audio_path)
        estimated_duration = file_size / 16000  # Estimativa conservadora
        return estimated_duration

def generate_sentence_timestamps(audio_path: str, text: str) -> List[Dict]:
    """
    Gera timestamps para cada FRASE do texto.
    Muito mais simples e eficiente que palavra por palavra.
    
    Args:
        audio_path: Caminho do arquivo MP3
        text: Texto completo da lei
    
    Returns:
        Lista de dicionários com {text, start, end}
    """
    print(f"\n[INFO] Gerando timestamps por frase...")
    
    try:
        # Obter duração do áudio
        duration = get_mp3_duration(audio_path)
        
        # Dividir em frases
        sentences = split_into_sentences(text)
        total_sentences = len(sentences)
        
        print(f"[INFO] Total de frases: {total_sentences}")
        print(f"[INFO] Duracao do audio: {duration:.1f}s")
        
        if total_sentences == 0:
            print("[!] Nenhuma frase encontrada!")
            return []
        
        # Estimar duração de cada frase baseado no tamanho
        total_chars = sum(len(s) for s in sentences)
        
        if total_chars == 0:
            print("[!] Texto vazio!")
            return []
        
        timestamps = []
        current_time = 0.0
        
        for sentence in sentences:
            # Duração proporcional ao tamanho da frase
            sentence_ratio = len(sentence) / total_chars
            sentence_duration = duration * sentence_ratio
            
            timestamps.append({
                'text': sentence,
                'start': round(current_time, 2),
                'end': round(current_time + sentence_duration, 2)
            })
            
            current_time += sentence_duration
        
        print(f"[OK] Timestamps gerados: {len(timestamps)} frases")
        print(f"[INFO] Sincronizacao rapida e eficiente!")
        
        return timestamps
        
    except Exception as e:
        print(f"[X] Erro ao gerar timestamps: {e}")
        import traceback
        traceback.print_exc()
        return []

def save_timestamps(timestamps: List[Dict], output_path: str):
    """Salva timestamps em arquivo JSON."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(timestamps, f, ensure_ascii=False, indent=2)
    print(f"[SAVE] Timestamps salvos em: {output_path}")

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 2:
        audio_path = sys.argv[1]
        text_path = sys.argv[2]
        
        with open(text_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        timestamps = generate_sentence_timestamps(audio_path, text)
        
        output_path = audio_path.replace('.mp3', '_timestamps.json')
        save_timestamps(timestamps, output_path)
