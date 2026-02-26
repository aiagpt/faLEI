import os
import time
import requests
from typing import Optional
from tqdm import tqdm

from models.constants import MAX_CHARS_GEMINI
from utils.text_processor import dividir_texto_inteligente

# Porta do servidor bridge do Electron (definida em main.js como IPC_PORT)
ELECTRON_IPC_PORT = int(os.getenv('ELECTRON_IPC_PORT', 5001))
ELECTRON_IPC_URL = f'http://127.0.0.1:{ELECTRON_IPC_PORT}'

PROMPT_HUMANIZACAO = """Você é um NARRADOR PROFISSIONAL DE AUDIOLIVROS JURÍDICOS, especializado em transformar textos legais formais em versões preparadas para locução clara, solene e fluida.

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
8. Ignorar totalmente qualquer artefato HTML: nomes de imagem (.gif, .png), "Tabela com", "Linha um:", "bytes" — não ler nem mencionar.
9. Sempre que houver numeração em algarismos romanos isolados (I, II, III...) OU a palavra "item" seguida de numeral, converter obrigatoriamente para "inciso" + ordinal por extenso.
10. SUBSTITUIR qualquer traço, hífen ou ponto-e-vírgula após incisos por ponto final.

EXPANSÃO OBRIGATÓRIA:

1) Abreviações:
- "Art." → "Artigo"
- "§" → "Parágrafo"
- "inc." → "inciso"
- "al." → "alínea"
- "nº" ou "n." → "número"
- "S.A." → "Sociedade Anônima"
- "DOU" → "Diário Oficial da União"
- "CF" → "Constituição Federal"
- Expandir qualquer outra abreviação existente.

2) Siglas e acrônimos:
- Siglas entre PARÊNTESES logo após o nome por extenso: remover parênteses, ler cada letra separada por espaço.
  Exemplos: "(INC)" → "I N C" | "(STF)" → "S T F" | "(dois)" após número → só "dois"
- Siglas standalone no texto (sem parênteses): MANTER exatamente como estão.
  Exemplos que NÃO devem ser alterados: EMBRAFILME, STF, STJ, CNJ, AGU, BNDES, IBGE.

3) Incisos em algarismos romanos e "item":
- I / item I → inciso primeiro.
- II / item II / item Il → inciso segundo.
- III / item III → inciso terceiro.
- IV / item IV → inciso quarto.
- V / item V → inciso quinto.
- VI / item VI → inciso sexto.
- VII / item VII → inciso sétimo.
- VIII / item VIII → inciso oitavo.
- IX / item IX → inciso nono.
- X / item X → inciso décimo.
- Continuar a conversão ordinal corretamente para quaisquer outros numerais romanos.
- Após cada inciso convertido, utilizar ponto final, nunca traço.

4) Aspas:
- "texto" → abre aspas, texto, fecha aspas.
- 'texto' → abre aspas, texto, fecha aspas.

5) Números:
- Cardinais (1, 25, 300) → por extenso.
- Ordinais (1º, 2º, 3ª) → primeiro, segundo, terceira.
- Leis e Decretos (Lei 8.666/93) → Lei oito mil seiscentos e sessenta e seis, de mil novecentos e noventa e três.
- Valores monetários (R$ 1.000,00 | Cr$ 80.000.000,00) → por extenso com moeda.
- Datas → por extenso.
- Anos isolados (ex: 1975, 1976) → por extenso.

6) Símbolos:
- % → por cento.
- & → e.

7) Referências legais entre parênteses no corpo do texto:
- "(Vide Decreto-lei nº 1.900, de 1981)" → "Vide, Decreto-lei número mil e novecentos, de mil novecentos e oitenta e um."
- Manter sem os parênteses, como parte da leitura.

ESTILO:
- Manter a pontuação original sempre que possível.
- Preservar formalidade e ritmo jurídico.
- Garantir fluidez sonora.
- Não alterar termos técnicos.
- Nomes de pessoas em caixa alta → Title Case com ponto final. Ex: "ERNESTO GEISEL" → "Ernesto Geisel."

FORMATO FINAL:
Entregar apenas o texto convertido, sem introduções, sem comentários e sem marcações adicionais.

TEXTO PARA CONVERTER:
"""

