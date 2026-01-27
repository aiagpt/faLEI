import requests
from bs4 import BeautifulSoup
from typing import Optional
import re
import urllib3

# Desabilitar avisos de SSL (necessário para alguns sites governamentais)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class WebScraper:
    """Extrai texto de leis publicadas em HTML."""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def buscar_lei(self, url: str) -> Optional[str]:
        """
        Busca e extrai o texto de uma lei a partir de uma URL.
        
        Args:
            url: URL da lei (formato HTML)
        
        Returns:
            Texto extraído ou None em caso de erro
        """
        try:
            print(f"\n[INFO] Buscando lei em: {url}")
            
            # Fazer requisição (verify=False para sites gov com SSL antigo)
            from config.settings import settings
            response = requests.get(
                url, 
                headers=self.headers, 
                timeout=30,
                verify=settings.ssl_verify  # Configurado no .env (padrão False)
            )
            response.raise_for_status()
            
            # Tratamento especial para Planalto (geralmente Latin-1/Windows-1252 incorreto)
            if 'planalto.gov.br' in url:
                response.encoding = 'windows-1252'
            
            # Detectar encoding correto (fallback)
            elif response.encoding and response.encoding.lower() in ['iso-8859-1', 'latin-1', 'windows-1252']:
                response.encoding = 'ISO-8859-1'
            elif not response.encoding or response.encoding == 'ISO-8859-1':
                if 'charset=iso-8859-1' in response.text.lower() or 'charset=latin1' in response.text.lower():
                    response.encoding = 'ISO-8859-1'
                else:
                    response.encoding = 'utf-8'
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser', from_encoding=response.encoding)
            
            # Tentar extrair texto do corpo principal
            texto = self._extrair_texto(soup)
            
            if texto:
                print(f"[OK] Lei extraida com sucesso! ({len(texto)} caracteres)")
                return texto
            else:
                print("[X] Nao foi possivel extrair o texto da lei.")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"✗ Erro ao buscar URL: {e}")
            return None
        except Exception as e:
            print(f"[X] Erro ao processar HTML: {e}")
            return None
    
    def _extrair_texto(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrai texto do HTML usando várias estratégias."""
        
        # Estratégia 1: Procurar por tags comuns de conteúdo
        content_tags = [
            soup.find('div', class_=re.compile(r'content|texto|lei|artigo', re.I)),
            soup.find('article'),
            soup.find('main'),
            soup.find('body')
        ]
        
        for tag in content_tags:
            if tag:
                # Remover hyperlinks (tags <a>) ANTES de processar
                self._remover_hyperlinks(tag)
                
                # Processar tabelas ANTES de remover outros elementos
                self._processar_tabelas(tag)
                
                # Remover elementos tachados (texto revogado/alterado)
                for strikethrough in tag.find_all(['strike', 's', 'del']):
                    strikethrough.decompose()
                
                # Remover elementos com estilo text-decoration: line-through
                for element in tag.find_all(style=re.compile(r'text-decoration:\s*line-through', re.I)):
                    element.decompose()
                
                # Remover scripts, styles e outros elementos não desejados
                for script in tag(['script', 'style', 'nav', 'header', 'footer']):
                    script.decompose()
                
                # Extrair texto
                texto = tag.get_text(separator='\n', strip=True)
                
                # Limpar texto
                texto = self._limpar_texto(texto)
                
                # Validar se tem conteúdo relevante (relaxado)
                # Planalto as vezes usa "Art " sem ponto ou está em caixa alta
                texto_lower = texto.lower()
                if 'art' in texto_lower or 'lei' in texto_lower or 'decreto' in texto_lower or 'portaria' in texto_lower:
                    return texto
                
                # Se o texto for longo o suficiente, aceita mesmo sem "Art."
                if len(texto) > 500:
                    return texto
        
        return None
    
    def _remover_hyperlinks(self, tag: BeautifulSoup) -> None:
        """
        Remove hyperlinks (tags <a>) do conteúdo, mantendo apenas o texto interno.
        Preserva textos importantes como "VETADO", "Revogado", etc.
        
        Args:
            tag: Tag BeautifulSoup contendo o conteúdo
        """
        for link in tag.find_all('a'):
            texto_link = link.get_text(strip=True)
            
            # Preservar textos jurídicos importantes mesmo que sejam hyperlinks
            textos_importantes = ['VETADO', 'REVOGADO', 'REVOGADA', 'ALTERADO', 'ALTERADA', 
                                 'INCLUÍDO', 'INCLUÍDA', 'ACRESCIDO', 'ACRESCIDA']
            
            # Se o texto do link é importante, manter entre parênteses
            if texto_link.upper() in textos_importantes:
                link.replace_with(f"({texto_link})")
            else:
                # Caso contrário, substituir apenas pelo texto
                link.replace_with(texto_link)
    
    def _processar_tabelas(self, tag: BeautifulSoup) -> None:
        """
        Substitui tabelas HTML por descrições textuais acessíveis.
        
        Args:
            tag: Tag BeautifulSoup contendo o conteúdo
        """
        tabelas = tag.find_all('table')
        
        for idx, tabela in enumerate(tabelas, 1):
            # Extrair cabeçalhos
            headers = []
            thead = tabela.find('thead')
            if thead:
                header_cells = thead.find_all(['th', 'td'])
                headers = [cell.get_text(strip=True) for cell in header_cells if cell.get_text(strip=True)]
            
            # Se não tem thead, tentar primeira linha
            if not headers:
                first_row = tabela.find('tr')
                if first_row:
                    header_cells = first_row.find_all('th')
                    if header_cells:
                        headers = [cell.get_text(strip=True) for cell in header_cells if cell.get_text(strip=True)]
            
            # Extrair linhas de dados
            linhas_dados = []
            tbody = tabela.find('tbody') or tabela
            rows = tbody.find_all('tr')
            
            # Pular primeira linha se foi usada como cabeçalho
            start_idx = 1 if headers and not thead else 0
            
            for row in rows[start_idx:]:
                cells = row.find_all(['td', 'th'])
                linha = [cell.get_text(strip=True) for cell in cells if cell.get_text(strip=True)]
                if linha:  # Só adicionar se tiver conteúdo
                    linhas_dados.append(linha)
            
            # Criar descrição textual
            descricao = self._criar_descricao_tabela(headers, linhas_dados, idx)
            
            # Substituir tabela pela descrição
            tabela.replace_with(descricao)
    
    def _criar_descricao_tabela(self, headers: list, linhas: list, numero: int) -> str:
        """
        Cria uma descrição textual de uma tabela.
        
        Args:
            headers: Lista de cabeçalhos
            linhas: Lista de linhas (cada linha é uma lista de células)
            numero: Número da tabela
        
        Returns:
            Descrição textual da tabela
        """
        partes = []
        
        # Introdução
        num_linhas = len(linhas)
        num_colunas = len(headers) if headers else (len(linhas[0]) if linhas else 0)
        
        partes.append(f"\n[Início da Tabela {numero}]")
        partes.append(f"Tabela com {num_linhas} linha{'s' if num_linhas != 1 else ''} e {num_colunas} coluna{'s' if num_colunas != 1 else ''}.")
        
        # Cabeçalhos
        if headers:
            partes.append(f"Colunas: {', '.join(headers)}.")
        
        # Dados
        for i, linha in enumerate(linhas, 1):
            if headers and len(linha) == len(headers):
                # Descrever com nome das colunas
                descricao_linha = []
                for header, valor in zip(headers, linha):
                    descricao_linha.append(f"{header}: {valor}")
                partes.append(f"Linha {i}: {'; '.join(descricao_linha)}.")
            else:
                # Descrever sem cabeçalhos
                partes.append(f"Linha {i}: {', '.join(linha)}.")
        
        partes.append(f"[Fim da Tabela {numero}]\n")
        
        return '\n'.join(partes)
    
    def _limpar_texto(self, texto: str) -> str:
        """Limpa e formata o texto extraído."""
        # Remover linhas vazias excessivas
        linhas = [linha.strip() for linha in texto.split('\n') if linha.strip()]
        texto = '\n'.join(linhas)
        
        # Remover espaços múltiplos
        texto = re.sub(r' +', ' ', texto)
        
        # Remover padrões de hyperlinks APENAS entre parênteses
        # Remove (hyperlink), (link), (clique aqui), etc.
        texto = re.sub(r'\s*\((?:hyperlink|link|clique\s+aqui|veja\s+mais|saiba\s+mais)\)\s*', ' ', texto, flags=re.IGNORECASE)
        
        # Remover parênteses vazios que sobraram
        texto = re.sub(r'\s*\(\s*\)\s*', ' ', texto)
        
        # Limpar espaços múltiplos novamente
        texto = re.sub(r' +', ' ', texto)
        
        # Limpar espaços antes de pontuação
        texto = re.sub(r'\s+([.,;:])', r'\1', texto)
        
        return texto

def buscar_lei_por_url(url: str) -> Optional[str]:
    """
    Função helper para buscar lei por URL.
    
    Args:
        url: URL da lei
    
    Returns:
        Texto da lei ou None
    """
    scraper = WebScraper()
    return scraper.buscar_lei(url)
