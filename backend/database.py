"""Capa de datos SQLite y generador de datos piloto calibrados para NetPulse La Paz."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from backend.config import (
    PROVEEDORES,
    SECTORES_LA_PAZ,
    SECTORES_POR_ID,
    TECNOLOGIAS,
    UMBRAL_MUESTRAS_CONFIANZA_BAJA,
    UMBRAL_MUESTRAS_CONFIANZA_MEDIA,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "netpulse_lapaz.db"
CSV_EXPORT_PATH = DATA_DIR / "mediciones_etiquetadas.csv"


def obtener_franja_horaria(hora: int) -> str:
    if 0 <= hora < 6:
        return "madrugada"
    if 6 <= hora < 12:
        return "manana"
    if 12 <= hora < 18:
        return "tarde"
    return "pico_nocturno"


def etiquetar_qos_uit(
    descarga_mbps: float,
    subida_mbps: float,
    latencia_ms: float,
    jitter_ms: float,
    perdida_pct: float,
    dns_ms: float,
) -> Dict[str, Any]:
    """
    Asignación transparente de etiqueta y puntaje de degradación (0-100)
    basada en criterios técnicos inspirados en UIT-T Y.1540.
    Puntaje 0 = sin degradación; 100 = degradación crítica.
    """
    penalizacion = 0.0

    # Latencia RTT
    if latencia_ms > 180:
        penalizacion += 34
    elif latencia_ms > 110:
        penalizacion += 22
    elif latencia_ms > 60:
        penalizacion += 11
    elif latencia_ms > 35:
        penalizacion += 4

    # Jitter
    if jitter_ms > 45:
        penalizacion += 28
    elif jitter_ms > 24:
        penalizacion += 18
    elif jitter_ms > 10:
        penalizacion += 8

    # Pérdida de paquetes (%)
    if perdida_pct >= 3.0:
        penalizacion += 36
    elif perdida_pct >= 1.2:
        penalizacion += 22
    elif perdida_pct >= 0.4:
        penalizacion += 10

    # Resolución DNS
    if dns_ms > 130:
        penalizacion += 14
    elif dns_ms > 70:
        penalizacion += 7

    # Capacidad de descarga y subida
    if descarga_mbps < 5:
        penalizacion += 26
    elif descarga_mbps < 15:
        penalizacion += 14
    elif descarga_mbps < 30:
        penalizacion += 5

    if subida_mbps < 2:
        penalizacion += 8

    indice_degradacion = float(np.clip(penalizacion, 0.0, 100.0))

    # Reglas de frontera dura por pérdida severa o latencia extrema
    if indice_degradacion >= 60 or perdida_pct >= 3.5 or latencia_ms >= 220:
        clase = "Crítica"
    elif indice_degradacion >= 35 or perdida_pct >= 1.3 or jitter_ms >= 28:
        clase = "Degradada"
    elif indice_degradacion >= 15 or latencia_ms > 55 or descarga_mbps < 25:
        clase = "Aceptable"
    else:
        clase = "Óptima"

    return {
        "clase_qos": clase,
        "indice_degradacion": round(indice_degradacion, 1),
    }


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mediciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_iso TEXT NOT NULL,
                fecha TEXT NOT NULL,
                hora INTEGER NOT NULL,
                franja_horaria TEXT NOT NULL,
                sector_id TEXT NOT NULL,
                sector_nombre TEXT NOT NULL,
                macrodistrito TEXT NOT NULL,
                lat_aprox REAL NOT NULL,
                lng_aprox REAL NOT NULL,
                proveedor TEXT NOT NULL,
                tecnologia TEXT NOT NULL,
                metodo_prueba TEXT NOT NULL,
                escenario_emulado TEXT NOT NULL,
                descarga_mbps REAL NOT NULL,
                subida_mbps REAL NOT NULL,
                latencia_ms REAL NOT NULL,
                jitter_ms REAL NOT NULL,
                perdida_pct REAL NOT NULL,
                dns_ms REAL NOT NULL,
                clase_qos TEXT NOT NULL,
                indice_degradacion REAL NOT NULL,
                es_piloto INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS modelos_ia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                fecha_entrenamiento TEXT NOT NULL,
                n_registros INTEGER NOT NULL,
                accuracy REAL NOT NULL,
                f1_macro REAL NOT NULL,
                mae_degradacion REAL NOT NULL,
                rmse_degradacion REAL NOT NULL,
                detalle_json TEXT NOT NULL
            )
            """
        )
        conn.commit()


