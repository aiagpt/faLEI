const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow;
let flaskProcess;
let geminiWindow = null; // Janela oculta do Gemini

// --- Fila para pedidos de humanização vindos do Flask ---
// Cada item: { text, resolve, reject }
let humanizeQueue = [];
let isProcessingQueue = false;

const FLASK_HOST = '127.0.0.1';
const FLASK_PORT = 5000;
const FLASK_URL = `http://${FLASK_HOST}:${FLASK_PORT}`;

// Porta do servidor de IPC HTTP (usado pelo Flask para solicitar humanização)
const IPC_PORT = 5001;

const fs = require('fs');

const logStream = fs.createWriteStream(path.join(__dirname, 'app.log'), { flags: 'a' });

function log(msg) {
    const time = new Date().toISOString();
    const entry = `[${time}] ${msg}\n`;
    console.log(msg);
    logStream.write(entry);
}

// ===========================================================
// GEMINI WEB AUTOMATION
// ===========================================================

function createGeminiWindow() {
    log('Criando janela do Gemini (oculta)...');
    geminiWindow = new BrowserWindow({
        width: 1100,
        height: 800,
        show: false,
        title: 'Gemini (faLEI - não feche!)',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            backgroundThrottling: false, // Crítico: evita congelar em background
            partition: 'persist:gemini'  // Crítico: salva a sessão de login
        }
    });

    geminiWindow.loadURL('https://gemini.google.com/app');

    geminiWindow.webContents.on('did-fail-load', (event, code, desc) => {
        log(`[Gemini] Falha ao carregar: ${desc} (código ${code})`);
    });

    geminiWindow.on('closed', () => {
        log('[Gemini] Janela fechada.');
        geminiWindow = null;
    });
}

/**
 * Abre a janela do Gemini de forma visível para que o usuário possa fazer login.
 */
function showGeminiWindow() {
    if (!geminiWindow || geminiWindow.isDestroyed()) {
        createGeminiWindow();
    }
    geminiWindow.show();
    geminiWindow.focus();
}

/**
 * Envia um texto para o Gemini via automação de DOM e retorna a resposta.
 * @param {string} text - O texto do chunk a ser humanizado
 * @param {string} prompt - O prompt completo para humanização
 * @returns {Promise<string>}
 */
