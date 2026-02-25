import time
from typing import Optional, List
from google import genai
from google.genai import types
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
        self.client = None
        
        if self.api_key and self.api_key != "SUA_CHAVE_AQUI":
            self.client = genai.Client(api_key=self.api_key)
    
    def humanizar_texto(self, texto_bruto: str) -> Optional[str]:
        """
        Humaniza texto expandindo abreviações jurídicas.
        
        Args:
            texto_bruto: Texto original
        
        Returns:
            Texto humanizado ou None em caso de erro
        """
        if not self.client:
            print("\n[AVISO] GEMINI_API_KEY não configurada. Pulando humanização...")
            return texto_bruto
        
        print("\n--- HUMANIZANDO TEXTO COM GEMINI ---")
        
        prompt = """
        Você é um NARRADOR PROFISSIONAL DE AUDIOLIVROS JURÍDICOS, especializado em transformar textos legais formais em versões preparadas para locução clara, solene e fluida.

OBJETIVO:
Converter o texto jurídico fornecido em uma versão pronta para narração, expandindo todas as abreviações, símbolos e elementos gráficos para sua forma por extenso, mantendo rigorosamente o conteúdo original.

ENTRADA:
Texto jurídico completo (Lei, Decreto, Artigo, Código etc.).

SAÍDA:
O MESMO texto integral, sem cortes, sem resumos e sem comentários adicionais, apenas com as adaptações necessárias para leitura em voz alta.

REGRAS OBRIGATÓRIAS:
1. NÃO resumir.
2. NÃO explicar.
3. NÃO interpretar.
4. NÃO omitir nenhuma parte.
5. Processar o texto até o final, independentemente do tamanho.
6. Manter a estrutura original (artigos, parágrafos, incisos, alíneas).
7. A saída deve ter o mesmo conteúdo da entrada, alterando apenas o necessário para leitura fluida.
8. Sempre que houver numeração em algarismos romanos isolados (I, II, III, IV, V, VI, VII, VIII, IX, X, etc.), preceder obrigatoriamente pela palavra "inciso".
9. SUBSTITUIR qualquer traço, hífen ou marcador após incisos por ponto final.
10. Cada inciso deve terminar com ponto final, nunca com traço.

EXPANSÃO OBRIGATÓRIA:

1) Abreviações:
- "Art." → "Artigo"
- "§" → "Parágrafo"
- "inc." → "inciso"
- "al." → "alínea"
- "nº" ou "n." → "número"
- "CF" → "Constituição Federal"
- Expandir qualquer outra abreviação existente.

2) Incisos em algarismos romanos:
- I → inciso primeiro.
- II → inciso segundo.
- III → inciso terceiro.
- IV → inciso quarto.
- V → inciso quinto.
- VI → inciso sexto.
- VII → inciso sétimo.
- VIII → inciso oitavo.
- IX → inciso nono.
- X → inciso décimo.
- Continuar a conversão ordinal corretamente para quaisquer outros numerais romanos.
- Após cada inciso convertido, utilizar ponto final, nunca traço.

3) Aspas:
- "texto" → abre aspas, texto, fecha aspas.
- 'texto' → abre aspas, texto, fecha aspas.

4) Números:
- Cardinais (1, 25, 300) → por extenso.
- Ordinais (1º, 2º, 3ª) → primeiro, segundo, terceira.
- Leis e Decretos (Lei 8.666/93) → Lei oito mil seiscentos e sessenta e seis, de mil novecentos e noventa e três.
- Valores monetários (R$ 1.000,00) → mil reais.
- Datas → por extenso.

5) Símbolos:
- % → por cento.
- & → e.
- / → barra (quando necessário para clareza formal).

ESTILO:
- Manter a pontuação original sempre que possível.
- Preservar formalidade e ritmo jurídico.
- Garantir fluidez sonora.
- Não alterar termos técnicos.

FORMATO FINAL:
Entregar apenas o texto convertido, sem introduções, sem comentários e sem marcações adicionais.

TEXTO PARA CONVERTER:

[INSERIR TEXTO AQUI]
"""
        
        try:
            
            if len(texto_bruto) > MAX_CHARS_GEMINI:
                return self._processar_chunks(texto_bruto, prompt)
            else:
                for tentativa in range(MAX_RETRIES_GEMINI):
                    try:
                        response = self.client.models.generate_content(
                            model=GEMINI_MODEL,
                            contents=f"{prompt}\n{texto_bruto}"
                        )
                        print("Texto humanizado com sucesso!")
                        return response.text.strip()
                    except Exception as e:
                        if "429" in str(e) and tentativa < MAX_RETRIES_GEMINI - 1:
                            wait_time = (2 ** tentativa) * 2
                            print(f"\n  Cota excedida, aguardando {wait_time}s... (Tentativa {tentativa + 1}/{MAX_RETRIES_GEMINI})")
                            time.sleep(wait_time)
                        elif tentativa < MAX_RETRIES_GEMINI - 1:
                            wait_time = 2
                            print(f"\n  Erro transiente ({e}), tentando novamente em {wait_time}s...")
                            time.sleep(wait_time)
                        elif "404" in str(e):
                            print(f"\n[ERRO] Modelo nao encontrado: {e}")
                            raise e
                        elif "401" in str(e):
                            print(f"\n[ERRO] Chave de API invalida: {e}")
                            raise e
                        elif "403" in str(e):
                            print(f"\n[ERRO] Acesso negado: {e}")
                            raise e
                        elif "500" in str(e):
                            print(f"\n[ERRO] Erro interno do servidor: {e}")
                            raise e
                        elif "503" in str(e):
                            print(f"\n[ERRO] Servico indisponivel: {e}")
                            raise e
                        elif "504" in str(e):
                            print(f"\n[ERRO] Gateway timeout: {e}")
                            raise e 
                        else:
                            print(f"\n[ERRO] Falha no Gemini apos {MAX_RETRIES_GEMINI} tentativas: {e}")
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
                    response = self.client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=f"{prompt}\n{chunk}"
                    )
                    textos_humanizados.append(response.text.strip())
                    

                    if i < len(chunks):
                        time.sleep(RATE_LIMIT_DELAY)
                    break
                    
                except Exception as e:
                    if tentativa < MAX_RETRIES_GEMINI - 1:
                        wait_time = (2 ** tentativa) * 2
                        print(f"\n  Erro na parte {i}, tentativa {tentativa + 1}/{MAX_RETRIES_GEMINI}. Aguardando {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        print(f"\n  [X] Falha definitiva na parte {i}: {e}")
                        return None
        
        texto_final = "\n\n".join(textos_humanizados)
        print(f"\n[OK] Texto humanizado com sucesso! ({len(chunks)} partes)")
        return texto_final
