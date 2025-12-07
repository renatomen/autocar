"""
Testes para o módulo kml_parser.
TDD: Testes escritos antes da implementação.
"""
import pytest
from pathlib import Path
from shapely.geometry import Polygon

# Fixtures path
FIXTURES_DIR = Path(__file__).parent / 'fixtures'


class TestParseKml:
    """Testes para a função parse_kml."""

    def test_parse_valid_kml_returns_geodataframe_and_polygon(self):
        """Deve retornar GeoDataFrame e Polygon para KML válido."""
        from geospatial.kml_parser import parse_kml

        kml_path = FIXTURES_DIR / 'mursa_real.kml'
        gdf, perimeter = parse_kml(str(kml_path))

        assert gdf is not None
        assert not gdf.empty
        assert isinstance(perimeter, Polygon)

    def test_parse_kml_extracts_correct_crs(self):
        """Deve extrair coordenadas em WGS84 (EPSG:4326)."""
        from geospatial.kml_parser import parse_kml

        kml_path = FIXTURES_DIR / 'mursa_real.kml'
        gdf, _ = parse_kml(str(kml_path))

        assert gdf.crs is not None
        assert gdf.crs.to_epsg() == 4326

    def test_parse_kml_perimeter_is_valid_geometry(self):
        """O perímetro extraído deve ser uma geometria válida."""
        from geospatial.kml_parser import parse_kml

        kml_path = FIXTURES_DIR / 'mursa_real.kml'
        _, perimeter = parse_kml(str(kml_path))

        assert perimeter.is_valid
        assert not perimeter.is_empty

    def test_parse_kml_perimeter_is_closed(self):
        """O perímetro deve ser um polígono fechado."""
        from geospatial.kml_parser import parse_kml

        kml_path = FIXTURES_DIR / 'mursa_real.kml'
        _, perimeter = parse_kml(str(kml_path))

        # Um polígono fechado tem primeiro e último ponto iguais
        coords = list(perimeter.exterior.coords)
        assert coords[0] == coords[-1]

    def test_parse_kml_preserves_vertex_count(self):
        """Deve preservar o número de vértices do KML original."""
        from geospatial.kml_parser import parse_kml

        kml_path = FIXTURES_DIR / 'mursa_real.kml'
        _, perimeter = parse_kml(str(kml_path))

        # O KML Mursa tem 14 coordenadas (13 vértices + fechamento)
        coords = list(perimeter.exterior.coords)
        assert len(coords) == 14

    def test_parse_empty_kml_raises_error(self):
        """Deve levantar erro para KML vazio."""
        from geospatial.kml_parser import parse_kml

        kml_path = FIXTURES_DIR / 'invalid_empty.kml'

        with pytest.raises(ValueError, match="não contém"):
            parse_kml(str(kml_path))

    def test_parse_linestring_only_raises_error(self):
        """Deve levantar erro para KML sem polígonos."""
        from geospatial.kml_parser import parse_kml

        kml_path = FIXTURES_DIR / 'linestring_only.kml'

        with pytest.raises(ValueError, match="não contém polígonos"):
            parse_kml(str(kml_path))

    def test_parse_nonexistent_file_raises_error(self):
        """Deve levantar erro para arquivo inexistente."""
        from geospatial.kml_parser import parse_kml

        with pytest.raises(Exception):
            parse_kml('/path/to/nonexistent.kml')


class TestCoordinatePrecision:
    """Testes para validação de precisão de coordenadas."""

    def test_mursa_coordinates_have_sufficient_precision(self):
        """As coordenadas do KML Mursa devem ter precisão suficiente."""
        from geospatial.kml_parser import parse_kml

        kml_path = FIXTURES_DIR / 'mursa_real.kml'
        _, perimeter = parse_kml(str(kml_path))

        coords = list(perimeter.exterior.coords)
        for lon, lat in coords:
            # Verificar pelo menos 8 casas decimais
            lon_str = str(lon)
            lat_str = str(lat)

            if '.' in lon_str:
                assert len(lon_str.split('.')[-1]) >= 8
            if '.' in lat_str:
                assert len(lat_str.split('.')[-1]) >= 8