async function runGeminiAutomation(text, prompt) {
    if (!geminiWindow || geminiWindow.isDestroyed()) {
        createGeminiWindow();
    }

    // Aguarda o carregamento da página (com timeout de segurança)
    if (geminiWindow.webContents.isLoading()) {
        await new Promise((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error('Timeout carregando Gemini')), 15000);
            geminiWindow.webContents.once('did-finish-load', () => {
                clearTimeout(timeout);
                resolve();
            });
        }).catch(e => log(`[Gemini] ${e.message}, prosseguindo mesmo assim...`));
    }

    // Iniciar nova conversa limpa — sem navegar por URL (evita cancelamento mid-script por redirect)
    const currentURL = geminiWindow.webContents.getURL();
    const alreadyOnGemini = currentURL.includes('gemini.google.com');

    if (alreadyOnGemini) {
        // Tentar clicar no botão "New chat" para começar conversa limpa
        try {
            await geminiWindow.webContents.executeJavaScript(`
                (() => {
                    const btn = document.querySelector(
                        'a[href*="/app"][aria-label*="new" i], ' +
                        'a[href*="/app"][aria-label*="nova" i], ' +
                        'button[aria-label*="new chat" i], ' +
                        'button[aria-label*="nova conversa" i], ' +
                        'a[data-test-id*="new"], ' +
                        'nav a[href="/app"]'
                    );
                    if (btn) { btn.click(); return true; }
                    return false;
                })()
            `);
            await new Promise(r => setTimeout(r, 3000));
        } catch (e) {
            log('[Gemini] Botão new chat não encontrado, navegando...');
            geminiWindow.loadURL('https://gemini.google.com/app');
            // Esperar a URL estabilizar (não só did-finish-load, que dispara nos redirects)
            await new Promise(r => setTimeout(r, 6000));
        }
    } else {
        geminiWindow.loadURL('https://gemini.google.com/app');
        await new Promise(r => setTimeout(r, 6000));
    }

    // Buffer extra para o SPA hidratar
    await new Promise(r => setTimeout(r, 2000));

    const fullPrompt = prompt + '\n\n' + text;

    // Injetar o texto como variável global PRIMEIRO (evita problemas de escaping no template literal)
    await geminiWindow.webContents.executeJavaScript(
        `window.__faLeiPrompt = ${JSON.stringify(fullPrompt)};`
    );

    const script = `
        (async () => {
            const waitForSelector = async (selector, timeout = 12000) => {
                const start = Date.now();
                while (Date.now() - start < timeout) {
                    const el = document.querySelector(selector);
                    if (el) return el;
                    await new Promise(r => setTimeout(r, 500));
                }
                return null;
            };

            try {
                // Passo 1: Aguardar a caixa de texto
                const input = await waitForSelector('div[contenteditable="true"]', 12000);
                if (!input) {
                    return 'ERROR_LOGIN: Caixa de texto não encontrada — o Gemini pode precisar de login ou ainda está carregando.';
                }

                // Passo 2: Contar respostas ANTES de enviar (para só pegar a nova)
                const countBefore = document.querySelectorAll('model-response').length;

                // Passo 3: Inserir o prompt via variável global (sem embedding no script)
                input.focus();
                while (input.firstChild) input.removeChild(input.firstChild);

                const textToInsert = window.__faLeiPrompt || '';
                if (!textToInsert) return 'ERROR: Variável __faLeiPrompt não encontrada.';

                const inserted = document.execCommand('insertText', false, textToInsert);

                // Fallback se execCommand não funcionou
                if (!inserted || !input.textContent.trim()) {
                    while (input.firstChild) input.removeChild(input.firstChild);
                    const p = document.createElement('p');
                    p.textContent = textToInsert;
                    input.appendChild(p);
                    input.dispatchEvent(new InputEvent('input', {
                        bubbles: true,
                        cancelable: true,
                        inputType: 'insertText',
                        data: textToInsert
                    }));
                }

                if (!input.textContent.trim()) {
                    return 'ERROR: Não foi possível inserir texto na caixa do Gemini.';
                }

                await new Promise(r => setTimeout(r, 1500));

                // Passo 4: Clicar no botão Enviar
                const sendBtn = await waitForSelector(
                    'button[aria-label*="Send"], button[aria-label*="Enviar"], button[aria-label*="send"]',
                    6000
                );
                if (!sendBtn) return 'ERROR: Botão Enviar não encontrado no Gemini.';
                sendBtn.click();

                // Passo 5: Aguardar a NOVA model-response aparecer
                await new Promise(r => setTimeout(r, 3000));

                let lastText = '';
                let stableCount = 0;

                for (let i = 0; i < 120; i++) {
                    await new Promise(r => setTimeout(r, 1000));

                    // Como pode ser uma única UI reativa, pegar todos
                    const allResponses = document.querySelectorAll('model-response');
                    if (allResponses.length === 0) continue;

                    // O Gemini costuma adicionar as respostas no fim.
                    // Nos precaivemos caso "countBefore" falhe na recriação de tela nova:
                    const lastResponse = allResponses[allResponses.length - 1];
                    const markdownBlock = lastResponse.querySelector('.markdown, .model-response-text, message-content');
                    const currentText = (markdownBlock || lastResponse).innerText || '';

                    if (currentText && currentText.trim().length > 0 && currentText === lastText) {
                        stableCount++;
                        if (stableCount >= 3) {
                            return currentText
                                .split('\\n')
                                .filter(line => {
                                    const l = line.trim();
                                    return l !== 'Fontes'
                                        && !l.startsWith('O Gemini disse')
                                        && !l.startsWith('Mostrar rascunhos')
                                        && !l.startsWith('volume_up')
                                        && !l.startsWith('content_copy')
                                        && !l.startsWith('thumb_up')
                                        && !l.startsWith('thumb_down')
                                        && !l.startsWith('more_vert');
                                })
                                .join('\\n')
                                .trim();

                        }
                    } else if (currentText && currentText.trim().length > 0) {
                        stableCount = 0;
                        lastText = currentText;
                    }
                }

                return lastText || 'TIMEOUT: Gemini demorou demais para responder.';

            } catch (e) {
                return 'ERROR: ' + e.message;
            }
        })();
    `;


    log('[Gemini] Executando script de automação...');
    let result;
    try {
        result = await geminiWindow.webContents.executeJavaScript(script);
    } catch (scriptErr) {
        log(`[Gemini] ERRO ao executar script: ${scriptErr.message}`);
        throw new Error(`Script failed to execute: ${scriptErr.message}`);
    }

    log(`[Gemini] Script retornou: "${String(result).substring(0, 150)}..."`);

    if (typeof result === 'string' && (result.startsWith('ERROR') || result.startsWith('TIMEOUT'))) {
        throw new Error(result);
    }

    return result;
}


