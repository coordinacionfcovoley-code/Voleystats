"""
Identidad visual de Club Ferro Carril Oeste (verde y blanco) para VoleyStats.
Todo lo relacionado con el "look" vive acá: colores, CSS, encabezado y helpers de gráficos.

Para poner el escudo oficial: guardá una imagen en  assets/escudo.png  (fondo transparente,
idealmente cuadrada). Si no existe, se muestra un monograma "FCO" provisorio.
"""

import os
import base64
import streamlit as st

# ---------------------------------------------------------------- paleta
VERDE = "#0B6B3A"
VERDE_OSCURO = "#064E2B"
VERDE_MEDIO = "#7FBF97"
VERDE_CLARO = "#E6F2EA"
TINTA = "#14231B"
GRIS = "#B8C2BC"
ROJO = "#C0392B"
NARANJA = "#E08A3C"

_OTROS = ["#6B7280", "#D97706", "#7C3AED", "#0EA5E9", "#DB2777", "#64748B",
          "#A16207", "#0891B2", "#9333EA", "#EA580C", "#475569", "#BE185D"]

NOMBRES_CORTOS = {
    "Club Ferro Carril Oeste": "Ferro",
    "Club Atlético Boca Juniors": "Boca",
    "Club Atlético River Plate": "River",
    "Club Atlético San Lorenzo de Almagro": "San Lorenzo",
    "Club Atlético Velez Sarsfield": "Vélez",
    "Club Banco Provincia de Buenos Aires La Plata": "Banco Provincia",
    "Club Estudiantes de La Plata": "Estudiantes LP",
    "Club Gimnasia y Esgrima de La Plata": "Gimnasia LP",
    'Instituto Educativo San Gregorio "El Iluminador"': "San Gregorio",
    "Universidad Nacional de Tres de Febrero": "UNTREF",
    "Universidad Nacional de la Matanza": "UNLaM",
}


def short_team(name):
    """Nombre corto para mostrar. Si no está en el diccionario, limpia prefijos comunes."""
    if not isinstance(name, str):
        return name
    if name in NOMBRES_CORTOS:
        return NOMBRES_CORTOS[name]
    if name.startswith("Club Social, Deportivo y Cultural Argentino"):
        return "Argentino de Castelar"
    for pref in ("Club Atlético ", "Club "):
        if name.startswith(pref):
            return name[len(pref):]
    return name


def es_ferro(name):
    return isinstance(name, str) and "ferro" in name.lower()


def team_colors(teams):
    """Ferro en verde, el resto en tonos que no se confunden con el verde."""
    cmap, i = {}, 0
    for t in teams:
        if es_ferro(t):
            cmap[t] = VERDE
        else:
            cmap[t] = _OTROS[i % len(_OTROS)]
            i += 1
    return cmap


def ranking_colors(teams):
    """Para barras de ranking: Ferro verde, resto gris."""
    return {t: (VERDE if es_ferro(t) else GRIS) for t in teams}


def ferro_record(matches_df):
    """(PJ, ganados, perdidos, sets a favor, sets en contra) de Ferro."""
    pj = g = p = sf = sc = 0
    for _, r in matches_df.iterrows():
        if es_ferro(r["home_team"]):
            a, b = int(r["home_sets"]), int(r["away_sets"])
        elif es_ferro(r["away_team"]):
            a, b = int(r["away_sets"]), int(r["home_sets"])
        else:
            continue
        pj += 1
        sf += a
        sc += b
        if a > b:
            g += 1
        elif b > a:
            p += 1
    return pj, g, p, sf, sc


