"""
Geração de Shapefiles formatados para upload no SICAR-SP.
"""
import geopandas as gpd
import zipfile
from pathlib import Path
import logging
from typing import Dict, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DEFAULT_CRS, SICAR_ATTRIBUTES, OUTPUT_DIR

logger = logging.getLogger(__name__)


class SICARShapefileBuilder:
    """Builder de Shapefiles para SICAR-SP."""

    def __init__(self, output_name: str, output_base: str = None):
        """
        Args:
            output_name: Nome base para os arquivos de saída
            output_base: Diretório base de saída (default: OUTPUT_DIR)
        """
        self.output_name = output_name
        base = Path(output_base) if output_base else OUTPUT_DIR
        self.output_dir = base / output_name / 'shapefiles'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.layers: Dict[str, gpd.GeoDataFrame] = {}

    def add_layer(self, name: str, gdf: gpd.GeoDataFrame) -> None:
        """
        Adiciona uma camada ao builder.

        Args:
            name: Nome da camada (perimetro, app, reserva_legal, etc.)
            gdf: GeoDataFrame com os dados
        """
        if gdf is None or gdf.empty:
            logger.warning(f"Camada '{name}' está vazia, ignorando")
            return

        # Garantir CRS WGS84
        if gdf.crs is None:
            gdf = gdf.set_crs(DEFAULT_CRS)
        elif gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(DEFAULT_CRS)

        # Validar e adicionar atributos obrigatórios
        gdf = self._ensure_attributes(name, gdf)

        self.layers[name] = gdf
        logger.info(f"Camada '{name}' adicionada: {len(gdf)} feições")

    def _ensure_attributes(
        self,
        layer_name: str,
        gdf: gpd.GeoDataFrame
    ) -> gpd.GeoDataFrame:
        """Garante que a camada tenha os atributos obrigatórios."""
        schema = SICAR_ATTRIBUTES.get(layer_name, {})

        for attr, dtype in schema.items():
            if attr not in gdf.columns:
                # Adicionar atributo com valor padrão
                if dtype == str:
                    gdf[attr] = ''
                elif dtype == float:
                    gdf[attr] = 0.0
                else:
                    gdf[attr] = None

        return gdf

    def build_shapefiles(self) -> Dict[str, str]:
        """
        Gera os shapefiles individuais.

        Returns:
            Dict com caminhos dos shapefiles gerados
        """
        paths = {}

        for name, gdf in self.layers.items():
            shp_path = self.output_dir / f'{name}.shp'

            # Salvar com encoding UTF-8
            gdf.to_file(
                str(shp_path),
                driver='ESRI Shapefile',
                encoding='UTF-8'
            )

            paths[name] = str(shp_path)
            logger.info(f"Shapefile gerado: {shp_path}")

        return paths

    def build_zip(self) -> str:
        """
        Gera ZIP com todos os shapefiles para upload no SICAR.

        Returns:
            Caminho do arquivo ZIP
        """
        # Primeiro gerar shapefiles
        self.build_shapefiles()

        zip_path = self.output_dir.parent / 'car_upload.zip'

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in self.output_dir.iterdir():
                # Incluir todos os componentes do shapefile
                if file.suffix in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                    zf.write(file, file.name)
                    logger.debug(f"Adicionado ao ZIP: {file.name}")

        logger.info(f"ZIP gerado: {zip_path}")

        # Verificar componentes obrigatórios
        self._validate_zip(str(zip_path))

        return str(zip_path)

    def _validate_zip(self, zip_path: str) -> bool:
        """Valida se o ZIP contém todos os componentes necessários."""
        required_extensions = {'.shp', '.shx', '.dbf', '.prj'}

        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = {Path(f).suffix for f in zf.namelist()}

            missing = required_extensions - files
            if missing:
                logger.warning(
                    f"ZIP pode estar incompleto. Extensões faltando: {missing}"
                )
                return False
            else:
                logger.info("ZIP validado: contém todos os componentes obrigatórios")
                return True


def build_sicar_package(
    output_name: str,
    perimetro_gdf: gpd.GeoDataFrame,
    app_gdf: gpd.GeoDataFrame = None,
    reserva_legal_gdf: gpd.GeoDataFrame = None,
    vegetacao_nativa_gdf: gpd.GeoDataFrame = None,
    area_consolidada_gdf: gpd.GeoDataFrame = None,
    uso_restrito_gdf: gpd.GeoDataFrame = None,
    hidrografia_gdf: gpd.GeoDataFrame = None,
    servidao_gdf: gpd.GeoDataFrame = None,
    output_base: str = None
) -> str:
    """
    Função de conveniência para gerar pacote SICAR completo.

    Args:
        output_name: Nome do imóvel/saída
        perimetro_gdf: GeoDataFrame do perímetro (obrigatório)
        app_gdf: GeoDataFrame das APPs
        reserva_legal_gdf: GeoDataFrame da Reserva Legal
        vegetacao_nativa_gdf: GeoDataFrame da vegetação nativa
        area_consolidada_gdf: GeoDataFrame das áreas consolidadas
        uso_restrito_gdf: GeoDataFrame de uso restrito
        hidrografia_gdf: GeoDataFrame da hidrografia
        servidao_gdf: GeoDataFrame das servidões
        output_base: Diretório base de saída

    Returns:
        Caminho do arquivo ZIP
    """
    builder = SICARShapefileBuilder(output_name, output_base=output_base)

    builder.add_layer('perimetro', perimetro_gdf)
    builder.add_layer('app', app_gdf)
    builder.add_layer('reserva_legal', reserva_legal_gdf)
    builder.add_layer('vegetacao_nativa', vegetacao_nativa_gdf)
    builder.add_layer('area_consolidada', area_consolidada_gdf)
    builder.add_layer('uso_restrito', uso_restrito_gdf)
    builder.add_layer('hidrografia', hidrografia_gdf)
    builder.add_layer('servidao', servidao_gdf)

    return builder.build_zip()
