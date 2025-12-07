"""
Coleta de dados hidrográficos de fontes públicas.
"""
import geopandas as gpd
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union
import logging
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DEFAULT_CRS, UTM_CRS_SP, IBGE_DIR

logger = logging.getLogger(__name__)


class HydrologyCollector:
    """Coletor de dados hidrográficos."""

    def __init__(self, data_dir: Path = None):
        """
        Args:
            data_dir: Diretório com dados IBGE (opcional)
        """
        self.data_dir = data_dir or IBGE_DIR

    def get_rivers_in_area(
        self,
        polygon: Polygon,
        buffer_km: float = 2
    ) -> gpd.GeoDataFrame:
        """
        Busca rios dentro e próximos ao polígono.

        Args:
            polygon: Perímetro do imóvel
            buffer_km: Buffer de busca em km

        Returns:
            GeoDataFrame com rios (LineString) e atributo largura_m
        """
        logger.info(f"Buscando hidrografia com buffer de {buffer_km}km")

        search_area = self._create_search_buffer(polygon, buffer_km)

        # Tentar carregar dados locais IBGE
        rivers = self._load_local_rivers(search_area)

        if rivers is None or rivers.empty:
            logger.warning("Dados hidrográficos locais não encontrados")
            # Retornar GeoDataFrame vazio com schema correto
            rivers = gpd.GeoDataFrame({
                'geometry': [],
                'nome': [],
                'largura_m': []
            }, crs=DEFAULT_CRS)

        # Garantir que tem atributo largura_m
        if 'largura_m' not in rivers.columns:
            # Estimar largura baseado em tipo/classe se disponível
            rivers['largura_m'] = self._estimate_river_width(rivers)

        logger.info(f"Encontrados {len(rivers)} cursos d'água")
        return rivers

    def get_lakes_in_area(self, polygon: Polygon) -> gpd.GeoDataFrame:
        """
        Busca lagos e lagoas dentro do polígono.

        Args:
            polygon: Perímetro do imóvel

        Returns:
            GeoDataFrame com lagos (Polygon) e atributo area_ha
        """
        logger.info("Buscando lagos e lagoas")

        # Tentar carregar dados locais
        lakes = self._load_local_lakes(polygon)

        if lakes is None or lakes.empty:
            lakes = gpd.GeoDataFrame({
                'geometry': [],
                'nome': [],
                'area_ha': []
            }, crs=DEFAULT_CRS)

        # Calcular área se não existir
        if 'area_ha' not in lakes.columns and not lakes.empty:
            lakes_utm = lakes.to_crs(UTM_CRS_SP)
            lakes['area_ha'] = lakes_utm.geometry.area / 10000

        logger.info(f"Encontrados {len(lakes)} lagos/lagoas")
        return lakes

    def _create_search_buffer(
        self,
        polygon: Polygon,
        buffer_km: float
    ) -> Polygon:
        """Cria área de busca com buffer em km."""
        # Converter para UTM, aplicar buffer, converter de volta
        gdf = gpd.GeoDataFrame({'geometry': [polygon]}, crs=DEFAULT_CRS)
        gdf_utm = gdf.to_crs(UTM_CRS_SP)

        buffer_m = buffer_km * 1000
        buffered = gdf_utm.geometry.iloc[0].buffer(buffer_m)

        gdf_buffered = gpd.GeoDataFrame({'geometry': [buffered]}, crs=UTM_CRS_SP)
        return gdf_buffered.to_crs(DEFAULT_CRS).geometry.iloc[0]

    def _load_local_rivers(
        self,
        search_area: Polygon
    ) -> Optional[gpd.GeoDataFrame]:
        """Carrega rios de arquivo local IBGE."""
        # Procurar arquivos de hidrografia
        possible_files = [
            self.data_dir / 'hidrografia.shp',
            self.data_dir / 'drenagem.shp',
            self.data_dir / 'rios.shp',
            self.data_dir / 'cursos_dagua.shp',
        ]

        for filepath in possible_files:
            if filepath.exists():
                logger.info(f"Carregando hidrografia de {filepath}")
                try:
                    rivers = gpd.read_file(filepath)
                    rivers = rivers.to_crs(DEFAULT_CRS)
                    # Filtrar pela área de busca
                    rivers = rivers[rivers.intersects(search_area)]
                    return rivers
                except Exception as e:
                    logger.error(f"Erro ao carregar {filepath}: {e}")

        return None

    def _load_local_lakes(self, polygon: Polygon) -> Optional[gpd.GeoDataFrame]:
        """Carrega lagos de arquivo local."""
        possible_files = [
            self.data_dir / 'lagos.shp',
            self.data_dir / 'massas_dagua.shp',
            self.data_dir / 'reservatorios.shp',
        ]

        for filepath in possible_files:
            if filepath.exists():
                logger.info(f"Carregando lagos de {filepath}")
                try:
                    lakes = gpd.read_file(filepath)
                    lakes = lakes.to_crs(DEFAULT_CRS)
                    lakes = lakes[lakes.intersects(polygon)]
                    return lakes
                except Exception as e:
                    logger.error(f"Erro ao carregar {filepath}: {e}")

        return None

    def _estimate_river_width(self, rivers: gpd.GeoDataFrame) -> list:
        """
        Estima largura de rios baseado em atributos disponíveis.

        Heurística:
        - Rios com nome conhecido: assumir 10m
        - Córregos/riachos: 5m
        - Desconhecidos: 5m (menor APP)
        """
        widths = []

        for idx, row in rivers.iterrows():
            nome = str(row.get('nome', '')).lower()
            tipo = str(row.get('tipo', '')).lower()

            if 'rio' in nome or 'rio' in tipo:
                widths.append(10.0)
            elif 'córrego' in nome or 'riacho' in nome:
                widths.append(5.0)
            elif 'ribeirão' in nome:
                widths.append(8.0)
            else:
                widths.append(5.0)  # Padrão conservador

        return widths if widths else []


