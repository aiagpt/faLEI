# Padrão: Automação de IA via Janela Web Embutida (Electron)

> **Objetivo:** Documentar como o projeto *Processador de Chunk* usa o Gemini (e o ChatGPT) **sem a API oficial**, interagindo diretamente com a interface web das plataformas através de uma janela Electron oculta e injeção de JavaScript.

---

## Visão Geral do Padrão

Em vez de consumir a API REST do Gemini (que exige chave paga e tem limites de uso), o projeto utiliza uma técnica de **Web Scraping / DOM Automation** via `BrowserWindow` do Electron. O fluxo é:

```
Renderer (UI)
    │
    ▼ ipcRenderer.invoke('summarize-auto', texto)
Main Process (main.js)
    │https://github.com/aiagpt/faLEI.git
    ▼ Abre/Reusa uma BrowserWindow oculta → https://gemini.google.com/app
    │
    ▼ webContents.executeJavaScript(script)
       → Digita o prompt no chat
       → Clica no botão Enviar
       → Aguarda a resposta estabilizar no DOM
       → Retorna o texto da resposta
    │
    ▼ Retorna resultado para a UI via IPC
```

**Vantagem:** Usa a **sessão do usuário já logada** no Gemini, sem precisar de API Key.  
**Desvantagem:** Frágil a mudanças nos seletores CSS/DOM da plataforma de IA.

---

## Arquitetura em 3 Camadas

### Camada 1: Main Process ([main.js](file:///c:/Users/%C3%81gape/Desktop/projetos/Processador_de_chunk_V2/programa/main.js))

É o núcleo do padrão. Contém:

