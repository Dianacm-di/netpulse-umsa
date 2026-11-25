/* NetPulse La Paz — Frontend PWA e Interfaz del Emulador */

const state = {
  catalogo: null,
  mapaData: null,
  analiticaData: null,
  iaData: null,
  selectedSectorId: "centro",
  runningTest: false,
};

const QOS_COLORS = {
  "Óptima": "#10b981",
  "Aceptable": "#38bdf8",
  "Degradada": "#f59e0b",
  "Crítica": "#ef4444",
  "Sin datos": "#475569",
};

function badgeClass(clase) {
  if (clase === "Óptima") return "qos-Optima";
  if (clase === "Crítica") return "qos-Critica";
  if (clase === "Degradada") return "qos-Degradada";
  return "qos-Aceptable";
}

function franjaTexto(hora) {
  if (hora < 6) return "Madrugada";
  if (hora < 12) return "Mañana";
  if (hora < 18) return "Tarde";
  return "Pico Nocturno";
}

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return res.json();
}

function fillSelect(selectEl, items, includeAllLabel = null) {
  selectEl.innerHTML = "";
  if (includeAllLabel) {
    const opt = document.createElement("option");
    opt.value = "todos";
    opt.textContent = includeAllLabel;
    selectEl.appendChild(opt);
  }
  items.forEach((item) => {
    const opt = document.createElement("option");
    if (typeof item === "string") {
      opt.value = item;
      opt.textContent = item;
    } else {
      opt.value = item.id;
      opt.textContent = item.altitud_m ? `${item.nombre} (${item.altitud_m} m)` : (item.label || item.nombre);
    }
    selectEl.appendChild(opt);
  });
}

// ======================================================
// Navegación por pestañas
// ======================================================
function switchTab(tabName) {
  document.querySelectorAll(".nav-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.toggle("active", p.id === `view-${tabName}`);
  });

  if (tabName === "mapa") loadMapa();
  if (tabName === "analitica") loadAnalitica();
  if (tabName === "ia") loadIA();
}

// ======================================================
// Emulador de prueba QoS (Paso a paso + Diagnóstico IA)
// ======================================================
function setGauge(value, maxVal, unit, phase, color = "#22d3ee") {
  const arc = document.getElementById("gauge-arc");
  const totalLen = typeof arc.getTotalLength === "function" ? arc.getTotalLength() : 378;
  const ratio = Math.max(0, Math.min(1, value / maxVal));
  arc.style.strokeDasharray = String(totalLen);
  arc.style.strokeDashoffset = String(totalLen * (1 - ratio));
  arc.style.stroke = color;
  document.getElementById("gauge-val").textContent = Number(value).toFixed(1);
  document.getElementById("gauge-unit").textContent = unit;
  document.getElementById("gauge-phase").textContent = phase;
}

