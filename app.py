import base64
import datetime
import json
import math
import os
import time
from io import BytesIO

import ee
import folium
import matplotlib
import numpy as np
import requests
import streamlit as st
from matplotlib.colors import Normalize
from PIL import Image
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Virtual Harvest · Satellite Reliability",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- DICCIONARIO DE TRADUCCIONES (ES / EN) ---
TEXTOS = {
    "es": {
        "badge": "🛰️ Teledetección Sentinel-2 · Google Earth Engine",
        "title": "🌾 Virtual Harvest · Monitor de Fiabilidad Satelital",
        "subtitle": "Evalúa la aptitud y salud de tus potreros combinando <b>4 indicadores multiespectrales</b> de alta resolución sobre imagen aérea real.",
        "sidebar_title": "## ⚙️ Configuración de Análisis",
        "sec1_header": "📍 1. Ubicación desde Google Maps",
        "sec1_caption": "Haz clic derecho en Google Maps, copia las coordenadas y pégalas aquí:",
        "coord_label": "Coordenadas (Latitud, Longitud)",
        "sec2_header": "📐 2. Tamaño del Área a Analizar",
        "unit_label": "Unidad de medida",
        "units": [
            "Hectáreas (superficie total)",
            "Metros (lado del cuadrado)",
            "Kilómetros (lado del cuadrado)",
        ],
        "qty_label": "Cantidad",
        "sec3_header": "📅 3. Rango de Fechas",
        "date_from": "Desde",
        "date_to": "Hasta",
        "sec4_header": "🎨 4. Visualización en Mapa",
        "opacity_label": "Opacidad de capa de colores",
        "sec5_header": "⚖️ 5. Importancia de cada dato (%)",
        "w_vigor": "🌿 Vigor Vegetal (NDVI)",
        "w_moisture": "💧 Humedad en Cultivo (NDMI)",
        "w_chloro": "🍃 Clorofila / Nitrógeno (NDRE)",
        "w_dry": "☀️ Terreno Libre Agua/Nubes (NDWI)",
        "preview_title": "📐 **Vista previa de parcela:**",
        "preview_sq": "• Cuadrado de **{lado:.0f} m × {lado:.0f} m**",
        "preview_ha": "• Superficie total: **{ha:.2f} ha**",
        "coord_err_short": "Formato inválido. Usa ejemplo: -42.15, -73.50",
        "weight_exact": "✅ Ponderación exacta: **100%**",
        "weight_norm": "ℹ️ Suma actual: **{suma}%** (se normalizará a 100%)",
        "btn_run": "🚀 Calcular Fiabilidad del Terreno",
        "err_zero_weights": "Debes asignar al menos un porcentaje mayor a 0 en los criterios.",
        "err_dates": "La fecha 'Desde' no puede ser posterior a la fecha 'Hasta'.",
        "err_coords": "Por favor revisa las coordenadas. Deben tener el formato: Latitud, Longitud (ej. -42.15, -73.5)",
        "loader_title": "🛰️ Escaneo Orbital Sentinel-2 en Curso",
        "loader_sub": "Analizando {ha:.1f} ha ({lado:.0f}m × {lado:.0f}m) · Resolución espacial 10m/px",
        "step1": "🔐 Estableciendo enlace satelital seguro con Google Earth Engine...",
        "step2": "📡 Filtrando pasadas orbitales Sentinel-2 y limpiando nubosidad...",
        "step3": "🧬 Procesando bandas espectrales (NDVI · NDMI · NDRE · NDWI)...",
        "step4": "⚖️ Ponderando {n} escenas satelitales y renderizando mapa...",
        "step_done": "✨ ¡Escaneo orbital completado! ({n} escenas procesadas)",
        "err_process": "Ocurrió un error al procesar los datos: {e}",
        "err_no_imgs": "No se encontraron imágenes Sentinel-2 disponibles (con <60% de nubes) para esa ubicación y rango de fechas. Intenta ampliar las fechas.",
        "warn_all_clouds": "Todos los píxeles de la parcela estaban cubiertos por nubes en las fechas seleccionadas. Prueba ampliar el rango de fechas.",
        "diag_title": "### 📊 Diagnóstico de Parcela · {ha:.1f} ha ({lado:.0f}m × {lado:.0f}m)",
        "m1_label": "🌱 Fiabilidad Global",
        "m1_delta": "Índice compuesto",
        "m2_label": "✅ Superficie Óptima",
        "m2_delta": "Score > 70%",
        "m3_label": "⚠️ Superficie Crítica",
        "m3_delta": "Score < 40%",
        "m4_label": "🛰️ Escenas Analizadas",
        "m4_val": "{n} img",
        "m4_delta": "{ha:.1f} ha ({lado:.0f}m lado)",
        "alert_opt": "🌿 Estado Óptimo: El terreno presenta condiciones favorables y equilibradas en los 4 indicadores multiespectrales.",
        "alert_mod": "🌾 Estado Moderado: Se detectan sectores con posible estrés hídrico o vigor medio que requieren monitoreo en terreno.",
        "alert_crit": "🚨 Estado Crítico: Baja fiabilidad detectada. Se recomienda revisar humedad del suelo, niveles de nitrógeno o anegamiento.",
        "layer_sat": "Google Satélite",
        "layer_border": "Límite Parcela",
        "layer_heat": "Fiabilidad de Terreno",
        "legend_bottom": "🟢 **70% - 100%**: Fiabilidad Alta / Óptima  \n🟡 **45% - 69%**: Fiabilidad Media / Aceptable  \n🔴 **0% - 44%**: Zona Crítica / Revisar Terreno",
        "guide_title": "### 🧭 Guía de Lectura",
        "guide_body": "🟢 **70% - 100% (Óptimo)**  \nTerreno altamente fiable, vigoroso y con buen balance hídrico.\n\n🟡 **45% - 69% (Moderado)**  \nRendimiento aceptable; conviene vigilar su evolución en los próximos días.\n\n🔴 **0% - 44% (Crítico)**  \nZona problema: posible suelo desnudo, sequía, falta de nitrógeno o exceso de agua.",
        "tech_title": "### 📋 Ficha Técnica",
        "tech_body": "Dimensiones reales:\n- Ancho: {lado:.0f} m\n- Alto: {lado:.0f} m\n- Superficie: {ha:.2f} ha\n- Escenas Sentinel-2: {n}\n\nPesos aplicados:\n- 🌿 Vigor: {w1:.0f}%\n- 💧 Humedad: {w2:.0f}%\n- 🍃 Clorofila: {w3:.0f}%\n- ☀️ Drenaje: {w4:.0f}%",
        "btn_download": "📥 Descargar Mapa (PNG)",
        "file_prefix": "virtual_harvest_parcela",
        "empty_title": "🛰️ Listo para analizar tu predio",
        "empty_body": "Configura las coordenadas, el tamaño y los pesos en el panel izquierdo, luego presiona <b>\"Calcular Fiabilidad del Terreno\"</b>.",
    },
    "en": {
        "badge": "🛰️ Sentinel-2 Remote Sensing · Google Earth Engine",
        "title": "🌾 Virtual Harvest · Satellite Reliability Monitor",
        "subtitle": "Assess field suitability and crop health by combining <b>4 multispectral indicators</b> at high resolution over real satellite imagery.",
        "sidebar_title": "## ⚙️ Analysis Settings",
        "sec1_header": "📍 1. Location from Google Maps",
        "sec1_caption": "Right-click on Google Maps, copy the coordinates, and paste them here:",
        "coord_label": "Coordinates (Latitude, Longitude)",
        "sec2_header": "📐 2. Area Size to Analyze",
        "unit_label": "Unit of measurement",
        "units": [
            "Hectares (total surface)",
            "Meters (square side)",
            "Kilometers (square side)",
        ],
        "qty_label": "Amount",
        "sec3_header": "📅 3. Date Range",
        "date_from": "From",
        "date_to": "To",
        "sec4_header": "🎨 4. Map Visualization",
        "opacity_label": "Color layer opacity",
        "sec5_header": "⚖️ 5. Indicator Weights (%)",
        "w_vigor": "🌿 Plant Vigor (NDVI)",
        "w_moisture": "💧 Crop Moisture (NDMI)",
        "w_chloro": "🍃 Chlorophyll / Nitrogen (NDRE)",
        "w_dry": "☀️ Water/Cloud-Free Ground (NDWI)",
        "preview_title": "📐 **Field preview:**",
        "preview_sq": "• Square of **{lado:.0f} m × {lado:.0f} m**",
        "preview_ha": "• Total area: **{ha:.2f} ha**",
        "coord_err_short": "Invalid format. Example: -42.15, -73.50",
        "weight_exact": "✅ Exact weighting: **100%**",
        "weight_norm": "ℹ️ Current sum: **{suma}%** (will normalize to 100%)",
        "btn_run": "🚀 Calculate Field Reliability",
        "err_zero_weights": "You must assign at least one percentage greater than 0 to the criteria.",
        "err_dates": "The 'From' date cannot be later than the 'To' date.",
        "err_coords": "Please check the coordinates. Format must be: Latitude, Longitude (e.g. -42.15, -73.5)",
        "loader_title": "🛰️ Sentinel-2 Orbital Scan in Progress",
        "loader_sub": "Scanning {ha:.1f} ha ({lado:.0f}m × {lado:.0f}m) · 10m/px spatial resolution",
        "step1": "🔐 Establishing secure satellite link with Google Earth Engine...",
        "step2": "📡 Filtering Sentinel-2 orbital passes & masking cloud cover...",
        "step3": "🧬 Computing spectral bands (NDVI · NDMI · NDRE · NDWI)...",
        "step4": "⚖️ Weighting {n} satellite scenes and rendering heatmap...",
        "step_done": "✨ Orbital scan complete! ({n} scenes processed)",
        "err_process": "An error occurred while processing the data: {e}",
        "err_no_imgs": "No Sentinel-2 images available (<60% cloud cover) were found for this location and date range. Try expanding the dates.",
        "warn_all_clouds": "All pixels in the field were covered by clouds during the selected dates. Try expanding the date range.",
        "diag_title": "### 📊 Field Diagnostics · {ha:.1f} ha ({lado:.0f}m × {lado:.0f}m)",
        "m1_label": "🌱 Global Reliability",
        "m1_delta": "Composite index",
        "m2_label": "✅ Optimal Area",
        "m2_delta": "Score > 70%",
        "m3_label": "⚠️ Critical Area",
        "m3_delta": "Score < 40%",
        "m4_label": "🛰️ Analyzed Scenes",
        "m4_val": "{n} img",
        "m4_delta": "{ha:.1f} ha ({lado:.0f}m side)",
        "alert_opt": "🌿 Optimal Status: The field shows favorable and balanced conditions across all 4 multispectral indicators.",
        "alert_mod": "🌾 Moderate Status: Sectors with potential water stress or medium vigor detected; field monitoring recommended.",
        "alert_crit": "🚨 Critical Status: Low reliability detected. Check soil moisture, nitrogen levels, or waterlogging.",
        "layer_sat": "Google Satellite",
        "layer_border": "Field Boundary",
        "layer_heat": "Field Reliability",
        "legend_bottom": "🟢 **70% - 100%**: High / Optimal Reliability  \n🟡 **45% - 69%**: Medium / Acceptable Reliability  \n🔴 **0% - 44%**: Critical Zone / Inspect Field",
        "guide_title": "### 🧭 Reading Guide",
        "guide_body": "🟢 **70% - 100% (Optimal)**  \nHighly reliable, vigorous terrain with good water balance.\n\n🟡 **45% - 69% (Moderate)**  \nAcceptable performance; monitor its evolution over the coming days.\n\n🔴 **0% - 44% (Critical)**  \nProblem zone: possible bare soil, drought, nitrogen deficiency, or excess water.",
        "tech_title": "### 📋 Technical Sheet",
        "tech_body": "Actual dimensions:\n- Width: {lado:.0f} m\n- Height: {lado:.0f} m\n- Area: {ha:.2f} ha\n- Sentinel-2 scenes: {n}\n\nApplied weights:\n- 🌿 Vigor: {w1:.0f}%\n- 💧 Moisture: {w2:.0f}%\n- 🍃 Chlorophyll: {w3:.0f}%\n- ☀️ Drainage: {w4:.0f}%",
        "btn_download": "📥 Download Map (PNG)",
        "file_prefix": "virtual_harvest_field",
        "empty_title": "🛰️ Ready to analyze your field",
        "empty_body": "Set the coordinates, area size, and weights in the left panel, then click <b>\"Calculate Field Reliability\"</b>.",
    },
}

