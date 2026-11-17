#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

echo "Starting Lexyta Multi-User Telegram Server..."
python3 run_server.py
