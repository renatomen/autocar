"""
Testes para o módulo hydrology.
TDD: Testes escritos antes da implementação.
"""
import pytest
from pathlib import Path
from shapely.geometry import Polygon, LineString, Point
import geopandas as gpd

FIXTURES_DIR = Path(__file__).parent / 'fixtures'


class TestHydrologyCollector:
    """Testes para coleta de dados hidrográficos."""

    def test_get_rivers_returns_geodataframe(self):
        """Deve retornar GeoDataFrame com rios."""
        from data_sources.hydrology import HydrologyCollector
        from geospatial.kml_parser import parse_kml

        kml_path = FIXTURES_DIR / 'mursa_real.kml'
        _, perimeter = parse_kml(str(kml_path))

        collector = HydrologyCollector()
        rivers = collector.get_rivers_in_area(perimeter, buffer_km=2)

        assert isinstance(rivers, gpd.GeoDataFrame)
        # Pode estar vazio se não houver dados locais
        assert 'geometry' in rivers.columns

    def test_rivers_have_required_attributes(self):
        """Rios devem ter atributos necessários para APP."""
        from data_sources.hydrology import HydrologyCollector
        from geospatial.kml_parser import parse_kml

        kml_path = FIXTURES_DIR / 'mursa_real.kml'
        _, perimeter = parse_kml(str(kml_path))

        collector = HydrologyCollector()
        rivers = collector.get_rivers_in_area(perimeter, buffer_km=2)

        if not rivers.empty:
            # Deve ter largura para cálculo de APP
            assert 'largura_m' in rivers.columns or 'width' in rivers.columns

    def test_get_lakes_returns_geodataframe(self):
        """Deve retornar GeoDataFrame com lagos."""
        from data_sources.hydrology import HydrologyCollector
        from geospatial.kml_parser import parse_kml

        kml_path = FIXTURES_DIR / 'mursa_real.kml'
        _, perimeter = parse_kml(str(kml_path))

        collector = HydrologyCollector()
        lakes = collector.get_lakes_in_area(perimeter)

        assert isinstance(lakes, gpd.GeoDataFrame)

    def test_buffer_expands_search_area(self):
        """Buffer deve expandir área de busca."""
        from data_sources.hydrology import HydrologyCollector

        polygon = Polygon([
            (-46.85, -23.20),
            (-46.84, -23.20),
            (-46.84, -23.21),
            (-46.85, -23.21),
            (-46.85, -23.20)
        ])

        collector = HydrologyCollector()

        # Área de busca deve ser maior que o polígono original
        search_area = collector._create_search_buffer(polygon, buffer_km=2)

        assert search_area.area > polygon.area


class TestNascenteIdentifier:
    """Testes para identificação de nascentes."""

    def test_identify_nascentes_returns_geodataframe(self):
        """Deve retornar GeoDataFrame com pontos de nascentes."""
        from data_sources.hydrology import NascenteIdentifier
        from geospatial.kml_parser import parse_kml

        kml_path = FIXTURES_DIR / 'mursa_real.kml'
        _, perimeter = parse_kml(str(kml_path))

        identifier = NascenteIdentifier()

        # Criar rios fictícios para teste
        rivers = gpd.GeoDataFrame({
            'geometry': [
                LineString([(-46.815, -23.255), (-46.820, -23.260)])
            ],
            'largura_m': [5]
        }, crs='EPSG:4326')

        nascentes = identifier.identify_from_rivers(perimeter, rivers)

        assert isinstance(nascentes, gpd.GeoDataFrame)

    def test_nascentes_are_points(self):
        """Nascentes devem ser geometrias do tipo Point."""
        from data_sources.hydrology import NascenteIdentifier

        identifier = NascenteIdentifier()

        # Criar rio fictício
        rivers = gpd.GeoDataFrame({
            'geometry': [
                LineString([(-46.815, -23.255), (-46.820, -23.260)])
            ],
            'largura_m': [5]
        }, crs='EPSG:4326')

        polygon = Polygon([
            (-46.83, -23.24),
            (-46.81, -23.24),
            (-46.81, -23.27),
            (-46.83, -23.27),
            (-46.83, -23.24)
        ])

        nascentes = identifier.identify_from_rivers(polygon, rivers)

        if not nascentes.empty:
            for geom in nascentes.geometry:
                assert isinstance(geom, Point)