def generar_datos_piloto(force: bool = False) -> int:
    """Genera un conjunto inicial de mediciones piloto realistas para La Paz si la BD está vacía."""
    init_db()
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM mediciones").fetchone()[0]
        if count > 0 and not force:
            return count
        if force:
            conn.execute("DELETE FROM mediciones")
            conn.commit()

    rng = np.random.default_rng(202604)
    registros: List[Dict[str, Any]] = []
    ahora = datetime(2026, 11, 25, 12, 0, 0)

    isps_activos = [p for p in PROVEEDORES if p != "No especificado"]
    tecs_activas = [
        ("Fibra Óptica (FTTH)", 0.44),
        ("Cable / HFC", 0.25),
        ("4G LTE / 5G Móvil", 0.21),
        ("ADSL / Cobre", 0.06),
        ("Radioenlace", 0.04),
    ]
    tec_nombres = [t[0] for t in tecs_activas]
    tec_probs = [t[1] for t in tecs_activas]

    hora_probs = np.array(
        [
            0.015, 0.01, 0.01, 0.01, 0.01, 0.02,
            0.03, 0.045, 0.055, 0.055, 0.055, 0.05,
            0.045, 0.045, 0.05, 0.05, 0.05, 0.055,
            0.065, 0.08, 0.09, 0.075, 0.045, 0.025,
        ],
        dtype=float,
    )
    hora_probs = hora_probs / hora_probs.sum()

    for i in range(280):
        sector = SECTORES_LA_PAZ[int(rng.integers(0, len(SECTORES_LA_PAZ)))]
        dias_atras = int(rng.integers(0, 21))
        hora = int(rng.choice(list(range(24)), p=hora_probs))
        minuto = int(rng.integers(0, 60))
        ts = ahora - timedelta(days=dias_atras, hours=(12 - hora), minutes=minuto)
        franja = obtener_franja_horaria(hora)
        proveedor = str(rng.choice(isps_activos, p=[0.36, 0.31, 0.14, 0.13, 0.06]))
        tecnologia = str(rng.choice(tec_nombres, p=tec_probs))

        # Modificador de congestión según hora en La Paz (pico 19:00-22:30)
        pico = 1.0
        if 19 <= hora <= 22:
            pico = 1.48
        elif 12 <= hora <= 14 or 17 <= hora <= 18:
            pico = 1.18
        elif 1 <= hora <= 5:
            pico = 0.78

        cov = sector.factor_cobertura

        if tecnologia == "Fibra Óptica (FTTH)":
            desc_base = rng.normal(82 * cov, 18)
            sub_base = rng.normal(46 * cov, 12)
            lat_base = rng.normal(22 / cov, 6) * pico
            jit_base = rng.normal(5.5, 2.5) * pico
            perd_base = max(0.0, rng.normal(0.15, 0.18) * (pico ** 1.2))
            dns_base = rng.normal(24, 7) * (1.1 if pico > 1.2 else 1.0)
        elif tecnologia == "Cable / HFC":
            desc_base = rng.normal(48 * cov, 14) / (1.0 + 0.22 * (pico - 1.0))
            sub_base = rng.normal(14 * cov, 4)
            lat_base = rng.normal(38 / cov, 10) * pico
            jit_base = rng.normal(12, 5) * pico
            perd_base = max(0.0, rng.normal(0.45, 0.45) * pico)
            dns_base = rng.normal(34, 11) * pico
        elif tecnologia == "4G LTE / 5G Móvil":
            desc_base = rng.normal(28 * cov, 11) / (1.0 + 0.28 * (pico - 1.0))
            sub_base = rng.normal(11 * cov, 4)
            lat_base = rng.normal(58 / cov, 16) * pico
            jit_base = rng.normal(21, 9) * pico
            perd_base = max(0.0, rng.normal(0.95, 0.75) * pico)
            dns_base = rng.normal(48, 16) * pico
        elif tecnologia == "ADSL / Cobre":
            desc_base = rng.normal(12 * cov, 3.5)
            sub_base = rng.normal(2.2 * cov, 0.7)
            lat_base = rng.normal(64 / cov, 14) * pico
            jit_base = rng.normal(18, 7) * pico
            perd_base = max(0.0, rng.normal(1.1, 0.7) * pico)
            dns_base = rng.normal(52, 15)
        else:  # Radioenlace
            desc_base = rng.normal(20 * cov, 7)
            sub_base = rng.normal(9 * cov, 3)
            lat_base = rng.normal(54 / cov, 15) * pico
            jit_base = rng.normal(23, 10) * pico
            perd_base = max(0.0, rng.normal(1.25, 0.9) * pico)
            dns_base = rng.normal(46, 14)

        # Inyectar algunas anomalías locales/externas realistas (~12% de muestras)
        escenario = "Muestreo Piloto"
        roll = rng.random()
        if roll < 0.05:
            # Wi-Fi local saturado / lejos del router
            lat_base += rng.uniform(35, 85)
            jit_base += rng.uniform(18, 42)
            desc_base *= rng.uniform(0.35, 0.65)
            escenario = "Degradación Wi-Fi Local"
        elif roll < 0.09:
            # Congestión ISP / pérdida de paquetes en tramo de acceso
            perd_base += rng.uniform(1.5, 4.2)
            lat_base += rng.uniform(45, 110)
            escenario = "Congestión de Acceso"
        elif roll < 0.12:
            # Demora DNS / ruta externa
            dns_base += rng.uniform(75, 175)
            lat_base += rng.uniform(25, 65)
            escenario = "Demora DNS / Ruta Externa"

        descarga = round(float(np.clip(desc_base, 1.2, 220.0)), 2)
        subida = round(float(np.clip(sub_base, 0.5, 140.0)), 2)
        latencia = round(float(np.clip(lat_base, 8.0, 320.0)), 1)
        jitter = round(float(np.clip(jit_base, 1.0, 95.0)), 1)
        perdida = round(float(np.clip(perd_base, 0.0, 12.0)), 2)
        dns = round(float(np.clip(dns_base, 7.0, 290.0)), 1)

        # Jitter geográfico de privacidad (+/- 0.004 grados) para nunca revelar domicilio
        lat_aprox = round(sector.lat + float(rng.uniform(-0.004, 0.004)), 4)
        lng_aprox = round(sector.lng + float(rng.uniform(-0.004, 0.004)), 4)

        etiqueta = etiquetar_qos_uit(descarga, subida, latencia, jitter, perdida, dns)

        registros.append(
            {
                "timestamp_iso": ts.isoformat(timespec="seconds"),
                "fecha": ts.strftime("%Y-%m-%d"),
                "hora": hora,
                "franja_horaria": franja,
                "sector_id": sector.id,
                "sector_nombre": sector.nombre,
                "macrodistrito": sector.macrodistrito,
                "lat_aprox": lat_aprox,
                "lng_aprox": lng_aprox,
                "proveedor": proveedor,
                "tecnologia": tecnologia,
                "metodo_prueba": "Emulador WebSocket/HTTP (Piloto)",
                "escenario_emulado": escenario,
                "descarga_mbps": descarga,
                "subida_mbps": subida,
                "latencia_ms": latencia,
                "jitter_ms": jitter,
                "perdida_pct": perdida,
                "dns_ms": dns,
                "clase_qos": etiqueta["clase_qos"],
                "indice_degradacion": etiqueta["indice_degradacion"],
                "es_piloto": 1,
            }
        )

    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO mediciones (
                timestamp_iso, fecha, hora, franja_horaria, sector_id, sector_nombre,
                macrodistrito, lat_aprox, lng_aprox, proveedor, tecnologia, metodo_prueba,
                escenario_emulado, descarga_mbps, subida_mbps, latencia_ms, jitter_ms,
                perdida_pct, dns_ms, clase_qos, indice_degradacion, es_piloto
            ) VALUES (
                :timestamp_iso, :fecha, :hora, :franja_horaria, :sector_id, :sector_nombre,
                :macrodistrito, :lat_aprox, :lng_aprox, :proveedor, :tecnologia, :metodo_prueba,
                :escenario_emulado, :descarga_mbps, :subida_mbps, :latencia_ms, :jitter_ms,
                :perdida_pct, :dns_ms, :clase_qos, :indice_degradacion, :es_piloto
            )
            """,
            registros,
        )
        conn.commit()

    exportar_csv()
    return len(registros)


def insertar_medicion(payload: Dict[str, Any]) -> Dict[str, Any]:
    init_db()
    sector = SECTORES_POR_ID.get(payload.get("sector_id", "centro"), SECTORES_POR_ID["centro"])
    ahora = datetime.now()
    hora = int(payload.get("hora", ahora.hour))
    franja = obtener_franja_horaria(hora)

    rng = np.random.default_rng()
    lat_aprox = round(sector.lat + float(rng.uniform(-0.0035, 0.0035)), 4)
    lng_aprox = round(sector.lng + float(rng.uniform(-0.0035, 0.0035)), 4)

    descarga = round(float(payload["descarga_mbps"]), 2)
    subida = round(float(payload["subida_mbps"]), 2)
    latencia = round(float(payload["latencia_ms"]), 1)
    jitter = round(float(payload["jitter_ms"]), 1)
    perdida = round(float(payload["perdida_pct"]), 2)
    dns = round(float(payload["dns_ms"]), 1)

    etiqueta = etiquetar_qos_uit(descarga, subida, latencia, jitter, perdida, dns)

    registro = {
        "timestamp_iso": ahora.isoformat(timespec="seconds"),
        "fecha": ahora.strftime("%Y-%m-%d"),
        "hora": hora,
        "franja_horaria": franja,
        "sector_id": sector.id,
        "sector_nombre": sector.nombre,
        "macrodistrito": sector.macrodistrito,
        "lat_aprox": lat_aprox,
        "lng_aprox": lng_aprox,
        "proveedor": payload.get("proveedor") or "No especificado",
        "tecnologia": payload.get("tecnologia") or "No especificado",
        "metodo_prueba": payload.get("metodo_prueba") or "Emulador PWA Interactivo",
        "escenario_emulado": payload.get("escenario_emulado") or "Manual / En Vivo",
        "descarga_mbps": descarga,
        "subida_mbps": subida,
        "latencia_ms": latencia,
        "jitter_ms": jitter,
        "perdida_pct": perdida,
        "dns_ms": dns,
        "clase_qos": payload.get("clase_qos") or etiqueta["clase_qos"],
        "indice_degradacion": payload.get("indice_degradacion", etiqueta["indice_degradacion"]),
        "es_piloto": 0,
    }

    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO mediciones (
                timestamp_iso, fecha, hora, franja_horaria, sector_id, sector_nombre,
                macrodistrito, lat_aprox, lng_aprox, proveedor, tecnologia, metodo_prueba,
                escenario_emulado, descarga_mbps, subida_mbps, latencia_ms, jitter_ms,
                perdida_pct, dns_ms, clase_qos, indice_degradacion, es_piloto
            ) VALUES (
                :timestamp_iso, :fecha, :hora, :franja_horaria, :sector_id, :sector_nombre,
                :macrodistrito, :lat_aprox, :lng_aprox, :proveedor, :tecnologia, :metodo_prueba,
                :escenario_emulado, :descarga_mbps, :subida_mbps, :latencia_ms, :jitter_ms,
                :perdida_pct, :dns_ms, :clase_qos, :indice_degradacion, :es_piloto
            )
            """,
            registro,
        )
        conn.commit()
        registro["id"] = cur.lastrowid

    exportar_csv()
    return registro