1. **Variável da janela** — referência global para a `BrowserWindow` da IA.
2. **Função [createGeminiWindow()](file:///c:/Users/%C3%81gape/Desktop/projetos/Processador_de_chunk_V2/programa/main.js#375-392)** — cria a janela oculta com sessão persistente.
3. **Função [runGeminiAutomation(text)](file:///c:/Users/%C3%81gape/Desktop/projetos/Processador_de_chunk_V2/programa/main.js#75-204)** — o script de automação principal.
4. **Handler IPC `summarize-auto`** — expõe a função para a UI, com lógica de retry.

```js
// main.js
const { app, BrowserWindow, ipcMain } = require('electron');

let geminiWindow; // Referência global da janela

// --- 1. Criar a Janela Oculta ---
function createGeminiWindow() {
    geminiWindow = new BrowserWindow({
        width: 1000,
        height: 800,
        show: false, // OCULTA! O usuário não vê (a não ser que queira)
        title: "Gemini Automation (Não feche!)",
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            backgroundThrottling: false, // CRÍTICO: evita que a janela "congele" em background
            partition: 'persist:gemini'  // CRÍTICO: salva cookies/sessão de login entre reinicializações
        }
    });

    geminiWindow.loadURL('https://gemini.google.com/app');

    geminiWindow.on('close', () => {
        geminiWindow = null; // Limpa a referência ao fechar
    });
}

// --- 2. IPC Handler com Retry Automático ---
ipcMain.handle('summarize-auto', async (event, text) => {
    while (true) { // Loop infinito de tentativas
        for (let i = 1; i <= 3; i++) { // 3 tentativas por ciclo
            try {
                const result = await runGeminiAutomation(text);
                return { success: true, text: result };
            } catch (error) {
                console.error(`Gemini tentativa ${i} falhou:`, error.message);
                if (i < 3) await new Promise(r => setTimeout(r, 2000)); // Espera 2s entre tentativas
            }
        }
        // Após 3 falhas: fecha a janela e recria no próximo ciclo
        if (geminiWindow && !geminiWindow.isDestroyed()) {
            geminiWindow.destroy();
            geminiWindow = null;
        }
        await new Promise(r => setTimeout(r, 3000));
    }
});
```

---

### Camada 2: Função de Automação DOM ([runGeminiAutomation](file:///c:/Users/%C3%81gape/Desktop/projetos/Processador_de_chunk_V2/programa/main.js#75-204))

Esta função é a mais complexa. Ela:

1. Garante que a janela existe e está carregada.
2. Injeta um script JS que automatiza o chat.
3. Retorna o texto da resposta.

```js
// main.js (continuação)
async function runGeminiAutomation(text) {
    // Cria a janela se não existir
    if (!geminiWindow || geminiWindow.isDestroyed()) createGeminiWindow();

    // Aguarda o carregamento inicial (com timeout de segurança)
    if (geminiWindow.webContents.isLoading()) {
        await new Promise((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error("Timeout")), 10000);
            geminiWindow.webContents.once('did-finish-load', () => {
                clearTimeout(timeout);
                resolve();
            });
        }).catch(() => console.log("Timeout ignorado, prosseguindo..."));
    }

    // Dá um tempo para a página "hidratar" (renderizar o React/Angular)
    await new Promise(r => setTimeout(r, 2000));

    // O script que roda DENTRO da página do Gemini
    const script = `
        (async () => {
            // Utilitário: espera um seletor aparecer no DOM
            const waitForSelector = async (selector, timeout = 10000) => {
                const start = Date.now();
                while (Date.now() - start < timeout) {
                    const el = document.querySelector(selector);
                    if (el) return el;
                    await new Promise(r => setTimeout(r, 500));
                }
                return null;
            };

            try {
                // PASSO 1: Localizar a caixa de texto
                // O Gemini usa um div contenteditable, não um <input> ou <textarea>
                const input = await waitForSelector('div[contenteditable="true"]', 8000);

                // Checar se não carregou por falta de login
                if (!input) {
                    const bodyText = document.body.innerText;
                    if (bodyText.includes("Fazer login") || bodyText.includes("Sign in")) {
                        return "ERROR: Usuário não está logado no Gemini.";
                    }
                    return "ERROR: Caixa de texto não encontrada.";
                }

                // PASSO 2: Digitar o prompt
                input.focus();
                const prompt = 'Seu prompt aqui: ' + ${JSON.stringify(text)};
                // execCommand é aceito em contenteditable (sem precisar simular cada tecla)
                document.execCommand('insertText', false, prompt);

                // Aguarda o botão de envio ficar ativo
                await new Promise(r => setTimeout(r, 1000));

                // PASSO 3: Clicar no botão Enviar
                // O aria-label varia conforme idioma ("Send" em inglês, "Enviar" em português)
                const sendBtn = await waitForSelector(
                    'button[aria-label*="Send"], button[aria-label*="Enviar"]',
                    5000
                );
                if (!sendBtn) return "ERROR: Botão Enviar não encontrado.";
                sendBtn.click();

                // PASSO 4: Aguardar a resposta estabilizar
                await new Promise(r => setTimeout(r, 2000)); // Buffer inicial

                let lastText = "";
                let stableCount = 0;

                // Polling por até 60 segundos
                for (let i = 0; i < 60; i++) {
                    await new Promise(r => setTimeout(r, 1000));

                    // Seletores da resposta (podem mudar com updates do Gemini!)
                    const responses = document.querySelectorAll(
                        '.model-response-text, .message-content, markdown-renderer'
                    );

                    if (responses.length > 0) {
                        const currentText = responses[responses.length - 1].innerText;

                        // Considera "estável" se o texto não mudou por 3 segundos consecutivos
                        if (currentText && currentText.length > 20 && currentText === lastText) {
                            stableCount++;
                            if (stableCount > 3) return currentText; // SUCESSO
                        } else {
                            stableCount = 0;
                        }
                        lastText = currentText;
                    }
                }

                return lastText || "TIMEOUT: Gemini demorou demais.";

            } catch (e) {
                return "ERROR: " + e.message;
            }
        })();
    `;

    // Executa o script na janela do Gemini e aguarda o resultado
    const result = await geminiWindow.webContents.executeJavaScript(script);

    // Propaga erros para o sistema de retry
    if (result.startsWith("ERROR") || result.startsWith("TIMEOUT")) {
        throw new Error(result);
    }

    return result;
}
```

---

### Camada 3: Preload e Renderer

O [preload.js](file:///c:/Users/%C3%81gape/Desktop/projetos/Processador_de_chunk_V2/programa/preload.js) expõe os handlers IPC de forma segura para a UI (nunca exponha `ipcRenderer` diretamente):

```js
// preload.js
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // Abre a janela do Gemini manualmente (para o usuário fazer login)
    openGemini: () => ipcRenderer.send('open-gemini'),

    // Envia um texto para resumo e aguarda a resposta
    summarizeAuto: (text) => ipcRenderer.invoke('summarize-auto', text),
});
```

No [renderer.js](file:///c:/Users/%C3%81gape/Desktop/projetos/Processador_de_chunk_V2/programa/renderer.js) (a interface HTML/JS), o uso é simples:

```js
// renderer.js
async function resumirChunk(texto) {
    try {
        const resultado = await window.electronAPI.summarizeAuto(texto);
        if (resultado.success) {
            console.log("Resumo:", resultado.text);
        }
    } catch (e) {
        console.error("Erro ao resumir:", e);
    }
}
```

---

## Fluxo de Login pelo Usuário

Como o programa usa a sessão do usuário, o fluxo de setup é:

1. **Na primeira execução**, a janela do Gemini é criada oculta. O usuário clica em **"Abrir Gemini"** para que ela apareça visível.
2. **Faz login** normalmente no `gemini.google.com`.
3. A partir daí, graças à opção `partition: 'persist:gemini'`, os cookies ficam salvos e **não é necessário logar novamente**, mesmo após reiniciar o app.

```js
// IPC handler para o botão "Abrir Gemini"
ipcMain.on('open-gemini', () => {
    if (!geminiWindow || geminiWindow.isDestroyed()) {
        createGeminiWindow();
    }
    geminiWindow.show(); // Torna visível para o usuário logar
    geminiWindow.focus();
});
```

---

## Pontos de Atenção (Pontos Frágeis)

| Ponto | Risco | Mitigação |
|---|---|---|
| **Seletor `div[contenteditable="true"]`** | O Gemini pode adicionar atributos ou trocar a estrutura | Adicionar seletores alternativos com fallback |
| **Seletor `button[aria-label*="Send"]`** | Muda conforme idioma ou update da plataforma | Testar com `aria-label*="Enviar"` e `aria-label*="Send"` |
| **Seletores de resposta** (`.model-response-text`, etc.) | Os mais frágeis — o Gemini muda classes frequentemente | Monitorar e atualizar periodicamente |
| **`document.execCommand('insertText')`** | Pode ser removido em futuras versões dos browsers | Usar como fallback `input.textContent = ...` + evento `input` |
| **Login necessário** | Sem login a automação não funciona | Detectar o estado de login e avisar o usuário |

---

## Como Adaptar para Outro Projeto

### Checklist de Implementação

- [ ] Instalar o Electron (`npm install electron --save-dev`)
- [ ] Criar `createAiWindow()` com `partition: 'persist:NOME_DA_IA'` e `show: false`
- [ ] Criar `runAiAutomation(text)` com a lógica de injeção de script
- [ ] Criar handler IPC `ipcMain.handle('ai-task', ...)` com retry
- [ ] Expor via `contextBridge` no [preload.js](file:///c:/Users/%C3%81gape/Desktop/projetos/Processador_de_chunk_V2/programa/preload.js)
- [ ] Chamar via `window.electronAPI.nomeDoMetodo(texto)` no frontend
- [ ] Criar botão "Abrir [IA]" para o usuário fazer login manualmente na primeira execução

### Adaptando para ChatGPT

Basta trocar a URL e os seletores:

```js
// ChatGPT
window.loadURL('https://chatgpt.com/');

// Seletor do input (ChatGPT usa <textarea>)
const input = document.querySelector('#prompt-textarea');
input.innerText = prompt;
input.dispatchEvent(new Event('input', { bubbles: true })); // Necessário para React

// Botão Enviar
const sendBtn = document.querySelector('button[data-testid="send-button"]');

// Capturar resposta
const responses = document.querySelectorAll('.markdown');
const currentText = responses[responses.length - 1].innerText;

// Aguardar fim: monitorar desaparecimento do botão "Stop"
const stopBtn = document.querySelector('button[aria-label="Stop generating"]');
if (!stopBtn && currentText) return currentText; // Geração concluída
```

---

## Exemplo de Prompt Estruturado

O projeto usa um prompt com **formato de saída controlado** para facilitar o parsing:

```
"Analise este texto.
Se houver problemas, responda: STATUS: ERRO | LISTA_ERROS: [...]
Se estiver válido, responda: STATUS: OK
RESUMO: [seu resumo] FIM DO RESUMO

Texto: [CONTEÚDO AQUI]"
```

Isso permite parsear a resposta com segurança:

```js
if (response.includes("STATUS: OK")) {
    const resumo = response.match(/RESUMO: (.+?) FIM DO RESUMO/s)?.[1];
}
```
