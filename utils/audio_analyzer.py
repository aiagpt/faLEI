"""
Gerador de timestamps de palavras usando análise de áudio.
"""
import json
import os
from typing import List, Dict
import speech_recognition as sr
from pydub import AudioSegment
from pydub.silence import split_on_silence

def estimate_word_duration(word: str) -> float:
    """
    Estima duração de uma palavra baseado em características.
    """
    # Contar vogais (aproximação de sílabas)
    vowels = 'aeiouáéíóúâêôãõ'
    syllables = sum(1 for c in word.lower() if c in vowels)
    syllables = max(1, syllables)
    
    # Palavras longas levam mais tempo
    length_factor = len(word) / 10.0
    
    # Base: 200ms por sílaba + ajuste por tamanho
    duration = (syllables * 0.2) + (length_factor * 0.05)
    
    # Mínimo de 150ms, máximo de 1s
    return max(0.15, min(1.0, duration))

def generate_word_timestamps(audio_path: str, text: str) -> List[Dict]:
    """
    Gera timestamps para cada palavra do texto baseado no áudio.
    
    Args:
        audio_path: Caminho do arquivo MP3
        text: Texto completo da lei
    
    Returns:
        Lista de dicionários com {word, start, end}
    """
    print(f"\n🎤 Analisando áudio: {audio_path}")
    
    try:
        # Carregar áudio
        audio = AudioSegment.from_mp3(audio_path)
        duration = len(audio) / 1000.0  # Duração em segundos
        
        # Dividir texto em palavras
        words = text.split()
        total_words = len(words)
        
        print(f"📝 Total de palavras: {total_words}")
        print(f"⏱️ Duração do áudio: {duration:.1f}s")
        
        # Estimar duração total baseada nas palavras
        estimated_total = sum(estimate_word_duration(w) for w in words)
        
        # Calcular fator de escala
        scale_factor = duration / estimated_total
        
        print(f"📊 Fator de escala: {scale_factor:.2f}x")
        
        # Gerar timestamps
        timestamps = []
        current_time = 0.0
        
        for word in words:
            word_duration = estimate_word_duration(word) * scale_factor
            
            timestamps.append({
                'word': word,
                'start': round(current_time, 3),
                'end': round(current_time + word_duration, 3)
            })
            
            current_time += word_duration
        
        print(f"✅ Timestamps gerados: {len(timestamps)} palavras")
        print(f"⏱️ Tempo total estimado: {current_time:.1f}s (real: {duration:.1f}s)")
        
        return timestamps
        
    except Exception as e:
        print(f"❌ Erro ao analisar áudio: {e}")
        import traceback
        traceback.print_exc()
        # Fallback: estimativa simples
        return generate_simple_timestamps(text, 60)

def generate_simple_timestamps(text: str, duration: float) -> List[Dict]:
    """Gera timestamps simples baseado em estimativa."""
    words = text.split()
    time_per_word = duration / len(words)
    
    timestamps = []
    for i, word in enumerate(words):
        timestamps.append({
            'word': word,
            'start': i * time_per_word,
            'end': (i + 1) * time_per_word
        })
    
    return timestamps

def save_timestamps(timestamps: List[Dict], output_path: str):
    """Salva timestamps em arquivo JSON."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(timestamps, f, ensure_ascii=False, indent=2)
    print(f"💾 Timestamps salvos em: {output_path}")

if __name__ == '__main__':
    # Teste
    import sys
    if len(sys.argv) > 2:
        audio_path = sys.argv[1]
        text_path = sys.argv[2]
        
        with open(text_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        timestamps = generate_word_timestamps(audio_path, text)
        
        output_path = audio_path.replace('.mp3', '_timestamps.json')
        save_timestamps(timestamps, output_path)
