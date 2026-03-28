#!/bin/bash
set -euo pipefail

echo "[*] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "[*] Installing pinned dependencies..."
pip install -r requirements.txt

echo "[*] Setting up pre-commit hooks..."
pip install pre-commit
pre-commit install

if [ ! -f .env ]; then
    cp .env.example .env
    echo "[!] Created .env from .env.example — edit it with your values."
else
    echo "[*] .env already exists, skipping copy."
fi

echo "[*] Setup complete. Edit .env, then run: docker compose up -d --build"
