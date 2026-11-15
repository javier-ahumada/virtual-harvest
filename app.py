import base64
import datetime
import json
import math
import os
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
    page_title="TerraAgro · Fiabilidad Satelital",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
</style>
""",
    unsafe_allow_html=True,
)

# --- ENCABEZADO ---
st.markdown(
    """
<div class="header-agro">
    <div class="header-badge">🛰️ Teledetección Sentinel-2 · Google Earth Engine</div>
    <h1>🌱 TerraAgro · Monitor de Fiabilidad Satelital</h1>
    <p>Evalúa la aptitud y salud de tus potreros combinando <b>4 indicadores multiespectrales</b> de alta resolución sobre imagen aérea real.</p>
</div>
""",
    unsafe_allow_html=True,
)

# --- PANEL LATERAL ---
st.sidebar.markdown("## ⚙️ Configuración de Análisis")
st.sidebar.divider()

st.sidebar.header("📍 1. Ubicación desde Google Maps")
st.sidebar.caption(
    "Haz clic derecho en Google Maps, copia las coordenadas y pégalas aquí:"
)
coord_texto = st.sidebar.text_input(
    "Coordenadas (Latitud, Longitud)", value="-42.1500, -73.5000"
)

st.sidebar.header("📐 2. Tamaño del Área a Analizar")
unidad = st.sidebar.selectbox(
    "Unidad de medida",
    [
        "Hectáreas (superficie total)",
        "Metros (lado del cuadrado)",
        "Kilómetros (lado del cuadrado)",
    ],
)
valor_tamano = st.sidebar.number_input(
    f"Cantidad ({unidad.split()[0]})",
    min_value=0.1,
    value=25.0,
    step=1.0,
)

st.sidebar.header("📅 3. Rango de Fechas")
col_f1, col_f2 = st.sidebar.columns(2)
with col_f1:
    fecha_inicio = st.date_input("Desde", value=datetime.date(2026, 10, 15))
with col_f2:
    fecha_fin = st.date_input("Hasta", value=datetime.date(2026, 11, 12))

st.sidebar.header("🎨 4. Visualización en Mapa")
transparencia = st.sidebar.slider(
    "Opacidad de capa de colores", 0.0, 1.0, 0.65, step=0.05
)

st.sidebar.header("⚖️ 5. Importancia de cada dato (%)")
p_vigor = st.sidebar.slider("🌿 Vigor Vegetal (NDVI)", 0, 100, 35)
p_humedad = st.sidebar.slider("💧 Humedad en Cultivo (NDMI)", 0, 100, 30)
p_clorofila = st.sidebar.slider("🍃 Clorofila / Nitrógeno (NDRE)", 0, 100, 20)
p_calidad = st.sidebar.slider("☀️ Terreno Libre Agua/Nubes (NDWI)", 0, 100, 15)


# --- CONEXIÓN Y DESCARGA CON GOOGLE EARTH ENGINE ---
@st.cache_resource
def inicializar_gee():
    """
    Inicializa Google Earth Engine de forma silenciosa usando:
    1. Streamlit Secrets (cuando está desplegado en la web).
    2. Archivo local 'credenciales-gee.json' (cuando corre en tu PC).
    """
    try:
        if "gee_credentials" in st.secrets:
            info_cuenta = dict(st.secrets["gee_credentials"])
            credenciales = ee.ServiceAccountCredentials(
                info_cuenta["client_email"], key_data=json.dumps(info_cuenta)
            )
            ee.Initialize(credenciales)
            return True
    except Exception:
        pass

    if os.path.exists("credenciales-gee.json"):
        with open("credenciales-gee.json", encoding="utf-8") as f:
            info_cuenta = json.load(f)
        credenciales = ee.ServiceAccountCredentials(
            info_cuenta["client_email"], "credenciales-gee.json"
        )
        ee.Initialize(credenciales)
        return True

    st.error(
        "No se encontraron credenciales de Google Earth Engine. "
        "Agrega 'credenciales-gee.json' en la carpeta local o configura "
        "'[gee_credentials]' en Streamlit Secrets."
    )
    st.stop()


def enmascarar_nubes_s2(imagen):
    """Enmascara nubes y cirros usando la banda QA60 de Sentinel-2."""
    qa = imagen.select("QA60")
    mascara_nubes = 1 << 10
    mascara_cirros = 1 << 11
    mascara = qa.bitwiseAnd(mascara_nubes).eq(0).And(qa.bitwiseAnd(mascara_cirros).eq(0))
    return imagen.updateMask(mascara).divide(10000)


@st.cache_data(ttl=3600, show_spinner=False)
def obtener_indices_gee(west, east, south, north, f_inicio_str, f_fin_str):
    """
    Calcula los 4 índices escalados (0-100) en Google Earth Engine y descarga
    un único arreglo NumPy en memoria (.npy) en ~2-4 segundos.
    Cacheado por 1 hora: cambiar los pesos o la opacidad es instantáneo (0s).
    """
    inicializar_gee()

    region = ee.Geometry.Rectangle([west, south, east, north])

    # Google Earth Engine requiere fecha final exclusiva; sumamos 1 día
    f_fin_dt = datetime.date.fromisoformat(f_fin_str) + datetime.timedelta(days=1)

    coleccion = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(f_inicio_str, f_fin_dt.isoformat())
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 60))
    )

    cantidad_imagenes = coleccion.size().getInfo()
    if cantidad_imagenes == 0:
        raise ValueError(
            "No se encontraron imágenes Sentinel-2 disponibles (con <60% de nubes) "
            "para esa ubicación y rango de fechas. Intenta ampliar las fechas."
        )

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

    # Descarga directa en formato NPY (sin archivos temporales ni GeoTIFF)
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
def calcular_bounding_box(coord_str, unidad_sel, cantidad):
    partes = coord_str.replace("(", "").replace(")", "").split(",")
    lat_centro = float(partes[0].strip())
    lon_centro = float(partes[1].strip())

    if "Hectáreas" in unidad_sel:
        area_m2 = cantidad * 10000.0
        lado_metros = math.sqrt(area_m2)
    elif "Kilómetros" in unidad_sel:
        lado_metros = cantidad * 1000.0
        area_m2 = lado_metros**2
    else:  # Metros
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
    """Genera una imagen PNG transparente en memoria codificada en Base64 para Folium."""
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
    """Genera los bytes de un archivo PNG descargable."""
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
        coord_texto, unidad, valor_tamano
    )
    st.sidebar.success(
        f"📐 **Vista previa de parcela:**"

        f"• Cuadrado de **{lado_m_prev:.0f} m × {lado_m_prev:.0f} m**"

        f"• Superficie total: **{ha_tot_prev:.2f} ha**"
    )
except Exception:
    st.sidebar.error("Formato inválido. Usa ejemplo: -42.15, -73.50")

suma_pesos = p_vigor + p_humedad + p_clorofila + p_calidad
if suma_pesos == 100:
    st.sidebar.caption("✅ Ponderación exacta: **100%**")
else:
    st.sidebar.caption(f"ℹ️ Suma actual: **{suma_pesos}%** (se normalizará a 100%)")

# --- BOTÓN PRINCIPAL ---
col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
with col_btn2:
    ejecutar = st.button("🚀 Calcular Fiabilidad del Terreno", type="primary")

if ejecutar:
    if suma_pesos == 0:
        st.error("Debes asignar al menos un porcentaje mayor a 0 en los criterios.")
    elif fecha_inicio > fecha_fin:
        st.error("La fecha 'Desde' no puede ser posterior a la fecha 'Hasta'.")
    else:
        try:
            bbox, centro, lado_m, ha_tot = calcular_bounding_box(
                coord_texto, unidad, valor_tamano
            )
        except Exception:
            st.error(
                "Por favor revisa las coordenadas. Deben tener el formato: "
                "Latitud, Longitud (ej. -42.15, -73.5)"
            )
            st.stop()

        w1 = p_vigor / suma_pesos
        w2 = p_humedad / suma_pesos
        w3 = p_clorofila / suma_pesos
        w4 = p_calidad / suma_pesos

        with st.status(
            f"🛰️ Procesando {ha_tot:.1f} hectáreas ({lado_m:.0f}m × {lado_m:.0f}m) en Google Earth Engine...",
            expanded=True,
        ) as status:
            try:
                st.write("1. Autenticando con Google Earth Engine...")
                inicializar_gee()

                st.write("2. Consultando catálogo Sentinel-2 y calculando índices...")
                datos_bandas, n_imgs = obtener_indices_gee(
                    round(bbox["west"], 6),
                    round(bbox["east"], 6),
                    round(bbox["south"], 6),
                    round(bbox["north"], 6),
                    str(fecha_inicio),
                    str(fecha_fin),
                )

                st.write(f"3. Ponderando {n_imgs} escenas satelitales en memoria...")
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
                status.update(
                    label=f"✅ Análisis completado ({n_imgs} imágenes procesadas)",
                    state="complete",
                    expanded=False,
                )

            except Exception as e:
                status.update(label="❌ Error en el procesamiento", state="error")
                st.error(f"Ocurrió un error al procesar los datos: {e}")

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
        st.warning(
            "Todos los píxeles de la parcela estaban cubiertos por nubes en las "
            "fechas seleccionadas. Prueba ampliar el rango de fechas."
        )
        st.stop()

    promedio = float(np.nanmean(matriz))
    zona_optima = float(np.nanmean(matriz >= 70) * 100)
    zona_critica = float(np.nanmean(matriz < 40) * 100)

    st.divider()
    st.markdown(
        f"### 📊 Diagnóstico de Parcela · {ha_tot:.1f} ha "
        f"({lado_m:.0f}m × {lado_m:.0f}m)"
    )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🌱 Fiabilidad Global", f"{promedio:.1f}%", delta="Índice compuesto")
    m2.metric("✅ Superficie Óptima", f"{zona_optima:.1f}%", delta="Score > 70%")
    m3.metric(
        "⚠️ Superficie Crítica",
        f"{zona_critica:.1f}%",
        delta="Score < 40%",
        delta_color="inverse",
    )
    m4.metric(
        "🛰️ Escenas Analizadas",
        f"{n_imgs} img",
        delta=f"{ha_tot:.1f} ha ({lado_m:.0f}m lado)",
    )
    st.write("")

    if promedio >= 75:
        st.success(
            "🌿 Estado Óptimo: El terreno presenta condiciones favorables "
            "y equilibradas en los 4 indicadores multiespectrales."
        )
    elif promedio >= 50:
        st.warning(
            "🌾 Estado Moderado: Se detectan sectores con posible estrés hídrico "
            "o vigor medio que requieren monitoreo en terreno."
        )
    else:
        st.error(
            "🚨 Estado Crítico: Baja fiabilidad detectada. Se recomienda revisar "
            "humedad del suelo, niveles de nitrógeno o anegamiento."
        )

    col_mapa, col_leyenda = st.columns([3.2, 1.2], gap="large")

    with col_mapa:
        mapa = folium.Map(location=centro, zoom_start=15, tiles=None)
        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
            attr="Google",
            name="Google Satélite",
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
            name="Límite Parcela",
        ).add_to(mapa)

        img_url = matriz_a_imagen_png_url(matriz)
        folium.raster_layers.ImageOverlay(
            image=img_url,
            bounds=[
                [bbox["south"], bbox["west"]],
                [bbox["north"], bbox["east"]],
            ],
            opacity=transparencia,
            name="Fiabilidad de Terreno",
        ).add_to(mapa)

        folium.LayerControl().add_to(mapa)
        st_folium(mapa, use_container_width=True, height=530, returned_objects=[])

        st.markdown(
            """
