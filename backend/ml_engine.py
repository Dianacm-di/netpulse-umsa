"""Módulo de Inteligencia Artificial (Clasificación QoS, Predicción Temporal y Diagnóstico) para NetPulse La Paz."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    root_mean_squared_error,
)
from sklearn.model_selection import train_test_split

from backend.config import (
    CLASES_QOS,
    PROVEEDORES,
    SECTORES_LA_PAZ,
    SECTORES_POR_ID,
    TECNOLOGIAS,
    UMBRAL_MUESTRAS_CONFIANZA_BAJA,
)
from backend.database import (
    cargar_dataframe,
    etiquetar_qos_uit,
    generar_datos_piloto,
    get_connection,
    nivel_confianza,
)

FEATURES_QOS = [
    "descarga_mbps",
    "subida_mbps",
    "latencia_ms",
    "jitter_ms",
    "perdida_pct",
    "dns_ms",
]

FEATURES_LABEL_ES = {
    "descarga_mbps": "Descarga (Mbps)",
    "subida_mbps": "Subida (Mbps)",
    "latencia_ms": "Latencia RTT (ms)",
    "jitter_ms": "Jitter (ms)",
    "perdida_pct": "Pérdida de paquetes (%)",
    "dns_ms": "Resolución DNS (ms)",
}


class NetPulseAIEngine:
    """Motor de aprendizaje automático y diagnóstico orientativo de NetPulse La Paz."""

    def __init__(self) -> None:
        self.clf: Optional[RandomForestClassifier] = None
        self.reg: Optional[RandomForestRegressor] = None
        self.version: str = "v1.0-init"
        self.fecha_entrenamiento: str = ""
        self.metrics_report: Dict[str, Any] = {}
        self.sector_map = {s.id: idx for idx, s in enumerate(SECTORES_LA_PAZ)}
        self.isp_map = {p: idx for idx, p in enumerate(PROVEEDORES)}
        self.tec_map = {t: idx for idx, t in enumerate(TECNOLOGIAS)}

    def _encode_context(self, df: pd.DataFrame) -> np.ndarray:
        sector_idx = df["sector_id"].map(self.sector_map).fillna(0).astype(float)
        isp_idx = df["proveedor"].map(self.isp_map).fillna(len(self.isp_map) - 1).astype(float)
        tec_idx = df["tecnologia"].map(self.tec_map).fillna(len(self.tec_map) - 1).astype(float)
        hora_sin = np.sin(2 * np.pi * df["hora"].astype(float) / 24.0)
        hora_cos = np.cos(2 * np.pi * df["hora"].astype(float) / 24.0)
        return np.column_stack([df["hora"].astype(float), hora_sin, hora_cos, sector_idx, isp_idx, tec_idx])

    def entrenar(self, version_tag: Optional[str] = None) -> Dict[str, Any]:
        generar_datos_piloto(force=False)
        df = cargar_dataframe()
        if len(df) < 20:
            raise ValueError("Se requieren al menos 20 registros para entrenar los modelos.")

        X = df[FEATURES_QOS]
        y = df["clase_qos"]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=y
        )

        clf = RandomForestClassifier(
            n_estimators=150,
            random_state=42,
            class_weight="balanced",
        )
        clf.fit(X_train, y_train)
        y_pred = clf.predict(X_test)

        acc = float(accuracy_score(y_test, y_pred))
        f1_mac = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
        labels_present = [c for c in CLASES_QOS if c in set(y_test) or c in set(y_pred)]
        cm = confusion_matrix(y_test, y_pred, labels=labels_present).tolist()
        report_dict = classification_report(
            y_test, y_pred, labels=labels_present, output_dict=True, zero_division=0
        )

        # Modelo 2: Predictor temporal de índice de degradación (0-100)
        X_ctx = self._encode_context(df)
        y_deg = df["indice_degradacion"].astype(float)
        Xc_train, Xc_test, yd_train, yd_test = train_test_split(
            X_ctx, y_deg, test_size=0.25, random_state=42
        )
        reg = RandomForestRegressor(n_estimators=140, max_depth=8, random_state=42)
        reg.fit(Xc_train, yd_train)
        yd_pred = reg.predict(Xc_test)

        mae = float(mean_absolute_error(yd_test, yd_pred))
        rmse = float(root_mean_squared_error(yd_test, yd_pred))

        importancias = [
            {
                "variable": FEATURES_LABEL_ES[col],
                "campo": col,
                "importancia": round(float(imp), 4),
            }
            for col, imp in zip(FEATURES_QOS, clf.feature_importances_)
        ]
        importancias.sort(key=lambda x: x["importancia"], reverse=True)

        ahora = datetime.now().isoformat(timespec="seconds")
        version = version_tag or f"v1.{len(df)}"

        self.clf = clf
        self.reg = reg
        self.version = version
        self.fecha_entrenamiento = ahora
        self.metrics_report = {
            "version": version,
            "fecha_entrenamiento": ahora,
            "n_registros": int(len(df)),
            "n_train": int(len(X_train)),
            "n_test": int(len(X_test)),
            "accuracy": round(acc, 4),
            "f1_macro": round(f1_mac, 4),
            "mae_degradacion": round(mae, 2),
            "rmse_degradacion": round(rmse, 2),
            "labels": labels_present,
            "matriz_confusion": cm,
            "reporte_por_clase": {
                k: {
                    "precision": round(float(v["precision"]), 3),
                    "recall": round(float(v["recall"]), 3),
                    "f1": round(float(v["f1-score"]), 3),
                    "support": int(v["support"]),
                }
                for k, v in report_dict.items()
                if k in labels_present
            },
            "importancia_variables": importancias,
            "distribucion_clases": {
                c: int((df["clase_qos"] == c).sum()) for c in CLASES_QOS
            },
        }

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO modelos_ia (
                    version, fecha_entrenamiento, n_registros,
                    accuracy, f1_macro, mae_degradacion, rmse_degradacion, detalle_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version,
                    ahora,
                    int(len(df)),
                    round(acc, 4),
                    round(f1_mac, 4),
                    round(mae, 2),
                    round(rmse, 2),
                    json.dumps(self.metrics_report, ensure_ascii=False),
                ),
            )
            conn.commit()

        return self.metrics_report

    def asegurar_entrenado(self) -> None:
        if self.clf is None or self.reg is None:
            self.entrenar()

    def diagnosticar(self, muestra: Dict[str, Any]) -> Dict[str, Any]:
        self.asegurar_entrenado()
        assert self.clf is not None and self.reg is not None

        df_in = pd.DataFrame(
            [
                {
                    "descarga_mbps": float(muestra["descarga_mbps"]),
                    "subida_mbps": float(muestra["subida_mbps"]),
                    "latencia_ms": float(muestra["latencia_ms"]),
                    "jitter_ms": float(muestra["jitter_ms"]),
                    "perdida_pct": float(muestra["perdida_pct"]),
                    "dns_ms": float(muestra["dns_ms"]),
                }
            ]
        )

        pred_clase = str(self.clf.predict(df_in)[0])
        probs_raw = self.clf.predict_proba(df_in)[0]
        probs = {
            str(cls): round(float(p), 3)
            for cls, p in zip(self.clf.classes_, probs_raw)
        }
        confianza_modelo = round(float(max(probs_raw)) * 100.0, 1)

        uit = etiquetar_qos_uit(
            float(muestra["descarga_mbps"]),
            float(muestra["subida_mbps"]),
            float(muestra["latencia_ms"]),
            float(muestra["jitter_ms"]),
            float(muestra["perdida_pct"]),
            float(muestra["dns_ms"]),
        )

        # Contexto histórico en la misma zona / proveedor
        sector_id = muestra.get("sector_id", "centro")
        proveedor = muestra.get("proveedor", "No especificado")
        tecnologia = muestra.get("tecnologia", "No especificado")
        hora = int(muestra.get("hora", datetime.now().hour))

        df_hist = cargar_dataframe(sector_id=sector_id)
        n_sector = len(df_hist)
        n_mismo_isp = (
            int((df_hist["proveedor"] == proveedor).sum())
            if proveedor != "No especificado"
            else n_sector
        )

        # Predicción de riesgo horario en el sector
        ctx_df = pd.DataFrame(
            [
                {
                    "hora": hora,
                    "sector_id": sector_id,
                    "proveedor": proveedor,
                    "tecnologia": tecnologia,
                }
            ]
        )
        riesgo_esperado_zona = round(
            float(np.clip(self.reg.predict(self._encode_context(ctx_df))[0], 0.0, 100.0)),
            1,
        )

        # Análisis explicativo orientativo (Sección 3.2, 7.1 y 7.3)
        lat = float(muestra["latencia_ms"])
        jit = float(muestra["jitter_ms"])
        loss = float(muestra["perdida_pct"])
        dns = float(muestra["dns_ms"])
        down = float(muestra["descarga_mbps"])
        up = float(muestra["subida_mbps"])

        hipotesis: List[Dict[str, str]] = []
        recomendaciones: List[str] = []

        if pred_clase == "Óptima" and uit["indice_degradacion"] < 15:
            origen_probable = "Desempeño estable (sin indicios de falla)"
            resumen = (
                "La conexión presenta parámetros compatibles con videollamadas HD, "
                "clases virtuales y trabajo en la nube según los umbrales orientativos UIT-T Y.1540."
            )
            recomendaciones.append("Mantener la ubicación actual o guardar este registro como línea base de comparación.")
        else:
            # 1. Revisión de DNS / Ruta externa
            if dns >= 85 and down >= 15 and loss < 1.0:
                hipotesis.append(
                    {
                        "ambito": "Resolución DNS / Ruta Externa",
                        "nivel": "Indicador principal" if dns >= 110 else "Posible factor",
                        "detalle": (
                            f"El tiempo de consulta DNS ({dns:.0f} ms) es elevado frente a la velocidad de descarga "
                            f"({down:.1f} Mbps), lo que suele percibirse como lentitud al abrir páginas nuevas."
                        ),
                    }
                )
                recomendaciones.append("Verificar si el router o dispositivo usa DNS automáticos lentos y probar en otro navegador.")

            # 2. Revisión de red local / Wi-Fi
            if (jit >= 22 or (lat >= 70 and down < 25 and tecnologia == "Fibra Óptica (FTTH)")) and loss < 1.8:
                hipotesis.append(
                    {
                        "ambito": "Posible interferencia en red local o Wi-Fi",
                        "nivel": "Sospecha orientativa",
                        "detalle": (
                            f"El jitter ({jit:.1f} ms) y la variabilidad observada pueden deberse a señal Wi-Fi débil, "
                            "paredes gruesas, banda 2.4 GHz congestionada o descargas simultáneas en el hogar."
                        ),
                    }
                )
                recomendaciones.append("Repetir la prueba cerca del router o mediante cable Ethernet para aislar el tramo Wi-Fi.")

            # 3. Revisión de acceso / congestión horaria
            if loss >= 1.0 or (18 <= hora <= 23 and (lat >= 75 or down < 18)):
                coincidencia_zona = ""
                if n_sector >= UMBRAL_MUESTRAS_CONFIANZA_BAJA:
                    pico_hist = df_hist[df_hist["hora"].between(18, 23)]
                    if len(pico_hist) >= 4:
                        deg_pico = pico_hist["indice_degradacion"].mean()
                        coincidencia_zona = (
                            f" En el histórico del sector ({len(pico_hist)} muestras nocturnas), "
                            f"la degradación promedio observada es {deg_pico:.1f}/100."
                        )
                hipotesis.append(
                    {
                        "ambito": "Posible congestión en tramo de acceso o franja horaria",
                        "nivel": "Alta probabilidad de congestión observada" if loss >= 1.5 else "Tendencia horaria",
                        "detalle": (
                            f"La combinación de pérdida de paquetes ({loss:.2f}%), latencia ({lat:.0f} ms) y horario ({hora:02d}:00) "
                            f"sugiere saturación en el acceso o demanda pico.{coincidencia_zona}"
                        ),
                    }
                )
                recomendaciones.append("Repetir la medición en horario de mañana (07:00–10:00) para contrastar el efecto horario.")

            if not hipotesis:
                hipotesis.append(
                    {
                        "ambito": "Degradación moderada multifactorial",
                        "nivel": "Orientativo",
                        "detalle": (
                            "Se observa reducción parcial de capacidad o aumento de retardo sin un síntoma único dominante."
                        ),
                    }
                )
                recomendaciones.append("Registrar 2 o 3 mediciones adicionales en distintos momentos para ampliar el historial.")

            origen_probable = hipotesis[0]["ambito"]
            resumen = hipotesis[0]["detalle"]

        aviso_validez = (
            f"Muestra local en {SECTORES_POR_ID.get(sector_id, SECTORES_LA_PAZ[0]).nombre}: "
            f"n={n_sector} registros ({nivel_confianza(n_sector)}). "
            "Este diagnóstico es orientativo y no confirma fallas internas del operador."
        )
        if n_mismo_isp < 5 and proveedor != "No especificado":
            aviso_validez += f" Datos insuficientes para comparar específicamente a {proveedor} en este sector (n={n_mismo_isp})."

        return {
            "modelo_version": self.version,
            "clase_predicha_ia": pred_clase,
            "probabilidades_clase": probs,
            "confianza_modelo_pct": confianza_modelo,
            "clase_regla_uit": uit["clase_qos"],
            "indice_degradacion": uit["indice_degradacion"],
            "riesgo_esperado_zona": riesgo_esperado_zona,
            "origen_probable": origen_probable,
            "resumen_explicativo": resumen,
            "hipotesis": hipotesis,
            "recomendaciones": recomendaciones,
            "aviso_validez": aviso_validez,
            "apto_para": {
                "videollamadas_hd": lat <= 85 and jit <= 25 and loss <= 1.0 and down >= 8 and up >= 3,
                "clases_en_linea": lat <= 110 and jit <= 30 and loss <= 1.5 and down >= 6,
                "juegos_tiempo_real": lat <= 60 and jit <= 15 and loss <= 0.5,
                "streaming_4k": down >= 25 and loss <= 1.5,
            },
        }

    def curva_prediccion_horaria(
        self,
        sector_id: str = "centro",
        proveedor: str = "todos",
        tecnologia: str = "todos",
    ) -> List[Dict[str, Any]]:
        self.asegurar_entrenado()
        assert self.reg is not None

        df_sector = cargar_dataframe(
            sector_id=sector_id if sector_id != "todos" else None,
            proveedor=proveedor if proveedor != "todos" else None,
            tecnologia=tecnologia if tecnologia != "todos" else None,
        )

        tec_ref = tecnologia if tecnologia != "todos" else "Fibra Óptica (FTTH)"
        isp_ref = proveedor if proveedor != "todos" else "Entel"
        sec_ref = sector_id if sector_id != "todos" else "centro"

        resultado: List[Dict[str, Any]] = []
        for h in range(24):
            ctx = pd.DataFrame(
                [
                    {
                        "hora": h,
                        "sector_id": sec_ref,
                        "proveedor": isp_ref,
                        "tecnologia": tec_ref,
                    }
                ]
            )
            pred = float(np.clip(self.reg.predict(self._encode_context(ctx))[0], 0.0, 100.0))
            sub = df_sector[df_sector["hora"] == h]
            n_h = int(len(sub))
            obs_mean = round(float(sub["indice_degradacion"].mean()), 1) if n_h > 0 else None
            obs_lat = round(float(sub["latencia_ms"].mean()), 1) if n_h > 0 else None
            obs_down = round(float(sub["descarga_mbps"].mean()), 1) if n_h > 0 else None

            # Margen de incertidumbre mayor cuando hay pocas muestras
            incertidumbre = round(max(6.0, 22.0 - min(n_h, 16) * 0.9), 1)
            resultado.append(
                {
                    "hora": h,
                    "etiqueta_hora": f"{h:02d}:00",
                    "riesgo_predicho_ia": round(pred, 1),
                    "banda_min": round(max(0.0, pred - incertidumbre), 1),
                    "banda_max": round(min(100.0, pred + incertidumbre), 1),
                    "incertidumbre": incertidumbre,
                    "degradacion_observada": obs_mean,
                    "latencia_observada": obs_lat,
                    "descarga_observada": obs_down,
                    "n_muestras": n_h,
                }
            )
        return resultado


def emular_telemetria(
    sector_id: str,
    proveedor: str,
    tecnologia: str,
    hora: int,
    escenario: str = "auto_contexto",
    manual: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Genera una ejecución emulada paso a paso de prueba QoS para La Paz,
    respetando la topografía/cobertura del sector, tecnología, horario o escenario de falla.
    """
    if escenario == "manual" and manual:
        descarga = float(manual.get("descarga_mbps", 40.0))
        subida = float(manual.get("subida_mbps", 18.0))
        latencia = float(manual.get("latencia_ms", 35.0))
        jitter = float(manual.get("jitter_ms", 8.0))
        perdida = float(manual.get("perdida_pct", 0.2))
        dns = float(manual.get("dns_ms", 28.0))
    else:
        rng = np.random.default_rng()
        sector = SECTORES_POR_ID.get(sector_id, SECTORES_POR_ID["centro"])
        cov = sector.factor_cobertura

        pico = 1.0
        if 19 <= hora <= 22:
            pico = 1.45
        elif 12 <= hora <= 14 or 17 <= hora <= 18:
            pico = 1.18
        elif 1 <= hora <= 5:
            pico = 0.8

        if tecnologia == "Fibra Óptica (FTTH)":
            descarga, subida, latencia, jitter, perdida, dns = (
                85 * cov, 48 * cov, (21 / cov) * pico, 5.0 * pico, 0.12 * pico, 23.0
            )
        elif tecnologia == "Cable / HFC":
            descarga, subida, latencia, jitter, perdida, dns = (
                46 * cov / (1 + 0.2 * (pico - 1)), 13 * cov, (37 / cov) * pico, 12.0 * pico, 0.45 * pico, 34.0
            )
        elif tecnologia == "4G LTE / 5G Móvil":
            descarga, subida, latencia, jitter, perdida, dns = (
                26 * cov / (1 + 0.25 * (pico - 1)), 10 * cov, (56 / cov) * pico, 20.0 * pico, 0.9 * pico, 46.0
            )
        elif tecnologia == "ADSL / Cobre":
            descarga, subida, latencia, jitter, perdida, dns = (
                11 * cov, 2.1 * cov, (62 / cov) * pico, 17.0 * pico, 1.05 * pico, 50.0
            )
        else:
            descarga, subida, latencia, jitter, perdida, dns = (
                22 * cov, 9 * cov, (50 / cov) * pico, 19.0 * pico, 0.85 * pico, 42.0
            )

        # Escenarios explícitos del emulador
        if escenario == "optima_ftth":
            descarga, subida, latencia, jitter, perdida, dns = 115.0, 68.0, 18.0, 3.2, 0.0, 17.0
        elif escenario == "wifi_saturado":
            descarga *= 0.42
            subida *= 0.48
            latencia += 52.0
            jitter += 29.0
            perdida += 0.65
            dns += 12.0
        elif escenario == "congestion_nocturna":
            descarga *= 0.36
            subida *= 0.55
            latencia += 78.0
            jitter += 24.0
            perdida += 2.1
            dns += 38.0
        elif escenario == "ruta_dns_lenta":
            dns += 135.0
            latencia += 34.0
            jitter += 8.0
        elif escenario == "microcortes_severos":
            descarga *= 0.28
            subida *= 0.32
            latencia += 125.0
            jitter += 46.0
            perdida += 4.5
            dns += 55.0

        # Variación estocástica realista
        descarga = round(float(np.clip(descarga * rng.uniform(0.88, 1.12), 1.0, 240.0)), 2)
        subida = round(float(np.clip(subida * rng.uniform(0.88, 1.12), 0.4, 150.0)), 2)
        latencia = round(float(np.clip(latencia * rng.uniform(0.90, 1.12), 8.0, 340.0)), 1)
        jitter = round(float(np.clip(jitter * rng.uniform(0.85, 1.18), 1.0, 110.0)), 1)
        perdida = round(float(np.clip(perdida + rng.uniform(-0.1, 0.25), 0.0, 15.0)), 2)
        dns = round(float(np.clip(dns * rng.uniform(0.90, 1.15), 6.0, 310.0)), 1)

    # Generar traza de 10 pings individuales para mostrar en vivo en el emulador
    rng_ping = np.random.default_rng()
    pings_ms: List[Optional[float]] = []
    n_perdidos = int(round((perdida / 100.0) * 10))
    perdidos_idx = set(rng_ping.choice(10, size=min(n_perdidos, 10), replace=False).tolist()) if n_perdidos > 0 else set()
    for i in range(10):
        if i in perdidos_idx:
            pings_ms.append(None)
        else:
            p = float(np.clip(rng_ping.normal(latencia, max(1.5, jitter * 0.65)), 6.0, 380.0))
            pings_ms.append(round(p, 1))

    return {
        "descarga_mbps": descarga,
        "subida_mbps": subida,
        "latencia_ms": latencia,
        "jitter_ms": jitter,
        "perdida_pct": perdida,
        "dns_ms": dns,
        "pings_detalle_ms": pings_ms,
    }


ai_engine = NetPulseAIEngine()
