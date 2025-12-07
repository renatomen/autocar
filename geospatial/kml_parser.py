"""
Parser de KML de entrada com validação inicial.
Suporta extração de perímetro, córregos, nascentes e reserva legal.
"""
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, LineString, Point
from shapely.validation import make_valid
import logging
from pathlib import Path
from typing import Optional, Dict

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


def parse_kml_completo(kml_file_path: str) -> Dict:
    """
    Extrai todos os elementos de um KML completo.

    Identifica automaticamente:
    - Perímetro (polígono maior ou com nome específico)
    - Córregos (LineStrings)
    - Nascentes (Points)
    - Reserva Legal (polígono com nome 'Reserva_Legal')
    - Vegetação Remanescente/Nativa (polígono com nome 'vegetacao*')

    Args:
        kml_file_path: Caminho para o arquivo KML

    Returns:
        Dict com:
            - 'perimetro': Polygon
            - 'corregos': GeoDataFrame com LineStrings
            - 'nascentes': GeoDataFrame com Points
            - 'reserva_legal': Polygon ou None
            - 'vegetacao_nativa': Polygon ou None
    """
    kml_path = Path(kml_file_path)

    if not kml_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {kml_file_path}")

    logger.info(f"Lendo KML completo: {kml_file_path}")

    # Ler KML
    try:
        gdf = gpd.read_file(kml_file_path, driver='KML')
    except Exception as e:
        raise ValueError(f"Erro ao ler KML: {e}")

    if gdf.empty:
        raise ValueError("KML não contém geometrias")

    # Garantir CRS WGS84
    if gdf.crs is None:
        gdf = gdf.set_crs(DEFAULT_CRS)
    elif str(gdf.crs) != DEFAULT_CRS:
        gdf = gdf.to_crs(DEFAULT_CRS)

    # Classificar elementos
    perimetro = None
    reserva_legal = None
    vegetacao_nativa = None
    corregos = []
    nascentes = []

    for idx, row in gdf.iterrows():
        geom = row.geometry
        nome = str(row.get('Name', '')).lower() if 'Name' in gdf.columns else ''

        if geom is None:
            continue

        # Identificar por tipo de geometria e nome
        if isinstance(geom, (Polygon, MultiPolygon)):
            if 'reserva' in nome or 'legal' in nome:
                logger.info(f"Reserva Legal identificada: {row.get('Name', 'sem nome')}")
                if isinstance(geom, MultiPolygon):
                    geom = max(geom.geoms, key=lambda p: p.area)
                reserva_legal = _validate_and_fix_geometry(geom)
            elif 'vegetacao' in nome or 'remanescente' in nome or 'nativa' in nome:
                logger.info(f"Vegetação Nativa/Remanescente identificada: {row.get('Name', 'sem nome')}")
                if isinstance(geom, MultiPolygon):
                    geom = max(geom.geoms, key=lambda p: p.area)
                vegetacao_nativa = _validate_and_fix_geometry(geom)
            elif 'perimetro' in nome or 'gleba' in nome or 'imovel' in nome or perimetro is None:
                # Primeiro polígono não-RL e não-vegetação é o perímetro
                if isinstance(geom, MultiPolygon):
                    geom = max(geom.geoms, key=lambda p: p.area)
                if perimetro is None or geom.area > perimetro.area:
                    logger.info(f"Perímetro identificado: {row.get('Name', 'sem nome')}")
                    perimetro = _validate_and_fix_geometry(geom)

        elif isinstance(geom, LineString):
            logger.info(f"Córrego identificado: {row.get('Name', 'sem nome')}")
            # Estimar largura pelo nome se possível
            largura = _extrair_largura_do_nome(row.get('Name', ''))
            corregos.append({
                'geometry': geom,
                'nome': row.get('Name', f'Corrego_{len(corregos)+1}'),
                'largura_m': largura,
                'source': 'KML_LOCAL'
            })

        elif isinstance(geom, Point):
            nome_upper = str(row.get('Name', '')).upper()
            if 'NASCENTE' in nome_upper or 'NASC' in nome_upper:
                logger.info(f"Nascente identificada: {row.get('Name', 'sem nome')}")
                nascentes.append({
                    'geometry': geom,
                    'nome': row.get('Name', f'Nascente_{len(nascentes)+1}'),
                    'tipo': 'NASCENTE_MAPEADA',
                    'source': 'KML_LOCAL'
                })

    if perimetro is None:
        raise ValueError("KML não contém polígono de perímetro válido")

    # Criar GeoDataFrames
    corregos_gdf = gpd.GeoDataFrame(corregos, crs=DEFAULT_CRS) if corregos else gpd.GeoDataFrame(
        {'geometry': [], 'nome': [], 'largura_m': [], 'source': []}, crs=DEFAULT_CRS
    )

    nascentes_gdf = gpd.GeoDataFrame(nascentes, crs=DEFAULT_CRS) if nascentes else gpd.GeoDataFrame(
        {'geometry': [], 'nome': [], 'tipo': [], 'source': []}, crs=DEFAULT_CRS
    )

    logger.info(f"Elementos extraídos: perímetro=1, córregos={len(corregos)}, nascentes={len(nascentes)}, reserva_legal={'sim' if reserva_legal else 'não'}, vegetacao_nativa={'sim' if vegetacao_nativa else 'não'}")

    return {
        'perimetro': perimetro,
        'corregos': corregos_gdf,
        'nascentes': nascentes_gdf,
        'reserva_legal': reserva_legal,
        'vegetacao_nativa': vegetacao_nativa
    }


def _extrair_largura_do_nome(nome: str) -> float:
    """
    Tenta extrair largura do córrego a partir do nome.
    Ex: 'Córrego Norte - 3m' -> 3.0
    """
    import re

    if not nome:
        return 5.0  # Default para córregos pequenos

    # Procurar padrão de metros no nome
    match = re.search(r'(\d+(?:\.\d+)?)\s*m(?:etros?)?', nome, re.IGNORECASE)
    if match:
        return float(match.group(1))

    return 5.0  # Default
