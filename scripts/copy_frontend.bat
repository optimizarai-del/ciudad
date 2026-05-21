@echo off
REM Rebuildea el frontend y copia el dist a backend\app\static
REM para que el ZIP de "Versiones local" lo incluya y que el Dockerfile
REM de produccion lo empaquete en el container sin necesidad de Node.
REM
REM Uso:  scripts\copy_frontend.bat

setlocal
cd /d "%~dp0\.."

echo ==^> Buildeando frontend con Vite...
cd frontend
call npm run build
if errorlevel 1 (
    echo Error en npm run build
    exit /b 1
)
cd ..

echo ==^> Copiando frontend\dist a backend\app\static
if exist backend\app\static rmdir /s /q backend\app\static
mkdir backend\app\static
xcopy /e /q /y frontend\dist\* backend\app\static\ >nul

echo.
echo Listo. Recorda commitear backend\app\static\ para que el deploy lo levante.
dir backend\app\static
