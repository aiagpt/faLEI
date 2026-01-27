"""
Gerador de timestamps PERFEITOS usando Whisper (OpenAI) - 100% GRATUITO.
Roda localmente no seu PC, sem custos de API.
"""
import json
import os
from typing import List, Dict
import whisper
from pydub import AudioSegment

def generate_whisper_timestamps(audio_path: str) -> List[Dict]:
    """
    Gera timestamps PERFEITOS usando Whisper (local, gratuito).
    
    Args:
        audio_path: Caminho do arquivo MP3
    
    Returns:
        Lista de dicionários com {word, start, end}
    """
    print(f"\n🎤 Gerando timestamps com Whisper (gratuito)...")
    print("⏳ Primeira vez pode demorar (baixando modelo ~150MB)...")
    
    try:
        # Carregar modelo Whisper
        # Opções: tiny, base, small, medium, large
        # tiny = mais rápido, menos preciso
        # base = bom equilíbrio (recomendado)
        # small/medium/large = mais preciso, mais lento
        
        print("📥 Carregando modelo Whisper 'base'...")
        model = whisper.load_model("base")
        
        print(f"🎧 Analisando áudio: {audio_path}")
        
        # Transcrever com timestamps de palavras
        result = model.transcribe(
            audio_path,
            language='pt',
            word_timestamps=True,  # CRUCIAL: habilita timestamps por palavra
            verbose=False
        )
        
        # Extrair timestamps
        timestamps = []
        
        for segment in result['segments']:
            if 'words' in segment:
                for word_info in segment['words']:
                    word = word_info['word'].strip()
                    start = word_info['start']
                    end = word_info['end']
                    
                    if word:  # Ignorar palavras vazias
                        timestamps.append({
                            'word': word,
                            'start': round(start, 3),
                            'end': round(end, 3)
                        })
        
        print(f"✅ Timestamps perfeitos gerados: {len(timestamps)} palavras")
        print(f"🎯 Sincronização 100% automática e gratuita!")
        
        return timestamps
        
    except Exception as e:
        print(f"❌ Erro ao usar Whisper: {e}")
        print(f"⚠️ Usando fallback com estimativa...")
        
        # Fallback para método anterior
        from utils.audio_analyzer import generate_word_timestamps
        
        # Tentar carregar texto do checkpoint
        try:
            # Buscar texto do banco de dados
            import re
            job_id = re.search(r'lei_(\d+)_', audio_path)
            if job_id:
                from database.job_db import JobDatabase
                db = JobDatabase()
                job = db.get_job(int(job_id.group(1)))
                text = job.get('checkpoint_humanized') or job.get('checkpoint_text') or ''
                return generate_word_timestamps(audio_path, text)
        except:
            pass
        
        return generate_word_timestamps(audio_path, "")

def save_timestamps(timestamps: List[Dict], output_path: str):
    """Salva timestamps em arquivo JSON."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(timestamps, f, ensure_ascii=False, indent=2)
    print(f"💾 Timestamps salvos em: {output_path}")

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
        timestamps = generate_whisper_timestamps(audio_path)
        
        output_path = audio_path.replace('.mp3', '_timestamps.json')
        save_timestamps(timestamps, output_path)
