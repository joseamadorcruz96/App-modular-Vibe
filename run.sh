#!/usr/bin/env bash
# CoffeePOS - Script de inicio automático para Linux y macOS

set -e

echo "=============================================================================="
echo "                     INICIANDO SISTEMA COFFEEPOS"
echo "=============================================================================="
echo ""

# 1. Verificar si existe el entorno virtual
if [ -f ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
else
    echo "[INFO] Configurando entorno virtual (.venv)..."
    if command -v python3 &>/dev/null; then
        python3 -m venv .venv
    elif command -v python &>/dev/null; then
        python -m venv .venv
    else
        echo "[ERROR] No se encontro Python 3 instalado en el sistema."
        echo "Por favor instale Python 3.10 o superior (ej. sudo apt install python3 python3-venv)."
        exit 1
    fi
    PYTHON_BIN=".venv/bin/python"
    echo "[INFO] Instalando dependencias en el entorno virtual..."
    "$PYTHON_BIN" -m pip install --upgrade pip
    "$PYTHON_BIN" -m pip install -r requirements.txt
fi

echo "[INFO] Verificando base de datos SQLite en data/cafeteria.db..."
"$PYTHON_BIN" -c "from app.database import init_db; init_db()"

echo "[INFO] Servidor listo. Abriendo navegador en http://127.0.0.1:8000..."
if command -v xdg-open &>/dev/null; then
    xdg-open "http://127.0.0.1:8000" &>/dev/null &
elif command -v open &>/dev/null; then
    open "http://127.0.0.1:8000" &>/dev/null &
fi

echo "[INFO] Iniciando Uvicorn en http://127.0.0.1:8000 (Presione Ctrl+C para detener)..."
"$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
