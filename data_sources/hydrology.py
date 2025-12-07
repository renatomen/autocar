"""
Coleta de dados hidrográficos de fontes públicas.
Suporta dados locais (IBGE) e busca online (OpenStreetMap).
"""
import geopandas as gpd
from shapely.geometry import Polygon, Point, LineString, box, shape
from shapely.ops import unary_union
import requests
import logging
from pathlib import Path
from typing import Optional
import time

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DEFAULT_CRS, UTM_CRS_SP, IBGE_DIR

logger = logging.getLogger(__name__)

# API Overpass para OpenStreetMap
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


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
            logger.info("Dados locais não encontrados, buscando no OpenStreetMap...")
            rivers = self._fetch_rivers_from_osm(search_area)

        if rivers is None or rivers.empty:
            logger.warning("Nenhum curso d'água encontrado na área")
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
            logger.info("Lagos locais não encontrados, buscando no OpenStreetMap...")
            lakes = self._fetch_lakes_from_osm(polygon)

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

    def _fetch_rivers_from_osm(
        self,
        search_area: Polygon
    ) -> Optional[gpd.GeoDataFrame]:
        """
        Busca rios no OpenStreetMap via API Overpass.

        Args:
            search_area: Polígono da área de busca

        Returns:
            GeoDataFrame com rios ou None
        """
        bounds = search_area.bounds  # (minx, miny, maxx, maxy)
        bbox = f"{bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]}"  # lat,lon,lat,lon

        # Query Overpass para waterways
        query = f"""
        [out:json][timeout:60];
        (
          way["waterway"="river"]({bbox});
          way["waterway"="stream"]({bbox});
          way["waterway"="canal"]({bbox});
          way["waterway"="ditch"]({bbox});
          way["waterway"="drain"]({bbox});
        );
        out body;
        >;
        out skel qt;
        """

        try:
            logger.info("Consultando OpenStreetMap (Overpass API)...")
            response = requests.post(
                OVERPASS_URL,
                data={'data': query},
                timeout=90
            )
            response.raise_for_status()
            data = response.json()

            rivers = self._parse_osm_ways(data, search_area)

            if rivers:
                gdf = gpd.GeoDataFrame(rivers, crs=DEFAULT_CRS)
                logger.info(f"Encontrados {len(gdf)} cursos d'água no OSM")
                return gdf

        except requests.exceptions.Timeout:
            logger.warning("Timeout ao consultar OpenStreetMap")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Erro ao consultar OpenStreetMap: {e}")
        except Exception as e:
            logger.error(f"Erro ao processar dados OSM: {e}")

        return None

    def _fetch_lakes_from_osm(
        self,
        polygon: Polygon
    ) -> Optional[gpd.GeoDataFrame]:
        """
        Busca lagos no OpenStreetMap via API Overpass.

        Args:
            polygon: Polígono da área de busca

        Returns:
            GeoDataFrame com lagos ou None
        """
        bounds = polygon.bounds
        bbox = f"{bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]}"

        # Query Overpass para water bodies
        query = f"""
        [out:json][timeout:60];
        (
          way["natural"="water"]({bbox});
          relation["natural"="water"]({bbox});
          way["water"="lake"]({bbox});
          way["water"="pond"]({bbox});
          way["water"="reservoir"]({bbox});
        );
        out body;
        >;
        out skel qt;
        """

        try:
            logger.info("Consultando lagos no OpenStreetMap...")
            response = requests.post(
                OVERPASS_URL,
                data={'data': query},
                timeout=90
            )
            response.raise_for_status()
            data = response.json()

            lakes = self._parse_osm_areas(data, polygon)

            if lakes:
                gdf = gpd.GeoDataFrame(lakes, crs=DEFAULT_CRS)
                logger.info(f"Encontrados {len(gdf)} lagos no OSM")
                return gdf

        except requests.exceptions.Timeout:
            logger.warning("Timeout ao consultar OpenStreetMap para lagos")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Erro ao consultar OpenStreetMap: {e}")
        except Exception as e:
            logger.error(f"Erro ao processar dados OSM lagos: {e}")

        return None

    def _parse_osm_ways(self, data: dict, search_area: Polygon) -> list:
        """
        Converte dados OSM (ways) para lista de geometrias.

        Args:
            data: Resposta JSON da API Overpass
            search_area: Área de busca para filtrar

        Returns:
            Lista de dicts com geometry e atributos
        """
        # Criar índice de nodes
        nodes = {}
        for element in data.get('elements', []):
            if element['type'] == 'node':
                nodes[element['id']] = (element['lon'], element['lat'])

        # Processar ways
        rivers = []
        for element in data.get('elements', []):
            if element['type'] == 'way':
                coords = []
                for node_id in element.get('nodes', []):
                    if node_id in nodes:
                        coords.append(nodes[node_id])

                if len(coords) >= 2:
                    line = LineString(coords)

                    # Filtrar apenas linhas que intersectam a área
                    if line.intersects(search_area):
                        tags = element.get('tags', {})
                        nome = tags.get('name', '')
                        waterway_type = tags.get('waterway', '')

                        # Estimar largura baseado no tipo
                        if waterway_type == 'river':
                            largura = 15.0
                        elif waterway_type == 'stream':
                            largura = 5.0
                        elif waterway_type == 'canal':
                            largura = 8.0
                        else:
                            largura = 3.0

                        rivers.append({
                            'geometry': line,
                            'nome': nome,
                            'tipo': waterway_type,
                            'largura_m': largura,
                            'source': 'OSM'
                        })

        return rivers

    def _parse_osm_areas(self, data: dict, polygon: Polygon) -> list:
        """
        Converte dados OSM (areas) para lista de geometrias.

        Args:
            data: Resposta JSON da API Overpass
            polygon: Área de busca para filtrar

        Returns:
            Lista de dicts com geometry e atributos
        """
        # Criar índice de nodes
        nodes = {}
        for element in data.get('elements', []):
            if element['type'] == 'node':
                nodes[element['id']] = (element['lon'], element['lat'])

        # Processar ways como polígonos
        lakes = []
        for element in data.get('elements', []):
            if element['type'] == 'way':
                coords = []
                for node_id in element.get('nodes', []):
                    if node_id in nodes:
                        coords.append(nodes[node_id])

                # Precisa de pelo menos 4 pontos para formar um polígono
                if len(coords) >= 4:
                    # Fechar o polígono se necessário
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])

                    try:
                        poly = Polygon(coords)
                        if poly.is_valid and poly.intersects(polygon):
                            tags = element.get('tags', {})
                            nome = tags.get('name', '')

                            lakes.append({
                                'geometry': poly,
                                'nome': nome,
                                'tipo': tags.get('water', tags.get('natural', 'water')),
                                'source': 'OSM'
                            })
                    except Exception:
                        pass  # Ignorar polígonos inválidos

        return lakes

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
