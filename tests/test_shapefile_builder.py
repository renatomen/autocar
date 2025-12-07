"""
Testes para o módulo shapefile_builder.
TDD: Testes escritos antes da implementação.
"""
import pytest
from pathlib import Path
from shapely.geometry import Polygon
import geopandas as gpd
import zipfile
import tempfile
import shutil

FIXTURES_DIR = Path(__file__).parent / 'fixtures'


class TestShapefileBuilder:
    """Testes para geração de Shapefiles SICAR."""

    def test_creates_output_directory(self):
        """Deve criar diretório de saída."""
        from sicar_formatter.shapefile_builder import SICARShapefileBuilder

        with tempfile.TemporaryDirectory() as tmpdir:
            builder = SICARShapefileBuilder('teste', output_base=tmpdir)

            assert builder.output_dir.exists()

    def test_adds_layer_successfully(self):
        """Deve adicionar camada ao builder."""
        from sicar_formatter.shapefile_builder import SICARShapefileBuilder

        polygon = Polygon([
            (-46.85, -23.20),
            (-46.84, -23.20),
            (-46.84, -23.21),
            (-46.85, -23.21),
            (-46.85, -23.20)
        ])

        gdf = gpd.GeoDataFrame({
            'geometry': [polygon],
            'nome': ['Teste']
        }, crs='EPSG:4326')

        with tempfile.TemporaryDirectory() as tmpdir:
            builder = SICARShapefileBuilder('teste', output_base=tmpdir)
            builder.add_layer('perimetro', gdf)

            assert 'perimetro' in builder.layers

    def test_builds_shapefile_with_all_components(self):
        """Shapefile deve ter todos os componentes (.shp, .shx, .dbf, .prj)."""
        from sicar_formatter.shapefile_builder import SICARShapefileBuilder

        polygon = Polygon([
            (-46.85, -23.20),
            (-46.84, -23.20),
            (-46.84, -23.21),
            (-46.85, -23.21),
            (-46.85, -23.20)
        ])

        gdf = gpd.GeoDataFrame({
            'geometry': [polygon],
            'nome': ['Teste']
        }, crs='EPSG:4326')

        with tempfile.TemporaryDirectory() as tmpdir:
            builder = SICARShapefileBuilder('teste', output_base=tmpdir)
            builder.add_layer('perimetro', gdf)
            paths = builder.build_shapefiles()

            shp_path = Path(paths['perimetro'])
            assert shp_path.exists()
            assert shp_path.with_suffix('.shx').exists()
            assert shp_path.with_suffix('.dbf').exists()
            assert shp_path.with_suffix('.prj').exists()

    def test_builds_valid_zip(self):
        """Deve gerar ZIP válido com todos os shapefiles."""
        from sicar_formatter.shapefile_builder import SICARShapefileBuilder

        polygon = Polygon([
            (-46.85, -23.20),
            (-46.84, -23.20),
            (-46.84, -23.21),
            (-46.85, -23.21),
            (-46.85, -23.20)
        ])

        gdf = gpd.GeoDataFrame({
            'geometry': [polygon],
            'nome': ['Teste']
        }, crs='EPSG:4326')

        with tempfile.TemporaryDirectory() as tmpdir:
            builder = SICARShapefileBuilder('teste', output_base=tmpdir)
            builder.add_layer('perimetro', gdf)
            zip_path = builder.build_zip()

            assert Path(zip_path).exists()

            # Verificar conteúdo do ZIP
            with zipfile.ZipFile(zip_path, 'r') as zf:
                names = zf.namelist()
                extensions = {Path(n).suffix for n in names}

                assert '.shp' in extensions
                assert '.shx' in extensions
                assert '.dbf' in extensions
                assert '.prj' in extensions

    def test_shapefiles_in_wgs84(self):
        """Shapefiles devem estar em WGS84 (EPSG:4326)."""
        from sicar_formatter.shapefile_builder import SICARShapefileBuilder

        polygon = Polygon([
            (-46.85, -23.20),
            (-46.84, -23.20),
            (-46.84, -23.21),
            (-46.85, -23.21),
            (-46.85, -23.20)
        ])

        # Criar GeoDataFrame em UTM
        gdf = gpd.GeoDataFrame({
            'geometry': [polygon],
            'nome': ['Teste']
        }, crs='EPSG:31983')  # UTM

        with tempfile.TemporaryDirectory() as tmpdir:
            builder = SICARShapefileBuilder('teste', output_base=tmpdir)
            builder.add_layer('perimetro', gdf)
            paths = builder.build_shapefiles()

            # Ler shapefile gerado
            result = gpd.read_file(paths['perimetro'])
            assert result.crs.to_epsg() == 4326


class TestSICARPackage:
    """Testes para geração de pacote SICAR completo."""

    def test_build_complete_package(self):
        """Deve gerar pacote completo com todas as camadas."""
        from sicar_formatter.shapefile_builder import build_sicar_package

        perimetro = Polygon([
            (-46.85, -23.20),
            (-46.84, -23.20),
            (-46.84, -23.21),
            (-46.85, -23.21),
            (-46.85, -23.20)
        ])

        app = Polygon([
            (-46.848, -23.202),
            (-46.842, -23.202),
            (-46.842, -23.205),
            (-46.848, -23.205),
            (-46.848, -23.202)
        ])

        perimetro_gdf = gpd.GeoDataFrame({
            'geometry': [perimetro],
            'nom_imovel': ['Fazenda Teste']
        }, crs='EPSG:4326')

        app_gdf = gpd.GeoDataFrame({
            'geometry': [app],
            'tip_app': ['MARGEM_CURSO_DAGUA']
        }, crs='EPSG:4326')

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = build_sicar_package(
                output_name='teste',
                perimetro_gdf=perimetro_gdf,
                app_gdf=app_gdf,
                output_base=tmpdir
            )

            assert Path(zip_path).exists()

            # Verificar que tem múltiplas camadas
            with zipfile.ZipFile(zip_path, 'r') as zf:
                names = zf.namelist()
                # Deve ter arquivos de perimetro e app
                assert any('perimetro' in n for n in names)
                assert any('app' in n for n in names)

    def test_ensures_sicar_attributes(self):
        """Deve garantir atributos obrigatórios do SICAR."""
        from sicar_formatter.shapefile_builder import SICARShapefileBuilder

        polygon = Polygon([
            (-46.85, -23.20),
            (-46.84, -23.20),
            (-46.84, -23.21),
            (-46.85, -23.21),
            (-46.85, -23.20)
        ])

        # GeoDataFrame sem atributos SICAR
        gdf = gpd.GeoDataFrame({
            'geometry': [polygon]
        }, crs='EPSG:4326')

        with tempfile.TemporaryDirectory() as tmpdir:
            builder = SICARShapefileBuilder('teste', output_base=tmpdir)
            builder.add_layer('perimetro', gdf)
            paths = builder.build_shapefiles()

            # Ler shapefile e verificar atributos
            result = gpd.read_file(paths['perimetro'])

            # Deve ter adicionado atributos obrigatórios
            assert 'cod_imovel' in result.columns or 'nom_imovel' in result.columns
