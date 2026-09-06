@echo off
setlocal EnableDelayedExpansion
title CoffeePOS - Sistema Local de Punto de Venta y Gestion
color 0E

echo ==============================================================================
echo                      INICIANDO SISTEMA COFFEEPOS
echo ==============================================================================
echo.

:: 1. Si ya existe el entorno virtual con Python funcional, usarlo directamente
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    goto :START_APP
)

:: 2. Buscar ejecutable de Python en el sistema
set "PYTHON_EXE="

:: Intentar con python
python --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_EXE=python"
    goto :CREATE_VENV
)

:: Intentar con py launcher de Windows
py --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_EXE=py"
    goto :CREATE_VENV
)

:: Intentar rutas directas estandar en Windows
if exist "C:\Python314\python.exe" (
    set "PYTHON_EXE=C:\Python314\python.exe"
    goto :CREATE_VENV
)
if exist "C:\Python313\python.exe" (
    set "PYTHON_EXE=C:\Python313\python.exe"
    goto :CREATE_VENV
)
if exist "C:\Python312\python.exe" (
    set "PYTHON_EXE=C:\Python312\python.exe"
    goto :CREATE_VENV
)
if exist "C:\Python311\python.exe" (
    set "PYTHON_EXE=C:\Python311\python.exe"
    goto :CREATE_VENV
)
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    goto :CREATE_VENV
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :CREATE_VENV
)

if not defined PYTHON_EXE (
    echo [ERROR] No se pudo encontrar una instalacion de Python en el sistema.
    echo Por favor descargue e instale Python 3.11 o superior desde https://www.python.org/
    echo Asegurese de marcar la casilla "Add python.exe to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

:CREATE_VENV
echo [INFO] Configurando entorno virtual (.venv) usando: !PYTHON_EXE!...
"!PYTHON_EXE!" -m venv .venv
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Falla al crear el entorno virtual.
    pause
    exit /b 1
)

echo [INFO] Instalando dependencias en el entorno virtual...
.\.venv\Scripts\pip.exe install -r requirements.txt
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Falla al instalar dependencias.
    pause
    exit /b 1
)

set "PYTHON_EXE=.venv\Scripts\python.exe"

:START_APP
echo [INFO] Verificando base de datos SQLite en data/cafeteria.db...
.\.venv\Scripts\python.exe -c "from app.database import init_db; init_db()"

echo [INFO] Servidor listo. Abriendo navegador en http://127.0.0.1:8000...
start "" http://127.0.0.1:8000

echo [INFO] Iniciando Uvicorn en http://127.0.0.1:8000 (Presione Ctrl+C para detener)...
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [AVISO] El servidor se ha detenido.
    pause
)
