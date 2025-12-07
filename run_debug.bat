@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
python main.py "assets\Mursa - CAR.kml" --nome "Mursa_Debug" -v
pause