function updateContextSummary() {
  const secId = document.getElementById("emu-sector").value;
  const isp = document.getElementById("emu-proveedor").value;
  const tec = document.getElementById("emu-tecnologia").value;
  const hora = Number(document.getElementById("emu-hora").value);
  const sec = state.catalogo?.sectores.find((s) => s.id === secId);
  document.getElementById("emu-hora-label").textContent = `${String(hora).padStart(2, "0")}:00 (${franjaTexto(hora)})`;
  document.getElementById("emu-context-summary").textContent = `${sec ? sec.nombre : secId} · ${isp} · ${tec} · ${String(hora).padStart(2, "0")}:00`;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function runEmulator(e) {
  e.preventDefault();
  if (state.runningTest) return;
  state.runningTest = true;

  const btn = document.getElementById("btn-ejecutar");
  btn.disabled = true;
  btn.textContent = "⏳ Ejecutando sondas emuladas...";

  const sector_id = document.getElementById("emu-sector").value;
  const proveedor = document.getElementById("emu-proveedor").value;
  const tecnologia = document.getElementById("emu-tecnologia").value;
  const hora = Number(document.getElementById("emu-hora").value);
  const escenario = document.getElementById("emu-escenario").value;
  const guardar = document.getElementById("emu-guardar").checked;

  const manual = escenario === "manual" ? {
    descarga_mbps: Number(document.getElementById("man-down").value),
    subida_mbps: Number(document.getElementById("man-up").value),
    latencia_ms: Number(document.getElementById("man-lat").value),
    jitter_ms: Number(document.getElementById("man-jit").value),
    perdida_pct: Number(document.getElementById("man-loss").value),
    dns_ms: Number(document.getElementById("man-dns").value),
  } : null;

  const badge = document.getElementById("emu-badge-clase");
  badge.className = "qos-badge qos-Aceptable";
  badge.textContent = "Midiendo...";

  ["m-down", "m-up", "m-lat", "m-jit", "m-loss", "m-dns"].forEach((id) => {
    document.getElementById(id).textContent = "...";
  });
  document.getElementById("ping-strip").innerHTML = '<span class="ping-chip">Iniciando sondas...</span>';

  const progress = document.getElementById("emu-progress");
  progress.style.width = "10%";

  try {
    // Solicitar resultado al backend y animar fases didácticamente
    const respPromise = fetchJSON("/api/emular", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sector_id, proveedor, tecnologia, hora, escenario, guardar, manual }),
    });

    // Fase 1: DNS
    setGauge(18, 150, "ms", "Fase 1/5: Resolviendo DNS...", "#38bdf8");
    progress.style.width = "22%";
    await sleep(320);

    const data = await respPromise;
    const t = data.telemetria;
    const d = data.diagnostico;

    document.getElementById("m-dns").textContent = t.dns_ms.toFixed(1);
    setGauge(t.dns_ms, 200, "ms DNS", "Fase 2/5: Midiendo Latencia RTT", "#38bdf8");
    progress.style.width = "42%";

    // Fase 2: Pings en vivo
    const strip = document.getElementById("ping-strip");
    strip.innerHTML = "";
    for (let i = 0; i < t.pings_detalle_ms.length; i++) {
      const p = t.pings_detalle_ms[i];
      const chip = document.createElement("span");
      if (p === null) {
        chip.className = "ping-chip lost";
        chip.textContent = `#${i + 1}: timeout`;
      } else {
        chip.className = "ping-chip";
        chip.textContent = `#${i + 1}: ${p} ms`;
        setGauge(p, 200, "ms RTT", `Fase 2/5: Sonda #${i + 1}/10`, "#22d3ee");
      }
      strip.appendChild(chip);
      await sleep(75);
    }

    document.getElementById("m-lat").textContent = t.latencia_ms.toFixed(1);
    document.getElementById("m-jit").textContent = t.jitter_ms.toFixed(1);
    document.getElementById("m-loss").textContent = t.perdida_pct.toFixed(2);
    progress.style.width = "64%";

    // Fase 3: Descarga animada
    for (let step = 1; step <= 6; step++) {
      const val = (t.descarga_mbps * step) / 6;
      setGauge(val, Math.max(100, t.descarga_mbps * 1.2), "Mbps", "Fase 4/5: Flujo de descarga", "#10b981");
      await sleep(70);
    }
    document.getElementById("m-down").textContent = t.descarga_mbps.toFixed(1);
    progress.style.width = "84%";

    // Fase 4: Subida
    for (let step = 1; step <= 4; step++) {
      const val = (t.subida_mbps * step) / 4;
      setGauge(val, Math.max(60, t.subida_mbps * 1.2), "Mbps", "Fase 5/5: Flujo de subida", "#22d3ee");
      await sleep(65);
    }
    document.getElementById("m-up").textContent = t.subida_mbps.toFixed(1);
    progress.style.width = "100%";

    // Mostrar resultado final en el medidor
    const colorFinal = QOS_COLORS[d.clase_predicha_ia] || "#22d3ee";
    setGauge(t.descarga_mbps, Math.max(100, t.descarga_mbps * 1.2), "Mbps ↓", `Clase IA: ${d.clase_predicha_ia}`, colorFinal);
    badge.className = `qos-badge ${badgeClass(d.clase_predicha_ia)}`;
    badge.textContent = `${d.clase_predicha_ia} (${d.confianza_modelo_pct}%)`;

    renderDiagnostico(d);
    await refreshHealth();
  } catch (err) {
    alert("Error ejecutando la prueba emulada: " + err.message);
  } finally {
    state.runningTest = false;
    btn.disabled = false;
    btn.textContent = "▶ Ejecutar Prueba Emulada QoS";
  }
}

