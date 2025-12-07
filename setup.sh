#!/bin/bash
echo "========================================"
echo "AUTO CAR Generator - Setup"
echo "========================================"
echo

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "ERRO: Python3 não encontrado. Instale Python 3.10+ primeiro."
    exit 1
fi

echo "Criando ambiente virtual..."
python3 -m venv venv

echo "Ativando ambiente virtual..."
source venv/bin/activate

echo "Instalando dependências..."
pip install --upgrade pip
pip install geopandas fiona shapely pyproj numpy pandas python-dotenv lxml pytest

echo
echo "========================================"
echo "Setup concluído!"
echo "========================================"
echo
echo "Para usar:"
echo "  1. Ative o ambiente: source venv/bin/activate"
echo "  2. Execute: python main.py 'assets/Mursa - CAR.kml' --nome 'Mursa'"
echo
