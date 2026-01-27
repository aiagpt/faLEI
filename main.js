const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow;
let flaskProcess;

const FLASK_HOST = '127.0.0.1';
const FLASK_PORT = 5000;
const FLASK_URL = `http://${FLASK_HOST}:${FLASK_PORT}`;

const fs = require('fs');

const logStream = fs.createWriteStream(path.join(__dirname, 'app.log'), { flags: 'a' });

function log(msg) {
    const time = new Date().toISOString();
    const entry = `[${time}] ${msg}\n`;
    console.log(msg);
    logStream.write(entry);
}

function startFlaskServer() {
    log('Iniciando servidor Python Flask...');

    // Caminho para o Python no venv
    const pythonExecutable = path.join(__dirname, '.venv', 'Scripts', 'python.exe');
    const scriptPath = path.join(__dirname, 'app.py');

    if (!fs.existsSync(pythonExecutable)) {
        log(`ERRO: Python não encontrado em: ${pythonExecutable}`);
    }

    flaskProcess = spawn(pythonExecutable, [scriptPath], {
        cwd: __dirname,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    });

    flaskProcess.stdout.on('data', (data) => {
        log(`Flask Output: ${data}`);
    });

    flaskProcess.stderr.on('data', (data) => {
        const msg = data.toString();
        // Flask logs access requests to stderr. If it contains " 200 " or " 304 ", it's just info.
        if (msg.includes('" 200 ') || msg.includes('" 304 ') || msg.includes('Running on')) {
            log(`Flask Access: ${msg}`);
        } else {
            log(`Flask Log: ${msg}`);
        }
    });
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        title: "faLei",
        webPreferences: {
            nodeIntegration: false
        },
        autoHideMenuBar: true,
        icon: path.join(__dirname, 'assets', 'icon.png') // Opcional se tiver ícone
    });

    // Tentar conectar ao Flask até ele estar pronto
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

function killFlaskServer() {
    if (flaskProcess) {
        flaskProcess.kill();
        flaskProcess = null;
    }
}

app.on('ready', () => {
    startFlaskServer();
    createWindow();
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
