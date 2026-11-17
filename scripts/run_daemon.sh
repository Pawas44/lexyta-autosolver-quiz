#!/usr/bin/env bash
# Runs LMS Lexyta bot in background with nohup

DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

LOG_FILE="logs/bot.log"
mkdir -p logs

echo "Starting LMS Lexyta Bot in background..."
nohup python3 run.py > /dev/null 2>&1 &
PID=$!
echo "Bot started with PID: $PID"
echo "Logs: tail -f $LOG_FILE"
