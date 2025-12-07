@echo off
cd /d "%~dp0"
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install --upgrade pip
    pip install geopandas fiona shapely pyproj numpy pandas python-dotenv lxml pytest requests
) else (
    call venv\Scripts\activate.bat
)
echo.
echo Running pipeline with OSM hydrology...
python main.py "assets\Mursa - CAR.kml" --nome "Mursa_Test" -v
echo.
echo Checking output...
dir output\Mursa_Test\shapefiles\
pause
