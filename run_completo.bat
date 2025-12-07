@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
python main.py "assets\Mursa - CAR+Corregos+ReservaLegal.kml" --nome "Mursa_Completo" -v
echo.
echo Verificando arquivos gerados...
dir output\Mursa_Completo\shapefiles\
pause
