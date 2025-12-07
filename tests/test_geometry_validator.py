"""
Testes para o módulo geometry_validator.
TDD: Testes escritos antes da implementação.
"""
import pytest
from pathlib import Path
from shapely.geometry import Polygon, LineString, Point

FIXTURES_DIR = Path(__file__).parent / 'fixtures'


class TestGeometryValidator:
    """Testes para validação de geometrias."""

    def test_valid_polygon_passes_validation(self):
        """Polígono válido deve passar na validação."""
        from geospatial.geometry_validator import GeometryValidator

        # Quadrado simples
        polygon = Polygon([
            (-46.85, -23.20),
            (-46.84, -23.20),
            (-46.84, -23.21),
            (-46.85, -23.21),
            (-46.85, -23.20)
        ])

        validator = GeometryValidator()
        result, errors = validator.validate(polygon)

        assert result is not None
        assert result.is_valid
        assert len(errors) == 0

    def test_self_intersecting_polygon_is_fixed(self):
        """Polígono com auto-interseção deve ser corrigido."""
        from geospatial.geometry_validator import GeometryValidator

        # Polígono em forma de "8" (auto-intersecção)
        polygon = Polygon([
            (0, 0), (2, 2), (2, 0), (0, 2), (0, 0)
        ])

        assert not polygon.is_valid  # Confirma que é inválido

        validator = GeometryValidator()
        result, errors = validator.validate(polygon)

        assert result.is_valid
        assert any('auto-intersec' in e.lower() for e in errors)

    def test_area_below_minimum_raises_warning(self):
        """Área abaixo do mínimo legal deve gerar warning."""
        from geospatial.geometry_validator import GeometryValidator

        # Polígono muito pequeno (~100m²)
        polygon = Polygon([
            (-46.850000, -23.200000),
            (-46.849990, -23.200000),
            (-46.849990, -23.200010),
            (-46.850000, -23.200010),
            (-46.850000, -23.200000)
        ])

        validator = GeometryValidator()
        result, errors = validator.validate(polygon)

        assert any('área' in e.lower() or 'mínimo' in e.lower() for e in errors)

    def test_complex_polygon_is_simplified(self):
        """Polígono muito complexo deve ser simplificado."""
        from geospatial.geometry_validator import GeometryValidator

        # Criar polígono com muitos vértices
        import math
        n_points = 1500
        coords = []
        for i in range(n_points):
            angle = 2 * math.pi * i / n_points
            x = -46.85 + 0.01 * math.cos(angle)
            y = -23.20 + 0.01 * math.sin(angle)
            coords.append((x, y))
        coords.append(coords[0])  # Fechar

        polygon = Polygon(coords)
        assert len(polygon.exterior.coords) > 1000

        validator = GeometryValidator(max_vertices=1000)
        result, errors = validator.validate(polygon)

        assert len(result.exterior.coords) <= 1000
        assert any('simplificad' in e.lower() for e in errors)

    def test_mursa_kml_passes_validation(self):
        """O KML real Mursa deve passar na validação."""
        from geospatial.kml_parser import parse_kml
        from geospatial.geometry_validator import GeometryValidator

        kml_path = FIXTURES_DIR / 'mursa_real.kml'
        _, perimeter = parse_kml(str(kml_path))

        validator = GeometryValidator()
        result, errors = validator.validate(perimeter)

        assert result is not None
        assert result.is_valid
        # Pode ter warnings mas não erros críticos


class TestGeometryType:
    """Testes para verificação de tipo de geometria."""

    def test_rejects_linestring(self):
        """Deve rejeitar LineString."""
        from geospatial.geometry_validator import GeometryValidator

        line = LineString([(-46.85, -23.20), (-46.84, -23.21)])

        validator = GeometryValidator()

        with pytest.raises(TypeError, match="[Pp]olígono"):
            validator.validate(line)

    def test_rejects_point(self):
        """Deve rejeitar Point."""
        from geospatial.geometry_validator import GeometryValidator

        point = Point(-46.85, -23.20)

        validator = GeometryValidator()

        with pytest.raises(TypeError, match="[Pp]olígono"):
            validator.validate(point)