function renderDiagnostico(d) {
  const panel = document.getElementById("diag-panel");
  panel.style.display = "block";
  document.getElementById("diag-origen").textContent = `Clasificación IA (${d.modelo_version}): ${d.origen_probable} · Riesgo horario zona: ${d.riesgo_esperado_zona}/100`;
  document.getElementById("diag-indice").textContent = `${d.indice_degradacion} / 100`;

  const hypoDiv = document.getElementById("diag-hipotesis");
  hypoDiv.innerHTML = "";
  if (d.hipotesis && d.hipotesis.length > 0) {
    d.hipotesis.forEach((h) => {
      const box = document.createElement("div");
      box.className = "hypo-box";
      box.innerHTML = `<strong>${h.ambito}</strong> <span style="color:var(--cyan);font-size:0.74rem;">[${h.nivel}]</span><div style="margin-top:3px;color:#cbd5e1;">${h.detalle}</div>`;
      hypoDiv.appendChild(box);
    });
  } else {
    const box = document.createElement("div");
    box.className = "hypo-box";
    box.style.borderLeftColor = "#10b981";
    box.innerHTML = `<strong>${d.origen_probable}</strong><div style="margin-top:3px;color:#cbd5e1;">${d.resumen_explicativo}</div>`;
    hypoDiv.appendChild(box);
  }

  const recsUl = document.getElementById("diag-recs");
  recsUl.innerHTML = "";
  d.recomendaciones.forEach((r) => {
    const li = document.createElement("li");
    li.textContent = r;
    recsUl.appendChild(li);
  });

  const probsDiv = document.getElementById("diag-probs");
  probsDiv.innerHTML = "";
  ["Óptima", "Aceptable", "Degradada", "Crítica"].forEach((cls) => {
    const p = Math.round((d.probabilidades_clase[cls] || 0) * 100);
    const row = document.createElement("div");
    row.className = "prob-bar-row";
    row.innerHTML = `
      <span>${cls}</span>
      <div class="prob-bar-bg"><div class="prob-bar-fg" style="width:${p}%;background:${QOS_COLORS[cls]};"></div></div>
      <span style="text-align:right;">${p}%</span>
    `;
    probsDiv.appendChild(row);
  });

  const aptDiv = document.getElementById("diag-aptitud");
  const labels = [
    ["videollamadas_hd", "Videollamada HD"],
    ["clases_en_linea", "Clases virtuales"],
    ["juegos_tiempo_real", "Tiempo real / Ping"],
    ["streaming_4k", "Streaming HD/4K"],
  ];
  aptDiv.innerHTML = "";
  labels.forEach(([k, label]) => {
    const ok = Boolean(d.apto_para[k]);
    const item = document.createElement("div");
    item.className = "aptitud-item";
    item.innerHTML = `<span>${label}</span><strong style="color:${ok ? "#34d399" : "#f87171"};">${ok ? "Apto" : "Limitado"}</strong>`;
    aptDiv.appendChild(item);
  });

  document.getElementById("diag-validez").textContent = d.aviso_validez;
}

// ======================================================
// Mapa Interactivo de La Paz
// ======================================================
function colorPorDegradacion(deg, n) {
  if (!n || n === 0) return "#475569";
  if (deg < 18) return "#10b981";
  if (deg < 35) return "#38bdf8";
  if (deg < 55) return "#f59e0b";
  return "#ef4444";
}

async function loadMapa() {
  const proveedor = document.getElementById("map-filter-isp").value || "todos";
  const tecnologia = document.getElementById("map-filter-tec").value || "todos";
  const franja = document.getElementById("map-filter-franja").value || "todos";

  const params = new URLSearchParams({
    proveedor,
    tecnologia,
    franja_horaria: franja === "todos" ? "todas" : franja,
  });

  const data = await fetchJSON(`/api/mapa?${params.toString()}`);
  state.mapaData = data;
  document.getElementById("map-total-pill").textContent = `${data.total_filtrado} muestras`;
  renderMapaSVG(data);
  selectSectorMap(state.selectedSectorId);
}

