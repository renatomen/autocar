@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
python main.py "assets\Mursa - CAR+Corregos+ReservaLegal_avr.kml" --nome "Mursa_AVR" -v
echo.
echo Verificando arquivos gerados...
dir output\Mursa_AVR\shapefiles\
pause
