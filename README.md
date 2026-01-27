# Sistema de Conversão de Leis para Áudio

Sistema modular para converter textos jurídicos brasileiros em áudio de alta qualidade usando Gemini (humanização) e Google Cloud Text-to-Speech.

## 📁 Estrutura do Projeto

```
voz/
├── main.py                    # Ponto de entrada principal
├── .env                       # Variáveis de ambiente (API keys)
├── key.json                   # Credenciais Google Cloud
├── README.md                  # Este arquivo
│
├── config/
│   └── settings.py           # Configurações centralizadas
│
├── services/
│   ├── gemini_service.py     # Serviço de humanização de texto
│   └── tts_service.py        # Serviço de síntese de voz
│
├── utils/
│   ├── text_processor.py     # Processamento e chunking de texto
│   ├── audio_merger.py       # Mesclagem de arquivos de áudio
│   └── web_scraper.py        # Extração de leis da web
│
└── models/
    └── constants.py          # Constantes do sistema
```

## 🚀 Instalação

### 1. Dependências Python

```bash
pip install google-cloud-texttospeech google-auth google-generativeai python-dotenv beautifulsoup4 requests tqdm
```

### 2. FFmpeg (Opcional - apenas para textos muito grandes)

**Windows:**
```powershell
winget install ffmpeg
```

Ou baixe em: https://ffmpeg.org/download.html

> **Nota:** FFmpeg só é necessário se você for processar leis com mais de 4.500 caracteres que precisem ser divididas em múltiplos arquivos de áudio.

### 3. Configuração

#### a) Gemini API Key

1. Acesse: https://aistudio.google.com/app/apikey
2. Crie uma API Key
3. Adicione no `.env`:
```
GEMINI_API_KEY=sua_chave_aqui
```

#### b) Google Cloud Credentials

1. Acesse: https://console.cloud.google.com/
2. Crie um projeto
3. Ative a API "Cloud Text-to-Speech"
4. Ative o faturamento (necessário mesmo para free tier)
5. Crie uma Service Account
6. Baixe o JSON e salve como `key.json` na raiz do projeto

## 📖 Uso

### Modo Interativo (Recomendado)

```bash
python main.py
```

O sistema vai solicitar:
```
➤ URL da lei: https://www3.al.es.gov.br/Arquivo/Documents/legislacao/html/LO6200.html
```

Cole a URL de qualquer lei em formato HTML.

### Modo Programático

```python
from services.gemini_service import GeminiService
from services.tts_service import TTSService
from utils.web_scraper import buscar_lei_por_url

# Buscar lei
texto = buscar_lei_por_url("https://www3.al.es.gov.br/.../LO6200.html")

# Humanizar
gemini = GeminiService()
texto_humanizado = gemini.humanizar_texto(texto)

# Gerar áudio
tts = TTSService(voice_name="pt-BR-Wavenet-B")
tts.sintetizar_arquivo(texto_humanizado, "output.mp3")
```

## 🎯 Recursos

- ✅ **Busca automática** de leis via URL
- ✅ **Humanização** com Gemini (expande abreviações)
- ✅ Suporte para textos de **500k+ caracteres**
- ✅ Chunking inteligente (respeita limites de artigos)
- ✅ Progress bars em tempo real
- ✅ Retry logic com exponential backoff
- ✅ Rate limiting (evita erro 429)
- ✅ Merge automático de áudios (se ffmpeg instalado)
- ✅ Bypass de SSL para sites governamentais

## 🔧 Configurações Disponíveis

### Vozes (em `models/constants.py`)

- `pt-BR-Wavenet-A`: Feminina premium
- `pt-BR-Wavenet-B`: Masculina premium (padrão)
- `pt-BR-Wavenet-C`: Feminina alternativa

### Parâmetros de Áudio

- Sample rate: 48kHz
- Speaking rate: 0.95 (mais lento)
- Pitch: -1.0 (tom grave/autoritário)

## 📊 Limites

- **Gemini**: 25k caracteres por chunk
- **TTS**: 4.5k caracteres por chunk
- **Free Tier**: 4M caracteres/mês (Standard), 1M (WaveNet)

## 🐛 Troubleshooting

### Erro: "pydub não disponível"
- **Solução**: Instale ffmpeg (veja seção de instalação)
- **Impacto**: Apenas para textos grandes (>4.5k chars)
- Para textos pequenos, funciona normalmente sem ffmpeg

### Erro: "429 Quota exceeded"
- **Solução**: Aguarde alguns segundos entre execuções
- O script já tem rate limiting automático (1.5s entre chunks)

### Erro: "Credentials not found"
- Verifique se `key.json` está na raiz do projeto
- Ou configure `GOOGLE_APPLICATION_CREDENTIALS` no ambiente

### Erro: "SSL Certificate"
- O script já ignora erros de SSL para sites governamentais
- Isso é seguro para URLs conhecidas (.gov.br)

## 📝 Exemplo de Uso Completo

```bash
# 1. Execute o script
python main.py

# 2. Cole a URL quando solicitado
➤ URL da lei: https://www3.al.es.gov.br/Arquivo/Documents/legislacao/html/LO6200.html

# 3. Aguarde o processamento
📥 Buscando lei...
✓ Lei extraída com sucesso! (12345 caracteres)

--- HUMANIZANDO TEXTO COM GEMINI ---
Humanizando: 100%|████████| 1/1 [00:03<00:00, 3.2s/parte]
✓ Texto humanizado com sucesso!

--- PROCESSANDO ÁUDIO ---
Gerando áudio: 100%|████████| 3/3 [00:15<00:00, 5.1s/parte]
✓ SUCESSO: Áudio completo salvo em 'LO6200.mp3'

# 4. Arquivo gerado: LO6200.mp3
```

## 📄 Licença

MIT