class NascenteIdentifier:
    """Identificador de nascentes a partir de hidrografia."""

    def identify_from_rivers(
        self,
        polygon: Polygon,
        rivers: gpd.GeoDataFrame
    ) -> gpd.GeoDataFrame:
        """
        Identifica nascentes como pontos iniciais de rios.

        Heurística: pontos de início de cursos d'água dentro
        ou próximos ao perímetro são potenciais nascentes.

        Args:
            polygon: Perímetro do imóvel
            rivers: GeoDataFrame com rios

        Returns:
            GeoDataFrame com pontos de nascentes
        """
        logger.info("Identificando nascentes")

        nascentes = []

        if rivers.empty:
            return gpd.GeoDataFrame({
                'geometry': [],
                'tipo': []
            }, crs=DEFAULT_CRS)

        # Buffer do perímetro para busca
        gdf_poly = gpd.GeoDataFrame({'geometry': [polygon]}, crs=DEFAULT_CRS)
        gdf_utm = gdf_poly.to_crs(UTM_CRS_SP)
        buffer_100m = gdf_utm.geometry.iloc[0].buffer(100)
        gdf_buffer = gpd.GeoDataFrame({'geometry': [buffer_100m]}, crs=UTM_CRS_SP)
        search_area = gdf_buffer.to_crs(DEFAULT_CRS).geometry.iloc[0]

        for idx, row in rivers.iterrows():
            geom = row.geometry

            if isinstance(geom, LineString):
                # Ponto inicial do rio pode ser nascente
                start_point = Point(geom.coords[0])

                if search_area.contains(start_point):
                    nascentes.append({
                        'geometry': start_point,
                        'tipo': 'NASCENTE_IDENTIFICADA'
                    })

        if nascentes:
            gdf = gpd.GeoDataFrame(nascentes, crs=DEFAULT_CRS)
            # Remover duplicatas próximas (50m)
            gdf = self._remove_nearby_duplicates(gdf, tolerance_m=50)
            logger.info(f"Identificadas {len(gdf)} nascentes")
            return gdf

        return gpd.GeoDataFrame({
            'geometry': [],
            'tipo': []
        }, crs=DEFAULT_CRS)

    def _remove_nearby_duplicates(
        self,
        points: gpd.GeoDataFrame,
        tolerance_m: float
    ) -> gpd.GeoDataFrame:
        """Remove pontos muito próximos."""
        if points.empty:
            return points

        points_utm = points.to_crs(UTM_CRS_SP)
        keep = [True] * len(points_utm)

        for i in range(len(points_utm)):
            if not keep[i]:
                continue
            for j in range(i + 1, len(points_utm)):
                if not keep[j]:
                    continue
                dist = points_utm.geometry.iloc[i].distance(
                    points_utm.geometry.iloc[j]
                )
                if dist < tolerance_m:
                    keep[j] = False

        return points[keep].reset_index(drop=True)
