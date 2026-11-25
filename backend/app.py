"""Servidor API Starlette + PWA estática para NetPulse La Paz."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from backend.config import (
    FRANJAS_HORARIAS,
    PROVEEDORES,
    SECTORES_LA_PAZ,
    TECNOLOGIAS,
    UMBRALES_UIT_Y1540,
)
from backend.database import (
    CSV_EXPORT_PATH,
    cargar_dataframe,
    exportar_csv,
    generar_datos_piloto,
    insertar_medicion,
    nivel_confianza,
)
from backend.ml_engine import ai_engine, emular_telemetria

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


async def api_health(request) -> JSONResponse:
    ai_engine.asegurar_entrenado()
    df = cargar_dataframe()
    return JSONResponse(
        {
            "status": "ok",
            "sistema": "NetPulse La Paz",
            "version_modelo": ai_engine.version,
            "total_mediciones": int(len(df)),
        }
    )


async def api_catalogo(request) -> JSONResponse:
    return JSONResponse(
        {
            "sectores": [asdict(s) for s in SECTORES_LA_PAZ],
            "proveedores": PROVEEDORES,
            "tecnologias": TECNOLOGIAS,
            "franjas_horarias": FRANJAS_HORARIAS,
            "umbrales_uit_y1540": UMBRALES_UIT_Y1540,
            "proyecto": {
                "titulo": "NETPULSE LA PAZ",
                "subtitulo": "Sistema Web de Monitoreo Colaborativo, Diagnóstico de Red y Predicción de la Degradación QoS por Macrodistritos en La Paz",
                "universidad": "Universidad Mayor de San Andrés (UMSA) — Carrera de Informática",
                "docente": "Miguel Toledo Paz",
                "autores": [
                    "Canaza Mamani Diana (CI: 9965614)",
                    "Martinez Cornejo Mauricio Cecilio (CI: 9902489)",
                    "Gianina Madelein Rodriguez Mendez (CI: 9110875)",
                ],
                "gestion": "La Paz – Bolivia · 2026",
            },
        }
    )


async def api_emular_y_registrar(request) -> JSONResponse:
    body: Dict[str, Any] = await request.json()
    sector_id = body.get("sector_id", "centro")
    proveedor = body.get("proveedor", "Entel")
    tecnologia = body.get("tecnologia", "Fibra Óptica (FTTH)")
    hora = int(body.get("hora", 20))
    escenario = body.get("escenario", "auto_contexto")
    guardar = bool(body.get("guardar", True))
    manual = body.get("manual")

    telemetria = emular_telemetria(
        sector_id=sector_id,
        proveedor=proveedor,
        tecnologia=tecnologia,
        hora=hora,
        escenario=escenario,
        manual=manual,
    )

    payload_diag = {
        **telemetria,
        "sector_id": sector_id,
        "proveedor": proveedor,
        "tecnologia": tecnologia,
        "hora": hora,
        "escenario_emulado": escenario,
        "metodo_prueba": "Emulador PWA (Simulación + Modelo IA)"
        if escenario != "manual"
        else "Modo Laboratorio Manual",
    }

    diagnostico = ai_engine.diagnosticar(payload_diag)

    registro = None
    if guardar:
        payload_diag["clase_qos"] = diagnostico["clase_predicha_ia"]
        payload_diag["indice_degradacion"] = diagnostico["indice_degradacion"]
        registro = insertar_medicion(payload_diag)

    return JSONResponse(
        {
            "telemetria": telemetria,
            "diagnostico": diagnostico,
            "registro": registro,
        }
    )


async def api_resumen_mapa(request) -> JSONResponse:
    proveedor = request.query_params.get("proveedor", "todos")
    tecnologia = request.query_params.get("tecnologia", "todos")
    franja = request.query_params.get("franja_horaria", "todas")

    df = cargar_dataframe(
        proveedor=proveedor, tecnologia=tecnologia, franja_horaria=franja
    )

    sectores_resumen = []
    for sec in SECTORES_LA_PAZ:
        sub = df[df["sector_id"] == sec.id]
        n = int(len(sub))
        if n > 0:
            desc_avg = round(float(sub["descarga_mbps"].mean()), 1)
            sub_avg = round(float(sub["subida_mbps"].mean()), 1)
            lat_avg = round(float(sub["latencia_ms"].mean()), 1)
            jit_avg = round(float(sub["jitter_ms"].mean()), 1)
            loss_avg = round(float(sub["perdida_pct"].mean()), 2)
            dns_avg = round(float(sub["dns_ms"].mean()), 1)
            deg_avg = round(float(sub["indice_degradacion"].mean()), 1)
            clase_dom = str(sub["clase_qos"].mode().iloc[0])
            conteo_clases = {
                c: int((sub["clase_qos"] == c).sum())
                for c in ["Óptima", "Aceptable", "Degradada", "Crítica"]
            }
        else:
            desc_avg = sub_avg = lat_avg = jit_avg = loss_avg = dns_avg = deg_avg = 0.0
            clase_dom = "Sin datos"
            conteo_clases = {"Óptima": 0, "Aceptable": 0, "Degradada": 0, "Crítica": 0}

        sectores_resumen.append(
            {
                **asdict(sec),
                "n_muestras": n,
                "confianza": nivel_confianza(n),
                "descarga_prom": desc_avg,
                "subida_prom": sub_avg,
                "latencia_prom": lat_avg,
                "jitter_prom": jit_avg,
                "perdida_prom": loss_avg,
                "dns_prom": dns_avg,
                "degradacion_prom": deg_avg,
                "clase_dominante": clase_dom,
                "conteo_clases": conteo_clases,
            }
        )

    # Puntos anonimizados aproximados para visualización en mapa
    puntos = []
    if len(df) > 0:
        for _, row in df.head(140).iterrows():
            puntos.append(
                {
                    "id": int(row["id"]),
                    "sector_id": row["sector_id"],
                    "lat_aprox": float(row["lat_aprox"]),
                    "lng_aprox": float(row["lng_aprox"]),
                    "clase_qos": row["clase_qos"],
                    "indice_degradacion": float(row["indice_degradacion"]),
                    "tecnologia": row["tecnologia"],
                    "proveedor": row["proveedor"],
                    "hora": int(row["hora"]),
                }
            )

    return JSONResponse(
        {
            "total_filtrado": int(len(df)),
            "sectores": sectores_resumen,
            "puntos_aproximados": puntos,
        }
    )


async def api_analitica(request) -> JSONResponse:
    sector_id = request.query_params.get("sector_id", "todos")
    proveedor = request.query_params.get("proveedor", "todos")
    tecnologia = request.query_params.get("tecnologia", "todos")
    franja = request.query_params.get("franja_horaria", "todas")

    df = cargar_dataframe(
        sector_id=sector_id,
        proveedor=proveedor,
        tecnologia=tecnologia,
        franja_horaria=franja,
    )

    curva_horaria = ai_engine.curva_prediccion_horaria(
        sector_id=sector_id, proveedor=proveedor, tecnologia=tecnologia
    )

    por_tecnologia = []
    if len(df) > 0:
        for tec, grp in df.groupby("tecnologia"):
            por_tecnologia.append(
                {
                    "tecnologia": str(tec),
                    "n": int(len(grp)),
                    "descarga_prom": round(float(grp["descarga_mbps"].mean()), 1),
                    "latencia_prom": round(float(grp["latencia_ms"].mean()), 1),
                    "jitter_prom": round(float(grp["jitter_ms"].mean()), 1),
                    "degradacion_prom": round(float(grp["indice_degradacion"].mean()), 1),
                }
            )
        por_tecnologia.sort(key=lambda x: x["descarga_prom"], reverse=True)

    por_proveedor = []
    if len(df) > 0:
        for isp, grp in df.groupby("proveedor"):
            por_proveedor.append(
                {
                    "proveedor": str(isp),
                    "n": int(len(grp)),
                    "confianza": nivel_confianza(int(len(grp))),
                    "descarga_prom": round(float(grp["descarga_mbps"].mean()), 1),
                    "latencia_prom": round(float(grp["latencia_ms"].mean()), 1),
                    "perdida_prom": round(float(grp["perdida_pct"].mean()), 2),
                    "degradacion_prom": round(float(grp["indice_degradacion"].mean()), 1),
                }
            )
        por_proveedor.sort(key=lambda x: x["n"], reverse=True)

    kpis = {
        "n_muestras": int(len(df)),
        "confianza": nivel_confianza(int(len(df))),
        "descarga_prom": round(float(df["descarga_mbps"].mean()), 1) if len(df) else 0.0,
        "latencia_prom": round(float(df["latencia_ms"].mean()), 1) if len(df) else 0.0,
        "jitter_prom": round(float(df["jitter_ms"].mean()), 1) if len(df) else 0.0,
        "perdida_prom": round(float(df["perdida_pct"].mean()), 2) if len(df) else 0.0,
        "dns_prom": round(float(df["dns_ms"].mean()), 1) if len(df) else 0.0,
        "degradacion_prom": round(float(df["indice_degradacion"].mean()), 1) if len(df) else 0.0,
    }

    return JSONResponse(
        {
            "kpis": kpis,
            "curva_horaria": curva_horaria,
            "por_tecnologia": por_tecnologia,
            "por_proveedor": por_proveedor,
        }
    )


async def api_mediciones(request) -> JSONResponse:
    limit = min(int(request.query_params.get("limit", 40)), 200)
    sector_id = request.query_params.get("sector_id", "todos")
    proveedor = request.query_params.get("proveedor", "todos")
    tecnologia = request.query_params.get("tecnologia", "todos")
    franja = request.query_params.get("franja_horaria", "todas")

    df = cargar_dataframe(
        sector_id=sector_id,
        proveedor=proveedor,
        tecnologia=tecnologia,
        franja_horaria=franja,
    )
    rows = df.head(limit).to_dict(orient="records")
    return JSONResponse({"total": int(len(df)), "items": rows})


async def api_ia_estado(request) -> JSONResponse:
    ai_engine.asegurar_entrenado()
    return JSONResponse(ai_engine.metrics_report)


async def api_ia_reentrenar(request) -> JSONResponse:
    metrics = ai_engine.entrenar()
    return JSONResponse({"mensaje": "Modelos re-entrenados correctamente", "metricas": metrics})


async def api_reset_piloto(request) -> JSONResponse:
    n = generar_datos_piloto(force=True)
    metrics = ai_engine.entrenar(version_tag="v1.0-piloto")
    return JSONResponse(
        {
            "mensaje": f"Dataset piloto restaurado con {n} registros.",
            "metricas": metrics,
        }
    )


async def api_exportar_csv(request) -> Response:
    path = exportar_csv()
    return FileResponse(
        path,
        media_type="text/csv; charset=utf-8",
        filename="mediciones_etiquetadas_lapaz.csv",
    )


async def index_page(request) -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@asynccontextmanager
async def lifespan(app: Starlette):
    generar_datos_piloto(force=False)
    ai_engine.entrenar(version_tag="v1.0-piloto")
    yield


routes = [
    Route("/", index_page),
    Route("/api/health", api_health),
    Route("/api/catalogo", api_catalogo),
    Route("/api/emular", api_emular_y_registrar, methods=["POST"]),
    Route("/api/mapa", api_resumen_mapa),
    Route("/api/analitica", api_analitica),
    Route("/api/mediciones", api_mediciones),
    Route("/api/ia/estado", api_ia_estado),
    Route("/api/ia/reentrenar", api_ia_reentrenar, methods=["POST"]),
    Route("/api/piloto/reset", api_reset_piloto, methods=["POST"]),
    Route("/api/exportar-csv", api_exportar_csv),
    Mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="static"),
]

app = Starlette(debug=False, routes=routes, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
