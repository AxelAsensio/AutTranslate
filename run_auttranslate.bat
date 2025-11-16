@echo off
rem Lanzador simple para AutTranslate
set APPDIR=%~dp0

rem Si existe un entorno virtual local, úsalo
if exist "%APPDIR%venv\Scripts\python.exe" (
    "%APPDIR%venv\Scripts\python.exe" "%APPDIR%main.py"
    goto :EOF
)

rem Intentar usar el lanzador py o python en PATH
py -3 "%APPDIR%main.py" 2>nul && goto :EOF
python "%APPDIR%main.py" 2>nul && goto :EOF

echo No se encontró una instalación de Python 3.
echo Por favor instala Python 3 y asegúrate de que el lanzador 'py' o el comando 'python' estén en el PATH.
pause