# --- ESTILOS VISUALES ---
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    .stApp {
        background-color: #f8fbf9;
    }
    .header-agro {
        background: linear-gradient(125deg, #081c15 0%, #1b4332 45%, #2d6a4f 85%, #40916c 100%);
        padding: 2rem 2.5rem;
        border-radius: 18px;
        color: white;
        margin-bottom: 1.8rem;
        box-shadow: 0 10px 25px rgba(27, 67, 50, 0.22);
        border: 1px solid rgba(255, 255, 255, 0.12);
        position: relative;
        overflow: hidden;
    }
    .header-badge {
        display: inline-block;
        background: rgba(216, 243, 220, 0.18);
        color: #b7e4c7;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 0.6rem;
        border: 1px solid rgba(183, 228, 199, 0.3);
    }
    .header-agro h1 {
        color: #ffffff !important;
        margin: 0;
        font-size: 2.15rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }
    .header-agro p {
        color: #d8f3dc;
        margin: 0.5rem 0 0 0;
        font-size: 1.05rem;
        max-width: 780px;
        line-height: 1.5;
    }
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2d6a4f 0%, #1b4332 100%);
        border: none;
        color: white;
        font-weight: 700;
        font-size: 1rem;
        border-radius: 12px;
        padding: 0.75rem 1.8rem;
        box-shadow: 0 6px 16px rgba(45, 106, 79, 0.28);
        transition: all 0.25s ease;
        width: 100%;
    }
    div.stButton > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 22px rgba(27, 67, 50, 0.38);
        background: linear-gradient(135deg, #40916c 0%, #2d6a4f 100%);
    }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e2efe7;
        border-top: 4px solid #2d6a4f;
        padding: 18px 20px;
        border-radius: 14px;
        box-shadow: 0 4px 12px rgba(27, 67, 50, 0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 20px rgba(27, 67, 50, 0.1);
    }
    div[data-testid="stMetricLabel"] {
        color: #4a6b58 !important;
        font-weight: 600;
        font-size: 0.92rem;
    }
    div[data-testid="stMetricValue"] {
        color: #1b4332 !important;
        font-weight: 800;
        font-size: 1.85rem;
    }
    section[data-testid="stSidebar"] {
        background-color: #f0f7f3;
        border-right: 1px solid #d8f3dc;
    }
    section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {
        color: #1b4332 !important;
        font-weight: 700;
        font-size: 1.05rem;
    }
    .empty-state {
        background: #ffffff;
        border: 2px dashed #b7e4c7;
        border-radius: 16px;
        padding: 3rem 2rem;
        text-align: center;
        color: #2d6a4f;
        margin-top: 1.5rem;
    }

    /* --- BARRA DE CARGA ÉPICA ORBITAL --- */
    @keyframes pulseRadar {
        0% { transform: scale(0.92); box-shadow: 0 0 0 0 rgba(82, 183, 136, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 14px rgba(82, 183, 136, 0); }
        100% { transform: scale(0.92); box-shadow: 0 0 0 0 rgba(82, 183, 136, 0); }
    }
    @keyframes shimmerBeam {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
    @keyframes floatSat {
        0%, 100% { transform: translateY(0px) rotate(0deg); }
        50% { transform: translateY(-4px) rotate(6deg); }
    }
    .epic-loader-card {
        background: linear-gradient(135deg, #071912 0%, #133124 55%, #1d4d38 100%);
        border: 1px solid rgba(116, 198, 157, 0.35);
        border-radius: 18px;
        padding: 1.6rem 2rem;
        margin: 1.4rem 0;
        box-shadow: 0 16px 36px rgba(8, 28, 21, 0.26);
        color: #ffffff;
        position: relative;
        overflow: hidden;
    }
    .epic-loader-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 1rem;
    }
    .epic-loader-left {
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .radar-orb {
        width: 46px;
        height: 46px;
        border-radius: 50%;
        background: radial-gradient(circle at 30% 30%, #74c69d, #2d6a4f);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.35rem;
        animation: pulseRadar 1.8s infinite;
        flex-shrink: 0;
    }
    .sat-icon {
        display: inline-block;
        animation: floatSat 2.2s ease-in-out infinite;
    }
    .epic-loader-title {
        font-size: 1.15rem;
        font-weight: 800;
        color: #ffffff;
        margin: 0;
        letter-spacing: -0.01em;
    }
    .epic-loader-sub {
        font-size: 0.85rem;
        color: #b7e4c7;
        margin: 2px 0 0 0;
    }
    .epic-pct-badge {
        background: rgba(116, 198, 157, 0.16);
        border: 1px solid rgba(116, 198, 157, 0.45);
        color: #95d5b2;
        font-weight: 800;
        font-size: 1.2rem;
        padding: 6px 14px;
        border-radius: 12px;
        font-variant-numeric: tabular-nums;
    }
    .epic-track {
        width: 100%;
        height: 14px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 999px;
        overflow: hidden;
        box-shadow: inset 0 2px 5px rgba(0, 0, 0, 0.4);
        margin-bottom: 0.85rem;
    }
    .epic-fill {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(
            90deg,
            #40916c 0%,
            #74c69d 30%,
            #d8f3dc 50%,
            #52b788 70%,
            #40916c 100%
        );
        background-size: 200% 100%;
        animation: shimmerBeam 1.6s linear infinite;
        box-shadow: 0 0 14px rgba(116, 198, 157, 0.85);
        transition: width 0.45s cubic-bezier(0.22, 1, 0.36, 1);
    }
    .epic-step-text {
        font-size: 0.92rem;
        font-weight: 600;
        color: #d8f3dc;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }
</style>
""",
    unsafe_allow_html=True,
)


def renderizar_barra_epica(contenedor, pct, titulo, subtitulo, paso_actual):
    """Dibuja o actualiza la tarjeta de carga orbital animada."""
    contenedor.markdown(
        f"""
        <div class="epic-loader-card">
            <div class="epic-loader-top">
                <div class="epic-loader-left">
                    <div class="radar-orb"><span class="sat-icon">🛰️</span></div>
                    <div>
                        <p class="epic-loader-title">{titulo}</p>
                        <p class="epic-loader-sub">{subtitulo}</p>
                    </div>
                </div>
                <div class="epic-pct-badge">{pct}%</div>
            </div>
            <div class="epic-track">
                <div class="epic-fill" style="width: {pct}%;"></div>
            </div>
            <p class="epic-step-text">{paso_actual}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --- SELECTOR DE IDIOMA EN PANEL LATERAL ---
idioma_sel = st.sidebar.radio(
    "🌐 Idioma / Language",
    ["Español", "English"],
    horizontal=True,
)
lang = "es" if idioma_sel == "Español" else "en"
t = TEXTOS[lang]

# --- ENCABEZADO ---
st.markdown(
    f"""
<div class="header-agro">
    <div class="header-badge">{t["badge"]}</div>
    <h1>{t["title"]}</h1>
    <p>{t["subtitle"]}</p>
</div>
""",
    unsafe_allow_html=True,
)

# --- PANEL LATERAL ---
st.sidebar.markdown(t["sidebar_title"])
st.sidebar.divider()

st.sidebar.header(t["sec1_header"])
st.sidebar.caption(t["sec1_caption"])
coord_texto = st.sidebar.text_input(t["coord_label"], value="-42.1500, -73.5000")

st.sidebar.header(t["sec2_header"])
unidad_idx = st.sidebar.selectbox(
    t["unit_label"],
    range(len(t["units"])),
    format_func=lambda i: t["units"][i],
)
unidad_nombre_corto = t["units"][unidad_idx].split()[0]
valor_tamano = st.sidebar.number_input(
    f"{t['qty_label']} ({unidad_nombre_corto})",
    min_value=0.1,
    value=25.0,
    step=1.0,
)

st.sidebar.header(t["sec3_header"])
col_f1, col_f2 = st.sidebar.columns(2)
with col_f1:
    fecha_inicio = st.date_input(t["date_from"], value=datetime.date(2026, 10, 15))
with col_f2:
    fecha_fin = st.date_input(t["date_to"], value=datetime.date(2026, 11, 12))

st.sidebar.header(t["sec4_header"])
transparencia = st.sidebar.slider(t["opacity_label"], 0.0, 1.0, 0.65, step=0.05)

st.sidebar.header(t["sec5_header"])
p_vigor = st.sidebar.slider(t["w_vigor"], 0, 100, 35)
p_humedad = st.sidebar.slider(t["w_moisture"], 0, 100, 30)
p_clorofila = st.sidebar.slider(t["w_chloro"], 0, 100, 20)
p_calidad = st.sidebar.slider(t["w_dry"], 0, 100, 15)


# --- CONEXIÓN Y DESCARGA CON GOOGLE EARTH ENGINE ---
@st.cache_resource
def inicializar_gee():
    """
    Inicializa Google Earth Engine de forma silenciosa usando:
    1. Streamlit Secrets (cuando está desplegado en la web).
    2. Archivo local 'credenciales-gee.json' (cuando corre en PC).
    """
    info_cuenta = None

    try:
        if "gee_credentials" in st.secrets:
            info_cuenta = dict(st.secrets["gee_credentials"])
    except Exception:
        pass

    if info_cuenta is None:
        if not os.path.exists("credenciales-gee.json"):
            st.error(
                "No se encontró 'credenciales-gee.json' ni '[gee_credentials]' en Streamlit Secrets."
            )
            st.stop()
        with open("credenciales-gee.json", encoding="utf-8") as f:
            info_cuenta = json.load(f)

    credenciales = ee.ServiceAccountCredentials(
        info_cuenta["client_email"], key_data=json.dumps(info_cuenta)
    )
    ee.Initialize(
        credentials=credenciales,
        project=info_cuenta["project_id"],
    )
    return True


def enmascarar_nubes_s2(imagen):
    """Enmascara nubes y cirros usando la banda QA60 de Sentinel-2."""
    qa = imagen.select("QA60")
    mascara_nubes = 1 << 10
    mascara_cirros = 1 << 11
    mascara = qa.bitwiseAnd(mascara_nubes).eq(0).And(qa.bitwiseAnd(mascara_cirros).eq(0))
    return imagen.updateMask(mascara).divide(10000)


@st.cache_data(ttl=3600, show_spinner=False)
def obtener_indices_gee(west, east, south, north, f_inicio_str, f_fin_str, msg_no_imgs):
    """
    Calcula los 4 índices escalados (0-100) en Google Earth Engine y descarga
    un único arreglo NumPy en memoria (.npy).
    """
    inicializar_gee()

    region = ee.Geometry.Rectangle([west, south, east, north])
    f_fin_dt = datetime.date.fromisoformat(f_fin_str) + datetime.timedelta(days=1)

    coleccion = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(f_inicio_str, f_fin_dt.isoformat())
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 60))
    )

    cantidad_imagenes = coleccion.size().getInfo()
    if cantidad_imagenes == 0:
        raise ValueError(msg_no_imgs)

    imagen_compuesta = coleccion.map(enmascarar_nubes_s2).mean().clip(region)

    ndvi = imagen_compuesta.normalizedDifference(["B8", "B4"])
    ndmi = imagen_compuesta.normalizedDifference(["B8", "B11"])
    ndre = imagen_compuesta.normalizedDifference(["B8", "B5"])
    ndwi = imagen_compuesta.normalizedDifference(["B3", "B8"])

    s_vigor = ndvi.subtract(0.1).divide(0.7).multiply(100.0).rename("vigor")
    s_humedad = ndmi.add(0.1).divide(0.6).multiply(100.0).rename("humedad")
    s_clorofila = ndre.subtract(0.1).divide(0.6).multiply(100.0).rename("clorofila")
    s_terreno_seco = (
        ee.Image.constant(0.1).subtract(ndwi).divide(0.5).multiply(100.0).rename("seco")
    )

    imagen_4_bandas = ee.Image.cat([s_vigor, s_humedad, s_clorofila, s_terreno_seco])

    url_npy = imagen_4_bandas.getDownloadURL(
        {
            "region": region,
            "scale": 10,
            "format": "NPY",
        }
    )

    respuesta = requests.get(url_npy, timeout=60)
    respuesta.raise_for_status()

    arreglo_estructurado = np.load(BytesIO(respuesta.content))
    datos = np.stack(
        [
            arreglo_estructurado["vigor"].astype(np.float32),
            arreglo_estructurado["humedad"].astype(np.float32),
            arreglo_estructurado["clorofila"].astype(np.float32),
            arreglo_estructurado["seco"].astype(np.float32),
        ],
        axis=0,
    )
    return datos, cantidad_imagenes


# --- FUNCIONES AUXILIARES ---
def calcular_bounding_box(coord_str, idx_unidad, cantidad):
    partes = coord_str.replace("(", "").replace(")", "").split(",")
    lat_centro = float(partes[0].strip())
    lon_centro = float(partes[1].strip())

    if idx_unidad == 0:  # Hectáreas
        area_m2 = cantidad * 10000.0
        lado_metros = math.sqrt(area_m2)
    elif idx_unidad == 2:  # Kilómetros
        lado_metros = cantidad * 1000.0
        area_m2 = lado_metros**2
    else:  # Metros (idx_unidad == 1)
        lado_metros = cantidad
        area_m2 = lado_metros**2

    mitad_metros = lado_metros / 2.0
    delta_lat = mitad_metros / 111320.0
    delta_lon = mitad_metros / (111320.0 * math.cos(math.radians(lat_centro)))

    bbox = {
        "west": lon_centro - delta_lon,
        "east": lon_centro + delta_lon,
        "south": lat_centro - delta_lat,
        "north": lat_centro + delta_lat,
    }
    hectareas_totales = area_m2 / 10000.0
    return bbox, (lat_centro, lon_centro), lado_metros, hectareas_totales


def matriz_a_imagen_png_url(matriz):
    norm = Normalize(vmin=0, vmax=100)
    cmap = matplotlib.colormaps["RdYlGn"]
    rgba = cmap(norm(matriz))
    rgba[np.isnan(matriz), 3] = 0
    img = Image.fromarray((rgba * 255).astype(np.uint8))
    img_suave = img.resize(
        (max(1, img.width * 4), max(1, img.height * 4)),
        resample=Image.Resampling.BICUBIC,
    )
    buffered = BytesIO()
    img_suave.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"


def matriz_a_bytes_png(matriz):
    norm = Normalize(vmin=0, vmax=100)
    cmap = matplotlib.colormaps["RdYlGn"]
    rgba = cmap(norm(matriz))
    rgba[np.isnan(matriz), 3] = 0
    img = Image.fromarray((rgba * 255).astype(np.uint8))
    img_suave = img.resize(
        (max(1, img.width * 4), max(1, img.height * 4)),
        resample=Image.Resampling.BICUBIC,
    )
    buffered = BytesIO()
    img_suave.save(buffered, format="PNG")
    return buffered.getvalue()


# --- VISTA PREVIA EN SIDEBAR ---
st.sidebar.divider()
try:
    _, _, lado_m_prev, ha_tot_prev = calcular_bounding_box(
        coord_texto, unidad_idx, valor_tamano
    )
    st.sidebar.success(
        f"{t['preview_title']}\n\n"
        f"{t['preview_sq'].format(lado=lado_m_prev)}\n\n"
        f"{t['preview_ha'].format(ha=ha_tot_prev)}"
    )
except Exception:
    st.sidebar.error(t["coord_err_short"])

suma_pesos = p_vigor + p_humedad + p_clorofila + p_calidad
if suma_pesos == 100:
    st.sidebar.caption(t["weight_exact"])
else:
    st.sidebar.caption(t["weight_norm"].format(suma=suma_pesos))

# --- BOTÓN PRINCIPAL ---
col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
with col_btn2:
    ejecutar = st.button(t["btn_run"], type="primary")

# Contenedor dedicado para la barra de carga épica
loader_slot = st.empty()

if ejecutar:
    if suma_pesos == 0:
        st.error(t["err_zero_weights"])
    elif fecha_inicio > fecha_fin:
        st.error(t["err_dates"])
    else:
        try:
            bbox, centro, lado_m, ha_tot = calcular_bounding_box(
                coord_texto, unidad_idx, valor_tamano
            )
        except Exception:
            st.error(t["err_coords"])
            st.stop()

        w1 = p_vigor / suma_pesos
        w2 = p_humedad / suma_pesos
        w3 = p_clorofila / suma_pesos
        w4 = p_calidad / suma_pesos

        subtitulo_loader = t["loader_sub"].format(ha=ha_tot, lado=lado_m)

        try:
            # Fase 1: Conexión y enlace orbital
            renderizar_barra_epica(
                loader_slot, 20, t["loader_title"], subtitulo_loader, t["step1"]
            )
            inicializar_gee()
            time.sleep(0.25)

            # Fase 2: Filtrado orbital y máscara de nubes
            renderizar_barra_epica(
                loader_slot, 50, t["loader_title"], subtitulo_loader, t["step2"]
            )
            time.sleep(0.2)

            # Fase 3: Procesamiento de bandas espectrales en GEE
            renderizar_barra_epica(
                loader_slot, 78, t["loader_title"], subtitulo_loader, t["step3"]
            )
            datos_bandas, n_imgs = obtener_indices_gee(
                round(bbox["west"], 6),
                round(bbox["east"], 6),
                round(bbox["south"], 6),
                round(bbox["north"], 6),
                str(fecha_inicio),
                str(fecha_fin),
                t["err_no_imgs"],
            )

            # Fase 4: Ponderación y síntesis final
            renderizar_barra_epica(
                loader_slot,
                95,
                t["loader_title"],
                subtitulo_loader,
                t["step4"].format(n=n_imgs),
            )
            fiabilidad = (
                (datos_bandas[0] * w1)
                + (datos_bandas[1] * w2)
                + (datos_bandas[2] * w3)
                + (datos_bandas[3] * w4)
            )
            matriz = np.clip(fiabilidad, 0, 100)

            st.session_state["resultado_agro"] = {
                "matriz": matriz,
                "bbox": bbox,
                "centro": centro,
                "lado_m": lado_m,
                "ha_tot": ha_tot,
                "pesos": (w1, w2, w3, w4),
                "n_imgs": n_imgs,
            }

            # Completado al 100% con pausa breve para apreciar el cierre
            renderizar_barra_epica(
                loader_slot,
                100,
                t["loader_title"],
                subtitulo_loader,
                t["step_done"].format(n=n_imgs),
            )
            time.sleep(0.75)
            loader_slot.empty()

        except Exception as e:
            loader_slot.empty()
            st.error(t["err_process"].format(e=e))

# --- MOSTRAR RESULTADOS ---
if "resultado_agro" in st.session_state:
    res = st.session_state["resultado_agro"]
    matriz = res["matriz"]
    bbox = res["bbox"]
    centro = res["centro"]
    lado_m = res["lado_m"]
    ha_tot = res["ha_tot"]
    w1, w2, w3, w4 = res["pesos"]
    n_imgs = res.get("n_imgs", 0)

    if np.all(np.isnan(matriz)):
        st.warning(t["warn_all_clouds"])
        st.stop()

    promedio = float(np.nanmean(matriz))
    zona_optima = float(np.nanmean(matriz >= 70) * 100)
    zona_critica = float(np.nanmean(matriz < 40) * 100)

    st.divider()
    st.markdown(t["diag_title"].format(ha=ha_tot, lado=lado_m))
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t["m1_label"], f"{promedio:.1f}%", delta=t["m1_delta"])
    m2.metric(t["m2_label"], f"{zona_optima:.1f}%", delta=t["m2_delta"])
    m3.metric(
        t["m3_label"],
        f"{zona_critica:.1f}%",
        delta=t["m3_delta"],
        delta_color="inverse",
    )
    m4.metric(
        t["m4_label"],
        t["m4_val"].format(n=n_imgs),
        delta=t["m4_delta"].format(ha=ha_tot, lado=lado_m),
    )
    st.write("")

    if promedio >= 75:
        st.success(t["alert_opt"])
    elif promedio >= 50:
        st.warning(t["alert_mod"])
    else:
        st.error(t["alert_crit"])

    col_mapa, col_leyenda = st.columns([3.2, 1.2], gap="large")

    with col_mapa:
        mapa = folium.Map(location=centro, zoom_start=15, tiles=None)
        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
            attr="Google",
            name=t["layer_sat"],
        ).add_to(mapa)

        folium.Rectangle(
            bounds=[
                [bbox["south"], bbox["west"]],
                [bbox["north"], bbox["east"]],
            ],
            color="#ffffff",
            weight=2.5,
            dash_array="5, 5",
            fill=False,
            name=t["layer_border"],
        ).add_to(mapa)

        img_url = matriz_a_imagen_png_url(matriz)
        folium.raster_layers.ImageOverlay(
            image=img_url,
            bounds=[
                [bbox["south"], bbox["west"]],
                [bbox["north"], bbox["east"]],
            ],
            opacity=transparencia,
            name=t["layer_heat"],
        ).add_to(mapa)

        folium.LayerControl().add_to(mapa)
        st_folium(mapa, use_container_width=True, height=530, returned_objects=[])

        st.markdown(t["legend_bottom"])

    with col_leyenda:
        st.markdown(t["guide_title"])
        st.markdown(t["guide_body"])
        st.markdown(t["tech_title"])
        st.info(
            t["tech_body"].format(
                lado=lado_m,
                ha=ha_tot,
                n=n_imgs,
                w1=w1 * 100,
                w2=w2 * 100,
                w3=w3 * 100,
                w4=w4 * 100,
            )
        )

        png_bytes = matriz_a_bytes_png(matriz)
        st.download_button(
            label=t["btn_download"],
            data=png_bytes,
            file_name=f"{t['file_prefix']}_{ha_tot:.0f}ha.png",
            mime="image/png",
            use_container_width=True,
        )
else:
    st.markdown(
        f"""
<div class="empty-state">
    <h3>{t["empty_title"]}</h3>
    <p>{t["empty_body"]}</p>
</div>
""",
        unsafe_allow_html=True,
    )
