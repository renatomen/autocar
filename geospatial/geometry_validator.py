"""
Validação e correção de geometrias para SICAR.
"""
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, LineString, Point
from shapely.validation import make_valid
import logging
from pathlib import Path
from typing import Tuple, List

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DEFAULT_CRS, UTM_CRS_SP, MIN_PROPERTY_AREA_M2

logger = logging.getLogger(__name__)


class GeometryValidator:
    """Validador de geometrias para SICAR."""

    def __init__(self, max_vertices: int = 1000, min_area_m2: float = None):
        """
        Args:
            max_vertices: Número máximo de vértices antes de simplificar
            min_area_m2: Área mínima em m² (default: MIN_PROPERTY_AREA_M2)
        """
        self.max_vertices = max_vertices
        self.min_area_m2 = min_area_m2 if min_area_m2 is not None else MIN_PROPERTY_AREA_M2

    def validate(self, geometry) -> Tuple[Polygon, List[str]]:
        """
        Valida e corrige uma geometria.

        Args:
            geometry: Geometria a validar (deve ser Polygon)

        Returns:
            Tuple com (geometria corrigida, lista de warnings/erros)

        Raises:
            TypeError: Se a geometria não for um Polygon
        """
        errors = []

        # Verificar tipo
        if not isinstance(geometry, (Polygon, MultiPolygon)):
            raise TypeError(
                f"Esperado Polígono, recebido {type(geometry).__name__}. "
                "O perímetro deve ser um polígono fechado."
            )

        # Se for MultiPolygon, pegar o maior
        if isinstance(geometry, MultiPolygon):
            geometry = max(geometry.geoms, key=lambda p: p.area)
            errors.append("MultiPolygon convertido para o maior polígono")

        # 1. Corrigir auto-interseção
        if not geometry.is_valid:
            geometry = make_valid(geometry)
            errors.append("Auto-interseção detectada e corrigida")

            # make_valid pode retornar MultiPolygon
            if isinstance(geometry, MultiPolygon):
                geometry = max(geometry.geoms, key=lambda p: p.area)

        # 2. Verificar área mínima
        area_m2 = self._calculate_area_m2(geometry)
        if area_m2 < self.min_area_m2:
            errors.append(
                f"Área ({area_m2:.0f} m²) abaixo do mínimo legal ({self.min_area_m2:.0f} m²)"
            )

        # 3. Simplificar se muito complexo
        n_vertices = len(geometry.exterior.coords)
        if n_vertices > self.max_vertices:
            geometry = self._simplify_polygon(geometry)
            new_vertices = len(geometry.exterior.coords)
            errors.append(
                f"Polígono simplificado de {n_vertices} para {new_vertices} vértices"
            )

        # 4. Garantir que ainda é válido após simplificação
        if not geometry.is_valid:
            geometry = make_valid(geometry)
            if isinstance(geometry, MultiPolygon):
                geometry = max(geometry.geoms, key=lambda p: p.area)

        return geometry, errors

    def _calculate_area_m2(self, geometry: Polygon) -> float:
        """Calcula área em metros quadrados usando projeção UTM."""
        gdf = gpd.GeoDataFrame({'geometry': [geometry]}, crs=DEFAULT_CRS)
        gdf_utm = gdf.to_crs(UTM_CRS_SP)
        return gdf_utm.geometry.iloc[0].area

    def _simplify_polygon(self, geometry: Polygon) -> Polygon:
        """Simplifica polígono mantendo topologia."""
        # Começar com tolerância pequena e aumentar até atingir max_vertices
        tolerance = 0.00001  # ~1m em graus

        while len(geometry.exterior.coords) > self.max_vertices and tolerance < 0.001:
            simplified = geometry.simplify(tolerance, preserve_topology=True)
            if isinstance(simplified, Polygon):
                geometry = simplified
            tolerance *= 2

        return geometry


def validate_polygon_for_sicar(geometry) -> Tuple[Polygon, List[str]]:
    """
    Função de conveniência para validar geometria para SICAR.

    Args:
        geometry: Geometria a validar

    Returns:
        Tuple com (geometria corrigida, lista de warnings)
    """
    validator = GeometryValidator()
    return validator.validate(geometry)
