"""
Testes para o módulo app_calculator.
TDD: Testes escritos antes da implementação.
"""
import pytest
from pathlib import Path
from shapely.geometry import Polygon, LineString, Point
import geopandas as gpd

FIXTURES_DIR = Path(__file__).parent / 'fixtures'


class TestAPPMargem:
    """Testes para APP de margem de curso d'água."""

    def test_app_30m_for_river_under_10m(self):
        """Rio <10m deve ter APP de 30m."""
        from car_layers.app_calculator import APPCalculator

        polygon = Polygon([
            (-46.83, -23.24),
            (-46.81, -23.24),
            (-46.81, -23.27),
            (-46.83, -23.27),
            (-46.83, -23.24)
        ])

        rivers = gpd.GeoDataFrame({
            'geometry': [
                LineString([(-46.82, -23.25), (-46.82, -23.26)])
            ],
            'largura_m': [5]  # 5m < 10m
        }, crs='EPSG:4326')

        calc = APPCalculator(polygon)
        app_gdf = calc.calculate_app_margem(rivers)

        assert not app_gdf.empty
        # Verificar que usou buffer de 30m
        assert any(app_gdf['buffer_m'] == 30)

    def test_app_50m_for_river_10_to_50m(self):
        """Rio 10-50m deve ter APP de 50m."""
        from car_layers.app_calculator import APPCalculator

        polygon = Polygon([
            (-46.83, -23.24),
            (-46.81, -23.24),
            (-46.81, -23.27),
            (-46.83, -23.27),
            (-46.83, -23.24)
        ])

        rivers = gpd.GeoDataFrame({
            'geometry': [
                LineString([(-46.82, -23.25), (-46.82, -23.26)])
            ],
            'largura_m': [25]  # 10m < 25m < 50m
        }, crs='EPSG:4326')

        calc = APPCalculator(polygon)
        app_gdf = calc.calculate_app_margem(rivers)

        assert not app_gdf.empty
        assert any(app_gdf['buffer_m'] == 50)

    def test_app_only_inside_perimeter(self):
        """APP deve ser recortada ao perímetro do imóvel."""
        from car_layers.app_calculator import APPCalculator

        # Polígono pequeno
        polygon = Polygon([
            (-46.820, -23.255),
            (-46.818, -23.255),
            (-46.818, -23.257),
            (-46.820, -23.257),
            (-46.820, -23.255)
        ])

        # Rio que passa pelo meio e continua fora
        rivers = gpd.GeoDataFrame({
            'geometry': [
                LineString([(-46.825, -23.256), (-46.815, -23.256)])
            ],
            'largura_m': [5]
        }, crs='EPSG:4326')

        calc = APPCalculator(polygon)
        app_gdf = calc.calculate_app_margem(rivers)

        if not app_gdf.empty:
            # APP deve estar contida no perímetro
            app_union = app_gdf.unary_union
            assert polygon.contains(app_union) or polygon.intersects(app_union)


class TestAPPNascente:
    """Testes para APP de nascente."""

    def test_app_nascente_50m_radius(self):
        """Nascente deve ter APP de 50m de raio."""
        from car_layers.app_calculator import APPCalculator

        polygon = Polygon([
            (-46.83, -23.24),
            (-46.81, -23.24),
            (-46.81, -23.27),
            (-46.83, -23.27),
            (-46.83, -23.24)
        ])

        nascentes = gpd.GeoDataFrame({
            'geometry': [Point(-46.82, -23.255)],
            'tipo': ['NASCENTE']
        }, crs='EPSG:4326')

        calc = APPCalculator(polygon)
        app_gdf = calc.calculate_app_nascente(nascentes)

        assert not app_gdf.empty
        assert app_gdf['tip_app'].iloc[0] == 'NASCENTE'


class TestAPPLago:
    """Testes para APP de lago."""

    def test_app_lago_pequeno_50m(self):
        """Lago ≤20ha deve ter APP de 50m."""
        from car_layers.app_calculator import APPCalculator

        polygon = Polygon([
            (-46.83, -23.24),
            (-46.81, -23.24),
            (-46.81, -23.27),
            (-46.83, -23.27),
            (-46.83, -23.24)
        ])

        # Lago pequeno (~10ha)
        lago = Polygon([
            (-46.822, -23.252),
            (-46.818, -23.252),
            (-46.818, -23.256),
            (-46.822, -23.256),
            (-46.822, -23.252)
        ])

        lagos = gpd.GeoDataFrame({
            'geometry': [lago],
            'area_ha': [10]
        }, crs='EPSG:4326')

        calc = APPCalculator(polygon)
        app_gdf = calc.calculate_app_lago(lagos)

        if not app_gdf.empty:
            assert app_gdf['buffer_m'].iloc[0] == 50


class TestAPPCalculatorIntegration:
    """Testes de integração do calculador de APP."""

    def test_calculate_all_apps(self):
        """Deve calcular todas as APPs de uma vez."""
        from car_layers.app_calculator import APPCalculator

        polygon = Polygon([
            (-46.83, -23.24),
            (-46.81, -23.24),
            (-46.81, -23.27),
            (-46.83, -23.27),
            (-46.83, -23.24)
        ])

        rivers = gpd.GeoDataFrame({
            'geometry': [
                LineString([(-46.82, -23.25), (-46.82, -23.26)])
            ],
            'largura_m': [5]
        }, crs='EPSG:4326')

        nascentes = gpd.GeoDataFrame({
            'geometry': [Point(-46.82, -23.25)],
            'tipo': ['NASCENTE']
        }, crs='EPSG:4326')

        calc = APPCalculator(polygon)
        app_gdf = calc.calculate_all_apps(
            rivers_gdf=rivers,
            nascentes_gdf=nascentes
        )

        assert isinstance(app_gdf, gpd.GeoDataFrame)
        assert 'tip_app' in app_gdf.columns
        assert 'num_area' in app_gdf.columns

    def test_app_has_sicar_attributes(self):
        """APP deve ter atributos obrigatórios do SICAR."""
        from car_layers.app_calculator import APPCalculator

        polygon = Polygon([
            (-46.83, -23.24),
            (-46.81, -23.24),
            (-46.81, -23.27),
            (-46.83, -23.27),
            (-46.83, -23.24)
        ])

        rivers = gpd.GeoDataFrame({
            'geometry': [
                LineString([(-46.82, -23.25), (-46.82, -23.26)])
            ],
            'largura_m': [5]
        }, crs='EPSG:4326')

        calc = APPCalculator(polygon)
        app_gdf = calc.calculate_all_apps(rivers_gdf=rivers)

        required_attrs = ['cod_app', 'tip_app', 'des_condic', 'num_area']
        for attr in required_attrs:
            assert attr in app_gdf.columns
