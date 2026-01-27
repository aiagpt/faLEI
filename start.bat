@echo off
title faLei - Desktop
color 0f

if not exist "node_modules" (
    echo [INFO] Instalando dependencias...
    call npm install
)

echo [INFO] Iniciando Aplicativo...
call npm start
if %errorlevel% neq 0 (
    echo [ERRO] Ocorreu um erro ao rodar o Electron.
    exit /b %errorlevel%
)

echo.
echo [INFO] Script finalizado.
