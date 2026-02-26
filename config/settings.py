import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

class Settings:
    """Configurações centralizadas do sistema."""
    
    def __init__(self):
        # Credenciais Google Cloud (para TTS)
        self.google_credentials_path = self._find_credentials()
        self.ssl_verify = os.getenv("SSL_VERIFY", "False").lower() == "true"

        # Porta do servidor bridge Electron/Gemini
        self.electron_ipc_port = int(os.getenv("ELECTRON_IPC_PORT", 5001))
        
        if self.google_credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.google_credentials_path
    
    def _find_credentials(self):
        """Procura automaticamente por arquivo de credenciais JSON."""
        path_atual = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        credentials_path = os.path.join(path_atual, "key.json")
        
        if os.path.exists(credentials_path):
            return credentials_path
        
        for f in os.listdir(path_atual):
            if f.endswith(".json") and f not in ["package.json", "tsconfig.json", "package-lock.json"]:
                return os.path.join(path_atual, f)
        
        return None
    
    def validate(self):
        """Valida se as configurações necessárias estão presentes."""
        errors = []
        
        # Gemini: agora usa automação web (não precisa de API key)
        # TTS precisa do key.json — mas pode ser ignorado no modo SKIP_TTS
        skip_tts = os.getenv('SKIP_TTS', '0') == '1'
        if not skip_tts and not self.google_credentials_path:
            errors.append("Arquivo de credenciais Google Cloud (key.json) não encontrado — necessário para o TTS")
        
        return errors

# Instância global
settings = Settings()

