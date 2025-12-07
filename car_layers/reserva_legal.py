"""
Cálculo e sugestão de localização da Reserva Legal.
"""
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
import logging
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import RESERVA_LEGAL_PERCENT, UTM_CRS_SP, DEFAULT_CRS

logger = logging.getLogger(__name__)


class ReservaLegalCalculator:
    """Calculadora de Reserva Legal."""

    def __init__(self, perimeter: Polygon, bioma: str = 'MATA_ATLANTICA'):
        """
        Args:
            perimeter: Polígono do perímetro do imóvel
            bioma: Bioma do imóvel (MATA_ATLANTICA, CERRADO, AMAZONIA)
        """
        self.perimeter = perimeter
        self.bioma = bioma
        self.percent = RESERVA_LEGAL_PERCENT.get(bioma, 0.20)
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

    def calculate_required_area(self) -> float:
        """
        Calcula área de RL necessária em hectares.

        Returns:
            Área necessária em hectares
        """
        total_area_ha = self.perimeter_utm.area / 10000
        required_ha = total_area_ha * self.percent

        logger.info(f"Área total: {total_area_ha:.2f} ha")
        logger.info(f"RL necessária ({self.percent*100}%): {required_ha:.2f} ha")

        return required_ha

    def suggest_location(
        self,
        app_gdf: gpd.GeoDataFrame = None,
        vegetacao_nativa_gdf: gpd.GeoDataFrame = None
    ) -> gpd.GeoDataFrame:
        """
        Sugere localização da Reserva Legal.

        Prioridades (Lei 12.651/2012):
        1. Área com vegetação nativa existente
        2. Área contígua à APP
        3. Área de menor aptidão agrícola

        Args:
            app_gdf: GeoDataFrame com APPs calculadas
            vegetacao_nativa_gdf: GeoDataFrame com vegetação nativa existente

        Returns:
            GeoDataFrame com sugestão de RL
        """
        logger.info("Sugerindo localização de Reserva Legal")

        required_ha = self.calculate_required_area()
        required_m2 = required_ha * 10000

        # Área disponível = Perímetro - APP
        disponivel = self._calculate_available_area(app_gdf)

        # Determinar geometria da RL
        rl_geometry = self._select_rl_area(
            disponivel=disponivel,
            required_m2=required_m2,
            app_gdf=app_gdf,
            vegetacao_nativa_gdf=vegetacao_nativa_gdf
        )

        # Converter para WGS84
        rl_wgs84 = self._utm_to_wgs84(rl_geometry)
        area_ha = rl_geometry.area / 10000

        # Determinar condição
        condic = 'PROPOSTA' if area_ha >= required_ha * 0.95 else 'PROPOSTA_INCOMPLETA'

        gdf = gpd.GeoDataFrame([{
            'geometry': rl_wgs84,
            'cod_rl': 'RL_001',
            'des_condic': condic,
            'num_area': round(area_ha, 4),
            'ind_averbada': 'N',
            'num_matricula': '',
            'pct_exigido': self.percent * 100,
            'area_exigida_ha': round(required_ha, 4)
        }], crs=DEFAULT_CRS)

        logger.info(f"RL sugerida: {area_ha:.2f} ha (necessário: {required_ha:.2f} ha)")

        return gdf

    def _calculate_available_area(
        self,
        app_gdf: gpd.GeoDataFrame = None
    ) -> Polygon:
        """Calcula área disponível (perímetro - APP)."""
        disponivel = self.perimeter_utm

        if app_gdf is not None and not app_gdf.empty:
            app_utm = app_gdf.to_crs(UTM_CRS_SP)
            app_union = unary_union(app_utm.geometry)
            disponivel = self.perimeter_utm.difference(app_union)

            # Garantir que é Polygon
            if isinstance(disponivel, MultiPolygon):
                disponivel = max(disponivel.geoms, key=lambda p: p.area)

        return disponivel

    def _select_rl_area(
        self,
        disponivel: Polygon,
        required_m2: float,
        app_gdf: gpd.GeoDataFrame = None,
        vegetacao_nativa_gdf: gpd.GeoDataFrame = None
    ) -> Polygon:
        """
        Seleciona área para RL baseado em prioridades legais.
        """
        # Prioridade 1: Vegetação nativa existente
        if vegetacao_nativa_gdf is not None and not vegetacao_nativa_gdf.empty:
            veg_utm = vegetacao_nativa_gdf.to_crs(UTM_CRS_SP)
            veg_union = unary_union(veg_utm.geometry)

            # Interseção com área disponível
            veg_disponivel = veg_union.intersection(disponivel)

            if not veg_disponivel.is_empty:
                veg_area = veg_disponivel.area

                if veg_area >= required_m2:
                    # Vegetação nativa suficiente
                    logger.info("Vegetação nativa existente é suficiente para RL")
                    return self._extract_area(veg_disponivel, required_m2)
                else:
                    # Usar toda vegetação + complementar
                    logger.info("Complementando RL com área contígua à APP")
                    complemento = self._select_contigua_app(
                        disponivel=disponivel.difference(veg_disponivel),
                        app_gdf=app_gdf,
                        required_m2=required_m2 - veg_area
                    )
                    return unary_union([veg_disponivel, complemento])

        # Prioridade 2: Área contígua à APP
        return self._select_contigua_app(disponivel, app_gdf, required_m2)

    def _select_contigua_app(
        self,
        disponivel: Polygon,
        app_gdf: gpd.GeoDataFrame,
        required_m2: float
    ) -> Polygon:
        """Seleciona área contígua à APP para RL."""
        if app_gdf is None or app_gdf.empty:
            # Sem APP, usar qualquer área disponível
            return self._extract_area(disponivel, required_m2)

        app_utm = app_gdf.to_crs(UTM_CRS_SP)
        app_union = unary_union(app_utm.geometry)

        # Criar buffer progressivo até atingir área necessária
        for buffer_size in [50, 100, 200, 500, 1000, 2000]:
            app_buffer = app_union.buffer(buffer_size)
            area_contigua = app_buffer.intersection(disponivel)

            if area_contigua.area >= required_m2:
                return self._extract_area(area_contigua, required_m2)

        # Se não encontrou área suficiente, retornar toda área disponível
        logger.warning("Não foi possível encontrar área suficiente contígua à APP")
        return disponivel

    def _extract_area(self, geometry: Polygon, target_m2: float) -> Polygon:
        """
        Extrai área específica de um polígono.

        Se a geometria for maior que o necessário, tenta extrair
        apenas a porção necessária mantendo a forma compacta.
        """
        if geometry.area <= target_m2:
            return geometry

        # Para simplificar, usar a geometria completa se for maior
        # Em implementação mais sofisticada, poderia usar algoritmo
        # de particionamento para extrair área exata
        return geometry

    def _utm_to_wgs84(self, geometry) -> Polygon:
        """Converte geometria de UTM para WGS84."""
        if isinstance(geometry, MultiPolygon):
            geometry = max(geometry.geoms, key=lambda p: p.area)

        gdf = gpd.GeoDataFrame({'geometry': [geometry]}, crs=UTM_CRS_SP)
        return gdf.to_crs(DEFAULT_CRS).geometry.iloc[0]
