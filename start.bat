@echo off
title faLei - Desktop
color 0f

if not exist "node_modules\electron\dist\electron.exe" (
    echo [INFO] Instalando dependencias...
    call npm install --ignore-scripts
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao instalar dependencias.
        pause
        exit /b 1
    )
)

:: Modo teste: start.bat teste -> pula TTS, so testa o Gemini
if "%1"=="teste" (
    echo [MODO TESTE] TTS desativado - testando apenas Gemini...
    set SKIP_TTS=1
) else (
    set SKIP_TTS=0
)

echo [INFO] Iniciando Aplicativo...
call npm start
if %errorlevel% neq 0 (
    echo [ERRO] Ocorreu um erro ao rodar o Electron.
    pause
    exit /b %errorlevel%
)

echo.
echo [INFO] Script finalizado.
