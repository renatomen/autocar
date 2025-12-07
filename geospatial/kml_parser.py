"""
Parser de KML de entrada com validação inicial.
"""
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from shapely.validation import make_valid
import logging
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DEFAULT_CRS, MIN_COORDINATE_DECIMALS

logger = logging.getLogger(__name__)


def parse_kml(kml_file_path: str) -> tuple:
    """
    Converte KML de entrada para GeoDataFrame.

    Args:
        kml_file_path: Caminho para o arquivo KML

    Returns:
        Tuple com (GeoDataFrame completo, geometria do perímetro)

    Raises:
        ValueError: Se o KML não contiver polígonos válidos
        FileNotFoundError: Se o arquivo não existir
    """
    kml_path = Path(kml_file_path)

    if not kml_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {kml_file_path}")

    logger.info(f"Lendo KML: {kml_file_path}")

    # Ler KML
    try:
        gdf = gpd.read_file(kml_file_path, driver='KML')
    except Exception as e:
        raise ValueError(f"Erro ao ler KML: {e}")

    if gdf.empty:
        raise ValueError("KML não contém geometrias")

    # Garantir CRS WGS84
    if gdf.crs is None:
        logger.warning("KML sem CRS definido, assumindo WGS84")
        gdf = gdf.set_crs(DEFAULT_CRS)
    elif str(gdf.crs) != DEFAULT_CRS:
        logger.info(f"Convertendo de {gdf.crs} para {DEFAULT_CRS}")
        gdf = gdf.to_crs(DEFAULT_CRS)

    # Extrair perímetro (primeiro polígono)
    perimeter = _extract_perimeter(gdf)

    if perimeter is None:
        raise ValueError("KML não contém polígonos. Verifique se o perímetro está fechado.")

    # Validar geometria
    perimeter = _validate_and_fix_geometry(perimeter)

    # Log de informações
    logger.info(f"Perímetro extraído com {len(perimeter.exterior.coords)} vértices")

    return gdf, perimeter


def _extract_perimeter(gdf: gpd.GeoDataFrame) -> Polygon:
    """Extrai o primeiro polígono do GeoDataFrame."""
    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        if isinstance(geom, Polygon):
            return geom
        if isinstance(geom, MultiPolygon):
            # Retorna o maior polígono
            return max(geom.geoms, key=lambda p: p.area)

    return None


def _validate_and_fix_geometry(perimeter: Polygon) -> Polygon:
    """Valida e corrige a geometria se necessário."""
    if not perimeter.is_valid:
        logger.warning("Polígono inválido detectado, aplicando correção automática")
        perimeter = make_valid(perimeter)
        if isinstance(perimeter, MultiPolygon):
            perimeter = max(perimeter.geoms, key=lambda p: p.area)

    return perimeter


def validate_coordinate_precision(geometry: Polygon, min_decimals: int = None) -> list:
    """
    Valida se coordenadas têm precisão suficiente para SICAR.

    Args:
        geometry: Polígono a validar
        min_decimals: Número mínimo de casas decimais (default: MIN_COORDINATE_DECIMALS)

    Returns:
        Lista de warnings sobre coordenadas com precisão insuficiente
    """
    if min_decimals is None:
        min_decimals = MIN_COORDINATE_DECIMALS

    warnings = []
    coords = list(geometry.exterior.coords)

    for i, (lon, lat) in enumerate(coords):
        lon_decimals = _count_decimals(lon)
        lat_decimals = _count_decimals(lat)

        if lon_decimals < min_decimals or lat_decimals < min_decimals:
            warnings.append(
                f"Vértice {i}: precisão insuficiente ({lon}, {lat}). "
                f"SICAR recomenda {min_decimals} casas decimais."
            )

    return warnings


def _count_decimals(value: float) -> int:
    """Conta o número de casas decimais de um float."""
    str_value = str(value)
    if '.' not in str_value:
        return 0
    return len(str_value.split('.')[-1])
