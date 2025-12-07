@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
python main.py "assets\Mursa - CAR+Corregos+ReservaLegal_avr.kml" --nome "Mursa_SICAR" -v
echo.
echo Verificando arquivos gerados...
dir output\Mursa_SICAR\shapefiles\
echo.
echo ZIP para upload:
dir output\Mursa_SICAR\*.zip
pause