function renderMapaSVG(data) {
  const svg = document.getElementById("lapaz-map-svg");
  svg.innerHTML = "";

  const ns = "http://www.w3.org/2000/svg";

  // Curvas de nivel decorativas (La Hoyada vs Laderas vs Altiplano)
  const bgGroup = document.createElementNS(ns, "g");
  bgGroup.innerHTML = `
    <ellipse cx="450" cy="370" rx="340" ry="265" fill="none" stroke="rgba(148,163,184,0.08)" stroke-dasharray="6 6" />
    <ellipse cx="450" cy="365" rx="240" ry="185" fill="none" stroke="rgba(148,163,184,0.10)" stroke-dasharray="4 6" />
    <ellipse cx="450" cy="360" rx="140" ry="110" fill="none" stroke="rgba(34,211,238,0.12)" />
    <path d="M 380 250 Q 430 340 465 445 T 615 585" fill="none" stroke="rgba(56,189,248,0.22)" stroke-width="3" stroke-linecap="round" />
    <text x="58" y="38" fill="#64748b" font-size="12" font-weight="600">ALTIPLANO (~4,090 m)</text>
    <text x="645" y="38" fill="#64748b" font-size="12" font-weight="600">LADERAS NORTE/ESTE (~3,750 m)</text>
    <text x="655" y="705" fill="#64748b" font-size="12" font-weight="600">ZONA SUR / VALLE (~3,200 m)</text>
  `;
  svg.appendChild(bgGroup);

  // Polígonos de macrodistritos
  data.sectores.forEach((sec) => {
    const color = colorPorDegradacion(sec.degradacion_prom, sec.n_muestras);
    const poly = document.createElementNS(ns, "polygon");
    poly.setAttribute("points", sec.polygon);
    poly.setAttribute("fill", color);
    poly.setAttribute("fill-opacity", "0.34");
    poly.setAttribute("stroke", color);
    poly.setAttribute("stroke-width", "1.8");
    poly.setAttribute("class", `sector-poly ${sec.id === state.selectedSectorId ? "selected" : ""}`);
    poly.dataset.sectorId = sec.id;
    poly.addEventListener("click", () => selectSectorMap(sec.id));
    svg.appendChild(poly);
  });

  // Puntos aproximados anonimizados alrededor del centroide del sector
  const sectorMap = Object.fromEntries(data.sectores.map((s) => [s.id, s]));
  data.puntos_aproximados.forEach((pt, idx) => {
    const sec = sectorMap[pt.sector_id];
    if (!sec) return;
    // Dispersión determinística visual basada en id para no revelar domicilio
    const angle = (pt.id * 137.5) % 360;
    const rad = 10 + (pt.id % 28);
    const cx = sec.svg_x + Math.cos((angle * Math.PI) / 180) * rad;
    const cy = sec.svg_y + Math.sin((angle * Math.PI) / 180) * rad;
    const dot = document.createElementNS(ns, "circle");
    dot.setAttribute("cx", cx.toFixed(1));
    dot.setAttribute("cy", cy.toFixed(1));
    dot.setAttribute("r", "3.2");
    dot.setAttribute("fill", QOS_COLORS[pt.clase_qos] || "#94a3b8");
    dot.setAttribute("fill-opacity", "0.85");
    dot.setAttribute("pointer-events", "none");
    svg.appendChild(dot);
  });

  // Etiquetas de macrodistritos
  data.sectores.forEach((sec) => {
    const g = document.createElementNS(ns, "g");
    g.style.cursor = "pointer";
    g.addEventListener("click", () => selectSectorMap(sec.id));

    const pill = document.createElementNS(ns, "rect");
    pill.setAttribute("x", sec.svg_x - 56);
    pill.setAttribute("y", sec.svg_y - 16);
    pill.setAttribute("width", "112");
    pill.setAttribute("height", "34");
    pill.setAttribute("rx", "8");
    pill.setAttribute("fill", "rgba(8, 13, 23, 0.85)");
    pill.setAttribute("stroke", sec.id === state.selectedSectorId ? "#22d3ee" : "rgba(148,163,184,0.3)");

    const txt1 = document.createElementNS(ns, "text");
    txt1.setAttribute("x", sec.svg_x);
    txt1.setAttribute("y", sec.svg_y - 2);
    txt1.setAttribute("text-anchor", "middle");
    txt1.setAttribute("fill", "#f8fafc");
    txt1.setAttribute("font-size", "11");
    txt1.setAttribute("font-weight", "700");
    txt1.textContent = sec.nombre.replace(" (Comparativo)", "");

    const txt2 = document.createElementNS(ns, "text");
    txt2.setAttribute("x", sec.svg_x);
    txt2.setAttribute("y", sec.svg_y + 12);
    txt2.setAttribute("text-anchor", "middle");
    txt2.setAttribute("fill", "#94a3b8");
    txt2.setAttribute("font-size", "10");
    txt2.textContent = sec.n_muestras > 0 ? `${sec.descarga_prom} Mbps · n=${sec.n_muestras}` : "Sin datos";

    g.appendChild(pill);
    g.appendChild(txt1);
    g.appendChild(txt2);
    svg.appendChild(g);
  });
}

