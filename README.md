# NetPulse La Paz 🌐

**Sistema Web de Monitoreo Colaborativo, Diagnóstico de Red y Predicción de la Degradación de la Calidad del Servicio de Internet (QoS) por Macrodistritos en La Paz**

> Prototipo académico desarrollado para la carrera de **Informática** de la **Universidad Mayor de San Andrés (UMSA)** · La Paz – Bolivia · 2026

---

## 📋 Descripción

NetPulse La Paz es una aplicación web progresiva (PWA) que combina:

- **Emulador de pruebas de red** paso a paso (DNS, Latencia RTT, Jitter, Pérdida de paquetes, Descarga y Subida)
- **Mapa topográfico interactivo** de los 10 macrodistritos de La Paz con resultados por sector
- **Modelos de Inteligencia Artificial** (`RandomForestClassifier` y `RandomForestRegressor`) entrenados con scikit-learn para clasificar calidad QoS y predecir riesgo de degradación temporal
- **Panel de analítica** con curva horaria de degradación, comparativa por tecnología y proveedor
- **Diagnóstico orientativo** que distingue posibles fallas en red local/Wi-Fi, tramo de acceso ISP o DNS/ruta externa
- **Referencias técnicas**: Recomendación UIT-T Y.1540 y datos públicos de la ATT Bolivia

---

## 👥 Autores

| Nombre                                | CI        |
|---------------------------------------|-----------|
| Canaza Mamani Diana                   | 9965614   |
| Martinez Cornejo Mauricio Cecilio     | 9902489   |
| Gianina Madelein Rodriguez Mendez     | 9110875   |

**Docente:** Miguel Toledo Paz  
**Carrera:** Informática · UMSA · La Paz – Bolivia · 2026

---

## 🗂️ Estructura del proyecto

```text
netpulse-la-paz/
├── run.py                     ← Punto de entrada: arranca el servidor
├── requirements.txt           ← Dependencias Python
├── .gitignore
├── README.md
│
├── backend/
│   ├── __init__.py
│   ├── config.py              ← Sectores/macrodistritos, proveedores, umbrales UIT-T Y.1540
│   ├── database.py            ← SQLite, generación de datos piloto, etiquetado QoS
│   ├── ml_engine.py           ← RandomForest, predicción temporal, diagnóstico IA
│   └── app.py                 ← API REST Starlette + servicio de la PWA estática
│
└── frontend/
    ├── index.html             ← Estructura HTML de las 4 vistas
    ├── styles.css             ← Estilos responsive dark-mode
    ├── app.js                 ← Lógica PWA: emulador, mapa SVG, gráficos Canvas
    ├── manifest.webmanifest   ← Metadatos PWA (instalable en móvil/PC)
    ├── sw.js                  ← Service Worker para funcionamiento offline
    └── icon.svg               ← Ícono de la aplicación
```

---

## ⚙️ Requisitos previos

- **Python 3.11 o superior** (probado con Python 3.14)
- **pip** (gestor de paquetes)
- Navegador moderno: Chrome, Edge o Firefox

---

## 🚀 Instalación y ejecución

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/netpulse-la-paz.git
cd netpulse-la-paz
```

### 2. Crear entorno virtual (recomendado)

```bash
python -m venv venv

# Windows (PowerShell):
venv\Scripts\activate

# macOS / Linux:
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Ejecutar el servidor

```bash
python run.py
```

Verás:

```
Iniciando NetPulse La Paz en http://127.0.0.1:8000 ...
INFO:     Started server process
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 5. Abrir en el navegador

```
http://127.0.0.1:8000
```

> La base de datos SQLite y el dataset piloto de **280 mediciones** se generan automáticamente al primer inicio. Los modelos de IA también se entrenan automáticamente.

---

## 🖥️ Cómo usar en Visual Studio Code

1. Abre VS Code y selecciona **Archivo → Abrir carpeta** → elige `netpulse-la-paz`
2. Abre una terminal integrada con `Ctrl + ñ`
3. Activa el entorno virtual:
   ```powershell
   venv\Scripts\activate
   ```
4. Instala dependencias si es la primera vez:
   ```powershell
   pip install -r requirements.txt
   ```
5. Ejecuta el proyecto:
   ```powershell
   python run.py
   ```
6. Abre `http://127.0.0.1:8000` en tu navegador

**Recomendación:** Instala la extensión **Python** de Microsoft en VS Code para resaltado de sintaxis y depuración.

---

## 📡 API REST (Endpoints disponibles)

