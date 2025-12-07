"""
Configurações e constantes do AUTO CAR Generator.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================
# PATHS
# ============================================
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / 'data_cache'
OUTPUT_DIR = PROJECT_ROOT / 'output'
TOPODATA_DIR = DATA_DIR / 'topodata'
IBGE_DIR = DATA_DIR / 'ibge'
MAPBIOMAS_DIR = DATA_DIR / 'mapbiomas'

# ============================================
# SISTEMA DE REFERÊNCIA DE COORDENADAS
# ============================================
DEFAULT_CRS = 'EPSG:4326'  # WGS84 - Obrigatório SICAR
UTM_CRS_SP = 'EPSG:31983'  # SIRGAS 2000 / UTM 23S (para cálculos em metros)

# ============================================
# PARÂMETROS LEGAIS (LEI 12.651/2012)
# ============================================
# APP - Faixas marginais por largura do rio (metros)
APP_MARGEM = {
    10: 30,      # Rio ≤10m → 30m cada lado
    50: 50,      # Rio 10-50m → 50m
    200: 100,    # Rio 50-200m → 100m
    600: 200,    # Rio 200-600m → 200m
    float('inf'): 500  # Rio >600m → 500m
}

APP_NASCENTE_RAIO_M = 50           # Raio APP nascente
APP_LAGO_PEQUENO_M = 50            # Lagos ≤20ha
APP_LAGO_GRANDE_M = 100            # Lagos >20ha
APP_DECLIVIDADE_GRAUS = 45         # Encostas >45° = APP
APP_ALTITUDE_M = 1800              # Acima de 1800m = APP

# Reserva Legal
RESERVA_LEGAL_PERCENT = {
    'MATA_ATLANTICA': 0.20,
    'CERRADO': 0.20,
    'AMAZONIA': 0.80,
}

# Uso Restrito
USO_RESTRITO_DECLIVIDADE_MIN = 25  # graus
USO_RESTRITO_DECLIVIDADE_MAX = 45  # graus

# Área mínima
MIN_PROPERTY_AREA_M2 = 2500  # ~0.25 hectare

# ============================================
# PRECISÃO DE COORDENADAS
# ============================================
MIN_COORDINATE_DECIMALS = 8  # SICAR exige alta precisão

# ============================================
# ATRIBUTOS OBRIGATÓRIOS POR CAMADA SICAR-SP
# Nomes das camadas seguem padrão SICAR-SP
# ============================================
SICAR_ATTRIBUTES = {
    'AREA_IMOVEL': {
        'cod_imovel': str,
        'nom_imovel': str,
        'mod_fiscal': float,
        'num_area': float,
        'cod_estado': str,
        'cod_municipio': str,
    },
    'APP': {
        'cod_app': str,
        'tip_app': str,
        'des_condic': str,
        'num_area': float,
    },
    'RESERVA_LEGAL': {
        'cod_rl': str,
        'des_condic': str,
        'num_area': float,
        'ind_averbada': str,
        'num_matricula': str,
    },
    'VEGETACAO_NATIVA': {
        'cod_veg': str,
        'des_estagio': str,
        'num_area': float,
    },
    'USO_CONSOLIDADO': {
        'cod_uso': str,
        'des_uso': str,
        'num_area': float,
    },
    'USO_RESTRITO': {
        'cod_ur': str,
        'des_tipo': str,
        'num_area': float,
    },
    'HIDROGRAFIA': {
        'cod_hidro': str,
        'tip_hidro': str,
        'nom_hidro': str,
        'num_largura': float,
    },
    'SERVIDAO_ADMINISTRATIVA': {
        'cod_serv': str,
        'tip_serv': str,
        'num_area': float,
    }
}

# ============================================
# CÓDIGOS MAPBIOMAS (Coleção 8)
# ============================================
MAPBIOMAS_VEGETACAO_NATIVA = [3, 4, 5, 6, 49, 11, 12, 32, 29, 50, 13]
MAPBIOMAS_AREA_CONSOLIDADA = [14, 15, 9, 21, 24, 30, 25]
MAPBIOMAS_AGUA = [33, 31]

# ============================================
# APIS E ENDPOINTS
# ============================================
GOOGLE_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
INCRA_WFS = 'http://acervofundiario.incra.gov.br/geoserver/wfs'
IBGE_WFS = 'https://geoservicos.ibge.gov.br/geoserver/wfs'

# ============================================
# RATE LIMITING
# ============================================
REQUESTS_PER_SECOND = 5
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