function selectSectorMap(sectorId) {
  state.selectedSectorId = sectorId;
  document.querySelectorAll(".sector-poly").forEach((p) => {
    p.classList.toggle("selected", p.dataset.sectorId === sectorId);
  });

  const sec = state.mapaData?.sectores.find((s) => s.id === sectorId);
  if (!sec) return;

  document.getElementById("det-nombre").textContent = sec.nombre;
  document.getElementById("det-meta").textContent = `${sec.macrodistrito} · ${sec.zona_topografica} · ${sec.altitud_m} m s. n. m.`;
  const badge = document.getElementById("det-clase");
  badge.className = `qos-badge ${badgeClass(sec.clase_dominante)}`;
  badge.textContent = sec.clase_dominante;

  document.getElementById("det-down").textContent = sec.n_muestras ? `${sec.descarga_prom}` : "--";
  document.getElementById("det-lat").textContent = sec.n_muestras ? `${sec.latencia_prom}` : "--";
  document.getElementById("det-jit-loss").textContent = sec.n_muestras ? `${sec.jitter_prom} / ${sec.perdida_prom}%` : "--";
  document.getElementById("det-deg").textContent = sec.n_muestras ? `${sec.degradacion_prom}` : "--";
  document.getElementById("det-n").textContent = sec.n_muestras;
  document.getElementById("det-confianza").textContent = sec.confianza;

  const distDiv = document.getElementById("det-dist");
  distDiv.innerHTML = "";
  ["Óptima", "Aceptable", "Degradada", "Crítica"].forEach((cls) => {
    const cnt = sec.conteo_clases[cls] || 0;
    const pct = sec.n_muestras ? Math.round((cnt / sec.n_muestras) * 100) : 0;
    const row = document.createElement("div");
    row.className = "prob-bar-row";
    row.innerHTML = `
      <span>${cls}</span>
      <div class="prob-bar-bg"><div class="prob-bar-fg" style="width:${pct}%;background:${QOS_COLORS[cls]};"></div></div>
      <span style="text-align:right;">${cnt}</span>
    `;
    distDiv.appendChild(row);
  });
}

// ======================================================
// Analítica y Gráficos Canvas
// ======================================================
async function loadAnalitica() {
  const sector_id = document.getElementById("ana-filter-sector").value || "todos";
  const proveedor = document.getElementById("ana-filter-isp").value || "todos";
  const tecnologia = document.getElementById("ana-filter-tec").value || "todos";

  const params = new URLSearchParams({ sector_id, proveedor, tecnologia });
  const [ana, hist] = await Promise.all([
    fetchJSON(`/api/analitica?${params.toString()}`),
    fetchJSON(`/api/mediciones?${params.toString()}&limit=30`),
  ]);

  state.analiticaData = ana;
  const k = ana.kpis;
  document.getElementById("kpi-n").textContent = k.n_muestras;
  document.getElementById("kpi-down").textContent = `${k.descarga_prom} Mbps`;
  document.getElementById("kpi-lat").textContent = `${k.latencia_prom} ms`;
  document.getElementById("kpi-jit").textContent = `${k.jitter_prom} ms`;
  document.getElementById("kpi-loss").textContent = `${k.perdida_prom}%`;
  document.getElementById("kpi-deg").textContent = `${k.degradacion_prom}/100`;

  drawHourlyChart(ana.curva_horaria);
  drawTechChart(ana.por_tecnologia);
  renderProveedorTable(ana.por_proveedor);
  renderHistorialTable(hist.items);
}

function setupHiDPICanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(320, rect.width || 560);
  const height = rect.height || 280;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  return { ctx, width, height };
}

function drawHourlyChart(curva) {
  const canvas = document.getElementById("chart-horaria");
  const { ctx, width, height } = setupHiDPICanvas(canvas);
  ctx.clearRect(0, 0, width, height);

  const pad = { top: 24, right: 20, bottom: 38, left: 42 };
  const w = width - pad.left - pad.right;
  const h = height - pad.top - pad.bottom;

  // Grid Y
  ctx.strokeStyle = "rgba(148,163,184,0.14)";
  ctx.fillStyle = "#94a3b8";
  ctx.font = "11px system-ui";
  for (let v = 0; v <= 100; v += 25) {
    const y = pad.top + h - (v / 100) * h;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(pad.left + w, y);
    ctx.stroke();
    ctx.fillText(String(v), 10, y + 4);
  }

  const xFor = (i) => pad.left + (i / 23) * w;
  const yFor = (val) => pad.top + h - (val / 100) * h;

  // Banda de incertidumbre IA
  ctx.beginPath();
  curva.forEach((pt, i) => {
    const x = xFor(i);
    const y = yFor(pt.banda_max);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  for (let i = curva.length - 1; i >= 0; i--) {
    ctx.lineTo(xFor(i), yFor(curva[i].banda_min));
  }
  ctx.closePath();
  ctx.fillStyle = "rgba(34, 211, 238, 0.14)";
  ctx.fill();

  // Línea predicción IA
  ctx.beginPath();
  curva.forEach((pt, i) => {
    const x = xFor(i);
    const y = yFor(pt.riesgo_predicho_ia);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = "#22d3ee";
  ctx.lineWidth = 2.5;
  ctx.stroke();

  // Puntos observados
  curva.forEach((pt, i) => {
    if (pt.degradacion_observada !== null) {
      const x = xFor(i);
      const y = yFor(pt.degradacion_observada);
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = "#f59e0b";
      ctx.fill();
    }
    if (i % 3 === 0) {
      ctx.fillStyle = "#94a3b8";
      ctx.fillText(`${String(i).padStart(2, "0")}h`, xFor(i) - 10, height - 12);
    }
  });

  // Leyenda
  ctx.fillStyle = "#22d3ee";
  ctx.fillRect(pad.left, 6, 14, 4);
  ctx.fillStyle = "#cbd5e1";
  ctx.fillText("Predicción IA + incertidumbre", pad.left + 20, 12);

  ctx.beginPath();
  ctx.arc(pad.left + 215, 8, 4, 0, Math.PI * 2);
  ctx.fillStyle = "#f59e0b";
  ctx.fill();
  ctx.fillStyle = "#cbd5e1";
  ctx.fillText("Promedio observado", pad.left + 224, 12);
}

function drawTechChart(items) {
  const canvas = document.getElementById("chart-tecnologia");
  const { ctx, width, height } = setupHiDPICanvas(canvas);
  ctx.clearRect(0, 0, width, height);

  if (!items || items.length === 0) {
    ctx.fillStyle = "#94a3b8";
    ctx.font = "13px system-ui";
    ctx.fillText("Sin datos para el filtro actual", 24, 40);
    return;
  }

  const maxDown = Math.max(100, ...items.map((x) => x.descarga_prom));
  const pad = { top: 20, right: 20, bottom: 20, left: 145 };
  const w = width - pad.left - pad.right;
  const rowH = Math.min(46, (height - pad.top - pad.bottom) / items.length);

  items.forEach((it, idx) => {
    const y = pad.top + idx * rowH;
    const barW = (it.descarga_prom / maxDown) * w;

    ctx.fillStyle = "#cbd5e1";
    ctx.font = "11px system-ui";
    const shortName = it.tecnologia.replace(" (FTTH)", "").slice(0, 19);
    ctx.fillText(shortName, 8, y + 18);

    ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
    ctx.fillRect(pad.left, y + 6, w, 18);

    ctx.fillStyle = "#10b981";
    ctx.fillRect(pad.left, y + 6, barW, 18);

    ctx.fillStyle = "#f8fafc";
    ctx.fillText(`${it.descarga_prom} Mbps (n=${it.n})`, pad.left + 8, y + 19);
  });
}

function renderProveedorTable(items) {
  const tbody = document.getElementById("tbl-proveedores");
  tbody.innerHTML = "";
  items.forEach((p) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${p.proveedor}</strong></td>
      <td>${p.n}</td>
      <td>${p.descarga_prom} Mbps</td>
      <td>${p.latencia_prom} ms</td>
      <td>${p.perdida_prom}%</td>
      <td style="font-size:0.76rem;color:var(--text-muted);">${p.confianza}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderHistorialTable(items) {
  const tbody = document.getElementById("tbl-historial");
  tbody.innerHTML = "";
  items.forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.sector_nombre.replace(" (Comparativo)", "")}</td>
      <td>${String(r.hora).padStart(2, "0")}:00</td>
      <td>${r.proveedor}<div style="font-size:0.72rem;color:var(--text-dim);">${r.tecnologia}</div></td>
      <td>${r.descarga_mbps} Mbps / ${r.latencia_ms} ms</td>
      <td><span class="qos-badge ${badgeClass(r.clase_qos)}" style="font-size:0.72rem;">${r.clase_qos}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// ======================================================
// Laboratorio IA
// ======================================================
async function loadIA() {
  const data = await fetchJSON("/api/ia/estado");
  state.iaData = data;
  renderIA(data);
}

function renderIA(data) {
  document.getElementById("ia-version").textContent = data.version;
  document.getElementById("ia-acc").textContent = `${(data.accuracy * 100).toFixed(1)}%`;
  document.getElementById("ia-f1").textContent = data.f1_macro.toFixed(3);
  document.getElementById("ia-mae").textContent = `${data.mae_degradacion} pts`;
  document.getElementById("ia-rmse").textContent = `${data.rmse_degradacion} pts`;

  // Matriz de confusión
  const cmWrap = document.getElementById("ia-cm-wrap");
  const labels = data.labels;
  let html = `<table class="cm-table"><thead><tr><th>Real \\ Pred</th>${labels.map((l) => `<th>${l}</th>`).join("")}</tr></thead><tbody>`;
  data.matriz_confusion.forEach((row, i) => {
    const maxRow = Math.max(1, ...row);
    html += `<tr><th>${labels[i]}</th>`;
    row.forEach((val, j) => {
      const alpha = (val / maxRow) * 0.42;
      const bg = i === j ? `rgba(16,185,129,${0.12 + alpha})` : `rgba(245,158,11,${alpha})`;
      html += `<td style="background:${bg};font-weight:${i === j ? 700 : 400};">${val}</td>`;
    });
    html += `</tr>`;
  });
  html += `</tbody></table>`;
  cmWrap.innerHTML = html;

  // Importancia de variables
  const impDiv = document.getElementById("ia-importancias");
  impDiv.innerHTML = "";
  data.importancia_variables.forEach((v) => {
    const pct = Math.round(v.importancia * 100);
    const row = document.createElement("div");
    row.className = "prob-bar-row";
    row.style.gridTemplateColumns = "165px 1fr 48px";
    row.innerHTML = `
      <span>${v.variable}</span>
      <div class="prob-bar-bg"><div class="prob-bar-fg" style="width:${pct}%;background:linear-gradient(90deg,#22d3ee,#10b981);"></div></div>
      <span style="text-align:right;">${pct}%</span>
    `;
    impDiv.appendChild(row);
  });

  // Reporte por clase
  const tbl = document.getElementById("tbl-ia-clases");
  tbl.innerHTML = "";
  Object.entries(data.reporte_por_clase).forEach(([cls, m]) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><span class="qos-badge ${badgeClass(cls)}">${cls}</span></td>
      <td>${m.precision.toFixed(2)}</td>
      <td>${m.recall.toFixed(2)}</td>
      <td>${m.f1.toFixed(2)}</td>
      <td>${m.support}</td>
    `;
    tbl.appendChild(tr);
  });
}

async function refreshHealth() {
  const h = await fetchJSON("/api/health");
  document.getElementById("header-status").textContent = `Modelo ${h.version_modelo} activo · ${h.total_mediciones} registros`;
  document.getElementById("badge-total-registros").textContent = `${h.total_mediciones} registros`;
}

// ======================================================
// Inicialización
// ======================================================
async function init() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => null);
  }

  // Registrar eventos UI primero para garantizar interactividad
  document.querySelectorAll(".nav-btn").forEach((b) => {
    b.addEventListener("click", () => switchTab(b.dataset.tab));
  });

  ["emu-sector", "emu-proveedor", "emu-tecnologia", "emu-hora"].forEach((id) => {
    document.getElementById(id).addEventListener("input", updateContextSummary);
  });

  document.getElementById("emu-escenario").addEventListener("change", (ev) => {
    document.getElementById("manual-box").style.display = ev.target.value === "manual" ? "block" : "none";
  });

  document.getElementById("form-emulador").addEventListener("submit", runEmulator);
  document.getElementById("btn-map-refresh").addEventListener("click", loadMapa);
  document.getElementById("btn-ana-refresh").addEventListener("click", loadAnalitica);

  document.getElementById("btn-emular-sector").addEventListener("click", () => {
    document.getElementById("emu-sector").value = state.selectedSectorId;
    updateContextSummary();
    switchTab("emulador");
  });

  document.getElementById("btn-reentrenar").addEventListener("click", async () => {
    const msg = document.getElementById("ia-train-msg");
    msg.textContent = "Re-entrenando Random Forest...";
    const res = await fetchJSON("/api/ia/reentrenar", { method: "POST" });
    renderIA(res.metricas);
    await refreshHealth();
    msg.textContent = `Actualizado (${res.metricas.version}) con ${res.metricas.n_registros} registros.`;
  });

  document.getElementById("btn-reset-piloto").addEventListener("click", async () => {
    const msg = document.getElementById("ia-train-msg");
    msg.textContent = "Restaurando dataset piloto...";
    const res = await fetchJSON("/api/piloto/reset", { method: "POST" });
    renderIA(res.metricas);
    await refreshHealth();
    msg.textContent = res.mensaje;
  });

  try {
    const cat = await fetchJSON("/api/catalogo");
    state.catalogo = cat;

    fillSelect(document.getElementById("emu-sector"), cat.sectores);
    document.getElementById("emu-sector").value = "centro";
    fillSelect(document.getElementById("emu-proveedor"), cat.proveedores);
    fillSelect(document.getElementById("emu-tecnologia"), cat.tecnologias);

    // Filtros de Mapa y Analítica
    fillSelect(document.getElementById("map-filter-isp"), cat.proveedores, "Todos los proveedores");
    fillSelect(document.getElementById("map-filter-tec"), cat.tecnologias, "Todas las tecnologías");
    fillSelect(document.getElementById("map-filter-franja"), cat.franjas_horarias, "Todas las franjas");

    fillSelect(document.getElementById("ana-filter-sector"), cat.sectores, "Todos los macrodistritos");
    fillSelect(document.getElementById("ana-filter-isp"), cat.proveedores, "Todos los proveedores");
    fillSelect(document.getElementById("ana-filter-tec"), cat.tecnologias, "Todas las tecnologías");

    updateContextSummary();
    await refreshHealth();
  } catch (err) {
    document.getElementById("header-status").textContent = "Error cargando catálogo: " + err.message;
  }
}

window.addEventListener("DOMContentLoaded", init);
