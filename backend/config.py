"""Configuración geográfica, técnica y criterios UIT-T Y.1540 para NetPulse La Paz."""

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class SectorInfo:
    id: str
    nombre: str
    macrodistrito: str
    zona_topografica: str
    altitud_m: int
    lat: float
    lng: float
    # Coordenadas normalizadas (0..1000 x 0..760) para el mapa topográfico SVG interactivo
    svg_x: int
    svg_y: int
    polygon: str
    factor_cobertura: float  # Modificador realista de infraestructura/densidad (solo piloto)


SECTORES_LA_PAZ: List[SectorInfo] = [
    SectorInfo(
        id="max_paredes",
        nombre="Max Paredes",
        macrodistrito="Max Paredes",
        zona_topografica="Ladera Noroeste",
        altitud_m=3840,
        lat=-16.492,
        lng=-68.152,
        svg_x=295,
        svg_y=250,
        polygon="200,180 355,165 385,265 330,320 215,295",
        factor_cobertura=0.86,
    ),
    SectorInfo(
        id="periferica",
        nombre="Periférica",
        macrodistrito="Periférica",
        zona_topografica="Ladera Norte",
        altitud_m=3780,
        lat=-16.480,
        lng=-68.122,
        svg_x=475,
        svg_y=185,
        polygon="360,120 580,105 620,210 510,260 390,245",
        factor_cobertura=0.88,
    ),
    SectorInfo(
        id="san_antonio",
        nombre="San Antonio",
        macrodistrito="San Antonio",
        zona_topografica="Ladera Este",
        altitud_m=3720,
        lat=-16.496,
        lng=-68.105,
        svg_x=635,
        svg_y=295,
        polygon="545,235 735,215 765,335 645,380 540,335",
        factor_cobertura=0.87,
    ),
    SectorInfo(
        id="cotahuma_alto",
        nombre="Cotahuma Alto",
        macrodistrito="Cotahuma",
        zona_topografica="Ladera Oeste",
        altitud_m=3810,
        lat=-16.512,
        lng=-68.150,
        svg_x=255,
        svg_y=390,
        polygon="170,315 325,325 350,435 245,480 155,425",
        factor_cobertura=0.85,
    ),
    SectorInfo(
        id="centro",
        nombre="Centro",
        macrodistrito="Centro",
        zona_topografica="Hoyada Central",
        altitud_m=3640,
        lat=-16.500,
        lng=-68.133,
        svg_x=420,
        svg_y=310,
        polygon="355,260 495,260 505,355 375,365 340,320",
        factor_cobertura=1.05,
    ),
    SectorInfo(
        id="miraflores",
        nombre="Miraflores",
        macrodistrito="Centro / Miraflores",
        zona_topografica="Hoyada Este",
        altitud_m=3610,
        lat=-16.502,
        lng=-68.118,
        svg_x=540,
        svg_y=350,
        polygon="495,265 565,275 595,380 510,415 475,355",
        factor_cobertura=1.06,
    ),
    SectorInfo(
        id="sopocachi",
        nombre="Sopocachi",
        macrodistrito="Cotahuma",
        zona_topografica="Hoyada Media",
        altitud_m=3580,
        lat=-16.513,
        lng=-68.128,
        svg_x=405,
        svg_y=415,
        polygon="345,365 480,365 495,465 365,485 335,430",
        factor_cobertura=1.03,
    ),
    SectorInfo(
        id="zona_sur",
        nombre="Zona Sur",
        macrodistrito="Sur",
        zona_topografica="Valle Bajo",
        altitud_m=3260,
        lat=-16.542,
        lng=-68.082,
        svg_x=635,
        svg_y=520,
        polygon="490,445 775,410 835,565 650,625 485,560",
        factor_cobertura=1.08,
    ),
    SectorInfo(
        id="mallasa",
        nombre="Mallasa",
        macrodistrito="Mallasa",
        zona_topografica="Valle Sur",
        altitud_m=3180,
        lat=-16.571,
        lng=-68.094,
        svg_x=545,
        svg_y=655,
        polygon="440,590 645,625 630,720 435,710",
        factor_cobertura=0.79,
    ),
    SectorInfo(
        id="el_alto",
        nombre="El Alto (Comparativo)",
        macrodistrito="El Alto (Área Complementaria)",
        zona_topografica="Altiplano",
        altitud_m=4090,
        lat=-16.505,
        lng=-68.168,
        svg_x=115,
        svg_y=275,
        polygon="35,145 180,155 185,435 40,445",
        factor_cobertura=0.84,
    ),
]

SECTORES_POR_ID: Dict[str, SectorInfo] = {s.id: s for s in SECTORES_LA_PAZ}

PROVEEDORES: List[str] = [
    "Entel",
    "Tigo",
    "Viva",
    "AXS",
    "Comteco / Otro",
    "No especificado",
]

TECNOLOGIAS: List[str] = [
    "Fibra Óptica (FTTH)",
    "Cable / HFC",
    "4G LTE / 5G Móvil",
    "ADSL / Cobre",
    "Radioenlace",
    "No especificado",
]

FRANJAS_HORARIAS: List[Dict[str, str]] = [
    {"id": "madrugada", "label": "Madrugada (00:00–05:59)", "rango": "00:00-05:59"},
    {"id": "manana", "label": "Mañana (06:00–11:59)", "rango": "06:00-11:59"},
    {"id": "tarde", "label": "Tarde (12:00–17:59)", "rango": "12:00-17:59"},
    {"id": "pico_nocturno", "label": "Pico Nocturno (18:00–23:59)", "rango": "18:00-23:59"},
]

CLASES_QOS: List[str] = ["Óptima", "Aceptable", "Degradada", "Crítica"]

# Criterios técnicos orientativos inspirados en UIT-T Y.1540 (clase QoS IP interactiva)
# y parámetros de referencia ATT Bolivia (no reemplazan mediciones oficiales).
UMBRALES_UIT_Y1540 = {
    "latencia_optima_max_ms": 45.0,
    "latencia_aceptable_max_ms": 95.0,
    "latencia_degradada_max_ms": 170.0,
    "jitter_optimo_max_ms": 10.0,
    "jitter_aceptable_max_ms": 25.0,
    "jitter_degradado_max_ms": 45.0,
    "perdida_optima_max_pct": 0.3,
    "perdida_aceptable_max_pct": 1.0,
    "perdida_degradada_max_pct": 2.5,
    "dns_optimo_max_ms": 35.0,
    "dns_aceptable_max_ms": 75.0,
    "descarga_optima_min_mbps": 25.0,
    "descarga_aceptable_min_mbps": 10.0,
}

UMBRAL_MUESTRAS_CONFIANZA_BAJA = 8
UMBRAL_MUESTRAS_CONFIANZA_MEDIA = 20
