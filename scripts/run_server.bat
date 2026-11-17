@echo off
cd /d "%~dp0\.."
title Lexyta LMS Multi-User Telegram Server
echo =======================================================
echo   Lexyta LMS Multi-User Autonomous Server
echo =======================================================
echo.
python run_server.py
pause
