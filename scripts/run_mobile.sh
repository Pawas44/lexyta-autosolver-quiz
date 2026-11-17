#!/data/data/com.termux/files/usr/bin/bash

# ==========================================================
# LMS Lexyta Auto Quiz Solver & Assignment Notifier
# Termux Mobile Runner Script
# ==========================================================

DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

echo "=================================================="
echo " Starting LMS Lexyta Mobile Bot for Pawas"
echo " Target Number: 9315135782"
echo "=================================================="

# Keep Termux awake in background so Android does not kill it
if command -v termux-wake-lock &> /dev/null; then
    termux-wake-lock
    echo "[+] Termux wake lock acquired (Running in background)."
fi

# Check Python installation
if ! command -v python &> /dev/null; then
    echo "[!] Python not found. Installing..."
    pkg update -y && pkg install python -y
fi

# Install requirements
pip install -r requirements.txt

# Run main bot loop
echo "[+] Starting bot loop..."
python run.py