# ---------------------------------------------------------------- escudo
def _escudo_html():
    ruta = os.path.join(os.path.dirname(__file__), "assets", "escudo.png")
    if os.path.exists(ruta):
        with open(ruta, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img class="fc-badge" src="data:image/png;base64,{b64}" alt="Escudo Ferro">'
    return '<div class="fc-badge fc-badge-mono">FCO</div>'


# ---------------------------------------------------------------- CSS
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');

:root {
  --verde: #0B6B3A; --verde-osc: #064E2B; --verde-med: #7FBF97; --verde-cl: #E6F2EA;
  --tinta: #14231B; --gris: #5B6B62; --linea: #D5E3DA;
}
html, body, [class*="css"] { font-family: 'Inter', 'Segoe UI', sans-serif; color: var(--tinta); }
h1, h2, h3, h4 { font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif; letter-spacing: .2px; color: var(--verde-osc); }
h3 { font-weight: 700; }
.block-container { padding-top: 1.4rem; max-width: 1400px; }
footer, .stDeployButton, #MainMenu { visibility: hidden; height: 0; }

/* ---- encabezado ---- */
.fc-hero {
  background: linear-gradient(120deg, var(--verde-osc) 0%, var(--verde) 70%);
  border-radius: 14px 14px 0 0; padding: 22px 28px; color: #fff;
  display: flex; align-items: center; justify-content: space-between; gap: 20px; flex-wrap: wrap;
}
.fc-hero-left { display: flex; align-items: center; gap: 18px; }
.fc-badge { width: 74px; height: 74px; border-radius: 50%; background: #fff; object-fit: contain; padding: 4px; flex: none; }
.fc-badge-mono {
  display: flex; align-items: center; justify-content: center; color: var(--verde);
  font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: 1.7rem; border: 3px solid var(--verde-med);
}
.fc-kicker { font-size: .8rem; letter-spacing: 2px; text-transform: uppercase; color: #CFE8D8; font-weight: 600; }
.fc-title { font-family: 'Barlow Condensed', sans-serif; font-size: 2.5rem; font-weight: 800; line-height: 1.05; color: #fff; }
.fc-sub { font-size: .95rem; color: #DDEFE3; margin-top: 2px; }
.fc-chips { display: flex; gap: 10px; flex-wrap: wrap; }
.fc-chip { background: rgba(255,255,255,.13); border: 1px solid rgba(255,255,255,.28); border-radius: 12px; padding: 8px 16px; text-align: center; min-width: 78px; }
.fc-chip b { display: block; font-family: 'Barlow Condensed', sans-serif; font-size: 1.7rem; line-height: 1.1; }
.fc-chip span { font-size: .68rem; letter-spacing: 1px; text-transform: uppercase; color: #CFE8D8; }
.fc-stripe { height: 8px; background: repeating-linear-gradient(90deg, #fff 0 40px, var(--verde) 40px 80px); border: 1px solid var(--linea); border-top: none; border-radius: 0 0 14px 14px; margin-bottom: 1.2rem; }

/* ---- tarjetas KPI (mantiene las clases originales) ---- */
.metric-card {
  background: #fff; border: 1px solid var(--linea); border-top: 4px solid var(--verde);
  border-radius: 10px; padding: 14px 10px; text-align: center; box-shadow: 0 2px 6px rgba(6,78,43,.06);
}
.metric-val { font-family: 'Barlow Condensed', sans-serif; font-size: 2.3rem; font-weight: 800; color: var(--verde-osc); line-height: 1.05; }
.metric-lbl { font-size: .74rem; color: var(--gris); text-transform: uppercase; letter-spacing: .8px; font-weight: 600; }
.info-box { background: var(--verde-cl); border-left: 4px solid var(--verde); padding: 12px; border-radius: 6px; }

/* ---- st.metric ---- */
[data-testid="stMetric"] { background: #fff; border: 1px solid var(--linea); border-left: 4px solid var(--verde); border-radius: 10px; padding: 10px 14px; }
[data-testid="stMetricValue"] { font-family: 'Barlow Condensed', sans-serif; font-weight: 800; color: var(--verde-osc); }

/* ---- pestañas ---- */
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 2px solid var(--linea); }
.stTabs [data-baseweb="tab"] { font-weight: 600; padding: 10px 16px; border-radius: 8px 8px 0 0; }
.stTabs [aria-selected="true"] { color: var(--verde) !important; background: var(--verde-cl); }
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--verde) !important; height: 3px; }

/* ---- barra lateral ---- */
[data-testid="stSidebar"] { background: var(--verde-cl); border-right: 1px solid var(--linea); }
[data-testid="stSidebar"] h1 { font-size: 1.9rem; margin: 0; }
.fc-side-brand { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
.fc-side-brand .fc-badge { width: 52px; height: 52px; font-size: 1.1rem; border-width: 2px; }
.fc-side-name { font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: 1.35rem; line-height: 1.05; color: var(--verde-osc); }
.fc-side-name small { display: block; font-family: 'Inter', sans-serif; font-weight: 500; font-size: .72rem; color: var(--gris); letter-spacing: .5px; }

/* ---- botones ---- */
.stButton > button { border-radius: 8px; border: 1px solid var(--verde); color: var(--verde); font-weight: 600; }
.stButton > button:hover { background: var(--verde); color: #fff; border-color: var(--verde); }

.fc-footer { text-align: center; color: var(--gris); font-size: .8rem; margin-top: 2.5rem; padding-top: 12px; border-top: 1px solid var(--linea); }
</style>
"""


def inject_css():
    st.markdown(_CSS, unsafe_allow_html=True)


def sidebar_brand():
    st.markdown(
        f'<div class="fc-side-brand">{_escudo_html()}'
        '<div class="fc-side-name">Ferro Carril Oeste<small>Vóley femenino · VoleyStats</small></div></div>',
        unsafe_allow_html=True,
    )


def render_header(matches_df):
    pj, g, p, sf, sc = ferro_record(matches_df)
    chips = ""
    if pj:
        chips = (f'<div class="fc-chip"><b>{pj}</b><span>Jugados</span></div>'
                 f'<div class="fc-chip"><b>{g}</b><span>Ganados</span></div>'
                 f'<div class="fc-chip"><b>{p}</b><span>Perdidos</span></div>'
                 f'<div class="fc-chip"><b>{sf}-{sc}</b><span>Sets</span></div>')
    html = (
        '<div class="fc-hero"><div class="fc-hero-left">' + _escudo_html() +
        '<div><div class="fc-kicker">Club Ferro Carril Oeste · Vóley femenino</div>'
        '<div class="fc-title">Tablero de rendimiento</div>'
        '<div class="fc-sub">División de Honor Damas · Metro 2026 · análisis punto a punto desde Data Volley</div></div></div>'
        f'<div class="fc-chips">{chips}</div></div><div class="fc-stripe"></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def footer():
    st.markdown('<div class="fc-footer">Club Ferro Carril Oeste · Vóley femenino · VoleyStats</div>',
                unsafe_allow_html=True)
