"""
Testes para o módulo reserva_legal.
TDD: Testes escritos antes da implementação.
"""
import pytest
from pathlib import Path
from shapely.geometry import Polygon
import geopandas as gpd

FIXTURES_DIR = Path(__file__).parent / 'fixtures'


class TestReservaLegalCalculator:
    """Testes para cálculo de Reserva Legal."""

    def test_required_area_is_20_percent_mata_atlantica(self):
        """RL deve ser 20% da área em Mata Atlântica."""
        from car_layers.reserva_legal import ReservaLegalCalculator

        # Polígono de ~100 ha
        polygon = Polygon([
            (-46.85, -23.20),
            (-46.841, -23.20),
            (-46.841, -23.209),
            (-46.85, -23.209),
            (-46.85, -23.20)
        ])

        calc = ReservaLegalCalculator(polygon, bioma='MATA_ATLANTICA')
        required_ha = calc.calculate_required_area()

        # ~100 ha * 20% = ~20 ha (com margem de erro)
        assert 15 < required_ha < 25

    def test_required_area_is_80_percent_amazonia(self):
        """RL deve ser 80% da área na Amazônia."""
        from car_layers.reserva_legal import ReservaLegalCalculator

        polygon = Polygon([
            (-46.85, -23.20),
            (-46.841, -23.20),
            (-46.841, -23.209),
            (-46.85, -23.209),
            (-46.85, -23.20)
        ])

        calc = ReservaLegalCalculator(polygon, bioma='AMAZONIA')
        required_ha = calc.calculate_required_area()

        # ~100 ha * 80% = ~80 ha
        assert 60 < required_ha < 100

    def test_suggest_location_returns_geodataframe(self):
        """Deve retornar GeoDataFrame com sugestão de RL."""
        from car_layers.reserva_legal import ReservaLegalCalculator

        polygon = Polygon([
            (-46.85, -23.20),
            (-46.841, -23.20),
            (-46.841, -23.209),
            (-46.85, -23.209),
            (-46.85, -23.20)
        ])

        calc = ReservaLegalCalculator(polygon)
        rl_gdf = calc.suggest_location()

        assert isinstance(rl_gdf, gpd.GeoDataFrame)
        assert not rl_gdf.empty

    def test_rl_not_overlaps_app(self):
        """RL não deve sobrepor APP."""
        from car_layers.reserva_legal import ReservaLegalCalculator
        from shapely.geometry import LineString

        polygon = Polygon([
            (-46.83, -23.24),
            (-46.81, -23.24),
            (-46.81, -23.27),
            (-46.83, -23.27),
            (-46.83, -23.24)
        ])

        # Criar APP fictícia (10% da área)
        app_polygon = Polygon([
            (-46.825, -23.245),
            (-46.815, -23.245),
            (-46.815, -23.250),
            (-46.825, -23.250),
            (-46.825, -23.245)
        ])
        app_gdf = gpd.GeoDataFrame({
            'geometry': [app_polygon],
            'tip_app': ['MARGEM_CURSO_DAGUA']
        }, crs='EPSG:4326')

        calc = ReservaLegalCalculator(polygon)
        rl_gdf = calc.suggest_location(app_gdf=app_gdf)

        if not rl_gdf.empty:
            rl_geometry = rl_gdf.geometry.iloc[0]
            app_geometry = app_gdf.geometry.iloc[0]

            # RL não deve ter interseção significativa com APP
            intersection = rl_geometry.intersection(app_geometry)
            assert intersection.area < 0.001 * rl_geometry.area

    def test_rl_has_sicar_attributes(self):
        """RL deve ter atributos obrigatórios do SICAR."""
        from car_layers.reserva_legal import ReservaLegalCalculator

        polygon = Polygon([
            (-46.85, -23.20),
            (-46.841, -23.20),
            (-46.841, -23.209),
            (-46.85, -23.209),
            (-46.85, -23.20)
        ])

        calc = ReservaLegalCalculator(polygon)
        rl_gdf = calc.suggest_location()

        required_attrs = ['cod_rl', 'des_condic', 'num_area', 'ind_averbada']
        for attr in required_attrs:
            assert attr in rl_gdf.columns

    def test_prioritizes_native_vegetation(self):
        """Deve priorizar áreas com vegetação nativa para RL."""
        from car_layers.reserva_legal import ReservaLegalCalculator

        polygon = Polygon([
            (-46.83, -23.24),
            (-46.81, -23.24),
            (-46.81, -23.27),
            (-46.83, -23.27),
            (-46.83, -23.24)
        ])

        # Vegetação nativa cobrindo parte do imóvel
        veg_polygon = Polygon([
            (-46.825, -23.255),
            (-46.815, -23.255),
            (-46.815, -23.265),
            (-46.825, -23.265),
            (-46.825, -23.255)
        ])
        veg_gdf = gpd.GeoDataFrame({
            'geometry': [veg_polygon],
            'des_estagio': ['MEDIO']
        }, crs='EPSG:4326')

        calc = ReservaLegalCalculator(polygon)
        rl_gdf = calc.suggest_location(vegetacao_nativa_gdf=veg_gdf)

        if not rl_gdf.empty:
            rl_geometry = rl_gdf.geometry.iloc[0]
            veg_geometry = veg_gdf.geometry.iloc[0]

            # RL deve ter interseção significativa com vegetação nativa
            intersection = rl_geometry.intersection(veg_geometry)
            assert intersection.area > 0