/**
 * Aguarda o usuário logar no Gemini (polling do DOM).
 * Abre a janela automaticamente e monitora até o login ser detectado.
 */
async function waitForLogin(timeoutMs = 300000) {
    log('[Gemini] Login necessário — abrindo janela automaticamente...');
    showGeminiWindow(); // Mostra a janela para o usuário logar

    const start = Date.now();

    while (Date.now() - start < timeoutMs) {
        await new Promise(r => setTimeout(r, 3000)); // verifica a cada 3 segundos

        if (!geminiWindow || geminiWindow.isDestroyed()) {
            createGeminiWindow();
            showGeminiWindow();
            await new Promise(r => setTimeout(r, 3000));
            continue;
        }

        try {
            const isLoggedIn = await geminiWindow.webContents.executeJavaScript(`
                (() => {
                    return !!document.querySelector('div[contenteditable="true"]');
                })()
            `);

            if (isLoggedIn) {
                log('[Gemini] Login detectado! Continuando...');
                // Oculta a janela novamente após login
                if (geminiWindow && !geminiWindow.isDestroyed()) {
                    geminiWindow.hide();
                }
                return true;
            } else {
                log('[Gemini] Aguardando login...');
            }
        } catch (e) {
            log(`[Gemini] Erro ao verificar login: ${e.message}`);
        }
    }

    return false; // Timeout
}

/**
 * Processa a fila de humanizações sequencialmente.
 */
async function processQueue() {
    if (isProcessingQueue || humanizeQueue.length === 0) return;
    isProcessingQueue = true;

    while (humanizeQueue.length > 0) {
        const { text, prompt, resolve, reject } = humanizeQueue.shift();

        let success = false;
        let loginAttempted = false;

        for (let attempt = 1; attempt <= 5 && !success; attempt++) {
            try {
                log(`[Gemini] Processando chunk (tentativa ${attempt})...`);
                const result = await runGeminiAutomation(text, prompt);
                resolve(result);
                success = true;
            } catch (error) {
                log(`[Gemini] Tentativa ${attempt} falhou: ${error.message}`);

                const isLoginError = error.message.includes('ERROR_LOGIN');

                if (isLoginError && !loginAttempted) {
                    // Abre a janela automaticamente e espera o login
                    loginAttempted = true;
                    const loggedIn = await waitForLogin();
                    if (!loggedIn) {
                        reject(new Error('Timeout aguardando login no Gemini (5 minutos).'));
                        success = true;
                    }
                    // loop continua e tenta novamente após o login
                } else if (isLoginError && loginAttempted) {
                    // Já tentou login — problema persistente
                    reject(new Error('Falha no login do Gemini após tentativa automática.'));
                    success = true;
                } else if (attempt < 5) {
                    // Erro genérico — recriar janela e tentar de novo
                    if (geminiWindow && !geminiWindow.isDestroyed()) {
                        geminiWindow.destroy();
                        geminiWindow = null;
                    }
                    log('[Gemini] Recriando janela e aguardando 3s...');
                    await new Promise(r => setTimeout(r, 3000));
                } else {
                    reject(error);
                }
            }
        }
    }

    isProcessingQueue = false;
}


// ===========================================================
// SERVIDOR HTTP LOCAL (porta 5001) — Bridge Flask → Electron
// ===========================================================
// O Python/Flask faz POST em http://localhost:5001/humanize
// com JSON { text, prompt } e recebe a resposta humanizada.

