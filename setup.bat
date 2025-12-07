@echo off
echo ========================================
echo AUTO CAR Generator - Setup
echo ========================================
echo.

REM Verificar se Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado. Instale Python 3.10+ primeiro.
    pause
    exit /b 1
)

echo Criando ambiente virtual...
python -m venv venv

echo Ativando ambiente virtual...
call venv\Scripts\activate.bat

echo Instalando dependencias...
pip install --upgrade pip
pip install geopandas fiona shapely pyproj numpy pandas python-dotenv lxml pytest

echo.
echo ========================================
echo Setup concluido!
echo ========================================
echo.
echo Para usar:
echo   1. Ative o ambiente: venv\Scripts\activate
echo   2. Execute: python main.py "assets\Mursa - CAR.kml" --nome "Mursa"
echo.
pause
