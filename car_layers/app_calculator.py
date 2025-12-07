"""
Cálculo automático de Áreas de Preservação Permanente (APP)
conforme Lei 12.651/2012 (Código Florestal).
"""
import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon, Point, LineString, MultiPolygon
from shapely.ops import unary_union
import logging
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    APP_MARGEM, APP_NASCENTE_RAIO_M, APP_LAGO_PEQUENO_M,
    APP_LAGO_GRANDE_M, APP_DECLIVIDADE_GRAUS, UTM_CRS_SP,
    DEFAULT_CRS
)

logger = logging.getLogger(__name__)


class APPCalculator:
    """Calculadora de APP para imóvel rural."""

    def __init__(self, perimeter: Polygon, dem_path: str = None):
        """
        Args:
            perimeter: Polígono do perímetro do imóvel
            dem_path: Caminho para o DEM (TOPODATA) - opcional
        """
        self.perimeter = perimeter
        self.dem_path = dem_path
        self._perimeter_utm = None

    @property
    def perimeter_utm(self):
        """Perímetro em UTM para cálculos em metros."""
        if self._perimeter_utm is None:
            gdf = gpd.GeoDataFrame(
                {'geometry': [self.perimeter]},
                crs=DEFAULT_CRS
            )
            self._perimeter_utm = gdf.to_crs(UTM_CRS_SP).geometry.iloc[0]
        return self._perimeter_utm

    def calculate_all_apps(
        self,
        rivers_gdf: gpd.GeoDataFrame = None,
        nascentes_gdf: gpd.GeoDataFrame = None,
        lagos_gdf: gpd.GeoDataFrame = None
    ) -> gpd.GeoDataFrame:
        """
        Calcula todas as APPs do imóvel.

        Args:
            rivers_gdf: GeoDataFrame com rios
            nascentes_gdf: GeoDataFrame com nascentes
            lagos_gdf: GeoDataFrame com lagos

        Returns:
            GeoDataFrame com todas as APPs calculadas
        """
        logger.info("Iniciando cálculo de APPs")

        all_apps = []

        # 1. APP de margem de rio
        if rivers_gdf is not None and not rivers_gdf.empty:
            app_margem = self.calculate_app_margem(rivers_gdf)
            if not app_margem.empty:
                all_apps.append(app_margem)

        # 2. APP de nascente
        if nascentes_gdf is not None and not nascentes_gdf.empty:
            app_nascente = self.calculate_app_nascente(nascentes_gdf)
            if not app_nascente.empty:
                all_apps.append(app_nascente)

        # 3. APP de lago
        if lagos_gdf is not None and not lagos_gdf.empty:
            app_lago = self.calculate_app_lago(lagos_gdf)
            if not app_lago.empty:
                all_apps.append(app_lago)

        # 4. APP de declividade (se DEM disponível)
        if self.dem_path:
            app_decliv = self.calculate_app_declividade()
            if app_decliv is not None and not app_decliv.empty:
                all_apps.append(app_decliv)

        # Consolidar todas as APPs
        if all_apps:
            result = gpd.GeoDataFrame(
                pd.concat(all_apps, ignore_index=True),
                crs=DEFAULT_CRS
            )
            logger.info(f"Total de APPs calculadas: {len(result)} polígonos")
            return result

        # Retornar GeoDataFrame vazio com schema correto
        return self._empty_app_gdf()

    def calculate_app_margem(
        self,
        rivers_gdf: gpd.GeoDataFrame
    ) -> gpd.GeoDataFrame:
        """Calcula APP de margem de curso d'água."""
        logger.info(f"Calculando APP de margem para {len(rivers_gdf)} cursos d'água")

        apps = []
        rivers_utm = rivers_gdf.to_crs(UTM_CRS_SP)

        for idx, row in rivers_utm.iterrows():
            river = row.geometry
            largura = row.get('largura_m', 5) if hasattr(row, 'get') else row['largura_m'] if 'largura_m' in rivers_gdf.columns else 5

            # Determinar faixa de APP baseado na largura
            buffer_m = self._get_buffer_by_width(largura)

            # Criar buffer ao redor do rio (APP)
            app_buffer = river.buffer(buffer_m)

            # Verificar se o buffer do rio (APP) intersecta o perímetro
            # A APP conta mesmo que o rio esteja fora, desde que a faixa de proteção entre no imóvel
            app_dentro = app_buffer.intersection(self.perimeter_utm)

            # Log para debug
            dist_to_perimeter = river.distance(self.perimeter_utm)
            logger.debug(f"Rio {idx}: largura={largura}m, buffer={buffer_m}m, dist_ao_perimetro={dist_to_perimeter:.1f}m, intersecção_vazia={app_dentro.is_empty}")

            if not app_dentro.is_empty:
                app_wgs84 = self._utm_to_wgs84(app_dentro)
                area_ha = app_dentro.area / 10000

                apps.append({
                    'geometry': app_wgs84,
                    'cod_app': f'APP_MARGEM_{idx+1:03d}',
                    'tip_app': 'MARGEM_CURSO_DAGUA',
                    'des_condic': 'A_CLASSIFICAR',
                    'num_area': round(area_ha, 4),
                    'buffer_m': buffer_m,
                    'largura_rio_m': largura
                })

        if apps:
            logger.info(f"APPs de margem criadas: {len(apps)}")
            return gpd.GeoDataFrame(apps, crs=DEFAULT_CRS)

        # Se não criou APPs, informar a distância mínima encontrada
        if rivers_utm is not None and len(rivers_utm) > 0:
            min_dist = min(r.geometry.distance(self.perimeter_utm) for _, r in rivers_utm.iterrows())
            logger.info(f"Nenhuma APP de margem criada - curso d'água mais próximo está a {min_dist:.0f}m do perímetro")
        else:
            logger.info("Nenhuma APP de margem criada - nenhum curso d'água encontrado")

        return self._empty_app_gdf()

    def calculate_app_nascente(
        self,
        nascentes_gdf: gpd.GeoDataFrame
    ) -> gpd.GeoDataFrame:
        """Calcula APP de nascente (50m de raio)."""
        logger.info("Calculando APP de nascente")

        apps = []
        nascentes_utm = nascentes_gdf.to_crs(UTM_CRS_SP)

        for idx, row in nascentes_utm.iterrows():
            nascente = row.geometry

            # Buffer de 50m
            app_buffer = nascente.buffer(APP_NASCENTE_RAIO_M)

            # Intersectar com perímetro
            app_dentro = app_buffer.intersection(self.perimeter_utm)

            if not app_dentro.is_empty:
                app_wgs84 = self._utm_to_wgs84(app_dentro)
                area_ha = app_dentro.area / 10000

                apps.append({
                    'geometry': app_wgs84,
                    'cod_app': f'APP_NASC_{idx+1:03d}',
                    'tip_app': 'NASCENTE',
                    'des_condic': 'A_CLASSIFICAR',
                    'num_area': round(area_ha, 4),
                    'buffer_m': APP_NASCENTE_RAIO_M
                })

        if apps:
            return gpd.GeoDataFrame(apps, crs=DEFAULT_CRS)

        return self._empty_app_gdf()

    def calculate_app_lago(
        self,
        lagos_gdf: gpd.GeoDataFrame
    ) -> gpd.GeoDataFrame:
        """Calcula APP de lagos e lagoas naturais."""
        logger.info("Calculando APP de lagos")

        apps = []
        lagos_utm = lagos_gdf.to_crs(UTM_CRS_SP)

        for idx, row in lagos_utm.iterrows():
            lago = row.geometry
            area_ha = row.get('area_ha', lago.area / 10000)

            # Determinar buffer baseado no tamanho
            buffer_m = APP_LAGO_GRANDE_M if area_ha > 20 else APP_LAGO_PEQUENO_M

            # Buffer a partir da borda do lago (excluindo o próprio lago)
            app_buffer = lago.buffer(buffer_m).difference(lago)

            # Intersectar com perímetro
            app_dentro = app_buffer.intersection(self.perimeter_utm)

            if not app_dentro.is_empty:
                app_wgs84 = self._utm_to_wgs84(app_dentro)
                app_area_ha = app_dentro.area / 10000

                apps.append({
                    'geometry': app_wgs84,
                    'cod_app': f'APP_LAGO_{idx+1:03d}',
                    'tip_app': 'LAGO_LAGOA',
                    'des_condic': 'A_CLASSIFICAR',
                    'num_area': round(app_area_ha, 4),
                    'buffer_m': buffer_m,
                    'area_lago_ha': area_ha
                })

        if apps:
            return gpd.GeoDataFrame(apps, crs=DEFAULT_CRS)

        return self._empty_app_gdf()

    def calculate_app_declividade(self) -> Optional[gpd.GeoDataFrame]:
        """Calcula APP de declividade >45°."""
        if not self.dem_path:
            logger.warning("DEM não fornecido, pulando APP de declividade")
            return None

        logger.info("Calculando APP de declividade")

        try:
            import rasterio
            from rasterio.mask import mask as rio_mask

            with rasterio.open(self.dem_path) as src:
                # Recortar DEM pelo perímetro
                perimeter_geojson = [self.perimeter.__geo_interface__]
                dem_clip, transform = rio_mask(
                    src, perimeter_geojson, crop=True
                )
                dem_data = dem_clip[0]

                # Calcular declividade (slope)
                dy, dx = np.gradient(dem_data, src.res[1], src.res[0])
                slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
                slope_deg = np.degrees(slope_rad)

                # Criar máscara de áreas >45°
                steep_mask = slope_deg > APP_DECLIVIDADE_GRAUS

                if np.any(steep_mask):
                    from rasterio.features import shapes

                    steep_shapes = list(shapes(
                        steep_mask.astype(np.uint8),
                        mask=steep_mask,
                        transform=transform
                    ))

                    apps = []
                    for i, (geom, value) in enumerate(steep_shapes):
                        if value == 1:
                            poly = Polygon(geom['coordinates'][0])
                            poly_wgs84 = gpd.GeoSeries(
                                [poly], crs=src.crs
                            ).to_crs(DEFAULT_CRS).iloc[0]

                            # Intersectar com perímetro
                            app_dentro = poly_wgs84.intersection(self.perimeter)

                            if not app_dentro.is_empty:
                                area_ha = gpd.GeoSeries(
                                    [app_dentro], crs=DEFAULT_CRS
                                ).to_crs(UTM_CRS_SP).iloc[0].area / 10000

                                apps.append({
                                    'geometry': app_dentro,
                                    'cod_app': f'APP_DECLIV_{i+1:03d}',
                                    'tip_app': 'DECLIVIDADE_SUPERIOR_45',
                                    'des_condic': 'A_CLASSIFICAR',
                                    'num_area': round(area_ha, 4)
                                })

                    if apps:
                        return gpd.GeoDataFrame(apps, crs=DEFAULT_CRS)

                logger.info("Nenhuma área com declividade >45° encontrada")

        except ImportError:
            logger.warning("rasterio não instalado, pulando APP de declividade")
        except Exception as e:
            logger.error(f"Erro ao calcular APP de declividade: {e}")

        return None

    def _get_buffer_by_width(self, width_m: float) -> float:
        """Retorna largura do buffer APP baseado na largura do rio."""
        for max_width, buffer in sorted(APP_MARGEM.items()):
            if width_m <= max_width:
                return buffer
        return 500  # Máximo para rios >600m

    def _utm_to_wgs84(self, geometry):
        """Converte geometria de UTM para WGS84."""
        gdf = gpd.GeoDataFrame({'geometry': [geometry]}, crs=UTM_CRS_SP)
        return gdf.to_crs(DEFAULT_CRS).geometry.iloc[0]

    def _empty_app_gdf(self) -> gpd.GeoDataFrame:
        """Retorna GeoDataFrame vazio com schema correto."""
        return gpd.GeoDataFrame({
            'geometry': [],
            'cod_app': [],
            'tip_app': [],
            'des_condic': [],
            'num_area': []
        }, crs=DEFAULT_CRS)


# Importação necessária para concatenação
import pandas as pd