PROMPT_VERIFICACAO = """Você é um REVISOR DE AUDIOLIVROS JURÍDICOS.
Sua missão é verificar se o Texto Humanizado é uma boa conversão para leitura em áudio do Texto Original.

REGRAS DE VERIFICAÇÃO (só reprove se houver violação CLARA):
1. O conteúdo essencial do texto (artigos, parágrafos, incisos) NÃO pode ter sido omitido.
2. Artefatos estritamente HTML (nomes de arquivos como ".gif", tags HTML, descrições técnicas de imagem) devem ter sido ignorados. ATENÇÃO: Cabeçalhos institucionais como "Presidência da República", "Casa Civil" NÃO são artefatos HTML — são parte legítima do texto.
3. Incisos em algarismos romanos devem ter sido convertidos para ordinal por extenso.
4. Siglas REAIS entre parênteses (ex: "(INC)", "(STF)") devem estar soletradas. ATENÇÃO: Palavras comuns entre parênteses como "(VETADO)", "(Revogado)", "(Incluído)" NÃO são siglas — são termos jurídicos e devem ser mantidos naturalmente.
5. Siglas standalone conhecidas (ex: EMBRAFILME, DOU, STJ) podem ser mantidas intactas OU lidas por extenso — ambas as formas são aceitáveis.

INSTRUÇÕES DE RESPOSTA:
- Se o texto humanizado é uma conversão aceitável para áudio, responda EXATAMENTE: SIM
- Se há erros GRAVES (conteúdo omitido, números não convertidos, artefatos HTML incluídos), responda: NÃO
  (Na linha seguinte, justificativa curta.)
- NÃO reprove por questões meramente estilísticas ou de preferência.

===TEXTO ORIGINAL===
{texto_original}

===TEXTO HUMANIZADO===
{texto_humanizado}
"""

