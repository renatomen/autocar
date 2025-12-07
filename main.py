#!/usr/bin/env python3
"""
AUTO CAR Generator - Geração automática de arquivos para SICAR-SP.

Uso:
    python main.py <arquivo.kml> [--nome <nome_imovel>] [--bioma <bioma>]

Exemplo:
    python main.py assets/Mursa-CAR.kml --nome "Fazenda Mursa" --bioma MATA_ATLANTICA
"""
import argparse
import logging
import sys
from pathlib import Path

import geopandas as gpd

from config import OUTPUT_DIR, DEFAULT_CRS, UTM_CRS_SP
from geospatial.kml_parser import parse_kml, parse_kml_completo
from geospatial.geometry_validator import GeometryValidator
from geospatial.area_calculator import get_area_summary
from data_sources.hydrology import HydrologyCollector, NascenteIdentifier
from car_layers.app_calculator import APPCalculator
from car_layers.reserva_legal import ReservaLegalCalculator
from sicar_formatter.shapefile_builder import build_sicar_package

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='AUTO CAR Generator - Geração automática de arquivos para SICAR-SP'
    )
    parser.add_argument('kml_file', help='Arquivo KML com o perímetro do imóvel')
    parser.add_argument('--nome', '-n', default='imovel', help='Nome do imóvel')
    parser.add_argument('--bioma', '-b', default='MATA_ATLANTICA',
                       choices=['MATA_ATLANTICA', 'CERRADO', 'AMAZONIA'],
                       help='Bioma do imóvel')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Modo verbose')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        run_pipeline(args.kml_file, args.nome, args.bioma)
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def run_pipeline(kml_path: str, nome: str, bioma: str):
    """
    Executa o pipeline completo de geração de arquivos CAR.
    Detecta automaticamente se o KML contém hidrografia local.
    """
    logger.info("=" * 60)
    logger.info("AUTO CAR Generator - Iniciando processamento")
    logger.info("=" * 60)

    # ===========================================
    # FASE 1: Leitura e validação do KML
    # ===========================================
    logger.info("FASE 1: Leitura do KML de entrada")

    # Tentar ler como KML completo (com hidrografia e RL)
    try:
        kml_data = parse_kml_completo(kml_path)
        perimeter = kml_data['perimetro']
        corregos_local = kml_data['corregos']
        nascentes_local = kml_data['nascentes']
        reserva_legal_manual = kml_data['reserva_legal']

        usar_hidro_local = not corregos_local.empty or not nascentes_local.empty
        usar_rl_manual = reserva_legal_manual is not None

        if usar_hidro_local:
            logger.info("Hidrografia local detectada no KML")
        if usar_rl_manual:
            logger.info("Reserva Legal manual detectada no KML")

    except Exception as e:
        logger.warning(f"Erro ao ler KML completo, usando parser simples: {e}")
        gdf_input, perimeter = parse_kml(kml_path)
        corregos_local = gpd.GeoDataFrame({'geometry': []}, crs=DEFAULT_CRS)
        nascentes_local = gpd.GeoDataFrame({'geometry': []}, crs=DEFAULT_CRS)
        reserva_legal_manual = None
        usar_hidro_local = False
        usar_rl_manual = False

    # Validar geometria
    validator = GeometryValidator()
    perimeter, validation_errors = validator.validate(perimeter)

    if validation_errors:
        for error in validation_errors:
            logger.warning(f"Validação: {error}")

    # Calcular área total
    area_summary = get_area_summary(perimeter)
    area_total_ha = area_summary['area_ha']
    logger.info(f"Área total do imóvel: {area_total_ha:.2f} hectares")
    logger.info(f"Módulos fiscais: {area_summary['modulos_fiscais']:.2f}")

    # Criar GeoDataFrame do perímetro
    perimetro_gdf = gpd.GeoDataFrame([{
        'geometry': perimeter,
        'cod_imovel': '',
        'nom_imovel': nome,
        'mod_fiscal': area_summary['modulos_fiscais'],
        'num_area': round(area_total_ha, 4),
        'cod_estado': 'SP',
        'cod_municipio': '',
    }], crs=DEFAULT_CRS)

    # ===========================================
    # FASE 2: Coleta de dados de hidrografia
    # ===========================================
    logger.info("FASE 2: Coleta de dados de hidrografia")

    if usar_hidro_local:
        # Usar hidrografia do KML
        logger.info(f"Usando hidrografia local: {len(corregos_local)} córregos, {len(nascentes_local)} nascentes")
        hidrografia_gdf = corregos_local
        nascentes_gdf = nascentes_local
        lagos_gdf = gpd.GeoDataFrame({'geometry': [], 'nome': [], 'area_ha': []}, crs=DEFAULT_CRS)
    else:
        # Buscar hidrografia externa (OSM)
        logger.info("Buscando hidrografia externa...")
        hydro_collector = HydrologyCollector()
        hidrografia_gdf = hydro_collector.get_rivers_in_area(perimeter, buffer_km=2)
        lagos_gdf = hydro_collector.get_lakes_in_area(perimeter)

        # Identificar nascentes a partir dos rios
        logger.info("Identificando nascentes...")
        nascente_identifier = NascenteIdentifier()
        nascentes_gdf = nascente_identifier.identify_from_rivers(perimeter, hidrografia_gdf)

    # ===========================================
    # FASE 3: Cálculo das camadas CAR
    # ===========================================
    logger.info("FASE 3: Cálculo das camadas CAR")

    # APP
    logger.info("Calculando APPs...")
    app_calc = APPCalculator(perimeter)
    app_gdf = app_calc.calculate_all_apps(
        rivers_gdf=hidrografia_gdf if not hidrografia_gdf.empty else None,
        nascentes_gdf=nascentes_gdf if not nascentes_gdf.empty else None,
        lagos_gdf=lagos_gdf if not lagos_gdf.empty else None
    )

    # Reserva Legal
    if usar_rl_manual:
        logger.info("Usando Reserva Legal definida manualmente no KML")
        # Calcular área da RL manual
        rl_gdf_temp = gpd.GeoDataFrame({'geometry': [reserva_legal_manual]}, crs=DEFAULT_CRS)
        rl_utm = rl_gdf_temp.to_crs(UTM_CRS_SP)
        rl_area_ha = rl_utm.geometry.iloc[0].area / 10000

        reserva_legal_gdf = gpd.GeoDataFrame([{
            'geometry': reserva_legal_manual,
            'cod_rl': 'RL_001',
            'ind_averbada': 'NAO',
            'num_matricula': '',
            'num_area': round(rl_area_ha, 4),
            'pct_exigido': 20.0,
            'area_exigida_ha': round(area_total_ha * 0.20, 4)
        }], crs=DEFAULT_CRS)

        logger.info(f"Reserva Legal manual: {rl_area_ha:.2f} ha ({rl_area_ha/area_total_ha*100:.1f}%)")
    else:
        logger.info("Calculando Reserva Legal sugerida...")
        rl_calc = ReservaLegalCalculator(perimeter, bioma)
        reserva_legal_gdf = rl_calc.suggest_location(
            app_gdf=app_gdf if not app_gdf.empty else None
        )

    # ===========================================
    # FASE 4: Geração dos arquivos de saída
    # ===========================================
    logger.info("FASE 4: Geração dos arquivos de saída")

    # Shapefiles + ZIP
    logger.info("Gerando Shapefiles...")
    zip_path = build_sicar_package(
        output_name=nome,
        perimetro_gdf=perimetro_gdf,
        app_gdf=app_gdf if not app_gdf.empty else None,
        reserva_legal_gdf=reserva_legal_gdf,
        hidrografia_gdf=hidrografia_gdf if not hidrografia_gdf.empty else None
    )

    # ===========================================
    # RESUMO FINAL
    # ===========================================
    logger.info("=" * 60)
    logger.info("PROCESSAMENTO CONCLUÍDO")
    logger.info("=" * 60)
    logger.info(f"Arquivos gerados em: {OUTPUT_DIR}/{nome}/")
    logger.info(f"  - ZIP para SICAR: {zip_path}")
    logger.info("")
    logger.info("RESUMO DO IMÓVEL:")
    logger.info(f"  - Nome: {nome}")
    logger.info(f"  - Área total: {area_total_ha:.2f} ha")
    logger.info(f"  - Módulos fiscais: {area_summary['modulos_fiscais']:.2f}")

    if app_gdf is not None and not app_gdf.empty:
        app_area = app_gdf['num_area'].sum()
        logger.info(f"  - APP total: {app_area:.2f} ha ({app_area/area_total_ha*100:.1f}%)")

    if reserva_legal_gdf is not None and not reserva_legal_gdf.empty:
        rl_area = reserva_legal_gdf['num_area'].sum()
        logger.info(f"  - Reserva Legal: {rl_area:.2f} ha ({rl_area/area_total_ha*100:.1f}%)")

    logger.info("")
    logger.info("PRÓXIMOS PASSOS:")
    logger.info("1. Revisar os arquivos no QGIS")
    logger.info("2. Adicionar dados de hidrografia local se necessário")
    logger.info("3. Ajustar manualmente se necessário")
    logger.info("4. Fazer upload do ZIP no SICAR-SP")
    logger.info("=" * 60)

    return zip_path


if __name__ == '__main__':
    main()