| Método | Endpoint              | Descripción                                      |
|--------|-----------------------|--------------------------------------------------|
| GET    | `/api/health`         | Estado del servidor y versión del modelo IA      |
| GET    | `/api/catalogo`       | Sectores, proveedores, tecnologías, umbrales     |
| POST   | `/api/emular`         | Ejecutar prueba emulada QoS + diagnóstico IA     |
| GET    | `/api/mapa`           | Resumen por macrodistrito (con filtros)          |
| GET    | `/api/analitica`      | KPIs, curva horaria, comparativas                |
| GET    | `/api/mediciones`     | Historial de mediciones (con filtros)            |
| GET    | `/api/ia/estado`      | Métricas del modelo entrenado                    |
| POST   | `/api/ia/reentrenar`  | Re-entrenar modelos con datos actuales           |
| POST   | `/api/piloto/reset`   | Restaurar dataset piloto (280 muestras)          |
| GET    | `/api/exportar-csv`   | Descargar CSV con todas las mediciones           |

---

## 🤖 Módulo de Inteligencia Artificial

### Clasificador de calidad QoS
- **Modelo:** `RandomForestClassifier` (n_estimators=150, class_weight="balanced")
- **Variables:** Descarga (Mbps), Subida (Mbps), Latencia RTT (ms), Jitter (ms), Pérdida de paquetes (%), Resolución DNS (ms)
- **Clases:** `Óptima`, `Aceptable`, `Degradada`, `Crítica`
- **Métricas piloto:** Accuracy ≈ 77%, F1-Score macro ≈ 0.66
- **Evaluación:** Split 75/25 estratificado

### Predictor de degradación temporal
- **Modelo:** `RandomForestRegressor` (n_estimators=140, max_depth=8)
- **Objetivo:** Índice de riesgo 0–100 por hora, sector, proveedor y tecnología
- **Métricas piloto:** MAE ≈ 11.4 puntos, RMSE ≈ 14.2 puntos

### Etiquetado UIT-T Y.1540
El etiquetado de las clases QoS sigue reglas técnicas transparentes inspiradas en la recomendación UIT-T Y.1540 y los parámetros de referencia de la ATT Bolivia. No se usan etiquetas arbitrarias.

---

## 🗺️ Macrodistritos cubiertos

| Sector              | Altitud (m) | Zona Topográfica      |
|---------------------|-------------|-----------------------|
| Centro              | 3,640       | Hoyada Central        |
| Miraflores          | 3,610       | Hoyada Este           |
| Sopocachi           | 3,580       | Hoyada Media          |
| San Antonio         | 3,720       | Ladera Este           |
| Periférica          | 3,780       | Ladera Norte          |
| Max Paredes         | 3,840       | Ladera Noroeste       |
| Cotahuma Alto       | 3,810       | Ladera Oeste          |
| Zona Sur            | 3,260       | Valle Bajo            |
| Mallasa             | 3,180       | Valle Sur             |
| El Alto (comp.)     | 4,090       | Altiplano             |

---

## 🛠️ Tecnologías utilizadas

| Capa        | Tecnología                                   |
|-------------|----------------------------------------------|
| Backend     | Python 3.11+, Starlette, Uvicorn             |
| IA / ML     | scikit-learn, pandas, NumPy                  |
| Base datos  | SQLite (stdlib Python), archivos CSV         |
| Frontend    | HTML5, CSS3, JavaScript ES2020 (PWA)         |
| Mapas       | SVG topográfico interactivo (vanilla JS)     |
| Gráficos    | Canvas API (vanilla JS)                      |
| Offline     | Service Worker (sw.js)                       |

---

## ⚠️ Limitaciones y validez académica

- Los datos piloto iniciales son **sintéticos y calibrados** para demostración del flujo de IA. En producción real se usarían exclusivamente mediciones voluntarias reales.
- Las pruebas emuladas **no miden directamente la infraestructura del proveedor**.
- Los diagnósticos son **orientativos** y no confirman causas físicas exactas.
- La comparación entre proveedores solo es válida **controlando tecnología, zona y tamaño de muestra**.
- El sistema distingue entre mediciones observadas, inferencias del modelo y causas confirmadas.

---

## 📄 Referencias

1. ATT Bolivia — SIS ATT: https://sis.att.gob.bo/
2. ATT — Resolución ATT-DJ-RAR-TL LP 299/2018 (Estándar de Calidad)
3. UIT-T Recomendación Y.1540 (2019) — Parámetros de desempeño IP: https://www.itu.int/rec/T-REC-Y.1540/en
4. Pedregosa, F. et al. (2011). Scikit-learn: Machine Learning in Python. JMLR, 12, 2825–2830.

---

## 📝 Licencia

Proyecto académico de la **Universidad Mayor de San Andrés (UMSA)** · Carrera de Informática · La Paz, Bolivia · 2026.  
Uso educativo y de investigación. No sustituye auditorías o diagnósticos oficiales de telecomunicaciones.