function startIpcServer() {
    const ipcServer = http.createServer((req, res) => {
        if (req.method === 'POST' && req.url === '/humanize') {
            let body = '';
            req.on('data', chunk => { body += chunk.toString(); });
            req.on('end', () => {
                let payload;
                try {
                    payload = JSON.parse(body);
                } catch (e) {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: 'JSON inválido' }));
                    return;
                }

                const { text, prompt } = payload;

                if (!text) {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: 'Campo "text" é obrigatório' }));
                    return;
                }

                // Enfileirar e aguardar resultado
                new Promise((resolve, reject) => {
                    humanizeQueue.push({ text, prompt: prompt || '', resolve, reject });
                    processQueue();
                })
                    .then(result => {
                        res.writeHead(200, { 'Content-Type': 'application/json' });
                        res.end(JSON.stringify({ success: true, text: result }));
                    })
                    .catch(err => {
                        log(`[IPC Server] Erro ao humanizar: ${err.message}`);
                        res.writeHead(500, { 'Content-Type': 'application/json' });
                        res.end(JSON.stringify({ error: err.message }));
                    });
            });

        } else if (req.method === 'GET' && req.url === '/open-gemini') {
            // Endpoint para abrir janela do Gemini (login)
            showGeminiWindow();
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ success: true }));

        } else if (req.method === 'GET' && req.url === '/health') {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'ok', geminiReady: !!(geminiWindow && !geminiWindow.isDestroyed()) }));

        } else {
            res.writeHead(404);
            res.end();
        }
    });

    ipcServer.listen(IPC_PORT, '127.0.0.1', () => {
        log(`[IPC Server] Servidor de bridge rodando na porta ${IPC_PORT}`);
    });

    ipcServer.on('error', err => {
        log(`[IPC Server] Erro: ${err.message}`);
    });
}

// ===========================================================
// FLASK SERVER
// ===========================================================

function startFlaskServer() {
    log('Iniciando servidor Python Flask...');

    // Tenta o .venv primeiro; se não encontrar, usa python do PATH
    const venvPython = path.join(__dirname, '.venv', 'Scripts', 'python.exe');
    const pythonExecutable = fs.existsSync(venvPython) ? venvPython : 'python';

    if (pythonExecutable === 'python') {
        log('AVISO: .venv não encontrado, usando python do PATH.');
    }

    const scriptPath = path.join(__dirname, 'app.py');

    flaskProcess = spawn(pythonExecutable, [scriptPath], {
        cwd: __dirname,
        env: {
            ...process.env,
            PYTHONIOENCODING: 'utf-8',
            PYTHONUNBUFFERED: '1',
            ELECTRON_IPC_PORT: String(IPC_PORT),
            SKIP_TTS: process.env.SKIP_TTS || '0'
        }
    });

    flaskProcess.stdout.on('data', (data) => {
        log(`Flask Output: ${data}`);
    });

    flaskProcess.stderr.on('data', (data) => {
        const msg = data.toString();
        // Filtrar logs de acesso HTTP do Werkzeug (GET/POST com status code)
        if (msg.includes('" 200 ') || msg.includes('" 304 ')) {
            // Silenciar completamente os logs de polling
            return;
        }
        if (msg.includes('Running on') || msg.includes('Press CTRL')) {
            log(`Flask Log: ${msg}`);
        } else {
            log(`Flask Log: ${msg}`);
        }
    });
}

// ===========================================================
// JANELA PRINCIPAL
// ===========================================================

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        title: 'faLei',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        },
        autoHideMenuBar: true,
        icon: path.join(__dirname, 'assets', 'icon.png')
    });

    const checkServer = () => {
        http.get(FLASK_URL, (res) => {
            if (res.statusCode === 200) {
                mainWindow.loadURL(FLASK_URL);
            } else {
                setTimeout(checkServer, 500);
            }
        }).on('error', () => {
            setTimeout(checkServer, 500);
        });
    };

    checkServer();

    mainWindow.on('closed', function () {
        mainWindow = null;
        killFlaskServer();
    });
}

// ===========================================================
// IPC HANDLERS (interface → main)
// ===========================================================

ipcMain.on('open-gemini', () => {
    showGeminiWindow();
});

ipcMain.handle('gemini-status', () => {
    return {
        ready: !!(geminiWindow && !geminiWindow.isDestroyed()),
        queueSize: humanizeQueue.length
    };
});

// ===========================================================
// UTILITÁRIOS
// ===========================================================

function killFlaskServer() {
    if (flaskProcess) {
        flaskProcess.kill();
        flaskProcess = null;
    }
}

// ===========================================================
// CICLO DE VIDA DO APP
// ===========================================================

app.on('ready', () => {
    startIpcServer();
    startFlaskServer();
    createWindow();
    // Pré-carregar a janela do Gemini em background já no boot
    createGeminiWindow();
});

app.on('window-all-closed', function () {
    killFlaskServer();
    if (process.platform !== 'darwin') app.quit();
});

app.on('activate', function () {
    if (mainWindow === null) createWindow();
});

app.on('will-quit', () => {
    killFlaskServer();
});