🟢 **70% - 100%**: Fiabilidad Alta / Óptima  
🟡 **45% - 69%**: Fiabilidad Media / Aceptable  
🔴 **0% - 44%**: Zona Crítica / Revisar Terreno
"""
        )

    with col_leyenda:
        st.markdown("### 🧭 Guía de Lectura")
        st.markdown(
            """
🟢 **70% - 100% (Óptimo)**  
Terreno altamente fiable, vigoroso y con buen balance hídrico.

🟡 **45% - 69% (Moderado)**  
Rendimiento aceptable; conviene vigilar su evolución en los próximos días.

🔴 **0% - 44% (Crítico)**  
Zona problema: posible suelo desnudo, sequía, falta de nitrógeno o exceso de agua.
"""
        )
        st.markdown("### 📋 Ficha Técnica")
        st.info(
            f"Dimensiones reales:"

            f"- Ancho: {lado_m:.0f} m"

            f"- Alto: {lado_m:.0f} m"
            
            f"- Superficie: {ha_tot:.2f} ha"

            f"- Escenas Sentinel-2: {n_imgs}"

            f"Pesos aplicados:"

            f"- 🌿 Vigor: {w1*100:.0f}%"

            f"- 💧 Humedad: {w2*100:.0f}%"

            f"- 🍃 Clorofila: {w3*100:.0f}%"
            
            f"- ☀️ Drenaje: {w4*100:.0f}%"
        )

        png_bytes = matriz_a_bytes_png(matriz)
        st.download_button(
            label="📥 Descargar Mapa (PNG)",
            data=png_bytes,
            file_name=f"fiabilidad_parcela_{ha_tot:.0f}ha.png",
            mime="image/png",
            use_container_width=True,
        )
else:
    st.markdown(
        """
<div class="empty-state">
    <h3>🛰️ Listo para analizar tu predio</h3>
    <p>Configura las coordenadas, el tamaño y los pesos en el panel izquierdo, luego presiona <b>"Calcular Fiabilidad del Terreno"</b>.</p>
</div>
""",
        unsafe_allow_html=True,
    )