class GeminiService:
    """
    Serviço de humanização de texto.

    Em vez de chamar a API REST do Gemini (que exige API key),
    comunica-se com o Electron via servidor bridge HTTP local (porta 5001).
    O Electron controla uma BrowserWindow oculta com a sessão do usuário
    logada em gemini.google.com, automatizando o chat via injeção de JS.
    """

    def __init__(self):
        self.ipc_url = ELECTRON_IPC_URL
        self._check_bridge()

    def _check_bridge(self):
        """Verifica se o servidor bridge do Electron está disponível."""
        try:
            r = requests.get(f'{self.ipc_url}/health', timeout=3)
            data = r.json()
            print(f"[Gemini Bridge] Conectado. Janela Gemini pronta: {data.get('geminiReady', False)}")
        except Exception:
            print('[Gemini Bridge] AVISO: Servidor Electron não respondeu. '
                  'Certifique-se de que o app está rodando via Electron (npm start).')

    def _humanizar_chunk(self, texto: str, chunk_num: int = 1, total: int = 1) -> Optional[str]:
        """
        Envia um chunk de texto ao Electron para humanização via Gemini web.

        Returns:
            Texto humanizado ou None em caso de erro.
        """
        try:
            payload = {
                'text': texto,
                'prompt': PROMPT_HUMANIZACAO
            }
            # Timeout generoso: leis longas podem demorar até 2 min
            response = requests.post(
                f'{self.ipc_url}/humanize',
                json=payload,
                timeout=180
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data['text']
                else:
                    print(f'\n[ERRO] Gemini retornou erro: {data.get("error")}')
                    return None
            else:
                error_body = response.json() if response.content else {}
                err_msg = error_body.get('error', f'HTTP {response.status_code}')

                # Propagar erro de login de forma clara
                if 'autenticado' in err_msg or 'login' in err_msg.lower():
                    raise Exception(f'LOGIN_REQUIRED: {err_msg}')

                print(f'\n[ERRO] Chunk {chunk_num}/{total} falhou: {err_msg}')
                return None

        except Exception as e:
            err_str = str(e)
            if 'LOGIN_REQUIRED' in err_str:
                raise  # Propaga erro de login sem retry
            if 'Connection refused' in err_str or 'timeout' in err_str.lower():
                print(f'\n[ERRO] Bridge do Electron inacessível: {e}')
            else:
                print(f'\n[ERRO] Falha ao comunicar com o Electron: {e}')
            return None

    def _verificar_chunk(self, texto_original: str, texto_humanizado: str, chunk_num: int = 1) -> tuple[bool, str]:
        """
        Pede ao Gemini para auditar a própria resposta e dizer SIM (aprovado) ou NÃO (reprovado).
        Returns: (bool aprovado, str justificativa)
        """
        try:
            prompt_formatado = PROMPT_VERIFICACAO.format(
                texto_original=texto_original,
                texto_humanizado=texto_humanizado
            )
            payload = {
                'text': prompt_formatado,
                'prompt': '' # enviamos via texto para não usar o prompt default
            }

            print(f'  [Auditoria] Verificando qualidade da conversão da parte {chunk_num}...')
            response = requests.post(f'{self.ipc_url}/humanize', json=payload, timeout=180)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    res_text = str(data['text']).strip()
                    res_upper = res_text.upper()
                    
                    # LOG EXTRA: Mostrar cruamente o que o Gemini respondeu (cortado em 200 caracteres para não espalhar muito)
                    print(f'    -> Resposta Bruta do Gemini: "{res_text[:200].replace(chr(10), " ")}..."')
                    
                    if res_upper.startswith('SIM') or 'SIM' in res_upper[:15]:
                        return True, 'Aprovado pelo Gemini.'
                    elif res_upper.startswith('NÃO') or res_upper.startswith('NAO') or 'NÃO' in res_upper[:15] or 'NAO' in res_upper[:15]:
                        linhas = res_text.split('\n')
                        motivo = linhas[1] if len(linhas) > 1 else res_text
                        motivo = motivo.strip() or res_text[:60]
                        return False, f'Reprovada: {motivo}'
                    else:
                        # Se respondeu diferente, consideramos reprovado por ambiguidade
                        return False, f'Reprovada: Resposta ambígua ({res_text[:60]}...)'
                else:
                    print(f'    -> Erro IPC durante auditoria: {data.get("error")}')
                    return False, f'Erro IPC: {data.get("error")}'
            else:
                return False, f'Erro HTTP {response.status_code}'

        except Exception as e:
            if 'LOGIN_REQUIRED' in str(e):
                raise
            return False, f'Erro Exception: {e}'

    def humanizar_texto(self, texto_bruto: str) -> Optional[str]:
        """
        Humaniza o texto completo, dividindo em chunks se necessário (c/ validação de qualidade).
        """
        print('\n--- HUMANIZANDO TEXTO COM GEMINI (via Web) ---')

        if len(texto_bruto) > MAX_CHARS_GEMINI:
            return self._processar_chunks(texto_bruto)
        else:
            chunks = dividir_texto_inteligente(texto_bruto, MAX_CHARS_GEMINI)
            if len(chunks) == 1:
                return self._processar_chunks(texto_bruto) # reutiliza logica principal
            resultado = self._humanizar_chunk(texto_bruto)
            if resultado:
                aprovado, motivo = self._verificar_chunk(texto_bruto, resultado, 1)
                if aprovado:
                    print('[OK] Texto humanizado e validado com sucesso!')
                    return resultado
                print(f'[AVISO] Humanização simples reprovada na avaliação: {motivo}')
                return resultado # fallback

    def _processar_chunks(self, texto: str) -> Optional[str]:
        """Processa texto grande dividindo em chunks, humanizando sequencialmente com validação."""
        print(f'Texto grande detectado ({len(texto)} chars). Dividindo em partes...')
        chunks = dividir_texto_inteligente(texto, MAX_CHARS_GEMINI)
        total = len(chunks)
        print(f'Processando {total} partes...')

        textos_humanizados = []

        for i, chunk in enumerate(tqdm(chunks, desc='Humanizando', unit='parte'), 1):
            
            resultado_aprovado = None
            max_tentativas = 3

            for tentativa in range(1, max_tentativas + 1):
                try:
                    print(f'\n  [Progresso] Humanizando parte {i}/{total} (Tentativa {tentativa}/{max_tentativas})')
                    resultado_parcial = self._humanizar_chunk(chunk, i, total)
                    
                    if not resultado_parcial:
                        time.sleep(3)
                        continue

                    aprovado, motivo = self._verificar_chunk(chunk, resultado_parcial, i)
                    
                    if aprovado:
                        print(f'  [V] Parte {i} aprovada pela IA: {motivo}')
                        resultado_aprovado = resultado_parcial
                        break
                    else:
                        print(f'  [X] Parte {i} reprovada pela IA: {motivo}')
                        if tentativa < max_tentativas:
                            print(f'      Refazendo a parte {i}...')
                            time.sleep(4)

                except Exception as e:
                    if 'LOGIN_REQUIRED' in str(e):
                        print('\n[ERRO FATAL] Usuário não está logado no Gemini.')
                        print('  → Abra o app, clique em "Abrir Gemini" e faça login.')
                        return None
                    raise

            if not resultado_aprovado:
                print(f'\n[ERRO] Falha definitiva na parte {i}/{total} após {max_tentativas} tentativas (reprovada ou com erro).')
                # Por segurança, podemos abortar ou seguir com o último resultado falho. 
                # Abortando para garantir a qualidade estrita solicitada.
                return None

            textos_humanizados.append(resultado_aprovado)

        texto_final = '\n\n'.join(textos_humanizados)
        print(f'\n[OK] Texto humanizado e verificado com sucesso! ({total} partes)')
        return texto_final

