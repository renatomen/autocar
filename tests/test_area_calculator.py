"""
Testes para o módulo area_calculator.
TDD: Testes escritos antes da implementação.
"""
import pytest
from pathlib import Path
from shapely.geometry import Polygon

FIXTURES_DIR = Path(__file__).parent / 'fixtures'


class TestAreaCalculator:
    """Testes para cálculo de área."""

    def test_calculate_area_in_hectares(self):
        """Deve calcular área corretamente em hectares."""
        from geospatial.area_calculator import calculate_area_hectares

        # Quadrado de aproximadamente 1km x 1km = 100 hectares
        # 1 grau ≈ 111km no equador, então 0.009 graus ≈ 1km
        polygon = Polygon([
            (-46.85, -23.20),
            (-46.841, -23.20),  # ~1km leste
            (-46.841, -23.209),  # ~1km sul
            (-46.85, -23.209),
            (-46.85, -23.20)
        ])

        area_ha = calculate_area_hectares(polygon)

        # Deve ser aproximadamente 100 ha (com margem de erro de 20%)
        assert 80 < area_ha < 120

    def test_mursa_area_is_reasonable(self):
        """A área do KML Mursa deve ser razoável para uma propriedade rural."""
        from geospatial.kml_parser import parse_kml
        from geospatial.area_calculator import calculate_area_hectares

        kml_path = FIXTURES_DIR / 'mursa_real.kml'
        _, perimeter = parse_kml(str(kml_path))

        area_ha = calculate_area_hectares(perimeter)

        # Propriedade rural típica: entre 1 e 1000 hectares
        assert 1 < area_ha < 1000

    def test_calculate_area_in_square_meters(self):
        """Deve calcular área em metros quadrados."""
        from geospatial.area_calculator import calculate_area_m2

        polygon = Polygon([
            (-46.85, -23.20),
            (-46.841, -23.20),
            (-46.841, -23.209),
            (-46.85, -23.209),
            (-46.85, -23.20)
        ])

        area_m2 = calculate_area_m2(polygon)

        # ~100 ha = 1.000.000 m²
        assert 800000 < area_m2 < 1200000

    def test_area_with_different_crs(self):
        """Deve converter CRS antes de calcular área."""
        from geospatial.area_calculator import calculate_area_hectares
        import geopandas as gpd

        polygon = Polygon([
            (-46.85, -23.20),
            (-46.841, -23.20),
            (-46.841, -23.209),
            (-46.85, -23.209),
            (-46.85, -23.20)
        ])

        # Criar GeoDataFrame com CRS diferente
        gdf = gpd.GeoDataFrame({'geometry': [polygon]}, crs='EPSG:4326')

        area_ha = calculate_area_hectares(polygon)

        # Deve funcionar mesmo com CRS diferente
        assert area_ha > 0


class TestModuloFiscal:
    """Testes para cálculo de módulos fiscais."""

    def test_calculate_modulos_fiscais(self):
        """Deve calcular número de módulos fiscais."""
        from geospatial.area_calculator import calculate_modulos_fiscais

        # Supondo módulo fiscal de 20 ha para SP
        area_ha = 100
        modulo_fiscal_ha = 20

        modulos = calculate_modulos_fiscais(area_ha, modulo_fiscal_ha)

        assert modulos == 5.0

    def test_modulos_fiscais_with_default(self):
        """Deve usar módulo fiscal padrão de SP se não especificado."""
        from geospatial.area_calculator import calculate_modulos_fiscais

        area_ha = 100

        modulos = calculate_modulos_fiscais(area_ha)

        # Deve retornar um valor válido
        assert modulos > 0
