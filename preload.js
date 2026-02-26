const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // Abre a janela do Gemini para o usuário fazer login
    openGemini: () => ipcRenderer.send('open-gemini'),

    // Retorna o status da janela do Gemini
    getGeminiStatus: () => ipcRenderer.invoke('gemini-status'),
});