def cargar_dataframe(
    sector_id: Optional[str] = None,
    proveedor: Optional[str] = None,
    tecnologia: Optional[str] = None,
    franja_horaria: Optional[str] = None,
) -> pd.DataFrame:
    init_db()
    query = "SELECT * FROM mediciones WHERE 1=1"
    params: List[Any] = []
    if sector_id and sector_id != "todos":
        query += " AND sector_id = ?"
        params.append(sector_id)
    if proveedor and proveedor != "todos":
        query += " AND proveedor = ?"
        params.append(proveedor)
    if tecnologia and tecnologia != "todos":
        query += " AND tecnologia = ?"
        params.append(tecnologia)
    if franja_horaria and franja_horaria != "todas":
        query += " AND franja_horaria = ?"
        params.append(franja_horaria)

    query += " ORDER BY id DESC"
    with get_connection() as conn:
        df = pd.read_sql_query(query, conn, params=params)
    return df


def exportar_csv() -> Path:
    df = cargar_dataframe()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_EXPORT_PATH, index=False, encoding="utf-8")
    return CSV_EXPORT_PATH


def nivel_confianza(n: int) -> str:
    if n < UMBRAL_MUESTRAS_CONFIANZA_BAJA:
        return "Baja (muestra insuficiente)"
    if n < UMBRAL_MUESTRAS_CONFIANZA_MEDIA:
        return "Media (exploratoria)"
    return "Alta (referencia piloto)"
