@echo off
title CIUDAD. — Frontend (Vite)
cd /d "%~dp0frontend"
echo.
echo  ============================================
echo    CIUDAD. — Frontend
echo    http://localhost:5173
echo  ============================================
echo.
call npm install
call npm run dev
pause
