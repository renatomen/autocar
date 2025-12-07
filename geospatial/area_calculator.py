"""
Cálculo de áreas em diferentes unidades para SICAR.
"""
import geopandas as gpd
from shapely.geometry import Polygon
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DEFAULT_CRS, UTM_CRS_SP

# Módulo fiscal médio de São Paulo (varia por município)
# Fonte: INCRA - Tabela de Módulos Fiscais por Município
MODULO_FISCAL_SP_MEDIO_HA = 16.0


def calculate_area_m2(polygon: Polygon, source_crs: str = None) -> float:
    """
    Calcula área de um polígono em metros quadrados.

    Args:
        polygon: Polígono Shapely
        source_crs: CRS de origem (default: WGS84)

    Returns:
        Área em metros quadrados
    """
    if source_crs is None:
        source_crs = DEFAULT_CRS

    gdf = gpd.GeoDataFrame({'geometry': [polygon]}, crs=source_crs)
    gdf_utm = gdf.to_crs(UTM_CRS_SP)

    return gdf_utm.geometry.iloc[0].area


def calculate_area_hectares(polygon: Polygon, source_crs: str = None) -> float:
    """
    Calcula área de um polígono em hectares.

    Args:
        polygon: Polígono Shapely
        source_crs: CRS de origem (default: WGS84)

    Returns:
        Área em hectares
    """
    area_m2 = calculate_area_m2(polygon, source_crs)
    return area_m2 / 10000.0


def calculate_modulos_fiscais(
    area_ha: float,
    modulo_fiscal_ha: float = None
) -> float:
    """
    Calcula o número de módulos fiscais de uma propriedade.

    Args:
        area_ha: Área em hectares
        modulo_fiscal_ha: Tamanho do módulo fiscal em hectares
                         (default: média de SP)

    Returns:
        Número de módulos fiscais
    """
    if modulo_fiscal_ha is None:
        modulo_fiscal_ha = MODULO_FISCAL_SP_MEDIO_HA

    return area_ha / modulo_fiscal_ha


def get_area_summary(polygon: Polygon) -> dict:
    """
    Retorna resumo completo de áreas de um polígono.

    Args:
        polygon: Polígono Shapely

    Returns:
        Dict com área em diferentes unidades
    """
    area_m2 = calculate_area_m2(polygon)
    area_ha = area_m2 / 10000.0
    modulos = calculate_modulos_fiscais(area_ha)

    return {
        'area_m2': round(area_m2, 2),
        'area_ha': round(area_ha, 4),
        'area_km2': round(area_m2 / 1_000_000, 4),
        'modulos_fiscais': round(modulos, 2),
        'modulo_fiscal_referencia_ha': MODULO_FISCAL_SP_MEDIO_HA
    }
