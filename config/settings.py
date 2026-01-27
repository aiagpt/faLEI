import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

class Settings:
    """Configurações centralizadas do sistema."""
    
    def __init__(self):
        # API Keys
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.google_credentials_path = self._find_credentials()
        self.ssl_verify = os.getenv("SSL_VERIFY", "False").lower() == "true"

        
        # Validações
        if self.google_credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.google_credentials_path
    
    def _find_credentials(self):
        """Procura automaticamente por arquivo de credenciais JSON."""
        path_atual = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        credentials_path = os.path.join(path_atual, "key.json")
        
        if os.path.exists(credentials_path):
            return credentials_path
        
        # Procurar outros arquivos JSON
        for f in os.listdir(path_atual):
            if f.endswith(".json") and f not in ["package.json", "tsconfig.json"]:
                return os.path.join(path_atual, f)
        
        return None
    
    def validate(self):
        """Valida se as configurações necessárias estão presentes."""
        errors = []
        
        if not self.gemini_api_key or self.gemini_api_key == "SUA_CHAVE_AQUI":
            errors.append("GEMINI_API_KEY não configurada no .env")
        
        if not self.google_credentials_path:
            errors.append("Arquivo de credenciais Google Cloud não encontrado")
        
        return errors

# Instância global
settings = Settings()
