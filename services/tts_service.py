import time
import os
from typing import List
from google.cloud import texttospeech
from tqdm import tqdm

from config.settings import settings
from models.constants import (
    VOICES,
    AUDIO_CONFIG,
    FREE_TIER_CHARS,
    MAX_RETRIES_TTS,
    MAX_CHARS_TTS
)
from utils.text_processor import dividir_texto_inteligente, formatar_lei_ssml
from utils.audio_merger import mesclar_audios
from utils.usage_tracker import usage_tracker

class TTSService:
    def __init__(self, voice_name: str = "pt-BR-Wavenet-B"):
        """
        Inicializa o serviço TTS.
        
        Args:
            voice_name: Nome da voz a ser usada (chave em VOICES)
        """
        # Configurar credenciais
        if settings.google_credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_credentials_path
            
        self.client = texttospeech.TextToSpeechClient()
        
        # Validar voz
        if voice_name not in VOICES:
            print(f"[!] Voz '{voice_name}' desconhecida. Usando padrao.")
            voice_name = "pt-BR-Wavenet-B"
            
        voice_info = VOICES[voice_name]
        
        # Configurar Voz
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="pt-BR",
            name=voice_name,
            ssml_gender=getattr(texttospeech.SsmlVoiceGender, voice_info["gender"])
        )
        
        # Configurar Áudio
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            sample_rate_hertz=AUDIO_CONFIG["sample_rate"],
            speaking_rate=AUDIO_CONFIG["speaking_rate"],
            pitch=AUDIO_CONFIG["pitch"]
        )
    # REPLACING sintetizar_arquivo with tracked version
    def sintetizar_arquivo(self, texto: str, arquivo_saida: str = "output.mp3", progress_callback=None) -> bool:
        """
        Sintetiza texto em arquivo de áudio, com suporte para textos grandes.
        """
        print("\\n--- PROCESSANDO ÁUDIO ---")
        


        # Dividir texto em chunks
        chunks = dividir_texto_inteligente(texto, max_chars=MAX_CHARS_TTS)
        print(f"Texto dividido em {len(chunks)} partes para síntese.")
        
        # Configurar diretórios
        output_dir = os.path.dirname(os.path.abspath(arquivo_saida))
        temp_dir = os.path.join(output_dir, "temp_parts")
        os.makedirs(temp_dir, exist_ok=True)
        
        arquivos_temp = []
        
        # Processar cada chunk
        for i, chunk in enumerate(tqdm(chunks, desc="Gerando áudio", unit="parte"), 1):
            ssml_content = formatar_lei_ssml(chunk)
            arquivo_temp = os.path.join(temp_dir, f"part_{i:03d}.mp3")
            
            chunk_len = len(chunk)
            
            # Resume Logic: Verificar se o arquivo já existe e é válido
            if os.path.exists(arquivo_temp) and os.path.getsize(arquivo_temp) > 0:
                # tqdm.write(f"  [OK] Parte {i} (cache)")
                arquivos_temp.append(arquivo_temp)
                # NOTA: Não cobramos quota novamente por arquivos em cache
                continue
            


            # Sintetizar com retry
            if self._sintetizar_chunk(ssml_content, arquivo_temp):
                arquivos_temp.append(arquivo_temp)
                # ✅ Contabilizar uso apenas após sucesso
                usage_tracker.add_usage(chunk_len)
                
                # Granular Progress Update (40% -> 90%)
                if progress_callback:
                    percent_complete = (i / len(chunks)) * 100
                    # Map 0-100 to 40-90
                    mapped_progress = 40 + (percent_complete * 0.5)
                    progress_callback(int(mapped_progress), f"Gerando áudio: Parte {i}/{len(chunks)}")
            else:
                tqdm.write(f"  [X] Falha na parte {i}")
                break
        
        # Mesclar áudios
        if len(arquivos_temp) == len(chunks):
            if mesclar_audios(arquivos_temp, arquivo_saida):
                print(f"\\n[OK] SUCESSO: Audio completo salvo em '{arquivo_saida}'")
                return True
        else:
            print(f"\\n[X] ERRO: Apenas {len(arquivos_temp)}/{len(chunks)} partes geradas.")
        
        return False
    
    def _sintetizar_chunk(self, ssml_texto: str, arquivo_saida: str) -> bool:
        """Sintetiza um chunk com retry logic."""
        input_text = texttospeech.SynthesisInput(ssml=ssml_texto)
        
        for tentativa in range(MAX_RETRIES_TTS):
            try:
                response = self.client.synthesize_speech(
                    input=input_text,
                    voice=self.voice,
                    audio_config=self.audio_config
                )
                
                with open(arquivo_saida, "wb") as out:
                    out.write(response.audio_content)
                return True
                
            except Exception as e:
                if tentativa < MAX_RETRIES_TTS - 1:
                    wait_time = (2 ** tentativa) * 1
                    tqdm.write(f"  ⚠ Erro, tentativa {tentativa + 1}. Aguardando {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    tqdm.write(f"  [X] ERRO definitivo: {e}")
                    return False
        
        return False
