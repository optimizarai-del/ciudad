@echo off
echo.
echo  CIUDAD. — Reset datos demo
echo  ===========================
echo.
echo  IMPORTANTE: cierra el backend antes de continuar.
echo  Presiona cualquier tecla para continuar o Ctrl+C para cancelar.
pause > nul

cd /d "%~dp0backend"
python reset_seed.py

echo.
echo  Listo. Ahora podes iniciar el backend con start-backend.bat
pause
