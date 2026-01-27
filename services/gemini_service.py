import time
from typing import Optional, List
import google.generativeai as genai
from tqdm import tqdm

from config.settings import settings
from models.constants import (
    MAX_CHARS_GEMINI,
    MAX_RETRIES_GEMINI,
    RATE_LIMIT_DELAY,
    GEMINI_MODEL
)
from utils.text_processor import dividir_texto_inteligente

class GeminiService:
    """Serviço de humanização de texto usando Gemini."""
    
    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model = None
        
        if self.api_key and self.api_key != "SUA_CHAVE_AQUI":
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(GEMINI_MODEL)
    
    def humanizar_texto(self, texto_bruto: str) -> Optional[str]:
        """
        Humaniza texto expandindo abreviações jurídicas.
        
        Args:
            texto_bruto: Texto original
        
        Returns:
            Texto humanizado ou None em caso de erro
        """
        if not self.model:
            print("\n[AVISO] GEMINI_API_KEY não configurada. Pulando humanização...")
            return texto_bruto
        
        print("\n--- HUMANIZANDO TEXTO COM GEMINI ---")
        
        prompt = """
        ATUE COMO UM NARRADOR DE AUDIOLIVROS JURÍDICOS.
        Sua tarefa é PREPARAR o texto abaixo para locução, expandindo abreviações para leitura fluida.

        ENTRADA: Texto jurídico (Lei, Artigo, etc).
        SAÍDA: O MESMO texto, mas com as abreviações expandidas por extenso.
        
        REGRAS CRÍTICAS (Siga estritamente):
        1. NÃO RESUMA. NÃO EXPLIQUE. NÃO COMENTE. A saída deve ter o MESMO TAMANHO da entrada (exceto pelas expansões).
        2. Mantenha TODOS os artigos, parágrafos e incisos. Se o texto for longo, processe TUDO até o final.
        
        DIRETRIZES DE LEITURA (Humanização):
        - Abreviaturas: Expanda TODAS.
          * "Art." -> "Artigo"
          * "§" -> "Parágrafo"
          * "inc." -> "inciso"
          * "al." -> "alínea"
          * "nº" -> "número"
        
        - Aspas: Substitua aspas visuais por narração.
          * "texto" -> "abre aspas, texto, fecha aspas"
          * 'texto' -> "abre aspas, texto, fecha aspas"
        
        - Números:
          * Cardinais (1, 2, 100): Leia normalmente ("um", "dois", "cem"). 
          * Ordinais (1º, 2º): "primeiro", "segundo".
          * Leis/Decretos: "Lei 8.666" -> "Lei oito mil seiscentos e sessenta e seis".
          * Cifras (R$): "R$ 1.000,00" -> "mil reais".
        
        - Estrutura:
          * Mantenha a pontuação original onde possível para preservar o ritmo jurídico.
        
        TEXTO PARA PREPARAR:
        """
        
        try:
            # Texto grande: dividir em chunks
            if len(texto_bruto) > MAX_CHARS_GEMINI:
                return self._processar_chunks(texto_bruto, prompt)
            else:
                # Texto pequeno: processar de uma vez COM RETRY
                for tentativa in range(MAX_RETRIES_GEMINI):
                    try:
                        response = self.model.generate_content(f"{prompt}\n{texto_bruto}")
                        print("Texto humanizado com sucesso!")
                        return response.text.strip()
                    except Exception as e:
                        if "429" in str(e) and tentativa < MAX_RETRIES_GEMINI - 1:
                            wait_time = (2 ** tentativa) * 2
                            print(f"\n  ⚠ Cota excedida, aguardando {wait_time}s... (Tentativa {tentativa + 1}/{MAX_RETRIES_GEMINI})")
                            time.sleep(wait_time)
                        elif tentativa < MAX_RETRIES_GEMINI - 1:
                            wait_time = 2
                            print(f"\n  ⚠ Erro transiente ({e}), tentando novamente em {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            print(f"\n[ERRO] Falha no Gemini após {MAX_RETRIES_GEMINI} tentativas: {e}")
                            raise e
                return None
                
        except Exception as e:
            print(f"[ERRO] Falha Geral no Gemini: {e}")
            return None
    
    def _processar_chunks(self, texto: str, prompt: str) -> Optional[str]:
        """Processa texto grande em chunks com retry logic."""
        print(f"Texto grande detectado ({len(texto)} chars). Dividindo em partes...")
        chunks = dividir_texto_inteligente(texto, MAX_CHARS_GEMINI)
        print(f"Processando {len(chunks)} partes...")
        
        textos_humanizados = []
        
        for i, chunk in enumerate(tqdm(chunks, desc="Humanizando", unit="parte"), 1):
            # Retry logic com exponential backoff
            for tentativa in range(MAX_RETRIES_GEMINI):
                try:
                    response = self.model.generate_content(f"{prompt}\n{chunk}")
                    textos_humanizados.append(response.text.strip())
                    
                    # Rate limiting
                    if i < len(chunks):
                        time.sleep(RATE_LIMIT_DELAY)
                    break
                    
                except Exception as e:
                    if tentativa < MAX_RETRIES_GEMINI - 1:
                        wait_time = (2 ** tentativa) * 2
                        print(f"\n  ⚠ Erro na parte {i}, tentativa {tentativa + 1}/{MAX_RETRIES_GEMINI}. Aguardando {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        print(f"\n  [X] Falha definitiva na parte {i}: {e}")
                        return None
        
        texto_final = "\n\n".join(textos_humanizados)
        print(f"\n[OK] Texto humanizado com sucesso! ({len(chunks)} partes)")
        return texto_final
