# AUTO CAR Generator

Geração automática de arquivos para cadastro no SICAR-SP (Cadastro Ambiental Rural).

## Funcionalidades

- Leitura de KML com perímetro do imóvel
- Cálculo automático de APP (Área de Preservação Permanente)
  - Margem de curso d'água (30-500m conforme largura)
  - Nascentes (50m de raio)
  - Lagos e lagoas (50-100m)
- Cálculo de Reserva Legal (20% para Mata Atlântica)
- Geração de Shapefiles compatíveis com SICAR
- Validação de geometrias e coordenadas

## Requisitos

- Python 3.10+
- Dependências: geopandas, fiona, shapely, pyproj, numpy, pandas

## Instalação

### Windows
```batch
setup.bat
```

### Linux/Mac
```bash
chmod +x setup.sh
./setup.sh
```

### Manual
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Uso

```bash
python main.py <arquivo.kml> --nome <nome_imovel> [--bioma <bioma>]
```

### Exemplo
```bash
python main.py "assets/Mursa - CAR.kml" --nome "Fazenda_Mursa" --bioma MATA_ATLANTICA
```

### Parâmetros
- `arquivo.kml`: Arquivo KML com o perímetro do imóvel (obrigatório)
- `--nome, -n`: Nome do imóvel (default: "imovel")
- `--bioma, -b`: Bioma do imóvel (MATA_ATLANTICA, CERRADO, AMAZONIA)
- `--verbose, -v`: Modo verbose para debug

## Saída

Os arquivos são gerados em `output/<nome_imovel>/`:

```
output/
└── Fazenda_Mursa/
    ├── shapefiles/
    │   ├── perimetro.shp (+ .shx, .dbf, .prj, .cpg)
    │   ├── app.shp
    │   └── reserva_legal.shp
    └── car_upload.zip  ← Arquivo para upload no SICAR
```

## Estrutura do Projeto

```
car_automation/
├── main.py                 # CLI principal
├── config.py               # Configurações e constantes legais
├── geospatial/
│   ├── kml_parser.py       # Leitura de KML
│   ├── geometry_validator.py
│   └── area_calculator.py
├── data_sources/
│   └── hydrology.py        # Coleta de hidrografia
├── car_layers/
│   ├── app_calculator.py   # Cálculo de APP
│   └── reserva_legal.py    # Cálculo de RL
├── sicar_formatter/
│   └── shapefile_builder.py
└── tests/                  # Testes TDD
```

## Regras Legais Implementadas

### APP (Lei 12.651/2012)
| Tipo | Faixa de Proteção |
|------|-------------------|
| Rio ≤10m | 30m cada margem |
| Rio 10-50m | 50m cada margem |
| Rio 50-200m | 100m cada margem |
| Rio 200-600m | 200m cada margem |
| Rio >600m | 500m cada margem |
| Nascente | 50m de raio |
| Lago ≤20ha | 50m |
| Lago >20ha | 100m |

### Reserva Legal
| Bioma | Percentual |
|-------|-----------|
| Mata Atlântica | 20% |
| Cerrado | 20% |
| Amazônia | 80% |

## Testes

```bash
pytest tests/ -v
```

## Dados Externos

Para melhor precisão, baixe dados de hidrografia do IBGE e coloque em `data_cache/ibge/`:
- https://www.ibge.gov.br/geociencias/downloads-geociencias.html

## Limitações

- Identificação de nascentes é heurística (baseada em início de rios)
- Sem dados de hidrografia local, APPs de margem não são calculadas
- Vegetação nativa e área consolidada requerem dados MapBiomas (não implementado ainda)

## Licença

MIT
