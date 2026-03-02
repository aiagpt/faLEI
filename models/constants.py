# Constantes do Sistema

# Limites de processamento
MAX_CHARS_GEMINI = 8000    # Máximo de chars por chunk enviado ao Gemini web
MAX_CHARS_TTS = 600        # Reduzido para 600 (SSML expande muito o tamanho em bytes)
FREE_TIER_CHARS = 4000000  # Cota mensal free tier (TTS)
SAFE_LIMIT_CHARS = 3500000 # Trava de segurança do usuário

# Configurações de Retry
MAX_RETRIES_TTS = 3
RATE_LIMIT_DELAY = 10.0   # 10s entre requisições (mais seguro para Free Tier)

# Vozes disponíveis
VOICES = {
    "pt-BR-Wavenet-A": {"gender": "FEMALE", "description": "Voz feminina premium"},
    "pt-BR-Wavenet-B": {"gender": "MALE",   "description": "Voz masculina premium"},
    "pt-BR-Wavenet-C": {"gender": "FEMALE", "description": "Voz feminina alternativa"},
}

# Configurações de áudio
AUDIO_CONFIG = {
    "sample_rate": 48000,
    "speaking_rate": 0.95,
    "pitch": -1.0,
}
