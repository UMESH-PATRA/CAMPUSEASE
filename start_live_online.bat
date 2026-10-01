@echo off
title CampusEase - Live Online Launcher
cd /d "%~dp0"

echo ========================================================
echo Starting CampusEase Backend Server + Live Public Tunnel
echo ========================================================

:: Check if server is running on port 3000
netstat -ano | findstr :3000 >nul
if %errorlevel% neq 0 (
    echo Starting backend server on port 3000...
    start /min "" py server.py
    timeout /t 2 /nobreak >nul
)

:: Start Cloudflare public tunnel
echo Exposing website to public internet with Cloudflare...
start .\cloudflared.exe tunnel --url http://localhost:3000

echo.
echo Tunnel started! Check the Cloudflare window for your live public HTTPS link.
pause
